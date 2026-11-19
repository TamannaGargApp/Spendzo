# Expense Ledger

Two independent projects:

```
backend/    FastAPI + MongoDB API (uv)        -> http://localhost:8000
frontend/   static HTML/CSS/JS (no build)     -> http://localhost:5173
docker-compose.yml   MongoDB
```

## Backend
```bash
docker compose up -d
ollama pull qwen3:4b            # once; keep Ollama running
cd backend
cp .env.example .env            # set JWT_SECRET, optional ADMIN_EMAIL
uv sync
uv run fastapi dev app/main.py  # API docs at /docs
```

## Frontend
```bash
cd frontend
python3 -m http.server 5173
```
Open http://localhost:5173. The API address is set in `frontend/js/config.js`; the backend allows the frontend origin through `CORS_ORIGINS` in `backend/.env`.

## Notes
- Auth: JWT access + refresh, Argon2 hashes. Every record has `owner_id`; all queries go through `owner_filter()` (`backend/app/core/deps.py`).
- Admin scope: roles exist, `/api/admin/*` is guarded, features come later via `owner_filter(user, all_accounts=True)`.
- Money is stored as integer paise. Bills are optional (PDF/JPG/PNG, 5 MB) via `backend/app/services/storage.py`.
- Assistant: Ollama `qwen3:4b` limited to 5 read-only tools with the owner injected by code; replies not grounded in a tool call are replaced by a refusal.
