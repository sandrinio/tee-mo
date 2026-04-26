---
bug_id: "BUG-002"
parent_ref: "EPIC-005"
status: "Shipped"
severity: "P1-High"
reporter: "@sandrinio"
approved: true
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-sprint-13-candidate"
updated_at_version: "cleargate-sprint-13-candidate"
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

# BUG-002: Team members can't access workspaces they created under a shared Slack team

## 1. The Anomaly (Expected vs. Actual)

**Expected Behavior:** A user who registers, completes Slack OAuth for a team that was previously installed by another user, and lands on that team's workspace page should see their own workspaces (or an empty list) and be able to create new ones. The "multi-user team membership" design from S-09 explicitly supports multiple users coexisting under one Slack-team install, each with their own workspaces.

**Actual Behavior:** The team page renders the team ID, but `GET /api/slack-teams/{team_id}/workspaces` returns **HTTP 403** with `{"detail": "You do not have access to this Slack team."}`. The toast *"You do not have access to this Slack team."* appears in the corner; the main panel shows *"Failed to load workspaces. Please try again."* Users cannot proceed — they can only open the "+ New Workspace" modal but the create endpoint has the same guard and would also return 403 on submit.

## 2. Reproduction Protocol

**Prereq:** A Slack team `T0AS4M2U93L` is already installed by user A (owner). User B has not yet registered.

1. As user B, register at `/register` with a new email (e.g. `newuser@example.com`). Receive JWT.
2. Log in as user B. Go through Slack OAuth for team `T0AS4M2U93L` (dashboard "Install Slack" button).
3. OAuth callback at `GET /api/slack/oauth/callback` runs:
   - `existing.data` at `backend/app/api/routes/slack_oauth.py:185-191` returns user A's row.
   - `is_new_team = False`, `is_owner = False`.
   - The `if is_owner:` branch at `slack_oauth.py:199` is **skipped** (no team upsert).
   - `teemo_slack_team_members` receives an upsert with `role="member"` at `slack_oauth.py:214-220`.
   - Redirect to `/app?slack_install=ok`.
4. `GET /api/slack/teams` at `slack_oauth.py:226` joins `teemo_slack_team_members` → team appears in user B's team list ✓
5. User B clicks the team card → frontend navigates to `/app/teams/T0AS4M2U93L`.
6. Frontend fires `GET /api/slack-teams/T0AS4M2U93L/workspaces`.
7. `workspaces.py:144` calls `assert_team_owner(team_id, user_id)`:
   ```python
   sb.table("teemo_slack_teams")
       .select("slack_team_id")
       .eq("slack_team_id", team_id)
       .eq("owner_user_id", user_id)   # ← only checks owner, not membership
       .limit(1)
   ```
8. No row matches (user B is a member, not owner) → 403 raised at `workspaces.py:75-79`.

## 3. Evidence & Context

**Failing assertion source:** `backend/app/api/routes/workspaces.py:51-79`

```python
async def assert_team_owner(team_id: str, user_id: str) -> None:
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_slack_teams")
        .select("slack_team_id")
        .eq("slack_team_id", team_id)
        .eq("owner_user_id", user_id)
        .limit(1)
        )
    )
    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this Slack team.",
        )
```

**The query that already filters by creator** (the reason the assertion is over-restrictive) — `workspaces.py:146-153`:

```python
await execute_async(sb.table("teemo_workspaces")
    .select("*")
    .eq("slack_team_id", team_id)
    .eq("user_id", user_id)     # ← already scoped to the authenticated user's workspaces
    .order("created_at", desc=False)
)
```

**Correct pattern used elsewhere** — `slack_oauth.py:239-244` (list_slack_teams):

```python
memberships = (
    await execute_async(sb.table("teemo_slack_team_members")
    .select("slack_team_id, role")
    .eq("user_id", user_id)
    )
)
```

**Same bug in a second place:** `backend/app/api/routes/channels.py:114-...` defines `_assert_slack_team_owner` with the same owner-only check, and `channels.py:446` invokes it from `GET /api/slack/teams/{team_id}/channels`. Members would be blocked from the channel picker too.

**Historical origin:** The S-09 "multi-user team membership" bonus feature added `teemo_slack_team_members` and updated `list_slack_teams` to join it, but the team-scoped workspace + channel endpoints were not migrated off the single-owner ADR-024 model.

## 4. Execution Sandbox (Suspected Blast Radius)

**Investigate / Modify:**
- `backend/app/api/routes/workspaces.py` — `assert_team_owner`, 2 call sites (`list_workspaces`, `create_workspace`)
- `backend/app/api/routes/channels.py` — `_assert_slack_team_owner`, 1 call site (`list_slack_channels`)

**Explicitly out of scope (do NOT touch):**
- `_assert_workspace_owner` helpers in `keys.py`, `drive_oauth.py`, `automations.py`, `channels.py`, `knowledge.py`. Those are scoped to an individual workspace row (whose `user_id` column is the canonical creator) — owner semantics are correct there.
- `slack_oauth.py` OAuth callback write logic. The membership row is already written correctly.
- Frontend. Once the 403 stops firing, the existing frontend flow works as-is.

## 5. Verification Protocol (The Failing Test)

**Failing test to add** (before the fix): `backend/tests/test_workspaces_team_member_access.py`

```python
# Given a Slack team owned by user A with one of user A's workspaces
# And user B registered and joined the team as a "member" via OAuth callback
# When user B calls GET /api/slack-teams/{team_id}/workspaces
# Then the response is 200 OK with an empty list (not 403)
#
# And when user B calls POST /api/slack-teams/{team_id}/workspaces {"name": "B-ws"}
# Then the response is 201 Created
#
# And when user A calls GET /api/slack-teams/{team_id}/workspaces
# Then the response still shows only user A's workspaces (not user B's)
```

**Regression suite:**
- All existing `test_workspaces*.py` tests must still pass (owner-as-member cases still covered — owners have a `teemo_slack_team_members` row with `role="owner"`).
- `test_slack_oauth_callback.py` — no behavioral change expected; still writes owner + member rows.

**Command:** `cd backend && .venv/bin/python -m pytest tests/test_workspaces_team_member_access.py tests/test_workspaces*.py -v`

## 6. Fix Plan (Implementation Guide)

### 6.1 Rename + rewrite the assertion helper

Replace `assert_team_owner` in `workspaces.py` with `assert_team_member`:

```python
async def assert_team_member(team_id: str, user_id: str) -> None:
    """Verify that the authenticated user is a member of the given Slack team.

    Queries teemo_slack_team_members for any role (owner OR member) matching
    (slack_team_id, user_id). Raises HTTP 403 if no match.

    Per the multi-user design from S-09, any member of a team can manage
    their own workspaces inside it — workspace isolation is enforced at
    the row level by teemo_workspaces.user_id.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_slack_team_members")
        .select("slack_team_id")
        .eq("slack_team_id", team_id)
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this Slack team.",
        )
```

Update both call sites in `workspaces.py` (`list_workspaces`, `create_workspace`) to call `assert_team_member`.

### 6.2 Same fix in channels.py

Rename `_assert_slack_team_owner` → `_assert_slack_team_member` and change the query from `.eq("owner_user_id", user_id)` on `teemo_slack_teams` to `.eq("user_id", user_id)` on `teemo_slack_team_members`. Update the one call site in `list_slack_channels`.

### 6.3 Docstring cleanup

Routes that used `assert_team_owner` have docstrings that say *"Authenticated user does not own this Slack team"* — reword to *"Authenticated user is not a member of this Slack team"*.

### 6.4 Error detail text

Consider updating the HTTP 403 detail from *"You do not have access to this Slack team"* (still accurate for non-members) — no change needed, this is already generic.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)

**Current Status: 🟢 Low Ambiguity**

Requirements to pass to Green (Ready for Fix):
- [x] Reproduction steps are 100% deterministic (backed by code line references).
- [x] Actual vs. Expected behavior is explicitly defined, traced to exact assertion sites.
- [x] Root cause identified — S-09 multi-user migration missed two auth helpers.
- [x] Fix plan enumerates all touch points (2 files, 3 call sites, 1 new test file).
- [x] Verification test specified in Gherkin-equivalent form.
- [ ] `approved: true` set by human to authorize push.
