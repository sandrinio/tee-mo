---
story_id: "STORY-018-01-service-layer"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §4; new_app migrations 025 + 034; backend/app/core/keys.py; backend/app/api/routes/channels.py"
actor: "Workspace Admin (indirect — service feeds REST + executor + agent tools)"
complexity_label: "L2"
---

# STORY-018-01: Automations Schema + Service Layer

**Complexity: L2** — Two new tables with triggers + plpgsql next-run function + a CRUD service module. Known pattern (matches `wiki_service.py` / `skill_service.py` shape).

---

## 1. The Spec (The Contract)

### 1.1 User Story
> This story **creates the persistence + business-logic foundation for scheduled automations** because every downstream layer (REST, cron executor, agent tools, frontend) reads and writes through this service. Until this lands, no other STORY-018-* can start.

### 1.2 Detailed Requirements

- **R1 — Migration `012_teemo_automations.sql`** creates `teemo_automations` and `teemo_automation_executions` using the new_app SQL as the source of truth, with these **Tee-Mo adaptations**:
  - Table + function names renamed `chy_` → `teemo_`.
  - `channel_id UUID` (single FK) → **`slack_channel_ids TEXT[] NOT NULL` with `CHECK (array_length(slack_channel_ids, 1) >= 1)`**.
  - `delivered_content TEXT` on executions → **`delivery_results JSONB`** (per-channel result array).
  - Execution `status` CHECK adds `'partial'`: `CHECK (status IN ('pending','running','success','partial','failed'))`.
  - Execution adds `was_dry_run BOOLEAN DEFAULT FALSE`.
  - **RLS DISABLED** (all other teemo_* tables disable RLS; workspace ownership is enforced at the application layer via `_assert_workspace_owner`). Do NOT copy new_app's RLS policies.
  - Use `CREATE TABLE IF NOT EXISTS` + `CREATE OR REPLACE FUNCTION` (idempotency per FLASHCARDS migration conventions).
- **R2 — `calculate_next_run_time(schedule JSONB, from_time TIMESTAMPTZ)`** is a direct port of the **migration-034 version** (IMMUTABLE, timezone-correct for `once`). Do NOT port the earlier 025 version.
- **R3 — `get_due_automations()`** returns `SETOF teemo_automations WHERE is_active AND next_run_at IS NOT NULL AND next_run_at <= NOW() ORDER BY next_run_at ASC`.
- **R4 — BEFORE INSERT trigger** sets `next_run_at` from `calculate_next_run_time(NEW.schedule, NOW())` if active and NULL.
- **R5 — BEFORE UPDATE trigger** recalculates `next_run_at` when `schedule`, `timezone`, or `is_active` change. Sets `next_run_at = NULL` when `is_active` becomes false. Always bumps `updated_at = now()`.
- **R6 — `backend/app/services/automation_service.py`** module exporting these functions (all accept `supabase` as keyword-only param, following `skill_service.py` convention):
  - `validate_schedule(schedule: dict) -> None` — raises `ValueError` on invalid shape. Validates occurrence ∈ {daily, weekdays, weekly, monthly, once}; required keys per occurrence; `days` ⊂ {0..6}; `day_of_month` ∈ 1..31; `when` matches `HH:MM`; `at` is ISO 8601 and in the future (when occurrence=once).
  - `validate_channels(workspace_id: str, slack_channel_ids: list[str], *, supabase) -> None` — raises `ValueError` if ≥1 id is missing from `teemo_workspace_channels` for this workspace. Must accept ≥1 id (empty list is invalid).
  - `create_automation(workspace_id, owner_user_id, payload, *, supabase) -> dict` — validates, inserts row (trigger computes next_run_at), returns the row.
  - `list_automations(workspace_id, *, supabase) -> list[dict]` — ordered `created_at DESC`.
  - `get_automation(workspace_id, automation_id, *, supabase) -> dict | None` — filters by BOTH ids (workspace isolation).
  - `update_automation(workspace_id, automation_id, patch, *, supabase) -> dict | None` — partial update; re-validates schedule if `schedule` in patch; re-validates channels if `slack_channel_ids` in patch.
  - `delete_automation(workspace_id, automation_id, *, supabase) -> bool` — returns True if a row was deleted. Cascade deletes execution history via FK.
  - `get_automation_history(workspace_id, automation_id, *, supabase) -> list[dict]` — last 50 executions DESC by `started_at`.
  - `prune_execution_history(automation_id, *, supabase, cap: int = 50) -> int` — deletes executions beyond the newest `cap` rows for that automation; returns deleted count. Idempotent.
- **R7 — Add both new tables to `TEEMO_TABLES` tuple** in `backend/app/main.py:200` so `/api/health` aggregates them. (This is the only `main.py` change in this story.)
- **R8 — FLASHCARD compliance**: after implementation, if a new gotcha is discovered (e.g. `jsonb_typeof` double-encoding), record it.

### 1.3 Out of Scope
- REST endpoints → STORY-018-02.
- Executor, cron loop, Slack delivery → STORY-018-03.
- Agent tools → STORY-018-04.
- Frontend → STORY-018-05 / 06.
- Skill card seed (`teemo_skills` INSERT) → STORY-018-04 (lives with the agent tools it describes).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Automations Schema + Service

  Scenario: Migration creates both tables idempotently
    Given the migration file 012_teemo_automations.sql
    When I run it twice against a clean DB
    Then both runs succeed
    And teemo_automations + teemo_automation_executions exist
    And the status CHECK on executions permits 'partial'
    And /api/health reports row counts for both tables

  Scenario: calculate_next_run_time — daily 09:00 UTC
    Given schedule {"occurrence": "daily", "when": "09:00"} and from_time 2026-04-14T10:00:00Z
    When I call calculate_next_run_time(schedule, from_time)
    Then it returns 2026-04-15T09:00:00Z

  Scenario: calculate_next_run_time — once in user's timezone
    Given schedule {"occurrence": "once", "at": "2026-04-20T23:40:00"} with timezone Asia/Tbilisi
    When I call calculate_next_run_time(schedule)
    Then it returns 2026-04-20T19:40:00Z  # 23:40 Tbilisi = 19:40 UTC

  Scenario: Trigger sets next_run_at on insert
    When I INSERT a row with is_active=TRUE, schedule daily 09:00, next_run_at NULL
    Then the BEFORE INSERT trigger fills next_run_at with the correct future instant

  Scenario: Trigger clears next_run_at when disabled
    Given an active automation with next_run_at set
    When I UPDATE is_active=FALSE
    Then next_run_at becomes NULL

  Scenario: create_automation writes a valid row
    Given workspace W and two bound channels C1, C2
    When I call create_automation with slack_channel_ids=[C1, C2]
    Then a row is written with those channels and next_run_at populated

  Scenario: create_automation rejects unbound channel
    Given workspace W without channel C99 bound
    When I call create_automation with slack_channel_ids=[C99]
    Then ValueError is raised and no row is written

  Scenario: validate_schedule rejects empty channel list
    When I call validate_channels with []
    Then ValueError is raised

  Scenario: validate_schedule rejects past once-at
    When I call validate_schedule({"occurrence": "once", "at": "2020-01-01T00:00:00"})
    Then ValueError is raised with message mentioning "in the past"

  Scenario: update_automation partial patch preserves unchanged fields
    Given an automation with name="A", prompt="P1", schedule daily 09:00
    When I call update_automation with {"prompt": "P2"}
    Then name="A" and schedule unchanged, prompt="P2", updated_at bumped

  Scenario: get_automation is workspace-scoped
    Given automation X in workspace A
    When I call get_automation(workspace_id=B, automation_id=X)
    Then it returns None (no cross-workspace leak)

  Scenario: prune_execution_history caps at 50
    Given 55 execution rows for automation X
    When I call prune_execution_history(X)
    Then 5 oldest rows are deleted, 50 remain

  Scenario: get_due_automations returns only due+active
    Given 3 automations: (active, past next_run), (active, future next_run), (inactive, past next_run)
    When I SELECT * FROM get_due_automations()
    Then only the first is returned
```

### 2.2 Verification Steps (Manual)
- [ ] Apply migration to local Supabase; re-apply — no error.
- [ ] `SELECT * FROM pg_trigger WHERE tgrelid = 'teemo_automations'::regclass` shows both triggers.
- [ ] `curl localhost:8000/api/health` shows both new table counts.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | [ ] |
| **Services Running** | Self-hosted Supabase reachable | [ ] |
| **Migrations** | 001–011 already applied (`teemo_workspaces`, `teemo_workspace_channels` must exist) | [ ] |
| **Dependencies** | `pip install -r backend/requirements.txt` (no new packages needed) | [ ] |

### 3.1 Test Implementation
- **Unit tests** for `automation_service.py` → `backend/tests/test_automation_service.py`. Reuse `_make_supabase_mock()` helper pattern from `backend/tests/test_wiki_ingest_cron.py:54–142`.
- **DB integration tests** for triggers + `calculate_next_run_time` + `get_due_automations` → `backend/tests/test_automation_migration.py`. Uses real Supabase client (or a pg test container if we have one; otherwise skip with `@pytest.mark.integration`).
- Each Gherkin scenario above gets at least one test. L2 → **≥ 8 unit tests + ≥ 4 integration tests**.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/automation_service.py` (**NEW**) |
| **Related Files** | `database/migrations/012_teemo_automations.sql` (**NEW**), `backend/app/main.py` (modify `TEEMO_TABLES`), `backend/tests/test_automation_service.py` (**NEW**), `backend/tests/test_automation_migration.py` (**NEW**) |
| **New Files Needed** | Yes — migration + service + two test files |
| **ADR References** | ADR-002 (AES-GCM — not used here but keep mental model), ADR-024 (workspace model), ADR-015 (Supabase), ADR-020 (self-hosted Supabase). No new ADR required. |
| **First-Use Pattern** | **Yes — plpgsql trigger + BEFORE INSERT/UPDATE function computing a timestamp column.** No prior Tee-Mo table uses `CREATE TRIGGER ... EXECUTE FUNCTION` for next_run_at-style computation. Developer: grep `database/migrations/` for `CREATE TRIGGER`; port the `trigger_set_automation_next_run` + `trigger_update_automation_next_run` patterns verbatim from new_app/025. |

### 3.3 Technical Logic

**Migration `012_teemo_automations.sql`** — structure, in order:
1. Header comment (purpose + ADR refs + dependencies on 002/006).
2. `CREATE TABLE IF NOT EXISTS teemo_automations` — copy new_app/025 columns, swap `channel_id UUID` line for:
   ```sql
   slack_channel_ids TEXT[] NOT NULL,
   ```
   add a separate `CONSTRAINT check_slack_channel_ids_nonempty CHECK (array_length(slack_channel_ids, 1) >= 1)`.
   Keep `schedule_type TEXT NOT NULL DEFAULT 'recurring' CHECK (schedule_type IN ('recurring', 'once'))` from new_app/025 — do **not** remove it.
   **Do NOT include** columns from new_app migrations 030 (`internet_search`), 031 (`data_source_type`, `data_source_id`), or 041 (`delivery_method`) — out of S-018 scope.
3. `CREATE TABLE IF NOT EXISTS teemo_automation_executions` — copy new_app/025 columns, add `was_dry_run BOOLEAN DEFAULT FALSE`, replace `delivered_content TEXT` with `delivery_results JSONB`, extend status CHECK with `'partial'`.
4. Indexes: `idx_teemo_automations_due`, `idx_teemo_automations_workspace`, `idx_teemo_automation_executions_automation` (names renamed).
5. `CREATE OR REPLACE FUNCTION calculate_next_run_time(...)` — **copy verbatim from `/Users/ssuladze/Documents/Dev/new_app/database/migrations/034_fix_once_schedule_timezone.sql` lines 14–152**. Function is IMMUTABLE. No rename needed.
6. `CREATE OR REPLACE FUNCTION get_due_automations()` — copy from new_app/025 lines 198–205, rename `chy_automations` → `teemo_automations`.
7. Two BEFORE triggers + their plpgsql functions — copy from new_app/025 lines 245–279, rename all `chy_` → `teemo_`.
8. `ALTER TABLE teemo_automations DISABLE ROW LEVEL SECURITY; ALTER TABLE teemo_automation_executions DISABLE ROW LEVEL SECURITY;` — matches Tee-Mo convention (migration 006 line 25).
9. **Do NOT** include the new_app RLS policies (lines 282–337) or the skill card INSERT (lines 340–363).
10. Trailing `RAISE NOTICE '✓ teemo_automations migration complete'` (matches 010/011 style).

**Service module `automation_service.py`** — structure:
- Top-of-file docstring referencing EPIC-018 STORY-018-01 (matches `wiki_service.py` style).
- **Module-level imports**: `from app.core.db import get_supabase` only as type hint; actual client always passed in.
- `OCCURRENCE_VALIDATORS: dict[str, Callable]` — small dispatch table for schedule validation (one validator per occurrence type).
- All DB mutations accept `supabase` via keyword-only (`*, supabase`).
- On `create_automation`: call `validate_schedule(payload["schedule"])` → `validate_channels(workspace_id, payload["slack_channel_ids"], supabase=supabase)` → insert.
- On `update_automation`: re-validate only the fields present in the patch. Use `.update({...}).eq("id", automation_id).eq("workspace_id", workspace_id)`.
- On `prune_execution_history`: select `id` ordered `started_at DESC` offset 50 → delete those ids in one call.

**Supabase gotcha (FLASHCARDS)** — `.upsert()` with `DEFAULT NOW()` columns: **omit `created_at` / `updated_at` / `next_run_at` / `last_run_at` from every write payload**. Let the DB + triggers fill them.

**PostgREST filter gotcha (FLASHCARDS)** — do NOT write `.filter("next_run_at", "lte", "NOW() + interval '1 hour'")`. Compute timestamps in Python (`datetime.now(timezone.utc).isoformat()`) and pass the literal value.

### 3.4 API Contract

N/A — this story adds no HTTP endpoints.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests (service) | 8 | 1 per exported function + 2 validation edge cases |
| Integration tests (SQL) | 4 | INSERT trigger, UPDATE trigger (schedule change), UPDATE trigger (deactivate), get_due_automations |
| E2E / acceptance tests | 0 — N/A (no HTTP surface in this story) | — |
| Component tests | 0 — N/A (no UI in this story) | — |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced. Gherkin scenarios from §2.1 each map to a test written red-first.
- [ ] Minimum test expectations (§4.1) met.
- [ ] FLASHCARDS.md consulted (migration idempotency, PostgREST filter rule, `teemo_` prefix, upsert DEFAULT omit rule).
- [ ] No ADR violations. RLS DISABLED as per Tee-Mo convention.
- [ ] Migration runs cleanly twice on a local Supabase (idempotency verified).
- [ ] `TEEMO_TABLES` updated; `/api/health` aggregates both tables.
- [ ] Service module has JSDoc/docstrings on every exported function.
- [ ] Framework Integrity: none of `.claude/agents/`, `.vbounce/skills/`, `.vbounce/templates/`, `.vbounce/scripts/` modified.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 28 | 1,573 | 1,601 |
| Developer | 21 | 575 | 596 |
| DevOps | 14 | 250 | 264 |
