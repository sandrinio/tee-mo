---
task_id: "STORY-005A-03-dev-red"
story_id: "STORY-005A-03"
phase: "red"
agent: "developer"
worktree: ".worktrees/STORY-005A-03/"
sprint: "S-04"
---

# Developer Task — STORY-005A-03 Red Phase

## Working Directory
**You MUST operate inside** `/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-03/`

Do NOT touch `/Users/ssuladze/Documents/Dev/SlaXadeL/` (the main checkout).

**Parallel sibling:** STORY-005A-02 is running concurrently at `.worktrees/STORY-005A-02/`. You will NOT see its changes. Your only dependency is STORY-005A-01 (already merged — encryption.py, slack.py, config.py with 5 Slack fields, `get_settings()`).

## Phase
**RED PHASE — Tests ONLY.** Do NOT create `backend/app/api/routes/slack_oauth.py`. Do NOT create `backend/app/models/slack.py`. Do NOT modify `backend/app/core/security.py`. Do NOT register the router in `main.py`. Exit the moment the test file exists and fails at import for the expected reason.

## Story Spec
Read: `.worktrees/STORY-005A-03/product_plans/sprints/sprint-04/STORY-005A-03-install-url-builder.md`

§1 Spec, §2.1 Gherkin (6 scenarios), §3 Implementation Guide are ground truth.

## Mandatory Reading (before writing any test)
1. `.worktrees/STORY-005A-03/FLASHCARDS.md` — full file. **Especially the PyJWT module-local `_JWT` instance flashcard** (BUG-20260411) — `security.py` uses a per-module `jwt.PyJWT()` instance to avoid collision with `slack_sdk`'s monkey-patch of the global jwt module. Your tests must not mess with that.
2. `.worktrees/STORY-005A-03/.vbounce/sprint-context-S-04.md` — sprint-wide rules.
3. `.worktrees/STORY-005A-03/backend/app/core/security.py` — read to understand the existing `_JWT = jwt.PyJWT()` pattern. You'll write tests that import `create_slack_state_token` / `verify_slack_state_token` from this module (Green phase adds them).
4. `.worktrees/STORY-005A-03/backend/app/api/deps.py` — read to understand `get_current_user_id`. Your tests will need to mock/override this for the authenticated path, or use a real cookie.
5. `.worktrees/STORY-005A-03/backend/app/api/routes/auth.py` — find the `/me` route; it uses the same auth dependency you need to satisfy in tests.
6. `.worktrees/STORY-005A-03/backend/tests/test_auth_routes.py` — reference for authenticated fixture + `TestClient` cookie pattern.

## Test File to Create

**`backend/tests/test_slack_install.py`**

Cover all 6 Gherkin scenarios from §2.1:

**Unit tests (direct helper calls — no HTTP):**
1. **State token round-trip** — `create_slack_state_token("alice-uuid")` then `verify_slack_state_token(token)` returns `SlackInstallState(user_id="alice-uuid", exp=<future int>)`.
2. **State token expiry** — create with `now=<real_now - 301>` (helper must accept a `now=` kwarg per spec §3.3). Verify raises `jwt.ExpiredSignatureError`.
3. **State token tamper** — create valid token, mutate one char of the signature portion (split on `.`, flip the last char of the third segment), verify raises `jwt.InvalidSignatureError` (or `jwt.DecodeError` / `jwt.InvalidTokenError` — accept any of PyJWT's tamper subclasses).

**Integration tests (`TestClient` → `/api/slack/install`):**
4. **Authenticated 307** — logged-in user hits `/api/slack/install`. Response status == 307. `Location` header starts with `https://slack.com/oauth/v2/authorize?`. Parse the query string; assert:
   - `client_id` equals `settings.slack_client_id`
   - `redirect_uri` equals `settings.slack_redirect_url`
   - `scope` contains all 7 scope strings: `app_mentions:read`, `channels:history`, `channels:read`, `chat:write`, `groups:history`, `groups:read`, `im:history`
   - `state` is non-empty
5. **Anonymous → 401** — no auth cookie, hit `/api/slack/install`, assert status == 401.
6. **No plaintext user_id in Location header** — given a logged-in user with id `"alice-uuid-fixture"`, hit the endpoint, assert `"alice-uuid-fixture" not in response.headers["location"]`. (The state should be JWT-encoded, not a raw user_id.)

## Critical Rules
- **DO NOT create or modify** any production file. Tests only. If your imports fail on day 1, that is the CORRECT behavior:
  - `from app.core.security import create_slack_state_token, verify_slack_state_token` → ImportError
  - `from app.models.slack import SlackInstallState` → ModuleNotFoundError
  - `TestClient` hitting `/api/slack/install` → 404 (route not registered)
- Use the existing authenticated fixture pattern from `backend/tests/test_auth_routes.py`. Find the fixture name via grep:
  ```bash
  grep -nE "def (authenticated|auth_client|logged_in)" backend/tests/test_auth_routes.py
  ```
  Reuse it if appropriate; otherwise craft an equivalent fixture that sets the `access_token` cookie.
- When crafting the JWT for the authenticated fixture, use `create_access_token` from `app.core.security` (the existing helper). Do NOT roll your own JWT encoding in the test.
- For the "no plaintext user_id" test, the user_id must be something recognizable like `"alice-uuid-fixture"` so you can assert its absence in the Location header.
- Do NOT use `freezegun`. For time-shifted tests, pass `now=<int>` to `create_slack_state_token` per spec §3.3.

## Environment Check
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-03
ls -la .env   # must show symlink → main .env
grep -c "^SLACK_CLIENT_ID=" .env || echo "MISSING"
grep -c "^SLACK_REDIRECT_URL=" .env || echo "MISSING"
grep -c "^JWT_SECRET=" .env || echo "MISSING"
grep -c "^TEEMO_ENCRYPTION_KEY=" .env || echo "MISSING"
```
All four must be present. If not, STOP.

## After Writing Tests
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-03/backend
.venv/bin/pytest tests/test_slack_install.py -v 2>&1 | tail -40
```
Confirm all tests FAIL (collection errors or HTTP 404s are both acceptable — the point is to prove the tests are wired to the right targets that don't exist yet).

## Report
Write `.worktrees/STORY-005A-03/.vbounce/reports/STORY-005A-03-dev-red.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-03"
agent: "developer"
phase: "red"
status: "tests-written"
test_files:
  - "backend/tests/test_slack_install.py"
test_count: N
test_run_result: "..."
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```
Body: scenario → test mapping, any blockers (especially around the auth fixture pattern), open questions.

## Out-of-Scope Reminder
Do NOT touch:
- `slack_events.py` (story 02)
- `encryption.py` / `slack.py` (story 01 — already merged)
- `oauth/callback` route (story 04)
- `models/slack.py` adding `SlackTeamResponse` (story 05)
- Frontend (story 06)
- BYOK, AsyncAssistant
