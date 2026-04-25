---
story_id: "STORY-025-05"
parent_epic_ref: "EPIC-025"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-025-workspace-v2-redesign.md"
actor: "Workspace admin (Slack team owner) and workspace creator"
complexity_label: "L1"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-s16-kickoff"
updated_at_version: "cleargate-s16-kickoff"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-025-05: Workspace Group + Owner Gate
**Complexity:** L1 — small backend tightening + UI hide, ~1.5hr

## 1. The Spec

### 1.1 User Story
As a Slack team owner, I want admin-override authority to delete any workspace in the team while preserving the existing self-service delete for the workspace creator, so that admins can clean up after departed members without taking deletion away from owners-of-their-own-work.

### 1.2 Detailed Requirements

**Backend authorization model — Creator OR Team-Owner (resolved at SPRINT-16 kickoff, OQ-2 = C):**

- The current `DELETE /api/workspaces/{id}` handler filters by `.eq("user_id", user_id)` — only the workspace creator can delete; everyone else gets 404 (existence-leak guard per ADR-024). DELETE was never in BUG-002 scope.
- New rule: a delete succeeds when the caller is **either** (a) the workspace creator (`teemo_workspaces.user_id == caller`), **or** (b) the team owner (`teemo_slack_team_members.role == 'owner'` for the workspace's `slack_team_id`). One predicate is enough — both are not required.
- Error contract preserves the existence-leak guard:
  - **404** "Workspace not found." — when the workspace row does not exist OR the caller is not a member of the team at all.
  - **403** "Only the workspace creator or a team owner can delete this workspace." — when the workspace exists, the caller IS a team member, but is neither the creator nor a team owner. (Existence is already implied by team-membership, so 403 here does not leak new information.)
  - **204** — success.
- Implementation shape: handler fetches the workspace row first (single SELECT by `id` only) to read `user_id` and `slack_team_id`. If row missing → 404. Then check creator OR team-owner. If neither → 404 if not a member, 403 if member. New helper `is_team_owner(team_id, user_id) -> bool` queries `teemo_slack_team_members` for `role='owner'`. The existing `assert_team_member` helper is reused unchanged for the membership probe (no BUG-002 reversal).

**Workspace GET response extension (resolved at SPRINT-16 kickoff, OQ-3 = C):**

- `GET /api/workspaces/{id}` response gains TWO new fields, populated server-side only on the detail endpoint:
  - `is_owner: bool` — true when the caller has `role='owner'` in the workspace's Slack team. Frontend uses this to gate the Workspace tab + Danger zone module.
  - `slack_domain: str | null` — the workspace's Slack workspace domain (e.g. `acme.slack.com`), read from `teemo_slack_teams.domain` joined on `slack_team_id`. Null when no install row found (defensive). Frontend uses this for the SlackSection caption (consumed by STORY-025-02).
- **List endpoint `/api/teams/{id}/workspaces` does NOT include either field.** Detail-only contract. Frontend reads both exclusively from `useWorkspaceQuery`. No list-cache invalidation needed in this sprint.

**Frontend changes:**

- **DangerZoneSection** — extract from route inline `DeleteWorkspaceSection`. Single-row layout: title "Danger zone" (16px/600) + caption "Delete or transfer workspace" left, danger-variant Delete button right. Existing div-based confirmation dialog preserved verbatim.
- **Workspace tab + ModuleSection** renders only when `workspace.is_owner === true`. The registry is filtered at WorkspaceShell level. Note: this gates VISIBILITY, not authorization — a non-owner who happens to also be the creator can still delete via the API, just without a UI affordance in S-16. (Future epic may surface a "you can delete this workspace you created" affordance for creators-who-are-not-owners; out of scope here.)
- Status resolver: `neutral` always — Danger zone is action-only, never has a status.

### 1.3 Out of Scope
- Owner gating on other endpoints (Files, Channels, Persona) — broader gate is a future epic.
- Surfacing a creator-self-service delete UI for non-owner creators — future epic. Backend supports it; the S-16 UI hides Danger zone from non-owners regardless.
- Transfer-workspace flow (mentioned in caption only — no UI yet).
- Audit log gating (Audit module not in this epic).

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Workspace group + owner gate

  Scenario: Team owner can delete any workspace in the team
    Given the authenticated user has role "owner" in the Slack team
    And the workspace was created by a different team member
    When DELETE /api/workspaces/{id} is called
    Then the API responds with 204
    And the workspace row is removed (CASCADE drops children)

  Scenario: Workspace creator can delete their own workspace
    Given the authenticated user has role "member" in the Slack team
    And the workspace's user_id equals the authenticated user
    When DELETE /api/workspaces/{id} is called
    Then the API responds with 204

  Scenario: Team member who is neither creator nor owner is forbidden
    Given the authenticated user has role "member" in the Slack team
    And the workspace's user_id is a different team member
    When DELETE /api/workspaces/{id} is called
    Then the API responds with 403
    And the body equals `{"detail": "Only the workspace creator or a team owner can delete this workspace."}`

  Scenario: Non-team-member receives 404
    Given the authenticated user is not a member of the Slack team
    When DELETE /api/workspaces/{id} is called
    Then the API responds with 404
    And the body equals `{"detail": "Workspace not found."}`

  Scenario: Workspace GET surfaces is_owner and slack_domain
    Given the authenticated user has role "owner" in the Slack team
    And the team's Slack domain is "acme.slack.com"
    When GET /api/workspaces/{id} is called
    Then the response JSON contains `"is_owner": true`
    And the response JSON contains `"slack_domain": "acme.slack.com"`
    And the list endpoint /api/slack-teams/{team_id}/workspaces does NOT include either field

  Scenario: Danger zone visible to owner
    Given the authenticated user has is_owner=true on the workspace GET
    When the page renders
    Then the Workspace tab is present in the sticky tab bar
    And the Danger zone module renders with the Delete button

  Scenario: Danger zone hidden from non-owner
    Given the authenticated user has is_owner=false on the workspace GET
    When the page renders
    Then the Workspace tab is NOT present in the sticky tab bar
    And no Danger zone section is rendered
```

### 2.2 Verification Steps (Manual)
- [ ] Login as team owner → Workspace tab visible → delete a workspace created by someone else → succeeds.
- [ ] Login as regular member → Workspace tab absent.
- [ ] As regular member who created the workspace: `curl -X DELETE /api/workspaces/{id}` → 204 (creator self-service preserved).
- [ ] As regular member who did NOT create the workspace: `curl -X DELETE /api/workspaces/{id}` → 403.
- [ ] As non-member: `curl -X DELETE /api/workspaces/{id}` → 404.
- [ ] GET /api/workspaces/{id} as owner → JSON includes `is_owner: true` AND `slack_domain: "<domain>"`.
- [ ] GET /api/slack-teams/{team_id}/workspaces → list rows do NOT contain `is_owner` or `slack_domain`.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| New | `frontend/src/components/workspace/DangerZoneSection.tsx` (extracted from route) |
| Modify | `backend/app/api/routes/workspaces.py` — rewrite `delete_workspace` per §3.2 (creator OR team-owner OR semantics). Add `is_team_owner` helper. |
| Modify | `backend/app/api/routes/workspaces.py` — extend `get_workspace` to include `is_owner` + `slack_domain`. Update `_to_response` accordingly. |
| Modify | `backend/app/models/workspace.py` — add `is_owner: bool = False` and `slack_domain: str \| None = None` to `WorkspaceResponse`. One-line comment: detail-only fields, never on list endpoint. |
| Modify | `frontend/src/lib/api.ts` — add `is_owner?: boolean` and `slack_domain?: string \| null` to `Workspace` type (optional because list endpoint omits them). |
| Modify | `frontend/src/components/workspace/moduleRegistry.ts` — append `danger-zone` entry under `group: 'workspace'`. |
| Modify | `frontend/src/components/workspace/WorkspaceShell.tsx` — filter registry by `(entry) => entry.group !== 'workspace' || workspace.is_owner === true`. Suppress empty group's tab. |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — remove inline `DeleteWorkspaceSection` definition. |

### 3.2 Technical Logic

**`delete_workspace` rewrite:**

```python
async def delete_workspace(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> None:
    sb = get_supabase()
    # 1. Fetch workspace row (no user filter) to know creator + team.
    row = await execute_async(
        sb.table("teemo_workspaces")
        .select("user_id, slack_team_id")
        .eq("id", str(workspace_id))
        .limit(1)
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    workspace = row.data[0]
    is_creator = workspace["user_id"] == user_id
    is_owner = await is_team_owner(workspace["slack_team_id"], user_id)

    if not (is_creator or is_owner):
        # Distinguish team-member (403) from non-member (404, existence-leak guard).
        membership = await execute_async(
            sb.table("teemo_slack_team_members")
            .select("role")
            .eq("slack_team_id", workspace["slack_team_id"])
            .eq("user_id", user_id)
            .limit(1)
        )
        if not membership.data:
            raise HTTPException(status_code=404, detail="Workspace not found.")
        raise HTTPException(
            status_code=403,
            detail="Only the workspace creator or a team owner can delete this workspace.",
        )

    # CASCADE removes children (skills, knowledge_index, channels).
    result = await execute_async(
        sb.table("teemo_workspaces").delete().eq("id", str(workspace_id))
    )
    if not result.data:
        # Defensive: should not happen since we just SELECTed it.
        raise HTTPException(status_code=404, detail="Workspace not found.")
```

**`is_team_owner` helper (new, small):**

```python
async def is_team_owner(team_id: str, user_id: str) -> bool:
    sb = get_supabase()
    result = await execute_async(
        sb.table("teemo_slack_team_members")
        .select("role")
        .eq("slack_team_id", team_id)
        .eq("user_id", user_id)
        .eq("role", "owner")
        .limit(1)
    )
    return bool(result.data)
```

**`get_workspace` extension:** join `teemo_slack_team_members` for `is_owner` (caller's role), and `teemo_slack_teams` for `slack_domain`. Both stay null/false on missing rows (defensive). Inject into `_to_response`.

**`assert_team_member` helper (lines 53-85) is NOT modified.** BUG-002 list/create relaxation stays intact.

**`is_owner` + `slack_domain` cache contract.** Detail-only fields. List endpoints (`/api/teams/{id}/workspaces`) do not include them. Frontend reads both exclusively from `useWorkspaceQuery`. No list-cache invalidation needed.

**Role-change re-fetch.** Member role changes are out of scope for S-16 (no UI surface). If a role change happens out-of-band, the user must reload to see the Workspace tab appear/disappear. Acceptable for S-16; flag in REPORT.md if encountered.

**Frontend filter:** `MODULE_REGISTRY.filter((entry) => entry.group !== 'workspace' || workspace.is_owner === true)`. Tab bar receives the filtered list; if Workspace group has zero modules, the tab is suppressed.

### 3.3 API Contract

| Endpoint | Method | Auth | Change |
|---|---|---|---|
| `/api/workspaces/{id}` | DELETE | Bearer | 204 when caller is creator OR team-owner. 403 (with detail "Only the workspace creator or a team owner can delete this workspace.") when caller is a team-member but neither. 404 otherwise (preserves ADR-024 existence-leak guard). |
| `/api/workspaces/{id}` | GET | Bearer | Two new response fields: `is_owner: bool`, `slack_domain: string \| null`. |
| `/api/slack-teams/{team_id}/workspaces` | GET | Bearer | Unchanged. Does NOT include `is_owner` or `slack_domain`. |

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Pytest | 5 | (1) DELETE owner-but-not-creator → 204; (2) DELETE creator-but-not-owner → 204; (3) DELETE member-neither → 403; (4) DELETE non-member → 404; (5) GET surfaces is_owner + slack_domain when owner. |
| Vitest | 2 | Workspace tab visible when is_owner=true; absent when false. |
| BUG-002 regression | (re-run) | Member can still LIST + CREATE workspaces — existing tests must stay green without modification. |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered.
- [ ] `npm run typecheck` + `pytest backend/tests/` clean.
- [ ] BUG-002 regression check — member access to LIST + CREATE workspace endpoints still works (existing tests unmodified, still green).
- [ ] Confirm list endpoint `/api/teams/{id}/workspaces` response shape unchanged (no `is_owner` and no `slack_domain` leakage). Frontend reads both exclusively from `useWorkspaceQuery`.
- [ ] Manual verification §2.2 completed (all 7 steps).

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**

OQ-2 (DELETE owner-gate semantics) and OQ-3 (SlackSection caption data source) resolved at SPRINT-16 kickoff, 2026-04-25. See `.cleargate/sprint-runs/SPRINT-16/plans/W01.md` §7 for resolution record.
