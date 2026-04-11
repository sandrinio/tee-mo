---
story_id: "STORY-003-02-coolify-wiring"
parent_epic_ref: "ADR-026 (Deploy Infrastructure)"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Roadmap §3 ADR-019/ADR-026; User-confirmed Coolify setup (DNS ready, GitHub auto-deploy, env vars via UI); STORY-003-01 Dockerfile output"
actor: "DevOps agent (writes runbook) + Solo dev (executes Coolify UI clicks)"
complexity_label: "L2"
---

# STORY-003-02: Coolify Wiring + First Auto-Deploy

**Complexity: L2** — Runbook document + user-executed Coolify UI configuration + verification. ~1 hour straddling DevOps agent and user.

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

STORY-003-01 ships the Dockerfile but nothing yet deploys. This story is the first push-to-main → Coolify-auto-deploy cycle. It straddles the agent/user boundary: DevOps agent prepares a precise runbook and verifies the deploy once it's live; the user executes the Coolify web UI steps (service config, env vars, domain binding).

### 1.2 Detailed Requirements

- **R1 — Runbook doc**: Create `product_plans/sprints/sprint-03/coolify-setup-steps.md` — a step-by-step guide the user follows in the Coolify web UI. Covers: create service from GitHub repo, set Dockerfile build context, bind `teemo.soula.ge` domain, paste env vars, configure healthcheck, trigger first build.
- **R2 — Env var list**: The runbook must contain the **exact** env var list to paste into Coolify, with values the user can copy from their local `.env` (or blank placeholders for Slack secrets they haven't created yet).
- **R3 — Healthcheck**: Coolify healthcheck configured to `GET /api/health` expecting 200. Confirms post-deploy the backend is responsive.
- **R4 — HTTPS verification**: Once deploy is green, `https://teemo.soula.ge/api/health` must return 200 with all 4 (pre-migration) `teemo_*` tables `"ok"`. Migration 005/006/007 haven't landed yet — that's STORY-003-03. This story verifies the S-02 baseline is reachable from prod.
- **R5 — Frontend verification**: `https://teemo.soula.ge/` must render the Tee-Mo landing page. `https://teemo.soula.ge/login` and `https://teemo.soula.ge/register` must render (SPA fallback working). User can register a test account in prod and see the `/app` placeholder.
- **R6 — CORS verification**: A fetch from `https://teemo.soula.ge/` to `https://teemo.soula.ge/api/health` must succeed (same-origin so no CORS issue), AND a fetch with `credentials: 'include'` must also succeed. The S-02 auth cookie round-trip must work in prod.
- **R7 — Cookie verification**: Register a fresh user in prod, verify DevTools → Application → Cookies shows `access_token` and `refresh_token` with `Secure=true`, `HttpOnly=true`, `SameSite=Lax`. `Secure=true` is the key difference from dev — it's enforced because `DEBUG=false` in prod env.
- **R8 — Commit the runbook** to the sprint branch so it ships in the merge to main. Useful for future sprints that need to re-configure Coolify.

### 1.3 Out of Scope

- Multi-region / staging environments.
- CI/CD test-before-deploy pipeline — Coolify auto-deploy on push is the whole pipeline.
- Rollback procedures (future concern).
- Monitoring / alerting / logs aggregation — Coolify built-in container logs are enough for the hackathon.
- Custom domain verification beyond `teemo.soula.ge` (no `www.` or alt domains).

### TDD Red Phase: No

Rationale: This story is configuration + verification, not code. No unit tests possible.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: First Coolify auto-deploy of Tee-Mo

  Scenario: Runbook exists and is committable
    Given STORY-003-01 has merged (Dockerfile + .dockerignore on main)
    When I create product_plans/sprints/sprint-03/coolify-setup-steps.md
    Then the runbook contains step-by-step Coolify UI instructions
    And the runbook contains the exact env var list with values or placeholders
    And the runbook contains the rollback procedure (revert to prior commit + redeploy)

  Scenario: Coolify auto-deploy completes after first push
    Given the user has configured the Coolify service per the runbook
    When the user (or CI) pushes a commit to origin/main that includes the Dockerfile
    Then Coolify detects the push within 60 seconds
    And Coolify builds the Docker image
    And Coolify deploys the container
    And the Coolify healthcheck GET /api/health returns 200 within 90 seconds of deploy start

  Scenario: Production health endpoint returns 4 teemo_* tables ok
    Given the first auto-deploy has succeeded
    When I curl https://teemo.soula.ge/api/health
    Then the response status is 200
    And the response JSON has status = "ok"
    And the response JSON database has exactly 4 teemo_* keys (teemo_users, teemo_workspaces, teemo_knowledge_index, teemo_skills)
    And every database value is "ok"

  Scenario: Frontend landing page served over HTTPS
    Given the deploy is live
    When I visit https://teemo.soula.ge/ in a browser
    Then the page renders the Tee-Mo landing with "Backend: ok" badge
    And the browser shows a valid TLS certificate (no warnings)

  Scenario: SPA routes work in production
    Given the deploy is live
    When I visit https://teemo.soula.ge/login directly (no client-side navigation)
    Then the login form renders
    And the URL in the address bar is still /login

  Scenario: Auth flow works end-to-end in production
    Given the deploy is live and no user exists with the test email
    When I register test+{timestamp}@example.com with password "correcthorse"
    Then the response is 201
    And the browser receives access_token + refresh_token cookies with Secure=true, HttpOnly=true, SameSite=Lax
    And I am redirected to /app
    And /app shows "Signed in as test+{timestamp}@example.com"

  Scenario: CORS + credentials work in prod
    Given the deploy is live
    When the browser on https://teemo.soula.ge/ fetches https://teemo.soula.ge/api/auth/me with credentials: include
    Then the response is 200 or 401 (not a CORS error)
```

### 2.2 Verification Steps (Manual)

Dev agent cannot click buttons in Coolify UI. This section is a split between what the agent can do and what the user does.

**User does (in the Coolify web UI + a browser):**
- [ ] Follow every step in `product_plans/sprints/sprint-03/coolify-setup-steps.md`
- [ ] Paste the env var list into the Coolify env var UI
- [ ] Bind the `teemo.soula.ge` domain to the Tee-Mo service
- [ ] Trigger the first build (will happen automatically on first push-to-main after the service is configured)
- [ ] Confirm the healthcheck is green in the Coolify UI
- [ ] Visit `https://teemo.soula.ge/` in a fresh incognito browser — landing page renders
- [ ] Register a test account and verify cookies in DevTools → Application

**Dev agent (DevOps) does (curl from the command line, after user signals deploy is live):**
- [ ] `curl -sI https://teemo.soula.ge/api/health` returns `200`
- [ ] `curl -s https://teemo.soula.ge/api/health | jq '.database | keys | length'` returns `4`
- [ ] `curl -s https://teemo.soula.ge/api/health | jq '.status'` returns `"ok"`
- [ ] `curl -sI https://teemo.soula.ge/` returns `200` and `content-type: text/html`
- [ ] `curl -sI https://teemo.soula.ge/login` returns `200` and `content-type: text/html`
- [ ] `curl -s https://teemo.soula.ge/api/slack/events` returns `404` (endpoint not yet created — STORY-003-05 will add it)
- [ ] Verify TLS cert via `curl -vI https://teemo.soula.ge/ 2>&1 | grep 'SSL certificate verify ok'`

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-003-01** | Dockerfile + .dockerignore + main.py StaticFiles edit merged to `sprint/S-03` | [ ] |
| **DNS** | `teemo.soula.ge` points at Coolify VPS (user confirmed 2026-04-12) | [x] |
| **Coolify** | Coolify instance running, GitHub integration installed, sandrinio/tee-mo linked | [x] |
| **GitHub** | Repo is public (user confirmed) — Coolify can pull without tokens | [x] |
| **Env vars** | All values exist in local `.env` ready to paste | [x] |

### 3.1 Runbook to Write

Create `product_plans/sprints/sprint-03/coolify-setup-steps.md` with the following structure:

#### Structure

1. **Prerequisites check** — user confirms DNS, GitHub repo, Coolify access
2. **Create Coolify service** — Add Resource → Application → GitHub → sandrinio/tee-mo → Dockerfile build → port 8000
3. **Configure build** — Build pack: Dockerfile, Docker build context: `/` (repo root), base directory: `/`
4. **Add environment variables** — paste the full list (see §3.2 below)
5. **Configure domain** — Domains tab → add `teemo.soula.ge`, Coolify auto-provisions Let's Encrypt cert via Traefik
6. **Configure healthcheck** — Healthchecks tab → GET /api/health, expect 200, interval 30s, timeout 10s, retries 3
7. **First deploy** — either auto-triggered by the next push to main, or manually triggered by "Redeploy" button
8. **Post-deploy verification** — the 7 curl commands from §2.2 plus the browser register test
9. **Troubleshooting** — common failure modes (build timeout, healthcheck fails, 502 from Traefik, env var missing)
10. **Rollback** — how to revert: push the revert commit to main, Coolify auto-deploys the previous state

### 3.2 Environment Variable List (the exact values to paste into Coolify)

```bash
# Supabase — same values as local .env
SUPABASE_URL=https://sulabase.soula.ge
SUPABASE_ANON_KEY=<copy from local .env>
SUPABASE_SERVICE_ROLE_KEY=<copy from local .env>
SUPABASE_JWT_SECRET=<copy from local .env>

# Production flags
DEBUG=false
CORS_ORIGINS=https://teemo.soula.ge

# Google OAuth (user already has these in local .env — not consumed until EPIC-006)
GOOGLE_API_CLIENT_ID=<copy from local .env>
GOOGLE_API_SECRET=<copy from local .env>

# Slack app credentials — user adds AFTER completing Slack setup guide Steps 1-3
# Empty strings are OK for now — S-03 code does not consume them
# (EPIC-005 Phase A in S-04 is the consumer)
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
```

**Critical differences from local `.env`:**
- `DEBUG=false` — production does NOT enable dev-only endpoints
- `CORS_ORIGINS=https://teemo.soula.ge` — NOT `http://localhost:5173`

### 3.3 Post-Deploy Verification (Dev agent tasks)

Once the user signals "Coolify reports green", the Dev agent runs:

```bash
# Should return 200 + 4-table JSON
curl -s https://teemo.soula.ge/api/health | jq .

# Should return HTML containing "Tee-Mo"
curl -s https://teemo.soula.ge/ | head -20

# Should return the same HTML (SPA fallback)
curl -s https://teemo.soula.ge/login | head -20

# TLS verification
curl -vI https://teemo.soula.ge/ 2>&1 | grep -E 'SSL|certificate|HTTP/'
```

Paste all outputs into the Dev report.

### 3.4 Files to Modify

| File | Change Type |
|------|-------------|
| `product_plans/sprints/sprint-03/coolify-setup-steps.md` | **NEW** (the runbook) |

**No backend or frontend code changes.** STORY-003-01 already shipped the Dockerfile. This story only writes the runbook and verifies the deploy via curl.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (no code) | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — covered by manual curl + browser verification in §2.2 | |
| Integration tests | 0 — Coolify deploy IS the integration test | |

### 4.2 Definition of Done

- [ ] `coolify-setup-steps.md` exists and covers all 10 structure points from §3.1
- [ ] User has completed the runbook end-to-end in the Coolify UI
- [ ] User reports "Coolify healthcheck is green"
- [ ] All 7 Gherkin scenarios in §2.1 verified (user for browser-based, Dev agent for curl-based)
- [ ] `curl https://teemo.soula.ge/api/health` returns 200 with 4 `teemo_*` tables all `"ok"` (still at 4 — migrations land in STORY-003-03)
- [ ] `https://teemo.soula.ge/` renders the landing page
- [ ] Register flow works in prod with `Secure=true` cookies verified in DevTools
- [ ] Dev report includes the curl output pastes
- [ ] No changes to any code file — only the runbook `.md`

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
