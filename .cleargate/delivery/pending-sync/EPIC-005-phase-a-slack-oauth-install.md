---
epic_id: "EPIC-005-phase-a"
status: "Active"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "2026-04-13"
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-005_slack_integration/EPIC-005-phase-a_slack_oauth_install.md`. Carried forward during ClearGate migration 2026-04-24.

# EPIC-005 Phase A: Slack OAuth Install

## 1. Problem & Value

### 1.1 The Problem

Tee-Mo is a Slack-first AI assistant, but as of S-03 it has zero connection to Slack. The product cannot be demoed, tested in production shape, or unblock any Release 2 work (BYOK, Drive, Agent) until a real Slack team is installed and a `teemo_slack_teams` row exists. The S-03 `/api/slack/events` stub proves the webhook endpoint is reachable, but it is unsigned and handles no real events.

### 1.2 The Solution

Implement the **one-time per Slack team install** half of EPIC-005 — Charter §5.3 Phase A — end to end:

1. A logged-in user clicks **Install Slack** on `/app`.
2. Backend constructs a Slack OAuth v2 authorize URL with the 7 ADR-021/025 scopes and a CSRF-safe `state` parameter, redirects the browser to Slack.
3. User approves the app in their Slack workspace.
4. Slack redirects to `https://teemo.soula.ge/api/slack/oauth/callback?code=…&state=…`.
5. Backend verifies `state`, exchanges `code` via `oauth.v2.access`, extracts `team.id` + `bot_user_id` + `access_token`, encrypts the token with AES-256-GCM, upserts a `teemo_slack_teams` row owned by the authenticated user, redirects back to `/app`.
6. `/app` now lists the installed team.
7. As a side deliverable: the S-03 `/api/slack/events` stub gets **real** Slack signing-secret verification, closing the `TODO(S-04)` in `backend/app/api/routes/slack_events.py:24`.

### 1.3 Success Metrics (North Star)

- **A user can install Tee-Mo into a real Slack workspace from the dashboard in <30 seconds end-to-end.**
- **One `teemo_slack_teams` row exists in production with a non-null `encrypted_slack_bot_token` and a non-null `slack_bot_user_id`.**
- **The team appears on `/app` immediately after the OAuth redirect completes.**
- **Re-installing the same team (a second click through the flow) does not create a duplicate row** — verified by unique `slack_team_id` count.
- **`/api/slack/events` rejects unsigned or expired Slack requests** — verified by a negative test that POSTs without a valid `X-Slack-Signature`.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)

- [ ] `backend/app/core/encryption.py` — AES-256-GCM wrapper (`encrypt(plaintext: str) -> str`, `decrypt(ciphertext: str) -> str`) using `cryptography.AESGCM`, key loaded from `TEEMO_ENCRYPTION_KEY` env var (32-byte base64). Per ADR-002 + ADR-010.
- [ ] `backend/app/core/slack.py` — `slack_bolt.AsyncApp` instance + `AsyncSlackRequestHandler` factory, configured from `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`. Single source for all future Slack client work.
- [ ] `backend/app/core/config.py` — declare `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_REDIRECT_URL`, `TEEMO_ENCRYPTION_KEY` as `Settings` fields. Startup validation: `TEEMO_ENCRYPTION_KEY` must decode to 32 bytes.
- [ ] `backend/app/api/routes/slack_oauth.py` — **`GET /api/slack/install`**: requires auth (cookie), generates signed `state` containing `user_id`, returns `307 Temporary Redirect` to Slack authorize URL with `client_id`, `scope`, `redirect_uri`, `state`.
- [ ] `backend/app/api/routes/slack_oauth.py` — **`GET /api/slack/oauth/callback`**: verifies `state` signature, handles `?error=access_denied` (redirects `/app?slack_install=cancelled`), exchanges `code` via `oauth.v2.access`, extracts `team.id` + `authed_user.id` + `bot_user_id` + `access_token`, encrypts token, **upserts** `teemo_slack_teams` on `slack_team_id` (PK) with `owner_user_id = state.user_id`, redirects to `/app?slack_install=ok`.
- [ ] `backend/app/api/routes/slack_events.py` — replace the `TODO(S-04)` with **real `X-Slack-Signature` + `X-Slack-Request-Timestamp` verification** against `SLACK_SIGNING_SECRET` per Slack's signing spec (HMAC-SHA256, 5-minute timestamp window). Still handles only `url_verification` challenge + 202s everything else. Real event handlers remain Phase B.
- [ ] `backend/app/models/slack.py` — Pydantic models: `SlackInstallState`, `SlackOAuthCallbackQuery`, `SlackTeamRow` (response).
- [ ] `frontend/src/routes/app.tsx` — replace the welcome card body with: **"Slack Teams" heading**, **list of installed teams** (from a new `GET /api/slack/teams` endpoint), **Install Slack button** that navigates to `/api/slack/install` via `<a href>`. Show a flash banner on return if `?slack_install=ok` or `?slack_install=cancelled` in the URL.
- [ ] `frontend/src/lib/api.ts` — add `listSlackTeams()` wrapping `GET /api/slack/teams`.
- [ ] Backend tests: signature verification happy + unhappy; state token sign/verify; callback success path (mocked `oauth.v2.access`); callback denial path; callback with bad state; upsert semantics (re-install same team).
- [ ] Frontend tests: `/app` renders Install button when no teams, renders team list when teams present, renders success/cancel banners from query params.
- [ ] **Coolify env vars**: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_REDIRECT_URL=https://teemo.soula.ge/api/slack/oauth/callback`, `TEEMO_ENCRYPTION_KEY=<32-byte base64>` — DevOps adds these to the Coolify service config before the S-04 release merges.

### ❌ OUT-OF-SCOPE (Do NOT Build This)

- `app_mention` or `message.im` event handlers — **deferred to EPIC-005 Phase B** (after EPIC-007 agent exists).
- Self-message filter logic — Phase B.
- Workspace CRUD under a team — **deferred to S-05 / EPIC-003 Slice B**.
- Channel binding CRUD, `conversations.list`, channel picker modal — Phase B.
- The unbound-channel nudge handler — Phase B.
- `GET /api/slack/teams/:id/channels` — Phase B.
- Token rotation, uninstall webhook handling, `app_uninstalled` cleanup — **explicitly deferred**.
- Multi-user per team (the "organization install" flow) — single-user install only.
- BYOK key CRUD — EPIC-004 (Release 2).
- Google Drive OAuth — EPIC-006 (Release 2).
- **Slack Agents & AI Apps surface** — **explicitly deferred to Phase B evaluation.** Investigated 2026-04-12: `slack-bolt==1.28.0` ships `AsyncAssistant` middleware but plan-tier gate is undocumented. Decision: **do NOT toggle AI Apps in S-04**; revisit at the start of Phase B planning with a 15-min spike.

---

## 3. Context

### 3.1 User Personas

- **Solo Dev (installer)** — a user who has registered via EPIC-002 and is logged into `/app`. Clicks Install Slack, approves consent in Slack, lands back on `/app` with a visible team. First-and-only user persona for the hackathon demo.
- **(Deferred) Team admin** — in the real world, installing Tee-Mo into a shared Slack workspace requires Slack workspace admin permission.

### 3.2 User Journey (Happy Path)

```mermaid
flowchart LR
    A[User on /app] -->|clicks Install Slack| B[GET /api/slack/install]
    B -->|signed state + redirect| C[Slack authorize page]
    C -->|user approves| D[GET /api/slack/oauth/callback?code=&state=]
    D -->|verify state| E[oauth.v2.access]
    E -->|encrypt token| F[upsert teemo_slack_teams]
    F -->|302| G[/app?slack_install=ok]
    G -->|list teams| H[Team card visible]
```

### 3.3 Constraints

| Type | Constraint |
|------|------------|
| **Performance** | OAuth callback must complete in <3s. |
| **Security** | (1) Bot token MUST be AES-256-GCM encrypted at rest per ADR-010 — never plaintext, not even in logs. (2) `state` parameter MUST be cryptographically signed. (3) `/api/slack/events` MUST reject requests with missing/invalid/expired Slack signatures. (4) `/api/slack/install` MUST require authentication. (5) `TEEMO_ENCRYPTION_KEY` MUST NOT appear in any log or error message. |
| **Tech Stack** | `slack-bolt==1.28.0` (pinned, already in `pyproject.toml`); `cryptography==46.0.7` (already installed). Must not pull in new Slack libraries. |
| **Cookies** | Auth cookie is `SameSite=Lax` per FLASHCARDS.md 2026-04-11 — this is WHY Lax is required (OAuth redirect hop would drop Strict cookies). |
| **Redirect URL** | The manifest registered `https://teemo.soula.ge/api/slack/oauth/callback`. Backend `redirect_uri` in the authorize URL must match EXACTLY. |

---

## 4. Technical Context

### 4.1 Affected Areas

| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Backend encryption | `backend/app/core/encryption.py` | **NEW** |
| Backend Slack client | `backend/app/core/slack.py` | **NEW** |
| Backend config | `backend/app/core/config.py` | **MODIFY** (add 5 fields + 1 startup validator) |
| Backend OAuth routes | `backend/app/api/routes/slack_oauth.py` | **NEW** |
| Backend events (hardening) | `backend/app/api/routes/slack_events.py` | **MODIFY** (add signing-secret verification; remove TODO) |
| Backend Slack models | `backend/app/models/slack.py` | **NEW** |
| Backend router registration | `backend/app/main.py` | **MODIFY** (include `slack_oauth_router`) |
| Backend tests | `backend/tests/test_slack_oauth.py`, `backend/tests/test_slack_events_signed.py`, `backend/tests/test_encryption.py` | **NEW** |
| Frontend `/app` | `frontend/src/routes/app.tsx` | **MODIFY** |
| Frontend API client | `frontend/src/lib/api.ts` | **MODIFY** (add `listSlackTeams()`) |
| Frontend types | `frontend/src/types/slack.ts` (or inline) | **NEW** |
| Frontend tests | `frontend/src/routes/__tests__/app.test.tsx` (or equivalent) | **NEW/MODIFY** |
| Coolify env vars | (external, not in repo) | **CONFIG** — 5 new vars added via Coolify UI by DevOps |

### 4.2 Dependencies

| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-002 (Auth) — need `get_current_user_id` dep for `/api/slack/install` | Done (S-02) |
| **Requires** | EPIC-003 Slice A (schema) — `teemo_slack_teams` table exists | Done (S-03) |
| **Requires** | ADR-026 Deploy — `https://teemo.soula.ge` reachable with HTTPS for OAuth `redirect_uri` | Done (S-03) |
| **Requires** | Slack app registered in api.slack.com with correct scopes, redirect URL, signing secret | Done |
| **Unlocks** | EPIC-003 Slice B (Workspace CRUD) — needs real `teemo_slack_teams` rows to render under | Waiting (S-05) |
| **Unlocks** | EPIC-005 Phase B (events) — needs `slack_bot_user_id` from Phase A install rows | Deferred (after EPIC-007) |
| **Unlocks** | EPIC-004 (BYOK) — reuses `encryption.py` wrapper | Waiting (R2) |
| **Unlocks** | EPIC-006 (Drive) — reuses `encryption.py` wrapper for refresh tokens | Waiting (R2) |

### 4.3 Integration Points

| System | Purpose | Docs |
|--------|---------|------|
| Slack OAuth v2 `oauth.v2.access` | Exchange `code` → `access_token` + `team.id` + `authed_user.id` + `bot_user_id` | https://api.slack.com/methods/oauth.v2.access |
| Slack signing secret verification | Verify `/api/slack/events` requests come from Slack | https://api.slack.com/authentication/verifying-requests-from-slack |
| `slack_bolt.AsyncApp` | Bolt Python async app with `AsyncSlackRequestHandler` for FastAPI | https://slack.dev/bolt-python |
| `cryptography.AESGCM` | AES-256-GCM symmetric encryption | https://cryptography.io/en/latest/hazmat/primitives/aead/ |
| Supabase Python client | `teemo_slack_teams` upsert via `.upsert()` method | (already used in auth routes) |

### 4.4 Data Changes

| Entity | Change | Fields |
|--------|--------|--------|
| `teemo_slack_teams` | **WRITE** (first writes) | `slack_team_id` (PK), `owner_user_id`, `slack_bot_user_id`, `encrypted_slack_bot_token`, `installed_at`, `updated_at` |
| (No schema changes) | — | Migration 005 already created the table in S-03 |

---

## 5. Decomposition Guidance

### Suggested Sequencing Hints

1. **Foundation first** — `encryption.py` + config vars + `slack.py` Bolt scaffold.
2. **Events hardening** — signature verification for `/api/slack/events`.
3. **Install URL builder** — `GET /api/slack/install` with signed state.
4. **OAuth callback** — `GET /api/slack/oauth/callback` with code exchange + encrypt + upsert.
5. **Teams list endpoint** — `GET /api/slack/teams`.
6. **Frontend Install button + teams list** — consumes #5.
7. **Success/cancel flash banners** — small UX polish on #6.

The natural shape is **6–8 stories**.

---

## 6. Risks & Edge Cases

| # | Risk | Likelihood | Mitigation |
|---|------|------------|------------|
| R1 | **Encryption key loss between deploys** | Medium | Store key in Coolify env UI (never in repo). |
| R2 | **Slack signing secret clock skew** | Low | The 5-minute window is standard. |
| R3 | **State parameter replay** | Low | Sign `state` with HMAC-SHA256 using `JWT_SECRET` + add a short `exp` claim (5 minutes). |
| R4 | **Cross-user team hijacking** | Low | `state` token includes `user_id`, verified on callback. |
| R5 | **Re-install with different owner** | Medium | On callback, if row exists with a different `owner_user_id`, return 409 Conflict. |
| R6 | **`SLACK_REDIRECT_URL` mismatch** | Medium | Single source of truth: `settings.slack_redirect_url`. |
| R7 | **OAuth `code` single-use** | Low | Callback catches `invalid_code` and redirects to `/app?slack_install=expired`. |
| R8 | **Bot token leaks via error message** | Low | Catch-all `try/except` in the callback that logs errors WITHOUT the response body. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Slack OAuth Install (EPIC-005 Phase A)

  Background:
    Given the user is registered and logged in via EPIC-002 auth
    And TEEMO_ENCRYPTION_KEY, SLACK_CLIENT_ID, SLACK_CLIENT_SECRET,
        SLACK_SIGNING_SECRET, SLACK_REDIRECT_URL are set in Coolify
    And the Slack app at api.slack.com has the 7 scopes from ADR-021/025
    And the Event Subscriptions Request URL shows ✅ Verified

  Scenario: Complete Happy Path — first install
    Given the user is on https://teemo.soula.ge/app
    And no teemo_slack_teams row exists for their account
    When they click the "Install Slack" button
    Then they are redirected to slack.com/oauth/v2/authorize
    When they approve the install in Slack
    Then Slack redirects to /api/slack/oauth/callback with code + state
    And the backend exchanges the code via oauth.v2.access
    And a teemo_slack_teams row is written with encrypted_slack_bot_token
    And the user is redirected to /app?slack_install=ok
    And the /app page shows a success banner
    And the team appears in the "Slack Teams" list

  Scenario: Re-install same team (same owner)
    Given the user already has a teemo_slack_teams row for team T1
    When they click "Install Slack" again and complete the OAuth flow for T1
    Then the callback UPSERTS the existing row
    And NO duplicate row is created

  Scenario: User cancels the Slack consent screen
    When they click Cancel
    Then Slack redirects to /api/slack/oauth/callback?error=access_denied
    And the backend redirects to /app?slack_install=cancelled
    And NO teemo_slack_teams row is created

  Scenario: State token tampered with
    When they GET /api/slack/oauth/callback?code=…&state=<forged>
    Then the backend returns 400 "Invalid state"
    And NO Slack API call is made

  Scenario: Slack /api/slack/events rejects unsigned POSTs
    Given an attacker POSTs to /api/slack/events without X-Slack-Signature
    Then the backend returns 401 Unauthorized

  Scenario: Slack /api/slack/events rejects expired timestamp
    Given a POST to /api/slack/events with X-Slack-Request-Timestamp older than 5 minutes
    Then the backend returns 401 Unauthorized (replay defense)

  Scenario: Slack /api/slack/events still handles url_verification (S-03 behavior preserved)
    When Slack POSTs {"type": "url_verification", "challenge": "abc123"} with a valid signature
    Then the backend returns 200 with body "abc123"
```

---

## 8. Open Questions

All 9 open questions (Q1–Q9) decided 2026-04-12. Ambiguity dropped from 🟡 → 🟢. Status moved Draft → Ready.

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [ ] [STORY-005A-01] — Slack Bootstrap (encryption + config + slack.py scaffold) — **L2** — Backlog
- [ ] [STORY-005A-02] — `/api/slack/events` Signing-Secret Verification — **L2** — Backlog
- [ ] [STORY-005A-03] — `GET /api/slack/install` Install URL Builder — **L2** — Backlog
- [ ] [STORY-005A-04] — `GET /api/slack/oauth/callback` Code Exchange + Upsert — **L3** — Backlog
- [ ] [STORY-005A-05] — `GET /api/slack/teams` List Endpoint — **L1** — Backlog
- [ ] [STORY-005A-06] — Frontend `/app` Install UI + Flash Banners — **L2** — Backlog

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Epic drafted after Explorer Context Pack. Ambiguity 🟡 — 9 open questions blocking decomposition. | Team Lead |
| 2026-04-12 | Live simulation against production validated S-03 stub behavior. | Team Lead |
| 2026-04-12 | Q5 decided (Option A) after inspecting `slack-bolt==1.28.0` source. | Team Lead |
| 2026-04-12 | All 8 remaining Open Questions decided. Ambiguity 🟡 → 🟢. Status Draft → Ready. Epic unblocked. | Human |
| 2026-04-12 | Slack AI Apps / Agents surface investigated and explicitly deferred to Phase B. | Team Lead |
| 2026-04-12 | Story decomposition complete. 6 stories created. | Team Lead |
