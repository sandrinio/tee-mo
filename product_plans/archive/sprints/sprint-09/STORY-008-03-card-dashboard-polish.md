---
story_id: "STORY-008-03-card-dashboard-polish"
parent_epic_ref: "EPIC-008"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1 / Design Guide §6.3, §6.6, §9.2 / Codebase"
actor: "Workspace Owner"
complexity_label: "L2"
---

# STORY-008-03: Workspace Card & Dashboard List Polish

**Complexity: L2** — 2-3 files, known patterns, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **workspace owner**,
I want to **see at a glance which workspaces are fully set up, which channels are bound, and which workspace handles DMs**,
So that **I can quickly assess the state of my configuration without clicking into each workspace**.

### 1.2 Detailed Requirements

**Workspace card enhancements (`WorkspaceCard.tsx`):**
- **R1**: Add a **channel chips row** below the existing card content. Reuse the chip/pill styling from STORY-008-02's `ChannelSection` (same `Badge` pattern: green for Active, amber for Pending). Show up to 3 chips inline; if more, show "+N more" overflow pill.
- **R2**: Add a **"DMs route here"** text badge on the card that has `is_default_for_team === true`. Style: `text-xs font-medium text-brand-600 bg-brand-50 rounded-full px-2 py-0.5`. Show next to the existing "Default" badge.
- **R3**: Add a **setup completeness indicator** below the workspace name: show small inline status tags for each setup component. Pattern: "Drive" (green if connected, slate if not), "Key" (green if configured, slate if not), "Files N/15" (green if >0, slate if 0). Use `text-xs` captions.
- **R4**: Fetch channel bindings data for each workspace card using `useChannelBindingsQuery(workspaceId)`.

**Workspace list page enhancements (`app.teams.$teamId.index.tsx`):**
- **R5**: Change layout to grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6` per design guide §9.2.
- **R6**: "New Workspace" button creates workspace via `CreateWorkspaceModal`, then on success navigates to `/app/teams/$teamId/$newWorkspaceId` (entering guided setup mode from STORY-008-01).
- **R7**: Empty state follows design guide §6.7: dashed border (`border-2 border-dashed border-slate-200 bg-slate-50`), centered text, CTA button.

**Design token cleanup (these files only):**
- **R8**: Replace all hardcoded `#E94560` / `bg-[#E94560]` with `brand-500` / `bg-brand-500` in: `WorkspaceCard.tsx` (2 instances), `CreateWorkspaceModal.tsx` (2 instances), `RenameWorkspaceModal.tsx` (2 instances), `app.teams.$teamId.index.tsx` (3 instances).
- **R9**: Replace ad-hoc `<button className="bg-[#E94560] ...">` elements with `<Button variant="primary">` (import from `frontend/src/components/ui/Button.tsx`) in the same files.

### 1.3 Out of Scope
- Channel binding CRUD (STORY-008-02 — this story only *displays* bindings on the card)
- Guided setup mode (STORY-008-01)
- Top nav (STORY-008-04)
- Token cleanup in `app.index.tsx` or `app.teams.$teamId.$workspaceId.tsx` (owned by 008-04 and 008-01)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Workspace Card & Dashboard Polish

  Scenario: Card shows channel chips
    Given a workspace with 2 bound channels (#general Active, #eng Pending)
    When the WorkspaceCard renders
    Then 2 channel chips are visible
    And #general has a green "Active" badge
    And #eng has an amber "Pending /invite" badge

  Scenario: Card shows DM badge on default workspace
    Given a workspace with is_default_for_team = true
    When the WorkspaceCard renders
    Then a "DMs route here" badge is visible next to the "Default" badge

  Scenario: Card shows setup completeness
    Given a workspace with Drive connected, no BYOK key, 0 files
    When the WorkspaceCard renders
    Then "Drive" indicator shows green
    And "Key" indicator shows slate/muted
    And "Files 0/15" indicator shows slate/muted

  Scenario: Workspace list uses grid layout
    Given a Slack team with 4 workspaces
    When the workspace list page renders at desktop width
    Then workspaces are displayed in a 3-column grid

  Scenario: New workspace navigates to guided setup
    Given the user clicks "New Workspace" and enters a name
    When the workspace is created successfully
    Then the browser navigates to /app/teams/$teamId/$newWorkspaceId
    And the guided setup mode is visible (from STORY-008-01)

  Scenario: No hardcoded hex colors remain
    Given any of the modified files
    When the source is searched for #E94560 or bg-[#E94560]
    Then zero matches are found

  Scenario: Empty workspace list shows dashed empty state
    Given a Slack team with 0 workspaces
    When the workspace list page renders
    Then an empty state with dashed border and CTA button is shown
```

### 2.2 Verification Steps (Manual)
- [ ] `npm run build` succeeds
- [ ] `npx vitest run` — all tests pass
- [ ] `grep -r "E94560" frontend/src/components/dashboard/ frontend/src/routes/app.teams` returns no matches
- [ ] Workspace cards show channel chips and setup indicators in the browser
- [ ] Default workspace shows "DMs route here" badge
- [ ] Grid layout responds correctly at mobile/tablet/desktop widths
- [ ] Creating a new workspace navigates to its detail page

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | STORY-008-02 merged (channel hooks + ChannelSection available) | [ ] |
| **Dependencies** | STORY-008-01 merged (guided setup mode on detail page) | [ ] |

### 3.1 Test Implementation
- Update `frontend/src/components/dashboard/__tests__/WorkspaceCard.test.tsx` (if exists) or create it — test channel chips render, DM badge, setup indicators
- Update workspace list page tests — grid layout, empty state, new-workspace navigation

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/components/dashboard/WorkspaceCard.tsx` (modify) |
| **Related Files** | `frontend/src/routes/app.teams.$teamId.index.tsx` (modify), `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` (modify — tokens + Button), `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` (modify — tokens + Button) |
| **New Files Needed** | No |
| **ADR References** | ADR-022 (design system), ADR-024 (workspace model), ADR-025 (channel binding) |
| **First-Use Pattern** | No |

### 3.3 Technical Logic

**WorkspaceCard channel chips:**
```tsx
// After existing card content, before KeySection
const bindings = useChannelBindingsQuery(workspace.id);

{bindings.data && bindings.data.length > 0 && (
  <div className="mt-3 flex flex-wrap gap-1.5">
    {bindings.data.slice(0, 3).map(b => (
      <span key={b.slack_channel_id} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
        b.is_member ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
      }`}>
        <span className={`h-1.5 w-1.5 rounded-full ${b.is_member ? 'bg-emerald-500' : 'bg-amber-500'}`} />
        #{b.channel_name}
      </span>
    ))}
    {bindings.data.length > 3 && (
      <span className="text-xs text-slate-500">+{bindings.data.length - 3} more</span>
    )}
  </div>
)}
```

**DM badge:**
```tsx
{workspace.is_default_for_team && (
  <>
    <span className="...existing default badge...">Default</span>
    <span className="text-xs font-medium text-brand-600 bg-brand-50 rounded-full px-2 py-0.5">
      DMs route here
    </span>
  </>
)}
```

**Token cleanup pattern (all files):**
- Find: `bg-[#E94560]` → Replace: `bg-brand-500`
- Find: `hover:bg-[#d13a54]` or similar → Replace: `hover:bg-brand-600`
- Find: `focus:ring-[#E94560]` → Replace: `focus:ring-brand-500`
- Find: `text-[#E94560]` → Replace: `text-brand-500`
- Replace ad-hoc `<button>` with `<Button variant="primary">` or `<Button variant="secondary">` imports

**Navigate after create:**
```tsx
// In CreateWorkspaceModal onSuccess:
const navigate = useNavigate();
// After mutation success:
onClose();
navigate({ to: '/app/teams/$teamId/$workspaceId', params: { teamId, workspaceId: newWorkspace.id } });
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 5 | Card with channels, card with DM badge, card with setup indicators, empty state, grid layout |
| Unit tests | 0 | N/A — no standalone logic |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
- [ ] Zero hardcoded `#E94560` in modified files.
- [ ] All buttons use `Button` component.
- [ ] `npm run build` passes.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 137 | 10,864 | 11,001 |
