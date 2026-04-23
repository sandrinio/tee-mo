---
story_id: "STORY-018-03-executor-cron"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §3.3, §4, §6; backend/app/services/wiki_ingest_cron.py (cron pattern); backend/app/services/drive_sync_cron.py (cron pattern); backend/app/main.py (lifespan registration); new_app automation_executor.py + workers/cron.py (copy-then-strip reference)"
actor: "Background Scheduler (no human actor — fires autonomously)"
complexity_label: "L2"
---

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

**Step 1 — Skip-if-active guard**
- Query `teemo_automation_executions` for any row where `automation_id = auto["id"]` AND `status = 'running'`.
- If found: log `executor.automation_skipped`, return `{"skipped": True, "automation_id": auto["id"]}`. Do NOT write an execution row. Do NOT crash.

**Step 2 — Create execution row**
- INSERT into `teemo_automation_executions`: `automation_id`, `status='running'`, `was_dry_run=False`, `started_at=now()`.
- Store the returned `exec_id`.

**Step 3 — Resolve BYOK key**
- Query `teemo_workspaces` for `ai_provider`, `ai_model`, `encrypted_api_key` where `id = auto["workspace_id"]`.
- Decrypt `encrypted_api_key` via `app.core.encryption.decrypt`.
- If workspace missing OR `encrypted_api_key` is NULL: update execution row with `status='failed'`, `error="BYOK key not configured for this workspace"`, `completed_at=now()`. Advance `next_run_at`. Return early.

**Step 4 — Build and run agent**
- Import `build_agent` from `app.agents.agent`.
- Call `build_agent(workspace_id=auto["workspace_id"], supabase=supabase, provider=provider, api_key=api_key, model=model, user_id=auto["owner_user_id"])`.
- Run: `result = await asyncio.wait_for(agent.run(auto["prompt"], deps=deps), timeout=120.0)`.
- Extract `generated_content = result.output` (str).
- Extract `tokens_used` from `result.usage().total_tokens` (int, or None if unavailable — wrap in try/except).
- On `asyncio.TimeoutError`: set `generated_content = None`, `error = "Agent timed out after 120s"`, set execution status to `'failed'`, advance next_run_at, return.
- On any other exception: capture error string, status `'failed'`, advance, return.

**Step 5 — Deliver to Slack channels**
- For each `channel_id` in `automation["slack_channel_ids"]`:
  - Look up `teemo_slack_teams` joined to workspace to get `encrypted_slack_bot_token`. (Query `teemo_workspaces` → `slack_team_id` → `teemo_slack_teams.encrypted_slack_bot_token`.)
  - Decrypt token via `app.core.encryption.decrypt`.
  - Call `AsyncWebClient(token=plaintext_token).chat_postMessage(channel=channel_id, text=generated_content)`.
  - Record per-channel result: `{"channel_id": channel_id, "ok": True, "ts": response["ts"]}` on success, `{"channel_id": channel_id, "ok": False, "error": str(exc)}` on `SlackApiError` or any exception.
- Compute overall `status`:
  - All channels `ok=True` → `'success'`
  - Some `ok=True`, some `ok=False` → `'partial'`
  - All `ok=False` (or zero channels) → `'failed'`

**Step 6 — Finalise execution row**
- UPDATE `teemo_automation_executions` SET:
  - `status` (computed above)
  - `completed_at = now()`
  - `generated_content` (text from agent)
  - `delivery_results` (JSONB list of per-channel dicts)
  - `error` (top-level error string if Step 4 failed; NULL on success/partial)
  - `tokens_used`
  - `execution_time_ms` (ms elapsed since `started_at`)

**Step 7 — Advance schedule + bookkeeping**
- UPDATE `teemo_automations` SET `last_run_at = now()`.
- Compute next run:
  - If `auto["schedule_type"] == "once"`: SET `is_active=False`, `next_run_at=NULL`.
  - Else: Call Postgres RPC `calculate_next_run_time` with `{"schedule": auto["schedule"], "from_time": now().isoformat()}`, store result as `next_run_at`.
- Call `automation_service.prune_execution_history(auto["id"], supabase=supabase)` (cap 50 rows).

**Step 8 — Startup stale-run cleanup** (module-level function, not inside `execute_automation`)
- `async def reset_stale_executions(*, supabase) -> int` — on service start, UPDATE any `teemo_automation_executions` rows with `status='running'` AND `started_at < now() - interval '10 minutes'` to `status='failed'`, `error="Service restarted during execution"`, `completed_at=now()`. Return count. Log result.

---

#### R2 — `backend/app/services/automation_cron.py` (new module)

Structure mirrors `wiki_ingest_cron.py` exactly:

```python
async def automation_cron_loop() -> None:
    """Infinite 60-second loop — picks up due automations and executes them."""
    while True:
        try:
            # 1. Query due automations via RPC
            supabase = get_supabase()
            result = supabase.rpc("get_due_automations").execute()
            due: list[dict] = result.data or []

            executed, skipped, failed = 0, 0, 0
            for auto in due:
                try:
                    outcome = await execute_automation(auto, supabase=supabase)
                    if outcome.get("skipped"):
                        skipped += 1
                    else:
                        executed += 1
                except Exception as exc:
                    failed += 1
                    logger.error("cron.automation.error", ...)

            logger.info("cron.automation.complete", extra={..., "executed": executed, ...})
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("cron.automation.shutdown", ...)
            raise
        except Exception as exc:
            logger.exception("cron.automation.loop_error", ...)
```

Structured log events:
- `cron.automation.init` — on startup
- `cron.automation.start` — beginning of each cycle
- `cron.automation.complete` — end of cycle (with executed/skipped/failed counts)
- `cron.automation.error` — per-automation failure (automation_id, error)
- `cron.automation.shutdown` — on CancelledError

---

#### R3 — `backend/app/main.py` modifications

**Imports** (add at top alongside existing cron imports):
```python
from app.services.automation_cron import automation_cron_loop
from app.services.automation_executor import reset_stale_executions
```

**Lifespan** — add a third cron task alongside the existing two:
```python
# Startup: call reset_stale_executions first
await reset_stale_executions(supabase=get_supabase())

# Register third cron task
automation_cron_task = asyncio.create_task(automation_cron_loop())
logger.info("lifespan.startup", extra={..., "detail": "Automation cron registered"})
```

**Shutdown** — cancel and await the third task following the existing `try/except CancelledError` pattern.

---

### 1.3 Out of Scope
- ARQ / Redis — asyncio loop only.
- Dry-run via cron — dry-run is a REST endpoint concern (STORY-018-02).
- Multi-replica leader election — single-process cron; `SELECT ... FOR UPDATE SKIP LOCKED` is a future concern.
- Per-channel content customisation — same `generated_content` posted to all channels.
- Retry on failure — failed runs record error and advance schedule; no auto-retry.
- Agent tool for test-run — UI-only (STORY-018-02).

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

### 2.2 Test File
`backend/tests/test_automation_executor.py`

Mocks required:
- `app.agents.agent.build_agent` — return (mock_agent, mock_deps)
- `slack_sdk.web.async_client.AsyncWebClient.chat_postMessage` — return success or raise SlackApiError
- `app.core.encryption.decrypt` — return plaintext token/key
- `app.core.db.get_supabase` — return mock supabase client
- Supabase table queries (teemo_automations, teemo_automation_executions, teemo_workspaces, teemo_slack_teams)
- `supabase.rpc("calculate_next_run_time")` — return ISO 8601 datetime string
- `supabase.rpc("get_due_automations")` — return list of automation dicts

---

## 3. Implementation Guide

### 3.1 File Map

| File | Action | Notes |
|------|--------|-------|
| `backend/app/services/automation_executor.py` | **Create** | Full executor pipeline |
| `backend/app/services/automation_cron.py` | **Create** | 60s poll loop |
| `backend/app/main.py` | **Modify** | Register 3rd cron + startup cleanup |
| `backend/tests/test_automation_executor.py` | **Create** | Unit tests with mocks |

### 3.2 Execution Row Timing

Use `time.monotonic()` for `execution_time_ms` — start before Step 4, end after Step 5:

```python
import time
t0 = time.monotonic()
# ... Steps 4–5 ...
execution_time_ms = int((time.monotonic() - t0) * 1000)
```

### 3.3 Slack Token Resolution

The workspace has a `slack_team_id` FK. Resolution chain:
```python
# 1. Get workspace row (already fetched in Step 3 for BYOK)
ws_row = supabase.table("teemo_workspaces").select("slack_team_id, ai_provider, ai_model, encrypted_api_key").eq("id", workspace_id).maybe_single().execute().data

# 2. Get Slack team row
slack_row = supabase.table("teemo_slack_teams").select("encrypted_slack_bot_token").eq("slack_team_id", ws_row["slack_team_id"]).maybe_single().execute().data

# 3. Decrypt
bot_token = decrypt(slack_row["encrypted_slack_bot_token"])
```

Cache this per-execution (not per-channel) — decrypt once, reuse for all channels.

### 3.4 Postgres RPC call for next_run_at

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
rpc_result = supabase.rpc(
    "calculate_next_run_time",
    {"schedule": automation["schedule"], "from_time": now.isoformat()}
).execute()
next_run_at = rpc_result.data  # ISO 8601 string or None
```

If `rpc_result.data` is None (e.g. schedule is malformed), set `next_run_at = None` — don't crash.

### 3.5 main.py Pattern (copy-extend)

```python
# Existing pattern to extend:
cron_task = asyncio.create_task(drive_sync_loop())
wiki_cron_task = asyncio.create_task(wiki_ingest_loop())
# Add:
await reset_stale_executions(supabase=get_supabase())
automation_cron_task = asyncio.create_task(automation_cron_loop())

# Shutdown (extend existing cancel block):
automation_cron_task.cancel()
try:
    await automation_cron_task
except asyncio.CancelledError:
    pass
```

### 3.6 Import guard (lazy encryption import)

Use the same lazy import pattern as `wiki_ingest_cron._resolve_workspace_key`:

```python
from app.core.encryption import decrypt  # inside function body, not module top
```

This avoids env-var load at import time and makes tests easier to mock.

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-15 | Claude (doc-manager) | Initial draft. Port from new_app automation_executor.py + workers/cron.py, stripped to Tee-Mo shape: asyncio loop (no ARQ), slack_channel_ids array fanout with delivery_results JSONB, workspace BYOK only, no data-source injection, no mention resolution. |
