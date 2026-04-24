---
story_id: "STORY-008-02-channel-binding-ui"
parent_epic_ref: "EPIC-008"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L3"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-09/STORY-008-02-channel-binding-ui.md`. Shipped in sprint S-09, carried forward during ClearGate migration 2026-04-24.

# STORY-008-02: Channel Binding UI + Backend is_member Enrichment

**Complexity: L3** — Cross-cutting (frontend + backend), new API client functions, new hooks, new UI component

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **workspace owner**,
I want to **bind Slack channels to my workspace and see their Active/Pending status from the dashboard**,
So that **I know which channels will route questions to this workspace's knowledge base and which still need a `/invite @tee-mo`**.

### 1.2 Detailed Requirements

**Frontend — API client (`api.ts`):**
- **R1**: Add `listSlackTeamChannels(teamId: string) -> SlackChannel[]` — calls `GET /api/slack/teams/{team_id}/channels`. Type: `SlackChannel { id: string, name: string, is_private: boolean }`.
- **R2**: Add `listChannelBindings(workspaceId: string) -> ChannelBinding[]` — calls `GET /api/workspaces/{workspace_id}/channels`. Type: `ChannelBinding { slack_channel_id: string, workspace_id: string, bound_at: string, channel_name?: string, is_member?: boolean }`.
- **R3**: Add `bindChannel(workspaceId: string, channelId: string) -> ChannelBinding` — calls `POST /api/workspaces/{workspace_id}/channels` with `{ slack_channel_id: channelId }`.
- **R4**: Add `unbindChannel(workspaceId: string, channelId: string) -> void` — calls `DELETE /api/workspaces/{workspace_id}/channels/{channel_id}`.

**Frontend — hooks (`useChannels.ts`):**
- **R5**: `useSlackChannelsQuery(teamId)` — enabled when teamId is non-empty.
- **R6**: `useChannelBindingsQuery(workspaceId)` — enabled when workspaceId is non-empty.
- **R7**: `useBindChannelMutation(workspaceId)` — invalidates `['channel-bindings', workspaceId]` on success.
- **R8**: `useUnbindChannelMutation(workspaceId)` — invalidates `['channel-bindings', workspaceId]` on success.

**Frontend — ChannelSection component:**
- **R9**: Build `frontend/src/components/workspace/ChannelSection.tsx` with:
  - "Add channel" button that opens a dropdown/picker listing available Slack channels (from `useSlackChannelsQuery`)
  - Already-bound channels filtered out of the picker
  - Bound channels rendered as chips/pills with status:
    - **Active** (green emerald badge): `is_member === true`
    - **Pending /invite** (amber badge): `is_member === false`
  - Each chip has an `x` button to unbind (with confirm)
  - "Pending /invite" chips show a copy-to-clipboard snippet: `/invite @tee-mo` in `#channel-name`
- **R10**: Handle 409 conflict when channel is already bound to another workspace — show inline error: "This channel is already bound to workspace '{name}'. Unbind it there first."
- **R11**: Empty state when no channels are bound: "No channels bound yet. Bind a channel so Tee-Mo knows which workspace to use when @mentioned."

**Backend — `is_member` enrichment:**
- **R12**: Modify `list_channel_bindings` in `backend/app/api/routes/channels.py` to enrich each binding with `channel_name` and `is_member` by calling Slack `conversations.info(channel=slack_channel_id)` for each binding. Use the team's decrypted bot token. Return enriched objects.
- **R13**: If `conversations.info` fails for a binding (e.g., channel deleted), set `is_member: false` and `channel_name: slack_channel_id` (fallback to ID).

### 1.3 Out of Scope
- Guided setup mode integration (STORY-008-01 owns the stepper; this story delivers the standalone component)
- Workspace card channel chips (STORY-008-03)
- Auto-join channels (ADR-025: explicit `/invite` only)
- `member_joined_channel` event listener (ADR-025: no proactive messages)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Channel Binding UI

  Scenario: List available channels
    Given a workspace under a Slack team with channels #general, #engineering, #marketing
    And #general is already bound to this workspace
    When the user clicks "Add channel"
    Then the picker shows #engineering and #marketing (not #general)

  Scenario: Bind a channel
    Given the channel picker is open showing #engineering
    When the user selects #engineering
    Then a POST to /api/workspaces/{id}/channels is made with slack_channel_id
    And #engineering appears as a chip with "Pending /invite" status (amber)
    And a copy snippet shows: /invite @tee-mo in #engineering

  Scenario: Channel shows Active status
    Given #general is bound and the bot is a member (is_member=true)
    When the channel bindings load
    Then #general shows "Active" status (green badge)

  Scenario: Unbind a channel
    Given #general is bound to this workspace
    When the user clicks the x on the #general chip
    Then a confirmation appears
    And on confirm, DELETE /api/workspaces/{id}/channels/{channel_id} is called
    And #general disappears from the bound list

  Scenario: Channel already bound to another workspace (409)
    Given #sales is bound to workspace "Marketing Brain"
    When the user tries to bind #sales to workspace "Engineering Brain"
    Then the API returns 409
    And the UI shows "This channel is already bound to another workspace. Unbind it there first."

  Scenario: Backend enriches bindings with is_member
    Given workspace has 2 bindings: #general (bot is member) and #private (bot not member)
    When GET /api/workspaces/{id}/channels is called
    Then the response includes is_member=true for #general and is_member=false for #private
    And channel_name is populated for both

  Scenario: Empty state
    Given a workspace with no channel bindings
    When the channel section renders
    Then an empty state message is shown with guidance text
```

### 2.2 Verification Steps (Manual)
- [ ] `npm run build` succeeds
- [ ] `npx vitest run` — new ChannelSection component tests pass
- [ ] `pytest backend/tests/test_channel_binding.py` — existing + new tests pass
- [ ] Channel picker shows real Slack channels (dev environment)
- [ ] Binding a channel shows "Pending /invite" chip
- [ ] After `/invite @tee-mo` in Slack, refreshing page shows "Active" status
- [ ] Unbinding removes the chip
- [ ] Binding a channel already bound elsewhere shows 409 error

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Backend** | Slack bot installed (teemo_slack_teams row exists with valid encrypted token) | [ ] |
| **Dependencies** | No new dependencies (Slack SDK already installed) | [ ] |

### 3.1 Test Implementation
- Create `frontend/src/components/workspace/__tests__/ChannelSection.test.tsx` — render empty state, render bound channels with status, bind flow, unbind confirm, 409 error display
- Create `frontend/src/hooks/__tests__/useChannels.test.ts` — hook behavior with mocked API
- Add test in `backend/tests/test_channel_binding.py` for `is_member` enrichment (mock `conversations.info`)

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/components/workspace/ChannelSection.tsx` (new) |
| **Related Files** | `frontend/src/lib/api.ts` (modify — add 4 functions), `frontend/src/hooks/useChannels.ts` (new), `backend/app/api/routes/channels.py` (modify — enrich with is_member) |
| **New Files Needed** | Yes — `ChannelSection.tsx`, `useChannels.ts` |
| **ADR References** | ADR-024 (workspace model), ADR-025 (explicit channel binding) |
| **First-Use Pattern** | No — follows existing TanStack Query hook patterns |

### 3.3 Technical Logic

**API client additions (`api.ts`):**
```typescript
export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
}

export interface ChannelBinding {
  slack_channel_id: string;
  workspace_id: string;
  bound_at: string;
  channel_name?: string;
  is_member?: boolean;
}

export async function listSlackTeamChannels(teamId: string): Promise<SlackChannel[]> {
  return apiGet<SlackChannel[]>(`/api/slack/teams/${teamId}/channels`);
}

export async function listChannelBindings(workspaceId: string): Promise<ChannelBinding[]> {
  return apiGet<ChannelBinding[]>(`/api/workspaces/${workspaceId}/channels`);
}

export async function bindChannel(workspaceId: string, channelId: string): Promise<ChannelBinding> {
  return apiPost<{ slack_channel_id: string }, ChannelBinding>(
    `/api/workspaces/${workspaceId}/channels`,
    { slack_channel_id: channelId }
  );
}

export async function unbindChannel(workspaceId: string, channelId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/workspaces/${workspaceId}/channels/${channelId}`, {
    method: 'DELETE', credentials: 'include',
  });
  if (!res.ok) throw new Error(await res.text());
}
```

**Backend `is_member` enrichment (`channels.py`):**
```python
# In list_channel_bindings endpoint, after fetching bindings:
bot_token = decrypt(team_row["encrypted_slack_bot_token"])
client = AsyncWebClient(token=bot_token)
enriched = []
for binding in bindings:
    try:
        info = await client.conversations_info(channel=binding["slack_channel_id"])
        channel_data = info.get("channel", {})
        binding["channel_name"] = channel_data.get("name", binding["slack_channel_id"])
        binding["is_member"] = channel_data.get("is_member", False)
    except Exception:
        binding["channel_name"] = binding["slack_channel_id"]
        binding["is_member"] = False
    enriched.append(binding)
return enriched
```

**ChannelSection component pattern:**
- Channel picker: simple `<select>` or custom dropdown listing `useSlackChannelsQuery` results filtered by already-bound IDs
- Chips: `inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium` (per design guide §6.6)
- Active: `bg-emerald-50 text-emerald-700` with green dot
- Pending: `bg-amber-50 text-amber-700` with amber dot + copy button
- Unbind `x`: `ml-1 h-3.5 w-3.5 text-current opacity-60 hover:opacity-100 cursor-pointer`

### 3.4 API Contract

**Existing endpoints (no change to signature):**

| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/slack/teams/{team_id}/channels` | GET | Cookie JWT | — | `SlackChannel[]` |
| `/api/workspaces/{workspace_id}/channels` | GET | Cookie JWT | — | `ChannelBinding[]` (enriched with `channel_name`, `is_member`) |
| `/api/workspaces/{workspace_id}/channels` | POST | Cookie JWT | `{ slack_channel_id: string }` | `ChannelBinding` (201) or `{ detail: "channel_already_bound" }` (409) |
| `/api/workspaces/{workspace_id}/channels/{channel_id}` | DELETE | Cookie JWT | — | 204 No Content |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 5 | Empty state, bound channels render, bind flow, unbind confirm, 409 error |
| Unit tests | 2 | Hook behavior, API function calls |
| Integration tests | 2 | Backend `is_member` enrichment (mock conversations.info), fallback on error |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted (module-level imports for mocking, jsdom limitation, vitest globals).
- [ ] No ADR violations (ADR-025: explicit binding, no auto-join, no fallback).
- [ ] `npm run build` passes.
- [ ] `pytest` passes with new backend tests.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 4 | 221 | 225 |
| QA | 16 | 860 | 876 |
