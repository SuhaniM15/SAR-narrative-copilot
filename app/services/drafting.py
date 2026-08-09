"""Draft generation orchestration: evidence + retrieval → grounded 5 Ws JSON."""

from __future__ import annotations

import json
from typing import Optional

from app.adapters.llm import FakeLLMAdapter, GroqAdapter, LLMAdapter, LLMError, get_llm_adapter
from app.schemas.drafting import DraftGenerationResult, StructuredNarrative
from app.schemas.evidence import EvidencePack
from app.schemas.retrieval import RetrievalResult
from app.services.grounding import GroundingError, validate_narrative_grounding
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
) -> DraftGenerationResult:
    """Call the LLM and validate grounding. Does not persist to DB."""
    adapter: LLMAdapter = llm or get_llm_adapter()
    messages = build_draft_messages(pack, retrieval)

    try:
        completion = adapter.complete(messages, temperature=temperature)
    except LLMError as exc:
        raise UpstreamLLMError(str(exc)) from exc

    try:
        payload = json.loads(completion.content)
    except json.JSONDecodeError as exc:
        raise UpstreamLLMError(
            f"LLM returned non-JSON content: {completion.content[:400]}"
        ) from exc

    try:
        narrative = StructuredNarrative.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError
        raise UpstreamLLMError(f"LLM JSON did not match StructuredNarrative: {exc}") from exc

    try:
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
