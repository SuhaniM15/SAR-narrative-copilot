"""Draft generation schemas — structured FinCEN 5 Ws + How output."""

from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.retrieval import Citation


class StructuredNarrative(BaseModel):
    who: str = ""
    what: str = ""
    when: str = ""
    where: str = ""
    why: str = ""
    how: str = ""
    full_narrative: str = ""
    # Txn refs the model claims it used — must be subset of EvidencePack.allowed_txn_refs
    evidence_txn_refs: list[str] = Field(default_factory=list)


class DraftGenerationResult(BaseModel):
    narrative: StructuredNarrative
    model_name: str
    citations: list[Citation] = Field(default_factory=list)
    rag_query: str = ""
    # True when output passed txn-ref grounding checks
    grounded: bool = True
    grounding_notes: list[str] = Field(default_factory=list)


class LLMMessage(BaseModel):
    role: str
    content: str


class LLMCompletion(BaseModel):
    content: str
    model_name: str
    raw: Optional[dict] = None
