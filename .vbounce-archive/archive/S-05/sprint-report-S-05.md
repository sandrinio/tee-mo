---
sprint_id: "S-05"
sprint_goal: "Close Release 1 — ship EPIC-003 Slice B workspace CRUD end-to-end."
dates: "2026-04-12"
status: "Achieved"
release_tag: "v0.5.0"
merge_commit: "f5839c1"
roadmap_ref: "product_plans/strategy/roadmap.md"
---

# Sprint Report: S-05

## 1. What Was Delivered

### User-Facing (Accessible Now)

- **Team detail page** at `/app/teams/$teamId` — click a Slack team card to see all workspaces in that team
- **Create workspace** — "+ New Workspace" button opens a modal; workspace appears immediately in the list
- **Rename workspace** — "Rename" button on each workspace card opens an inline modal
- **Make default** — "Make Default" button on non-default workspaces; optimistic UI moves the "Default" badge instantly with rollback on error
- **Navigation** — clicking a team card on `/app` navigates to the workspace list; "← Teams" breadcrumb navigates back

### Internal / Backend (Not Directly Visible)

- 5 REST endpoints: `GET/POST /api/slack-teams/{team_id}/workspaces`, `GET/PATCH /api/workspaces/{id}`, `POST /api/workspaces/{id}/make-default`
- `assert_team_owner` authorization guard — prevents cross-user workspace access (403)
- Pydantic workspace models with secret-field exclusion (no `encrypted_api_key` in responses)
- 6 TanStack Query hooks with cache invalidation and optimistic update support
- `apiPatch<T,R>()` generic helper added to `frontend/src/lib/api.ts`

### Not Completed

- None — all 7 stories delivered.

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| B01 — Workspace Models | EPIC-003 | L1 | Done | 0 | 0 | 0% | — |
| B02 — Workspace Routes | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| B03 — Integration Tests | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| B04 — Frontend API Hooks | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| B05 — Workspace List UI | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| B06 — Rename + Make Default | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| B07 — Manual Verification | EPIC-003 | L1 | Done | 0 | 0 | 0% | — |

### Story Highlights

- **B01**: Salvaged verbatim from aborted S-05-fasttrack branch. 3 files, zero changes needed.
- **B02**: First use of Supabase two-step update for atomic default swap. `assert_team_owner` guard established as reusable pattern.
- **B04**: Salvaged hooks + additive-only `api.ts` changes. No S-04 regression.
- **B05**: jsdom doesn't implement `HTMLDialogElement.showModal()` — used div overlay instead.
- **B06**: First use of TanStack Query optimistic updates with `onMutate`/`onError`/`onSettled` rollback.

### 2.1 Change Requests

| Story | Category | Description | Impact |
|-------|----------|-------------|--------|
| B05 | Bug | TanStack Router: app.tsx had no `<Outlet>` — child route rendered blank page | Fix: split app.tsx into layout + app.index.tsx. No bounce reset. |
| B04 | Bug | Frontend API URLs didn't match backend route paths (salvage code had wrong URLs) | Fix: corrected 3 endpoint URLs in api.ts. No bounce reset. |

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value | Notes |
|--------|-------|-------|
| **Stories Planned** | 7 | |
| **Stories Delivered** | 7 | |
| **Stories Escalated** | 0 | |
| **Total QA Bounces** | 0 | Fast Track mode for B01/B02/B04/B07 |
| **Total Architect Bounces** | 0 | |
| **Bounce Ratio** | 0% | |
| **Average Correction Tax** | 0% | 🟢 |
| **First-Pass Success Rate** | 100% | |
| **Total Tests Written** | 23 | 14 backend + 9 frontend |
| **Tests per Story (avg)** | 3.3 | |
| **Merge Conflicts** | 0 | Worktree isolation worked perfectly |

### Post-Merge Validation

- Backend: **87 passed**, 2 warnings (pre-existing supabase deprecation)
- Frontend: **26 passed**
- Build: clean (`built in 228ms`, pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` warning)

---

## 4. Lessons Learned

| Source | Lesson | Recorded? |
|--------|--------|-----------|
| B02 Dev Report | Worktree `.env` placement: `config.py` resolves from `parents[3]` of config file — agents must copy `.env` to worktree root | Pending |
| B05 Dev Report | jsdom doesn't implement `HTMLDialogElement.showModal()` — use div overlay or polyfill in test-setup.ts | Pending |
| B06 Dev Report | `tsc -b` catches missing vitest globals imports even with `globals: true` — add `"types": ["vitest/globals"]` to tsconfig | Pending |
| Manual QA | TanStack Router layout routes MUST render `<Outlet>` for children — a file-based route with children is automatically a layout | Pending |
| Manual QA | Salvage code URLs must be verified against actual backend route paths — copy-paste from an orphan branch can silently use wrong endpoints | Pending |

---

## 5. Retrospective

### What Went Well

- **Salvage plan worked**: B01 and B04 reused code from the aborted S-05-fasttrack branch with minimal changes. Saved significant implementation time.
- **Parallel worktrees**: B02+B04 and B03+B05 ran in parallel with zero conflicts. Worktree isolation is proven at scale now.
- **0% bounce ratio**: All 7 stories passed on first attempt. Clean specs + low ambiguity + salvaged code contributed.
- **Manual QA caught real bugs**: The router outlet issue and API URL mismatch would have been invisible to automated tests (mocked). Live testing is essential.

### What Didn't Go Well

- **Salvage API URLs wrong**: The orphan branch `api.ts` used flat `/api/workspaces?team_id=` paths instead of the nested `/api/slack-teams/{teamId}/workspaces` pattern decided in sprint planning. The Developer agent copied them without cross-checking the backend.
- **Layout route gap**: Neither the Developer nor Team Lead caught that `app.tsx` needed `<Outlet>` — this is a fundamental TanStack Router concept that should have been in the task prompt.

### Framework Self-Assessment

#### Process Flow

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| Salvage code isn't validated against current backend contract | Team Lead | Friction | Add "verify salvage URLs match backend routes" step to salvage protocol in agent-team SKILL.md |
| Layout route + Outlet pattern not mentioned in FLASHCARDS.md or sprint context | Team Lead | Friction | Add a FLASHCARD: "TanStack Router file-based routes with children are layout routes — parent MUST render `<Outlet>`" |

#### Agent Handoffs

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| Dev agent for B04 wasn't given the actual backend route paths to verify against | Team Lead | Friction | When salvaging frontend code, include the backend route table in the developer prompt so URLs can be cross-checked |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint Report generated | Team Lead |
