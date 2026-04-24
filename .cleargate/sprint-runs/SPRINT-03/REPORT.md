---
sprint_id: "SPRINT-03"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-03.md"
---

# SPRINT-03 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-03.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: Land `https://teemo.soula.ge` as a live Coolify auto-deploy, apply the 3 ADR-024 schema migrations, fix BUG-20260411 (PyJWT test-order flake), and ship the minimal Slack events verification endpoint so EPIC-005 Phase A can start in S-04.

## §1 What Was Delivered

**User-facing:**
- First live Coolify auto-deploy of `https://teemo.soula.ge` lands with the release merge of this sprint.
- Backend health endpoint (`/api/health`) now reports 6 `teemo_*` tables (up from 4) and handles HEAD requests (Coolify healthcheck compatibility).

**Internal / infrastructure:**
- Multi-stage Dockerfile at repo root (node:22-alpine frontend + python:3.11-slim backend, 962 MB image — accepted). `.dockerignore` excludes `.env`, `.git`, `.worktrees`, `.vbounce`, transient paths.
- FastAPI same-origin static serving: `StaticFiles` mount at `/assets` + explicit SPA catch-all route `/{full_path:path}` → `FileResponse(index.html)`, guarded by `_static_dir.is_dir()` so local dev skips the mount.
- `frontend/src/lib/api.ts` `VITE_API_URL` default changed from `http://localhost:8000` to empty string (same-origin in prod). `vite.config.ts` gained `/api` dev proxy for local `npm run dev`.
- 318-line Coolify setup runbook at `product_plans/sprints/sprint-03/coolify-setup-steps.md` (service creation, env vars, domain binding, healthcheck, branch selection, troubleshooting, rollback).
- ADR-024 schema: migrations 005 (`teemo_slack_teams`), 006 (`teemo_workspace_channels`), 007 (`teemo_workspaces` ALTER — FK, `is_default_for_team` + `one_default_per_team` partial unique index, DO-block safety pre-check). `TEEMO_TABLES` extended 4 → 6 in `backend/app/main.py`.
- BUG-20260411 fixed: `decode_token` migrated to scoped `jwt.PyJWT()` instance, regression-lock test added (`test_decode_token_resists_global_options_poison`). 10-run stability loop green.
- `POST /api/slack/events` stub: handles `url_verification` challenge (PlainTextResponse 200), returns 202 for other event types, 400 for malformed JSON. No signature verification yet (S-04 owns that — documented TODO).

**Carried over (if any):**
- Docker image size 962 MB vs <500 MB target — optimization deferred until Coolify deploy time becomes painful.
- Production deploy verification (6 curl/browser checks) pending user manual Coolify redeploy post-push-to-main.
- Integration audit waived this sprint (infra/schema/fix work with clean story-to-story separation).

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-003-01 | Multi-stage Dockerfile + same-origin static serving | Done | 0 | 0 | 5% | L2, Fast Track. Two legit Starlette 1.0.0 fixes: `StaticFiles(html=True)` isn't SPA fallback; `@app.get` doesn't auto-handle HEAD. 32 regression tests. Image size 962 MB accepted. |
| STORY-003-02 | Coolify wiring runbook | Done | 0 | 0 | 0% | L2, Fast Track. Runbook-only, 318 lines. Deploy verification merged into sprint close. |
| STORY-003-03 | Migrations 005/006/007 + TEEMO_TABLES extension | Done | 0 | 0 | 0% | L2, Fast Track. 3 SQL files, DO-block safety pre-check in 007. 31 tests (9 health + 22 regression). User ran SQL manually in Supabase editor. |
| STORY-003-04 | PyJWT BUG-20260411 fix | Done | 0 | 0 | 0% | L1, Fast Track. `decode_token` → scoped `jwt.PyJWT()`. 10-run stability loop green. BUG closed. |
| STORY-003-05 | Slack events verification stub | Done | 0 | 0 | 0% | L1, Fast Track. Minimal `POST /api/slack/events` url_verification handler. 3 stub tests. |
| STORY-003-06 | Production deploy verification | Done (collapsed) | — | — | — | L1, manual. Collapsed into sprint close per user decision — runs inline with release merge, not a separate worktree bounce. |

**Change Requests / User Requests during sprint:**
- User collapsed STORY-003-06 into sprint close (no separate bounce).
- User ran SQL migrations at `https://sulabase.soula.ge` via Supabase SQL editor in parallel with agent work.
- User created Slack app at api.slack.com (Steps 1-4) + Google Cloud OAuth consent scopes (openid, userinfo.email, drive.file) in parallel.
- Flashcards batched at sprint close per user preference.

## §3 Execution Metrics

- **Stories planned → shipped:** 6/6 (5 bounced separately + 1 collapsed)
- **First-pass success rate:** 100% (Fast Track throughout; 0 QA, 0 Arch bounces, 0 escalations)
- **Bug-Fix Tax:** 1 bug closed in-sprint (BUG-20260411 PyJWT test-ordering)
- **Enhancement Tax:** 0 scope additions
- **Total tokens used:** ~500,000 aggregated across 6 Dev + 1 DevOps task-notification totals (Dev-report YAML token fields remain unreliable per S-02 lesson)
- **Aggregate correction tax:** ~0.83% (single Starlette spec deviation absorbed as framework reality)
- **Backend tests:** 36 at close (22 → 36, +14). **Frontend tests:** 10 unchanged.
- **Git:** 22 commits ahead of `main`. 5 `--no-ff` story merges.
- **Release tag:** `v0.3.0-deploy`.

## §4 Lessons

Top themes from flashcards recorded during this sprint:
- **#starlette-spa:** Starlette 1.0.0 `StaticFiles(html=True)` is NOT a SPA fallback — use an explicit catch-all `@app.api_route("/{full_path:path}", methods=["GET","HEAD"])` returning `FileResponse(index.html)`, plus StaticFiles mount at `/assets`.
- **#starlette-head:** `@app.get(...)` does NOT auto-register HEAD in Starlette 1.0.0 — use `@app.api_route(..., methods=["GET","HEAD"])` for any endpoint hit by reverse-proxy healthchecks or `curl -I`.
- **#worktree-paths:** Agent worktree isolation — Edit/Write tool calls inside a story worktree MUST use worktree-relative paths. Absolute paths like `/Users/ssuladze/...` bypass the worktree and land on whatever branch is checked out in the main repo. (Bit us on STORY-003-04 BUG report edit.)
- **#orbstack (rejected as flashcard):** macOS + OrbStack requires `--context orbstack` flag on every `docker` invocation. Rejected as universal flashcard (machine-specific), added to sprint-context file instead.

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals:**
  - `complete_story.mjs` + linter creating orphan §4 table rows twice this sprint — required manual fix commits. Framework improvement: script should append to §4 table row, not end of file.
  - Worktree `node_modules` symlink still manual — frontend Vitest in a worktree needs either `npm install` (slow) or manual symlink from main repo.
  - `.env` symlink automation still manual per worktree creation.
  - Team Lead `cp` path bugs when merging from inside a worktree (twice — relative-path failures). Personal discipline, not framework.
  - Two spec errors in STORY-003-01 (StaticFiles SPA fallback, HEAD auto-handling) — Starlette 1.0.0 library realities not fact-checked. Framework candidate: Architect could pre-flight spot-check when "First-Use Pattern: No" but library surface is actually new.
- **Framework issues filed:** 4 improvement candidates for V-Bounce `/improve`:
  1. Task file template should include explicit "use worktree-relative paths" instruction.
  2. `complete_story.mjs` should append to §4 table row, not end of file.
  3. Worktree setup script should symlink `frontend/node_modules`.
  4. Architect pre-flight spot-check when "First-Use Pattern" is "No" but library surface is new.
- **Hook failures:** N/A (V-Bounce had no hooks)

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- S-04 will ship the Slack events endpoint hardening (HMAC-SHA256 v0 signature verification) — closes the S-03 TODO.
- EPIC-005 Phase A (Slack OAuth install flow) unblocked by events stub + 6-table schema.
- User will manually trigger Coolify redeploy after push to main, then complete Slack app setup Steps 5-7 (Event Subscriptions URL verification at api.slack.com).
- Team Lead will curl-verify 4 production endpoints post-deploy (`/api/health`, `/`, `/login`, `/api/slack/events`).
- No new backlog items from S-03 (BUG-20260411 closed in-sprint).
- Vdoc generation still deferred (post-EPIC-003 Slice B).
