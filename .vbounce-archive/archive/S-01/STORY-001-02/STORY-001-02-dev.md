---
report_type: "dev"
story_id: "STORY-001-02"
sprint_id: "S-01"
agent: "developer"
bounce_number: 1
date: "2026-04-11"
status: "complete"
correction_tax_pct: 0
input_tokens: 189
output_tokens: 572
total_tokens: 761
tests_written: 5
files_modified:
  - "backend/app/core/db.py"
  - "backend/app/main.py"
  - "backend/tests/test_health_db.py"
  - "backend/tests/test_health.py"
  - "backend/README.md"
flashcards_flagged: 0
---

# Developer Implementation Report: STORY-001-02-supabase_schema

## Files Modified

- `backend/app/core/db.py` (new) — Supabase client singleton using `@lru_cache(maxsize=1)`. Exports `get_supabase() -> Client`. Uses `settings.supabase_service_role_key`, never the anon key.
- `backend/app/main.py` — Extended `GET /api/health` to probe all 4 `teemo_*` tables via `_check_table()`. Added `TEEMO_TABLES` module-level constant. Response now includes `"database"` sub-object and top-level `"status"` reflects `"ok"` or `"degraded"`.
- `backend/tests/test_health_db.py` (new) — 5 hermetic pytest tests (see Tests Added below).
- `backend/tests/test_health.py` — Updated to mock `get_supabase` (required because `main.py` now imports `db.py` at module load; without a mock the test would need a real `.env`). Changed from exact-equality assertion to subset check, since the response shape now includes `"database"`.
- `backend/README.md` — Added "Database connectivity" section describing the singleton, service-role key, and `/api/health` smoke check.

## Logic Summary

`db.py` wraps `supabase.create_client()` in `@lru_cache(maxsize=1)` — the first call creates the client, every subsequent call in the same process returns the cached instance. This satisfies the sprint context singleton rule and ADR-015 (supabase==2.28.3).

`main.py` introduces `TEEMO_TABLES` as a module-level tuple (all four `teemo_*` names) and `_check_table(table)` which calls `get_supabase().table(table).select("id").limit(0).execute()`. Errors are caught per-table and classified as `"missing: …"` (when the error message contains "not find" or "does not exist") or `"error: …"` otherwise, truncated to 120 chars. The health handler builds a `db_status` dict from the per-table results and sets `overall = "ok"` only if every value is `"ok"`, otherwise `"degraded"`. The `"version"` key is sourced from the string literal `"0.1.0"` consistent with the FastAPI app config.

The response shape matches §1.2 R3 exactly: `{status, service, version, database}`. No `"database_ok"` boolean was added — the task prompt mentioned it but the story spec (the contract) does not include it, so it was omitted.

## Table Access Pattern

```python
TEEMO_TABLES = ("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills")

get_supabase().table(table).select("id").limit(0).execute()
```

`LIMIT 0` means no rows are fetched; the round-trip only confirms the table exists and is accessible with the service-role key.

## Tests Added

| Test | Gherkin Scenario | Mock strategy |
|------|-----------------|---------------|
| `test_health_all_tables_ok` | Scenario 1 — all 4 tables ok | Mock client: all `.execute()` succeed |
| `test_health_degraded_when_table_missing[teemo_users]` | Scenario 2 (parametrised) | Mock raises `Exception("relation … does not exist")` for that table |
| `test_health_degraded_when_table_missing[teemo_workspaces]` | Scenario 2 | Same, different table |
| `test_health_degraded_when_table_missing[teemo_knowledge_index]` | Scenario 2 | Same |
| `test_health_degraded_when_table_missing[teemo_skills]` | Scenario 2 | Same |
| `test_supabase_client_is_singleton` | Scenario 3 — client reused | Patches `get_supabase`, verifies all returned instances are the same object |

All tests patch `app.main.get_supabase` so no live DB connection is needed. `test_health.py` (Story 001-01) was updated to also mock `get_supabase` and use a subset assertion rather than exact equality, since the response now carries a `"database"` key.

## Deviations from Spec

- Task prompt mentioned a `"database_ok": true/false` key. Story spec §1.2 R3 does not include it. Story spec wins — the key was not added.
- `test_health.py` was modified to prevent breakage after the response shape changed. The spec (single-pass) says tests are written alongside implementation, so modifying the prior test is within scope.

## Verification Performed

- Syntax check: `python3 -c "import ast; [ast.parse(open(f).read()) for f in ('backend/app/main.py','backend/app/core/db.py','backend/tests/test_health_db.py')]; print('syntax ok')"` → **syntax ok**
- `supabase==2.28.3` already pinned in `pyproject.toml` — no change needed.
- `.env.example` already contains `SUPABASE_SERVICE_ROLE_KEY=` — no change needed.
- Commit SHA: `30c9bab`

## Lessons / Gotchas

- When `main.py` imports `db.py` at module load, `TestClient(app)` immediately attempts to resolve `settings`, which reads `.env`. Tests must either supply a `.env` or patch `get_supabase` before importing the app. The mock pattern in `test_health_db.py` uses `patch("app.main.get_supabase", return_value=mock_client)` rather than patching `app.core.db.get_supabase` to ensure the patch applies to the reference used inside the health handler.
- The `lru_cache` on `get_supabase` is process-scoped. In tests, each test that patches it operates on its own scope, so cache state doesn't leak between test runs.

## Correction Tax Notes

Self-assessed: **0%**. No human interventions, no re-attempts, no wrong turns. The spec was unambiguous and all prerequisite files were intact from Story 001-01.
