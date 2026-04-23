---
total_input_tokens: 0
total_output_tokens: 0
total_tokens_used: 1118159
sprint_id: "S-08"
---

# Sprint Report: S-08 — EPIC-006 Google Drive

## 1. Key Takeaways

- **Delivery**: 6/6 stories shipped. EPIC-006 fully delivered. Google Drive OAuth, file indexing with AI descriptions, frontend Picker integration, and agent `read_drive_file` tool all live.
- **Quality**: 4/6 stories passed first attempt. 2 stories bounced (006-02: 1 Architect bounce; 006-03: 1 QA + 1 Architect bounce). First-pass success rate: 67%.
- **Correction Tax**: Average 5% across code stories. E2E verification (006-06) had 15% due to column name mismatches, OAuth scope change, and redirect URI fixes discovered during live testing.
- **Tests**: 120+ new tests written (30 drive_service, 8 scan_service, 5 config, 18 agent_factory, 34 drive_oauth, 26 knowledge_routes, 10 frontend hooks).
- **Top Surprise**: `drive.file` OAuth scope doesn't grant access to pre-existing files selected via Picker — required mid-E2E switch to `drive.readonly`. This is a real Google API behavior that mocked tests cannot catch.
- **Post-Sprint Fixes**: Slack mrkdwn formatting (agent was outputting Markdown), streaming responses via `run_stream()` + progressive `chat_update`, display name resolution fix.
- **Cost**: ~1.12M tokens across 17 subagent tasks (~67 min total agent runtime). Does not include Team Lead (main conversation) token usage.

## 2. Stories Delivered

| Story | Label | Mode | QA Bounces | Arch Bounces | Tax | Notes |
|-------|-------|------|------------|--------------|-----|-------|
| STORY-006-01 Drive Service | L2 | Fast Track | 0 | 0 | 0% | Foundation — drive_service + scan_service + config |
| STORY-006-04 Agent Drive Tool | L2 | Fast Track | 0 | 0 | 0% | read_drive_file tool + system prompt file catalog |
| STORY-006-02 Drive OAuth | L3 | Full Bounce | 0 | 1 | 5% | Arch caught: refresh token used as Bearer for userinfo |
| STORY-006-03 Knowledge CRUD | L3 | Full Bounce | 1 | 1 | 10% | QA+Arch: py39 compat, decrypt mock pattern, dead class |
| STORY-006-05 Frontend Drive | L3 | Full Bounce | 0 | 0 | 0% | Clean first pass. Layout refactor for TanStack Router |
| STORY-006-06 E2E Verification | L1 | Fast Track | 0 | 0 | 15% | Column names, OAuth scope, redirect, display name |

## 3. Bounce Analysis

### STORY-006-02 Architect Bounce
**Root cause**: `drive_status` endpoint passed the refresh token directly as a Bearer credential to Google's userinfo endpoint. Google requires an access token (obtained by exchanging the refresh token at the token endpoint). Mocked tests passed because `FakeDriveAsyncClient` returns success regardless of credential value.
**Lesson**: Protocol-level errors are invisible to hermetic mocks. Consider contract-shape assertions in mocks.

### STORY-006-03 QA + Architect Bounce
**Root cause 1 (QA)**: `drive_oauth.py` used Python 3.10+ `str | None` syntax without `from __future__ import annotations`, breaking on Python 3.9. Additionally, POST tests didn't mock `decrypt()`.
**Root cause 2 (Architect)**: Same decrypt mock issue caught independently.
**Lesson**: `from __future__ import annotations` breaks FastAPI's runtime type inspection — use `Optional[str]` instead for Python 3.9 compat.

## 4. E2E Findings (STORY-006-06)

Issues discovered during live testing that hermetic tests missed:

| Finding | Severity | Fix |
|---------|----------|-----|
| `owner_user_id` column doesn't exist (actual: `user_id`) | High | Renamed in drive_oauth.py + knowledge.py |
| `provider` column doesn't exist (actual: `ai_provider`) | High | Renamed in knowledge.py |
| `drive.file` scope blocks read of Picker-selected files via refresh token | High | Changed to `drive.readonly` |
| OAuth callback redirects to backend origin (port 8000) not frontend (5173) | Medium | Use `cors_origins` for redirect base URL |
| WorkspaceCard has no link to workspace detail page | Medium | Added `<Link>` component |
| No visible indexing progress indicator | Medium | Added pulsing amber progress banner |
| Slack display name empty-string fallback shows user ID | Medium | Strip + fallback chain fix |
| Agent outputs Markdown not Slack mrkdwn | Medium | Updated system prompt formatting rules |

## 5. Flashcards Flagged

| Flashcard | Status |
|-----------|--------|
| `drive.file` scope doesn't grant refresh-token access to Picker-selected files — use `drive.readonly` for backend file reads | Pending approval |
| `from __future__ import annotations` breaks FastAPI runtime type resolution on Python 3.9 — use `Optional[str]` | Pending approval |
| Google refresh tokens cannot be used as Bearer credentials for resource APIs — always exchange for access token first | Pending approval |
| Frontend worktrees need `npm install` before `vite build` — no `node_modules` in worktree | Pending approval |
| Column names in queries must match actual DB schema — hermetic mocks hide column-name typos | Pending approval |

## 6. Product Docs Affected

No `vdocs/_manifest.json` exists — skipped staleness detection.
Sprint delivered 5+ features with no vdocs. **Recommend vdoc init.**
