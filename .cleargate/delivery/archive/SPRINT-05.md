---
sprint_id: "SPRINT-05"
remote_id: "local:SPRINT-05"
source_tool: "vbounce-migration"
status: "Completed"
start_date: "2026-04-12"
end_date: "2026-04-13"
synced_at: "2026-04-24T00:00:00Z"
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-sprint-plan"
updated_at_version: "cleargate-migration-2026-04-24"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/archive/sprints/sprint-05/sprint-05.md`. Sprint Shipped in S-05. Body retains V-Bounce sprint-plan structure; not reshaped to ClearGate's PM-tool-pull template because V-Bounce plans encode more planning detail (§0 Readiness Gate, §4 Execution Strategy, §5 Metrics).

---
sprint_id: "sprint-05"
sprint_goal: "Close Release 1 — ship EPIC-003 Slice B workspace CRUD end-to-end."
dates: "2026-04-12 – 2026-04-13"
status: "Done"
delivery: "D-01"
confirmed_by: ""
confirmed_at: ""
---

# Sprint S-05 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry
- [x] **Human has confirmed this sprint plan** (2026-04-12)

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-003-B01: Backend Workspace Models](./STORY-003-B01-workspace-models.md) | EPIC-003 | L1 | Ready to Bounce | — |
| 2 | [STORY-003-B02: Backend Workspace Routes](./STORY-003-B02-workspace-routes.md) | EPIC-003 | L2 | Ready to Bounce | B01 |
| 3 | [STORY-003-B04: Frontend API Wrappers + Hooks](./STORY-003-B04-frontend-api-hooks.md) | EPIC-003 | L2 | Ready to Bounce | B01 |
| 4 | [STORY-003-B03: Backend Integration Tests](./STORY-003-B03-workspace-tests.md) | EPIC-003 | L2 | Ready to Bounce | B02 |
| 5 | [STORY-003-B05: Frontend Workspace List UI](./STORY-003-B05-team-workspace-list.md) | EPIC-003 | L2 | Ready to Bounce | B04 |
| 6 | [STORY-003-B06: Rename + Make Default](./STORY-003-B06-rename-make-default.md) | EPIC-003 | L2 | Ready to Bounce | B05 |
| 7 | [STORY-003-B07: Manual E2E Verification](./STORY-003-B07-manual-verification.md) | EPIC-003 | L1 | Ready to Bounce | B06 |

### Context Pack Readiness

**STORY-003-B01: Backend Workspace Models**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B02: Backend Workspace Routes**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B03: Backend Integration Tests**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B04: Frontend API Wrappers + Hooks**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B05: Frontend Workspace List UI**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B06: Rename + Make Default**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-003-B07: Manual E2E Verification**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Salvage Plan (from orphan branch `sprint/S-05-fasttrack` commit `e98d378`)

The aborted S-05-fasttrack sprint produced working code on branch `sprint/S-05-fasttrack` (commit `e98d378`). The following files are pre-validated and SHOULD be copied verbatim by the Developer agent during implementation:

| Story | File on branch | Salvage action |
|-------|---------------|----------------|
| B01 | `backend/app/models/workspace.py` | Copy verbatim |
| B01 | `backend/tests/test_workspace_models.py` | Copy verbatim |
| B01 | `backend/app/models/__init__.py` | Copy verbatim |
| B04 | `frontend/src/hooks/useWorkspaces.ts` | Copy verbatim |
| B04 | `frontend/src/hooks/useWorkspaces.test.tsx` | Copy + extend (add 1 more test — min 2 required by §4.1) |
| B04 | `frontend/src/lib/api.ts` | **DO NOT apply the branch diff** — it destructively rewrites S-04's `SlackTeam`/`SlackTeamsResponse`/`listSlackTeams`. Instead, ADDITIVELY copy only: `Workspace` interface, `apiPatch<T,R>()` helper, and the 5 new workspace wrappers. Leave all S-04 types/functions untouched. |

The Developer agent can retrieve salvage code via `git show e98d378:<path>`.

### Phase Plan
- **Phase 1**: B01 (Fast Track — salvaged L1, no dependencies)
- **Phase 2 (parallel after B01 merges)**: B02 + B04 (B02 = backend routes; B04 = frontend hooks — no shared files, can run in parallel worktrees)
- **Phase 3 (after B02 merges)**: B03 (integration tests require live routes)
- **Phase 4 (after B04 merges)**: B05 (frontend UI requires hooks)
- **Phase 5 (after B05 merges)**: B06 (rename + make-default extends workspace list UI)
- **Phase 6 (after B06 merges)**: B07 (manual E2E verification — no code changes)

### Merge Ordering
| Order | Story | Reason |
|-------|-------|--------|
| 1 | B01 | Pure model definitions — no runtime dependencies |
| 2 | B02 | Backend routes depend on B01 models |
| 3 | B04 | Frontend hooks — independent of B02 but logically follows models |
| 4 | B03 | Integration tests validate B02 routes |
| 5 | B05 | Frontend UI consumes B04 hooks |
| 6 | B06 | Rename + make-default extends B05 components |
| 7 | B07 | Manual verification only — no merge artifact |

### Shared Surface Warnings
| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `backend/app/models/__init__.py` | B01 (write), B02 (read) | Low — B01 merges first |
| `backend/app/main.py` | B02 (mount router) | Low — one new `include_router()` call |
| `frontend/src/lib/api.ts` | B04 (add wrappers + types) | **Medium** — MUST NOT modify existing S-04 exports (`SlackTeam`, `SlackTeamsResponse`, `listSlackTeams`). Additive changes only. |
| `frontend/src/routes/app.tsx` | B05 (add team→workspace navigation links in TeamCard) | **Medium** — touching S-04-shipped UI. Review carefully. |

### Execution Mode
| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| B01 | L1 | Fast Track | — | Salvaged, pure Pydantic schemas |
| B02 | L2 | Fast Track | — | Standard REST CRUD; Supabase transaction pattern established in S-04 |
| B03 | L2 | Full Bounce | — | Test-only story; QA validates the tests themselves |
| B04 | L2 | Fast Track | — | Salvaged hooks; additive api.ts changes only |
| B05 | L2 | Full Bounce | — | New route + components, touches S-04 `app.tsx` |
| B06 | L2 | Full Bounce | — | First-use TanStack optimistic updates |
| B07 | L1 | Fast Track | — | Manual verification, no code changes |

### ADR Compliance Notes
- B02: New routes mount at `/api/slack-teams/{team_id}/workspaces` and `/api/workspaces/{id}`. Coexists with S-04's `/api/slack/teams` (different router, different prefix). Consistent with ADR-024.
- B04: `apiPatch` helper follows the same pattern as existing `apiGet`/`apiPost` — no new libraries.
- B06: TanStack Query optimistic updates follow official docs — no custom state management. Consistent with ADR-022.

### Dependency Chain
| Story | Depends On | Reason |
|-------|-----------|--------|
| B02 | B01 | Routes import workspace models |
| B03 | B02 | Integration tests need live routes |
| B04 | B01 | Hooks reference `Workspace` type (models define the contract) |
| B05 | B04 | UI components use `useWorkspacesQuery` + `useCreateWorkspaceMutation` |
| B06 | B05 | Rename/make-default actions extend `WorkspaceCard` from B05 |
| B07 | B06 | E2E verification requires all features implemented |

### Risk Flags
- **S-04 regression risk (Medium):** B04 and B05 touch files delivered in S-04 (`lib/api.ts`, `app.tsx`). Salvage plan explicitly prohibits overwriting S-04 types. QA must verify S-04 Slack Teams page still works after B04 + B05 merges.
- **TanStack Router route-gen flake (Low):** B05 adds a new route file `app.teams.$teamId.tsx`. Known workaround: run `vite build` first after adding the route file, then `npm run build` (FLASHCARDS.md #9).
- **Supabase atomic transaction first-use (Low):** B02's `make-default` endpoint uses a transactional update (reset old default → set new default). Pattern is documented in B02 §3.3 but hasn't been used in Tee-Mo before. QA should test concurrent default-swap edge case.
- **Endpoint naming divergence (Accepted):** New workspace routes use `/api/slack-teams/...` (dash), while S-04's team list endpoint lives at `/api/slack/teams` (slash). User confirmed this coexistence is acceptable.

---

## 3. Sprint Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Route prefix for workspace endpoints | A: `/api/slack-teams` (dash), B: `/api/slack/teams/{id}/workspaces` (slash) | Affects B02, B04 | User | **Decided — Option A** |
| Orphan branch disposition | A: Delete after salvage, B: Keep as archive | Cleanup | User | **Decided — Option A** |
| Sprint scope | A: Full Slice B (B01–B07), B: Split across sprints | Release 1 target | User | **Decided — Option A** |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| B01 | Done | 0 | 0 | 1 | 0% | Salvaged from S-05-fasttrack |
| B02 | Done | 0 | 0 | 2 | 0% | CRUD routes + auth guard |
| B03 | Done | 0 | 0 | 13 | 0% | Comprehensive integration tests |
| B04 | Done | 0 | 0 | 2 | 0% | Salvaged hooks + additive api.ts |
| B05 | Done | 0 | 0 | 2 | 0% | Team detail page + workspace grid |
| B06 | Done | 0 | 0 | 3 | 0% | Optimistic make-default UI |
| B07 | Done | 0 | 0 | 0 | 0% | 87 backend + 26 frontend tests pass |
<!-- EXECUTION_LOG_END -->
