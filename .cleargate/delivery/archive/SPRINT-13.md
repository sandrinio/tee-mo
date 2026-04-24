---
sprint_id: "SPRINT-13"
remote_id: "local:SPRINT-13"
source_tool: "cleargate-native"
status: "Completed"
start_date: "2026-04-24"
end_date: "2026-04-24"
synced_at: "2026-04-24T00:00:00Z"
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-native-sprint"
updated_at_version: "cleargate-native-sprint"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# SPRINT-13 Plan

> First ClearGate-native sprint. Previous 12 sprints shipped under V-Bounce and are preserved in `.cleargate/delivery/archive/SPRINT-{01..12}.md`.

## Sprint Goal

**Close the loop on EPIC-018 by shipping the dashboard UI for Scheduled Automations, and fix a P1 auth bug that blocks any non-owner team member from reaching their own workspaces.** After this sprint, any Slack-team member can register, install, and manage both their automations and their workspaces from the dashboard end-to-end.

## 0. Sprint Readiness Gate

- [x] All stories reviewed — three 🟢 Low-ambiguity items, all referencing already-approved epics.
- [x] No 🔴 High-ambiguity items in scope (no spike needed).
- [x] Dependencies identified (see §3).
- [x] Risk flags reviewed (see §5).
- [x] **Human confirms this sprint plan before execution starts** ← GATE (approved 2026-04-24 via "start the sprint we have planned")

## 1. Active Scope

| # | Priority | Item | Parent | Complexity | Ambiguity | Status | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | P1 | [BUG-002: Team members can't access their workspaces under a shared Slack team](./BUG-002-slack-team-member-workspace-access.md) | EPIC-005 | L2 | 🟢 | Triaged | — |
| 2 | P0 | [STORY-018-05: Automations list + history UI](./STORY-018-05-ui-list-history.md) | EPIC-018 | L2 | 🟢 | Ready | — |
| 3 | P0 | [STORY-018-06: Automations create/edit modals UI](./STORY-018-06-ui-modals.md) | EPIC-018 | L2 | 🟢 | Ready | STORY-018-05 (shares the automations card wiring + API hooks) |

**Total: 3 items · 3× L2.** Backend for both stories is already live on main (shipped in SPRINT-12 squash-merge).

## 2. Context Pack Readiness

**BUG-002 — Team-member workspace access**
- [x] Root cause identified (assertion uses `teemo_slack_teams.owner_user_id` instead of `teemo_slack_team_members`).
- [x] Exact touch points enumerated (`workspaces.py` 2 call sites + `channels.py` 1 call site).
- [x] Failing test Gherkin spec'd in §5 of the bug.
- [x] Fix plan written (~20 lines net).
- [x] Out-of-scope list drafted (workspace-level `_assert_workspace_owner` helpers are correct — don't touch).

**STORY-018-05 — Automations list + history UI**
- [x] Backend API exists (`/api/workspaces/{id}/automations`, CRUD + `/executions` history per STORY-018-02).
- [x] Agent tools already manage state from Slack chat (STORY-018-04 shipped). UI is the last missing surface.
- [x] Workspace detail route is the host: `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` already renders sections for Drive/Key/Channels/Skills — automations section slots in alongside.
- [x] Design-guide reference available at `.cleargate/knowledge/design-guide.md` for card + chip styling.

**STORY-018-06 — Automations create/edit modals**
- [x] POST/PATCH backend endpoints exist; modals invoke them.
- [x] Modal pattern precedent: `CreateWorkspaceModal.tsx` (div overlay — jsdom does not support `<dialog>.showModal()` per FLASHCARD).
- [x] Schedule shape documented in agent system prompt (daily / weekdays / weekly / monthly / once — see `_AUTOMATIONS_PROMPT_SECTION` in `agent.py`); modal form surfaces the same options.
- [x] Acceptance includes a "Dry Run" action that hits `POST /api/workspaces/{id}/automations/{aid}/dry-run` and renders the output inline without posting to Slack.

## 3. Sequencing + Dependencies

1. **BUG-002 first.** Independent of EPIC-018. Lands fast (single-day). Unblocks manual QA of 018-05/06 as any team member, not just the owner.
2. **STORY-018-05 second.** Creates the `useAutomations` + `useAutomationExecutions` hooks, the `AutomationsSection` component, and the list + history chrome on the workspace page. Establishes the API-client surface and row component 018-06 reuses.
3. **STORY-018-06 third.** Builds `CreateAutomationModal` + `EditAutomationModal` on top of the hooks from 018-05. Dry Run + delete actions dispatch into the same row component.

**Parallel-eligibility:** Only BUG-002 runs fully in parallel with the others (different file space). 018-05 blocks 018-06 because of shared hook + component surfaces.

## 4. Execution Strategy

### Branching
- Sprint branch: `sprint/S-13` cut from current `main` (`a957832`).
- Per-story branches: `story/BUG-002-team-member-access`, `story/STORY-018-05-ui-list-history`, `story/STORY-018-06-ui-modals`.
- One commit per story (ClearGate convention): `feat(epic-005): BUG-002 ...`, `feat(epic-018): STORY-018-05 ...`, `feat(epic-018): STORY-018-06 ...`.
- Merge order follows §3 sequencing. DevOps merges sprint branch to `main` at sprint close.

### Four-agent loop
- **Architect** — draft `.cleargate/sprint-runs/SPRINT-13/plans/W01.md` covering all 3 items: per-story blueprints (files to touch, test scenarios), cross-story risks (especially the shared `AutomationsSection` + hooks surface between 018-05 and 018-06), and reuse opportunities.
- **Developer** — one story per commit. Must grep `.cleargate/FLASHCARD.md` for relevant tags (`#frontend`, `#auth`, `#vitest`) before implementing. BUG-002 fix must include the failing test FIRST (per bug's Gherkin spec) — that's the trigger for the bounce.
- **QA** — independent verification gate. Re-runs `npm test` (frontend) + `pytest` (backend). For BUG-002 specifically: verify the new test FAILS on a branch without the fix (commit prior to the assertion change), then passes post-fix.
- **Reporter** — at sprint close, writes `.cleargate/sprint-runs/SPRINT-13/REPORT.md` with the 6-section retrospective.

### Red-zone surfaces (3+ stories touch these)
- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — host route for 018-05 + 018-06. One story adds the `<AutomationsSection />` block; the second extends it with modal mount points. Team Lead inspects both merges.
- `frontend/src/lib/api.ts` — automation hooks added in 018-05, reused in 018-06.

### Shared surface warnings
- `backend/app/api/routes/workspaces.py` + `backend/app/api/routes/channels.py` touched by BUG-002 only. No other sprint item touches auth helpers.

## 5. Risk & Definition of Done

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| BUG-002 fix breaks owner-scoped flows that legitimately need owner-only | Low | High | Inspect every call site of the renamed helper; leave `_assert_workspace_owner` helpers untouched (workspace-level creator-scoped ownership stays). Full pytest suite on backend must pass. |
| Automations UI surfaces old `.execute()` Supabase pattern rather than new `execute_async()` | Low | Low | Scope note: frontend is API-client-side, not DB-side. Pattern concern lives in backend automations routes (filed as follow-up refactor candidate in the squash-merge commit message; NOT in SPRINT-13 scope). |
| Modal DOM pattern regresses jsdom test pollution | Medium | Medium | Follow the div-overlay pattern from `CreateWorkspaceModal.tsx` — the FLASHCARD rule says: no `<dialog>.showModal()` under Vitest + jsdom. |
| Schedule shape in modal diverges from agent tool signature | Low | Medium | Surface the same 5 occurrence types (daily / weekdays / weekly / monthly / once) with the same payload keys. Test fixture mirrors the spec in `_AUTOMATIONS_PROMPT_SECTION`. |

### Definition of Done
- [x] All 3 items pass QA on their own branches.
- [ ] Sprint branch `sprint/S-13` merges cleanly to `main`. — pending final merge (orchestrator will propose, human approves)
- [x] `npm test` (frontend Vitest) green — existing suite + new UI tests for 018-05 (7) + 018-06 (9). Pre-existing failures on `WorkspaceCard.test.tsx` + `KeySection.test.tsx` confirmed present on parent `3676a3e` — not regressions.
- [x] `pytest` (backend) green — 3 new BUG-002 tests, +0 regressions vs `main`. 4 modules excluded for pre-existing lifespan/asyncio deadlock (not a BUG-002 regression).
- [x] No regression on workspace-owner semantics — `_assert_workspace_owner` helpers in keys/drive_oauth/automations/knowledge untouched (QA verified via `git diff`).
- [ ] `cleargate wiki build` rebuilds cleanly. — pending orchestrator run
- [x] Reporter writes `.cleargate/sprint-runs/SPRINT-13/REPORT.md`. — written in Reporter-fallback mode (Reporter agent unavailable this session).
- [x] Flashcards recorded for any surprises discovered during execution. — 5 new cards on 2026-04-24.

## 6. Sprint Metrics & Goals

- **Stories planned:** 3 (1 bug + 2 stories)
- **Target first-pass success rate:** ≥ 67% (2/3 pass QA on first attempt)
- **Target Bug-Fix Tax:** 1 (the planned BUG-002 — anything else is drift)
- **Target Enhancement Tax:** 0 (no scope creep — further EPIC-018 polish goes to SPRINT-14 if needed)
- **Token budget:** no formal cap; reporter aggregates post-hoc

## 7. Out-of-Scope (deliberate)

- **EPIC-024 remaining stories** (STORY-024-02 background worker locks, STORY-024-04 fix legacy tests) — keep EPIC-018 focused; queue for SPRINT-14.
- **BUG-001** nav-aesthetics polish — ship as a side PR or bundle into SPRINT-14.
- **Automations backend refactor to `execute_async`** — follow-up from the SPRINT-12 squash-merge; not blocking UI work.
- **EPIC-018 scheduled-run observability / slack error channels** — future CR against EPIC-018.

---

## ClearGate Readiness Gate

**Final Status: ✅ Shipped** (closed 2026-04-24; see `.cleargate/sprint-runs/SPRINT-13/REPORT.md`)

- [x] Scope ≤ 4 items, all 🟢 ambiguity at entry.
- [x] Each item has a reachable parent (EPIC-005 for BUG-002, EPIC-018 for 018-05/06).
- [x] Red-zone surfaces identified and managed.
- [x] Dependencies documented with explicit blocker columns.
- [x] **Human approved this plan.**
