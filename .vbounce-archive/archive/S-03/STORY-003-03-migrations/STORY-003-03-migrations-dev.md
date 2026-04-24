---
story_id: "STORY-003-03-migrations"
agent: "developer"
phase: "single-pass"
bounce: 1
started_at: "2026-04-11T00:00:00Z"
completed_at: "2026-04-11T00:30:00Z"
files_modified:
  - "database/migrations/005_teemo_slack_teams.sql"
  - "database/migrations/006_teemo_workspace_channels.sql"
  - "database/migrations/007_teemo_workspaces_alter.sql"
  - "backend/app/main.py"
  - "backend/tests/test_health_db.py"
tests_written: 1
tests_passing: 31
tests_failing: 0
correction_tax_pct: 0
user_action_required: true
flashcards_flagged: []
input_tokens: 17
output_tokens: 980
total_tokens: 997
---

# Developer Implementation Report: STORY-003-03-migrations

## Summary

All 5 files for the ADR-024 schema migration work are written and all local
tests pass. Three new SQL migration files were created verbatim from story
spec §3.1, §3.2, §3.3. The `TEEMO_TABLES` constant in `backend/app/main.py`
was extended from 4 to 6 entries. The health-DB test file was updated: the
module docstring was corrected from "4 tables" to "6 tables", the scenario 1
docstring was updated to match, and a new `test_health_reports_all_six_teemo_tables`
test was appended.

An important design note: the existing `test_health_degraded_when_table_missing`
test uses `@pytest.mark.parametrize("failing_table", list(TEEMO_TABLES))` —
dynamically driven from the tuple. Adding 2 entries to `TEEMO_TABLES`
automatically expanded this parametrize suite from 4 to 6 cases with no
further test file changes required.

All 9 health tests pass against the mock. The new test
`test_health_reports_all_six_teemo_tables` verifies the exact 6-key set using
the mock client, so it is green right now. Against a live Supabase instance
(no mock), this same test would fail until the user runs the 3 SQL migrations
— that is expected behavior and is documented under "User Action Required"
below.

## Files Modified

- `database/migrations/005_teemo_slack_teams.sql` — NEW. Creates `teemo_slack_teams`
  per ADR-024. One row per Slack team installation; holds encrypted bot token and
  bot user ID for self-message filter. Updated_at trigger reuses `teemo_set_updated_at()`.
  RLS disabled. Trailing DO-block prints row count.

- `database/migrations/006_teemo_workspace_channels.sql` — NEW. Creates
  `teemo_workspace_channels` per ADR-024/ADR-025. PRIMARY KEY on `slack_channel_id`
  enforces one-workspace-per-channel globally. Two indexes for workspace and team
  lookups. RLS disabled. Trailing DO-block prints row count.

- `database/migrations/007_teemo_workspaces_alter.sql` — NEW. Applies ADR-024
  refactor to `teemo_workspaces`. Mandatory DO-block safety pre-check at the top
  RAISE EXCEPTIONs if any row has data in the columns being dropped. Drops obsolete
  unique constraint, drops 2 columns moved to `teemo_slack_teams`, adds FK constraint
  to `teemo_slack_teams`, adds `is_default_for_team` boolean, creates partial unique
  index `one_default_per_team` where `is_default_for_team = TRUE`. Trailing DO-block
  prints completion notice.

- `backend/app/main.py` — EDITED. `TEEMO_TABLES` extended from 4 entries to 6,
  adding `"teemo_slack_teams"` and `"teemo_workspace_channels"`. Module and health
  endpoint docstrings updated to say "6 tables". Comment on the constant explains
  the STORY-003-03/ADR-024 context.

- `backend/tests/test_health_db.py` — EDITED. Module docstring updated to
  reference 6 tables + added note about mock vs. live behavior. Scenario 1
  docstring corrected from "4" to "6". New test
  `test_health_reports_all_six_teemo_tables` added per story §3.5 — verifies exact
  6-key set in the database response and that all values are "ok".

## SQL Migrations Overview

| Migration File | Purpose | ADR Reference |
|---|---|---|
| `005_teemo_slack_teams.sql` | Create `teemo_slack_teams` — one row per Slack team installation | ADR-024 |
| `006_teemo_workspace_channels.sql` | Create `teemo_workspace_channels` — explicit channel-to-workspace bindings | ADR-024, ADR-025 |
| `007_teemo_workspaces_alter.sql` | ALTER `teemo_workspaces` — drop stale columns, add FK + `is_default_for_team` + partial unique index | ADR-024 |

## Regression Tests

Backend regression suite (auth + security, BUG-20260411 explicit order):

```
tests/test_auth_routes.py tests/test_security.py -v -p no:randomly
22 passed, 2 warnings in 8.24s
```

Health DB test suite:

```
tests/test_health_db.py -v
9 passed in 0.65s
```

Total: 31 tests, 0 failures, 0 skipped. All pass against the mock.

The health tests pass right now because `test_health_db.py` uses
`patch("app.main.get_supabase", ...)` — no live Supabase connection is made
during the local test run. The tests will continue to pass after the user runs
the SQL migrations. No re-run required from the developer after SQL execution.

---

## User Action Required

**YOU MUST RUN THESE 3 SQL FILES IN THE SUPABASE SQL EDITOR BEFORE THIS STORY IS DONE.**

### Step-by-step instructions

1. Open the SQL editor at `https://sulabase.soula.ge`

2. Open and run **`database/migrations/005_teemo_slack_teams.sql`**
   - Full path in repo: `database/migrations/005_teemo_slack_teams.sql`
   - Expected output: statement completes without error + NOTICE line:
     `✓ teemo_slack_teams migration complete. Current row count: 0`

3. Open and run **`database/migrations/006_teemo_workspace_channels.sql`**
   - Full path in repo: `database/migrations/006_teemo_workspace_channels.sql`
   - Expected output: statement completes without error + NOTICE line:
     `✓ teemo_workspace_channels migration complete. Current row count: 0`

4. Open and run **`database/migrations/007_teemo_workspaces_alter.sql`**
   - Full path in repo: `database/migrations/007_teemo_workspaces_alter.sql`
   - Expected output: statement completes without error + NOTICE line:
     `✓ teemo_workspaces migration 007 complete (ADR-024 refactor applied).`
   - If you see `Migration 007 aborted: N teemo_workspaces row(s) contain data...`,
     stop and investigate — there is stale data in the columns being dropped.
     The pre-check caught it before any damage was done. Report back before proceeding.

5. Run the verification query:
   ```sql
   SELECT table_name FROM information_schema.tables
   WHERE table_schema='public' AND table_name LIKE 'teemo_%'
   ORDER BY table_name;
   ```
   Expected: **6 rows** — `teemo_knowledge_index`, `teemo_skills`,
   `teemo_slack_teams`, `teemo_users`, `teemo_workspace_channels`, `teemo_workspaces`

6. Spot-check `teemo_workspaces` columns:
   ```sql
   SELECT column_name, data_type, is_nullable FROM information_schema.columns
   WHERE table_name = 'teemo_workspaces' AND table_schema = 'public'
   ORDER BY ordinal_position;
   ```
   Confirm: `is_default_for_team` IS present; `slack_bot_user_id` and
   `encrypted_slack_bot_token` are NOT present.

7. Spot-check partial unique index:
   ```sql
   SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'teemo_workspaces';
   ```
   Confirm: `one_default_per_team` index exists with `WHERE (is_default_for_team = true)`

8. Report back: **"All 3 migrations applied. 6 teemo_* tables present. Ready for STORY-003-04."**

### What happens after Coolify redeploys the backend

- `curl -s https://teemo.soula.ge/api/health | jq '.database | keys | length'` returns `6`
- `curl -s https://teemo.soula.ge/api/health | jq '.database'` shows all 6 keys with `"ok"` values
- `curl -s https://teemo.soula.ge/api/health | jq '.status'` returns `"ok"`

---

## Concerns

None. All SQL is copied verbatim from story spec §3.1-§3.3. The DO-block
safety pre-check in migration 007 provides a hard abort if the workspace table
contains stale data — zero risk of silent data loss.

The only thing that requires user action is the Supabase SQL execution above.
The backend code changes are fully tested locally and introduce no risk to the
22 existing auth/security tests.

## Product Docs Affected

None. No existing `vdocs/` behavior was changed — this story only adds new
tables and extends the health check response from 4 to 6 keys.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written alongside implementation (SINGLE-PASS) and pass
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-024, ADR-025)
- [x] Code is self-documenting (SQL header comments + Python docstring updates)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- Story spec §3.1-§3.3 provided complete, copy-paste-ready SQL — zero ambiguity.
  This is an excellent template for SQL migration stories.
- The dynamic `@pytest.mark.parametrize("failing_table", list(TEEMO_TABLES))`
  pattern in the existing test was a very clean design — adding 2 table entries
  automatically covered them in the degradation test without any test file changes
  beyond the new explicit 6-table assertion test. Worth preserving for future
  table additions.
