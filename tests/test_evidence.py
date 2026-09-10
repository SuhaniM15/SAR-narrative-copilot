"""Unit tests for the evidence pack — no HTTP, no LLM."""

from datetime import datetime, timezone

from app.models.case import Case, CaseStatus, Transaction, Typology
from app.services.evidence import build_evidence_pack, normalize_typologies


def _sample_case(**overrides) -> Case:
    data = dict(
        id=1,
        external_alert_id="ALT-EVIDENCE-1",
        title="Evidence pack test",
        status=CaseStatus.OPEN.value,
        typology=Typology.STRUCTURING_LAYERING.value,
        jurisdiction="FinCEN",
        alert_reason="Near-threshold deposits then offshore wire",
        risk_score=0.88,
        customer_id="CUST-1",
        customer_name="Jordan Hale",
        customer_occupation="Retail consultant",
        customer_expected_activity="Payroll under $3,000/week",
        customer_country="US",
        transactions=[
            Transaction(
                id=10,
                case_id=1,
                txn_ref="TXN-1001",
                amount=9800.0,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash - Branch 12",
                location="Miami, FL",
                channel="branch",
                occurred_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
                narrative_note="Just below CTR threshold",
            ),
            Transaction(
                id=11,
                case_id=1,
                txn_ref="TXN-1004",
                amount=28000.0,
                currency="USD",
                txn_type="wire_out",
                counterparty="Offshore Holdings Ltd",
                location="Cayman Islands",
                channel="wire",
                occurred_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
                narrative_note="Rapid offshore exit",
            ),
        ],
    )
    data.update(overrides)
    return Case(**data)


def test_normalize_typologies_splits_combined_label():
    assert normalize_typologies("structuring_layering") == ["structuring", "layering"]
    assert normalize_typologies("structuring") == ["structuring"]
    assert normalize_typologies("layering") == ["layering"]


def test_build_evidence_pack_separates_rag_query_and_llm_context():
    pack = build_evidence_pack(_sample_case())

    assert pack.case.external_alert_id == "ALT-EVIDENCE-1"
    assert pack.case.typology == "structuring_layering"  # raw DB value preserved
    assert pack.typologies == ["structuring", "layering"]
    assert pack.allowed_txn_refs == ["TXN-1001", "TXN-1004"]

    # rag_query: compact retrieval seed — typology theme, not full txn ledger
    assert "structuring" in pack.rag_query
    assert "layering" in pack.rag_query
    assert "Near-threshold deposits then offshore wire" in pack.rag_query
    assert "cash_deposit" in pack.rag_query
    assert "TXN-1001" not in pack.rag_query  # txn IDs belong in llm_context

    # llm_context: full factual brief for the model
    assert "TXN-1001" in pack.llm_context
    assert "TXN-1004" in pack.llm_context
    assert "Jordan Hale" in pack.llm_context
    assert "Near-threshold deposits then offshore wire" in pack.llm_context
    assert "Verified typology findings" in pack.llm_context
    assert any(f.rule_id.startswith("STRUCT") or f.rule_id.startswith("LAYER") for f in pack.findings)
