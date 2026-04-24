---
story_id: "STORY-003-B05-team-workspace-list"
parent_epic_ref: "EPIC-003"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §5, §9.2"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-003-B05: Frontend Workspace List UI

**Complexity: L2** — The main `/app/teams/$teamId` page layout and workspace creation modal.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a User,
I want to see a list of my workspaces within a team and be able to create new ones,
So I can manage the different silos of my AI data.

### 1.2 Detailed Requirements
- Create route `app.teams.$teamId.tsx` (or nested setup).
- Build the page header showing team name + breadcrumb "← Teams".
- Build the Workspace list grid using `Card` primitives (per Design Guide §9.2).
- Add "+ New Workspace" primary button.
- Create `CreateWorkspaceModal` (native `<form>`, one `name` field, inline error reporting). 
- Display workspace name, "Default for DMs" badge, "Not connected" chips.

### 1.3 Out of Scope
- Actually hooking up Rename and Make Default logic to the UI (B06).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Workspace List UI
  Scenario: Open create modal
    Given the user is on the team detail page
    When they click "+ New Workspace"
    Then the Create Workspace modal opens
    And submitting a name calls the API and closes the modal on success
```

### 2.2 Verification Steps (Manual)
- [ ] Navigate to `/app` (post Slack install) and into a team.
- [ ] Visually verify grid layout aligns with the Design Guide.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **API Hooks** | B04 completed | [ ] |

### 3.1 Test Implementation
- Component test for `CreateWorkspaceModal` verifying form submit and error rendering.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/app.teams.$teamId.tsx` |
| **Related Files** | `frontend/src/components/dashboard/CreateWorkspaceModal.tsx`, `WorkspaceCard.tsx` |
| **New Files Needed** | Yes |
| **ADR References** | ADR-022 |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- TanStack Router file-based route. Warning: The Vite rebuild flake (`tsc -b && vite build`) might occur when adding a new route file. Wait for the gen file to update.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 2 | Test modal render and form submit |

### 4.2 Definition of Done (The Gate)
- [ ] `npm run build` passes strict TS checks.
- [ ] No new `@theme` tokens added (use built-in Tailwind 4).
