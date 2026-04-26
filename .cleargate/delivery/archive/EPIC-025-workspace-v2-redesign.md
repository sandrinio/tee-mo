---
epic_id: "EPIC-025"
status: "Shipped"
ambiguity: "🟢 Low"
active_sprint: "S-16"
human_approved_at: "2026-04-25T00:00:00Z"
context_source: "design_handoff_workspace_redesign/README.md"
owner: "Solo dev"
target_date: "2026-05-09"
children:
  - "STORY-025-01-shell-foundation"
  - "STORY-025-02-connections-migration"
  - "STORY-025-03-knowledge-migration"
  - "STORY-025-04-behavior-migration"
  - "STORY-025-05-workspace-owner-gate"
  - "STORY-025-06-mobile-cutover"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-s16-kickoff"
updated_at_version: "cleargate-s16-kickoff"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---

# EPIC-025: Workspace v2 Redesign — Sticky Tabs + Scrollspy

> **Provenance.** Sourced from the design handoff bundle at `design_handoff_workspace_redesign/` (Variation B). Proposal step skipped per owner directive — handoff README is high-fidelity and acts as the spec. Two handoff features were dropped during interrogation (see §6): the Slack "Reinstall" button (not needed) and the Persona voice-preset 4-button picker (existing Persona implementation is staying as-is, re-skinned only).

## 0. AI Coding Agent Handoff

```xml
<agent_context>
  <objective>Replace the long stacked workspace settings page with a sticky-tab + scrollspy layout (Variation B), preserving every existing module's behavior verbatim. Chrome-only redesign — no backend or schema changes.</objective>
  <architecture_rules>
    <rule>Use existing UI primitives in frontend/src/components/ui/* (Button, Card, Badge). Do NOT add new primitive variants.</rule>
    <rule>Use Tailwind 4 CSS-first tokens already defined in frontend/src/app.css. Do NOT add new @theme tokens.</rule>
    <rule>Use lucide-react for icons. Do NOT use the Lucide CDN from the prototype HTML.</rule>
    <rule>Use @fontsource/inter and @fontsource/jetbrains-mono. Do NOT use Google Fonts CDN.</rule>
    <rule>Do NOT lift inline Tailwind CDN, Babel-in-browser, or window-scoped components from the prototype HTML.</rule>
    <rule>One layout in production — Variation B only. No dual-layout toggle. Setup wizard is retired (see §6 Q3) — `<WorkspaceShell />` renders unconditionally for any authenticated workspace member.</rule>
    <rule>Audit log + Usage modules are deferred. Module registry must accept future modules without rework, but do NOT build them in this epic.</rule>
    <rule>Scrollspy threshold: 200px from viewport top. `HEADER_OFFSET = 140` is exported from `useScrollspy.ts` and applied as `scrollMarginTop` on every `ModuleSection`. Tab click uses `element.scrollIntoView({behavior:'smooth', block:'start'})` — the section's `scroll-margin-top` produces the 140px offset for both cold-load deep links and programmatic scroll. No separate `window.scrollBy` correction.</rule>
    <rule>Each module section anchor id is `tm-{moduleId}`. Deep-links like `#tm-files` must jump on load.</rule>
    <rule>Scrollspy listener is gated by an `isProgrammaticScroll` ref during tab-click animations (cleared on `scrollend` or 600ms timeout fallback) to prevent active-tab flicker through intermediate groups.</rule>
    <rule>End-of-page guard: when `window.scrollY + window.innerHeight ≥ document.documentElement.scrollHeight - 8`, force `activeGroupId = lastGroupId`. Otherwise the topmost-≤-200 resolver leaves an earlier group active when the last group is shorter than the viewport.</rule>
    <rule>Mobile tab bar auto-scrolls the active tab into its visible overflow window via `scrollIntoView({inline:'center', block:'nearest'})` whenever activeGroupId changes (scrollspy or tab click).</rule>
    <rule>Owner-only gate on Danger zone — Slack team owner role only, members cannot see/use it. Backend enforces; UI hides. `is_owner` field surfaces only on the workspace detail GET (not list endpoints); frontend reads exclusively from `useWorkspaceQuery`.</rule>
    <rule>Mobile: match existing /app/teams/$teamId dashboard mobile pattern. Status strip collapses 4→2 columns below md.</rule>
    <rule>Preserve all current behavior of DriveSection, PickerSection, KnowledgeList, KeySection, ChannelSection, AutomationsSection, PersonaSection, SkillsSection, DeleteWorkspaceSection verbatim — chrome only, no behavior changes.</rule>
    <rule>Slack module: NO Reinstall button. Display info only (workspace name, team_id · domain, Installed badge).</rule>
    <rule>Persona module: NO voice preset picker. Existing textarea + Save behavior preserved as-is, only the card chrome and header treatment update.</rule>
  </architecture_rules>
  <target_files>
    <file path="frontend/src/routes/app.teams.$teamId.$workspaceId.tsx" action="modify" />
    <file path="frontend/src/components/workspace/WorkspaceShell.tsx" action="create" />
    <file path="frontend/src/components/workspace/StatusStrip.tsx" action="create" />
    <file path="frontend/src/components/workspace/StickyTabBar.tsx" action="create" />
    <file path="frontend/src/components/workspace/ModuleSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/moduleRegistry.ts" action="create" />
    <file path="frontend/src/components/workspace/useScrollspy.ts" action="create" />
    <file path="frontend/src/components/workspace/PersonaSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/SlackSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/DriveSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/FilesSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/SkillsSection.tsx" action="create" />
    <file path="frontend/src/components/workspace/DangerZoneSection.tsx" action="create" />
    <file path="backend/app/api/routes/workspaces.py" action="modify" />
  </target_files>
</agent_context>
```

## 1. Problem & Value

**Why are we doing this?**
The workspace detail page (`frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`, 1235 LOC) stacks every section vertically. Admins must scroll past Drive → Picker → Knowledge → Persona → Skills → Automation → Channels to reach Danger zone. As we add modules (voice presets now, Audit/Usage later), the scroll grows unbounded and modules become discovery-dead. The redesign groups modules into a 5-cell status strip + sticky tab bar so any module is one click away while preserving the deep-link/refresh URL contract.

**Success Metrics (North Star):**
- Time-to-reach any module from page load: ≤ 1 click (vs. unbounded scroll today).
- Page TTI unchanged or better than current implementation (no new heavy deps).
- Zero regressions in existing module behavior — full test suite green.
- Deep-links `#tm-{moduleId}` resolve and scroll-jump on load with the sticky-bar offset respected.

## 2. Scope Boundaries

**✅ IN-SCOPE (Build This)**
- [ ] Layout shell: Variation B only — header + status strip + sticky tab bar + anchored module sections + scrollspy. Renders unconditionally; SetupStepper guard removed.
- [ ] Module registry as typed source of truth (`moduleRegistry.ts` — id, group, label, icon, status resolver).
- [ ] Status semantics framework: `ok | partial | empty | error | neutral` with per-module resolver functions.
- [ ] Status strip: 4 cells (Workspace / Slack / Provider / Knowledge) at md+, 2 cells below md. Setup cell dropped (wizard retired — see §6 Q3).
- [ ] Sticky tab bar: one tab per group with `ok-count / total` pill. Active tab = `bg-white border slate-200 shadow-sm`.
- [ ] Scrollspy: window scroll listener (rAF-throttled), 200px threshold. Hardenings: (a) `isProgrammaticScroll` gate prevents flicker during tab-click animations; (b) end-of-page guard forces last group when scroll reaches `scrollHeight - 8`; (c) `HEADER_OFFSET = 140` shared between `scrollMarginTop` (sections) and the tab-click handler — single source of truth.
- [ ] Tab click: `element.scrollIntoView({behavior:'smooth', block:'start'})`. The section's `scroll-margin-top` does the offset; no `window.scrollBy` correction.
- [ ] Deep linking: `#tm-{moduleId}` jumps on load and updates on tab click. Cold-load uses native browser anchor scroll, which honors `scroll-margin-top` — same y as programmatic.
- [ ] Mobile: tab bar auto-scrolls the active tab into its visible overflow window when activeGroupId changes.
- [ ] Migrate 9 existing module bodies into the new shell with the redesigned content treatments per handoff §"Module bodies":
  - Slack: avatar tile + workspace name + mono `team_id · domain` + Installed badge. Info-only — no Reinstall.
  - Drive: avatar tile + connected email + caption + Disconnect.
  - AI provider: 3-button segmented control + masked key in slate-50 box + Rotate.
  - Channels: divider list with Bound badge + Bind/Unbind.
  - Files: header strip ("N of M files indexed" + "Add file" primary) + divider list with hover-revealed Remove.
  - Persona: existing textarea + Save behavior preserved verbatim; only card chrome and header treatment update.
  - Skills: divider list — sparkles icon + mono `/teemo skill-name` + caption. No Edit action (ADR-023 chat-only CRUD).
  - Automation: empty-state tile when zero triggers; preserve existing list when populated.
  - Danger zone: single-row layout — title + caption left, danger Delete button right.
- [ ] Owner-only gate on Danger zone — Slack team owner role only. **New gate on `DELETE /workspaces/{id}`** (the endpoint currently uses `assert_workspace_owner` = workspace creator; tightening to team-owner role). NOT a reversal of BUG-002 — BUG-002 only relaxed `assert_team_owner` on team-LIST endpoints (`list_workspaces`, `create_workspace`, `list_slack_channels`); the DELETE endpoint was never in BUG-002 scope. Backend enforces; UI hides for non-owners.
- [ ] Mobile: rail/tab bar follows existing `/app/teams/$teamId` dashboard pattern. Status strip 5→2 columns below md.
- [ ] Delete legacy stacked layout from `app.teams.$teamId.$workspaceId.tsx` once shell is wired.
- [ ] Existing module test suites (KeySection, ChannelSection, AutomationsSection, SetupStepper) remain green; new shell components ship with unit tests.

**❌ OUT-OF-SCOPE (Do NOT Build This)**
- Variation A (sidebar rail) — explicitly rejected by owner.
- Dual-layout toggle in production.
- ⌘K command palette — deferred until module list stabilizes (handoff §Interactions).
- Audit log module — no `audit_events` table, no ingestion at call sites, no API, no UI. Future epic.
- Usage module — no `api_call_log` table, no 7-day rollup, no aggregate query, no UI. Future epic.
- Slack Reinstall button — owner says not needed. No workspace-scoped reinstall endpoint, no UI element.
- Persona voice preset picker — owner says existing Persona works fine. No new column, no agent prompt changes, no 4-button picker.
- Skills Edit action — ADR-023 keeps skill CRUD chat-only.
- New @theme tokens, new UI primitive variants, new font families.
- AppNav rework — covered by `BUG-001-nav-aesthetics`.
- SetupStepper redesign — guided setup mode (`STORY-008-01`) is a separate surface; only the post-setup detail page is redesigned here.

## 3. The Reality Check (Context)

| Constraint Type | Limit / Rule |
|---|---|
| Performance | Page TTI ≤ current. Scrollspy listener throttled (rAF or 100ms). No layout thrash on tab switch. |
| Visual fidelity | Pixel-perfect match to handoff prototype using existing `app.css` tokens. No new tokens. |
| Routing | Deep links `#tm-{moduleId}` must work from cold load and from same-page navigation. |
| Test harness | jsdom does NOT support `IntersectionObserver` natively — scrollspy must be testable (mock or scroll-event polyfill). |
| Permissions | Danger zone owner-only. Backend `assert_team_owner` re-introduced for the delete endpoint; UI hides the section for non-owners. |
| Sprint | All stories must fit in one sprint (S-16). |
| Backwards compatibility | Existing API contracts unchanged. No schema migrations in this epic. |
| Mobile | Match existing dashboard mobile pattern; do not invent new responsive primitives. |

## 4. Technical Grounding (The "Shadow Spec")

**Affected files (verified to exist):**

- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — replace JSX body. Keep route declaration, `loadGapiScript`, `docTypeLabel`, `sourceBadgeProps`, `TruncationToast`, modal mount points (AddAutomationModal, DryRunModal, AutomationHistoryDrawer). Move section bodies into per-module components. New shell composes them.
- `frontend/src/components/workspace/AutomationsSection.tsx` — rendered inside new ModuleSection wrapper; empty-state visuals updated to handoff spec.
- `frontend/src/components/workspace/ChannelSection.tsx` — re-skinned to divider list with Bound badge.
- `frontend/src/components/workspace/KeySection.tsx` — re-skinned to 3-button segmented control + masked-key box.
- `frontend/src/components/workspace/SetupStepper.tsx` — unchanged (guided pre-setup surface).
- `frontend/src/components/ui/Button.tsx`, `Card.tsx`, `Badge.tsx` — consumed unchanged.
- `frontend/src/components/layout/AppNav.tsx` — unchanged (BUG-001 owns it).
- `frontend/src/app.css` — token reference only, no edits.
- `backend/app/api/routes/workspaces.py` — re-introduce `assert_team_owner` for `DELETE /workspaces/{id}` only. No other backend changes.

**New files:**

- `frontend/src/components/workspace/WorkspaceShell.tsx` — top-level layout: header → StatusStrip → StickyTabBar → ModuleSection list.
- `frontend/src/components/workspace/StatusStrip.tsx` — 5-cell card grid (md), 2-cell (below md).
- `frontend/src/components/workspace/StickyTabBar.tsx` — sticky `top-14`, `bg-slate-50/90 backdrop-blur-sm`, full-bleed within content column.
- `frontend/src/components/workspace/ModuleSection.tsx` — anchored `<section id="tm-{id}" class="scroll-mt-24">` wrapping a content card.
- `frontend/src/components/workspace/moduleRegistry.ts` — typed registry (id, group, label, icon, statusResolver, summary). Single source of truth.
- `frontend/src/components/workspace/useScrollspy.ts` — hook returning active group id; 200px threshold; rAF-throttled.
- `frontend/src/components/workspace/SlackSection.tsx`, `DriveSection.tsx`, `FilesSection.tsx`, `SkillsSection.tsx`, `PersonaSection.tsx`, `DangerZoneSection.tsx` — extract module bodies (DriveSection / KnowledgeList / PersonaSection / DeleteWorkspaceSection currently live inline in the route file). Behavior unchanged; only chrome updates.

**Data Changes:**

- None. No migrations, no schema changes. Audit + Usage tables explicitly deferred.

## 5. Acceptance Criteria

```gherkin
Feature: Workspace v2 — sticky tabs + scrollspy

  Scenario: Sticky tab bar reflects active module on scroll
    Given the workspace detail page has loaded with all groups present
    When the user scrolls so the Knowledge group's first section crosses 200px from the viewport top
    Then the Knowledge tab activates (bg-white, border slate-200, shadow-sm)
    And no other tab is active

  Scenario: Tab click smooth-scrolls with sticky-bar offset
    Given the user is at the top of the page
    When the user clicks the Behavior tab
    Then the page smooth-scrolls so the Behavior group's first section is positioned 140px below the viewport top
    And the URL hash updates to "#tm-persona"

  Scenario: Deep link jumps on cold load
    Given the user navigates directly to "/app/teams/T1/W1#tm-files"
    When the page finishes loading
    Then the Files section is positioned 140px below the viewport top
    And the Knowledge tab is active

  Scenario: Status strip cell renders provider name and masked key
    Given the workspace has an OpenAI key "sk-proj-XXXXG7vT" stored
    When the page renders
    Then the Provider strip cell shows kicker "PROVIDER", value "OpenAI", caption "sk-proj-…G7vT"

  Scenario: Module status dot reflects empty state
    Given the workspace has zero indexed files
    Then the Files module status resolver returns "empty"
    And the Knowledge tab pill shows "0 / 1 ok"

  Scenario: Danger zone hidden for non-owner team members
    Given the authenticated user is a member (not owner) of the Slack team
    When the page renders
    Then the Workspace tab does not include the Danger zone module
    And a direct DELETE /workspaces/{id} call returns 403

  Scenario: Mobile layout collapses status strip
    Given viewport width is below md breakpoint
    When the page renders
    Then the status strip displays as 2 columns
    And the sticky tab bar follows the existing dashboard mobile pattern

  Scenario: Existing module behavior preserved
    Given any existing module (Drive, Files, Channels, Automation, Skills)
    When the user performs an action that worked in the old layout
    Then the action succeeds with the same outcome and tests pass

  Scenario: Audit log and Usage are absent in v1
    Given the workspace detail page in production
    Then no Observability tab is rendered
    And the module registry contains no audit or usage entries
```

## 6. AI Interrogation Loop (Human Input Required)

- **AI Question 1:** "Slack module Reinstall button — link to team-level install URL or new workspace-scoped endpoint?"
- **Human Answer (2026-04-25):** Not needed. Drop the Reinstall button entirely; Slack module is info-only.

- **AI Question 2:** "Persona voice presets — hardcoded constants or new table?"
- **Human Answer (2026-04-25):** Skip voice presets entirely. Existing Persona (textarea + Save) works as-is; just re-skin the chrome.

- **AI Question 3:** "Setup wizard branch — keep gating route on `isSetupComplete && !wizardSkipped` or render shell unconditionally?"
- **Human Answer (2026-04-25):** Drop the wizard. Render `<WorkspaceShell />` for any authenticated workspace member regardless of setup state. SetupStepper guard removed in 025-01; SetupStepper component file deleted in 025-06 cutover.

- **AI Question 4:** "Status strip 5th cell (Setup) — what does click do, and what does it show after the wizard is dropped?"
- **Human Answer (2026-04-25):** Drop the Setup cell. Strip becomes 4 cells (Workspace / Slack / Provider / Knowledge), 2-col below md. Cells are informational, not clickable.

- **AI Question 5:** "Persona status resolver — `partial` when empty (warning) or `empty` when empty (neutral state dot)?"
- **Human Answer (2026-04-25):** Use `ok | empty`. Persona field always renders regardless of state. Empty just shows the empty status dot — no "must fill" warning.

- **AI Question 6 (resolved during ambiguity review):** "Cold-load `scroll-mt-24` (96px) vs programmatic 140px scroll — which wins?"
- **Resolution:** Single shared constant `HEADER_OFFSET = 140` exported from `useScrollspy.ts`. Sections use inline `style={{scrollMarginTop: HEADER_OFFSET}}`; tab click uses plain `scrollIntoView({behavior:'smooth'})`. Both cold-load and programmatic land at the same y.

All questions resolved. No outstanding ambiguities.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Low — Ready for Architect**

Requirements to pass to Green:
- [x] Owner approved epic decomposition (1 epic, ~6 stories, S-16).
- [x] §6 AI Interrogation Loop questions answered and integrated.
- [x] §0 `<agent_context>` block validated against final answers.
- [x] 0 "TBDs" exist in the document.

## Proposed Story Decomposition (for Architect)

This block is informational — the Architect agent runs the Granularity Rubric and finalizes story splits. With voice presets and Reinstall dropped, the epic shrinks from 7 to ~6 stories. Proposed seams:

1. **STORY-025-01 — Shell foundation.** WorkspaceShell + StatusStrip + StickyTabBar + ModuleSection + useScrollspy + moduleRegistry skeleton. Scrollspy + deep-linking unit tests. No module bodies yet — placeholder cards.
2. **STORY-025-02 — Connections group migration.** Slack tile (info-only, no Reinstall), Drive tile, AI provider segmented control, Channels divider list. Wires existing hooks unchanged.
3. **STORY-025-03 — Knowledge group migration.** Files header strip + divider list. Reuses PickerSection + KnowledgeList logic; chrome only.
4. **STORY-025-04 — Behavior group migration.** Skills row redesign, Automation empty state, Persona section extraction (textarea behavior preserved). Pure frontend chrome — no backend, no schema.
5. **STORY-025-05 — Workspace group + owner gate.** Danger zone redesign + `assert_team_owner` re-introduction on DELETE + UI hide for non-owners.
6. **STORY-025-06 — Mobile + cutover.** Status strip 5→2 col, tab bar mobile pattern matching dashboard, delete legacy stacked layout, full test suite green, manual smoke of every module + deep-link. (Architect may split mobile and cutover into 2 stories if Granularity Rubric trips.)
