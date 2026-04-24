---
sprint_id: "SPRINT-14"
remote_id: "local:SPRINT-14"
source_tool: "cleargate-native"
status: "Completed"
start_date: "2026-04-24"
end_date: "2026-04-25"
synced_at: "2026-04-24T00:00:00Z"
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-post-sprint-13"
updated_at_version: "cleargate-post-sprint-13"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# SPRINT-14 Plan

> Second ClearGate-native sprint. Picks up the EPIC-018 loose ends (timezone awareness on both dashboard and Slack-chat surfaces) and restores full backend test signal that was partially excluded in SPRINT-13.

## Sprint Goal

**Close EPIC-018's timezone loop end-to-end (dashboard + Slack chat) and restore full backend test signal so EPIC-024 can finish in SPRINT-15 without flying blind.** After this sprint, every automation — whether created via the dashboard or a Slack chat message — is saved in the user's actual local zone, and `pytest backend/tests/` runs the full suite without lifespan deadlocks or legacy-mock AssertionErrors.

## 0. Sprint Readiness Gate

- [x] All stories reviewed — four 🟢 Low-ambiguity items, all referencing already-approved epics.
- [x] No 🔴 High-ambiguity items in scope (no spike needed).
- [x] Dependencies identified (see §3).
- [x] Risk flags reviewed (see §5).
- [x] **Human confirms this sprint plan before execution starts** ← GATE (approved 2026-04-24 via "go ahead please")

## 1. Active Scope

| # | Priority | Item | Parent | Complexity | Ambiguity | Status | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | P0 | [STORY-024-05: TestClient lifespan unblock](./STORY-024-05-testclient-lifespan-unblock.md) | EPIC-024 | L2 | 🟢 | Draft | — |
| 2 | P0 | [STORY-024-04: Fix legacy backend test tech-debt](./STORY-024-04-fix-legacy-tests.md) | EPIC-024 | L1 | 🟢 | Draft | STORY-024-05 (both touch `test_channel_binding.py`) |
| 3 | P1 | [STORY-018-07: Dashboard modal browser-tz default](./STORY-018-07-frontend-browser-tz.md) | EPIC-018 | L1 | 🟢 | Draft | — |
| 4 | P1 | [STORY-018-08: Agent knows scheduler's timezone (Slack chat)](./STORY-018-08-agent-scheduler-tz.md) | EPIC-018 | L2 | 🟢 | Draft | — |

**Total: 4 items · 2× L1 · 2× L2.** Lean sprint — every item has a concrete file list and a proven pattern in the codebase.

## 2. Context Pack Readiness

**STORY-024-05 — TestClient lifespan unblock**
- [x] Root cause identified (`main.py:61-110` lifespan spawns 3 cron tasks that never return under pytest-asyncio auto mode).
- [x] Exact file list + line refs enumerated in the story (`test_workspace_routes.py`, `test_channel_binding.py`, `test_channel_enrichment.py`, `test_automations_routes.py`).
- [x] Pattern proven in SPRINT-13 via `test_workspaces_team_member_access.py:317` and `test_auth_routes.py:72`.
- [x] Flashcard already logged (2026-04-24 · `#test-harness #fastapi`) — the story formalizes R4 by turning it into a durable card.

**STORY-024-04 — Fix legacy test tech-debt**
- [x] 4 files + specific fixes itemized (google_picker_api_key default, drive.readonly scope, teemo_slack_teams mock seeding × 2).
- [x] No app-code changes — test mock fixes only (explicit §1.3 out-of-scope boundary).
- [x] Sequenced AFTER 024-05 because `test_channel_binding.py` appears in both — lifespan refactor first, mock assertions second.

**STORY-018-07 — Dashboard modal browser tz**
- [x] Primary file: `frontend/src/components/workspace/AddAutomationModal.tsx`.
- [x] Reference pattern lives in `new_app/frontend/src/components/settings/AutomationsTab.tsx:94` (the `DETECTED_TZ` constant).
- [x] Backend contract unchanged — still `timezone: string` IANA on the create payload.
- [x] Vitest expectations codified (2 component tests — default + non-curated zone merged).

**STORY-018-08 — Agent scheduler tz**
- [x] Surface-of-change concrete: `slack_dispatch.py:~338` (pluck `user.tz` from `users_info`), `agent.py` `AgentDeps`, `_build_system_prompt`, `create_automation` tool.
- [x] `AgentDeps` extension precedent: `citations` field, use `getattr(deps, "sender_tz", "UTC")` to tolerate old fakes.
- [x] 5 Gherkin scenarios + 6 test targets (4 unit + 2 integration) spec'd.
- [x] Slack scope `users:read` already present (name-resolution path uses it) — no scope bump.

## 3. Sequencing + Dependencies

1. **STORY-024-05 first.** Its refactor unblocks the full pytest suite, including `test_channel_binding.py` which 024-04 also edits. Landing 024-05 before 024-04 means QA for 024-04 can run its file under the default pytest collection path rather than a side-invocation.
2. **STORY-024-04 second.** Strictly mock-shape fixes in the same directory. Once the lifespan deadlock is gone, these assertions either pass or fail deterministically — the signal is clean.
3. **STORY-018-07 in parallel with 1/2** (different file space — pure frontend). Can be picked up concurrently by Developer if backend stories are in QA.
4. **STORY-018-08 last.** Depends on the backend test suite running cleanly (024-05) to validate the new `slack_dispatch` → `AgentDeps` → prompt wiring; its tests extend `test_automation_tools.py` and `test_slack_dispatch.py`, neither of which is in the 024-05 hang list — but bundling late gives us post-024-05 confidence.

**Parallel-eligibility:** STORY-018-07 is fully parallel (frontend-only). STORY-024-05 → 024-04 is strictly sequential (shared file). STORY-018-08 is independent of 018-07 (different tier — agent vs modal) so can begin as soon as Developer picks it up.

## 4. Execution Strategy

### Branching
- Sprint branch: `sprint/S-14` cut from current `main` (`4325ad1`).
- Per-story branches:
  - `story/STORY-024-05-lifespan-unblock`
  - `story/STORY-024-04-legacy-tests`
  - `story/STORY-018-07-browser-tz`
  - `story/STORY-018-08-agent-tz`
- One commit per story (ClearGate convention). Commit prefixes:
  - `refactor(epic-024): STORY-024-05 ...`
  - `fix(epic-024): STORY-024-04 ...`
  - `feat(epic-018): STORY-018-07 ...`
  - `feat(epic-018): STORY-018-08 ...`
- Merge order follows §3 sequencing. DevOps merges sprint branch to `main` at sprint close under explicit human approval (matching SPRINT-13 squash-merge pattern).

### Four-agent loop
- **Architect** — draft `.cleargate/sprint-runs/SPRINT-14/plans/W01.md` covering all 4 items: per-story blueprints (files to touch, exact test scenarios), cross-story risks (shared `test_channel_binding.py` between 024-04/05; shared `agent.py` surface between 018-08 and prior 018-0x work), and reuse opportunities.
- **Developer** — one story per commit. Must grep `.cleargate/FLASHCARD.md` for relevant tags (`#test-harness`, `#fastapi`, `#vitest`, `#llm #prompt`) before implementing. For 018-08 specifically, the `#llm #slack` flashcard about thread-history anchoring is load-bearing — test in a fresh thread if you're verifying the prompt change live.
- **QA** — independent verification gate. For 024-05: re-run the specific 4-file pytest invocation AND the full `backend/tests/` suite and confirm no hang. For 024-04: post-refactor counts per module match pre-refactor. For 018-07: run Vitest `AutomationsSection.test.tsx` + new modal tz test. For 018-08: run `test_automation_tools.py` + `test_slack_dispatch.py` under the now-unblocked pytest config.
- **Reporter** — at sprint close, writes `.cleargate/sprint-runs/SPRINT-14/REPORT.md` with the 6-section retrospective. Remember to write `.cleargate/sprint-runs/.active = SPRINT-14` at kickoff — without it the SubagentStop hook drops every token-ledger row (flashcard 2026-04-24 `#reporting #hook`).

### Red-zone surfaces (3+ stories touch these)
- None at 3+. Shared-surface warnings in §Shared surface warnings below.

### Shared surface warnings
- `backend/tests/test_channel_binding.py` — edited by **both** STORY-024-05 (lifespan construction) and STORY-024-04 (teemo_slack_teams mock seeding). Developer on 024-04 must rebase on top of merged 024-05 before starting; Team Lead inspects both diffs together.
- `backend/app/agents/agent.py` — STORY-018-08 only in this sprint, but it's the hottest file in the repo (EPIC-007, EPIC-015, EPIC-018 all touch it). Developer reads the flashcard line on keyword-gated prompt sections (2026-04-24 `#llm #prompt`) before editing.
- `frontend/src/components/workspace/AddAutomationModal.tsx` — STORY-018-07 only; no conflict with any other sprint item.

## 5. Risk & Definition of Done

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 024-05 pattern misapplied → some tests pass with lifespan bypass but hide a real startup bug | Low | Medium | Scope note: these are mock-heavy unit tests; the bypass is correct per SPRINT-13 flashcard. Integration-tier tests (outside the 4-file list) still run with lifespan. |
| 024-04 mock seeding hides a real regression — `FAKE_SLACK_TEAM_ROW` goes stale vs. current schema | Low | Medium | Re-verify column names against the latest migration at implementation time (standing flashcard lesson: "hermetic Supabase mocks don't validate column names"). |
| 018-07 browser-tz detection unavailable under jsdom → new Vitest test flakes | Medium | Low | R1 explicitly requires a `try/catch` → `'UTC'` fallback. Gherkin scenario 3 covers this path. Use `vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions')` to inject deterministic tz per test. |
| 018-08 prompt change bleeds into non-scheduling conversations → users see unwanted "Scheduled for …" confirmations in normal replies | Medium | Medium | R4 rule is phrased for scheduling context ("Whenever you schedule, confirm, or reason about a specific time"). QA checks a non-scheduling prompt does not trigger spurious tz citations. Prompt diff reviewed by Architect. |
| 018-08 breaks pre-existing `AgentDeps` construct-sites in tests | Low | Low | R2 mandates default value `sender_tz: str = "UTC"` so no test needs to pass the field. `getattr(deps, "sender_tz", "UTC")` at read-site covers hand-rolled `SimpleNamespace` fakes. |

### Definition of Done
- [ ] All 4 items pass QA on their own branches.
- [ ] Sprint branch `sprint/S-14` merges cleanly to `main` (squash-merge under explicit human approval, pushed to `origin/main`).
- [ ] `pytest backend/tests/` — full suite runs without hangs; 024-05 four-file target <60s; 024-04 target modules all green.
- [ ] `npm test` (frontend Vitest) — new 018-07 modal tz tests pass alongside existing suite.
- [ ] `pytest backend/tests/test_automation_tools.py backend/tests/test_slack_dispatch.py` — 018-08 new tests pass + 0 regressions.
- [ ] No regression on workspace-owner semantics, no regression on EPIC-018 dashboard UI, no regression on EPIC-007 agent loop.
- [ ] `cleargate wiki build` rebuilds cleanly (or wiki-ingest agent processes all SPRINT-14 work items when CLI unavailable, matching SPRINT-13 fallback).
- [ ] Reporter writes `.cleargate/sprint-runs/SPRINT-14/REPORT.md` — 6-section retrospective.
- [ ] Flashcards recorded for any surprises discovered during execution (including the formal 024-05 `#test-harness #fastapi` card per R4).
- [ ] Live-testing window — any post-squash hotfixes logged in REPORT.md §Post-ship hotfixes.

## 6. Sprint Metrics & Goals

- **Stories planned:** 4 (0 bug + 4 stories)
- **Target first-pass success rate:** ≥ 75% (3/4 pass QA on first attempt)
- **Target Bug-Fix Tax:** 0 (no planned bugs — the 024-05/04 work is tech-debt, not regression fixes)
- **Target Enhancement Tax:** 0 (no scope creep — further EPIC-024 goes to SPRINT-15; BUG-001 nav polish ships as a side PR if bored)
- **Token budget:** no formal cap; Reporter aggregates post-hoc. Remember to write `.cleargate/sprint-runs/.active = SPRINT-14` at kickoff so the SubagentStop hook captures rows.

## 7. Out-of-Scope (deliberate)

- **STORY-024-02** (background worker locks on wiki/drive crons) — higher blast-radius on shipped crons; deserves its own focused sprint with live-ops validation. Queued for SPRINT-15.
- **BUG-001** nav glassmorphism polish — P3 visual polish, `approved: false`; ship as a side PR mid-sprint if velocity allows, otherwise SPRINT-15.
- **Root-cause lifespan fix** (env-gated cron disable in tests) — deliberately deferred by STORY-024-05 §1.3; lands as a follow-up CR if the 024-05 pattern proves insufficient.
- **Dashboard-side workspace default timezone** — mentioned in STORY-018-08 §1.3; not blocking.
- **Full IANA tz searchable selector** (e.g. `react-timezone-select`) — STORY-018-07 §1.3 explicitly defers this.
- **EPIC-018 observability / per-run slack error channels** — still a future CR.

---

## ClearGate Readiness Gate

**Current Status: 🟢 Approved + Active.** Human approved 2026-04-24.

- [x] Scope ≤ 4 items, all 🟢 ambiguity at entry.
- [x] Each item has a reachable parent (EPIC-018 for 018-07/08, EPIC-024 for 024-04/05).
- [x] Red-zone surfaces identified and managed (see §4 Shared surface warnings).
- [x] Dependencies documented with explicit blocker columns.
- [x] **Human approval** — 2026-04-24.
