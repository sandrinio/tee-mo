---
story_id: "STORY-003-B06-rename-make-default"
parent_epic_ref: "EPIC-003"
status: "Blocked — Pending S-04"
ambiguity: "🟢 Low"
context_source: "Epic §5"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-003-B06: Workspace Rename & Make Default

**Complexity: L2** — Finishing the workspace card actions.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a User,
I want to rename my workspaces and change which one is the default,
So I can adjust my environment as my team needs change.

### 1.2 Detailed Requirements
- Build `RenameWorkspaceModal` inside the Workspace Card (same form structure as create).
- Hook up the "Rename" action button in `WorkspaceCard.tsx` to the mutation.
- Hook up "Make default" action with optimistic UI update + rollback on error.
- NO external toast library; use inline error cards directly inside the workspace card or the page's standard error boundary.

### 1.3 Out of Scope
- Workspace deletion (deferred post EPIC-007).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Workspace Card Actions
  Scenario: Make default
    Given a non-default workspace card
    When the user clicks Make Default
    Then the mutation is fired
    And the UI optimistically updates to move the "Default" badge
```

### 2.2 Verification Steps (Manual)
- [ ] Click "Make default" and ensure only one workspace has the badge.
- [ ] Disconnect internet, click Make Default, verify it gracefully rolls back and shows an error inline.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **UI** | B05 components exist | [ ] |

### 3.1 Test Implementation
- Add tests for the `WorkspaceCard` covering action buttons.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/components/dashboard/WorkspaceCard.tsx` |
| **Related Files** | `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` |
| **New Files Needed** | Yes |
| **ADR References** | ADR-022 |
| **First-Use Pattern** | Yes — "TanStack Optimistic Updates" |

### 3.3 Technical Logic
- TanStack Query `onMutate` runs optimistic update. `onError` rolls back state. `onSettled` invalidates the query. Follow standard docs.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 2 | Test rename modal and optimistic action |

### 4.2 Definition of Done (The Gate)
- [ ] No Radix toasts used.
- [ ] Optimistic update logic handles rollbacks cleanly.
