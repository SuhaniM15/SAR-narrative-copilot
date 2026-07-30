from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: str = "analyst"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class TransactionCreate(BaseModel):
    txn_ref: str
    amount: float
    currency: str = "USD"
    txn_type: str
    counterparty: str
    location: str = ""
    channel: str = "branch"
    occurred_at: datetime
    narrative_note: str = ""


class TransactionOut(TransactionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int


class CaseCreate(BaseModel):
    external_alert_id: str
    title: str
    typology: str = "structuring_layering"
    jurisdiction: str = "FinCEN"
    alert_reason: str
    risk_score: Optional[float] = None
    customer_id: str
    customer_name: str
    customer_occupation: str
    customer_expected_activity: str
    customer_country: str = "US"
    transactions: list[TransactionCreate] = Field(default_factory=list)


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_alert_id: str
    title: str
    status: str
    typology: str
    jurisdiction: str
    alert_reason: str
    risk_score: Optional[float]
    customer_id: str
    customer_name: str
    customer_occupation: str
    customer_expected_activity: str
    customer_country: str
    assigned_to_id: Optional[int]
    created_by_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    transactions: list[TransactionOut] = Field(default_factory=list)


class CaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_alert_id: str
    title: str
    status: str
    typology: str
    customer_name: str
    risk_score: Optional[float]
    created_at: datetime


class DraftUpdate(BaseModel):
    who: Optional[str] = None
    what: Optional[str] = None
    when: Optional[str] = None
    where: Optional[str] = None
    why: Optional[str] = None
    how: Optional[str] = None
    full_narrative: Optional[str] = None


class DraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    case_id: int
    version: int
    who: str
    what: str
    when: str
    where: str
    why: str
    how: str
    full_narrative: str
    model_name: Optional[str]
    retrieval_citations_json: str
    evidence_txn_refs_json: str
    created_by_id: Optional[int]
    created_at: datetime


class CaseDecision(BaseModel):
    comment: str = ""


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    entity_type: str
    entity_id: Optional[int]
    actor_id: Optional[int]
    actor_role: Optional[str]
    summary: str
    detail_json: str
    created_at: datetime


class MessageOut(BaseModel):
    detail: str
    data: Optional[dict[str, Any]] = None
