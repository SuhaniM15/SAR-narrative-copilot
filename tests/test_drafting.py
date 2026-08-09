"""Unit tests for Groq drafting path — FakeLLM only, no API key required."""

import json

import pytest

from app.adapters.llm import FakeLLMAdapter
from app.schemas.drafting import StructuredNarrative
from app.schemas.evidence import (
    EvidenceCaseMeta,
    EvidenceCustomer,
    EvidencePack,
    EvidenceTransaction,
)
from app.schemas.retrieval import Citation, RetrievalResult
from app.services.drafting import DraftValidationError, generate_structured_draft
from app.services.grounding import GroundingError, validate_narrative_grounding
from app.services.prompting import build_draft_messages
from datetime import datetime, timezone


def _pack() -> EvidencePack:
    return EvidencePack(
        case=EvidenceCaseMeta(
            case_id=1,
            external_alert_id="ALT-1",
            title="Test",
            status="open",
            typology="structuring_layering",
            jurisdiction="FinCEN",
            alert_reason="Near-threshold deposits then wire",
            risk_score=0.9,
        ),
        customer=EvidenceCustomer(
            customer_id="CUST-1",
            name="Jordan Hale",
            occupation="Consultant",
            expected_activity="Payroll",
            country="US",
        ),
        transactions=[
            EvidenceTransaction(
                txn_ref="TXN-1001",
                amount=9800,
                currency="USD",
                txn_type="cash_deposit",
                counterparty="Cash",
                location="Miami, FL",
                channel="branch",
                occurred_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            ),
            EvidenceTransaction(
                txn_ref="TXN-1004",
                amount=28000,
                currency="USD",
                txn_type="wire_out",
                counterparty="Offshore Holdings Ltd",
                location="Cayman Islands",
                channel="wire",
                occurred_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
            ),
        ],
        typologies=["structuring", "layering"],
        allowed_txn_refs=["TXN-1001", "TXN-1004"],
        rag_query="structuring layering FinCEN",
        llm_context="Customer Jordan Hale. TXN-1001 deposit. TXN-1004 wire.",
    )


def _retrieval() -> RetrievalResult:
    return RetrievalResult(
        query="structuring layering FinCEN",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="Answer Who What When Where Why How.",
                typologies=["general", "fincen"],
                distance=0.1,
            )
        ],
        policy_context="[fincen_5ws] Answer Who What When Where Why How.",
    )


def _good_json() -> str:
    return json.dumps(
        {
            "who": "Jordan Hale (CUST-1)",
            "what": "Cash deposits then offshore wire including TXN-1001 and TXN-1004",
            "when": "1–5 July 2026",
            "where": "Miami/Fort Lauderdale branches and Cayman Islands",
            "why": "Activity inconsistent with expected payroll profile",
            "how": "Near-threshold deposits aggregated then wired offshore",
            "full_narrative": "Subject Jordan Hale conducted TXN-1001 and later TXN-1004.",
            "evidence_txn_refs": ["TXN-1001", "TXN-1004"],
        }
    )


def test_prompt_includes_evidence_and_policy_not_mixed_wrongly():
    messages = build_draft_messages(_pack(), _retrieval())
    assert messages[0].role == "system"
    assert "allowed_txn_refs" in messages[0].content or "Hard rules" in messages[0].content
    user = messages[1].content
    assert "CASE EVIDENCE" in user
    assert "POLICY CONTEXT" in user
    assert "TXN-1001" in user
    assert "Jordan Hale" in user
    assert "Who What When Where Why How" in user


def test_grounding_rejects_invented_txn_in_prose():
    narrative = StructuredNarrative(
        who="Unknown person",
        what="Used TXN-9999 which does not exist",
        when="",
        where="",
        why="",
        how="",
        full_narrative="",
        evidence_txn_refs=["TXN-1001"],
    )
    with pytest.raises(GroundingError):
        validate_narrative_grounding(narrative, ["TXN-1001", "TXN-1004"])


def test_grounding_rejects_invented_declared_refs():
    narrative = StructuredNarrative(
        who="Jordan Hale",
        what="Deposit",
        evidence_txn_refs=["TXN-1001", "TXN-FAKE"],
    )
    with pytest.raises(GroundingError):
        validate_narrative_grounding(narrative, ["TXN-1001", "TXN-1004"])


def test_generate_structured_draft_with_fake_llm():
    llm = FakeLLMAdapter(_good_json())
    result = generate_structured_draft(_pack(), _retrieval(), llm=llm)

    assert result.grounded is True
    assert result.model_name == "fake-llm"
    assert "TXN-1001" in result.narrative.evidence_txn_refs
    assert result.citations[0].doc_id == "fincen_5ws"
    assert len(llm.calls) == 1


def test_generate_structured_draft_fails_on_hallucinated_txn():
    bad = json.dumps(
        {
            "who": "Someone",
            "what": "Mention of TXN-HOAX",
            "when": "",
            "where": "",
            "why": "",
            "how": "",
            "full_narrative": "TXN-HOAX happened",
            "evidence_txn_refs": ["TXN-1001"],
        }
    )
    llm = FakeLLMAdapter(bad)
    with pytest.raises(DraftValidationError, match="allow-list"):
        generate_structured_draft(_pack(), _retrieval(), llm=llm)
