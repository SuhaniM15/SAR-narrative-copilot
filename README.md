# SAR Narrative Copilot

Analyst-in-the-loop system that turns post-alert AML cases into FinCEN-style **5 Ws + How** SAR drafts, with citations and an append-only audit trail.

> Status: **Week 2–3 vertical slice** · API + Streamlit + Docker Compose.

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
├── ui/               # Streamlit thin client
├── docs/PRD.md
├── scripts/          # seed, ingest_knowledge, docker_entrypoint
├── Dockerfile
├── docker-compose.yml
└── tests/
```

## Streamlit UI (local)

Keep the API running, then in another terminal:

```bash
streamlit run ui/app.py
```

Login with seeded users (e.g. `analyst@example.com` / `AnalystPass123!`).
API base in the login form: `http://127.0.0.1:8000`.

## Docker Compose

One stack: API on `:8000`, Streamlit on `:8501`. SQLite + Chroma live under `./data` (bind-mounted).

```bash
copy .env.example .env
# set GROQ_API_KEY in .env

docker compose up --build
```

| URL | What |
|---|---|
| http://localhost:8000/docs | Swagger |
| http://localhost:8501 | Streamlit UI |

On first start the API container seeds users/sample case and ingests `data/knowledge` into Chroma (can take a minute while embeddings load).

**UI API base when using Compose:** leave `http://api:8000` (Streamlit talks to the API over the Compose network). Do not use `127.0.0.1:8000` inside the UI container.

Stop: `docker compose down` (data in `./data` is kept).

## Tests

```bash
pytest -q
```

## Roadmap

- **Week 1 (done):** users, cases, transactions, audit, RBAC
- **Week 2 (done):** evidence pack → RAG → Groq structured 5W draft + citations
- **Week 3 (done):** Streamlit review UI + Docker Compose

See [docs/PRD.md](docs/PRD.md) for scope and non-goals.
