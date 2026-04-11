---
task_id: "STORY-005A-05-dev"
story_id: "STORY-005A-05"
phase: "red+green"
agent: "developer"
worktree: ".worktrees/STORY-005A-05/"
sprint: "S-04"
execution_mode: "Fast Track"
---

# Developer Task — STORY-005A-05 (Teams List, L1 Fast Track)

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-05/` — branch `story/STORY-005A-05`, cut from `sprint/S-04` at commit `59430a2` (after 005A-01/02/03/04 merged).

## Execution Mode: L1 Fast Track — Red + Green in one pass
This is a trivial single-route addition. The story declares "TDD Red Phase: Yes" and L1. For L1 Fast Track, the Developer writes tests first, confirms they fail, then implements, all in one session. No Team Lead gate between Red and Green — the scope is too small to need it. One Dev report at the end covering both phases.

## Story Spec
`.worktrees/STORY-005A-05/product_plans/sprints/sprint-04/STORY-005A-05-teams-list-endpoint.md`

Read §1 Spec + §2 Gherkin (5 scenarios) + §3 Implementation Guide in full. It's short.

## Mandatory Reading
1. `FLASHCARDS.md` — especially Supabase factory + no-ciphertext-in-responses conventions.
2. `.vbounce/sprint-context-S-04.md` — `.select()` MUST be explicit-column; NEVER `.select("*")` on `teemo_slack_teams` (defense in depth — ADR-010).
3. `backend/app/api/routes/slack_oauth.py` — current state: `/install` and `/oauth/callback` exist. You are ADDING `/teams` as the third route.
4. `backend/app/models/slack.py` — current state: only `SlackInstallState`. You are ADDING `SlackTeamResponse`.
5. `backend/tests/test_slack_oauth_callback.py` — reference for the `alice_user` / `bob_user` fixture pattern with real Supabase cleanup and encrypted-row seeding.

## Files to Modify

### 1. MODIFY `backend/app/models/slack.py` — add `SlackTeamResponse`
```python
from datetime import datetime

class SlackTeamResponse(BaseModel):
    """API response shape for GET /api/slack/teams.

    NEVER include encrypted_slack_bot_token in this model. Adding it would
    cause the token to leak through FastAPI's JSON serialization. ADR-010
    mandates the token is encrypted at rest AND never in API responses.
    """
    slack_team_id: str
    slack_bot_user_id: str
    installed_at: datetime
```

### 2. MODIFY `backend/app/api/routes/slack_oauth.py` — add `/teams`
Add this route alongside `/install` and `/oauth/callback`:
```python
from app.models.slack import SlackTeamResponse  # if not already imported


@router.get("/teams")
async def list_slack_teams(user_id: str = Depends(get_current_user_id)) -> dict:
    """Return the list of Slack teams owned by the authenticated user.

    The response includes slack_team_id, slack_bot_user_id, and installed_at.
    The encrypted bot token is NEVER returned — the select clause is explicit
    by column to guarantee this at the DB boundary (defense in depth per ADR-010).
    """
    sb = get_supabase()
    result = (
        sb.table("teemo_slack_teams")
        .select("slack_team_id, slack_bot_user_id, installed_at")
        .eq("owner_user_id", user_id)
        .order("installed_at", desc=True)
        .execute()
    )
    return {"teams": [SlackTeamResponse(**row).model_dump(mode="json") for row in (result.data or [])]}
```
**Critical:** `.select("slack_team_id, slack_bot_user_id, installed_at")` — explicit columns. NEVER `.select("*")`.

**Note on `get_current_user_id` import:** 005A-03 already imports it at the top of `slack_oauth.py` for the `/install` route. Do NOT re-import. Same for `get_supabase` — if not already imported at the top, add it.

### 3. CREATE `backend/tests/test_slack_teams_list.py` — 5 tests

Cover all 5 Gherkin scenarios. Use the same real-Supabase pattern as `test_slack_oauth_callback.py`:

```python
"""Integration tests for STORY-005A-05 — GET /api/slack/teams."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_supabase
from app.core.encryption import encrypt
from app.core.security import create_access_token


# --- Helpers ------------------------------------------------------------------

def _register_user(email_prefix: str = "alice") -> tuple[str, str]:
    """Register a real user, return (user_id, access_token)."""
    email = f"{email_prefix}+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    row = get_supabase().table("teemo_users").select("id").eq("email", email).single().execute()
    user_id = str(row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    return user_id, token, email


def _seed_team(user_id: str, team_id: str, bot_user_id: str, bot_token: str, installed_at=None):
    """Insert a real teemo_slack_teams row with encrypted token. Returns the ciphertext."""
    ciphertext = encrypt(bot_token)
    row = {
        "slack_team_id": team_id,
        "owner_user_id": user_id,
        "slack_bot_user_id": bot_user_id,
        "encrypted_slack_bot_token": ciphertext,
    }
    if installed_at is not None:
        row["installed_at"] = installed_at.isoformat()
    get_supabase().table("teemo_slack_teams").insert(row).execute()
    return ciphertext


@pytest.fixture
def alice():
    user_id, token, email = _register_user("alice")
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def bob():
    user_id, token, email = _register_user("bob")
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def cleanup_list_rows():
    """Remove all T_LIST_* test rows before and after the test."""
    def _clean():
        get_supabase().table("teemo_slack_teams").delete().like("slack_team_id", "T_LIST_%").execute()
    _clean()
    yield
    _clean()
```

### The 5 Tests

1. **`test_empty_list_returns_200_with_empty_teams`** — alice is registered but has no teemo_slack_teams rows. GET /api/slack/teams with alice's cookie. Assert status == 200, `response.json() == {"teams": []}`.

2. **`test_single_team`** — seed one row for alice (`T_LIST_001`, `UBOT_LIST_001`, `"xoxb-list-one"`). GET /api/slack/teams with alice's cookie. Assert:
   - status 200
   - `response.json()["teams"][0]["slack_team_id"] == "T_LIST_001"`
   - `response.json()["teams"][0]["slack_bot_user_id"] == "UBOT_LIST_001"`
   - `"installed_at" in response.json()["teams"][0]`
   - `"encrypted_slack_bot_token" not in response.json()["teams"][0]`
   - `body_text = json.dumps(response.json()); ciphertext not in body_text; "encrypted" not in body_text.lower()`

3. **`test_only_my_teams`** — alice owns `T_LIST_AA`, bob owns `T_LIST_BB`. alice GETs /api/slack/teams. Assert:
   - `len(response.json()["teams"]) == 1`
   - `response.json()["teams"][0]["slack_team_id"] == "T_LIST_AA"`
   - `"T_LIST_BB" not in json.dumps(response.json())`

4. **`test_anonymous_returns_401`** — TestClient with no auth cookie. GET /api/slack/teams. Assert `response.status_code == 401`.

5. **`test_ordering_newest_first`** — seed 3 rows for alice with explicit `installed_at` timestamps:
   - `T_LIST_OLD`  at `now - 2h`
   - `T_LIST_MID`  at `now - 1h`
   - `T_LIST_NEW`  at `now`
   alice GETs /api/slack/teams. Assert:
   - `len == 3`
   - `teams[0]["slack_team_id"] == "T_LIST_NEW"`
   - `teams[2]["slack_team_id"] == "T_LIST_OLD"`

All tests use fixtures `alice`, `bob` (for test 3), and `cleanup_list_rows` (for tests 2, 3, 5).

## Execution Steps

### Step 1: Write the test file (Red Phase)
Create `backend/tests/test_slack_teams_list.py` with the scaffold + 5 tests. Run it:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-05/backend
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_teams_list.py -v 2>&1 | tail -30
```
Expect all 5 tests to FAIL with 404 (route doesn't exist yet) or similar. Record the failure mode.

### Step 2: Implement the model + route (Green Phase)
Modify `backend/app/models/slack.py` and `backend/app/api/routes/slack_oauth.py` per §2.1 above. Re-run:
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_teams_list.py -v 2>&1 | tail -30
```
Target: **5 passed**.

Then the full backend suite:
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest 2>&1 | tail -15
```
Target: **73 passed** (68 baseline + 5 new).

Re-run once if the flaky `test_decode_token_resists_global_options_poison` or `test_state_token_tamper` fails — known BUG-20260411 family flakes.

## Success Criteria
- 5/5 target tests pass
- Full suite: 73/73 (or 72/73 with known flake, passing on re-run)
- `.select(...)` uses explicit columns, not `*`
- Token never appears in any test response
- `/install` and `/oauth/callback` routes still pass their existing tests (3+10 = 13 unchanged)

## Report
Write **one** report `.vbounce/reports/STORY-005A-05-dev-green.md` covering both phases:
```yaml
---
story_id: "STORY-005A-05"
agent: "developer"
phase: "red+green"
status: "implementation-complete"
files_modified:
  - { path: "backend/app/models/slack.py", change: "add SlackTeamResponse" }
  - { path: "backend/app/api/routes/slack_oauth.py", change: "add GET /teams route with explicit-column select" }
  - { path: "backend/tests/test_slack_teams_list.py", change: "NEW — 5 integration tests" }
test_result: "5 passed (new), 73 passed (full suite)"
correction_tax_pct: <>
flashcards_flagged: []
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```
Body: brief summary of the 3 files, any gotchas, confirmation of no-ciphertext-in-response.

## Critical Rules
- **Explicit-column `.select(...)`** — NEVER `.select("*")`. Tests must fail if this regresses.
- **No test modifications** after Green Phase is entered (you can modify tests only between Red run and Green run if you discover a structural bug in YOUR OWN test).
- **No gold-plating.** No pagination, no team-name fetch, no filtering, no caching. 5 tests, 3 files.
- **Never log** the encrypted ciphertext.
- **Do NOT touch** `/install` or `/oauth/callback`, `deps.py`, `main.py`, `security.py`, `encryption.py`, or anything outside the 3 files listed.
- **Use `/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest`**.

## Final Message Must Include
- 5-test output showing `5 passed`
- Full suite summary (73 passed)
- List of files modified/created
- Any flashcards flagged
- Self-assessed Correction Tax %
