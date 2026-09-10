"""Deterministic typology rule engine tests."""

from datetime import datetime, timedelta, timezone

from app.schemas.evidence import EvidenceTransaction
from app.services.rules import evaluate_typology_rules


def _txn(
    ref: str,
    *,
    amount: float,
    txn_type: str,
    location: str,
    day: int,
    hour: int = 10,
) -> EvidenceTransaction:
    return EvidenceTransaction(
        txn_ref=ref,
        amount=amount,
        currency="USD",
        txn_type=txn_type,
        counterparty="X",
        location=location,
        channel="branch" if "cash" in txn_type else "wire",
        occurred_at=datetime(2026, 7, day, hour, 0, tzinfo=timezone.utc),
    )


def test_seed_like_case_triggers_struct_and_layer_rules():
    txns = [
        _txn("TXN-1001", amount=9800, txn_type="cash_deposit", location="Miami, FL", day=1),
        _txn("TXN-1002", amount=9500, txn_type="cash_deposit", location="Fort Lauderdale, FL", day=2),
        _txn("TXN-1003", amount=9700, txn_type="cash_deposit", location="Miami, FL", day=4),
        _txn(
            "TXN-1004",
            amount=28000,
            txn_type="wire_out",
            location="Cayman Islands",
            day=5,
            hour=12,
        ),
    ]
    findings = evaluate_typology_rules(txns)
    ids = {f.rule_id for f in findings}
    assert "STRUCT-001" in ids
    assert "STRUCT-002" in ids
    assert "LAYER-001" in ids
    assert "LAYER-002" in ids

    struct001 = next(f for f in findings if f.rule_id == "STRUCT-001")
    assert set(struct001.evidence_txn_refs) >= {"TXN-1001", "TXN-1002", "TXN-1003"}


def test_no_rules_on_benign_single_payroll():
    txns = [
        _txn("TXN-1", amount=2500, txn_type="ach_in", location="Miami, FL", day=1),
    ]
    assert evaluate_typology_rules(txns) == []
