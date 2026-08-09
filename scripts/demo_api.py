"""Quick live demo against a running API (no Groq required for steps 1-5)."""

import httpx

base = "http://127.0.0.1:8000"
client = httpx.Client(base_url=base, timeout=60.0)

print("=== DEMO: SAR Narrative Copilot ===\n")

h = client.get("/health")
print("1) Health:", h.json())

r = client.post(
    "/api/v1/auth/login",
    data={"username": "analyst@example.com", "password": "AnalystPass123!"},
)
r.raise_for_status()
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("2) Analyst login: OK (JWT received)")

me = client.get("/api/v1/auth/me", headers=headers).json()
print("3) /me:", me["email"], me["role"])

cases = client.get("/api/v1/cases", headers=headers).json()
print(
    "4) Cases:",
    [(c["id"], c["external_alert_id"], c["status"], c["customer_name"]) for c in cases],
)
case_id = cases[0]["id"]

case = client.get(f"/api/v1/cases/{case_id}", headers=headers).json()
print(
    "5) Case detail:",
    case["external_alert_id"],
    "| txns:",
    len(case["transactions"]),
    "| status:",
    case["status"],
)
for t in case["transactions"]:
    print(
        f"   - {t['txn_ref']}: {t['txn_type']} {t['amount']} "
        f"at {t['location']}"
    )

gen = client.post(f"/api/v1/cases/{case_id}/generate-draft", headers=headers)
print("6) generate-draft HTTP:", gen.status_code)
detail = gen.json().get("detail", gen.text)
print("   detail:", str(detail)[:240])

print("\nSwagger UI: http://127.0.0.1:8000/docs")
print("GROQ_API_KEY empty => live generate returns 502 until you add a key.")
