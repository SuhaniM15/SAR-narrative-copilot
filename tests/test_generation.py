"""Module 4 — persist generated drafts (service + API). Uses FakeLLM, no Groq key."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.adapters.chroma_retriever import ChromaKnowledgeStore, DeterministicHashEmbedding
from app.adapters.llm import FakeLLMAdapter
from app.api.llm_deps import get_llm
from app.config import BASE_DIR
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.case import CaseStatus
from app.models.user import User, UserRole
from app.schemas import CaseCreate, TransactionCreate
from app.schemas.retrieval import Citation, RetrievalResult
from app.services import cases as case_service
from app.services.generation import GenerationNotAllowed, generate_and_persist_draft
from app.services.drafting import DraftValidationError


def _fake_draft_json(txn_refs: list[str]) -> str:
    refs = ", ".join(txn_refs)
    return json.dumps(
        {
            "who": "Jordan Hale",
            "what": f"Activity involving {refs}",
            "when": "July 2026",
            "where": "Florida and Cayman Islands",
            "why": "Inconsistent with expected payroll activity",
            "how": "Near-threshold deposits then offshore wire",
            "full_narrative": f"Subject conducted {refs}.",
            "evidence_txn_refs": txn_refs,
        }
    )


def _ensure_analyst(db_session) -> User:
    analyst = db_session.scalars(select(User).where(User.email == "analyst@example.com")).first()
    if analyst:
        return analyst
    analyst = User(
        email="analyst@example.com",
        full_name="Analyst",
        hashed_password=hash_password("AnalystPass123!"),
        role=UserRole.ANALYST.value,
    )
    db_session.add(analyst)
    db_session.commit()
    db_session.refresh(analyst)
    return analyst


def _create_case_with_txns(db_session, analyst: User, alert_id: str = "ALT-GEN-1"):
    payload = CaseCreate(
        external_alert_id=alert_id,
        title="Generate draft test",
        typology="structuring_layering",
        alert_reason="Near-threshold deposits then offshore wire",
        customer_id="CUST-1",
        customer_name="Jordan Hale",
        customer_occupation="Consultant",
        customer_expected_activity="Payroll under $3,000/week",
        transactions=[
            TransactionCreate(
                txn_ref="TXN-1001",
                amount=9800,
                txn_type="cash_deposit",
                counterparty="Cash",
                location="Miami, FL",
                occurred_at=datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
            ),
            TransactionCreate(
                txn_ref="TXN-1004",
                amount=28000,
                txn_type="wire_out",
                counterparty="Offshore Holdings Ltd",
                location="Cayman Islands",
                channel="wire",
                occurred_at=datetime(2026, 7, 5, 12, 0, tzinfo=timezone.utc),
            ),
        ],
    )
    return case_service.create_case(db_session, payload, analyst)


def test_generate_and_persist_draft_service(db_session, tmp_path):
    analyst = _ensure_analyst(db_session)
    case = _create_case_with_txns(db_session, analyst)
    store = ChromaKnowledgeStore(
        persist_dir=tmp_path / "chroma",
        collection_name="gen_test",
        embedding_function=DeterministicHashEmbedding(),
    )
    store.ingest_directory(BASE_DIR / "data" / "knowledge", reset=True)
    llm = FakeLLMAdapter(_fake_draft_json(["TXN-1001", "TXN-1004"]))

    draft = generate_and_persist_draft(db_session, case, analyst, llm=llm, store=store)

    assert draft.version == 1
    assert draft.who == "Jordan Hale"
    assert "TXN-1001" in draft.full_narrative
    assert draft.model_name == "fake-llm"
    citations = json.loads(draft.retrieval_citations_json)
    assert isinstance(citations, list) and len(citations) >= 1

    db_session.refresh(case)
    assert case.status == CaseStatus.DRAFTED.value

    events = list(
        db_session.scalars(
            select(AuditEvent).where(
                AuditEvent.entity_id == case.id,
                AuditEvent.event_type == "DRAFT_GENERATED",
            )
        )
    )
    assert len(events) == 1


def test_generate_blocked_when_under_review(db_session):
    analyst = _ensure_analyst(db_session)
    case = _create_case_with_txns(db_session, analyst, alert_id="ALT-GEN-BLOCK")
    case.status = CaseStatus.UNDER_REVIEW.value
    db_session.commit()

    with pytest.raises(GenerationNotAllowed):
        generate_and_persist_draft(
            db_session,
            case,
            analyst,
            llm=FakeLLMAdapter(_fake_draft_json(["TXN-1001"])),
        )


def test_generate_rejects_case_with_no_transactions(db_session):
    analyst = _ensure_analyst(db_session)
    payload = CaseCreate(
        external_alert_id="ALT-NO-TXN",
        title="No txns",
        alert_reason="x",
        customer_id="C1",
        customer_name="N",
        customer_occupation="O",
        customer_expected_activity="E",
        transactions=[],
    )
    case = case_service.create_case(db_session, payload, analyst)
    with pytest.raises(DraftValidationError, match="no transactions"):
        generate_and_persist_draft(
            db_session,
            case,
            analyst,
            llm=FakeLLMAdapter(_fake_draft_json([])),
        )


def test_generate_rejects_empty_retrieval(db_session, monkeypatch):
    analyst = _ensure_analyst(db_session)
    case = _create_case_with_txns(db_session, analyst, alert_id="ALT-EMPTY-RAG")
    monkeypatch.setattr(
        "app.services.generation.retrieve_policy_context",
        lambda pack, store=None, top_k=None: RetrievalResult(query="q", citations=[], policy_context=""),
    )
    with pytest.raises(DraftValidationError, match="no policy citations"):
        generate_and_persist_draft(
            db_session,
            case,
            analyst,
            llm=FakeLLMAdapter(_fake_draft_json(["TXN-1001"])),
        )


def test_generate_draft_api_returns_400_on_hallucinated_txn(client, analyst_token, monkeypatch):
    fixed_retrieval = RetrievalResult(
        query="test-query",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="Answer Who What When Where Why How.",
                typologies=["general"],
                distance=0.2,
            )
        ],
        policy_context="[fincen_5ws] guidance",
    )
    monkeypatch.setattr(
        "app.services.generation.retrieve_policy_context",
        lambda pack, store=None, top_k=None: fixed_retrieval,
    )
    bad = json.dumps(
        {
            "who": "x",
            "what": "TXN-HOAX",
            "when": "",
            "where": "",
            "why": "",
            "how": "",
            "full_narrative": "TXN-HOAX",
            "evidence_txn_refs": ["TXN-1001"],
        }
    )
    client.app.dependency_overrides[get_llm] = lambda: FakeLLMAdapter(bad)
    headers = {"Authorization": f"Bearer {analyst_token}"}
    created = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "external_alert_id": "ALT-API-400",
            "title": "bad gen",
            "alert_reason": "x",
            "customer_id": "C1",
            "customer_name": "Jordan Hale",
            "customer_occupation": "Consultant",
            "customer_expected_activity": "Payroll",
            "transactions": [
                {
                    "txn_ref": "TXN-1001",
                    "amount": 9800,
                    "txn_type": "cash_deposit",
                    "counterparty": "Cash",
                    "occurred_at": "2026-07-01T10:00:00Z",
                }
            ],
        },
    )
    case_id = created.json()["id"]
    gen = client.post(f"/api/v1/cases/{case_id}/generate-draft", headers=headers)
    assert gen.status_code == 400, gen.text
    client.app.dependency_overrides.pop(get_llm, None)


def test_generate_draft_api_returns_502_on_llm_error(client, analyst_token, monkeypatch):
    from app.adapters.llm import LLMError

    class BoomLLM:
        def complete(self, messages, *, temperature: float = 0.2):
            raise LLMError("Groq timeout")

    fixed_retrieval = RetrievalResult(
        query="test-query",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="guidance",
                typologies=["general"],
                distance=0.2,
            )
        ],
        policy_context="guidance",
    )
    monkeypatch.setattr(
        "app.services.generation.retrieve_policy_context",
        lambda pack, store=None, top_k=None: fixed_retrieval,
    )
    client.app.dependency_overrides[get_llm] = lambda: BoomLLM()
    headers = {"Authorization": f"Bearer {analyst_token}"}
    created = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "external_alert_id": "ALT-API-502",
            "title": "llm fail",
            "alert_reason": "x",
            "customer_id": "C1",
            "customer_name": "Jordan Hale",
            "customer_occupation": "Consultant",
            "customer_expected_activity": "Payroll",
            "transactions": [
                {
                    "txn_ref": "TXN-1001",
                    "amount": 9800,
                    "txn_type": "cash_deposit",
                    "counterparty": "Cash",
                    "occurred_at": "2026-07-01T10:00:00Z",
                }
            ],
        },
    )
    case_id = created.json()["id"]
    gen = client.post(f"/api/v1/cases/{case_id}/generate-draft", headers=headers)
    assert gen.status_code == 502, gen.text
    assert "Groq timeout" in gen.json()["detail"]
    client.app.dependency_overrides.pop(get_llm, None)


def test_generate_draft_api_with_fake_llm(client, analyst_token, monkeypatch):
    """HTTP path: override LLM + stub retrieval so CI needs no Groq/ONNX download."""
    fixed_retrieval = RetrievalResult(
        query="test-query",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="Answer Who What When Where Why How.",
                typologies=["general"],
                distance=0.2,
            )
        ],
        policy_context="[fincen_5ws] Answer Who What When Where Why How.",
    )
    monkeypatch.setattr(
        "app.services.generation.retrieve_policy_context",
        lambda pack, store=None, top_k=None: fixed_retrieval,
    )
    client.app.dependency_overrides[get_llm] = lambda: FakeLLMAdapter(
        _fake_draft_json(["TXN-1001", "TXN-1004"])
    )

    headers = {"Authorization": f"Bearer {analyst_token}"}
    created = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "external_alert_id": "ALT-API-GEN-1",
            "title": "API gen",
            "alert_reason": "Structuring then layering",
            "customer_id": "C1",
            "customer_name": "Jordan Hale",
            "customer_occupation": "Consultant",
            "customer_expected_activity": "Payroll",
            "transactions": [
                {
                    "txn_ref": "TXN-1001",
                    "amount": 9800,
                    "txn_type": "cash_deposit",
                    "counterparty": "Cash",
                    "occurred_at": "2026-07-01T10:00:00Z",
                },
                {
                    "txn_ref": "TXN-1004",
                    "amount": 28000,
                    "txn_type": "wire_out",
                    "counterparty": "Offshore",
                    "occurred_at": "2026-07-05T12:00:00Z",
                },
            ],
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    gen = client.post(f"/api/v1/cases/{case_id}/generate-draft", headers=headers)
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["version"] == 1
    assert body["who"] == "Jordan Hale"
    assert "fincen_5ws" in body["retrieval_citations_json"]

    case = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert case.json()["status"] == "drafted"

    audit = client.get(f"/api/v1/cases/{case_id}/audit", headers=headers)
    types = [e["event_type"] for e in audit.json()]
    assert "DRAFT_GENERATED" in types

    # Cleanup override so other tests aren't affected if order changes
    client.app.dependency_overrides.pop(get_llm, None)
