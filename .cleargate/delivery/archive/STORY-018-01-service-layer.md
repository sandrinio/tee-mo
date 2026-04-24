---
story_id: "STORY-018-01-service-layer"
parent_epic_ref: "EPIC-018"
status: "Shipped"
approved: true
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "TBD"
target_date: "TBD"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-14T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-01-service-layer.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-01: Automations Schema + Service Layer

**Complexity: L2** — Two new tables with triggers + plpgsql next-run function + a CRUD service module. Known pattern (matches `wiki_service.py` / `skill_service.py` shape).

---

## 1. The Spec (The Contract)

### 1.1 User Story
> This story **creates the persistence + business-logic foundation for scheduled automations** because every downstream layer (REST, cron executor, agent tools, frontend) reads and writes through this service. Until this lands, no other STORY-018-* can start.

### 1.2 Detailed Requirements

- **R1 — Migration `012_teemo_automations.sql`** creates `teemo_automations` and `teemo_automation_executions` using the new_app SQL as the source of truth, with Tee-Mo adaptations:
  - Table + function names renamed `chy_` → `teemo_`.
  - `channel_id UUID` (single FK) → **`slack_channel_ids TEXT[] NOT NULL` with `CHECK (array_length(slack_channel_ids, 1) >= 1)`**.
  - `delivered_content TEXT` on executions → **`delivery_results JSONB`**.
  - Execution `status` CHECK adds `'partial'`.
  - Execution adds `was_dry_run BOOLEAN DEFAULT FALSE`.
  - **RLS DISABLED** — workspace ownership enforced at application layer.
  - Use `CREATE TABLE IF NOT EXISTS` + `CREATE OR REPLACE FUNCTION` (idempotency).
- **R2 — `calculate_next_run_time(schedule JSONB, from_time TIMESTAMPTZ)`** — port of migration-034 version (IMMUTABLE, timezone-correct for `once`).
- **R3 — `get_due_automations()`** returns `SETOF teemo_automations WHERE is_active AND next_run_at IS NOT NULL AND next_run_at <= NOW() ORDER BY next_run_at ASC`.
- **R4 — BEFORE INSERT trigger** sets `next_run_at` from `calculate_next_run_time(NEW.schedule, NOW())` if active and NULL.
- **R5 — BEFORE UPDATE trigger** recalculates `next_run_at` when `schedule`, `timezone`, or `is_active` change.
- **R6 — `backend/app/services/automation_service.py`** module exporting:
  - `validate_schedule(schedule: dict) -> None`
  - `validate_channels(workspace_id: str, slack_channel_ids: list[str], *, supabase) -> None`
  - `create_automation(workspace_id, owner_user_id, payload, *, supabase) -> dict`
  - `list_automations(workspace_id, *, supabase) -> list[dict]`
  - `get_automation(workspace_id, automation_id, *, supabase) -> dict | None`
  - `update_automation(workspace_id, automation_id, patch, *, supabase) -> dict | None`
  - `delete_automation(workspace_id, automation_id, *, supabase) -> bool`
  - `get_automation_history(workspace_id, automation_id, *, supabase) -> list[dict]`
  - `prune_execution_history(automation_id, *, supabase, cap: int = 50) -> int`
- **R7 — Add both new tables to `TEEMO_TABLES`** in `backend/app/main.py`.

### 1.3 Out of Scope
- REST endpoints → STORY-018-02.
- Executor, cron loop, Slack delivery → STORY-018-03.
- Agent tools → STORY-018-04.
- Frontend → STORY-018-05 / 06.

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
    Then it returns 2026-04-20T19:40:00Z

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

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests (service) | 8 | 1 per exported function + 2 validation edge cases |
| Integration tests (SQL) | 4 | INSERT trigger, UPDATE trigger (schedule change), UPDATE trigger (deactivate), get_due_automations |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced. Gherkin scenarios from §2.1 each map to a test written red-first.
- [ ] Minimum test expectations (§4.1) met.
- [ ] FLASHCARDS.md consulted (migration idempotency, PostgREST filter rule, `teemo_` prefix, upsert DEFAULT omit rule).
- [ ] No ADR violations. RLS DISABLED as per Tee-Mo convention.
- [ ] Migration runs cleanly twice on a local Supabase (idempotency verified).
- [ ] `TEEMO_TABLES` updated; `/api/health` aggregates both tables.
- [ ] Service module has JSDoc/docstrings on every exported function.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
