# SAR Narrative Copilot

Analyst-in-the-loop system that turns **post-alert** AML cases into FinCEN-style **5 Ws + How** SAR drafts, with deterministic typology findings, RAG citations, PII masking for LLM calls, fail-closed grounding, and an append-only audit trail.

Humans edit and approve. The system **never auto-files** to FinCEN and is **not** a fraud detection engine.

## Why this exists

Banks already generate alerts. The expensive, audit-sensitive work is writing a regulator-ready narrative and proving *why* each conclusion was drawn. This project drafts the narrative and the trail — analysts and reviewers keep the decision.

## Architecture

```text
Case + transactions (DB)
  → Evidence pack
  → Deterministic typology rules (STRUCT / LAYER findings)
  → RAG over curated policy docs (Chroma)
  → PII masking (LLM-bound copy only)
  → Groq structured 5W draft
  → Grounding gate (txn allow-list + required sections)
  → Versioned draft + audit
  → Analyst edit / submit → Reviewer approve|reject
```

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI + Pydantic |
| DB | SQLite (Postgres-ready SQLAlchemy models) |
| Auth | JWT + RBAC (`analyst`, `reviewer`, `admin`) |
| Rules | Deterministic structuring / layering findings |
| RAG | Custom retriever + Chroma (no LangChain) |
| LLM | Groq adapter (+ FakeLLM for tests) |
| UI | React (Vite + Tailwind) |
| Legacy UI | Streamlit thin client |
| Tests | Pytest |
| Deploy | Docker Compose |

## Quick start (API)

```bash
cd sar-copilot
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
copy .env.example .env
# set GROQ_API_KEY in .env

python -m scripts.seed
python -m scripts.ingest_knowledge
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir . --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs

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
3. Explore cases, evidence, generate-draft, audit

## React UI (recommended)

With the API running on `:8000`:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

Case Workspace supports generate, edit, submit, approve/reject, typology findings, citations, and **Export Markdown / JSON**.

## Streamlit UI (optional / legacy)

```bash
streamlit run ui/app.py
```

## Case lifecycle

`open` → `drafted` → `under_review` → `approved`  
(Rejection returns the case to `drafted` for revision.)

## Project layout

```text
sar-copilot/
├── app/
│   ├── api/          # HTTP routes
│   ├── core/         # JWT, RBAC
│   ├── models/       # SQLAlchemy
│   ├── schemas/      # Pydantic
│   ├── services/     # Evidence, rules, PII, RAG, drafting, audit
│   └── adapters/     # LLM + Chroma
├── frontend/         # React workbench
├── data/knowledge/   # Curated typology / FinCEN docs
├── ui/               # Streamlit (legacy)
├── docs/PRD.md
├── scripts/          # seed, ingest_knowledge, docker_entrypoint
├── Dockerfile
├── docker-compose.yml
└── tests/
```

## Docker Compose

```bash
copy .env.example .env
# set GROQ_API_KEY

docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:8000/docs | Swagger |
| http://localhost:8501 | Streamlit UI |

First start seeds data and ingests knowledge (can take a minute).  
Stop with `docker compose down` (keeps `./data`).

## Tests

```bash
pytest -q
```

## Scope / non-goals

**In scope:** post-alert narrative drafting, grounding, citations, RBAC, audit, React review UI.  
**Out of scope:** real bank/TM integration, auto-filing, LangChain agents, SSO, multi-tenant IAM.

See [docs/PRD.md](docs/PRD.md) for full product notes.
