---
sprint_id: "S-08"
sprint_goal: "Ship EPIC-006 — Google Drive OAuth, file indexing with AI descriptions, read_drive_file agent tool, frontend Picker. Complete the demo pipeline: register → workspace → Slack → Drive → @mention → answer from file."
dates: "2026-04-13"
status: "Achieved"
total_tokens_used: "N/A (not instrumented)"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
---

# Sprint Report: S-08

## 1. What Was Delivered

### User-Facing (Accessible Now)

- Google Drive OAuth connect/disconnect on WorkspaceCard + workspace detail page
- Google Picker file selector — pick files from Drive and add to knowledge base
- Knowledge file list with AI-generated descriptions, index/delete, 15-file cap enforcement + progress banner
- WorkspaceCard link to workspace detail page

### Internal / Backend (Not Directly Visible)

- `drive_service.py` — 6 MIME types (Docs/Sheets/Slides/PDF/Word/Excel) extraction + 50K char truncation
- `scan_service.py` — AI `ai_description` generation via scan-tier model at index time; self-healing hash check re-generates on content change
- Drive OAuth: `GET /api/workspaces/:id/drive/connect`, `/callback`, `/status`, `/disconnect` — offline refresh token, `drive.readonly` scope
- Knowledge CRUD: `GET/POST/DELETE /api/workspaces/:id/knowledge` — 15-file cap + BYOK gate + async lock
- Picker token endpoint + `read_drive_file` agent tool (MIME routing, file catalog in system prompt)

### Not Completed

None. All 6 stories delivered. Core EPIC-006 complete (5 enhancement stories deferred to S-10).

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| STORY-006-01: Drive service + scan service | EPIC-006 | L2 | Done | 0 | 0 | 0% | — |
| STORY-006-04: Agent read_drive_file tool | EPIC-006 | L2 | Done | 0 | 0 | 0% | — |
| STORY-006-02: Drive OAuth routes | EPIC-006 | L2 | Done | 0 | 1 | 5% | Bug Fix |
| STORY-006-03: Knowledge CRUD + Picker token | EPIC-006 | L2 | Done | 1 | 1 | 10% | Bug Fix |
| STORY-006-05: Frontend Drive + Picker UI | EPIC-006 | L2 | Done | 0 | 0 | 0% | — |
| STORY-006-06: E2E verification | EPIC-006 | L1 | Done | 0 | 0 | 15% | Bug Fix |

### Story Highlights

- **STORY-006-02 (Arch bounce)**: `drive_status` endpoint was using refresh token as Bearer credential for Google userinfo — invalid. Fixed: must exchange refresh token → access token first. Flashcard recorded.
- **STORY-006-03 (QA + Arch bounce)**: Python 3.9 compat issue (`from __future__ import annotations` breaks FastAPI runtime type resolution); dead class removed; decrypt mock pattern fixed. Flashcards recorded.
- **STORY-006-06 (15% correction tax — E2E)**: Several fixes during live verification: `drive.file` scope doesn't grant refresh-token access to Picker files (switched to `drive.readonly`); column name mismatches (`owner_user_id` vs `user_id`, `provider` vs `ai_provider`) — hermetic mocks had hidden these. Flashcards recorded.

### 2.1 Change Requests

None formal. All corrections found during standard QA/Arch/E2E passes.

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value |
|--------|-------|
| Stories Planned | 6 |
| Stories Delivered | 6 |
| Stories Escalated | 0 |
| Total QA Bounces | 1 |
| Total Architect Bounces | 2 |
| Bounce Ratio | 50% (3/6 stories bounced) |
| Average Correction Tax | ~5% |
| Bug Fix Tax | ~5% |
| Enhancement Tax | 0% |
| First-Pass Success Rate | 50% |
| Total Tests Written | ~120+ (30+17+34+26+10+E2E fixes) |

---

## 4. Lessons Learned

| Source | Lesson | Recorded? | When |
|--------|--------|-----------|------|
| STORY-006-06 | drive.file scope does not grant refresh-token access to Picker-selected files — use drive.readonly | Yes | Sprint close |
| STORY-006-03 | from __future__ import annotations breaks FastAPI runtime type resolution | Yes | Sprint close |
| STORY-006-02 | Google refresh tokens cannot be used as Bearer credentials — exchange for access token first | Yes | Sprint close |
| STORY-006-06 | Hermetic mocks hide column-name mismatches — verify against live schema | Yes | Sprint close |
| STORY-006-05 | Frontend worktrees need npm install before vite build | Yes | Sprint close |

---

## 5. Retrospective

### What Went Well

- Core Drive pipeline shipped and E2E verified. Full demo path (register → workspace → Slack → Drive → @mention → answer) is live.
- Architect review caught a real security issue (refresh token as Bearer) before it reached production.
- 120+ tests across 6 stories — most comprehensive test suite added in a single sprint.

### What Didn't Go Well

- 50% first-pass rate — highest bounce ratio in the project. Root cause: Google OAuth has many subtle API contract gotchas (`drive.readonly` vs `drive.file`, column names, py3.9 compat) that the story specs didn't fully capture.
- Hermetic mock pattern hiding column-name mismatches is a persistent risk. Multiple prod-only failures would have been caught earlier with a live schema smoke probe.

### Framework Self-Assessment

#### Templates

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| OAuth integration stories need explicit "verify column names against live schema" step in §3 | QA | Friction | Add live-schema verification checklist to story §3 for any story adding new Supabase queries |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-15 | Sprint Report generated retroactively at S-11 close audit | Team Lead |
