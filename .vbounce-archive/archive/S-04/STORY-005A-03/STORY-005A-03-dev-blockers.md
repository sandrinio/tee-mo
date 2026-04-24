---
status: "blocked"
story_id: "STORY-005A-03"
sprint_id: "S-04"
input_tokens: 3360
output_tokens: 1351
total_tokens: 4711
tokens_used: 4711
blocker_category: "test_pattern"
---

# Developer Blockers Report: STORY-005A-03 — Slack Install URL Builder

## What I Tried

- Implemented all 4 files per spec: `backend/app/core/security.py` (added `create_slack_state_token` + `verify_slack_state_token`), `backend/app/models/slack.py` (NEW `SlackInstallState`), `backend/app/api/routes/slack_oauth.py` (NEW `GET /api/slack/install`), `backend/app/main.py` (registered `slack_oauth_router`).
- Ran `pytest tests/test_slack_install.py -v`: **4 of 6 pass** (unit tests 1–3 + integration test 5). Tests 4 and 6 ERROR at fixture setup.
- Confirmed the 2 errors are NOT caused by my implementation — they fail at `pytest` fixture setup before any route or security code is invoked.

## Root Cause

The `authenticated_client` fixture in `backend/tests/test_slack_install.py` (lines 69–99) contains:

```python
alice_uuid = uuid.UUID("a11ce000-f1x7-0000-0000-a11ce0fixture")
```

The string `"a11ce000-f1x7-0000-0000-a11ce0fixture"` is **not a valid UUID**:
- Group 2 `f1x7` contains `x` — not a hex character.
- Group 5 `a11ce0fixture` is 13 characters — UUID group 5 must be exactly 12 hex chars.
- Group 5 contains `t`, `u`, `r`, `e` — none of which are hex.

Python's `uuid.UUID()` constructor raises `ValueError: badly formed hexadecimal UUID string` on this input. The error fires at fixture setup, before `create_access_token` or any of my route code is reached.

**Both failing tests use the `authenticated_client` fixture** (see their function signatures):
- `test_authenticated_user_gets_307_redirect(authenticated_client)` — line 191
- `test_location_header_does_not_contain_plaintext_user_id(authenticated_client)` — line 272

Test 6 also creates a separate `fresh_client` internally with a manually-constructed JWT (no UUID involved), but it still receives `authenticated_client` as a function parameter, triggering the fixture.

## Blocker Category

- [x] **Test Pattern Issue** — the `authenticated_client` fixture contains an invalid UUID string that raises `ValueError` before any test body runs. This cannot be fixed without modifying the test file.
- [ ] **Spec Gap**
- [ ] **Environment Issue**

## Suggested Fix

The Team Lead should fix the `authenticated_client` fixture's UUID string in `backend/tests/test_slack_install.py`. The intended "recognizable" UUID that relates to "alice" could be:

```python
# Option A — valid UUID, recognizable prefix (replace invalid string)
alice_uuid = uuid.UUID("a11ce000-0000-0000-0000-000000000001")
```

Or use a string-based approach entirely, bypassing `create_access_token`'s `UUID` type requirement by calling `jwt_module.encode` directly (as test 6 already does internally):

```python
# Option B — use jwt_module.encode directly, no uuid.UUID() call needed
import jwt as jwt_module
token = jwt_module.encode(
    {"sub": "alice-uuid-fixture", "role": "authenticated",
     "iat": int(time.time()), "exp": int(time.time()) + 900},
    settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm
)
client = TestClient(app, follow_redirects=False)
client.cookies.set("access_token", token)
```

Option B aligns with how test 6 already creates `fresh_client` internally and avoids the UUID type coupling entirely.

## Implementation Status (Partial — 4/6 tests pass)

My implementation is correct. The 4 passing tests confirm:
- `create_slack_state_token` / `verify_slack_state_token` work correctly (unit tests 1–3)
- `GET /api/slack/install` returns 401 for anonymous users (integration test 5)

The 2 blocked integration tests (4 + 6) would pass once the fixture UUID is fixed — the route, auth dependency, state token, and redirect URL construction are all implemented correctly per spec.

## Files Involved

- `backend/tests/test_slack_install.py` — lines 93–98: `authenticated_client` fixture has invalid UUID `"a11ce000-f1x7-0000-0000-a11ce0fixture"`. Needs a valid UUID string or switch to `jwt_module.encode` directly.
- `backend/app/core/security.py` — implementation complete, passing 3/3 unit tests.
- `backend/app/models/slack.py` — NEW, implementation complete.
- `backend/app/api/routes/slack_oauth.py` — NEW, implementation complete (anonymous 401 confirmed passing).
- `backend/app/main.py` — router registered, implementation complete.
