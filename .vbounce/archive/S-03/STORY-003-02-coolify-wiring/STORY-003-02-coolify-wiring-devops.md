---
story_id: "STORY-003-02-coolify-wiring"
agent: "devops"
phase: "single-pass"
bounce: 1
started_at: "2026-04-11T00:00:00Z"
completed_at: "2026-04-11T00:30:00Z"
files_modified:
  - "product_plans/sprints/sprint-03/coolify-setup-steps.md"
tests_written: 0
tests_passing: 32
tests_failing: 0
correction_tax_pct: 0
deploy_verification_deferred_to: "STORY-003-06 (sprint close)"
runbook_complete: true
user_action_required: true
flashcards_flagged: []
input_tokens: 3383
output_tokens: 886
total_tokens: 4269
---

# DevOps Report: STORY-003-02-coolify-wiring

## Summary

This story delivers the Coolify setup runbook at `product_plans/sprints/sprint-03/coolify-setup-steps.md` — a 200+ line step-by-step guide the user follows in the Coolify web UI to create the Tee-Mo service, paste production env vars, bind the `teemo.soula.ge` domain, and configure the healthcheck. Live deploy verification (`https://teemo.soula.ge/api/health` returning 200) is deferred to STORY-003-06 at sprint close. The runbook is committed to `story/STORY-003-02-coolify-wiring` and ready to merge.

## Files Modified

| File | Type | Notes |
|---|---|---|
| `product_plans/sprints/sprint-03/coolify-setup-steps.md` | NEW | Full Coolify setup runbook, 318 lines |

No code files were touched. This story is runbook-only per task spec and ADR-026 scope clarification.

## Scope Clarification

The original story spec §1.2 R4–R7 expected a live `https://teemo.soula.ge` endpoint verifiable during this story. That requirement is **deferred to STORY-003-06** for the following reasons:

1. STORY-003-01 merged the Dockerfile into `sprint/S-03`, not into `origin/main`. The `main` branch has no Dockerfile.
2. Coolify auto-deploys from `origin/main`. Every deploy attempt from `main` currently fails with "no Dockerfile found". This is expected and not a defect.
3. The Dockerfile reaches `main` only when STORY-003-06 executes the sprint-close merge (`sprint/S-03` → `main`). At that point, Coolify detects the push, builds successfully, and deploys the container.
4. STORY-003-06 owns the full curl-based verification (health endpoint, SPA fallback, TLS, auth cookies).

The runbook includes an Option B path for users who want mid-sprint verification by pointing Coolify at `sprint/S-03` temporarily. `sprint/S-03` has been pushed to `origin/sprint/S-03` by the Team Lead and is visible in Coolify's branch picker.

## Runbook Summary

| Section | Content |
|---|---|
| Preamble | What/who/when/prerequisites; explicit statement that first success is at sprint close |
| Step 1 — Create service | Coolify UI path, GitHub repo selection, Dockerfile build pack, port 8000, Option A/B branch choice |
| Step 2 — Env vars | Exact paste list (11 variables); critical prod-vs-dev differences table (DEBUG, CORS_ORIGINS); Slack empty-string rationale |
| Step 3 — Domain binding | `teemo.soula.ge`, Traefik auto-TLS, cert provisioning timing expectations |
| Step 4 — Healthcheck | GET /api/health, 200, 30s interval, 10s timeout, 3 retries, 60s start period |
| Step 5 — Option A deploy | Expected failure explanation; when first success fires; what to report back |
| Step 5b — Option B preview | Branch switch instructions; verification curl commands; CRITICAL sprint-close branch-switch reminder |
| Step 6 — Troubleshooting | 7 failure modes with concrete fixes (missing Dockerfile, npm cache, gcc, 502, healthcheck, TLS, CORS, degraded health) |
| Step 7 — Rollback | Three options: push revert commit, Coolify "Deploy previous", emergency stop |

## User Action Required

**You need to do the following in the Coolify web UI:**

1. Read `/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-003-02-coolify-wiring/product_plans/sprints/sprint-03/coolify-setup-steps.md` (or the same file at `product_plans/sprints/sprint-03/coolify-setup-steps.md` in the repo).
2. Follow **Steps 1 through 4** in the Coolify web UI:
   - Step 1: Create the application service from `github.com/sandrinio/tee-mo`
   - Step 2: Paste the 11 environment variables (values from your local `.env`)
   - Step 3: Bind the domain `teemo.soula.ge`
   - Step 4: Configure the healthcheck (GET /api/health, 60s start period)
3. Choose your verification path:
   - **Option A (default):** Select branch `main` in Coolify. The first deploy will fail (no Dockerfile on main yet). This is expected. First success fires at sprint close.
   - **Option B (optional preview):** Select branch `sprint/S-03` in Coolify. `sprint/S-03` is live on `origin/sprint/S-03` and visible in Coolify's branch picker. Deploy will succeed now. You MUST switch back to `main` at sprint close before STORY-003-06 runs.
4. Report back to the Team Lead: "Coolify service configured; I chose Option [A | B]; current deploy state: [failed as expected on main | succeeded on sprint/S-03 | in progress]."

## Concerns

- **Option B branch-switch risk:** If the user chooses Option B and forgets to switch Coolify back to `main` at sprint close, Coolify will stop auto-deploying after `sprint/S-03` is deleted. This is documented prominently in Step 5b with a CRITICAL callout.
- **TLS cert window:** Coolify may take 30–90 seconds to provision the Let's Encrypt cert after the first successful deploy. Browsers will show a TLS warning during this window. STORY-003-06 verification should wait for cert provisioning to complete before asserting TLS.
- **No Slack env vars yet:** `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, and `SLACK_SIGNING_SECRET` are empty in the Coolify config. The Slack Bolt scaffold must handle missing credentials at startup without crashing (verify in STORY-003-05).

## Process Feedback

- The task file's exact commit message (including Co-Authored-By line) was ready to copy verbatim — this is the right pattern for DevOps agent tasks. No guesswork on message format.
- Token counter script worked cleanly on first attempt from the worktree root.
- None.
