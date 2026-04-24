---
story_id: "STORY-018-03-executor-cron"
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
created_at: "2026-04-15T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-03-executor-cron.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-03: Automation Executor + Cron Loop

**Complexity: L2** — End-to-end execution pipeline + asyncio cron loop. Well-defined pattern (mirrors `wiki_ingest_cron.py`). Main risk surface: Slack fanout + partial-delivery status logic + skip-if-active guard.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As the **background scheduler**, I want to **pick up due automations every 60 seconds, run each prompt through the workspace agent, and deliver the result to every target Slack channel**, so that **scheduled posts land within ±60s of `next_run_at` without any human action**.

### 1.2 Detailed Requirements

#### R1 — `backend/app/services/automation_executor.py` (new module)

Entry point: `async def execute_automation(automation: dict, *, supabase) -> dict`

Full execution pipeline:

**Step 1 — Skip-if-active guard**: Query for any existing `status='running'` execution for this automation. If found, return `{"skipped": True}` without writing a new row.

**Step 2 — Create execution row**: INSERT into `teemo_automation_executions` with `status='running'`.

**Step 3 — Resolve BYOK key**: Query workspace; decrypt `encrypted_api_key`. If missing, write `status='failed'` with error and return early.

**Step 4 — Build and run agent**: Call `build_agent`, run with 120s `asyncio.wait_for(...)` timeout.

**Step 5 — Deliver to Slack channels**: For each `channel_id` in `automation["slack_channel_ids"]`, call `AsyncWebClient.chat_postMessage`. Record per-channel result. Compute overall `status`: all ok → `'success'`; some ok → `'partial'`; all fail → `'failed'`.

**Step 6 — Finalise execution row**: UPDATE with `status`, `completed_at`, `generated_content`, `delivery_results`, `error`, `tokens_used`, `execution_time_ms`.

**Step 7 — Advance schedule**: UPDATE `last_run_at`. If `schedule_type='once'`, set `is_active=False`, `next_run_at=NULL`. Else call `calculate_next_run_time` RPC for next `next_run_at`. Call `prune_execution_history`.

**Step 8 — Startup stale-run cleanup**: `async def reset_stale_executions(*, supabase) -> int` — on service start, UPDATE any `status='running'` rows older than 10 minutes to `status='failed'`.

#### R2 — `backend/app/services/automation_cron.py` (new module)

60-second asyncio loop mirroring `wiki_ingest_cron.py` exactly. Calls `supabase.rpc("get_due_automations")`, iterates results, calls `execute_automation` per item. Handles `CancelledError` for clean shutdown.

#### R3 — `backend/app/main.py` modifications

Add imports, call `reset_stale_executions` at startup, register third cron task `automation_cron_task = asyncio.create_task(automation_cron_loop())`, cancel and await on shutdown.

### 1.3 Out of Scope
- ARQ / Redis.
- Dry-run via cron — dry-run is a REST endpoint concern.
- Multi-replica leader election.
- Per-channel content customisation.
- Retry on failure.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Automation Executor

  Scenario: Happy path — single channel, success
    Given workspace W with BYOK key and a bound channel C1
    And an active automation A due now targeting [C1]
    When execute_automation(A, supabase=...) is called
    Then an execution row is written with status='running' first
    And build_agent is called with workspace W's provider + key
    And chat_postMessage is called with channel=C1 and generated_content
    And the execution row is updated to status='success', completed_at set, delivery_results=[{channel_id: C1, ok: True}]
    And A.last_run_at is updated
    And A.next_run_at is advanced to the next scheduled instant

  Scenario: Multi-channel fanout — partial delivery
    Given automation A targeting [C1, C2]
    And the Slack client raises SlackApiError('not_in_channel') for C2
    When execute_automation(A, ...) completes
    Then execution row status = 'partial'
    And delivery_results = [{channel_id: C1, ok: True, ts: "..."}, {channel_id: C2, ok: False, error: "not_in_channel"}]
    And next_run_at is still advanced

  Scenario: All channels fail
    Given automation A targeting [C1] and Slack raises SlackApiError for C1
    When execute_automation(A, ...) completes
    Then execution row status = 'failed'
    And next_run_at is still advanced (automation stays active)

  Scenario: Skip-if-active guard
    Given an existing execution row for automation A with status='running'
    When execute_automation(A, ...) is called again
    Then no new execution row is written
    And the function returns {"skipped": True}

  Scenario: BYOK key missing
    Given workspace W with no encrypted_api_key
    When execute_automation(A, ...) is called
    Then execution row is written with status='failed' and error="BYOK key not configured for this workspace"
    And next_run_at is still advanced

  Scenario: Agent timeout
    Given build_agent returns an agent that hangs > 120s
    When execute_automation(A, ...) is called
    Then execution row status = 'failed', error contains "timed out after 120s"
    And next_run_at is advanced

  Scenario: One-time automation deactivates after run
    Given automation A with schedule_type='once' and due now
    When execute_automation(A, ...) completes successfully
    Then A.is_active = False and A.next_run_at = NULL

  Scenario: Execution history is pruned to 50 rows
    Given automation A with 55 execution rows
    When execute_automation(A, ...) completes (run #56)
    Then teemo_automation_executions has exactly 50 rows for A (newest 50)

  Scenario: Cron loop picks up due automations
    Given 3 automations due now and 1 not due
    When automation_cron_loop() runs one tick
    Then execute_automation is called exactly 3 times
    And the not-due automation is not touched

  Scenario: Stale running execution is reset on startup
    Given an execution row with status='running' started 15 minutes ago
    When reset_stale_executions(supabase=...) is called
    Then that row is updated to status='failed', error="Service restarted during execution", completed_at set
    And the function returns count=1

  Scenario: Cron loop continues after per-automation failure
    Given 3 due automations where A2 raises an unexpected exception
    When automation_cron_loop() runs one tick
    Then A1 and A3 are executed successfully
    And the loop does not crash
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 11 | One per Gherkin scenario |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced.
- [ ] All Gherkin scenarios covered.
- [ ] Cron loop registers correctly in `main.py` lifespan.
- [ ] No ADR violations.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
