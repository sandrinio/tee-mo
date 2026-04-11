---
task_id: "STORY-005A-04-dev-green"
story_id: "STORY-005A-04"
phase: "green"
agent: "developer"
worktree: ".worktrees/STORY-005A-04/"
sprint: "S-04"
execution_mode: "Full Bounce"
---

# Developer Task — STORY-005A-04 Green Phase (OAuth Callback — L3 Full Bounce)

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-04/`

## Phase
**GREEN PHASE — Implement production code to make all 10 Red Phase tests pass.** DO NOT modify `backend/tests/test_slack_oauth_callback.py`.

## Red Phase Summary
10 tests written. Current failure mode: all 10 ERROR at fixture `patch_httpx` setup with:
```
AttributeError: module 'app.api.routes.slack_oauth' has no attribute 'httpx'
```
The test fixture does `monkeypatch.setattr(slack_oauth_module.httpx, "AsyncClient", FakeAsyncClient)`. Your production code MUST `import httpx` at module level (not inside the handler) for this to work.

Red Phase report: `.vbounce/reports/STORY-005A-04-dev-red.md`. The Developer also flagged two Green Phase requirements explicitly:
1. `import httpx` at module level in `slack_oauth.py`
2. Add `get_current_user_id_optional` to `deps.py`

## Mandatory Reading
1. `FLASHCARDS.md` — Supabase factory pattern + BUG-20260411 PyJWT.
2. `.vbounce/sprint-context-S-04.md`
3. `product_plans/sprints/sprint-04/STORY-005A-04-oauth-callback-upsert.md` — full spec, especially §3.3 pseudocode and §1.2 Req 1–11
4. `backend/tests/test_slack_oauth_callback.py` — READ ONLY. Understand the FakeAsyncClient pattern, the 10 scenarios, and the fixtures.
5. `backend/app/api/routes/slack_oauth.py` — current state: only `/install` route exists. You are ADDING `/oauth/callback`.
6. `backend/app/api/deps.py` — current `get_current_user_id`. You are adding an `_optional` variant.
7. `backend/app/core/encryption.py` — `encrypt` helper you'll call.
8. `backend/app/core/security.py` — `verify_slack_state_token` you'll call. Catches `jwt.ExpiredSignatureError` and `jwt.InvalidTokenError` separately.
9. `backend/app/core/db.py` — `get_supabase()` factory.
10. `database/migrations/005_teemo_slack_teams.sql` — column names for the upsert.

## Files to Modify

### 1. MODIFY `backend/app/api/deps.py` — add optional variant

Add next to the existing `get_current_user_id`:
```python
async def get_current_user_id_optional(request: Request) -> str | None:
    """Return the authenticated user_id, or None if no valid auth cookie.

    Used by routes that want to redirect to /login instead of returning 401
    on missing auth — e.g. the Slack OAuth callback, which cannot show a
    blank 401 page after the user just completed a consent flow.
    """
    try:
        return await get_current_user_id(request)
    except HTTPException:
        return None
```
Make sure `HTTPException` is imported in deps.py (it probably already is).

### 2. MODIFY `backend/app/api/routes/slack_oauth.py` — add `/oauth/callback`

At the TOP of the file (module-level imports), add:
```python
import logging
import httpx  # MUST be at module level so tests can monkeypatch httpx.AsyncClient
import jwt   # stdlib-style — use the SAME pattern as security.py if possible;
             # but since verify_slack_state_token wraps the decode, we only
             # need jwt for the exception classes (jwt.ExpiredSignatureError,
             # jwt.InvalidTokenError). Acceptable to `import jwt` at top.
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_id_optional
from app.core.db import get_supabase
from app.core.encryption import encrypt
from app.core.security import verify_slack_state_token

logger = logging.getLogger(__name__)
```

The new route body:
```python
@router.get("/oauth/callback")
async def slack_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user_id: str | None = Depends(get_current_user_id_optional),
):
    """Handle the Slack OAuth redirect after user consent.

    Verifies the signed state param, exchanges the auth code for a bot token,
    encrypts the token, upserts the teemo_slack_teams row, and redirects
    back to /app. See STORY-005A-04 spec §1.2 for the 5 redirect branches
    and the 3 hard-failure branches (400 invalid state, 403 cross-user, 409
    different owner).
    """
    # --- 1. Cancellation branch (no API calls, no DB writes) ---
    if error == "access_denied":
        return RedirectResponse("/app?slack_install=cancelled", status_code=302)

    # --- 2. Required params ---
    if not state or not code:
        raise HTTPException(status_code=400, detail="missing code or state")

    # --- 3. State verification: expired vs tampered are distinct branches ---
    try:
        state_payload = verify_slack_state_token(state)
    except jwt.ExpiredSignatureError:
        return RedirectResponse("/app?slack_install=expired", status_code=302)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="invalid state")

    # --- 4. Cross-user / session-lost checks ---
    if user_id is None:
        return RedirectResponse(
            "/login?next=/app&slack_install=session_lost", status_code=302
        )
    if user_id != state_payload.user_id:
        raise HTTPException(status_code=403, detail="state user mismatch")

    # --- 5. Exchange the auth code for a bot token ---
    s = get_settings()  # get_settings is already imported; if not, add the import
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "code": code,
                "client_id": s.slack_client_id,
                "client_secret": s.slack_client_secret,
                "redirect_uri": s.slack_redirect_url,
            },
        )
    payload = resp.json()

    if not payload.get("ok"):
        logger.warning(
            "oauth.v2.access failed: error=%s", payload.get("error", "unknown")
        )
        return RedirectResponse("/app?slack_install=error", status_code=302)

    team_id = payload.get("team", {}).get("id")
    bot_user_id = payload.get("bot_user_id")
    bot_token = payload.get("access_token")
    if not team_id or not bot_user_id or not bot_token:
        logger.warning("oauth.v2.access missing bot_user_id or team or access_token")
        return RedirectResponse("/app?slack_install=error", status_code=302)

    # --- 6. Different-owner check BEFORE upsert (409) ---
    sb = get_supabase()
    existing = (
        sb.table("teemo_slack_teams")
        .select("owner_user_id")
        .eq("slack_team_id", team_id)
        .limit(1)
        .execute()
    )
    if existing.data and existing.data[0]["owner_user_id"] != user_id:
        raise HTTPException(
            status_code=409,
            detail="This Slack team is already installed under a different account.",
        )

    # --- 7. Encrypt + upsert ---
    encrypted = encrypt(bot_token)
    sb.table("teemo_slack_teams").upsert(
        {
            "slack_team_id": team_id,
            "owner_user_id": user_id,
            "slack_bot_user_id": bot_user_id,
            "encrypted_slack_bot_token": encrypted,
        }
    ).execute()

    return RedirectResponse("/app?slack_install=ok", status_code=302)
```

**Important notes:**
- `get_settings` import — add to the top imports if not already there (from 005A-03 the file already imports `get_settings`).
- `Depends` — likely already imported in the file for the `/install` route.
- **Never log the bot token.** The `logger.warning` lines above only log Slack's error codes and structural missing-field warnings — never the body.
- **Do NOT add the `SlackTeamResponse` model** — that's STORY-005A-05's responsibility. Keep `models/slack.py` unchanged.
- **Do NOT touch `/install`** — only ADD the `/oauth/callback` route.

## Test Runner
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-04/backend
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_oauth_callback.py -v 2>&1 | tail -40
```
Target: **10 passed**.

Then full backend suite:
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest -v 2>&1 | tail -30
```
Target: **68 passed** (baseline 58 + 10 new). Flaky `test_decode_token_resists_global_options_poison` is pre-existing BUG-20260411 family — re-run the suite once if it fails.

## Success Criteria
- 10/10 target tests pass
- Full suite: 68/68 (or 67/68 with the known flaky security test that passes on re-run)
- No logs contain the plaintext token or the encrypted ciphertext (covered by test 10)
- `/api/slack/install` from 005A-03 still works (nothing should change its behavior)

## Report
`.vbounce/reports/STORY-005A-04-dev-green.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-04"
agent: "developer"
phase: "green"
status: "implementation-complete"
files_modified:
  - { path: "backend/app/api/deps.py", change: "add get_current_user_id_optional wrapper" }
  - { path: "backend/app/api/routes/slack_oauth.py", change: "add /oauth/callback route — state verify, code exchange via httpx, encrypt, upsert, 5 redirect branches + 3 hard-fail branches" }
test_result: "10 passed (new), 68 passed (full suite)"
correction_tax_pct: <>
flashcards_flagged:
  - "httpx.AsyncClient first use — monkeypatch pattern"
  - "Supabase .upsert() first use — DEFAULT NOW() survives re-upsert"
  - "<any others>"
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```

## Critical Rules
- **No test modifications.** If a test seems wrong, STOP and write a blockers report.
- **Never log the bot token** (plaintext or encrypted).
- **Different-owner check BEFORE upsert.** Do NOT upsert then rollback — 409 must be raised before any write.
- **No gold-plating.** No uninstall handler, no `app_uninstalled` event, no BYOK, no rate limiting, no audit trail.
- **Use `get_current_user_id_optional`** for this route — do NOT use the raising variant.
- **`httpx.AsyncClient` MUST be imported at module level** in `slack_oauth.py` so the test monkeypatch works.
