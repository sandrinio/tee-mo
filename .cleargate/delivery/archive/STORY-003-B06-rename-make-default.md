---
story_id: "STORY-003-B06-rename-make-default"
parent_epic_ref: "EPIC-003"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-05/STORY-003-B06-rename-make-default.md`. Shipped in sprint S-05, carried forward during ClearGate migration 2026-04-24.

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

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 1,078 | 1,174 | 2,252 |
