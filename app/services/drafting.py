"""Draft generation orchestration: evidence + retrieval → grounded 5 Ws JSON.

Pipeline: EvidencePack → PII mask (LLM-bound copy) → prompt → LLM → grounding gate.
"""

from __future__ import annotations

import json
from typing import Optional

from pydantic import ValidationError

from app.adapters.llm import FakeLLMAdapter, GroqAdapter, LLMAdapter, LLMError, get_llm_adapter
from app.schemas.drafting import DraftGenerationResult, StructuredNarrative
from app.schemas.evidence import EvidencePack
from app.schemas.retrieval import RetrievalResult
from app.services.grounding import GroundingError, validate_narrative_grounding
from app.services.pii import mask_evidence_pack_for_llm
from app.services.prompting import build_draft_messages


class DraftGenerationError(Exception):
    """Base for draft pipeline failures."""


class DraftValidationError(DraftGenerationError):
    """Client/data issues — map to HTTP 400 (grounding, empty evidence/retrieval)."""


class UpstreamLLMError(DraftGenerationError):
    """Model/provider issues — map to HTTP 502 (timeout, API error, bad shape)."""


def generate_structured_draft(
    pack: EvidencePack,
    retrieval: RetrievalResult,
    *,
    llm: Optional[LLMAdapter] = None,
    temperature: float = 0.2,
    apply_pii_mask: bool = True,
) -> DraftGenerationResult:
    """Call the LLM and validate grounding. Does not persist to DB.

    When apply_pii_mask is True (default), a masked copy of the pack is sent to
    the model. The caller's original pack is never mutated.
    """
    adapter: LLMAdapter = llm or get_llm_adapter()
    llm_pack = pack
    if apply_pii_mask:
        llm_pack = mask_evidence_pack_for_llm(pack).pack

    messages = build_draft_messages(llm_pack, retrieval)

    try:
        completion = adapter.complete(messages, temperature=temperature)
    except LLMError as exc:
        raise UpstreamLLMError(str(exc)) from exc

    try:
        payload = json.loads(completion.content)
    except json.JSONDecodeError as exc:
        # Malformed JSON must not be saved — treat as validation failure (400).
        raise DraftValidationError(
            f"LLM returned non-JSON content: {completion.content[:400]}"
        ) from exc

    if not isinstance(payload, dict):
        raise DraftValidationError(
            f"LLM JSON must be an object, got {type(payload).__name__}"
        )

    try:
        narrative = StructuredNarrative.model_validate(payload)
    except ValidationError as exc:
        raise DraftValidationError(
            f"LLM JSON did not match StructuredNarrative: {exc}"
        ) from exc

    try:
        # Allow-list always from the real (unmasked) pack — txn refs are unmasked.
        notes = validate_narrative_grounding(narrative, pack.allowed_txn_refs)
    except GroundingError as exc:
        raise DraftValidationError(str(exc)) from exc

    return DraftGenerationResult(
        narrative=narrative,
        model_name=completion.model_name,
        citations=retrieval.citations,
        rag_query=retrieval.query,
        grounded=True,
        grounding_notes=notes,
    )


__all__ = [
    "DraftGenerationError",
    "DraftValidationError",
    "UpstreamLLMError",
    "generate_structured_draft",
    "FakeLLMAdapter",
    "GroqAdapter",
]
