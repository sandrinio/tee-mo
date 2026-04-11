---
task_id: "STORY-005A-04-dev-red"
story_id: "STORY-005A-04"
phase: "red"
agent: "developer"
worktree: ".worktrees/STORY-005A-04/"
sprint: "S-04"
execution_mode: "Full Bounce"
---

# Developer Task — STORY-005A-04 Red Phase (OAuth Callback — L3 Full Bounce)

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-04/` — branch `story/STORY-005A-04`, cut from `sprint/S-04` at commit `a65a767` (after 005A-01, 005A-02, 005A-03 all merged).

## This is the Full Bounce story
Unlike the other 5 stories in S-04, this one goes through **Dev → QA → Architect → DevOps**. It is the only place in the whole sprint where a security mistake could leak a Slack bot token. Treat every test like it might be the one that catches a bug in production.

## Phase
**RED PHASE — Tests ONLY.** Do NOT modify:
- `backend/app/api/routes/slack_oauth.py` (exists from 005A-03 with `/install` route; 04 will ADD `/oauth/callback` in Green Phase)
- `backend/app/api/deps.py` (Green phase may add `get_current_user_id_optional` variant)
- `backend/app/models/slack.py` or any other production file

Write tests that fail with `ImportError` / `AttributeError` / HTTP 404 — that proves the tests are wired to the right targets that don't exist yet.

## Story Spec
`.worktrees/STORY-005A-04/product_plans/sprints/sprint-04/STORY-005A-04-oauth-callback-upsert.md`

§1 Spec, §2.1 Gherkin (**10 scenarios**), §3 Implementation Guide are ground truth. The spec is long — read it in full before writing any test. Pay special attention to §3.3 for the 5 redirect branches and the hand-rolled `FakeAsyncClient` pattern.

## Mandatory Reading
1. `.worktrees/STORY-005A-04/FLASHCARDS.md` — full file. **Especially the Supabase factory pattern** (`get_supabase()` is the only entry point, service-role, cached) and BUG-20260411 (PyJWT module-local instance).
2. `.worktrees/STORY-005A-04/.vbounce/sprint-context-S-04.md`
3. `.worktrees/STORY-005A-04/backend/tests/test_auth_routes.py` — reference for real-Supabase test pattern with `unique_email` fixture + cleanup. Tests use a REAL self-hosted Supabase (no DB mocking).
4. `.worktrees/STORY-005A-04/backend/tests/test_slack_install.py` — reference for authenticated fixture + 307/401 pattern (your tests need a similar authenticated client).
5. `.worktrees/STORY-005A-04/backend/app/api/routes/slack_oauth.py` — current state (has `/install` from 005A-03; you'll test the yet-to-exist `/oauth/callback`).
6. `.worktrees/STORY-005A-04/backend/app/core/encryption.py` — `encrypt` / `decrypt` (you'll assert the row decrypts to the plaintext token).
7. `.worktrees/STORY-005A-04/backend/app/core/security.py` — `create_slack_state_token` / `verify_slack_state_token`.
8. `.worktrees/STORY-005A-04/database/migrations/005_teemo_slack_teams.sql` — schema: `slack_team_id` (PK), `owner_user_id` (UUID FK to teemo_users), `slack_bot_user_id`, `encrypted_slack_bot_token`, `installed_at`, `updated_at`.

## Test File to Create

**`backend/tests/test_slack_oauth_callback.py`**

Cover all 10 Gherkin scenarios from §2.1 as 10 integration tests. Structure:

```python
"""Integration tests for STORY-005A-04 — Slack OAuth callback (Red phase)."""

import base64
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
import jwt as jwt_module  # noqa: used in one specific test for expired-token crafting

from app.main import app
from app.core.config import settings, get_settings
from app.core.security import create_access_token, create_slack_state_token
from app.core.encryption import encrypt, decrypt
from app.core.db import get_supabase

# These imports are from routes/slack_oauth.py — will succeed for slack_install already
# but the /oauth/callback route being tested does not exist yet, so tests will get 404
# from TestClient calls, proving Red phase.


# ---- Canonical mock payload (slack-bolt oauth.v2.access shape) ----
MOCK_OAUTH_V2_ACCESS_OK = {
    "ok": True,
    "access_token": "xoxb-test-token-1",
    "token_type": "bot",
    "scope": "app_mentions:read,channels:history,channels:read,chat:write,groups:history,groups:read,im:history",
    "bot_user_id": "UBOT_TEST_001",
    "app_id": "A_TEST_001",
    "team": {"id": "T_TEST_001", "name": "Test Team"},
    "enterprise": None,
    "authed_user": {"id": "U_INSTALLER_001", "scope": "", "access_token": "xoxp-ignored", "token_type": "user"},
}


# ---- Hand-rolled httpx mock (first-use pattern for this codebase) ----
class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]):
        self.status_code = status_code
        self._payload = payload
    def json(self) -> dict[str, Any]:
        return self._payload
    @property
    def text(self) -> str:
        return json.dumps(self._payload)


class FakeAsyncClient:
    """Stand-in for httpx.AsyncClient. Captures the last POST for assertion."""
    last_call: dict[str, Any] | None = None
    _response_queue: list[dict[str, Any]] = []

    def __init__(self, *args, **kwargs):
        self._kwargs = kwargs
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        return False
    async def post(self, url, data=None, **kw):
        FakeAsyncClient.last_call = {"url": url, "data": data, "kwargs": kw}
        payload = FakeAsyncClient._response_queue.pop(0) if FakeAsyncClient._response_queue else MOCK_OAUTH_V2_ACCESS_OK
        return FakeResponse(200, payload)

    @classmethod
    def reset(cls):
        cls.last_call = None
        cls._response_queue = []

    @classmethod
    def queue(cls, payload: dict[str, Any]):
        cls._response_queue.append(payload)


@pytest.fixture(autouse=True)
def _reset_fake_client():
    FakeAsyncClient.reset()
    yield
    FakeAsyncClient.reset()


@pytest.fixture
def patch_httpx(monkeypatch):
    """Replace httpx.AsyncClient inside the slack_oauth module with the fake."""
    # The route will `import httpx` and then `httpx.AsyncClient(...)`.
    # Patch on the module attribute so the route picks up the fake.
    import app.api.routes.slack_oauth as slack_oauth_module
    monkeypatch.setattr(slack_oauth_module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.fixture
def alice_user():
    """Register a real user in teemo_users via the auth route and return (id, token).

    Uses the unique_email pattern from test_auth_routes.py so parallel tests don't collide.
    The user is cleaned up after the test.
    """
    import uuid
    email = f"alice+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    user_row = get_supabase().table("teemo_users").select("id").eq("email", email).single().execute()
    user_id = str(user_row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    yield user_id, token
    # Cleanup (ON DELETE CASCADE handles teemo_slack_teams children)
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def bob_user():
    """Second real user for cross-user tests."""
    import uuid
    email = f"bob+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    user_row = get_supabase().table("teemo_users").select("id").eq("email", email).single().execute()
    user_id = str(user_row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def cleanup_slack_teams():
    """Remove any T_TEST_* rows from teemo_slack_teams before + after the test."""
    def _clean():
        sb = get_supabase()
        sb.table("teemo_slack_teams").delete().like("slack_team_id", "T_TEST_%").execute()
    _clean()
    yield
    _clean()


@pytest.fixture
def alice_client(alice_user):
    user_id, token = alice_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def bob_client(bob_user):
    user_id, token = bob_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client
```

Then write the **10 tests** — one per Gherkin scenario. Map from §2.1:

1. **`test_happy_path_first_install`** — valid state for alice, mock oauth.v2.access returns success, GET /oauth/callback with alice's cookie + valid state. Assert:
   - `response.status_code == 302`
   - `response.headers["location"] == "/app?slack_install=ok"`
   - `FakeAsyncClient.last_call["url"] == "https://slack.com/api/oauth.v2.access"`
   - `FakeAsyncClient.last_call["data"]` contains `code`, `client_id`, `client_secret`, `redirect_uri`
   - `get_supabase().table("teemo_slack_teams").select("*").eq("slack_team_id", "T_TEST_001").single().execute()` returns a row with `owner_user_id == alice_user[0]`, `slack_bot_user_id == "UBOT_TEST_001"`, `encrypted_slack_bot_token != "xoxb-test-token-1"`, and `decrypt(row["encrypted_slack_bot_token"]) == "xoxb-test-token-1"`.

2. **`test_reinstall_same_owner`** — alice already has a row with old encrypted token, do another callback with a different mock token `xoxb-new`. Assert exactly one row exists (`.select("*").eq("slack_team_id", "T_TEST_001").execute()` length == 1), `decrypt(...) == "xoxb-new"`, `owner_user_id` still alice.

3. **`test_reinstall_different_owner_returns_409`** — alice owns the row (pre-insert a test row with alice as owner), bob logs in and completes the callback for T_TEST_001 with bob's state. Assert:
   - `response.status_code == 409`
   - response body contains `"already installed under a different account"`
   - the existing row is UNCHANGED (still alice's owner_user_id, still old token)

4. **`test_cancellation_redirects_to_cancelled`** — GET `/api/slack/oauth/callback?error=access_denied&state=<alice_valid>` with alice's cookie. Assert:
   - `302`, Location == `"/app?slack_install=cancelled"`
   - `FakeAsyncClient.last_call is None` (no Slack API call was made)
   - No row was written

5. **`test_state_tampered_returns_400`** — craft a valid state, flip the last char of the signature, send with alice's cookie. Assert:
   - `400`
   - body contains `"invalid state"`
   - `FakeAsyncClient.last_call is None`

6. **`test_state_expired_redirects_to_expired`** — craft a state token with `now=` shifted 301s into the past (use `create_slack_state_token(user_id, now=past)` helper), send as alice. Assert:
   - `302`, Location == `"/app?slack_install=expired"`
   - `FakeAsyncClient.last_call is None`

7. **`test_cross_user_state_returns_403`** — alice_state + bob's cookie. Assert:
   - `403`
   - `FakeAsyncClient.last_call is None`

8. **`test_slack_ok_false_redirects_to_error`** — queue `{"ok": False, "error": "invalid_code"}` on the FakeAsyncClient. Assert:
   - `302`, Location == `"/app?slack_install=error"`
   - A warning was logged (`caplog`) containing `"invalid_code"` OR a rejection reason.

9. **`test_slack_missing_bot_user_id_redirects_to_error`** — queue an ok response but WITHOUT `bot_user_id`. Assert:
   - `302`, Location == `"/app?slack_install=error"`
   - A warning was logged containing `"missing bot_user_id"` (or similar keyword).

10. **`test_token_never_appears_in_logs`** — run the happy path with `caplog.set_level(logging.DEBUG)`, then assert:
    - `"xoxb-test-token-1" not in caplog.text`
    - The decrypted token's ciphertext (fetch the row, read the `encrypted_slack_bot_token` string) also `not in caplog.text`

## Critical Rules
- **Use REAL Supabase.** No DB mocking. Test users must be created in `teemo_users` and cleaned up via fixtures (cleanup is automatic via `ON DELETE CASCADE` + explicit `cleanup_slack_teams` fixture).
- **Mock ONLY httpx.** Production encryption, state token, auth dep, Supabase upsert are all real.
- **All test `slack_team_id` values use the prefix `T_TEST_`** so the cleanup fixture can find them.
- **Every test that hits the callback uses the `cleanup_slack_teams` fixture** to guarantee a clean slate.
- **Every test takes `patch_httpx`** to install the fake client.
- **Do not `time.sleep()`.** Use `create_slack_state_token(user_id, now=past)` to craft expired tokens.
- **Use `follow_redirects=False`** on the TestClient (already in the alice_client fixture) so you can inspect 302 headers.
- **Do NOT modify any production file.** If a test import fails with `AttributeError: module 'app.api.routes.slack_oauth' has no attribute 'httpx'`, that's OK — it proves the route doesn't yet import httpx.

## Environment Check
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-04
ls -la .env   # must be a symlink to main .env
grep -c "^SUPABASE_URL=" .env || echo "MISSING"
grep -c "^SUPABASE_SERVICE_ROLE_KEY=" .env || echo "MISSING"
grep -c "^SLACK_CLIENT_ID=" .env || echo "MISSING"
grep -c "^SLACK_CLIENT_SECRET=" .env || echo "MISSING"
grep -c "^TEEMO_ENCRYPTION_KEY=" .env || echo "MISSING"
```
If Supabase is not reachable from the test host, STOP and write a blockers report — this story cannot be red-phased without a live DB.

## After Writing Tests
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-04/backend
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_oauth_callback.py -v 2>&1 | tail -50
```
Expect all 10 tests to FAIL (most with 404 Not Found on `/api/slack/oauth/callback`, some with `AttributeError` if the route module doesn't import httpx yet). Record exact failure modes per test.

## Report
Write `.vbounce/reports/STORY-005A-04-dev-red.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-04"
agent: "developer"
phase: "red"
status: "tests-written"
test_files: ["backend/tests/test_slack_oauth_callback.py"]
test_count: 10
test_run_result: "10 failed, 0 passed (expected — /oauth/callback does not exist)"
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```
Body: scenario → test mapping, description of the FakeAsyncClient mock pattern for downstream reference, any blockers (especially around Supabase connectivity), open questions flagged for Team Lead.

## Out-of-Scope Reminder
Do NOT touch:
- Frontend (story 06)
- `/api/slack/teams` endpoint (story 05)
- slack_events.py (story 02 — already merged)
- Any other route
- BYOK, AsyncAssistant, uninstall flow
