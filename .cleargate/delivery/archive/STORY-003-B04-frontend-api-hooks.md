---
story_id: "STORY-003-B04-frontend-api-hooks"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-05/STORY-003-B04-frontend-api-hooks.md`. Shipped in sprint S-05, carried forward during ClearGate migration 2026-04-24.

# STORY-003-B04: Frontend API Wrappers & Hooks

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
| **Models** | B01 models merged (type contract for `Workspace`) | [ ] |
| **Backend B02** | NOT required — hooks are tested against mocked API module (`vi.mock('../lib/api')`) | N/A |

### 3.0a Salvage Source (Sprint S-05 — from aborted S-05-fasttrack)
Pre-validated files from `git show e98d378:<path>`:
- `frontend/src/hooks/useWorkspaces.ts` — 90 lines, 6 hooks. Copy verbatim.
- `frontend/src/hooks/useWorkspaces.test.tsx` — 45 lines, 1 test. Copy + **extend with 1 more test** (e.g. `useMakeDefaultMutation` invalidation) to meet §4.1 minimum of 2.
- `frontend/src/lib/api.ts` — **DO NOT apply the branch diff as-is.** It destructively rewrites S-04's `SlackTeam`/`SlackTeamsResponse`/`listSlackTeams`. Instead, ADDITIVELY copy only: `Workspace` interface, `apiPatch<TReq, TRes>()` helper, and the 5 new workspace wrappers (`listWorkspaces`, `getWorkspace`, `createWorkspace`, `renameWorkspace`, `makeWorkspaceDefault`). Leave all S-04 exports untouched.

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
