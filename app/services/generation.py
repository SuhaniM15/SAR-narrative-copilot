"""End-to-end draft generation for a case: pack → RAG → LLM → persist + audit.

This is the Module 4 orchestration layer. The API route stays thin.
"""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from app.adapters.chroma_retriever import ChromaKnowledgeStore
from app.adapters.llm import LLMAdapter
from app.models.case import Case, CaseStatus, NarrativeDraft
from app.models.user import User
from app.services.audit import log_event
from app.services.drafting import (
    DraftValidationError,
    UpstreamLLMError,
    generate_structured_draft,
)
from app.services.evidence import build_evidence_pack
from app.services.retrieval import retrieve_policy_context

# Statuses where regeneration is allowed (not mid-review / terminal).
_GENERATABLE_STATUSES = {CaseStatus.OPEN.value, CaseStatus.DRAFTED.value}


class GenerationNotAllowed(ValueError):
    pass


def generate_and_persist_draft(
    db: Session,
    case: Case,
    actor: User,
    *,
    llm: Optional[LLMAdapter] = None,
    store: Optional[ChromaKnowledgeStore] = None,
) -> NarrativeDraft:
    """Run the AI pipeline and append a new NarrativeDraft version.

    On failure: raises and writes nothing.
    - GenerationNotAllowed / DraftValidationError → HTTP 400
    - UpstreamLLMError → HTTP 502
    """
    if case.status not in _GENERATABLE_STATUSES:
        raise GenerationNotAllowed(
            f"Cannot generate draft while case status is '{case.status}'. "
            f"Allowed: {sorted(_GENERATABLE_STATUSES)}"
        )

    if not case.transactions:
        raise DraftValidationError(
            "Case has no transactions; cannot generate a grounded SAR draft."
        )

    pack = build_evidence_pack(case)
    retrieval = retrieve_policy_context(pack, store=store)

    if not retrieval.citations:
        raise DraftValidationError(
            "Retrieval returned no policy citations; cannot generate a grounded draft. "
            "Rebuild the knowledge index or check knowledge docs."
        )

    result = generate_structured_draft(pack, retrieval, llm=llm)

    next_version = (max((d.version for d in case.drafts), default=0) + 1)
    narrative = result.narrative

    citations_payload = [c.model_dump(mode="json") for c in result.citations]
    draft = NarrativeDraft(
        case_id=case.id,
        version=next_version,
        who=narrative.who,
        what=narrative.what,
        when=narrative.when,
        where=narrative.where,
        why=narrative.why,
        how=narrative.how,
        full_narrative=narrative.full_narrative,
        model_name=result.model_name,
        retrieval_citations_json=json.dumps(citations_payload),
        evidence_txn_refs_json=json.dumps(narrative.evidence_txn_refs),
        created_by_id=actor.id,
    )
    case.drafts.append(draft)
    case.status = CaseStatus.DRAFTED.value

    db.add(draft)
    db.flush()

    log_event(
        db,
        event_type="DRAFT_GENERATED",
        summary=f"Draft v{draft.version} generated for case {case.external_alert_id}",
        actor=actor,
        entity_id=case.id,
        detail={
            "draft_id": draft.id,
            "version": draft.version,
            "model_name": result.model_name,
            "citation_ids": [c.doc_id for c in result.citations],
            "evidence_txn_refs": narrative.evidence_txn_refs,
            "grounding_notes": result.grounding_notes,
            "rag_query": result.rag_query,
            "status": case.status,
        },
    )
    db.commit()
    db.refresh(draft)
    return draft
