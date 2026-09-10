"""Case workflow API tests — create, submit (requires draft), approve/reject, edit versions."""

import json

from app.adapters.llm import FakeLLMAdapter
from app.api.llm_deps import get_llm
from app.models.case import NarrativeDraft
from app.schemas.retrieval import Citation, RetrievalResult


def _attach_draft(db_session, case_id: int, analyst_id: int) -> None:
    draft = NarrativeDraft(
        case_id=case_id,
        version=1,
        who="Subject",
        what="Activity",
        when="July 2026",
        where="US",
        why="Inconsistent",
        how="Cash pattern",
        full_narrative="Narrative body.",
        model_name="test",
        retrieval_citations_json="[]",
        evidence_txn_refs_json="[]",
        created_by_id=analyst_id,
    )
    db_session.add(draft)
    db_session.commit()


def test_create_case_and_audit_trail(client, analyst_token):
    payload = {
        "external_alert_id": "ALT-TEST-1",
        "title": "Structuring test case",
        "typology": "structuring",
        "alert_reason": "Near-threshold deposits",
        "customer_id": "C1",
        "customer_name": "Test Customer",
        "customer_occupation": "Consultant",
        "customer_expected_activity": "Low domestic activity",
        "transactions": [
            {
                "txn_ref": "T1",
                "amount": 9900,
                "txn_type": "cash_deposit",
                "counterparty": "Cash",
                "occurred_at": "2026-07-01T10:00:00Z",
            }
        ],
    }
    created = client.post(
        "/api/v1/cases",
        json=payload,
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert created.json()["status"] == "open"
    assert len(created.json()["transactions"]) == 1

    audit = client.get(
        f"/api/v1/cases/{case_id}/audit",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert audit.status_code == 200
    types = [e["event_type"] for e in audit.json()]
    assert "CASE_CREATED" in types


def test_reviewer_cannot_create_case(client, reviewer_token):
    response = client.post(
        "/api/v1/cases",
        json={
            "external_alert_id": "ALT-X",
            "title": "x",
            "alert_reason": "x",
            "customer_id": "c",
            "customer_name": "n",
            "customer_occupation": "o",
            "customer_expected_activity": "e",
        },
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == 403


def test_submit_requires_draft(client, analyst_token):
    created = client.post(
        "/api/v1/cases",
        json={
            "external_alert_id": "ALT-NO-DRAFT",
            "title": "No draft",
            "alert_reason": "x",
            "customer_id": "C1",
            "customer_name": "A",
            "customer_occupation": "O",
            "customer_expected_activity": "E",
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    case_id = created.json()["id"]
    submitted = client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert submitted.status_code == 400
    assert "draft" in submitted.json()["detail"].lower()


def test_approve_flow(client, analyst_token, reviewer_token, db_session):
    created = client.post(
        "/api/v1/cases",
        json={
            "external_alert_id": "ALT-APPROVE-1",
            "title": "Approve flow",
            "alert_reason": "Layering",
            "customer_id": "C2",
            "customer_name": "Pat Lee",
            "customer_occupation": "Trader",
            "customer_expected_activity": "Domestic wires",
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    case_id = created.json()["id"]
    from app.models.user import User
    from sqlalchemy import select

    analyst = db_session.scalars(select(User).where(User.email == "analyst@example.com")).first()
    _attach_draft(db_session, case_id, analyst.id)

    submitted = client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "under_review"

    approved = client.post(
        f"/api/v1/cases/{case_id}/approve",
        json={"comment": "Narrative ready for filing"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # Approved drafts cannot be casually overwritten
    edited = client.patch(
        f"/api/v1/cases/{case_id}/draft",
        json={"who": "Should fail"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert edited.status_code == 400


def test_approve_requires_non_empty_comment(client, analyst_token, reviewer_token, db_session):
    created = client.post(
        "/api/v1/cases",
        json={
            "external_alert_id": "ALT-COMMENT-REQ",
            "title": "Comment required",
            "alert_reason": "Structuring",
            "customer_id": "C3",
            "customer_name": "Sam Lee",
            "customer_occupation": "Analyst",
            "customer_expected_activity": "Payroll",
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    case_id = created.json()["id"]
    from app.models.user import User
    from sqlalchemy import select

    analyst = db_session.scalars(select(User).where(User.email == "analyst@example.com")).first()
    _attach_draft(db_session, case_id, analyst.id)
    client.post(
        f"/api/v1/cases/{case_id}/submit",
        headers={"Authorization": f"Bearer {analyst_token}"},
    )

    missing = client.post(
        f"/api/v1/cases/{case_id}/approve",
        json={},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert missing.status_code == 422

    blank = client.post(
        f"/api/v1/cases/{case_id}/approve",
        json={"comment": "   "},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert blank.status_code == 422


def test_reject_returns_to_drafted_and_edit_versions(
    client, analyst_token, reviewer_token, db_session, monkeypatch
):
    fixed_retrieval = RetrievalResult(
        query="q",
        citations=[
            Citation(
                doc_id="fincen_5ws",
                title="FinCEN 5 Ws",
                source_path="data/knowledge/fincen_5ws.md",
                snippet="guidance",
                typologies=["general"],
                distance=0.1,
            )
        ],
        policy_context="guidance",
    )
    monkeypatch.setattr(
        "app.services.generation.retrieve_policy_context",
        lambda pack, store=None, top_k=None: fixed_retrieval,
    )
    draft_json = json.dumps(
        {
            "who": "Pat Lee",
            "what": "Activity TXN-1001",
            "when": "July 2026",
            "where": "US",
            "why": "Inconsistent",
            "how": "Cash",
            "full_narrative": "Pat Lee conducted TXN-1001.",
            "evidence_txn_refs": ["TXN-1001"],
        }
    )
    client.app.dependency_overrides[get_llm] = lambda: FakeLLMAdapter(draft_json)

    headers = {"Authorization": f"Bearer {analyst_token}"}
    created = client.post(
        "/api/v1/cases",
        headers=headers,
        json={
            "external_alert_id": "ALT-REJECT-REV",
            "title": "Reject revise",
            "alert_reason": "Structuring",
            "customer_id": "C9",
            "customer_name": "Pat Lee",
            "customer_occupation": "Trader",
            "customer_expected_activity": "Domestic",
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
    assert gen.status_code == 200, gen.text
    assert gen.json()["version"] == 1

    ev = client.get(f"/api/v1/cases/{case_id}/evidence", headers=headers)
    assert ev.status_code == 200
    assert "findings" in ev.json()

    client.post(f"/api/v1/cases/{case_id}/submit", headers=headers)
    rejected = client.post(
        f"/api/v1/cases/{case_id}/reject",
        json={"comment": "Needs clearer How section"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "drafted"

    edited = client.patch(
        f"/api/v1/cases/{case_id}/draft",
        json={"how": "Clarified layering path"},
        headers=headers,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["version"] == 2
    assert edited.json()["how"] == "Clarified layering path"

    drafts = client.get(f"/api/v1/cases/{case_id}/drafts", headers=headers)
    assert len(drafts.json()) == 2

    audit = client.get(f"/api/v1/cases/{case_id}/audit", headers=headers)
    types = [e["event_type"] for e in audit.json()]
    assert "CASE_REJECTED" in types
    assert "DRAFT_EDITED" in types

    client.app.dependency_overrides.pop(get_llm, None)
