---
story_id: "STORY-003-06-deploy-verification"
parent_epic_ref: "ADR-026 (Deploy Infrastructure)"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1 manual"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-03/STORY-003-06-deploy-verification.md`. Shipped in sprint S-03, carried forward during ClearGate migration 2026-04-24.

# STORY-003-06: Production Deploy Verification + Slack Setup Unblock

**Complexity: L1 manual** — Aggregate verification story. No new code. ~15 minutes (split between DevOps curl checks and user browser/Slack clicks).

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

All prior S-03 stories have been merged to `sprint/S-03`. Coolify auto-deploys every push to `main`, so once DevOps merges `sprint/S-03` → `main`, the production URL reflects the full S-03 state: 6-table schema, PyJWT fix, Slack events stub endpoint. This story is the sprint-level verification gate — it confirms every S-03 artifact works in production AND unblocks the user to finish Slack app setup guide Steps 5–7 (verify Request URL in api.slack.com).

### 1.2 Detailed Requirements

- **R1 — DevOps curl verification** of all S-03 production artifacts:
  - `https://teemo.soula.ge/api/health` returns 6 `teemo_*` tables, all `"ok"`
  - `https://teemo.soula.ge/api/slack/events` responds to a simulated `url_verification` challenge with the challenge string
  - `https://teemo.soula.ge/` serves the landing page
  - `https://teemo.soula.ge/login` and `/register` render via SPA fallback
  - Existing S-02 auth flow still works (register a fresh test user in prod)
- **R2 — Backend test suite stability**: run the full backend test suite 10 consecutive times locally with `pytest-randomly` active. All 10 runs must pass. Confirms STORY-003-04 PyJWT fix holds.
- **R3 — User action 1 — Slack app setup guide Step 5**: Go to api.slack.com → Tee-Mo app → Event Subscriptions tab → retry URL verification (or toggle Enable Events off/on). Slack POSTs a fresh `url_verification` to `https://teemo.soula.ge/api/slack/events`; the backend responds correctly; Slack shows "Verified ✓" badge. User reports "Slack Events URL verified" back to Dev.
- **R4 — User action 2 — Slack app setup guide Steps 6 and 7**: Install app to user's dev Slack workspace (will succeed on the Slack side even though the callback at `/api/slack/oauth/callback` returns 404 — that's expected until S-04 ships Phase A). Optionally invite the bot to a test channel.
- **R5 — Dev agent updates BUG-20260411 status in the Dev report** confirming the fix is live in prod and the 10-run stability test passed.
- **R6 — Dev report lists all verified artifacts** with the curl output pastes and the user's confirmation of Slack setup completion.

### 1.3 Out of Scope

- Any code changes (this is a pure verification story).
- Real Slack OAuth install flow — deferred to S-04 Phase A (the callback endpoint doesn't exist yet).
- Real Slack event handlers — deferred to EPIC-005 Phase B.
- End-to-end browser walkthrough of `/login` → `/register` → `/app` — S-02 regression; covered by R1 spot-check only.
- Sprint Report writing — that's the sprint-close work after this story merges.

### TDD Red Phase: No

Rationale: Verification story. No new code, no new tests.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Sprint S-03 production deploy verification

  Scenario: Production health endpoint reports all 6 teemo_* tables
    Given sprint/S-03 has been merged to main and Coolify auto-deploy has completed
    When I curl https://teemo.soula.ge/api/health
    Then the response status is 200
    And the response JSON database has 6 keys (teemo_users, teemo_workspaces, teemo_knowledge_index, teemo_skills, teemo_slack_teams, teemo_workspace_channels)
    And every database value is "ok"
    And the top-level status is "ok"

  Scenario: Production Slack events stub handles url_verification
    Given the deploy includes STORY-003-05
    When I curl -X POST https://teemo.soula.ge/api/slack/events -H 'Content-Type: application/json' -d '{"type":"url_verification","challenge":"prodtest"}'
    Then the response status is 200
    And the response body is exactly "prodtest"
    And the response content-type is text/plain

  Scenario: Production landing + auth routes still work
    Given the deploy is live
    When I visit https://teemo.soula.ge/
    Then the landing page renders with backend health badge
    When I visit https://teemo.soula.ge/login
    Then the login form renders
    When I register test+{timestamp}@example.com with correcthorse
    Then I land on /app with cookies set

  Scenario: Backend test suite passes 10 consecutive runs
    Given the S-03 code is merged
    When I run `pytest tests/` 10 times with pytest-randomly active
    Then every run passes 100%

  Scenario: Slack app Event Subscriptions URL verified
    Given the user is in api.slack.com on the Tee-Mo app Event Subscriptions tab
    When the user retries the Request URL verification
    Then Slack shows "Verified ✓" next to https://teemo.soula.ge/api/slack/events
    And the user reports this back to the Dev agent
```

### 2.2 Verification Steps (Manual)

**DevOps agent (from command line):**

- [ ] After DevOps merges `sprint/S-03` → `main`, wait ~60s for Coolify auto-deploy
- [ ] `curl -s https://teemo.soula.ge/api/health | jq .` shows 6-table database map, all `"ok"`, top-level `"ok"`
- [ ] `curl -s -X POST https://teemo.soula.ge/api/slack/events -H 'Content-Type: application/json' -d '{"type":"url_verification","challenge":"s03verify"}'` returns `s03verify`
- [ ] `curl -sI https://teemo.soula.ge/` returns `200 OK` with `content-type: text/html`
- [ ] `curl -sI https://teemo.soula.ge/login` returns `200 OK` with `content-type: text/html`
- [ ] 10-run stability loop (see STORY-003-04 §3.3) passes
- [ ] Paste all curl outputs and the 10-run summary into the Dev report

**User (browser + api.slack.com):**

- [ ] Visit `https://teemo.soula.ge/` in a fresh incognito tab → see landing page with green backend badge listing 6 tables
- [ ] Register a test user → lands on `/app` with cookies
- [ ] Sign out → lands on `/login`
- [ ] (Optional regression) Log back in → `/app` state persists
- [ ] Go to https://api.slack.com/apps → Tee-Mo → Event Subscriptions → click "Retry" on the Request URL → wait for "Verified ✓" badge
- [ ] Report to Dev agent: "Slack Events Request URL verified at https://teemo.soula.ge/api/slack/events"
- [ ] (Optional) Install app to dev Slack workspace → OAuth callback will 404 (expected) but install is recorded on Slack side
- [ ] (Optional) Invite bot to a test channel via `/invite @Tee-Mo` — succeeds because install recorded

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **All prior S-03 stories merged** | STORY-003-01 through 003-05 in `sprint/S-03` | [ ] |
| **DevOps merge** | `main` ← `sprint/S-03` done BEFORE this story runs verification | [ ] |
| **Coolify auto-deploy** | Latest push has been deployed (user confirms or waits 60s) | [ ] |
| **SQL migrations already applied** | User ran 005/006/007 per STORY-003-03 | [ ] |

### 3.1 Files to Modify

**None.** This story is pure verification. The only "artifact" it produces is the Dev report.

Possible exception: if any verification step finds a defect, this story creates a fix-up commit. In that case, the Dev agent SHOULD fix the defect in-line as part of this story rather than escalate (the defects would be trivial regressions from the prior 5 stories). Document any fix in the Dev report.

### 3.2 Execution order

1. Dev agent confirms all prior S-03 stories are merged to `sprint/S-03`.
2. Hands off to DevOps agent to merge `sprint/S-03` → `main` with `--no-ff`. Push to origin.
3. DevOps waits for Coolify auto-deploy (~60s–2min).
4. Dev agent runs the curl verification suite (§2.2 DevOps section).
5. Dev agent runs the 10-run pytest stability loop locally.
6. Dev agent notifies user: "Deploy verified on prod. Please complete Slack setup guide Steps 5–7 and confirm back."
7. User runs the browser + api.slack.com verification steps.
8. User reports back.
9. Dev agent writes the final Dev report with all outputs + user confirmation pasted in.
10. This story is marked Done. Sprint ready for close (Sprint Report + release merge + tag `v0.3.0-deploy`).

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (verification story) | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — manual verification is the gate | |
| Integration tests | 0 — N/A | |

### 4.2 Definition of Done

- [ ] All 5 prior S-03 stories merged to `sprint/S-03`
- [ ] `main` ← `sprint/S-03` merge complete (via DevOps agent)
- [ ] Coolify auto-deploy completed successfully
- [ ] `https://teemo.soula.ge/api/health` returns 6 tables all `"ok"`
- [ ] `https://teemo.soula.ge/api/slack/events` verifies round-trip with curl
- [ ] `https://teemo.soula.ge/` and `/login` and `/register` all serve
- [ ] S-02 auth flow regression: register test user → `/app` → sign out → `/login`
- [ ] 10-run `pytest-randomly` stability loop passes locally
- [ ] User completes Slack app setup guide Step 5 (Request URL verified)
- [ ] User reports confirmation back to Dev agent
- [ ] Dev report includes all curl outputs + stability loop summary + user confirmation quote
- [ ] No defects found OR any defects fixed in-line with documented reason

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
