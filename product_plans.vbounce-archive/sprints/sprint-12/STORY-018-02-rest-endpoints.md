---
story_id: "STORY-018-02-rest-endpoints"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §4; backend/app/api/routes/channels.py (auth pattern); new_app automations.py (endpoint shapes)"
actor: "Workspace Admin (Dashboard)"
complexity_label: "L2"
---

# STORY-018-02: Automations REST Endpoints

**Complexity: L2** — 7 FastAPI endpoints wrapping the service from STORY-018-01. Mirrors the auth + ownership pattern from `channels.py`. Dry-run endpoint is the only non-trivial one (it builds a tool-free preview agent).

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **CRUD my workspace's scheduled automations and preview the result of a prompt on screen**, so that **I can build, audit, and safely experiment with automations without spamming Slack**.

### 1.2 Detailed Requirements

- **R1 — All 7 endpoints** live in a new `backend/app/api/routes/automations.py` router. The router is mounted at the app level in `backend/app/main.py` (same location other routers are registered).
- **R2 — Ownership check** uses the exact same `_assert_workspace_owner(workspace_id, user_id)` pattern as `channels.py:77`. Copy or import it — do not reinvent. All mutating endpoints require owner; `GET` endpoints also require ownership for v1 (Tee-Mo has no member-role concept in schema yet).
- **R3 — Endpoints** (auth = `Depends(get_current_user_id)` + owner assert on every):

| # | Method | Path | Request body | Response | Status |
|---|--------|------|--------------|----------|--------|
| 1 | POST | `/api/workspaces/{workspace_id}/automations` | `AutomationCreate` | `AutomationResponse` | 201 |
| 2 | GET  | `/api/workspaces/{workspace_id}/automations` | — | `list[AutomationResponse]` | 200 |
| 3 | GET  | `/api/workspaces/{workspace_id}/automations/{automation_id}` | — | `AutomationResponse` | 200 (404 if missing) |
| 4 | PATCH | `/api/workspaces/{workspace_id}/automations/{automation_id}` | `AutomationUpdate` | `AutomationResponse` | 200 |
| 5 | DELETE | `/api/workspaces/{workspace_id}/automations/{automation_id}` | — | — | 204 |
| 6 | GET | `/api/workspaces/{workspace_id}/automations/{automation_id}/history` | — | `list[AutomationExecutionResponse]` | 200 |
| 7 | POST | `/api/workspaces/{workspace_id}/automations/test-run` | `AutomationTestRunRequest` | `AutomationTestRunResponse` | 200 |

- **R4 — Pydantic models** defined in `automations.py` at module scope:
  - `AutomationCreate`: `name: str`, `prompt: str`, `schedule: dict`, `slack_channel_ids: list[str]` (min_length=1), `schedule_type: Literal["recurring","once"] = "recurring"`, `timezone: str = "UTC"`, `description: str | None = None`.
  - `AutomationUpdate`: all fields optional.
  - `AutomationResponse`: matches the DB row (`id, workspace_id, name, description, prompt, slack_channel_ids, schedule, schedule_type, timezone, is_active, owner_user_id, last_run_at, next_run_at, created_at, updated_at`).
  - `AutomationExecutionResponse`: `id, automation_id, status, was_dry_run, started_at, completed_at, generated_content, delivery_results, error, tokens_used, execution_time_ms`.
  - `AutomationTestRunRequest`: `prompt: str` (single field — dry-run never persists a schedule).
  - `AutomationTestRunResponse`: `{success: bool, output: str | None, error: str | None, tokens_used: int | None, execution_time_ms: int | None}`.
- **R5 — Error mapping**:
  - `automation_service.ValueError` → 422 with `{"detail": "<message>"}`.
  - `get_automation` returning None → 404 with `{"detail": "Automation not found"}`.
  - Name collision on create (DB unique violation) → 409 `{"detail": "Automation with name '<x>' already exists"}`.
- **R6 — Dry-run handler** builds a **tool-free preview agent** so the prompt executes under the workspace's BYOK model but without side-effecting tools:
  1. `_assert_workspace_owner(workspace_id, user_id)` first.
  2. Read the workspace's `ai_provider + ai_model + encrypted_api_key` (use existing `build_agent()` logic path, but we need a lightweight version — see §3.3).
  3. If no BYOK key → return 200 with `{success: False, output: None, error: "no_key_configured", ...}` (do not 500).
  4. Build a **tool-free** `Agent(model=..., system_prompt="You are a preview agent...")` — NO tools registered, NO skills, NO wiki, NO documents. Just the model + the user prompt.
  5. Run with 30-second `asyncio.wait_for(...)` timeout.
  6. Return `{success, output, error, tokens_used, execution_time_ms}`. On timeout return `success=False, error="timeout after 30s"`.
  7. **Do NOT** write to `teemo_automation_executions` from this endpoint — dry-run history is captured by the UI-facing flow in STORY-018-06 (which goes through a **different** path: it writes a `was_dry_run=true` execution row via a new branch in the executor). For v1, the test-run endpoint is purely ephemeral — a "try the prompt right now" REPL.
  8. Do NOT log usage (matches new_app R4).
- **R7 — Mount** the new router in `backend/app/main.py` alongside other routers (match existing `app.include_router(...)` calls).
- **R8** — All list/read endpoints filter by `workspace_id` — no cross-workspace read ever returns a row.

### 1.3 Out of Scope
- Dry-run that writes a `was_dry_run=true` execution row — handled in STORY-018-06 via the executor.
- Authentication beyond `get_current_user_id` + owner assert.
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

### 2.2 Verification Steps (Manual)
- [ ] `curl` each endpoint with a valid session cookie; observe expected status codes.
- [ ] Confirm OpenAPI schema at `/docs` shows all 7 endpoints with correct request/response shapes.
- [ ] Confirm a 403 is returned for a logged-in non-owner (manually create two users).

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | same as STORY-018-01 | [ ] |
| **Services Running** | Backend running locally at `localhost:8000` | [ ] |
| **Migrations** | 012 (from STORY-018-01) applied | [ ] |
| **Dependencies** | `pydantic-ai[openai,anthropic,google]` already installed for build_agent (EPIC-007) | [ ] |

### 3.1 Test Implementation
- **Integration tests** in `backend/tests/test_automations_routes.py`, using FastAPI `TestClient` with a mocked Supabase (`_make_supabase_mock` pattern).
- Each Gherkin scenario → one test. L2 target: **≥ 13 tests (one per scenario)**.
- Dry-run timeout scenario uses `monkeypatch.setattr` on `pydantic_ai.Agent.run` to hang.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/automations.py` (**NEW**) |
| **Related Files** | `backend/app/main.py` (modify — add `app.include_router(...)`), `backend/app/services/automation_service.py` (from 018-01), `backend/app/api/routes/channels.py` (auth/ownership pattern), `backend/app/api/deps.py` (`get_current_user_id`), `backend/app/agents/agent.py:396` (`build_agent` — reference for how to fetch provider + key) |
| **New Files Needed** | Yes — routes file + test file |
| **ADR References** | ADR-001 (JWT auth via cookie), ADR-024 (workspace-owned channels) |
| **First-Use Pattern** | No — identical to `channels.py` |

### 3.3 Technical Logic

**Tool-free preview agent** (for dry-run endpoint) — keep it inside `automations.py` as a small helper:

```python
async def _run_preview_prompt(workspace_id: str, prompt: str, *, supabase) -> AutomationTestRunResponse:
    # 1. Fetch workspace config
    row = supabase.table("teemo_workspaces").select("ai_provider, ai_model, encrypted_api_key").eq("id", workspace_id).maybe_single().execute()
    if not row.data or not row.data.get("encrypted_api_key"):
        return AutomationTestRunResponse(success=False, error="no_key_configured", output=None, tokens_used=None, execution_time_ms=None)
    provider = row.data["ai_provider"]
    model_id = row.data["ai_model"]
    api_key = decrypt(row.data["encrypted_api_key"])
    # 2. Build minimal tool-free agent
    from pydantic_ai import Agent  # lazy import
    model_str = f"{provider}:{model_id}"
    preview = Agent(model=model_str, system_prompt="You are a preview agent. Respond to the user's prompt as you would in a scheduled run, without calling any tools.")
    # 3. Run with timeout
    import asyncio, time
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(preview.run(prompt, model_settings={"api_key": api_key}), timeout=30.0)
    except asyncio.TimeoutError:
        return AutomationTestRunResponse(success=False, error="timeout after 30s", output=None, tokens_used=None, execution_time_ms=int((time.monotonic()-t0)*1000))
    except Exception as e:  # noqa: BLE001
        return AutomationTestRunResponse(success=False, error=str(e), output=None, tokens_used=None, execution_time_ms=int((time.monotonic()-t0)*1000))
    dt = int((time.monotonic()-t0)*1000)
    return AutomationTestRunResponse(success=True, output=str(result.output), error=None, tokens_used=getattr(result, "usage_tokens", None), execution_time_ms=dt)
```

*(If the pydantic-ai API has moved since EPIC-007 — mirror what `build_agent` does for model construction and API-key injection. Do not reinvent; copy.)*

**Router skeleton**:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.api.deps import get_current_user_id
from app.core.db import get_supabase
from app.services import automation_service

router = APIRouter(prefix="/api/workspaces/{workspace_id}/automations", tags=["automations"])

def _owner(workspace_id: str, user_id: str, supabase):
    # copy / import _assert_workspace_owner from channels.py
    ...
```

**Error translation**:
```python
try:
    row = automation_service.create_automation(workspace_id, user_id, payload, supabase=supabase)
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))
```

For duplicate-name check: catch the unique-violation from supabase-py. Either inspect `e.code == "23505"` or do a `get_by_name` pre-check (pre-check is simpler and race-rare here).

### 3.4 API Contract

| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/workspaces/{id}/automations` | POST | cookie JWT + owner | `AutomationCreate` | `AutomationResponse` (201) |
| `/api/workspaces/{id}/automations` | GET | cookie JWT + owner | — | `list[AutomationResponse]` |
| `/api/workspaces/{id}/automations/{aid}` | GET | cookie JWT + owner | — | `AutomationResponse` \| 404 |
| `/api/workspaces/{id}/automations/{aid}` | PATCH | cookie JWT + owner | `AutomationUpdate` | `AutomationResponse` |
| `/api/workspaces/{id}/automations/{aid}` | DELETE | cookie JWT + owner | — | 204 |
| `/api/workspaces/{id}/automations/{aid}/history` | GET | cookie JWT + owner | — | `list[AutomationExecutionResponse]` |
| `/api/workspaces/{id}/automations/test-run` | POST | cookie JWT + owner | `AutomationTestRunRequest` | `AutomationTestRunResponse` (200 even on error) |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (logic lives in `automation_service`; this layer is thin) | — |
| Component tests | 0 — N/A | — |
| E2E / acceptance tests | 13 | One per Gherkin scenario in §2.1 |
| Integration tests | 7 | One per endpoint, covering at least happy path + one error |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced. Every Gherkin scenario in §2.1 has a failing test before implementation.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted (module-level imports for monkeypatching, `credentials` cookie forwarding, PostgREST filter rule).
- [ ] No ADR violations. Owner assertion on every endpoint.
- [ ] OpenAPI docs at `/docs` show all 7 endpoints with full schemas.
- [ ] Router mounted in `main.py`; no import cycles.
- [ ] Framework Integrity: no `.claude/agents/` / `.vbounce/` changes.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
