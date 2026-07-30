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


def test_approve_flow(client, analyst_token, reviewer_token):
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
