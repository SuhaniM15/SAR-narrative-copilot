# React frontend (Vite)

Professional compliance workbench for the SAR Narrative Copilot API.

## Run

```bash
# Terminal 1 — API
cd ..
.venv\Scripts\activate
uvicorn app.main:app --reload --app-dir .

# Terminal 2 — UI
cd frontend
npm run dev
```

Open http://localhost:5173

Default API base: `http://127.0.0.1:8000`  
Override with `VITE_API_BASE_URL`.

## Demo users

| Email | Password | Role |
|---|---|---|
| analyst@example.com | AnalystPass123! | analyst |
| reviewer@example.com | ReviewerPass123! | reviewer |
