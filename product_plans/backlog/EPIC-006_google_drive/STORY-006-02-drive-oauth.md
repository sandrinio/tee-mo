---
story_id: "STORY-006-02-drive-oauth"
parent_epic_ref: "EPIC-006"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1 / Charter §5.3 Phase B step 6 / Roadmap ADR-002, ADR-009 / Codebase: slack_oauth.py pattern"
actor: "Workspace Admin"
complexity_label: "L3"
---

# STORY-006-02: Google Drive OAuth (Backend + Redirect)

**Complexity: L3** — Cross-cutting, adapts proven Slack OAuth pattern for Google

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin**,
> I want to **connect my Google Drive to a workspace via OAuth**,
> So that **the bot can read files I select later**.

### 1.2 Detailed Requirements
- **R1**: `GET /api/workspaces/{workspace_id}/drive/connect` — builds Google OAuth URL with state token (5-min JWT, embeds user_id + workspace_id), scopes (`openid`, `userinfo.email`, `drive.file`), `access_type=offline`, `prompt=consent`, redirects browser to Google.
- **R2**: `GET /api/drive/oauth/callback` — verifies state JWT, exchanges auth code for tokens via Google token endpoint, encrypts refresh token with AES-256-GCM, stores on `teemo_workspaces.encrypted_google_refresh_token`, redirects to frontend with query param (`?drive_connect=ok|error|expired|cancelled`).
- **R3**: `GET /api/workspaces/{workspace_id}/drive/status` — returns `{ connected: bool, email: str|null }`. If refresh token exists, mint access token and call userinfo to get email. Cache-friendly (frontend polls this).
- **R4**: `POST /api/workspaces/{workspace_id}/drive/disconnect` — nulls `encrypted_google_refresh_token` on workspace row. Returns 200.
- **R5**: All routes require JWT auth. Workspace ownership verified via `_assert_workspace_owner` pattern (404 if not owned).
- **R6**: State token pattern MUST follow `slack_oauth.py` — 5-min JWT signed with `supabase_jwt_secret`, verified in callback.
- **R7**: Handle `invalid_grant` from Google (revoked token) gracefully — null the stored token and return appropriate error.

### 1.3 Out of Scope
- Frontend UI (STORY-006-05)
- Google Picker integration (STORY-006-05)
- Knowledge index CRUD (STORY-006-03)
- Handling token refresh failures during file reads (handled in drive_service.py from STORY-006-01)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Google Drive OAuth

  Scenario: Initiate Drive OAuth
    Given a logged-in user who owns workspace "ws-1"
    When they call GET /api/workspaces/ws-1/drive/connect
    Then the response is 307 redirect to accounts.google.com
    And the redirect URL contains scope=drive.file
    And the redirect URL contains access_type=offline
    And the redirect URL contains a state JWT with user_id and workspace_id

  Scenario: OAuth callback success
    Given a valid state JWT and a valid authorization code from Google
    When GET /api/drive/oauth/callback?code=AUTH_CODE&state=VALID_JWT
    Then the backend exchanges the code for access_token + refresh_token
    And encrypts the refresh_token via AES-256-GCM
    And stores it in teemo_workspaces.encrypted_google_refresh_token
    And redirects to /app?drive_connect=ok

  Scenario: OAuth callback with expired state
    Given a state JWT that has expired (>5 minutes)
    When GET /api/drive/oauth/callback?code=AUTH_CODE&state=EXPIRED_JWT
    Then the backend redirects to /app?drive_connect=expired

  Scenario: OAuth callback with user denied consent
    Given the user clicked "Deny" on Google consent screen
    When GET /api/drive/oauth/callback?error=access_denied
    Then the backend redirects to /app?drive_connect=cancelled

  Scenario: Drive status when connected
    Given workspace "ws-1" has an encrypted_google_refresh_token
    When GET /api/workspaces/ws-1/drive/status
    Then response is { "connected": true, "email": "user@example.com" }

  Scenario: Drive status when not connected
    Given workspace "ws-1" has null encrypted_google_refresh_token
    When GET /api/workspaces/ws-1/drive/status
    Then response is { "connected": false, "email": null }

  Scenario: Disconnect Drive
    Given workspace "ws-1" has an encrypted_google_refresh_token
    When POST /api/workspaces/ws-1/drive/disconnect
    Then encrypted_google_refresh_token is set to null on the workspace row
    And response is 200
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_drive_oauth.py` passes
- [ ] Full backend test suite passes (no regressions)
- [ ] OAuth redirect URL is well-formed with correct scopes

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `GOOGLE_API_CLIENT_ID`, `GOOGLE_API_SECRET` in `.env` | [ ] |
| **Dependencies** | STORY-006-01 merged (drive_service.py, config changes) | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_drive_oauth.py` — test initiate (redirect URL shape), callback (mock Google token exchange), status, disconnect
- Mock `httpx.AsyncClient` for Google token endpoint calls (follow slack_oauth test pattern)

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/drive_oauth.py` (new) |
| **Related Files** | `backend/app/core/security.py` (state token helpers — adapt or reuse Slack ones), `backend/app/core/encryption.py` (encrypt refresh token), `backend/app/main.py` (mount router) |
| **New Files Needed** | Yes — `drive_oauth.py` |
| **ADR References** | ADR-002 (AES-256-GCM), ADR-009 (offline refresh token) |
| **First-Use Pattern** | No — adapts existing Slack OAuth pattern |

### 3.3 Technical Logic

**Follow `slack_oauth.py` pattern exactly:**
1. State token: `create_drive_state_token(user_id, workspace_id)` → 5-min JWT
2. Authorize URL: `https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&scope=openid email https://www.googleapis.com/auth/drive.file&access_type=offline&prompt=consent&state=JWT`
3. Callback: verify state → `POST https://oauth2.googleapis.com/token` with code + client_id + client_secret + redirect_uri → get `refresh_token` → `encrypt(refresh_token)` → upsert workspace row
4. Redirect to frontend with status param

**FLASHCARDS rules:**
- Import `httpx` at module level (monkeypatch pattern)
- Supabase `.upsert()` — omit DEFAULT NOW() columns
- State token uses `supabase_jwt_secret` for signing (same as Slack)

### 3.4 API Contract
| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/workspaces/{id}/drive/connect` | GET | JWT cookie | — | 307 redirect to Google |
| `/api/drive/oauth/callback` | GET | State JWT (query param) | `?code=...&state=...` | 302 redirect to frontend |
| `/api/workspaces/{id}/drive/status` | GET | JWT cookie | — | `{ connected: bool, email: str\|null }` |
| `/api/workspaces/{id}/drive/disconnect` | POST | JWT cookie | — | `{ status: "disconnected" }` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 4 | State token create/verify, redirect URL shape, disconnect |
| Integration tests | 5 | Callback success/expired/denied, status connected/not, disconnect |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
- [ ] Refresh token NEVER logged or returned to frontend.
- [ ] Router mounted in `main.py`.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
