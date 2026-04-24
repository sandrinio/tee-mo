---
story_id: "STORY-001-02-supabase_schema"
parent_epic_ref: "EPIC-001"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-11T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-01/STORY-001-02-supabase_schema.md`. Shipped in sprint S-01, carried forward during ClearGate migration 2026-04-24.

# STORY-001-02: Supabase Client Wiring + Schema Smoke Check

**Complexity: L1** — Migrations are pre-written (`database/migrations/`) and the user runs them manually. This story only wires the Python Supabase client and extends `/api/health` to confirm all 4 teemo_ tables are reachable.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> This story verifies that the FastAPI backend can connect to the self-hosted Supabase instance and query the `teemo_*` tables created by migrations 001–004. Every subsequent backend story depends on a working DB client.

### 1.2 Detailed Requirements

- **R1**: Create `backend/app/core/db.py` exporting a `get_supabase()` factory that returns a lazily-initialized Supabase client using `settings.supabase_url` and `settings.supabase_service_role_key` (NOT the anon key — Tee-Mo's backend always uses the service role).
- **R2**: Extend `GET /api/health` to perform a zero-cost existence check on all 4 teemo_ tables (`teemo_users`, `teemo_workspaces`, `teemo_knowledge_index`, `teemo_skills`). Use `SELECT id FROM <table> LIMIT 0` via the client — returns empty but confirms the table exists and is queryable.
- **R3**: Health response shape becomes:
  ```json
  {
    "status": "ok" | "degraded",
    "service": "tee-mo",
    "version": "0.1.0",
    "database": {
      "teemo_users": "ok" | "missing" | "error: <msg>",
      "teemo_workspaces": "ok" | "missing" | "error: <msg>",
      "teemo_knowledge_index": "ok" | "missing" | "error: <msg>",
      "teemo_skills": "ok" | "missing" | "error: <msg>"
    }
  }
  ```
  Top-level `status` is `"ok"` only if all 4 table checks are `"ok"`; otherwise `"degraded"`.
- **R4**: Errors from the Supabase client are caught per-table and stringified — one table failing must not crash the health endpoint.
- **R5**: The Supabase client is created once (module-level or cached) — do NOT create a new client on every request.

### 1.3 Out of Scope
- No writing the migration SQL — already done in `database/migrations/`.
- No running migrations from Python — user runs them manually in Supabase Studio.
- No CRUD endpoints, no models, no auth.
- No connection pooling tuning.

### TDD Red Phase: No
Rationale: One integration test is enough; the logic is a pass-through to the Supabase client.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Database connection check

  Scenario: All 4 teemo_ tables exist and are queryable
    Given migrations 001–004 have been applied to the self-hosted Supabase
    And the backend is running
    When I send GET http://localhost:8000/api/health
    Then the response status is 200
    And response.database.teemo_users is "ok"
    And response.database.teemo_workspaces is "ok"
    And response.database.teemo_knowledge_index is "ok"
    And response.database.teemo_skills is "ok"
    And response.status is "ok"

  Scenario: Missing table degrades gracefully
    Given the teemo_skills table has been dropped
    When I send GET http://localhost:8000/api/health
    Then response.status is "degraded"
    And response.database.teemo_skills starts with "missing" or "error"
    And the other 3 tables still report "ok"
    And the endpoint does NOT return 500

  Scenario: Client is reused across requests
    Given two sequential GET /api/health requests
    When I inspect the Supabase client module
    Then only one client instance was created
```

### 2.2 Verification Steps (Manual)
- [ ] User confirms migrations 001–004 have been run in Supabase Studio
- [ ] `curl http://localhost:8000/api/health` shows all 4 tables as `"ok"` and `status: "ok"`
- [ ] Rename one table in Supabase Studio (e.g., `ALTER TABLE teemo_skills RENAME TO teemo_skills_bak`), hit the endpoint, see `status: "degraded"` and that specific table flagged, then rename back

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-001-01** | Merged — `backend/app/core/config.py` and `main.py` exist | [ ] |
| **Migrations** | User has run `database/migrations/001_teemo_users.sql` through `004_teemo_skills.sql` in Supabase Studio | [ ] |
| **Env Vars** | `.env` has SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, etc. | [x] |
| **Connection reachable** | `curl "$SUPABASE_URL/rest/v1/" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY"` returns JSON (verified during sprint planning) | [x] |

### 3.1 Test Implementation
`backend/tests/test_health_db.py`:
```python
from fastapi.testclient import TestClient
from app.main import app

def test_health_reports_all_tables_ok():
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    for table in ["teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills"]:
        assert body["database"][table] == "ok"
```
Note: this is an integration test — it requires the real Supabase connection. No mocking.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/core/db.py` (new) |
| **Related Files** | `backend/app/main.py` (update health endpoint), `backend/tests/test_health_db.py` (new) |
| **New Files Needed** | Yes — `db.py` and the test |
| **ADR References** | ADR-015 (Supabase 2.28.3), ADR-020 (self-hosted), Charter §2.4 (security) |
| **First-Use Pattern** | Yes — first Supabase client in Tee-Mo. Pattern reference: `new_app/backend/app/core/db.py`. Strip any legacy compatibility code. |

### 3.3 Technical Logic

**`backend/app/core/db.py`**:
```python
from functools import lru_cache
from supabase import create_client, Client
from app.core.config import settings

@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached service-role Supabase client. Never use the anon key from the backend."""
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
```

**Update `backend/app/main.py`** — extend the health endpoint:
```python
from app.core.db import get_supabase

TEEMO_TABLES = ("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills")

def _check_table(table: str) -> str:
    try:
        # LIMIT 0 = confirms table + permissions without fetching rows
        get_supabase().table(table).select("id").limit(0).execute()
        return "ok"
    except Exception as exc:  # noqa: BLE001  (graceful degradation by design)
        msg = str(exc)
        if "not find" in msg.lower() or "does not exist" in msg.lower():
            return f"missing: {msg[:120]}"
        return f"error: {msg[:120]}"

@app.get("/api/health")
def health():
    db_status = {t: _check_table(t) for t in TEEMO_TABLES}
    overall = "ok" if all(v == "ok" for v in db_status.values()) else "degraded"
    return {
        "status": overall,
        "service": "tee-mo",
        "version": "0.1.0",
        "database": db_status,
    }
```

### 3.4 API Contract

| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/health` | GET | None | — | See §1.2 R3 — extended with `database` object |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 1 | `test_health_reports_all_tables_ok` — real DB |
| Integration tests | Already counted above | Uses real Supabase, not mock |

### 4.2 Definition of Done
- [ ] Migrations confirmed run by user before starting
- [ ] Health endpoint returns all 4 tables as `"ok"` against the real Supabase
- [ ] Client is cached (verified by reading `db.py`)
- [ ] Error branch covered by the manual verification step
- [ ] No ADR violations

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
