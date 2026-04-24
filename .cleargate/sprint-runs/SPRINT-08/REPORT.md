---
sprint_id: "SPRINT-08"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-08.md"
---

# SPRINT-08 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-08.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: Ship EPIC-006 — Google Drive OAuth, file indexing with AI descriptions, frontend Picker integration, and agent `read_drive_file` tool, all live end-to-end.

## §1 What Was Delivered

**User-facing:**
- Google Drive OAuth install flow end-to-end.
- Frontend Google Drive Picker integration — user selects pre-existing files, backend indexes them with AI-generated descriptions.
- Visible indexing progress indicator (pulsing amber progress banner) added during E2E testing.
- `WorkspaceCard` now links to workspace detail page (added during E2E).
- Slack agent can call `read_drive_file` tool to read indexed Drive files.

**Internal / infrastructure:**
- `drive_service` (30 tests), `scan_service` (8 tests), `config` (5 tests).
- `agent_factory` refactor with Drive tool wiring (18 tests).
- `drive_oauth` routes (34 tests) — access-token exchange for userinfo (not refresh token), column names `user_id` + `ai_provider` (not `owner_user_id`/`provider`).
- `knowledge_routes` CRUD (26 tests) — `Optional[str]` instead of `str | None` for Python 3.9 + FastAPI runtime type compatibility.
- 10 frontend hooks tests — Drive integration + Picker flow.
- Agent system prompt updated with file catalog for `read_drive_file`.
- Slack mrkdwn formatting fix (agent was outputting Markdown).
- Streaming agent responses via `run_stream()` + progressive `chat_update`.
- Slack display name resolution fix (strip + fallback chain).

**Carried over (if any):**
- Live production click-through after release deploy.
- Vdoc initialization recommended — sprint delivered 5+ features with no vdocs; no `vdocs/_manifest.json` exists.

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-006-01 | Drive Service | Done | 0 | 0 | 0% | L2, Fast Track. Foundation: `drive_service` + `scan_service` + config. |
| STORY-006-04 | Agent Drive Tool | Done | 0 | 0 | 0% | L2, Fast Track. `read_drive_file` tool + system prompt file catalog. |
| STORY-006-02 | Drive OAuth | Done | 0 | 1 | 5% | L3, Full Bounce. Arch caught: refresh token used as Bearer for userinfo (requires access-token exchange). Mocked tests passed because `FakeDriveAsyncClient` returns success regardless of credential. |
| STORY-006-03 | Knowledge CRUD | Done | 1 | 1 | 10% | L3, Full Bounce. QA+Arch both caught: `drive_oauth.py` used Python 3.10+ `str \| None` without `from __future__ import annotations` (breaks on py3.9 + breaks FastAPI runtime type inspection). Plus POST tests didn't mock `decrypt()`. Plus dead class. |
| STORY-006-05 | Frontend Drive | Done | 0 | 0 | 0% | L3, Full Bounce. Clean first pass. Layout refactor for TanStack Router. |
| STORY-006-06 | E2E Verification | Done | 0 | 0 | 15% | L1, Fast Track. 4 real issues discovered during live testing: column names, OAuth scope, redirect URI, display name. |

**Change Requests / User Requests during sprint:**
- Mid-E2E OAuth scope change: `drive.file` → `drive.readonly` (real Google API behavior — `drive.file` doesn't grant access to pre-existing files selected via Picker via refresh token).
- OAuth callback redirect switched from backend origin (port 8000) to frontend (5173) using `cors_origins` for redirect base URL.
- Post-sprint fixes: Slack mrkdwn formatting, streaming responses via `run_stream()`, Slack display name resolution.

## §3 Execution Metrics

- **Stories planned → shipped:** 6/6 (EPIC-006 fully delivered)
- **First-pass success rate:** 67% (4/6 stories passed first attempt; 006-02 = 1 Arch bounce, 006-03 = 1 QA + 1 Arch bounce)
- **Bug-Fix Tax:** 0 bugs filed
- **Enhancement Tax:** Multiple E2E-driven scope additions (progress indicator, WorkspaceCard link, agent formatting fixes, streaming, display name fix) — 15% tax on STORY-006-06
- **Total tokens used:** 1,118,159 across 17 subagent tasks (~67 min total agent runtime). Does not include Team Lead (main conversation).
- **Aggregate correction tax:** ~5% average across code stories; 15% on E2E due to column-name mismatches, OAuth scope change, redirect URI fixes
- **Tests added:** 120+ (30 drive_service + 8 scan_service + 5 config + 18 agent_factory + 34 drive_oauth + 26 knowledge_routes + 10 frontend hooks).

## §4 Lessons

Top themes from flashcards flagged during this sprint (pending approval):
- **#oauth-scope:** `drive.file` OAuth scope doesn't grant refresh-token access to Picker-selected files — use `drive.readonly` for backend file reads. Real Google API behavior mocked tests cannot catch.
- **#py39-annotations:** `from __future__ import annotations` breaks FastAPI runtime type resolution on Python 3.9 — use `Optional[str]` instead of `str | None` for py3.9 compatibility.
- **#google-bearer:** Google refresh tokens cannot be used as Bearer credentials for resource APIs — always exchange for access token at the token endpoint first. Protocol-level errors invisible to hermetic mocks.
- **#worktree-npm:** Frontend worktrees need `npm install` before `vite build` — no `node_modules` in worktree.
- **#db-column-names:** Column names in queries must match actual DB schema — hermetic mocks hide column-name typos. (`owner_user_id` → `user_id`, `provider` → `ai_provider`.)

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals:**
  - Hermetic mocks hide protocol-level errors (refresh vs access token for Google userinfo) and column-name typos. Consider contract-shape assertions in mocks.
  - `from __future__ import annotations` incompatible with FastAPI's runtime type inspection on Python 3.9 — dev agents hit this twice.
  - Frontend worktree builds need manual `npm install` before `vite build`.
- **Framework issues filed:** Friction signals above noted in report; no dedicated `improvement-suggestions.md` entries for S-08.
- **Hook failures:** N/A (V-Bounce had no hooks).

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- Recommend vdoc initialization — sprint delivered 5+ features with no vdocs, no `vdocs/_manifest.json` exists.
- Post-sprint fixes (Slack mrkdwn, streaming, display name) to land alongside release.
- EPIC-007 agent factory work unblocked by `agent_factory` refactor + `read_drive_file` tool.
- Real-world live-testing revealed 4 classes of findings hermetic tests can't catch (OAuth scope, redirect URI, column names, display name) — recommend either production-smoke step post-merge OR richer fakes.
