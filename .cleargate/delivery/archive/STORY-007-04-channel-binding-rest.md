---
story_id: "STORY-007-04-channel-binding-rest"
parent_epic_ref: "EPIC-007"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
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

> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-07/STORY-007-04-channel-binding-rest.md`. Shipped in sprint S-07, carried forward during ClearGate migration 2026-04-24.

# STORY-007-04: Channel Binding REST Endpoints

**Complexity: L2** — Standard: 1 new route file + mount in main.py, follows established CRUD patterns.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Workspace Admin**, I want to bind Slack channels to my workspaces via API endpoints, so that the bot knows which workspace (knowledge silo) to use when @mentioned in a specific channel.

### 1.2 Detailed Requirements
- **R1**: `POST /api/workspaces/{workspace_id}/channels` — bind a channel to a workspace.
    - Body: `{"slack_channel_id": "C0123ABC"}`
    - Validates: workspace belongs to authenticated user (ownership check).
    - Validates: channel's team matches workspace's `slack_team_id`.
    - Returns 409 `channel_already_bound` if channel already has a binding (any workspace).
    - Returns 201 with the created binding.
- **R2**: `DELETE /api/workspaces/{workspace_id}/channels/{channel_id}` — unbind a channel.
    - Validates ownership.
    - Returns 204 on success.
    - Returns 404 if binding doesn't exist.
- **R3**: `GET /api/workspaces/{workspace_id}/channels` — list channel bindings for a workspace.
    - Returns list of `{slack_channel_id, workspace_id, slack_team_id, bound_at}`.
    - Validates ownership.
- **R4**: `GET /api/slack/teams/{team_id}/channels` — proxy to Slack `conversations.list`.
    - Validates: team belongs to authenticated user.
    - Decrypts bot token from `teemo_slack_teams`.
    - Calls `conversations.list(types="public_channel,private_channel")`.
    - Returns `[{id, name, is_private, is_member}]`.
    - This powers the dashboard channel picker (EPIC-008).
- **R5**: All endpoints require JWT authentication via `Depends(get_current_user_id)`.
- **R6**: Ownership is verified by checking `teemo_workspaces.user_id == current_user_id` (for workspace routes) or `teemo_slack_teams.owner_user_id == current_user_id` (for team routes).

### 1.3 Out of Scope
- Channel picker UI in the frontend — EPIC-008
- Channel status refresh (`is_member` check via `conversations.info`) — EPIC-008
- Validating that the channel exists in Slack before binding — V1 trusts the channel_id from the client

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: Channel Binding REST

  Scenario: Bind a channel to a workspace
    Given user U1 owns workspace W1 with slack_team_id "T001"
    When POST /api/workspaces/W1/channels with {"slack_channel_id": "C001"}
    Then 201 is returned with the binding record
    And teemo_workspace_channels has a row (C001, W1, T001)

  Scenario: Bind channel already bound
    Given channel C001 is already bound to workspace W2
    When POST /api/workspaces/W1/channels with {"slack_channel_id": "C001"}
    Then 409 is returned with detail "channel_already_bound"

  Scenario: Bind channel to workspace not owned by user
    Given user U1 does NOT own workspace W3
    When POST /api/workspaces/W3/channels with {"slack_channel_id": "C002"}
    Then 403 is returned

  Scenario: Unbind a channel
    Given channel C001 is bound to workspace W1 owned by user U1
    When DELETE /api/workspaces/W1/channels/C001
    Then 204 is returned
    And the binding row is removed

  Scenario: List bindings
    Given workspace W1 has 2 bound channels
    When GET /api/workspaces/W1/channels
    Then 200 with a list of 2 binding records

  Scenario: List Slack channels for a team
    Given user U1 owns team T001 with a valid bot token
    When GET /api/slack/teams/T001/channels
    Then 200 with a list of Slack channels [{id, name, is_private, is_member}]
```

### 2.2 Verification Steps (Manual)
- [ ] All tests pass with `pytest backend/tests/test_channel_binding.py -v`
- [ ] Full backend suite passes

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Migration** | `006_teemo_workspace_channels.sql` already applied | [ ] |
| **Dependencies** | `slack_sdk` (already installed) | [ ] |

### 3.1 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/channels.py` (new) |
| **Related Files** | `backend/app/main.py` (mount router), `backend/app/api/deps.py` (get_current_user_id), `backend/app/core/encryption.py` (decrypt bot token) |
| **New Files Needed** | Yes — `channels.py`, `tests/test_channel_binding.py` |
| **ADR References** | ADR-024 (workspace model), ADR-025 (explicit channel binding) |

### 3.2 Technical Logic

**Router structure:**
```python
router = APIRouter(tags=["channels"])

# Workspace-scoped channel binding
@router.post("/api/workspaces/{workspace_id}/channels", status_code=201)
@router.delete("/api/workspaces/{workspace_id}/channels/{channel_id}", status_code=204)
@router.get("/api/workspaces/{workspace_id}/channels")

# Team-scoped Slack channel list
@router.get("/api/slack/teams/{team_id}/channels")
```

**Ownership check helper:**
```python
def _verify_workspace_owner(supabase, workspace_id: str, user_id: str) -> dict:
    """Returns workspace row or raises 403/404."""
```

**Channel binding — insert logic:**
```python
supabase.table("teemo_workspace_channels").insert({
    "slack_channel_id": body.slack_channel_id,
    "workspace_id": workspace_id,
    "slack_team_id": workspace["slack_team_id"],
}).execute()
```
Catch unique constraint violation (23505) → return 409.

**Conversations list proxy:**
```python
from slack_sdk.web.async_client import AsyncWebClient
from app.core.encryption import decrypt

# Decrypt bot token from teemo_slack_teams
team = supabase.table("teemo_slack_teams")...
token = decrypt(team["encrypted_slack_bot_token"])
client = AsyncWebClient(token=token)
result = await client.conversations_list(types="public_channel,private_channel")
```

### 3.3 API Contract
| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/workspaces/{id}/channels` | POST | Bearer | `{"slack_channel_id": str}` | `{slack_channel_id, workspace_id, slack_team_id, bound_at}` |
| `/api/workspaces/{id}/channels/{ch_id}` | DELETE | Bearer | — | 204 No Content |
| `/api/workspaces/{id}/channels` | GET | Bearer | — | `[{slack_channel_id, workspace_id, slack_team_id, bound_at}]` |
| `/api/slack/teams/{team_id}/channels` | GET | Bearer | — | `[{id, name, is_private, is_member}]` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit/integration tests | 6 | 1 per Gherkin scenario |

### 4.2 Definition of Done (The Gate)
- [ ] 6+ tests passing.
- [ ] Router mounted in `main.py`.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
