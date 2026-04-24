---
story_id: "STORY-005A-04-oauth-callback-upsert"
parent_epic_ref: "EPIC-005-phase-a"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L3"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-04/STORY-005A-04-oauth-callback-upsert.md`. Shipped in sprint S-04, carried forward during ClearGate migration 2026-04-24.

# STORY-005A-04: `GET /api/slack/oauth/callback` — Code Exchange + Encrypt + Upsert

**Complexity: L3** — Cross-cutting: HTTP route, Slack Web API call, encryption, DB upsert, 5 distinct error branches, security-sensitive. ~6 files touched. Heaviest story in Phase A.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Tee-Mo user who just clicked "Allow" on Slack's OAuth consent**,
> I want to **be redirected back to `/app` with my Slack team installed and visible**,
> So that **I can move on to creating workspaces under that team in S-05**.

### 1.2 Detailed Requirements

- **Req 1 — Endpoint shape:** `GET /api/slack/oauth/callback` in `backend/app/api/routes/slack_oauth.py` (modify the file from STORY-005A-03 — add the second route).
- **Req 2 — Query params:** Slack will hit this URL with one of these param shapes:
  - **Success:** `?code=<oauth_code>&state=<our_signed_state>` — proceed with exchange.
  - **Denial:** `?error=access_denied&state=<our_signed_state>` — user clicked Cancel; redirect to `/app?slack_install=cancelled`.
- **Req 3 — Verify state FIRST:** Before any Slack API call, verify the `state` token via `verify_slack_state_token()` from STORY-005A-03:
  - Invalid signature → 400 with `{"detail": "invalid state"}`. No redirect (this is suspicious — caller is not a real Slack flow).
  - Expired (`jwt.ExpiredSignatureError`) → redirect to `/app?slack_install=expired`. (Benign — user took >5 min on the consent screen.)
  - Valid → extract `user_id` and continue.
- **Req 4 — Cross-user check:** The state's `user_id` MUST equal the authenticated user from the auth cookie (`get_current_user_id` dep) — if mismatch, 403 "state user mismatch". This closes R4 cross-user hijacking.
  - **Edge:** if there's no auth cookie at all (user logged out during the consent flow), redirect to `/login?next=/app&slack_install=session_lost`. Don't 401 — that produces a blank page.
- **Req 5 — Code exchange:** POST to `https://slack.com/api/oauth.v2.access` with form body:
  - `code=<query_code>`
  - `client_id=<settings.slack_client_id>`
  - `client_secret=<settings.slack_client_secret>`
  - `redirect_uri=<settings.slack_redirect_url>` (must match exactly what was sent in the install URL)
  - Use `httpx.AsyncClient` (already a transitive dep via supabase-py / fastapi). Timeout: 10s.
- **Req 6 — Response parsing:** Slack returns JSON. Parse and validate:
  - `ok: bool` — must be `True`. If `False`, log `error` field and redirect to `/app?slack_install=error` (single 500-style branch).
  - `team.id: str` — required.
  - `bot_user_id: str` — required (verified present at slack-bolt source `oauth_flow.py:344` on 2026-04-12). If missing → redirect `/app?slack_install=error` with log line "oauth.v2.access missing bot_user_id".
  - `access_token: str` — the bot token (`xoxb-...`). Required.
- **Req 7 — Encrypt the bot token:** Call `encrypt(access_token)` from `backend/app/core/encryption.py` (STORY-005A-01).
- **Req 8 — Upsert teemo_slack_teams:** Use `get_supabase().table("teemo_slack_teams").upsert(...).execute()` keyed on `slack_team_id` (PK). Row payload:
  ```python
  {
      "slack_team_id": team_id,
      "owner_user_id": user_id,         # from state token (== auth cookie user)
      "slack_bot_user_id": bot_user_id,
      "encrypted_slack_bot_token": encrypted_token,
      "updated_at": "now()",            # let Postgres default; or pass datetime.utcnow().isoformat()
  }
  ```
  `installed_at` is set by the column default on first insert and untouched on upsert (Supabase upsert won't reset DEFAULT NOW() columns unless you pass them).
- **Req 9 — Different-owner conflict (Q2 decided):** Before upserting, SELECT existing row by `slack_team_id`. If a row exists AND `existing.owner_user_id != user_id` → 409 Conflict with body `{"detail": "This Slack team is already installed under a different account."}`. Do NOT redirect — surface the error so the user understands.
- **Req 10 — Success redirect:** On successful upsert, return `RedirectResponse("/app?slack_install=ok", status_code=302)`.
- **Req 11 — Token never in logs / response:** The bot token (plaintext OR encrypted) MUST NEVER appear in any log line or response body. Validate via a grep test in §2.

### 1.3 Out of Scope
- Listing teams for the dashboard — STORY-005A-05.
- Frontend banner rendering of `?slack_install=ok|cancelled|expired|error|session_lost` — STORY-005A-06.
- `app_uninstalled` event handling — Phase B / future.
- Uninstall API — out of scope for hackathon.
- Any workspace-level work — S-05 / EPIC-003 Slice B.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: Slack OAuth Callback

  Background:
    Given Slack credentials, JWT_SECRET, TEEMO_ENCRYPTION_KEY are set
    And user "alice" is logged in with id "alice-uuid"

  Scenario: Happy path — first install
    Given a valid state token for user_id="alice-uuid"
    And mocked oauth.v2.access returns:
      | ok          | true               |
      | team.id     | T_TEST_001         |
      | bot_user_id | UBOT_TEST_001      |
      | access_token| xoxb-test-token-1  |
    When GET /api/slack/oauth/callback?code=ok_code&state=<valid> with alice's cookie
    Then the response status is 302
    And the Location header is "/app?slack_install=ok"
    And teemo_slack_teams contains a row with:
      | slack_team_id     | T_TEST_001    |
      | owner_user_id     | alice-uuid    |
      | slack_bot_user_id | UBOT_TEST_001 |
    And the row's encrypted_slack_bot_token decrypts to "xoxb-test-token-1"
    And the encrypted_slack_bot_token is NOT equal to "xoxb-test-token-1"

  Scenario: Re-install — same owner, same team
    Given alice already has a teemo_slack_teams row for T_TEST_001 with token "xoxb-old"
    And mocked oauth.v2.access returns a fresh token "xoxb-new"
    When alice completes the callback again
    Then the response is 302 to /app?slack_install=ok
    And exactly ONE row exists for T_TEST_001 (no duplicate)
    And the row's encrypted_slack_bot_token decrypts to "xoxb-new"
    And the row's owner_user_id is still "alice-uuid"

  Scenario: Re-install — different owner (R5 / Q2)
    Given alice already owns the row for T_TEST_001
    And bob (user_id "bob-uuid") is logged in
    And bob completes the OAuth flow for T_TEST_001
    When the callback runs with bob's cookie + bob's state
    Then the response status is 409
    And the response body contains "already installed under a different account"
    And the row in teemo_slack_teams is unchanged (still owned by alice with old token)

  Scenario: User cancelled at Slack consent
    Given the callback receives ?error=access_denied&state=<valid>
    When the callback runs
    Then the response status is 302
    And the Location header is "/app?slack_install=cancelled"
    And NO Slack API call was made
    And NO teemo_slack_teams row was written

  Scenario: State signature tampered
    Given the callback receives ?code=ok_code&state=<tampered>
    When the callback runs
    Then the response status is 400
    And the body contains "invalid state"
    And NO Slack API call was made
    And NO row was written

  Scenario: State expired (>5 min)
    Given the callback receives ?code=ok_code&state=<expired>
    When the callback runs
    Then the response status is 302
    And the Location is "/app?slack_install=expired"
    And NO Slack API call was made

  Scenario: State user_id != auth user_id (cross-user attempt)
    Given the state token is for "alice-uuid"
    And the auth cookie is for "bob-uuid"
    When the callback runs
    Then the response status is 403
    And NO Slack API call was made

  Scenario: Slack returns ok=false
    Given mocked oauth.v2.access returns {"ok": false, "error": "invalid_code"}
    When the callback runs
    Then the response status is 302
    And the Location is "/app?slack_install=error"
    And a warning is logged with the Slack error code

  Scenario: Slack response missing bot_user_id
    Given mocked oauth.v2.access returns ok=true but no bot_user_id field
    When the callback runs
    Then the response is 302 to /app?slack_install=error
    And a warning is logged "oauth.v2.access missing bot_user_id"

  Scenario: Token never appears in logs
    Given the happy path runs successfully
    When all log output for the request is captured
    Then the captured logs do NOT contain "xoxb-test-token-1"
    And the captured logs do NOT contain the encrypted ciphertext
```

### 2.2 Verification Steps (Manual)
- [ ] `cd backend && uv run pytest tests/test_slack_oauth_callback.py -v`
- [ ] After deploy + S-04 release: open the authorize URL from STORY-005A-03 in a browser, click Allow on the Slack consent screen, observe redirect to `https://teemo.soula.ge/app?slack_install=ok` and a `teemo_slack_teams` row in production Supabase. **This is the Phase A success demo.**

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-005A-01 (encryption.py + config + slack.py), STORY-005A-03 (state token helpers + slack_oauth.py exists) | [ ] |
| **Env Vars** | `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_REDIRECT_URL`, `JWT_SECRET`, `TEEMO_ENCRYPTION_KEY` | [ ] |
| **Slack app config** | `redirect_uri` in the Slack app manifest matches `SLACK_REDIRECT_URL` exactly (trailing slash, scheme, host) | [ ] |
| **Test deps** | `pytest`, `httpx` (already deps); NO new deps. | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_slack_oauth_callback.py`.
- **Mock Slack:** Use a hand-rolled `httpx.AsyncClient` mock via `monkeypatch` on the module's client constructor. Pattern:
  ```python
  class FakeAsyncClient:
      def __init__(self, *args, **kwargs): ...
      async def __aenter__(self): return self
      async def __aexit__(self, *a): return False
      async def post(self, url, data=None, **kw):
          return FakeResponse(200, MOCK_OAUTH_RESPONSE)

  monkeypatch.setattr("app.api.routes.slack_oauth.httpx.AsyncClient", FakeAsyncClient)
  ```
- **Canonical mock response** (use the shape verified in slack-bolt source on 2026-04-12):
  ```python
  MOCK_OAUTH_RESPONSE_SUCCESS = {
      "ok": True,
      "access_token": "xoxb-test-token-1",
      "token_type": "bot",
      "scope": "app_mentions:read,channels:history,...",
      "bot_user_id": "UBOT_TEST_001",
      "app_id": "A_TEST_001",
      "team": {"id": "T_TEST_001", "name": "Test Team"},
      "enterprise": None,
      "authed_user": {"id": "U_INSTALLER", "scope": "...", "access_token": "xoxp-...", "token_type": "user"},
  }
  ```
- **DB cleanup:** Use a `cleanup_slack_team` fixture that deletes test rows by `slack_team_id` prefix (`T_TEST_*`). Pattern from `test_auth_routes.py` `unique_email` fixture.
- One test per Gherkin scenario (10 scenarios → 10 tests).

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `backend/app/api/routes/slack_oauth.py` (MODIFY — add `/oauth/callback` route) |
| **Related Files** | `backend/app/core/encryption.py` (READ — `encrypt`), `backend/app/core/security.py` (READ — `verify_slack_state_token`), `backend/app/core/db.py` (READ — `get_supabase`), `backend/app/api/deps.py` (READ — `get_current_user_id`), `database/migrations/005_teemo_slack_teams.sql` (READ — column names) |
| **New Test Files** | `backend/tests/test_slack_oauth_callback.py` |
| **ADR References** | ADR-002 + ADR-010 (encryption), ADR-024 (slack_team_id PK + owner_user_id), ADR-001 (JWT for state) |
| **First-Use Pattern** | **Yes** — first time the codebase uses `httpx.AsyncClient` for outbound HTTP, first time it uses Supabase `.upsert()`, first time it composes encryption + DB write in one route. Search FLASHCARDS.md for any prior httpx pattern; if absent, add a flashcard after merge. |

### 3.3 Technical Logic

**Callback flow (pseudocode):**
```python
@router.get("/oauth/callback")
async def slack_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    user_id_or_none = Depends(get_current_user_id_optional),  # see note
):
    # 1. Cancellation
    if error == "access_denied":
        return RedirectResponse("/app?slack_install=cancelled", status_code=302)

    # 2. State verification (signature first, then expiry)
    if not state or not code:
        raise HTTPException(400, "missing code or state")
    try:
        state_payload = verify_slack_state_token(state)
    except jwt.ExpiredSignatureError:
        return RedirectResponse("/app?slack_install=expired", status_code=302)
    except jwt.InvalidTokenError:
        raise HTTPException(400, "invalid state")

    # 3. Cross-user check
    if user_id_or_none is None:
        return RedirectResponse("/login?next=/app&slack_install=session_lost", status_code=302)
    if user_id_or_none != state_payload.user_id:
        raise HTTPException(403, "state user mismatch")

    # 4. Exchange code
    s = get_settings()
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
        logger.warning("oauth.v2.access failed: %s", payload.get("error", "unknown"))
        return RedirectResponse("/app?slack_install=error", status_code=302)

    team_id = payload["team"]["id"]
    bot_user_id = payload.get("bot_user_id")
    bot_token = payload.get("access_token")
    if not bot_user_id or not bot_token:
        logger.warning("oauth.v2.access missing bot_user_id or access_token")
        return RedirectResponse("/app?slack_install=error", status_code=302)

    # 5. Different-owner check
    sb = get_supabase()
    existing = sb.table("teemo_slack_teams").select("owner_user_id").eq("slack_team_id", team_id).limit(1).execute()
    if existing.data and existing.data[0]["owner_user_id"] != user_id_or_none:
        raise HTTPException(409, "This Slack team is already installed under a different account.")

    # 6. Encrypt + upsert
    encrypted = encrypt(bot_token)
    sb.table("teemo_slack_teams").upsert({
        "slack_team_id": team_id,
        "owner_user_id": user_id_or_none,
        "slack_bot_user_id": bot_user_id,
        "encrypted_slack_bot_token": encrypted,
    }).execute()

    return RedirectResponse("/app?slack_install=ok", status_code=302)
```

**Note on `get_current_user_id_optional`:** The auth-cookie dep currently raises 401 on missing cookie. For this route we want to redirect to login instead. Either:
- Add a new optional variant in `backend/app/api/deps.py` (`get_current_user_id_optional() -> str | None`), OR
- Catch the `HTTPException(401)` in the route and convert to a redirect.
Prefer the optional variant — cleaner separation.

### 3.4 API Contract

| Endpoint | Method | Auth | Request Query | Responses |
|----------|--------|------|---------------|-----------|
| `/api/slack/oauth/callback` | GET | Auth cookie + signed state | `code`, `state` (success) OR `error=access_denied`, `state` (denial) | 302 → `/app?slack_install=ok\|cancelled\|expired\|error\|session_lost`; 400 invalid state; 403 cross-user; 409 different owner |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (logic is integration-shaped; helpers tested in 005A-01/03) | |
| Integration tests | 10 | One per Gherkin scenario |
| Component tests | 0 — N/A | |
| E2E / acceptance | 1 manual | Real OAuth click-through against production after merge |

### 4.2 Definition of Done
- [ ] TDD Red phase enforced — all 10 scenario tests written failing first.
- [ ] §4.1 minimum counts met.
- [ ] FLASHCARDS.md consulted (httpx.AsyncClient first-use, Supabase upsert first-use).
- [ ] Real OAuth click-through against production succeeds; row visible in `teemo_slack_teams`.
- [ ] Token never in logs (grep test passes).
- [ ] No ADR violations (uses encryption per ADR-002/010, owner per ADR-024).
- [ ] Sprint Context updated with the production install team_id for downstream stories to reference.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 1,046 | 599 | 1,645 |
| QA | 16 | 341 | 357 |
| DevOps | 17 | 446 | 463 |
