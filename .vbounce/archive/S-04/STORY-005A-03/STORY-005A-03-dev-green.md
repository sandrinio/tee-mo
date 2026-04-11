---
task_id: "STORY-005A-03-dev-green"
story_id: "STORY-005A-03"
phase: "green"
agent: "developer"
worktree: ".worktrees/STORY-005A-03/"
sprint: "S-04"
---

# Developer Task — STORY-005A-03 Green Phase

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-03/`

A sibling worktree `.worktrees/STORY-005A-02/` is running in parallel — do NOT touch it.

## Phase
**GREEN PHASE — Implement code to make the 6 Red Phase tests pass.** DO NOT modify the test file.

## Red Phase Summary
Tests at `backend/tests/test_slack_install.py` (6 tests). Collection error:
```
ImportError: cannot import name 'create_slack_state_token' from 'app.core.security'
```
Once `create_slack_state_token`, `verify_slack_state_token`, `SlackInstallState`, and the `/api/slack/install` route exist, the tests will run and must pass.

Red Phase report: `.vbounce/reports/STORY-005A-03-dev-red.md`.

## Spec Correction — JWT Secret Field Name
The story spec §3.3 example code uses `settings.jwt_secret` and `settings.jwt_algorithm`. **Neither exists on `Settings`.** The real field is `settings.supabase_jwt_secret` (it's the same JWT_SECRET used by auth cookies — ADR-001 dictates reusing this for all JWT signing in the app).

**Use `settings.supabase_jwt_secret` for both sign and verify.** Use `algorithms=["HS256"]` for verification (HS256 is the existing auth algorithm — check `backend/app/core/security.py` to confirm it matches `create_access_token`'s algorithm). Use the `audience="slack-install"` claim to namespace state tokens from access tokens (so a stolen auth cookie can't be replayed as a state token and vice versa).

## Mandatory Reading
1. `FLASHCARDS.md` — **especially BUG-20260411** PyJWT module-local `_JWT` instance flashcard. Your new helpers MUST use the existing `_JWT` instance from `security.py`. Do NOT `import jwt` at module level and use the global.
2. `.vbounce/sprint-context-S-04.md`
3. `product_plans/sprints/sprint-04/STORY-005A-03-install-url-builder.md` — full spec
4. `backend/tests/test_slack_install.py` — READ ONLY
5. `backend/app/core/security.py` — study the existing `_JWT = jwt.PyJWT()` pattern + `create_access_token`. You will add `create_slack_state_token` + `verify_slack_state_token` next to them.
6. `backend/app/api/deps.py` — `get_current_user_id` dep
7. `backend/app/api/routes/auth.py` — router registration pattern in `main.py`
8. `backend/app/main.py` — where to register the new `slack_oauth_router`

## Files to Create / Modify

### 1. MODIFY `backend/app/core/security.py` — add state token helpers

```python
# ... existing imports + _JWT + create_access_token + decode_access_token ...

def create_slack_state_token(user_id: str, *, now: int | None = None) -> str:
    """Create a short-lived (5 min) signed JWT for the Slack OAuth install flow state param.

    Audience is "slack-install" so this token cannot be confused with an access token.
    Algorithm is HS256 (matches access tokens). Reuses SUPABASE_JWT_SECRET via settings.
    """
    iat = now if now is not None else int(time.time())
    payload = {
        "user_id": user_id,
        "iat": iat,
        "exp": iat + 300,
        "aud": "slack-install",
    }
    return _JWT.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def verify_slack_state_token(token: str) -> "SlackInstallState":
    """Verify and decode a Slack install state token.

    Raises jwt.ExpiredSignatureError if expired, jwt.InvalidAudienceError if aud mismatch,
    jwt.InvalidSignatureError / jwt.DecodeError on tamper.
    """
    from app.models.slack import SlackInstallState  # late import to avoid circular
    payload = _JWT.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="slack-install",
    )
    return SlackInstallState(user_id=payload["user_id"], exp=payload["exp"])
```

**Do NOT** create a new JWT instance. Use the existing module-local `_JWT`. If `security.py` does not already `import time`, add it.

### 2. CREATE `backend/app/models/slack.py` — Pydantic models

```python
"""Pydantic models for Slack OAuth install flow."""
from pydantic import BaseModel


class SlackInstallState(BaseModel):
    """State parameter payload for the Slack OAuth authorize redirect.

    Signed as a JWT with audience=slack-install and 5-minute expiry.
    STORY-005A-04 will add the TeamResponse model here too.
    """
    user_id: str
    exp: int
```

### 3. CREATE `backend/app/api/routes/slack_oauth.py` — Install route

```python
"""Slack OAuth install flow routes.

STORY-005A-03 adds GET /install.
STORY-005A-04 will add GET /oauth/callback.
STORY-005A-05 will add GET /teams.
"""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_id
from app.core.config import get_settings
from app.core.security import create_slack_state_token

router = APIRouter(prefix="/api/slack", tags=["slack"])

# ADR-021 + ADR-025: exact 7-scope tuple
SLACK_SCOPES = (
    "app_mentions:read,channels:history,channels:read,"
    "chat:write,groups:history,groups:read,im:history"
)


@router.get("/install")
async def slack_install(user_id: str = Depends(get_current_user_id)) -> RedirectResponse:
    """Redirect the authenticated user to Slack's OAuth consent screen."""
    s = get_settings()
    state = create_slack_state_token(user_id)
    qs = urlencode({
        "client_id": s.slack_client_id,
        "scope": SLACK_SCOPES,
        "redirect_uri": s.slack_redirect_url,
        "state": state,
    })
    return RedirectResponse(
        f"https://slack.com/oauth/v2/authorize?{qs}", status_code=307
    )
```

**Prefix note:** The existing `slack_events` router uses `prefix="/api/slack"`. FastAPI allows two routers to share a prefix. If there's a collision/error on app startup, fall back to splitting the prefix (e.g. `slack_oauth_router` uses `prefix="/api/slack"` but defines route as `/install` → full path `/api/slack/install`, same as spec). Verify the existing `slack_events.py` prefix first and match the idiom.

### 4. MODIFY `backend/app/main.py` — register the router

Find where `slack_events_router` is registered and add the new router next to it:
```python
from app.api.routes.slack_oauth import router as slack_oauth_router
# ...
app.include_router(slack_oauth_router)
```

### 5. Do NOT modify
- `backend/app/core/config.py` (005A-01 already added Slack fields)
- `backend/app/core/slack.py` (005A-01 + 005A-02)
- `backend/app/api/routes/slack_events.py` (005A-02)
- Any frontend file
- Existing tests other than `test_slack_install.py`

## Test Runner
Worktrees have no `.venv` — use the main repo's:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-03/backend
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_install.py -v 2>&1 | tail -40
```
Then full suite:
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest -v 2>&1 | tail -50
```

## Success Criteria
- `tests/test_slack_install.py` — **6 passed**
- Full backend suite — no regressions
- Manual sanity check: the `Location` header from a `TestClient` hit on `/api/slack/install` starts with `https://slack.com/oauth/v2/authorize?` and the query string contains all 7 scopes.

## Report
`.vbounce/reports/STORY-005A-03-dev-green.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-03"
agent: "developer"
phase: "green"
status: "implementation-complete"
files_modified:
  - { path: "backend/app/core/security.py", change: "add create_slack_state_token + verify_slack_state_token using _JWT module-local instance + supabase_jwt_secret + aud=slack-install" }
  - { path: "backend/app/models/slack.py", change: "NEW — SlackInstallState Pydantic model" }
  - { path: "backend/app/api/routes/slack_oauth.py", change: "NEW — GET /api/slack/install with 7-scope redirect" }
  - { path: "backend/app/main.py", change: "register slack_oauth_router" }
test_result: "6 passed (new), N passed (full suite)"
correction_tax_pct: <>
flashcards_flagged: []
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```

## Critical Rules
- **No test modifications.** Only the Team Lead may touch test files between phases.
- **Use the existing `_JWT = jwt.PyJWT()` instance** from `security.py`. Do NOT import `jwt` at module top and use globals — that's the BUG-20260411 footgun.
- **Use `settings.supabase_jwt_secret`** (NOT `settings.jwt_secret` — doesn't exist).
- **Include `audience="slack-install"`** in both encode and decode to namespace state tokens from access tokens.
- **307 (not 302)** for the redirect — preserves GET method.
- **Never log the state token** — it's a signed user_id, treat as a secret.
- **No gold-plating** — no callback, no teams endpoint, no DB writes. Install redirect only.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 3,360 | 1,351 | 4,711 |
