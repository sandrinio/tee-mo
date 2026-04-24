---
story_id: "STORY-018-02-rest-endpoints"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-02-rest-endpoints.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-02: Automations REST Endpoints

**Complexity: L2** — 7 FastAPI endpoints wrapping the service from STORY-018-01. Mirrors the auth + ownership pattern from `channels.py`. Dry-run endpoint is the only non-trivial one.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **CRUD my workspace's scheduled automations and preview the result of a prompt on screen**, so that **I can build, audit, and safely experiment with automations without spamming Slack**.

### 1.2 Detailed Requirements

- **R1** — All 7 endpoints live in `backend/app/api/routes/automations.py`.
- **R2** — Ownership check uses `_assert_workspace_owner(workspace_id, user_id)` pattern from `channels.py:77`.
- **R3 — Endpoints**:

| # | Method | Path | Response | Status |
|---|--------|------|----------|--------|
| 1 | POST | `/api/workspaces/{workspace_id}/automations` | `AutomationResponse` | 201 |
| 2 | GET  | `/api/workspaces/{workspace_id}/automations` | `list[AutomationResponse]` | 200 |
| 3 | GET  | `/api/workspaces/{workspace_id}/automations/{automation_id}` | `AutomationResponse` | 200 (404 if missing) |
| 4 | PATCH | `/api/workspaces/{workspace_id}/automations/{automation_id}` | `AutomationResponse` | 200 |
| 5 | DELETE | `/api/workspaces/{workspace_id}/automations/{automation_id}` | — | 204 |
| 6 | GET | `/api/workspaces/{workspace_id}/automations/{automation_id}/history` | `list[AutomationExecutionResponse]` | 200 |
| 7 | POST | `/api/workspaces/{workspace_id}/automations/test-run` | `AutomationTestRunResponse` | 200 |

- **R4 — Pydantic models**: `AutomationCreate`, `AutomationUpdate`, `AutomationResponse`, `AutomationExecutionResponse`, `AutomationTestRunRequest`, `AutomationTestRunResponse`.
- **R5 — Error mapping**: `ValueError` → 422; missing automation → 404; duplicate name → 409.
- **R6 — Dry-run handler** builds a tool-free preview agent with 30-second `asyncio.wait_for(...)` timeout. Does NOT write to `teemo_automation_executions`.
- **R7 — Mount** the new router in `backend/app/main.py`.

### 1.3 Out of Scope
- Dry-run that writes a `was_dry_run=true` execution row — handled in STORY-018-06.
- Rate limits, pagination, filtering on list/history endpoints.
- Agent tools (STORY-018-04).
- Frontend (STORY-018-05 / 06).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Automations REST Endpoints

  Scenario: Create automation — happy path
    Given a workspace W owned by user U with bound channels [C1, C2]
    When U posts to /api/workspaces/W/automations with name, prompt, schedule daily 09:00, slack_channel_ids=[C1, C2]
    Then response 201 with AutomationResponse including computed next_run_at
    And a row exists in teemo_automations

  Scenario: Create automation — non-owner blocked
    Given user V who does not own workspace W
    When V posts to /api/workspaces/W/automations
    Then response 403

  Scenario: Create automation — empty channels list
    When the body's slack_channel_ids is []
    Then response 422 from Pydantic validation

  Scenario: Create automation — channel not bound
    When slack_channel_ids contains an id not in teemo_workspace_channels for this workspace
    Then response 422 with detail mentioning the channel

  Scenario: Create automation — duplicate name
    Given an automation "weekly-digest" already exists in W
    When another create is posted with the same name
    Then response 409 with detail

  Scenario: Get list — workspace-scoped
    Given workspace A has automation X and workspace B has automation Y
    When owner of A GETs /api/workspaces/A/automations
    Then the response contains X and NOT Y

  Scenario: Get one — 404 for missing id
    When owner of W GETs /api/workspaces/W/automations/{random-uuid}
    Then response 404

  Scenario: Patch — partial update
    Given automation X with prompt "old"
    When owner PATCHes {"prompt": "new"}
    Then response 200 and X.prompt == "new"
    And other fields unchanged

  Scenario: Patch — change schedule recomputes next_run_at
    Given automation X with daily 09:00 and next_run_at=T1
    When owner PATCHes {"schedule": {"occurrence": "daily", "when": "17:00"}}
    Then the trigger fires and next_run_at is set to the next 17:00 in the row's timezone

  Scenario: Delete — cascade
    Given automation X has 5 execution rows
    When owner DELETEs X
    Then response 204
    And teemo_automation_executions rows for X are gone (FK cascade)

  Scenario: History — last 50
    Given automation X has 60 execution rows
    When owner GETs /api/workspaces/W/automations/X/history
    Then response 200 with 50 rows sorted started_at DESC

  Scenario: Test-run — success
    Given workspace W has a valid BYOK key
    When owner POSTs /api/workspaces/W/automations/test-run with prompt "say hello"
    Then response 200 with {success: True, output: "<non-empty>"}
    And NO row is written to teemo_automation_executions

  Scenario: Test-run — missing BYOK key
    Given workspace W has no BYOK key
    When owner POSTs the test-run endpoint
    Then response 200 with {success: False, error: "no_key_configured"}

  Scenario: Test-run — timeout
    Given the BYOK provider hangs
    When the request exceeds 30s
    Then response 200 with {success: False, error: "timeout after 30s"}
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| E2E / acceptance tests | 13 | One per Gherkin scenario in §2.1 |
| Integration tests | 7 | One per endpoint, covering at least happy path + one error |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced. Every Gherkin scenario in §2.1 has a failing test before implementation.
- [ ] Minimum test expectations met.
- [ ] No ADR violations. Owner assertion on every endpoint.
- [ ] OpenAPI docs at `/docs` show all 7 endpoints with full schemas.
- [ ] Router mounted in `main.py`; no import cycles.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
