---
story_id: "STORY-001-01-backend_scaffold"
parent_epic_ref: "EPIC-001"
status: "Ready to Bounce — Fast Track approved"
ambiguity: "🟢 Low"
context_source: "Charter §3.2 + Roadmap ADR-015"
actor: "Backend Dev (Solo)"
complexity_label: "L2"
---

# STORY-001-01: Backend FastAPI Scaffold + Health Endpoint

**Complexity: L2** — Scaffold a new FastAPI backend with config loading and a health endpoint. 4-5 new files, known pattern, ~1 hour.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> This story bootstraps the Python backend because Tee-Mo has no code yet and every subsequent backend story depends on a running FastAPI app with env-based config.

### 1.2 Detailed Requirements

- **R1**: Create `backend/` directory at the project root with a `pyproject.toml` pinning all Charter §3.2 backend versions exactly: `fastapi[standard]==0.135.3`, `pydantic-ai[openai,anthropic,google]==1.79.0`, `supabase==2.28.3`, `cryptography==46.0.7`, `PyJWT==2.12.1`, `bcrypt==5.0.0`, `slack-bolt==1.28.0`, `google-api-python-client==2.194.0`, `google-auth==2.49.2`, `pypdf` (latest), `python-docx` (latest), `openpyxl` (latest). Python version: **3.11**.
- **R2**: Create `backend/app/core/config.py` using `pydantic-settings` to load env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `DEBUG` (bool, default False), `CORS_ORIGINS` (comma-separated, default `http://localhost:5173`). Reads from `.env` at project root (not `backend/.env`).
- **R3**: Create `backend/app/main.py` with a FastAPI `app` instance, CORS middleware configured from `settings.cors_origins`, and one route: `GET /api/health`.
- **R4**: `GET /api/health` returns `{"status": "ok", "service": "tee-mo", "version": "0.1.0"}` with HTTP 200.
- **R5**: Validate `SUPABASE_JWT_SECRET` is ≥ 32 bytes at startup. If not, raise a clear startup error (per Roadmap ADR-017 rationale / new_app flashcard).
- **R6**: Create `backend/.gitignore` excluding `__pycache__/`, `*.pyc`, `.venv/`, `*.egg-info/`.
- **R7**: Create `backend/README.md` with a 10-line quick-start: `cd backend && python3.11 -m venv .venv && source .venv/bin/activate && pip install -e . && uvicorn app.main:app --reload`.

### 1.3 Out of Scope
- No database connection (STORY-001-02).
- No auth endpoints (Sprint 2).
- No business logic, no models, no routes beyond `/api/health`.
- No Docker, no deploy config (Sprint 5).
- No testing framework setup beyond basic `pytest` in dependencies — actual test writing in later sprints.

### TDD Red Phase: No
Rationale: Pure scaffold, no Gherkin scenarios with meaningful logic. A single smoke test in §2 covers this.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Backend scaffold

  Scenario: Health endpoint responds on startup
    Given the backend is scaffolded with the required dependencies
    When I run `uvicorn app.main:app --reload` from the backend directory
    And I send GET http://localhost:8000/api/health
    Then the response status is 200
    And the response body is {"status": "ok", "service": "tee-mo", "version": "0.1.0"}

  Scenario: Config loads env vars from project root .env
    Given a valid .env file exists at the project root with SUPABASE_URL set
    When the FastAPI app starts
    Then settings.supabase_url equals the value from .env
    And no startup exception is raised

  Scenario: Startup fails on short JWT secret
    Given SUPABASE_JWT_SECRET is set to "short" (5 bytes)
    When the FastAPI app starts
    Then startup raises a clear error naming SUPABASE_JWT_SECRET and the 32-byte requirement

  Scenario: CORS allows frontend origin
    Given the backend is running
    When the frontend at http://localhost:5173 sends a preflight OPTIONS request to /api/health
    Then the response includes Access-Control-Allow-Origin: http://localhost:5173
```

### 2.2 Verification Steps (Manual)
- [ ] `pip install -e .` from `backend/` succeeds
- [ ] `uvicorn app.main:app --reload` starts the server on port 8000
- [ ] `curl http://localhost:8000/api/health` returns the exact JSON above
- [ ] Stopping the server, setting `SUPABASE_JWT_SECRET=short`, and re-running raises a clear error
- [ ] Browser DevTools shows CORS headers on a preflight from `localhost:5173`

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Python** | 3.11 installed (`python3.11 --version`) | [ ] |
| **Env Vars** | `.env` at project root with SUPABASE_* values (already present) | [x] |
| **Services Running** | None required for this story | [x] |
| **Migrations** | None required (STORY-001-02) | [x] |

### 3.1 Test Implementation
Minimal for L2 scaffold: one smoke test `backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_ok():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "tee-mo", "version": "0.1.0"}
```

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/main.py` (new) |
| **Related Files** | `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/.gitignore`, `backend/README.md`, `backend/tests/test_health.py` |
| **New Files Needed** | Yes — all files new (project is empty) |
| **ADR References** | Charter §3.2 (version pins), ADR-015 (Supabase 2.28.3) |
| **First-Use Pattern** | Yes — this is the first FastAPI app in the repo. Reference `new_app/backend/app/main.py` and `new_app/backend/app/core/config.py` as structural templates but strip everything except the skeleton. |

### 3.3 Technical Logic

**`pyproject.toml`** — PEP 621 format, `[project]` table with `dependencies` list. `requires-python = ">=3.11,<3.12"` (pin tight to avoid surprise upgrades). No `[tool.uv]`, no `[tool.poetry]` — just vanilla pip-compatible.

**`backend/app/core/config.py`**:
```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    debug: bool = False
    cors_origins: str = "http://localhost:5173"
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

settings = Settings()  # type: ignore[call-arg]

# Startup validation (per Roadmap ADR-017 rationale)
if len(settings.supabase_jwt_secret.encode("utf-8")) < 32:
    raise RuntimeError(
        "SUPABASE_JWT_SECRET must be >= 32 bytes. "
        f"Got {len(settings.supabase_jwt_secret)} bytes. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )
```

**`backend/app/main.py`**:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

app = FastAPI(title="Tee-Mo", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "tee-mo", "version": "0.1.0"}
```

**`backend/app/__init__.py`** and **`backend/app/core/__init__.py`**: empty files so Python treats them as packages.

### 3.4 API Contract

| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/health` | GET | None | — | `{"status": "ok", "service": "tee-mo", "version": "0.1.0"}` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (scaffold only) | |
| Component tests | 0 — N/A (backend story) | |
| E2E / acceptance tests | 1 | `test_health_returns_ok` |
| Integration tests | 0 — N/A (no external services yet) | |

### 4.2 Definition of Done
- [ ] `uvicorn app.main:app --reload` starts with no errors
- [ ] `curl http://localhost:8000/api/health` returns the exact JSON in §2.1
- [ ] `pytest backend/tests/test_health.py` passes
- [ ] Short-secret test verified manually (per §2.2)
- [ ] `backend/README.md` reflects the actual install steps
- [ ] No ADR violations

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
