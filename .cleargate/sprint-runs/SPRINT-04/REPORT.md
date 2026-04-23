---
sprint_id: "SPRINT-04"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-04.md"
---

# SPRINT-04 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-04.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: Real Slack OAuth install end-to-end — logged-in user clicks Install Slack on `/app`, completes consent, lands back with a `teemo_slack_teams` row owned by them and visible in the team list. Closes the S-03 events stub TODO (HMAC signature verification).

## §1 What Was Delivered

**User-facing:**
- `/app` replaced placeholder welcome card with a full Slack Teams page: empty state, team list, 5 flash banner variants (ok/cancelled/expired/error/session_lost), loading skeleton, inline error with retry, Install Slack anchor tag.
- End-to-end Slack OAuth install flow: logged-in user clicks Install Slack → Slack consent → lands back with a `teemo_slack_teams` row owned by them, visible in the team list.

**Internal / infrastructure:**
- 4 backend endpoints:
  - `GET /api/slack/install` — signed-state JWT redirect to Slack consent.
  - `GET /api/slack/oauth/callback` — code exchange, encrypt, upsert, 5 redirect branches + 3 hard-fail branches.
  - `GET /api/slack/teams` — list user's installed teams, no token leakage (explicit-column select + Pydantic model omission + test assertion).
  - `POST /api/slack/events` hardened with HMAC-SHA256 v0 signature verification (closes S-03 TODO).
- New `validateSearch` route schema + RTL test infrastructure (`vitest.config.ts` + `test-setup.ts` + jest-dom + jsdom).
- `encrypted_slack_bot_token` has ADR-010 defense in depth: backend column-explicit `.select()`, Pydantic `SlackTeamResponse` omits field, route-level test asserts neither plaintext nor ciphertext in response body.

**Carried over (if any):**
- **P0 framework bug:** `.vbounce/scripts/complete_story.mjs` corrupts sprint plan table cells — hit 5 times this sprint, hand-patched each time. Must be fixed before S-05.
- Production click-through verification deferred to post-release (needs S-04 on `main` + Coolify redeploy).
- Phase B risks flagged for EPIC-005 Phase B scoping: TOCTOU on different-owner check, `oauth.v2.access` response not Pydantic-validated, coalesced missing-field warning, brittle httpx monkeypatch, no retry / no status_code check before `.json()`.

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-005A-01 | Slack Bootstrap | Done | — | — | 5% | Fast Track. 8 tests. Merge: `466dc4e`. |
| STORY-005A-02 | Events Signing | Done | — | — | 0% | Fast Track. 8 tests. HMAC-SHA256 v0 signature verification. Merge: `baab1e9`. |
| STORY-005A-03 | Install URL | Done | — | — | 5% | Fast Track. 6 tests. Merge: `451412d`. |
| STORY-005A-04 | OAuth Callback | Done | 0 | 0 | 0% | **Full Bounce** — L3, passed on first attempt with zero security findings. 10 tests. Merge: `738ffc6`. |
| STORY-005A-05 | Teams List | Done | — | — | 0% | Fast Track. 5 tests. Merge: `5935186`. |
| STORY-005A-06 | Frontend UI | Done | — | — | 5% | Fast Track. 9 tests. Merge: `00ff3e2`. |

**Change Requests / User Requests during sprint:**
- During a rate-limit-induced blocker, Team Lead considered bypassing subagent tier and implementing 005A-02 + 005A-03 directly. User interrupted and corrected: "don't change the process." Deviation aborted before any code written — filed as a process lesson.
- User opted to skip local UI click-through (backend + frontend started on ports 8000/5173 after stopping `chyro-api-1`/`chyro-spa-1` containers holding the ports) and proceed directly to production release for real demo click-through.

## §3 Execution Metrics

- **Stories planned → shipped:** 6/6
- **First-pass success rate:** 100% (0 QA bounces, 0 Architect bounces — including the L3 Full Bounce story)
- **Bug-Fix Tax:** 0 (two known flaky tests logged for `test_decode_token_resists_global_options_poison` + `test_state_token_tamper` — BUG-20260411 family)
- **Enhancement Tax:** 0 scope additions
- **Total tokens used:** ~400-500k estimated across 22 Dev/QA/Architect/DevOps subagent calls — not precisely aggregated (subagent reports did not all populate `total_tokens` field). Individual runs consumed ~8-15k tokens each.
- **Aggregate correction tax:** ~2.5% (5%/0%/5%/0%/0%/5%)
- **Tests added:** 47. **Full suite at close:** 92 passing (73 backend + 19 frontend).
- **`teemo_slack_teams`** picked up as healthy tracked table via column-agnostic probe from S-03 hotfix (`ce7c0b1`).

## §4 Lessons

Top themes from flashcards recorded during this sprint (7 pending approval, batched per user preference):

Architect-approved (STORY-005A-04 audit):
- **#httpx:** `httpx.AsyncClient` first-use — import at module level for test monkeypatchability. Pattern: `monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)`. Applies to every future outbound HTTP story until `app/core/http.py` is extracted.
- **#supabase-upsert:** Supabase `.upsert()` — omit `DEFAULT NOW()` columns from the payload. PostgREST sets every field passed. Omit `installed_at`/`bound_at` to preserve original timestamps on re-installs.

Pending from Dev reports:
- **#base64-padding:** `base64.urlsafe_b64decode` needs padding. 43-char base64url strings in `.env` need `raw + "=" * (-len(raw) % 4)` before decode.
- **#slack-bolt-kwarg:** `slack_bolt.AsyncApp` uses `request_verification_enabled=True`, NOT `token_verification_enabled` (story template had wrong name).
- **#slack-events-400:** `/api/slack/events` malformed-JSON response body changed — old stub returned JSON `{"detail":"invalid_json"}`, hardened handler returns bare `Response(400)`.
- **#vitest-vite-peers:** `vitest@2.1.9 + vite@8` type conflict — inline `test:` block in `vite.config.ts` causes `ProxyOptions` TypeScript incompatibility. Fix: separate `vitest.config.ts` importing from `vitest/config`, excluded from `tsconfig.node.json`.
- **#rtl-globals:** `@testing-library/react` auto-cleanup requires `globals: true` — without it, cleanup is skipped and renders accumulate across tests.

Rejected by Architect:
- `get_current_user_id_optional` narrow-catch of `HTTPException` — Python 101 hygiene, converted to inline comment at `deps.py:88`.

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals (P0 — blocking):**
  - `.vbounce/scripts/complete_story.mjs` cell-corruption bug — over-aggressive regex replacement of table cells and column headers with "Done". Corrupted sprint plan after every call this sprint (5 times). Hand-patched each time. Filed as improvement #2 in `.vbounce/improvement-suggestions.md`. Suggested fix: replace regex with proper markdown-table parser + golden-file test. Audit S-02/S-03 archived sprint plans for retroactive damage.
- **Friction signals (P1 — high):**
  - Subagent rate-limit handling: one pair of Green Phase agents instant-failed with "You've hit your limit · resets 1am" after ~250ms and 0 tool uses. Failure mode indistinguishable from actual task failure until result-text inspection. Team Lead protocol needs explicit rate-limit detection + backoff/retry or escalation.
- **Friction signals (P2 — medium):**
  - Architect agent cannot write reports (profile lacks Write permission, or "return findings inline" rule conflicts with skill's "write to .vbounce/reports/"). Team Lead persisted 005A-04 Architect audit to disk manually.
  - QA agent writes reports to main repo, not worktree: `/Users/ssuladze/.vbounce/reports/` instead of worktree path. Team Lead moved it.
- **Friction signals (P3 — low):**
  - Flaky `test_decode_token_resists_global_options_poison` (BUG-20260411 family) — passes in isolation, fails ~1/20 full-suite runs due to PyJWT global state leakage. Re-run clears it. DevOps flagged `test_state_token_tamper` as second family flake.
- **Framework issues filed:** 5 entries in `.vbounce/improvement-suggestions.md` (P0-P3 above).
- **Hook failures:** N/A (V-Bounce had no hooks).

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- Release branch `sprint/S-04` → `main`. Release tag `v0.4.0` (post-release, DevOps to set).
- Coolify auto-deploys on push to `main`. `TEEMO_ENCRYPTION_KEY` fingerprint `aecf7b12` verified matching local `.env` and Coolify env.
- Production health probe post-deploy will show `teemo_slack_teams: "ok"` (table created in S-03).
- Release 1 ~85% → ~92% delivered after S-04; S-05 closes Release 1.
- **Must fix before S-05:** `complete_story.mjs` P0 bug.
- EPIC-005 Phase B should scope the 5 carried-forward risks (TOCTOU, Pydantic response model, per-field logging, DI for http client, retry/status check before .json()).
