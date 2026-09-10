"""Evidence pack — the only factual input the LLM is allowed to use.

Interview framing: we do not dump ORM rows into a prompt. We assemble a
deterministic, serializable brief so drafts are grounded, testable, and auditable.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceTransaction(BaseModel):
    txn_ref: str
    amount: float
    currency: str
    txn_type: str
    counterparty: str
    location: str
    channel: str
    occurred_at: datetime
    narrative_note: str = ""


class EvidenceCustomer(BaseModel):
    customer_id: str
    name: str
    occupation: str
    expected_activity: str
    country: str


class EvidenceCaseMeta(BaseModel):
    case_id: int
    external_alert_id: str
    title: str
    status: str
    # Raw DB value kept for fidelity / audit
    typology: str
    jurisdiction: str
    alert_reason: str
    risk_score: Optional[float] = None


class TypologyFinding(BaseModel):
    """Deterministic rule hit — verified before the LLM sees the case."""

    rule_id: str
    finding: str
    evidence_txn_refs: list[str] = Field(default_factory=list)


class EvidencePack(BaseModel):
    """Structured case brief for RAG query + LLM prompting."""

    case: EvidenceCaseMeta
    customer: EvidenceCustomer
    transactions: list[EvidenceTransaction] = Field(default_factory=list)
    # Normalized tags for multi-label retrieval (e.g. structuring + layering)
    typologies: list[str] = Field(default_factory=list)
    # Hard allow-list used later to reject invented transaction IDs in drafts
    allowed_txn_refs: list[str] = Field(default_factory=list)
    # Deterministic typology rule findings (explainable; not ML)
    findings: list[TypologyFinding] = Field(default_factory=list)
    # Short retrieval query — optimized for similarity search, not full detail
    rag_query: str = ""
    # Full factual brief — the only case facts the LLM may use
    llm_context: str = ""
