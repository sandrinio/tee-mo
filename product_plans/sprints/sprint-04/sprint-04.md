---
sprint_id: "sprint-04"
sprint_goal: "Real Slack OAuth install — a logged-in user clicks Install Slack on /app, completes the consent flow, and lands back on /app with a teemo_slack_teams row owned by them and visible in the team list. Closes the S-03 events stub TODO with real signing-secret verification."
dates: "2026-04-12 → 2026-04-13"
status: "Active"
delivery: "Release 1 (~85% → ~92% delivered after S-04; S-05 closes Release 1)"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-12"
---

# Sprint S-04 Plan

> **Single-source-of-truth during execution.** All story V-Bounce state changes update this file. The Roadmap is FROZEN once status flips to Active.

## 0. Sprint Readiness Gate

> This sprint CANNOT start until the human confirms this plan AND all checklist items are checked.
> AI sets status to "Planning" when drafting. Human confirmation moves it to "Confirmed". Execution moves it to "Active".

### Pre-Sprint Checklist
- [x] All 6 stories below are decomposed and have full §1/§2/§3 sections (verified during decomposition 2026-04-12)
- [x] Open questions (§3) are resolved or non-blocking (Phase A epic Q1–Q9 all Decided 2026-04-12)
- [x] No stories have 🔴 High ambiguity — all 6 are 🟢 Low
- [x] Dependencies identified and sequencing agreed (see §2 Dependency Chain)
- [x] Risk flags reviewed from Phase A epic §6 (R1–R12 documented; R5 closed by Q2 decision; R11 listed below as a human prereq)
- [x] **HUMAN PREREQ 1 — Slack Event Subscriptions Request URL ✅ Verified.** User confirmed 2026-04-12 that Slack app console → Event Subscriptions shows ✅ Verified. STORY-005A-02 cleared for production QA.
- [x] **HUMAN PREREQ 2 — Authorize URL eyeball check.** 2026-04-12: User opened the fresh authorize URL, consent screen rendered the 7 ADR-021/025 scopes and `https://teemo.soula.ge/api/slack/oauth/callback` redirect, clicked **Cancel** → expected harmless 404 from `/api/slack/oauth/callback` (route not yet implemented — STORY-005A-04 creates it). Domain + TLS + redirect_uri registration all validated.
- [x] **HUMAN PREREQ 3a — `TEEMO_ENCRYPTION_KEY` generated and saved to local `.env`.** Generated via `secrets.token_urlsafe(32)` and written to root `.env` on 2026-04-12. Fingerprint (sha256[:8]) = `aecf7b12`. STORY-005A-01 will log this fingerprint at startup; verify it matches in production logs after Coolify deploy.
- [x] **HUMAN PREREQ 3b — `TEEMO_ENCRYPTION_KEY` propagated to Coolify.** User confirmed 2026-04-12 that the same `aecf7b12` key has been pasted into the Coolify env vars UI on the Tee-Mo service. DevOps verifies fingerprint match in production logs after sprint merge.
- [x] **Human has confirmed this sprint plan** — confirmed by sandrinio on 2026-04-12.

---

## 1. Active Scope

> 6 stories. Phase A epic = `EPIC-005-phase-a_slack_oauth_install` (in `product_plans/backlog/EPIC-005_slack_integration/`). All stories were drafted 2026-04-12 with full §1/§2/§3.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-005A-01: Slack Bootstrap (encryption + config + slack.py)](./STORY-005A-01-slack-bootstrap.md) | EPIC-005 Phase A | L2 | Done | — |
| 2 | [STORY-005A-02: `/api/slack/events` Signing-Secret Verification](./STORY-005A-02-events-signing-verification.md) | EPIC-005 Phase A | L2 | Done | STORY-005A-01 |
| 3 | [STORY-005A-03: `GET /api/slack/install` Install URL Builder](./STORY-005A-03-install-url-builder.md) | EPIC-005 Phase A | L2 | Done | — |
| 4 | [STORY-005A-04: `GET /api/slack/oauth/callback` Code Exchange + Encrypt + Upsert](./STORY-005A-04-oauth-callback-upsert.md) | EPIC-005 Phase A | **L3** | Done | STORY-005A-01 + STORY-005A-03 |
| 5 | [STORY-005A-05: `GET /api/slack/teams` List Endpoint](./STORY-005A-05-teams-list-endpoint.md) | EPIC-005 Phase A | L1 | Done | STORY-005A-04 (model file from 03 + table state from 04) |
| 6 | [STORY-005A-06: Frontend `/app` Install UI + Flash Banners](./STORY-005A-06-frontend-install-ui.md) | EPIC-005 Phase A | L2 | Done | STORY-005A-05 |

**Complexity mix:** 1× L1, 4× L2, 1× L3 — same shape as the S-03 6-story Fast-Track-only run that closed with 0 bounces and ~0.83% correction tax.

### Context Pack Readiness

> Per V-Bounce, Context Pack must be ✅ before a story moves Refinement → Ready to Bounce. All 6 stories were decomposed with full §1/§2/§3 from a fresh Explorer Context Pack on 2026-04-12, but the per-story Ambiguity drop to 🟢 will only be confirmed by the Developer agent at the start of each story's Bounce.

**STORY-005A-01: Slack Bootstrap**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 5 Gherkin scenarios)
- [x] Implementation guide written (§3 — encryption.py skeleton, slack.py skeleton, config validator)
- [x] Ambiguity: 🟢 Low
- [x] First-Use Pattern flagged: `cryptography.AESGCM`, `slack_bolt.AsyncApp`

**STORY-005A-02: Events Signing Verification**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 6 Gherkin scenarios)
- [x] Implementation guide written (§3 — `verify_slack_signature` helper + route hardening)
- [x] Ambiguity: 🟢 Low
- [x] Test vectors verified: live simulation 2026-04-12 against production `/api/slack/events` provides known-good HMAC inputs/outputs

**STORY-005A-03: Install URL Builder**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 6 Gherkin scenarios)
- [x] Implementation guide written (§3 — `create_slack_state_token` + RedirectResponse 307)
- [x] Ambiguity: 🟢 Low
- [x] First-Use Pattern: TanStack Router auth dep already exists (verified in Context Pack)

**STORY-005A-04: OAuth Callback (L3)**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 10 Gherkin scenarios covering happy path, re-install same/different owner, denial, state expired/tampered, cross-user, ok=false, missing bot_user_id, no token leakage)
- [x] Implementation guide written (§3 — full callback pseudocode, hand-rolled httpx mock pattern, 5 redirect branches)
- [x] Ambiguity: 🟢 Low
- [x] First-Use Pattern flagged: `httpx.AsyncClient` outbound POST, Supabase `.upsert()`

**STORY-005A-05: Teams List**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 5 Gherkin scenarios including no-token-leakage assertion)
- [x] Implementation guide written (§3 — explicit column select, NEVER `.select("*")`)
- [x] Ambiguity: 🟢 Low

**STORY-005A-06: Frontend Install UI**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 9 Gherkin scenarios for empty state, list, 5 banner variants, dismiss, loading)
- [x] Implementation guide written (§3 — `<a href>` not `onClick`, useSearch for query params, BANNER_VARIANTS lookup)
- [x] Ambiguity: 🟢 Low
- [x] First-Use Pattern flagged: TanStack Router `useSearch()` (verify against existing routes during Bounce; if first use, add flashcard at sprint close)

### Escalated / Parking Lot
- None.

---

## 2. Execution Strategy

> Drafted by Team Lead. Architect Sprint Design Review will validate this section before status flips Confirmed → Active.

### Phase Plan

- **Phase 1 (sequential, foundation):** STORY-005A-01 — must land first; 02 + 03 import from `slack.py`, 03 imports from `security.py` extension, 04 imports from `encryption.py`. **No parallelism in Phase 1.**
- **Phase 2 (parallel, post-foundation):** STORY-005A-02 + STORY-005A-03 can run in parallel after 01. They touch disjoint files (02 → `slack_events.py`; 03 → `slack_oauth.py` + `models/slack.py`). The only shared file is `slack.py` (02 adds `verify_slack_signature` helper, 03 adds nothing — clean fork).
- **Phase 3 (sequential, callback):** STORY-005A-04 starts only after 03 (needs the models + router). 02 may still be in flight — that's fine; 04 doesn't touch `slack_events.py`.
- **Phase 4 (sequential, list endpoint):** STORY-005A-05 starts after 04 (so the test fixtures can encrypt + insert real rows that the list endpoint reads back).
- **Phase 5 (sequential, frontend):** STORY-005A-06 starts after 05 (needs the API endpoint for the TanStack Query call).

**Total wall-clock chain:** 5 sequential gates with 1 parallel point (Phase 2).

### Merge Ordering

| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-005A-01 | Foundation — 02 and 03 won't compile without it. |
| 2 | STORY-005A-02 OR STORY-005A-03 | Either order — disjoint file surfaces. Whichever finishes Bouncing first merges first. |
| 3 | (the other of 02 / 03) | Trivial conflict surface only on `main.py` router list. |
| 4 | STORY-005A-04 | Needs 01 + 03 merged. Callback uses encryption + state-verify helpers. |
| 5 | STORY-005A-05 | Trivial — single route addition to `slack_oauth.py`. |
| 6 | STORY-005A-06 | Frontend-only after backend is fully wired. |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|---------------------|------|
| `backend/app/core/slack.py` | 01 (NEW), 02 (add `verify_slack_signature`), 03 (no change after 01) | **Low** — append-only between stories; no contested edits. |
| `backend/app/core/config.py` | 01 (5 new fields + validator) | **Low** — single story touches it. |
| `backend/app/api/routes/slack_oauth.py` | 03 (NEW with `/install`), 04 (add `/oauth/callback`), 05 (add `/teams`) | **Medium** — 3 stories progressively add routes. Mitigation: strict merge ordering 03 → 04 → 05 above. |
| `backend/app/models/slack.py` | 03 (NEW with `SlackInstallState`), 05 (add `SlackTeamResponse`) | **Low** — append-only. |
| `backend/app/main.py` | 03 (router include) | **Low** — single story. |
| `backend/app/core/security.py` | 03 (add `create_slack_state_token` + `verify_slack_state_token`) | **Low** — single story. |
| `frontend/src/routes/app.tsx` | 06 (replace body) | **Low** — single story. |
| `frontend/src/lib/api.ts` | 06 (add `listSlackTeams`) | **Low** — single story. |

**Conclusion:** the only Medium-risk surface is `slack_oauth.py` shared by stories 03 → 04 → 05, fully mitigated by the strict sequential merge order. No file is touched by 2+ parallel-phase stories.

### Execution Mode

> S-03 baseline: 6 stories, **all Fast Track**, **0 QA bounces, 0 Architect bounces**, ~0.83% aggregate correction tax. The same posture is recommended for S-04, with one exception: STORY-005A-04 is L3 + cross-cutting + security-sensitive, so it gets Full Bounce.

| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-005A-01 | L2 | **Fast Track** | — | First-Use Pattern (AESGCM, AsyncApp) is encapsulated; pure infra; tests cover roundtrip + tamper. |
| STORY-005A-02 | L2 | **Fast Track** | — | Single function + route guard; known-good test vectors from 2026-04-12 simulation eliminate the unknown. |
| STORY-005A-03 | L2 | **Fast Track** | — | Reuses existing PyJWT helpers; small route surface. |
| STORY-005A-04 | **L3** | **Full Bounce** | — | Security-sensitive (token encryption + cross-user check + 409 conflict path); 10 test scenarios; first use of httpx + Supabase upsert. **Architect must validate** the encryption+DB-write composition and the 5 redirect branches before merge. |
| STORY-005A-05 | L1 | **Fast Track** | — | Trivial GET; explicit-column-select is the only non-trivial concern, covered by the no-leakage test. |
| STORY-005A-06 | L2 | **Fast Track** | — | Frontend-only; standard TanStack Query + Router patterns. |

**Aggregate forecast:** 5 Fast Track + 1 Full Bounce. The Full Bounce on 005A-04 is non-negotiable — it's the only place a security mistake could leak a Slack bot token.

### ADR Compliance Notes

> Pre-flight check against Roadmap §3 ADRs. No conflicts identified during decomposition.

- **ADR-001 (JWT auth):** STORY-005A-03 reuses `JWT_SECRET` + module-local `_JWT` instance from `security.py` for state token signing — compliant.
- **ADR-002 (AES-256-GCM via cryptography.AESGCM):** STORY-005A-01 uses exactly this primitive — compliant.
- **ADR-010 (Slack bot token encrypted at rest):** STORY-005A-04 encrypts before DB write; STORY-005A-05 NEVER returns encrypted_slack_bot_token in API responses (explicit column select + leak test) — compliant.
- **ADR-013 (No streaming v1):** Phase A uses no Slack reply primitives at all — compliant by absence. EPIC-011 may revisit.
- **ADR-019/020 (VPS + Coolify, self-hosted Supabase):** No infra changes in S-04 — compliant.
- **ADR-021 (event scope: app_mention + message.im, NO message.channels):** STORY-005A-02 only handles `url_verification` + 202s everything else; the 7 scopes encoded in STORY-005A-03 match exactly — compliant.
- **ADR-024 (workspace model: 1 user : N SlackTeams):** STORY-005A-04 enforces `owner_user_id` from auth + 409 on cross-user re-install — compliant.
- **ADR-025 (channels:read + groups:read scopes):** included in the 7-scope tuple — compliant.
- **ADR-026 (deploy infrastructure pulled forward):** S-03 already shipped; S-04 only consumes it — compliant.

**No ADR adjustments required for this sprint.**

### Dependency Chain

> Stories that MUST run sequentially due to `depends_on` or shared file surfaces.

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-005A-02 | STORY-005A-01 | Imports `verify_slack_signature` from `slack.py` and reads `settings.slack_signing_secret`. |
| STORY-005A-03 | STORY-005A-01 | Imports `slack_client_id`, `slack_redirect_url` from settings; uses `_JWT` from extended `security.py`. |
| STORY-005A-04 | STORY-005A-01 + STORY-005A-03 | Needs `encrypt()` from 01 AND `verify_slack_state_token` + `slack_oauth.py` file from 03. |
| STORY-005A-05 | STORY-005A-04 | Needs `models/slack.py` + `slack_oauth.py` file (added by 03/04); test fixtures require encryption (from 01). |
| STORY-005A-06 | STORY-005A-05 | TanStack Query call needs `/api/slack/teams` endpoint to be live in dev. |

### Risk Flags

Pulled from Phase A epic §6 + sprint-specific concerns:

- **R-S04-1: First-use httpx.AsyncClient pattern (STORY-005A-04).** No prior outbound HTTP from this codebase. **Mitigation:** the story §3.3 includes a hand-rolled mock pattern; QA must verify the mock works against the canonical `oauth.v2.access` shape verified in slack-bolt source on 2026-04-12. **Add flashcard at sprint close** documenting the chosen pattern.
- **R-S04-2: First-use Supabase `.upsert()` (STORY-005A-04).** Behavior of the Python client around DEFAULT NOW() columns is undocumented in our codebase. **Mitigation:** integration test verifies `installed_at` survives a re-install upsert (re-install scenario in §2.1).
- **R-S04-3: Coolify `TEEMO_ENCRYPTION_KEY` propagation (HUMAN PREREQ 3).** If the user pastes a different key into Coolify than `.env`, local tests pass and prod tests fail. **Mitigation:** STORY-005A-01 logs key fingerprint at startup; DevOps verifies fingerprint matches between local and prod after merge.
- **R-S04-4: Slack Event Subscriptions Request URL re-verification (R11).** S-03 left this in an unverified state. **Mitigation:** HUMAN PREREQ 1 in §0 above. Without this, STORY-005A-02 cannot be QA-passed in production (the manual curl test depends on the URL being live in Slack's eyes).
- **R-S04-5: Phase A epic OUT-OF-SCOPE temptation.** During Bouncing, Developer agents may be tempted to pull in BYOK key handling (because `encryption.py` is right there) or AI Apps surface (because `slack-bolt` is being imported). **Mitigation:** Architect Sprint Design Review verifies §2 OUT-OF-SCOPE is honored; QA flags any out-of-scope additions in story reports.
- **R-S04-6: Story 04 is the load-bearing demo story.** If 04 bounces hard, the entire Phase A demo is at risk. **Mitigation:** 04 is the only Full Bounce in this sprint; it gets the heaviest QA + Architect attention.

---

## 3. Sprint Open Questions

> Unresolved items that affect THIS sprint execution window only. (Strategic / epic-level questions belong in the epic, not here.)

| # | Question | Options | Impact | Owner | Status |
|---|----------|---------|--------|-------|--------|
| SQ-1 | If STORY-005A-02 or 005A-03 is QA-bounced, do we still allow the other to merge? | A: Yes — disjoint files, no risk. B: No — block both until both pass. | A is the obvious answer; documenting for explicitness. | Team Lead | **Decided — A** |
| SQ-2 | If STORY-005A-04 bounces 3+ times, do we de-scope to "deploy with mocked OAuth callback returning fake row" to keep the demo flow visible? | A: De-scope, ship a demo seam. B: Hold the sprint open, no shortcut. | A risks shipping a fake demo. B risks slipping Release 1 by a day. | Solo dev | **Resolved — N/A. 005A-04 merged on first pass with 0 QA + 0 Arch bounces.** |
| SQ-3 | Who runs the post-merge production smoke test (real OAuth click-through)? | A: Solo dev manually. B: Automated curl in CI. | A is the only viable option for hackathon — no Slack mock in CI. | Solo dev | **Decided — A** |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Team Lead after each story completes via `vbounce story complete STORY-ID`. Becomes the skeleton for Sprint Report §2 at sprint close.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-005A-01 | Done | 0 | 0 | 8 | 5% | Fast Track. 8/8 target + 44/44 full suite. Two skeleton fixes in Green: base64url padding, AsyncApp `request_verification_enabled`. Fingerprint `aecf7b12` matches. |
| STORY-005A-02 | Done | 0 | 0 | 8 | 0% | Fast Track. 8 new tests + 3 stub tests updated to carry valid signatures (intended behavior change). 52/52 full suite. Flashcards: bare `Response(400)` replaces old JSON body on malformed-JSON path — document in vdoc. |
| STORY-005A-03 | Done | 0 | 0 | 6 | 5% | Fast Track. 6/6 target + 58/58 full suite (stable 15 runs). Team Lead fixed malformed UUID fixture on line 96 per Step 2c. Flaky pre-existing `test_decode_token_resists_global_options_poison` (BUG-20260411 family) noted; not a regression. |
| STORY-005A-04 | Done | 0 | 0 | 10 | 0% | **Full Bounce.** 10/10 target + 68/68 full suite. 0 QA + 0 Architect bounces on first pass. 2 flashcards approved (httpx module-level import, Supabase `.upsert()` DEFAULT NOW() exclusion). 5 Phase B risks documented in Architect audit (TOCTOU on different-owner, unvalidated oauth.v2.access response, coalesced missing-field warning, brittle httpx monkeypatch, no retry/resp.status_code check). |
| STORY-005A-05 | Done | 0 | 0 | 5 | 0% | Fast Track L1. 5/5 target + 73/73 full suite. Explicit-column `.select()` verified; `SlackTeamResponse` model deliberately omits `encrypted_slack_bot_token`; no-ciphertext-in-response assertion passes. |
| STORY-005A-06 | Done | 0 | 0 | 9 | 5% | Fast Track L2. 9/9 new frontend tests + 19/19 full frontend suite, `pnpm tsc --noEmit` clean, `pnpm build` clean. Backend unchanged at 73/73. Legitimate scope expansion: added RTL test infrastructure (4 devDeps + new `vitest.config.ts` + `test-setup.ts` + `tsr.config.json` route-ignore) — the frontend had no component testing setup before this story. 3 flashcards flagged for sprint close (vitest@2+vite@8 type conflict fix, RTL auto-cleanup needs globals:true, getByText mixed-text-nodes need span wrapping). |
<!-- EXECUTION_LOG_END -->

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint plan drafted from `.vbounce/templates/sprint.md` after Phase A epic decomposition. Status: **Planning**. 6 stories scoped, dependency chain established, 5 Fast Track + 1 Full Bounce (005A-04 L3), 3 sprint-level questions (1 open at 005A-04 risk threshold), 6 risk flags identified (3 mitigated by §0 human prereqs). Awaiting human gate confirmation. | Team Lead |
| 2026-04-12 | All §0 human prereqs cleared: PREREQ 1 Request URL ✅ Verified, PREREQ 2 consent screen eyeballed + cancel 404 confirmed, PREREQ 3b Coolify env var set. Human confirmation received from sandrinio. Status: **Planning → Active**. Sprint Readiness Gate cleared; proceeding to sprint branch cut and Step 1 STORY-005A-01 worktree creation. | Team Lead |
| 2026-04-12 | **STORY-005A-01 Slack Bootstrap merged** (merge commit `466dc4e` into `sprint/S-04`). Fast Track, 0 QA / 0 Arch bounces, 5% correction tax. 8/8 target tests + 44/44 full backend suite passing. Fingerprint `aecf7b12` verified post-merge. Worktree removed, story branch deleted. 2 flashcards flagged for sprint close (base64url padding; slack_bolt `request_verification_enabled`). | Team Lead |
| 2026-04-12 | **Sprint plan table cell corruption recovered.** `complete_story.mjs STORY-005A-01` over-aggressively replaced multiple table cells and column headers with the string "Done" (rows 3–5 in §1 Active Scope, §2 Merge Ordering row 2 + "Reason" header, §2 Execution Mode Architect-Override cell for 005A-01, §2 Dependency Chain "Reason" header + rows 003/005, §3 Open Questions "Options" header, §4 Execution Log Tests-Written cell). All cells restored by hand from the original plan content. Execution Log row for 005A-01 rewritten in-place (the script appended a duplicate, missing the Tests-Written column). **Framework issue filed for `/improve` at sprint close.** | Team Lead |
