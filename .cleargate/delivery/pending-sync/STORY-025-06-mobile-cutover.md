---
story_id: "STORY-025-06"
parent_epic_ref: "EPIC-025"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-025-workspace-v2-redesign.md"
actor: "Workspace admin"
complexity_label: "L2"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-s16-kickoff"
updated_at_version: "cleargate-s16-kickoff"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-025-06: Mobile + Cutover
**Complexity:** L2 — responsive treatment + legacy delete + e2e verification, ~3hr

## 1. The Spec

### 1.1 User Story
As a workspace admin on any device, I want the redesigned page to work below the md breakpoint and to fully replace the old stacked layout, so that everyone sees the new experience and the old code is gone.

### 1.2 Detailed Requirements
- StatusStrip below md collapses 4→2 columns (already wired in 025-01 — verify visually).
- Sticky tab bar below md follows the existing dashboard mobile pattern: horizontal scroll on overflow with `-webkit-overflow-scrolling: touch`. Verified by inspecting `frontend/src/components/dashboard/WorkspaceCard.tsx` and `/app/teams/$teamId` route — match whatever pattern is used (likely `overflow-x-auto`).
- Tab bar tabs maintain min-width on mobile so labels don't truncate to ellipsis at standard widths (≥320px).
- **Mobile active-tab auto-scroll-into-view.** When `activeGroupId` changes (from scrollspy or tab click), the active tab element calls `tabEl.scrollIntoView({inline:'center', block:'nearest'})` so the active tab stays visible inside the horizontal-scroll bar. Without this, scrollspy can activate a tab that's currently scrolled off-screen at 375px width with 4 tabs near the limit.
- Module sections internal layouts (segmented controls, header strips, divider lists) reflow gracefully — single column where multi-column on desktop.
- **Delete the legacy stacked JSX** from `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`. The route now renders only `<WorkspaceShell />` plus the existing modal mount points (AddAutomationModal, DryRunModal, AutomationHistoryDrawer). No SetupStepper guard (already removed in 025-01).
- **Delete `frontend/src/components/workspace/SetupStepper.tsx`** plus any tests / direct imports. Wizard is retired (epic §6 Q3). Grep the repo for `SetupStepper` after deletion — zero remaining references expected.
- Update existing route tests for the new structure. E2E manual smoke covers all 9 modules + deep links + mobile viewport.

### 1.3 Out of Scope
- New mobile-specific UI primitives.
- Sheet/drawer pattern for mobile navigation.
- Changes to AppNav (covered by BUG-001).

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Mobile + cutover

  Scenario: Status strip 2-col on mobile
    Given viewport width 375px
    When the page renders
    Then the StatusStrip displays exactly 2 columns

  Scenario: Tab bar horizontally scrolls on mobile
    Given viewport width 375px and 4 tabs
    When the user swipes the tab bar horizontally
    Then the tab bar scrolls without page scroll
    And tabs do not truncate to ellipsis

  Scenario: Mobile auto-scrolls active tab into bar viewport
    Given viewport width 375px and the active tab is currently scrolled out of the bar's visible window
    When activeGroupId changes (via scrollspy or tab click)
    Then the active tab element calls scrollIntoView({inline:'center', block:'nearest'}) on its parent overflow container
    And the active tab is visible inside the bar

  Scenario: Legacy stacked JSX removed
    Given the route file frontend/src/routes/app.teams.$teamId.$workspaceId.tsx
    Then the file contains no inline DriveSection / PickerSection / KnowledgeList / PersonaSection / SkillsSection / DeleteWorkspaceSection definitions
    And renders only <WorkspaceShell /> and modal mount points (no SetupStepper guard)

  Scenario: SetupStepper component deleted
    Given the codebase after 025-06
    Then frontend/src/components/workspace/SetupStepper.tsx does not exist
    And `grep -r "SetupStepper" frontend/src` returns zero results

  Scenario: Full e2e smoke
    Given a fully-configured workspace
    When a manual smoke test runs all 9 module interactions plus deep-link load
    Then all interactions succeed without console errors

  Scenario: Existing test suites green
    Given npm test and pytest are run
    Then all pre-existing tests pass without regression
```

### 2.2 Verification Steps (Manual)
- [ ] Test at viewport widths 320 / 375 / 768 / 1024 / 1440px.
- [ ] Each of the 9 modules: trigger one action, verify success.
- [ ] Deep-link `#tm-files` cold load → lands on Files.
- [ ] Reload on `#tm-skills` → Behavior tab active, scrolled to Persona (first in group).
- [ ] DevTools → Performance → page TTI ≤ pre-redesign baseline.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| Modify | `frontend/src/components/workspace/StickyTabBar.tsx` — `overflow-x-auto` mobile treatment + `useEffect` that auto-scrolls active tab into bar viewport when activeGroupId changes |
| Modify | `frontend/src/components/workspace/WorkspaceShell.tsx` — responsive container max-w |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — delete legacy inline section bodies, keep only shell + modal mounts (no SetupStepper guard — removed in 025-01) |
| Delete | `frontend/src/components/workspace/SetupStepper.tsx` + any sibling test file. Wizard retired. |
| Modify | route's existing test file (if present) — update to new shell-mounted structure; remove any SetupStepper-related assertions |

### 3.2 Technical Logic
- StickyTabBar mobile treatment: `flex overflow-x-auto -mx-4 px-4 md:mx-0 md:px-0 md:overflow-visible`. Hide scrollbar with `[&::-webkit-scrollbar]:hidden`.
- Tab min-width: `min-w-max md:min-w-0` so labels don't wrap or truncate.
- **Active-tab auto-scroll.** Each tab gets a `ref` keyed by groupId. A `useEffect([activeGroupId])` finds `tabRefs[activeGroupId]?.current` and calls `.scrollIntoView({inline:'center', block:'nearest'})`. Guard with `if (!tabRefs[activeGroupId]?.current) return;`. The `block:'nearest'` is critical — it prevents this scroll from also moving the page (we only want horizontal motion inside the bar).
- Cutover diff size — expect the route file to drop from ~1235 LOC to ~150 LOC after legacy bodies are removed and section components live in their own files.
- SetupStepper deletion verification: after removing the file, run `grep -r "SetupStepper" frontend/src` — must return zero matches.

### 3.3 API Contract
None new.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Vitest | 5 | Mobile column count, tab overflow, route renders only shell, active-tab auto-scroll-into-view, SetupStepper grep zero |
| Manual smoke | 9 | One per module + deep link |
| Existing | green | All pre-existing tests pass |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered.
- [ ] `npm run typecheck` + `pytest backend/tests/` clean — zero new failures.
- [ ] Route file LOC reduced by ≥80%.
- [ ] Manual mobile smoke at 375px + desktop smoke at 1440px completed.
- [ ] Deep links verified.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**
