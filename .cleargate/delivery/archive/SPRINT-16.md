---
sprint_id: "SPRINT-16"
remote_id: "local:SPRINT-16"
source_tool: "cleargate-native"
status: "Completed"
start_date: "2026-04-25"
end_date: null
activated_at: "2026-04-25T00:00:00Z"
human_approved_at: "2026-04-25T00:00:00Z"
completed_at: "2026-04-26T02:35:00Z"
shipping_commit: "7fc4ba6"
synced_at: null
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-post-sprint-15"
updated_at_version: "cleargate-post-sprint-15"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# SPRINT-16 Plan

> Single-epic sprint: ship EPIC-025 (Workspace v2 redesign — Variation B sticky tabs + scrollspy) end-to-end. Six 🟢 stories under EPIC-025, plus one approved P3 side (CR-001 channel picker search). All chrome-only except a small backend authorization addition on `DELETE /workspaces/{id}` (creator-OR-team-owner per OQ-2 = C). Per owner directive at S-15 close: "we must run all in 1 sprint." Approved 2026-04-25.

> **BUG-001 dropped from scope at kickoff pre-flight (2026-04-25):** architect verified `AppNav.tsx` already contains every implementation marker on `main`. Resolved without commit; freed slot not re-allocated.

## Sprint Goal

**Replace the long stacked workspace settings page (`frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`, 1235 LOC) with the sticky-tab + scrollspy shell from `design_handoff_workspace_redesign/`. Every existing module's behavior preserved verbatim; Persona stays as today (no voice presets); Slack module is info-only (no Reinstall); Danger zone re-tightens to owner-only on DELETE.** After this sprint, the route file drops to ~150 LOC, every module is one click away via the sticky tab bar, deep links `#tm-{moduleId}` work cold-load, and the legacy stacked layout is deleted.

## 0. Sprint Readiness Gate

- [x] All items reviewed — six 🟢 Low-ambiguity stories under one approved epic (EPIC-025 🟢) + one 🟢 approved P3 side (CR-001). BUG-001 closed at pre-flight (already shipped on `main`).
- [x] No 🔴 High-ambiguity items in scope.
- [x] Dependencies identified (see §3).
- [x] Risk flags reviewed (see §5).
- [x] **Human confirmed this sprint plan 2026-04-25.**

## 1. Active Scope

| # | Priority | Item | Parent | Complexity | Ambiguity | Status | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | P1 | [STORY-025-01: Shell foundation](./STORY-025-01-shell-foundation.md) | EPIC-025 | L2 | 🟢 | Draft | — |
| 2 | P1 | [STORY-025-02: Connections migration](./STORY-025-02-connections-migration.md) | EPIC-025 | L2 | 🟢 | Draft | 025-01 (needs `<ModuleSection />` + registry) |
| 3 | P1 | [STORY-025-03: Knowledge migration](./STORY-025-03-knowledge-migration.md) | EPIC-025 | L1 | 🟢 | Draft | 025-01 |
| 4 | P1 | [STORY-025-04: Behavior migration](./STORY-025-04-behavior-migration.md) | EPIC-025 | L1 | 🟢 | Draft | 025-01 |
| 5 | P1 | [STORY-025-05: Workspace + owner gate](./STORY-025-05-workspace-owner-gate.md) | EPIC-025 | L1 | 🟢 | Draft | 025-01 |
| 6 | P1 | [STORY-025-06: Mobile + cutover](./STORY-025-06-mobile-cutover.md) | EPIC-025 | L2 | 🟢 | Draft | 025-02..05 (cuts over after all bodies migrated) |
| 7 | P3 | [CR-001: Channel picker search](./CR-001-channel-picker-search.md) | EPIC-005 | L1 | 🟢 | Approved | 025-02 (shared file `ChannelSection.tsx` — lands AFTER 025-02) |
| ~~8~~ | ~~P3~~ | ~~BUG-001~~ | ~~EPIC-023~~ | — | — | **Resolved at pre-flight** | Already shipped on `main` (architect verified during W01 blueprint, OQ-1 = a). No commit. |

**Total: 7 items — 6 stories under EPIC-025 (3× L1 · 3× L2) + 1 CR (L1).** BUG-001 dropped from active scope at kickoff (verified shipped during pre-flight). ~1.75× S-15 item count.

### Pre-sprint hygiene (no engineering — bookkeeping)
- [x] Mark EPIC-025 status `Active` (done at sprint draft time).
- [x] CR-001 `approved: true` set 2026-04-25.
- [x] BUG-001 verified shipped during W01 pre-flight; marked `Resolved` 2026-04-25 (OQ-1 = a). Removed from active scope.
- [x] OQ-2 resolved 2026-04-25 = (C) Creator OR team-owner OR semantics on DELETE. STORY-025-05 §1.2/§2.1/§3.2 rewritten accordingly.
- [x] OQ-3 resolved 2026-04-25 = (C) Add `slack_domain` field on workspace GET (piggybacks on 025-05's `is_owner` change). STORY-025-02 SlackSection caption + STORY-025-05 GET response both updated.
- [x] `.cleargate/sprint-runs/.active = SPRINT-16` (already set).
- [ ] Run wiki-ingest fallback so the index reflects EPIC-025 + 6 stories + CR-001 + SPRINT-16. (BUG-001 ingested with `Resolved` status.)

## 2. Context Pack Readiness

**STORY-025-01 — Shell foundation**
- [x] All 6 new files enumerated in §3.1. No existing primitives modified.
- [x] Scrollspy testability verified: jsdom 22+ supports `IntersectionObserver` and basic scroll events; tests assert state, not visual scroll.
- [x] Deep-link cold-load timing verified: `useLayoutEffect` after first paint, RAF-guarded.

**STORY-025-02 — Connections migration**
- [x] DriveSection currently inline at `app.teams.$teamId.$workspaceId.tsx:197-252`; KeySection + ChannelSection live in `frontend/src/components/workspace/`.
- [x] No new mutations or hooks — all four modules consume existing hooks unchanged.
- [x] Slack module info source: `useSlackInstallQuery` already in scope via team route; if not exposed at workspace scope, use the workspace's `team_id` + the existing `/api/teams/{id}/slack` endpoint or surface the team install row via the workspace endpoint already used by the route.

**STORY-025-03 — Knowledge migration**
- [x] PickerSection + KnowledgeList currently inline at route lines 301-678. Pure code move + chrome update.
- [x] All existing useKnowledge / useUploadKnowledgeMutation / useReindexKnowledgeMutation hooks preserved unchanged.
- [x] TruncationToast moves with FilesSection; rendering position inside the new module card verified visually against handoff.

**STORY-025-04 — Behavior migration**
- [x] PersonaSection inline at route lines 739-806. Existing textarea + Save flow shipped (mig 013, EPIC-019). NO voice preset changes — Persona stays as-is per epic §6 Q2 resolution.
- [x] SkillsSection inline at route lines 831-875. Read-only list per ADR-023 — no Edit affordance.
- [x] AutomationsSection lives in its own file — only the empty-state JSX changes; populated state and tests untouched.

**STORY-025-05 — Workspace + owner gate**
- [x] DELETE workspace handler exists at `backend/app/api/routes/workspaces.py` (search for the existing delete route). Currently uses `assert_team_member` (BUG-002 fix).
- [x] Owner role lookup: `teemo_slack_team_members` has `(user_id, team_id, role)` columns. Helper queries by all three with `role=eq.owner`.
- [x] Frontend `is_owner` field added to workspace GET response — type extension in `frontend/src/lib/api.ts`.

**STORY-025-06 — Mobile + cutover**
- [x] Mobile pattern source: `/app/teams/$teamId` route + `WorkspaceCard.tsx` — both use plain Tailwind `flex` / `grid` with no special mobile primitive. Pattern to replicate for tab bar: `overflow-x-auto -mx-4 px-4 md:mx-0 md:overflow-visible`.
- [x] Route file LOC target: drop from ~1235 to ~150. All section bodies extracted by 025-02..05.
- [x] Existing route test file location verified — only minor structural updates needed.

## 3. Sequencing + Dependencies

1. **STORY-025-01 first.** Foundation. Unblocks every other story. Shell + registry + scrollspy + deep-linking + status framework. Ships placeholder cards behind a feature branch — does NOT delete the legacy layout yet.
2. **STORY-025-02..05 can land in parallel** once 025-01 ships. Each migrates one module group. Different file spaces — zero conflict potential except in `moduleRegistry.ts` (shared) and `app.teams.$teamId.$workspaceId.tsx` (shared). Sequential commits to those resolve cleanly. **Recommendation: pull 025-05 forward in the parallel batch** so its `slack_domain` + `is_owner` GET fields are merged before 025-02 SlackSection consumes them (025-02 is forward-compatible if 025-05 hasn't landed, but the live caption only lights up once 025-05 is in).
3. **CR-001 lands AFTER 025-02.** Same file (`ChannelSection.tsx`). Adding the search input + count badge above the new divider list — trivial after 025-02 establishes the new chrome. NOT before 025-02 (would force CR-001 to redo its work after the re-skin).
4. **STORY-025-06 last.** Mobile responsive treatment + delete legacy stacked JSX from the route + delete `SetupStepper.tsx` + e2e verification. Strictly blocked by all of 025-02..05 + CR-001 since cutover deletes the legacy code paths they read from.

**Parallel-eligibility:** stories 02-05 can run in any order after 01 ships. Recommended order by complexity for early-bug-detection: 05 (backend GET fields first, unblocks Slack caption) → 02 (highest LOC change) → 03 → 04 → CR-001.

## 4. Execution Strategy

### Branching
- Sprint branch: `sprint/S-16` cut from current `main` (`c94bc6e`).
- Per-item branches:
  - `story/STORY-025-01-shell-foundation`
  - `story/STORY-025-02-connections-migration`
  - `story/STORY-025-03-knowledge-migration`
  - `story/STORY-025-04-behavior-migration`
  - `story/STORY-025-05-workspace-owner-gate`
  - `story/STORY-025-06-mobile-cutover`
  - `cr/CR-001-channel-picker-search`
- One commit per item (ClearGate convention). Commit prefixes:
  - `feat(epic-025): STORY-025-01 shell foundation`
  - `feat(epic-025): STORY-025-02 connections migration`
  - `feat(epic-025): STORY-025-03 knowledge migration`
  - `feat(epic-025): STORY-025-04 behavior migration`
  - `feat(epic-025): STORY-025-05 workspace owner gate`
  - `feat(epic-025): STORY-025-06 mobile + cutover`
  - `feat(epic-005): CR-001 channel picker search`
  - ~~`fix(epic-023): BUG-001`~~ — dropped at pre-flight (already shipped).
- DevOps merges sprint branch to `main` at sprint close under explicit human approval (S-13/14/15 squash-merge pattern).

### Four-agent loop
- **Architect** — W01 blueprint written 2026-04-25 to `.cleargate/sprint-runs/SPRINT-16/plans/W01.md`. Surfaced 3 OQs (BUG-001 may be shipped, OQ-2 DELETE semantics, OQ-3 caption source); all 3 resolved at kickoff and propagated into story files. Granularity Rubric pass: no splits/merges. 025-04 stays unified (Persona+Skills+Automation each <30 LOC change).
- **Developer** — one story per commit. Must grep `.cleargate/FLASHCARD.md` for relevant tags before implementing:
  - 025-01: `#frontend`, `#scroll-spy`, `#deep-link`, `#vitest`
  - 025-02..04: `#frontend`, `#tailwind`, `#vitest`
  - 025-05: `#fastapi`, `#auth`, `#supabase`, `#pytest`
  - 025-06: `#frontend`, `#responsive`, `#cutover`
- **QA** — independent verification gate per story.
  - 025-01: scrollspy threshold + deep-link cold load + status strip 5/2 col render.
  - 025-02..04: each module's existing behavior preserved; new chrome matches handoff.
  - 025-05: 5 pytest scenarios (DELETE owner-not-creator → 204; DELETE creator-not-owner → 204; DELETE member-neither → 403; DELETE non-member → 404; GET surfaces is_owner + slack_domain) + 2 Vitest (tab visible/absent); BUG-002 regression check (member access to LIST + CREATE workspace endpoints unchanged).
  - 025-06: legacy JSX absent from route file; manual mobile smoke at 375px; desktop smoke at 1440px.
- **Reporter** — at sprint close, writes `.cleargate/sprint-runs/SPRINT-16/REPORT.md` with the 6-section retrospective. Write `.cleargate/sprint-runs/.active = SPRINT-16` at kickoff. Token-ledger hook still not built — fourth sprint without cost capture; flag in REPORT Meta.

### Red-zone surfaces (3+ items touch these)
- `frontend/src/components/workspace/moduleRegistry.ts` — shared by 025-02/03/04/05. Mitigation: each story appends its group entries; merge conflicts trivially resolved.
- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — touched by every EPIC-025 story (025-01 mounts shell + drops SetupStepper guard, 02-05 remove inline section bodies, 06 deletes legacy + final cleanup). Mitigation: strict story sequencing for the route file; merge order = 01 → 02 → 03 → 04 → 05 → 06.

### Shared surface warnings
- `frontend/src/components/workspace/ChannelSection.tsx` — 025-02 (re-skin to divider list) AND CR-001 (search input + count badge). Mitigation: hard-sequence CR-001 AFTER 025-02 is merged; CR-001 adds search input above the new divider list.
- `frontend/src/components/layout/AppNav.tsx` — BUG-001 dropped at pre-flight; nothing in S-16 touches this file. Constraint stands for future stories: do NOT change `h-14` since StickyTabBar (025-01) uses `top-14`.
- `frontend/src/lib/api.ts` — 025-05 adds `is_owner` AND `slack_domain` fields to Workspace type. 025-02 SlackSection consumes `slack_domain` (read-only). No other touch.
- `backend/app/api/routes/workspaces.py` — 025-05 only.
- `backend/app/models/workspace.py` — 025-05 only (adds `is_owner` + `slack_domain` to `WorkspaceResponse`).

## 5. Risk & Definition of Done

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Scrollspy listener flake under jsdom (`IntersectionObserver` partial support) | Medium | Low | 025-01 uses scroll-event fallback (rAF-throttled); tests assert state (hash, activeGroupId, scrollIntoView spy), not visual scroll. |
| Active-tab pill flickers during smooth-scroll animation | Medium | Low | 025-01 `isProgrammaticScroll` ref gates the listener; cleared on `scrollend` event with 600ms timeout fallback (Safari ≤ 16). Vitest scenario verifies. |
| End-of-page leaves earlier tab active when last group is shorter than viewport | Medium | Low | 025-01 end-of-page guard: `scrollY + innerHeight ≥ scrollHeight - 8` forces last group. Vitest scenario verifies. |
| Cold-load deep-link y disagrees with programmatic y (96 vs 140) | Resolved | — | Single `HEADER_OFFSET = 140` constant in `useScrollspy.ts`; sections use inline `scrollMarginTop: HEADER_OFFSET`; tab click uses plain `scrollIntoView`. Native and programmatic land identically. |
| Mobile active tab scrolls off the bar's visible window at 375px | Medium | Low | 025-06 `useEffect([activeGroupId])` calls `tabEl.scrollIntoView({inline:'center', block:'nearest'})`. `block:'nearest'` prevents page scroll. |
| Deep-link cold load runs before sections mount → no scroll | Medium | Medium | `useLayoutEffect` + RAF guard; verified via Vitest scenario in §2.1 of 025-01. |
| `moduleRegistry.ts` merge conflicts when 02/03/04/05 land in parallel | Low | Low | Each story appends its group entry to a separate location in the file. Conflicts trivial; resolve at merge. |
| 025-06 cutover removes JSX still referenced by another in-flight story | Medium | High | 025-06 strictly blocked by 02..05. QA verifies all 5 prior stories merged + green before 025-06 starts. |
| Owner-gate addition leaks beyond DELETE and breaks BUG-002 list/create relaxation | Low | High | 025-05 adds a NEW helper `is_team_owner` (read-only predicate) distinct from any BUG-002-relaxed helper. Applied ONLY to DELETE workspace; list/create endpoints unchanged. DoD includes explicit BUG-002 regression check for member list/create access. Verified 2026-04-25 against BUG-002 source — the DELETE endpoint was never in BUG-002 scope. |
| Creator-OR-owner OR semantics (OQ-2 = C) widens the 403/404 contract — non-creator team-members today get 404, tomorrow get 403 (existence leak within team boundary) | Med | Low | Existence leak only within team (caller is already a confirmed team member). Per ADR-024, the leak guard exists to prevent cross-tenant probing — same-team disclosure is acceptable. 025-05 §3.2 documents the contract; 4 of 5 pytest scenarios cover the matrix exhaustively. |
| Persona section accidentally regressed during extraction | Low | Medium | 025-04 copies lines 739-806 verbatim; existing `useUpdateWorkspaceMutation` test should catch any save-path regression. Status resolver flipped to `ok | empty` (was `partial | ok`) — Vitest scenario verifies both branches. |
| `is_owner` field leaks to list endpoints, expanding cache invalidation surface | Low | Medium | 025-05 contract: `is_owner` only on detail GET. Frontend reads from `useWorkspaceQuery` only. DoD includes explicit "list endpoint shape unchanged" check. |
| SetupStepper deletion in 025-06 leaves dangling imports / broken tests | Low | Medium | 025-06 DoD: `grep -r "SetupStepper" frontend/src` returns zero. Plus typecheck must be clean. |
| Wizard removal exposes new workspaces with empty modules and no guidance | Medium | Low | Owner directive at 2026-04-25: wizard not needed; modules can be configured in any order. Empty status dots on the strip act as the guidance. Re-evaluate at S-17 if friction reports come in. |

### Definition of Done
- [ ] All 6 stories + 1 CR pass QA on their own branches.
- [ ] Sprint branch `sprint/S-16` merges cleanly to `main` (squash-merge under explicit human approval, pushed to `origin/main`).
- [ ] `pytest backend/tests/` — full suite runs without hangs; **5 new pytest** scenarios from 025-05 (DELETE 4 + GET 1) and zero new failures elsewhere.
- [ ] `npm test` (Vitest) — ~32 new tests across stories pass (025-01 +9, 025-02 +5, 025-03 +4, 025-04 +5, 025-05 +2, 025-06 +5, CR-001 +3 minus existing SetupStepper-tied tests removed in cutover); no existing failures introduced.
- [ ] `npm run typecheck` clean.
- [ ] EPIC-025 progresses from `Active` to `Shipped` — 6/6 stories shipped.
- [ ] Route file `app.teams.$teamId.$workspaceId.tsx` LOC reduced by ≥80% (from ~1235 to ≤250).
- [ ] No regression on EPIC-007 agent loop, EPIC-013 wiki ingest, EPIC-015 document service, EPIC-018 dashboard automations, EPIC-014 local upload.
- [ ] Manual smoke test at viewport 375px + 1440px completes for all 9 modules + 1 deep link.
- [ ] `cleargate wiki build` rebuilds cleanly (or wiki-ingest agent processes all SPRINT-16 work items when CLI unavailable, matching S-13/14/15 fallback).
- [ ] Reporter writes `.cleargate/sprint-runs/SPRINT-16/REPORT.md` — 6-section retrospective.
- [ ] Flashcards recorded for any surprises.
- [ ] Live-testing window — any post-squash hotfixes logged in REPORT.md §Post-ship hotfixes.

## 6. Sprint Metrics & Goals

- **Items planned:** 6 stories under EPIC-025 + 1 CR (CR-001) = 7 items. (BUG-001 closed at pre-flight; not counted against sprint capacity.)
- **Target first-pass success rate:** ≥ 71% (5/7 pass QA on first attempt). Expected friction points: 025-01 scrollspy testability; CR-001 / 025-02 merge sequence on `ChannelSection.tsx`; 025-05 OR-gate test matrix.
- **Target Bug-Fix Tax:** 0 (BUG-001 closed at pre-flight without commit).
- **Target Enhancement Tax:** 1 (CR-001 included by owner directive 2026-04-25; single-file UX add, hard-sequenced after 025-02). Anything past §1 goes to S-17.
- **Token budget:** no formal cap; Reporter aggregates post-hoc. Token-ledger hook still not built — fourth sprint without cost capture; Reporter flags in REPORT Meta.

## 7. Out-of-Scope (deliberate)

- **Audit log module** — no `audit_events` table, no ingestion at call sites, no API, no UI. Future epic. Module registry accommodates without rework.
- **Usage module** — no `api_call_log` aggregate, no UI. Future epic. Same accommodation.
- **Slack Reinstall button** — owner directive at epic interrogation: not needed. Slack module info-only.
- **Persona voice presets** — owner directive: existing Persona works fine. No `bot_voice_preset` column, no agent prompt change, no 4-button picker.
- **Variation A (sidebar rail)** — explicitly rejected by owner.
- **⌘K command palette** — deferred until module list stabilizes (handoff §Interactions).
- **AppNav rework** — BUG-001 (glassmorphism polish) confirmed shipped at pre-flight. Any layout / behavior change beyond the already-merged polish deferred to a future epic.
- **Skill Edit action** — ADR-023 chat-only CRUD.
- **Token-ledger hook** — fourth sprint without cost capture; backlogged.

---

## ClearGate Readiness Gate

**Current Status: 🟢 Approved — Active 2026-04-25. OQs 1/2/3 resolved at kickoff (a/C/C).**

- [x] Scope = 7 items (6 EPIC-025 stories + CR-001), all 🟢 ambiguity at entry. BUG-001 dropped at pre-flight (already shipped).
- [x] Each item has a reachable parent (EPIC-025 🟢 / EPIC-005 🟢, all linked).
- [x] Red-zone surfaces identified (`moduleRegistry.ts`, route file) with sequencing mitigation.
- [x] Shared surfaces warned (§4): `ChannelSection.tsx` (025-02 + CR-001), `lib/api.ts` (025-05), `routes/workspaces.py` (025-05), `models/workspace.py` (025-05).
- [x] Dependencies documented with explicit blocker columns.
- [x] Pre-sprint hygiene block enumerated (§1).
- [x] OQs resolved 2026-04-25: OQ-1 = a (BUG-001 shipped, drop), OQ-2 = C (creator OR team-owner OR semantics), OQ-3 = C (slack_domain on workspace GET).
- [x] **Human approval — 2026-04-25.**
