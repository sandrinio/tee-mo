# Tee-Mo Backend

FastAPI backend for the Tee-Mo AI Slack assistant.

## Quick Start

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy the example env file and fill in your values:

```bash
cp .env.example .env
# Edit .env with your Supabase credentials
```

Run the development server:

```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000.
Health check: `curl http://localhost:8000/api/health`

Run tests: `pytest tests/`

## Database connectivity

Tee-Mo connects to a self-hosted Supabase instance using a service-role key (never the anon key). The connection is initialised once as a cached singleton in `app/core/db.py` and reused for every request.

The `GET /api/health` endpoint doubles as a schema smoke check: it probes all four `teemo_*` tables (`teemo_users`, `teemo_workspaces`, `teemo_knowledge_index`, `teemo_skills`) with a zero-cost `SELECT id LIMIT 0` query and reports per-table status. A top-level `"status": "ok"` means all four tables are reachable; `"status": "degraded"` means at least one table is missing or erroring. Use this endpoint to confirm that migrations 001–004 have been applied before running the full application.
