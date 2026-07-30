# SAR Narrative Copilot

Analyst-in-the-loop system that turns post-alert AML cases into FinCEN-style **5 Ws + How** SAR drafts, with citations and an append-only audit trail.

> Status: **Week 1 foundation** — auth, cases, audit. Draft generation (RAG + Groq) is Week 2.

## Why this exists

Banks already generate alerts. The expensive, audit-sensitive work is writing a regulator-ready narrative and proving *why* each conclusion was drawn. This project automates the draft and the trail — humans keep approval.

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI + Pydantic |
| DB | SQLite (Postgres-ready SQLAlchemy models) |
| Auth | JWT + RBAC (`analyst`, `reviewer`, `admin`) |
| LLM (Week 2) | Groq via adapter |
| RAG (Week 2) | Custom retriever + Chroma |
| UI (Week 3) | Streamlit thin client |
| Tests | Pytest |
| Deploy (Week 3) | Docker Compose |

## Quick start

```bash
cd sar-copilot
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env

python -m scripts.seed
uvicorn app.main:app --reload --app-dir .
```

Open Swagger: http://127.0.0.1:8000/docs

### Seeded users

| Email | Password | Role |
|---|---|---|
| `admin@example.com` | `AdminPass123!` | admin |
| `analyst@example.com` | `AnalystPass123!` | analyst |
| `reviewer@example.com` | `ReviewerPass123!` | reviewer |

Sample case alert ID: `ALT-2026-0001`

### Auth in Swagger

1. `POST /api/v1/auth/login` (OAuth2 form: username = email)
2. Click **Authorize** and paste the access token
3. `GET /api/v1/cases` / `GET /api/v1/cases/{id}/audit`

## Case lifecycle

`open` → `drafted` → `under_review` → `approved` | `rejected`

## Project layout

```text
sar-copilot/
├── app/
│   ├── api/          # HTTP routes
│   ├── core/         # JWT, RBAC
│   ├── models/       # SQLAlchemy
│   ├── schemas/      # Pydantic
│   ├── services/     # Business logic + audit writer
│   └── adapters/     # LLM/RAG (Week 2)
├── data/knowledge/   # Curated typology docs for RAG
├── docs/PRD.md
├── scripts/seed.py
└── tests/
```

## Tests

```bash
pytest -q
```

## Roadmap

- **Week 1 (done scaffold):** users, cases, transactions, audit, RBAC
- **Week 2:** evidence pack → RAG → Groq structured 5W draft + citations
- **Week 3:** Streamlit review UI, Docker, README polish

See [docs/PRD.md](docs/PRD.md) for scope and non-goals.
