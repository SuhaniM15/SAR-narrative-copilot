"""PII masking checkpoint — LLM-bound copy only."""

from datetime import datetime, timezone

from app.schemas.evidence import (
    EvidenceCaseMeta,
    EvidenceCustomer,
    EvidencePack,
    EvidenceTransaction,
    TypologyFinding,
)
from app.services.pii import mask_evidence_pack_for_llm
from app.services.prompting import build_draft_messages
from app.schemas.retrieval import Citation, RetrievalResult
from app.services.drafting import generate_structured_draft
from app.adapters.llm import FakeLLMAdapter
import json


def _pack() -> EvidencePack:
    return EvidencePack(
        case=EvidenceCaseMeta(
            case_id=1,
            external_alert_id="ALT-1",
            title="Case for Jordan Hale",
            status="open",
            typology="structuring_layering",
            jurisdiction="FinCEN",
            alert_reason="Activity by Jordan Hale",
            risk_score=0.9,
        ),
        customer=EvidenceCustomer(
            customer_id="CUST-88421",
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
                narrative_note="Contact jordan.hale@example.com",
            )
        ],
        typologies=["structuring", "layering"],
        allowed_txn_refs=["TXN-1001"],
        findings=[
            TypologyFinding(
                rule_id="STRUCT-001",
                finding="Multiple cash deposits near reporting threshold",
                evidence_txn_refs=["TXN-1001"],
            )
        ],
        rag_query="structuring",
        llm_context="Customer Jordan Hale (CUST-88421). TXN-1001.",
    )


def test_mask_replaces_name_id_email_keeps_txn_refs():
    result = mask_evidence_pack_for_llm(_pack())
    masked = result.pack

    assert masked.customer.name == "<CUSTOMER_001>"
    assert masked.customer.customer_id == "<ACCOUNT_001>"
    assert "Jordan Hale" not in masked.llm_context
    assert "CUST-88421" not in masked.llm_context
    assert "<CUSTOMER_001>" in masked.llm_context
    assert masked.allowed_txn_refs == ["TXN-1001"]
    assert masked.transactions[0].txn_ref == "TXN-1001"
    assert "<EMAIL_001>" in masked.transactions[0].narrative_note
    assert result.mapping["<CUSTOMER_001>"] == "Jordan Hale"
    assert result.mapping["<ACCOUNT_001>"] == "CUST-88421"


def test_generate_sends_masked_prompt_not_raw_name():
    good = json.dumps(
        {
            "who": "<CUSTOMER_001> (<ACCOUNT_001>)",
            "what": "Cash deposit TXN-1001",
            "when": "July 2026",
            "where": "Miami, FL",
            "why": "Inconsistent with expected activity",
            "how": "Near-threshold cash deposit",
            "full_narrative": "<CUSTOMER_001> conducted TXN-1001.",
            "evidence_txn_refs": ["TXN-1001"],
        }
    )
    llm = FakeLLMAdapter(good)
    pack = _pack()
    retrieval = RetrievalResult(
        query="q",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="Answer Who What When Where Why How.",
                typologies=["general"],
                distance=0.1,
            )
        ],
        policy_context="guidance",
    )
    result = generate_structured_draft(pack, retrieval, llm=llm)
    assert result.grounded is True
    user_prompt = llm.calls[0][1].content
    assert "Jordan Hale" not in user_prompt
    assert "<CUSTOMER_001>" in user_prompt
    assert "TXN-1001" in user_prompt
    # Original pack unchanged for UI/API
    assert pack.customer.name == "Jordan Hale"
