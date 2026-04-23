---
epic_id: "EPIC-005-phase-a"
status: "Ready"
ambiguity: "🟢 Low"
context_source: "Charter §4, §5.3, §5.5, §6 / Roadmap §2 row 61, §3 ADR-002/010/019/021/024/025/026, §4 row 156 / User Input"
release: "Release 1: Foundation + Deploy + Slack Install"
owner: "Solo dev"
priority: "P0 - Critical"
tags: ["backend", "frontend", "slack", "oauth", "encryption", "security"]
target_date: "2026-04-13"
---

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
- [ ] `backend/app/api/routes/health.py` (or wherever it lives) — the health check already probes `teemo_slack_teams`; verify no change needed and add a regression test for the column-agnostic probe pattern from hotfix `ce7c0b1`.
- [ ] `backend/app/models/slack.py` — Pydantic models: `SlackInstallState`, `SlackOAuthCallbackQuery`, `SlackTeamRow` (response). No request body models (OAuth uses query params only).
- [ ] `frontend/src/routes/app.tsx` — replace the welcome card body with: **"Slack Teams" heading**, **list of installed teams** (from a new `GET /api/slack/teams` endpoint — see Question Q5), **Install Slack button** that navigates to `/api/slack/install` via `<a href>` (not SPA-mediated — the browser must leave the SPA for the OAuth redirect). Show a flash banner on return if `?slack_install=ok` or `?slack_install=cancelled` in the URL.
- [ ] `frontend/src/lib/api.ts` — add `listSlackTeams()` wrapping `GET /api/slack/teams`.
- [ ] Backend tests: signature verification happy + unhappy; state token sign/verify; callback success path (mocked `oauth.v2.access`); callback denial path; callback with bad state; upsert semantics (re-install same team).
- [ ] Frontend tests: `/app` renders Install button when no teams, renders team list when teams present, renders success/cancel banners from query params.
- [ ] **Coolify env vars**: `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_REDIRECT_URL=https://teemo.soula.ge/api/slack/oauth/callback`, `TEEMO_ENCRYPTION_KEY=<32-byte base64>` — DevOps adds these to the Coolify service config before the S-04 release merges.

### ❌ OUT-OF-SCOPE (Do NOT Build This)

- `app_mention` or `message.im` event handlers — **deferred to EPIC-005 Phase B** (after EPIC-007 agent exists).
- Self-message filter logic — Phase B (uses `slack_bot_user_id` stored in Phase A, but the filter itself runs during event handling).
- Workspace CRUD under a team (`GET/POST /api/slack-teams/:id/workspaces`, `/app/teams/$teamId` route, workspace cards) — **deferred to S-05 / EPIC-003 Slice B**.
- Channel binding CRUD, `conversations.list`, channel picker modal — Phase B.
- The unbound-channel nudge handler — Phase B.
- `GET /api/slack/teams/:id/channels` — Phase B.
- Token rotation, uninstall webhook handling, `app_uninstalled` cleanup — **explicitly deferred** (hackathon pragmatism; Charter §6 does not mandate uninstall handling in v1).
- Multi-user per team (the "organization install" flow) — single-user install only. `owner_user_id` is the installing user.
- BYOK key CRUD — EPIC-004 (Release 2). Even though `encryption.py` lands here, we do not pull BYOK key storage in.
- Google Drive OAuth — EPIC-006 (Release 2).
- **Slack Agents & AI Apps surface** (split-view container, `assistant_thread_started`, `assistant.threads.setStatus`, `setSuggestedPrompts`, `chat.startStream`, etc.) — **explicitly deferred to Phase B evaluation.** Investigated 2026-04-12: `slack-bolt==1.28.0` (already pinned) ships `AsyncAssistant` middleware + `AsyncAssistantUtilities` with `set_status`/`set_title`/`set_suggested_prompts`, so the SDK is ready. Slack docs state "some AI features require a paid plan" but **do not name which tier** — the plan-tier gate cannot be resolved from documentation and must be tested in a real workspace. Adding this to Phase A would also force re-installing the dev Slack app to add the `assistant:write` scope, invalidating the currently ✅ Verified Event Subscriptions URL. Decision: **do NOT toggle AI Apps in S-04**; revisit at the start of Phase B planning with a 15-min spike (toggle in app console → reinstall → observe whether the split-view appears in dev workspace), then choose Path X (classical channels+DMs only), Path Y (AI Apps as primary, supersedes ADR-013), or Path Z (additive — classical primary, AI Apps as opportunistic enhancement). Path Z is the likely winner.

---

## 3. Context

### 3.1 User Personas

- **Solo Dev (installer)** — a user who has registered via EPIC-002 and is logged into `/app`. Clicks Install Slack, approves consent in Slack, lands back on `/app` with a visible team. First-and-only user persona for the hackathon demo.
- **(Deferred) Team admin** — in the real world, installing Tee-Mo into a shared Slack workspace requires Slack workspace admin permission. Not relevant to hackathon demo but worth acknowledging in error messages.

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
| **Performance** | OAuth callback must complete in <3s (Slack redirect browser is waiting — user sees blank page). Slack `oauth.v2.access` typical latency ~300ms; encryption + DB write negligible. Not a concern unless Coolify cold-starts. |
| **Security** | (1) Bot token MUST be AES-256-GCM encrypted at rest per ADR-010 — never plaintext, not even in logs. (2) `state` parameter MUST be cryptographically signed (not a random nonce in memory — backend has no shared memory across Coolify restarts). (3) `/api/slack/events` MUST reject requests with missing/invalid/expired Slack signatures. (4) `/api/slack/install` MUST require authentication — anonymous users cannot start an install that will be attributed to another user. (5) `TEEMO_ENCRYPTION_KEY` MUST NOT appear in any log or error message. |
| **Tech Stack** | `slack-bolt==1.28.0` (pinned, already in `pyproject.toml`); `cryptography==46.0.7` (already installed). Must not pull in new Slack libraries. |
| **Cookies** | Auth cookie is `SameSite=Lax` per FLASHCARDS.md 2026-04-11 — this is WHY Lax is required (OAuth redirect hop would drop Strict cookies). If the cookie ever changes to Strict, Phase A breaks. |
| **Redirect URL** | The manifest (Charter-linked `slack-app-setup-guide.md` Step 2) registered `https://teemo.soula.ge/api/slack/oauth/callback`. Backend `redirect_uri` in the authorize URL must match EXACTLY — trailing slash, scheme, host, path. No `localhost` development OAuth until Slack app gets a second redirect URL registered. |

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
| Backend health tests | `backend/tests/test_health.py` (or equivalent) | **MODIFY** (regression for ce7c0b1 column-agnostic probe) |
| Backend tests | `backend/tests/test_slack_oauth.py`, `backend/tests/test_slack_events_signed.py`, `backend/tests/test_encryption.py` | **NEW** |
| Frontend `/app` | `frontend/src/routes/app.tsx` | **MODIFY** (replace welcome card; add team list + Install button + flash banners) |
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
| **Requires** | Slack app registered in api.slack.com with correct scopes, redirect URL, signing secret | Done (user completed `slack-app-setup-guide.md` Steps 1–6 during S-03) |
| **Requires** | Event Subscriptions Request URL ✅ Verified in Slack app console | **Unverified — see Sprint Readiness Gate below** |
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

> Analyze this epic and research the codebase to create small, focused stories. Each story must deliver a tangible, verifiable result — not just a layer of work. **Decomposition is blocked until §8 Open Questions are resolved.**

### Affected Areas (for codebase research)

- [ ] `backend/app/api/routes/slack_events.py:39-73` — S-03 stub, needs signature verification inlined
- [ ] `backend/app/api/routes/auth.py:48-78` — precedent for cookie handling, route structure
- [ ] `backend/app/core/config.py` — pattern for adding env vars + startup validators
- [ ] `backend/app/core/db.py` — `get_supabase()` singleton pattern
- [ ] `backend/app/main.py` — router registration pattern (`app.include_router`)
- [ ] `database/migrations/005_teemo_slack_teams.sql` — exact column names + PK shape
- [ ] `frontend/src/routes/app.tsx` — placeholder to replace
- [ ] `frontend/src/lib/api.ts` — API client pattern (credentials: 'include')
- [ ] `frontend/src/stores/__tests__/authStore.test.ts` — Vitest mock pattern
- [ ] `FLASHCARDS.md` entries: SameSite=Lax (load-bearing for this epic), column-agnostic probe, TanStack Query discipline

### Key Constraints for Story Sizing

- Each story touches 1–3 files with one clear deliverable
- Vertical slices preferred: a story that includes route + model + test beats a "routes layer" + "tests layer" split
- `encryption.py` is an exception: it's a shared primitive, so it gets its own story and is consumed by the OAuth callback story downstream

### Suggested Sequencing Hints (to inform decomposition, NOT prescribe stories)

1. **Foundation first** — `encryption.py` + config vars + `slack.py` Bolt scaffold. Nothing else can land without these.
2. **Events hardening** — signature verification for `/api/slack/events` (replace the TODO). Small, independent, can run in parallel with #1 once config is in place.
3. **Install URL builder** — `GET /api/slack/install` with signed state. Depends on #1.
4. **OAuth callback** — `GET /api/slack/oauth/callback` with code exchange + encrypt + upsert. Depends on #1, #3.
5. **Teams list endpoint** — `GET /api/slack/teams` returning teams owned by the current user. Depends on #4 (to have something to list). Small.
6. **Frontend Install button + teams list** — consumes #5. Depends on #5.
7. **Success/cancel flash banners** — small UX polish on #6.

The natural shape is **6–8 stories**. Final count emerges from decomposition after §8 is resolved.

---

## 6. Risks & Edge Cases

| # | Risk | Likelihood | Mitigation |
|---|------|------------|------------|
| R1 | **Encryption key loss between deploys** — `TEEMO_ENCRYPTION_KEY` rotates or is regenerated. All encrypted bot tokens become unreadable; every installed team must re-install. | Medium | Store key in Coolify env UI (never in repo). Document in deploy runbook: rotating this key invalidates all `encrypted_slack_bot_token` rows. Add a startup log line showing key fingerprint (first 8 chars of SHA-256) so you can spot accidental changes. |
| R2 | **Slack signing secret clock skew** — server clock drifts >5min; every request fails signature verification. | Low | The 5-minute window is standard. Coolify runs `systemd-timesyncd`. Regression test mocks `datetime.now()` to verify the window boundary. |
| R3 | **State parameter replay** — attacker captures a `state` token from a legitimate install, replays it later to hijack the team. | Low | Sign `state` with HMAC-SHA256 using `JWT_SECRET` + add a short `exp` claim (5 minutes). Reject expired state on callback. |
| R4 | **Cross-user team hijacking** — user A installs a team, user B somehow triggers a callback that writes the team against user B's `owner_user_id`. | Low | `state` token includes `user_id`, verified on callback. Auth cookie MUST ALSO match the `user_id` in state — mismatch → 403. |
| R5 | **Re-install with different owner** — user A installed team T1 yesterday, user B installs T1 today. Upsert on `slack_team_id` would silently reassign ownership. | Medium | On callback, if row exists with a different `owner_user_id`, return 409 Conflict with message "This Slack team is already installed under a different account." **Requires Q2 decision.** |
| R6 | **`SLACK_REDIRECT_URL` mismatch** — backend builds authorize URL with trailing slash, Slack app manifest registered without trailing slash (or vice versa). | Medium | Single source of truth: `settings.slack_redirect_url` used both as the string sent to Slack AND as the FastAPI route decorator for the callback (hardcoded exact match). Add a startup log line showing the value. |
| R7 | **OAuth `code` single-use** — if the callback fails mid-exchange and the user retries, the second exchange fails with `invalid_code`. User sees a broken state. | Low | Callback catches `invalid_code` and redirects to `/app?slack_install=expired` with a user-visible "Install session expired, please try again" banner. |
| R8 | **Bot token leaks via error message** — an unhandled exception in the callback surfaces the token in a FastAPI error response. | Low | Catch-all `try/except` in the callback that logs errors WITHOUT the response body + returns a generic 500 redirect. Test: post a corrupted `oauth.v2.access` response and verify no token chars appear in the error payload. |
| R9 | **Coolify cold-start causes callback timeout** — Slack is waiting <3s for redirect; if the VPS cold-starts, Slack may give up. | Low | Coolify keeps the container warm in practice. Mitigation if it bites: pre-warm by hitting `/api/health` before clicking Install. Not worth engineering around. |
| R10 | **Unused `SLACK_VERIFICATION_TOKEN` in `.env`** — legacy deprecated token left over from the setup guide. Could be mistakenly used instead of `SLACK_SIGNING_SECRET`. | Low | Do NOT add `SLACK_VERIFICATION_TOKEN` to `config.py` Settings. Document in a code comment in `slack_events.py` that signing secret is the source of truth, verification token is deprecated. |
| R11 | **Slack app Event Subscriptions Request URL not yet ✅ Verified** — the S-03 stub exists and returns challenges, but the Slack console may still show the URL as unverified if the user hasn't clicked Retry. | Medium | Sprint Readiness Gate item: verify ✅ Verified in the Slack console before S-04 starts. (User prerequisite, not a story.) |
| R12 | **`oauth.v2.access` response shape drift** — Slack changes field names (`bot_user_id` vs `authed_user.id`, etc.). | Low | Pin expectations in a Pydantic response model; test parses a known-good example response verbatim. Fail loudly on drift. |

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
    Then they are redirected to slack.com/oauth/v2/authorize with
      | client_id    | <SLACK_CLIENT_ID> from env                          |
      | scope        | app_mentions:read,channels:history,channels:read,  |
      |              | chat:write,groups:history,groups:read,im:history    |
      | redirect_uri | https://teemo.soula.ge/api/slack/oauth/callback     |
      | state        | signed JWT containing their user_id, exp 5min       |
    When they approve the install in Slack
    Then Slack redirects to /api/slack/oauth/callback with code + state
    And the backend exchanges the code via oauth.v2.access
    And a teemo_slack_teams row is written with:
      | slack_team_id             | the real Slack team.id             |
      | owner_user_id             | the logged-in user's UUID          |
      | slack_bot_user_id         | the real bot_user_id               |
      | encrypted_slack_bot_token | AES-256-GCM ciphertext, non-null   |
    And the user is redirected to /app?slack_install=ok
    And the /app page shows a success banner "Tee-Mo installed to <team name>"
    And the team appears in the "Slack Teams" list

  Scenario: Re-install same team (same owner)
    Given the user already has a teemo_slack_teams row for team T1
    When they click "Install Slack" again and complete the OAuth flow for T1
    Then the callback UPSERTS the existing row (same slack_team_id PK)
    And encrypted_slack_bot_token is replaced with a fresh encrypted value
    And updated_at is refreshed
    And NO duplicate row is created
    And the user sees /app?slack_install=ok

  Scenario: User cancels the Slack consent screen
    Given the user clicks Install Slack and reaches the Slack consent page
    When they click Cancel
    Then Slack redirects to /api/slack/oauth/callback?error=access_denied
    And the backend redirects to /app?slack_install=cancelled
    And the /app page shows a neutral banner "Install cancelled"
    And NO teemo_slack_teams row is created

  Scenario: State token tampered with
    Given a malicious actor crafts a callback URL with an invalid state signature
    When they GET /api/slack/oauth/callback?code=…&state=<forged>
    Then the backend returns 400 "Invalid state"
    And NO Slack API call is made
    And NO teemo_slack_teams row is written

  Scenario: Slack /api/slack/events rejects unsigned POSTs
    Given an attacker POSTs to /api/slack/events without X-Slack-Signature
    Then the backend returns 401 Unauthorized
    And the request body is NOT logged in full

  Scenario: Slack /api/slack/events rejects expired timestamp
    Given a POST to /api/slack/events with X-Slack-Request-Timestamp older than 5 minutes
    Then the backend returns 401 Unauthorized (replay defense)

  Scenario: Slack /api/slack/events still handles url_verification (S-03 behavior preserved)
    When Slack POSTs {"type": "url_verification", "challenge": "abc123"} with a valid signature
    Then the backend returns 200 with body "abc123"
```

---

## 8. Open Questions

> **These are blocking for decomposition.** The Team Lead will present them in chat and wait for human decisions before writing stories.

| # | Question | Options | Impact | Status |
|---|----------|---------|--------|--------|
| Q1 | **How is the OAuth `state` parameter signed?** | A: Reuse `JWT_SECRET` + PyJWT to sign a `{user_id, exp}` claim. B: Introduce a new `SLACK_STATE_SECRET`. C: Random nonce stored in a new `teemo_oauth_states` table with TTL. | A reuses existing `backend/app/core/security.py` helpers — zero new infra, no new migration, one import. | **✅ Decided — Option A** (2026-04-12) |
| Q2 | **What happens on re-install with a DIFFERENT owner?** | A: 409 Conflict with "team already installed under another account". B: Silent upsert — reassign ownership. C: Archive old row, write new row with a new surrogate PK. | A is the safest (prevents accidental hijack, matches charter `1 user : N teams` invariant). B is a security footgun. C breaks the `slack_team_id`-as-PK contract. | **✅ Decided — Option A** (2026-04-12) |
| Q3 | **Is `/api/slack/install` protected by the auth cookie?** | A: Yes — anonymous users get 401. B: No — public endpoint, capture ownership in the callback via cookie instead. | A lets us bake `user_id` into the `state` at install time (Q1 depends on this). B creates a cross-user race on the callback. | **✅ Decided — Option A** (2026-04-12) |
| Q4 | **Where does `TEEMO_ENCRYPTION_KEY` come from?** | A: New Coolify env var, 32-byte urlsafe base64, generated with `secrets.token_urlsafe(32)` locally and pasted into Coolify. B: Derived from `JWT_SECRET` via HKDF. C: Stored in a new `teemo_secrets` table. | A is simplest and matches Charter §3.3 "copy-then-optimize" posture. B is key reuse (explicitly bad per ADR-002 rationale). C creates chicken-and-egg. | **✅ Decided — Option A** (2026-04-12) |
| Q5 | **Where does the bot_user_id come from — `oauth.v2.access` response or a second `auth.test` call?** | A: Read `bot_user_id` from the `oauth.v2.access` response directly. B: Call `auth.test` as a second step. | **DECIDED (A) via empirical check 2026-04-12:** slack-bolt source `slack_bolt/oauth/oauth_flow.py:344` and `async_oauth_flow.py:346` both extract `bot_user_id=oauth_response.get("bot_user_id")` — it's a documented top-level field on `oauth.v2.access`. Defensively handle `None` with a 500 error "Slack OAuth response missing bot_user_id — please retry install", but do NOT make a second call. | **✅ Decided — Option A** |
| Q6 | **Does the `/app` list of installed teams need a new `GET /api/slack/teams` endpoint in Phase A, or does that belong in S-05 Slice B?** | A: Build in Phase A. B: Static banner only, defer list to S-05. | A keeps `/app` consistent across refreshes. B leaves a visual regression between install and refresh. | **✅ Decided — Option A** (2026-04-12) |
| Q7 | **Frontend Install button: `<a href>` direct link, or SPA-mediated fetch + `window.location.href`?** | A: `<a href="/api/slack/install">`. B: `onClick` → fetch → `window.location.href`. | A is simpler — backend returns 307 and browser follows automatically. B adds complexity for no benefit. | **✅ Decided — Option A** (2026-04-12) |
| Q8 | **Do we test the OAuth callback with a mocked Slack API or a real sandbox call?** | A: Hand-rolled mock of `httpx.AsyncClient.post` responses for `oauth.v2.access`. B: Record a real Slack response as fixture. C: Actually call Slack in tests. | A is hackathon-appropriate, no new dep. Use the canonical response shape from slack-bolt source. | **✅ Decided — Option A** (2026-04-12) |
| Q9 | **Is the signing-secret hardening of `/api/slack/events` its own story, or folded into the events stub story that S-03 already closed?** | A: Own story. B: Folded into the callback story. | A is cleaner V-Bounce accounting — already have known-good test vectors from today's simulation. Independently verifiable. | **✅ Decided — Option A** (2026-04-12) |

---

## 9. Artifact Links

> Auto-populated after §8 is resolved and stories are decomposed.

**Stories (Status Tracking):**
- [ ] [STORY-005A-01](./STORY-005A-01-slack-bootstrap.md) — Slack Bootstrap (encryption + config + slack.py scaffold) — **L2** — Backlog
- [ ] [STORY-005A-02](./STORY-005A-02-events-signing-verification.md) — `/api/slack/events` Signing-Secret Verification — **L2** — Backlog
- [ ] [STORY-005A-03](./STORY-005A-03-install-url-builder.md) — `GET /api/slack/install` Install URL Builder — **L2** — Backlog
- [ ] [STORY-005A-04](./STORY-005A-04-oauth-callback-upsert.md) — `GET /api/slack/oauth/callback` Code Exchange + Upsert — **L3** — Backlog
- [ ] [STORY-005A-05](./STORY-005A-05-teams-list-endpoint.md) — `GET /api/slack/teams` List Endpoint — **L1** — Backlog
- [ ] [STORY-005A-06](./STORY-005A-06-frontend-install-ui.md) — Frontend `/app` Install UI + Flash Banners — **L2** — Backlog

**Story sequencing (no parallelism — strict chain):**
1. STORY-005A-01 (foundation) → unblocks 02, 03
2. STORY-005A-02 (events hardening) AND STORY-005A-03 (install URL) can run in parallel after 01
3. STORY-005A-04 (callback) needs 01 + 03
4. STORY-005A-05 (teams list) needs 04 (so the list has rows to read in tests; also model file from 03)
5. STORY-005A-06 (frontend) needs 05

**Total complexity mix:** 1× L1, 4× L2, 1× L3 = 6 stories (matches the team's S-03 6-story rhythm with 0 bounces).

**References:**
- Charter: `product_plans/strategy/tee_mo_charter.md` §4 (Data Model), §5.3 (Setup Flow Phase A), §5.5 (Channel Binding — context), §6 (Constraints)
- Roadmap: `product_plans/strategy/tee_mo_roadmap.md` §2 row 61 (Phase A scope), §3 ADR-002/010/019/021/024/025/026, §4 row 156 (dependency chain)
- Slack app setup runbook: `product_plans/backlog/EPIC-005_slack_integration/slack-app-setup-guide.md`
- S-03 events stub: `backend/app/api/routes/slack_events.py:39-73`
- Schema: `database/migrations/005_teemo_slack_teams.sql`
- FLASHCARDS: SameSite=Lax (2026-04-11), column-agnostic probe (2026-04-12), Frontend TanStack Query discipline (2026-04-11)

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Epic drafted after Explorer Context Pack. Ambiguity 🟡 — 9 open questions blocking decomposition. | Team Lead |
| 2026-04-12 | **Live simulation against production** `POST /api/slack/events` validated S-03 stub behavior: unsigned POST → 200 + plain-text challenge echo; signed POST (real HMAC-SHA256 using `.env` `SLACK_SIGNING_SECRET`) → 200 identical behavior (stub does not yet check signatures — matches `TODO(S-04)`); signed `app_mention` event → 202 empty body. Confirms: (a) prod signing secret matches `.env`, (b) signing basestring format `v0:{ts}:{body}` works round-trip, (c) stub is ready to be hardened. Built canonical authorize URL for eyeball verification (manifest-matched scopes + redirect URI). | Team Lead |
| 2026-04-12 | Q5 **decided (Option A)** after inspecting `slack-bolt==1.28.0` source in `backend/.venv` — `bot_user_id` is extracted directly from `oauth.v2.access` top-level field at `slack_bolt/oauth/oauth_flow.py:344`. No `auth.test` round-trip needed. | Team Lead |
| 2026-04-12 | All 8 remaining Open Questions (Q1, Q2, Q3, Q4, Q6, Q7, Q8, Q9) **decided per Team Lead recommendations**. Ambiguity dropped from 🟡 → 🟢. Status moved Draft → Ready. Epic unblocked for story decomposition. | Human |
| 2026-04-12 | **Slack AI Apps / Agents surface** investigated and **explicitly deferred to Phase B**. Findings added to §2 OUT-OF-SCOPE: `slack-bolt 1.28.0` already ships `AsyncAssistant` middleware (no dep bump needed), but plan-tier gate is undocumented and `assistant:write` scope addition would force a Slack app re-install during S-04 — too much churn for Phase A. Phase B will run a 15-min spike to test the surface in dev workspace and choose Path X/Y/Z. | Team Lead |
| 2026-04-12 | High-level draft created for the AI Apps initiative as `EPIC-011: Slack Agents & AI Apps Surface` at `product_plans/backlog/EPIC-011_slack_ai_apps/EPIC-011_slack_ai_apps_surface.md`. Status Draft, ambiguity 🔴, priority P2, release TBD. Decomposition blocked on Phase B spike. | Team Lead |
| 2026-04-12 | **Story decomposition complete.** 6 stories created in this folder: 005A-01 (bootstrap, L2), 005A-02 (events signing, L2), 005A-03 (install URL, L2), 005A-04 (callback, L3), 005A-05 (teams list, L1), 005A-06 (frontend UI, L2). Sequencing chain documented in §9. Epic ready for sprint planning — say "plan sprint 4" to fold these into `product_plans/sprints/sprint-04/`. | Team Lead |
