# SAR Narrative Copilot — Vertical Slice PRD (v1)

## Problem
Compliance analysts spend 5–6 hours drafting regulator-ready SAR narratives after an alert already exists. The bottleneck is synthesis, consistency, and defensibility — not detection.

## Product
An analyst-in-the-loop copilot that turns a mock AML alert case into a FinCEN-style **5 Ws + How** draft, with retrieval citations and an append-only audit trail. The analyst edits and approves; the system never auto-files.

## Primary user
Compliance **analyst** / **reviewer** (post-alert investigation).

## In scope (2–3 weeks)
- Case ingest (seeded/mock alert + transactions + KYC summary)
- JWT auth + RBAC (`analyst`, `reviewer`, `admin`)
- RAG over curated typology/policy docs → grounded draft via Groq adapter
- Structured narrative (Who/What/When/Where/Why/How)
- Explainability via evidence + retrieval citations (not SHAP)
- Append-only audit events
- Thin Streamlit review UI
- Pytest happy-path tests + Docker Compose
- README / interview story

## Out of scope (v1)
- Real bank core / TM system integration
- FIU-IND dual schema
- Auto-filing to FinCEN
- LangChain, SHAP/LIME, Kubernetes
- Multi-tenant enterprise IAM / SSO

## Pilot typology
Structuring / layering (velocity, multi-source funds, rapid exit).

## Success criteria
1. Login → open case → generate draft → see citations → edit → approve/reject.
2. Every critical action appears in the audit trail with actor + timestamp.
3. Draft uses only provided evidence (prompt + tests assert no free invention of txn IDs).
4. Demo runs via local venv or Docker Compose.

## Case lifecycle
`open` → `drafted` → `under_review` → `approved` | `rejected`
