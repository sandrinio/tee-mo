---
story_id: "STORY-025-01"
parent_epic_ref: "EPIC-025"
status: "Shipped"
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

# STORY-025-01: Workspace v2 Shell Foundation
**Complexity:** L2 — 6 new files, scrollspy hook + 3 hardenings, deep-link wiring, route guard removal, ~4hr

## 1. The Spec

### 1.1 User Story
As a workspace admin, I want a sticky-tab + status-strip page chrome with scrollspy and deep-linking, so that any module is reachable in one click and shareable via URL.

### 1.2 Detailed Requirements
- **WorkspaceShell** composes: header (breadcrumb + H1 + workspace meta) → StatusStrip → StickyTabBar → vertical list of ModuleSection placeholders. Renders unconditionally — no `isSetupComplete && !wizardSkipped` guard.
- **Route change:** delete the SetupStepper guard from `app.teams.$teamId.$workspaceId.tsx`. The route renders `<WorkspaceShell />` plus existing modal mount points (AddAutomationModal, DryRunModal, AutomationHistoryDrawer) for any authenticated workspace member. SetupStepper component file is left dead-code in this story; deletion lands in 025-06 cutover.
- **StatusStrip:** 4-cell card grid at md+ (Workspace / Slack / Provider / Knowledge), 2-col below md. Setup cell dropped — wizard is retired (epic §6 Q3/Q4). Each cell = 11px uppercase kicker + 14px/600 value + 12px slate-500 caption. Cells are informational, not clickable.
- **StickyTabBar:** `top-14`, `bg-slate-50/90 backdrop-blur-sm`, full-bleed within content column. One tab per group with `ok-count / total` pill. Active tab = `bg-white border slate-200 shadow-sm`.
- **ModuleSection wrapper:** anchored `<section id="tm-{id}" style={{scrollMarginTop: HEADER_OFFSET}}>` with header (h2 16px/600 + caption + optional action slot) + content card (`rounded-lg border border-slate-200 bg-white`). `HEADER_OFFSET = 140` is exported from `useScrollspy.ts` — single source of truth shared with the scrollspy + tab-click handler.
- **moduleRegistry.ts:** typed array of module entries (`id`, `group`, `label`, `icon`, `summary`, `statusResolver`). Status resolver is `(workspaceData) => 'ok' | 'partial' | 'empty' | 'error' | 'neutral'`. Entry stub for each module — bodies arrive in 025-02 / 03 / 04 / 05.
- **useScrollspy hook:** window scroll listener throttled via `requestAnimationFrame`. Returns `{ activeGroupId }`. Threshold = 200px from viewport top. Three hardenings:
  - **`isProgrammaticScroll` gate.** Hook exposes `setProgrammaticScrolling(true)` for the tab-click handler. While true, the listener is short-circuited so the active pill stays on the clicked group through the smooth-scroll animation. Cleared on `scrollend` event; for browsers without `scrollend` (Safari ≤ 16), a 600ms `setTimeout` fallback clears it.
  - **End-of-page guard.** When `window.scrollY + window.innerHeight ≥ document.documentElement.scrollHeight - 8`, force `activeGroupId = lastGroupId`. Otherwise the topmost-≤-200 resolver leaves an earlier group active when the last group is shorter than the viewport.
  - **rAF throttling** (existing): one frame max per scroll burst.
- **Tab click:** `groupAnchorEl.scrollIntoView({behavior:'smooth', block:'start'})`. The section's `scrollMarginTop: HEADER_OFFSET` produces the 140px offset for free — no `window.scrollBy(0, -140)` correction. Before scrolling, call `setProgrammaticScrolling(true)`. Update `window.history.replaceState` with `#tm-{firstModuleId}` of that group.
- **Cold-load deep link:** `useLayoutEffect` on shell mount reads `window.location.hash`; if it matches `#tm-{id}`, calls `targetEl.scrollIntoView()` after one rAF (sections must be mounted). Native browser anchor scroll honors `scroll-margin-top` so the y matches programmatic exactly.

### 1.3 Out of Scope
- Any module body content (placeholder cards only). Bodies land in 025-02 / 03 / 04 / 05.
- Mobile responsive treatment beyond StatusStrip 4→2 col + tab bar `overflow-x-auto`. Mobile active-tab auto-scroll-into-view lands in 025-06.
- Legacy stacked layout deletion — defer to 025-06 cutover.
- SetupStepper component file deletion — defer to 025-06 cutover (file becomes dead code in this story).

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Workspace v2 shell foundation

  Scenario: Status strip renders 4 cells at md+
    Given viewport width ≥ 768px
    When the page renders with a fully-configured workspace
    Then the StatusStrip displays 4 cells in a single row (Workspace, Slack, Provider, Knowledge)
    And no Setup cell is rendered

  Scenario: Status strip collapses to 2 columns below md
    Given viewport width < 768px
    Then the StatusStrip displays 2 columns

  Scenario: Sticky tab bar activates on scroll past threshold
    Given the user has scrolled past the Connections group's first section
    When the Knowledge group's first section crosses 200px from viewport top
    Then the Knowledge tab gains active styling (bg-white border shadow-sm)
    And no other tab is active

  Scenario: Tab click smooth-scrolls with HEADER_OFFSET (140px)
    Given the user is at the top of the page
    When the user clicks the Behavior tab
    Then scrollIntoView is called on the Behavior group's first section with behavior:'smooth'
    And the section's scrollMarginTop equals HEADER_OFFSET (140)
    And window.location.hash equals "#tm-persona"

  Scenario: No active-tab flicker during programmatic scroll
    Given the user is at the top of the page
    When the user clicks the Behavior tab
    Then setProgrammaticScrolling(true) is called before scroll begins
    And the scrollspy listener is gated so activeGroupId stays "behavior" through the animation
    And on scrollend (or after 600ms timeout fallback) setProgrammaticScrolling(false) is called

  Scenario: End-of-page activates last group
    Given the last group's first section has not crossed the 200px threshold (group shorter than viewport)
    When window.scrollY + window.innerHeight ≥ scrollHeight - 8
    Then the resolver returns activeGroupId = lastGroupId
    And the last tab is active

  Scenario: Cold-load deep link lands at HEADER_OFFSET
    Given the user navigates to "/app/teams/T1/W1#tm-files"
    When the page first paints
    Then native anchor scroll lands the Files section's top at scrollMarginTop (140px) below viewport
    And the Knowledge tab is active

  Scenario: Shell renders without SetupStepper guard
    Given an authenticated workspace member views the route
    When the page renders
    Then WorkspaceShell mounts unconditionally
    And no SetupStepper is rendered regardless of bot_persona / has_key / drive state

  Scenario: Status resolver dispatch
    Given the module registry has entries with statusResolver functions
    When WorkspaceShell renders with a workspace data object
    Then each entry's statusResolver is invoked once with the workspace data
    And the returned status is reflected in the StatusStrip and tab pill
```

### 2.2 Verification Steps (Manual)
- [ ] Load workspace page — sticky bar stays pinned during scroll.
- [ ] Click each tab in sequence — smooth scroll, no layout shift.
- [ ] Refresh on `#tm-skills` — page lands directly on Skills.
- [ ] Resize viewport across md breakpoint — StatusStrip cleanly transitions 5↔2 col.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| New | `frontend/src/components/workspace/WorkspaceShell.tsx` |
| New | `frontend/src/components/workspace/StatusStrip.tsx` |
| New | `frontend/src/components/workspace/StickyTabBar.tsx` |
| New | `frontend/src/components/workspace/ModuleSection.tsx` |
| New | `frontend/src/components/workspace/moduleRegistry.ts` |
| New | `frontend/src/components/workspace/useScrollspy.ts` |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — remove SetupStepper guard. Render `<WorkspaceShell />` unconditionally for any authenticated workspace member. Existing inline section bodies stay in place during this story; they get extracted in 025-02..05 and the route is fully cleaned in 025-06 cutover. SetupStepper component file is left dead-code in this story. |

### 3.2 Technical Logic
- **Constants.** `useScrollspy.ts` exports `export const HEADER_OFFSET = 140` and `export const SCROLLSPY_THRESHOLD = 200`. ModuleSection imports HEADER_OFFSET and applies it as inline style: `<section id={...} style={{scrollMarginTop: HEADER_OFFSET}}>`. Tab-click handler imports both.
- **Hook signature.** `useScrollspy(groupAnchorIds: string[]): { activeGroupId: string; setProgrammaticScrolling: (v: boolean) => void }`. Single rAF-throttled `scroll` listener.
- **Resolver per frame.** If `isProgrammaticScroll === true`, short-circuit (return current state). Else: if `window.scrollY + window.innerHeight ≥ document.documentElement.scrollHeight - 8`, set `activeGroupId = lastGroupId`. Else: find the topmost section whose `getBoundingClientRect().top <= SCROLLSPY_THRESHOLD`, return its group.
- **`setProgrammaticScrolling`.** Sets a ref (no re-render). Tab-click handler calls `setProgrammaticScrolling(true)` before `scrollIntoView`, then registers a one-shot `scrollend` listener that calls `setProgrammaticScrolling(false)`. Fallback for browsers without `scrollend` (Safari ≤ 16): `setTimeout(() => setProgrammaticScrolling(false), 600)`. Detect via `'onscrollend' in window`.
- **Tab click handler.**
  ```ts
  const onTabClick = (groupId: string) => {
    const firstModuleId = registry.find(m => m.group === groupId)!.id;
    const el = document.getElementById(`tm-${firstModuleId}`);
    if (!el) return;
    setProgrammaticScrolling(true);
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    window.history.replaceState(null, '', `#tm-${firstModuleId}`);
    if ('onscrollend' in window) {
      window.addEventListener('scrollend', () => setProgrammaticScrolling(false), { once: true });
    } else {
      setTimeout(() => setProgrammaticScrolling(false), 600);
    }
  };
  ```
- **Cold-load deep link.** `useLayoutEffect` on shell mount: if `window.location.hash` matches `#tm-{id}` and the matching section exists, call `el.scrollIntoView()` after one rAF (sections must be mounted). Native anchor scroll honors `scroll-margin-top` so y matches programmatic.
- **jsdom note.** `IntersectionObserver` is available in jsdom 22+ but `scrollIntoView({behavior:'smooth'})` and `scrollend` are no-ops. Tests assert: hash, activeGroupId state, that `scrollIntoView` was called (spy), that `setProgrammaticScrolling(true)` was called before scroll. Tests do not assert visual scroll position.

### 3.3 API Contract
None. Pure frontend.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Vitest unit | 9 | One per Gherkin scenario in §2.1 (4-cell strip, 2-col mobile, scrollspy threshold, tab click + offset, no-flicker programmatic gate, end-of-page guard, cold-load deep link, no SetupStepper guard, status resolver dispatch) |
| Existing suite | green | Workspace route tests must not regress; SetupStepper test file (if any) is updated to assert the guard is gone |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered by Vitest tests.
- [ ] `npm run typecheck` clean.
- [ ] No new ESLint warnings.
- [ ] Manual verification §2.2 completed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**
