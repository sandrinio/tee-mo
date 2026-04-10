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
