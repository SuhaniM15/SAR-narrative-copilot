from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CaseStatus(str, Enum):
    OPEN = "open"
    DRAFTED = "drafted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class Typology(str, Enum):
    STRUCTURING = "structuring"
    LAYERING = "layering"
    STRUCTURING_LAYERING = "structuring_layering"


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_alert_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default=CaseStatus.OPEN.value, index=True)
    typology: Mapped[str] = mapped_column(String(50), default=Typology.STRUCTURING_LAYERING.value)
    jurisdiction: Mapped[str] = mapped_column(String(50), default="FinCEN")
    alert_reason: Mapped[str] = mapped_column(Text)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Mock KYC summary (embedded for v1; avoids separate KYC service)
    customer_id: Mapped[str] = mapped_column(String(100))
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_occupation: Mapped[str] = mapped_column(String(255))
    customer_expected_activity: Mapped[str] = mapped_column(Text)
    customer_country: Mapped[str] = mapped_column(String(100), default="US")

    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    transactions = relationship(
        "Transaction",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Transaction.occurred_at",
    )
    drafts = relationship(
        "NarrativeDraft",
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="NarrativeDraft.version",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    txn_ref: Mapped[str] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    txn_type: Mapped[str] = mapped_column(String(50))  # deposit, wire_out, transfer, etc.
    counterparty: Mapped[str] = mapped_column(String(255))
    location: Mapped[str] = mapped_column(String(255), default="")
    channel: Mapped[str] = mapped_column(String(100), default="branch")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    narrative_note: Mapped[str] = mapped_column(Text, default="")

    case = relationship("Case", back_populates="transactions")


class NarrativeDraft(Base):
    __tablename__ = "narrative_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    who: Mapped[str] = mapped_column(Text, default="")
    what: Mapped[str] = mapped_column(Text, default="")
    when: Mapped[str] = mapped_column(Text, default="")
    where: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    how: Mapped[str] = mapped_column(Text, default="")
    full_narrative: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    retrieval_citations_json: Mapped[str] = mapped_column(Text, default="[]")
    evidence_txn_refs_json: Mapped[str] = mapped_column(Text, default="[]")
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    case = relationship("Case", back_populates="drafts")
