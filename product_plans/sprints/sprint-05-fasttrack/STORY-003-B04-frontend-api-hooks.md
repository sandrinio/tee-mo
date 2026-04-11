---
story_id: "STORY-003-B04-frontend-api-hooks"
parent_epic_ref: "EPIC-003"
status: "Ready for Parallel"
ambiguity: "🟢 Low"
context_source: "Epic §5"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-003-B04: Frontend API API Wrappers & Hooks

**Complexity: L2** — TanStack Query hooks for workspace data.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a Frontend Developer,
I want typed API wrappers and TanStack Query hooks,
So that I can easily fetch, cache, and mutate workspace data in React components.

### 1.2 Detailed Requirements
- Add typed wrappers to `frontend/src/lib/api.ts`: `listSlackTeams`, `listWorkspaces(teamId)`, `createWorkspace(teamId, name)`, `getWorkspace(id)`, `renameWorkspace(id, name)`, `makeWorkspaceDefault(id)`.
- Define `SlackTeam` and `Workspace` TypeScript types.
- Create TanStack Query hooks in `frontend/src/hooks/useWorkspaces.ts`: `useSlackTeamsQuery`, `useWorkspacesQuery`, `useWorkspaceQuery`, `useCreateWorkspaceMutation`, `useRenameWorkspaceMutation`, `useMakeDefaultMutation`.

### 1.3 Out of Scope
- Building the UI that consumes these (B05 and B06).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: API Hooks Caching and Invalidation
  Scenario: Making a workspace default invalidates the list
    When useMakeDefaultMutation is called successfully
    Then the queryClient invalidates the workspaces query for that team
```

### 2.2 Verification Steps (Manual)
- [ ] Ensure that `npm run build` exits 0 with zero TypeScript errors.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Backend** | B02 running | [ ] |

### 3.1 Test Implementation
- Write `frontend/src/hooks/useWorkspaces.test.tsx`. Note: Remember Vitest TDZ `vi.hoisted()` for mocking API calls or setting up query clients.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/hooks/useWorkspaces.ts` |
| **Related Files** | `frontend/src/lib/api.ts` |
| **New Files Needed** | Yes |
| **ADR References** | ADR-022 |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Mutations must handle invalidating the `['workspaces', teamId]` query key upon success to automatically refresh the data.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 2 | Test hooks via a wrapper component or renderHook |

### 4.2 Definition of Done (The Gate)
- [ ] No raw `fetch` calls in components (all via `lib/api.ts`).
- [ ] Types perfectly match backend response models.
