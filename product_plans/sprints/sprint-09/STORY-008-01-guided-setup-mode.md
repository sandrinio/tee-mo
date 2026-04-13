---
story_id: "STORY-008-01-guided-setup-mode"
parent_epic_ref: "EPIC-008"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1 / Charter §5.3 / Design Guide §9.3 / Codebase"
actor: "New User"
complexity_label: "L3"
---

# STORY-008-01: Guided Setup Mode on Workspace Detail Page

**Complexity: L3** — Cross-cutting, touches 3+ files, component extraction + new UI pattern

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **new user** who just created a workspace,
I want to **see a step-by-step guide that walks me through Drive, Key, Files, and Channels setup**,
So that **I know exactly what to do next and don't miss any configuration step**.

### 1.2 Detailed Requirements
- **R1**: Extract `KeySection` (~300 lines, currently inline in `WorkspaceCard.tsx` lines 36–335) into a standalone `frontend/src/components/workspace/KeySection.tsx` component. Zero logic changes — same hooks (`useKeyQuery`, `useSaveKeyMutation`, `useDeleteKeyMutation`), same states (collapsed/expanded/delete-confirm), same UI. `WorkspaceCard` imports and renders the extracted component identically.
- **R2**: Add a **setup stepper** to the workspace detail page (`app.teams.$teamId.$workspaceId.tsx`). When setup is incomplete (any of: Drive not connected, no BYOK key, zero files), the page renders in "guided mode" with:
  - A horizontal step indicator at the top: 4 filled/empty circles labeled "Drive", "AI Key", "Files", "Channels"
  - Active step is highlighted with `brand-500`; completed steps show a checkmark; future steps are `slate-300`
  - Each step section is a card that expands when active and collapses when complete
- **R3**: Step completion logic:
  - Step 1 (Drive): complete when `useDriveStatusQuery` returns `connected: true`
  - Step 2 (AI Key): complete when `useKeyQuery` returns `has_key: true`
  - Step 3 (Files): complete when `useKnowledgeQuery` returns at least 1 file
  - Step 4 (Channels): always open (no hard gate — user may skip channels initially)
- **R4**: Steps 2-4 are gated (collapsed + disabled) until their prerequisite step is complete. Step 2 requires step 1. Step 3 requires step 2. Step 4 has no hard prerequisite but appears after step 3.
- **R5**: When all steps are complete (Drive connected + key configured + ≥1 file + page revisited), the guided mode is replaced by the normal detail view (existing DriveSection + PickerSection + KnowledgeList, now with KeySection and ChannelSection added).
- **R6**: The guided mode re-activates on page load whenever setup is incomplete. No localStorage or URL state needed — it's derived from query data.
- **R7**: Step 4 (Channels) renders a placeholder card with text "Bind Slack channels to this workspace" and a note "Coming in next step" until STORY-008-02 lands the `ChannelSection` component. This keeps 008-01 independently verifiable.
- **R8**: Embed the extracted `KeySection` as the content of Step 2.

### 1.3 Out of Scope
- Channel binding UI (STORY-008-02)
- Workspace card changes (STORY-008-03)
- Top nav (STORY-008-04)
- Design token cleanup in other files (folded into 008-03 and 008-04)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Guided Setup Mode

  Scenario: Incomplete setup shows guided mode
    Given a workspace with Drive not connected and no BYOK key
    When the workspace detail page loads
    Then the step indicator shows 4 steps
    And step 1 (Drive) is active and expanded
    And steps 2-4 are collapsed and grayed out

  Scenario: Drive connected advances to step 2
    Given a workspace with Drive connected but no BYOK key
    When the workspace detail page loads
    Then step 1 shows a checkmark (complete)
    And step 2 (AI Key) is active and expanded with KeySection
    And steps 3-4 remain collapsed

  Scenario: Key configured advances to step 3
    Given a workspace with Drive connected and BYOK key configured but 0 files
    When the workspace detail page loads
    Then steps 1-2 show checkmarks
    And step 3 (Files) is active with the Google Picker section
    And step 4 is visible but collapsed

  Scenario: All steps complete shows normal detail view
    Given a workspace with Drive connected, BYOK key, ≥1 file
    When the workspace detail page loads
    Then the guided mode is not shown
    And the normal detail view renders (Drive + Key + Files + Channels sections)

  Scenario: KeySection extraction preserves WorkspaceCard behavior
    Given a workspace with a BYOK key configured
    When the WorkspaceCard renders
    Then the KeySection shows the masked key, provider badge, and Update/Delete buttons
    And all interactions (expand, validate, save, delete) work identically

  Scenario: OAuth re-entry resumes guided mode
    Given a user on step 1 who clicked "Connect Drive" and completed OAuth
    When the browser redirects back to /app?drive_connect=ok
    And the user navigates to the workspace detail page
    Then step 1 shows complete (Drive is now connected)
    And step 2 is active
```

### 2.2 Verification Steps (Manual)
- [ ] `npm run build` succeeds (no TypeScript errors)
- [ ] `npx vitest run` — all existing WorkspaceCard tests pass after KeySection extraction
- [ ] New component tests for `SetupStepper` pass
- [ ] Guided mode activates for a new workspace with no config
- [ ] Completing Drive OAuth returns to workspace and advances stepper
- [ ] Adding a BYOK key advances stepper to step 3
- [ ] Adding a file transitions page to normal detail view

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | No new dependencies | [ ] |
| **Dev Server** | `npm run dev` in `frontend/` | [ ] |

### 3.1 Test Implementation
- Create `frontend/src/components/workspace/__tests__/KeySection.test.tsx` — render tests verifying collapsed/expanded states, validate/save flow (mock hooks)
- Create `frontend/src/components/workspace/__tests__/SetupStepper.test.tsx` — render tests for step indicator states (all incomplete, partial, all complete)
- Verify existing `WorkspaceCard` tests still pass after extraction

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (590 lines — major modify) |
| **Related Files** | `frontend/src/components/dashboard/WorkspaceCard.tsx` (477 lines — extract KeySection), `frontend/src/components/workspace/KeySection.tsx` (new), `frontend/src/components/workspace/SetupStepper.tsx` (new) |
| **New Files Needed** | Yes — `KeySection.tsx`, `SetupStepper.tsx` |
| **ADR References** | ADR-022 (design system), ADR-024 (workspace model) |
| **First-Use Pattern** | No — builds on existing TanStack Query patterns |

### 3.3 Technical Logic

**KeySection extraction:**
1. Cut lines 36–335 from `WorkspaceCard.tsx` (the `KeySection` function and its internal state/hooks)
2. Paste into `frontend/src/components/workspace/KeySection.tsx` as a named export
3. Props: `workspaceId: string`, `teamId: string` (currently derived from route params in WorkspaceCard — pass explicitly)
4. `WorkspaceCard.tsx` imports `KeySection` and renders it in the same position
5. Run existing tests — zero behavior change

**SetupStepper component:**
```tsx
// frontend/src/components/workspace/SetupStepper.tsx
interface SetupStep {
  key: string;
  label: string;
  isComplete: boolean;
  content: React.ReactNode;
}

function SetupStepper({ steps }: { steps: SetupStep[] }) {
  // Determine active step: first incomplete step
  // Render horizontal indicator (circles + labels)
  // Render active step content in a Card
  // Completed steps: checkmark circle (brand-500)
  // Active step: filled circle (brand-500) + expanded card
  // Future steps: empty circle (slate-300) + collapsed
}
```

**Workspace detail page integration:**
```tsx
// In app.teams.$teamId.$workspaceId.tsx
const driveStatus = useDriveStatusQuery(workspaceId);
const keyData = useKeyQuery(workspaceId);
const knowledge = useKnowledgeQuery(workspaceId);

const isSetupComplete = driveStatus.data?.connected
  && keyData.data?.has_key
  && (knowledge.data?.length ?? 0) > 0;

if (!isSetupComplete) {
  return <SetupStepper steps={[
    { key: 'drive', label: 'Connect Drive', isComplete: driveStatus.data?.connected ?? false, content: <DriveSection ... /> },
    { key: 'key', label: 'AI Key', isComplete: keyData.data?.has_key ?? false, content: <KeySection workspaceId={workspaceId} teamId={teamId} /> },
    { key: 'files', label: 'Add Files', isComplete: (knowledge.data?.length ?? 0) > 0, content: <PickerSection ... /> },
    { key: 'channels', label: 'Channels', isComplete: false, content: <ChannelPlaceholder /> },
  ]} />;
}

// Normal detail view (existing code)
```

**Step indicator design (per design guide §9.3):**
- Circles: `h-8 w-8 rounded-full` — complete: `bg-brand-500 text-white`, active: `ring-2 ring-brand-500 bg-white text-brand-500`, future: `bg-slate-200 text-slate-400`
- Lines between circles: `h-0.5 flex-1` — complete: `bg-brand-500`, future: `bg-slate-200`
- Labels below circles: `text-xs font-medium` — active: `text-brand-600`, else: `text-slate-500`

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 6 | KeySection render (2: collapsed no key, collapsed with key), SetupStepper states (4: all incomplete, partial, all complete, re-entry after OAuth) |
| Unit tests | 2 | Step completion logic, active step derivation |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted (jsdom modal limitation, TanStack Router layout routes, vitest globals).
- [ ] No ADR violations.
- [ ] KeySection extraction is zero-behavior-change — existing WorkspaceCard renders identically.
- [ ] Guided mode activates on incomplete setup, deactivates on complete setup.
- [ ] `npm run build` passes.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
