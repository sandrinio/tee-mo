---
story_id: "STORY-006-09"
parent_epic_ref: "EPIC-006"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Codebase workspaces.py, migrations ON DELETE CASCADE / User Input"
actor: "Workspace Admin"
complexity_label: "L1"
---

# STORY-006-09: Delete Workspace

**Complexity: L1** — Single endpoint + frontend button, known pattern, <1hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin**,
> I want to delete a workspace I own,
> So that all associated data (skills, knowledge files, channel bindings, keys) is permanently removed.

### 1.2 Detailed Requirements

- **R1: Backend endpoint** — `DELETE /api/workspaces/{workspace_id}` deletes the workspace row. PostgreSQL `ON DELETE CASCADE` handles all child tables automatically:
  - `teemo_skills` (workspace_id FK CASCADE)
  - `teemo_knowledge_index` (workspace_id FK CASCADE)
  - `teemo_workspace_channels` (workspace_id FK CASCADE)
- **R2: Owner-only** — Only the user who owns the workspace (matched by `user_id` from JWT) can delete it. Returns 404 if workspace doesn't exist or isn't owned by the caller.
- **R3: Return 204 No Content** on success.
- **R4: Default workspace guard** — If the deleted workspace was `is_default_for_team = true`, no automatic re-assignment. The team simply has no default until the user sets one. This is a safe-fail state the frontend already handles.
- **R5: Frontend** — Add a "Delete Workspace" button to the workspace detail page with a confirmation dialog. On success, navigate back to the team page.
- **R6: API client** — Add `deleteWorkspace(workspaceId)` to `frontend/src/lib/api.ts`.
- **R7: TanStack Query invalidation** — Invalidate the workspaces list query on successful deletion.

### 1.3 Out of Scope
- Soft delete / archive — hard delete only
- Bulk delete multiple workspaces
- Admin override (only owner can delete)
- Google Drive token revocation on workspace delete (token is just discarded; Google revocation is a EPIC-009 polish item)

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Delete Workspace

  Scenario: Owner deletes workspace — all data cascaded
    Given user "alice" owns workspace "ws-1" with 3 skills, 2 knowledge files, and 1 channel binding
    When alice sends DELETE /api/workspaces/ws-1
    Then the response is 204 No Content
    And teemo_workspaces has no row with id "ws-1"
    And teemo_skills has no rows with workspace_id "ws-1"
    And teemo_knowledge_index has no rows with workspace_id "ws-1"
    And teemo_workspace_channels has no rows with workspace_id "ws-1"

  Scenario: Non-owner cannot delete
    Given user "bob" does NOT own workspace "ws-1"
    When bob sends DELETE /api/workspaces/ws-1
    Then the response is 404

  Scenario: Unauthenticated request
    When an unauthenticated request sends DELETE /api/workspaces/ws-1
    Then the response is 401

  Scenario: Workspace not found
    When alice sends DELETE /api/workspaces/nonexistent-id
    Then the response is 404

  Scenario: Frontend delete flow
    Given alice is on the workspace detail page for "ws-1"
    When she clicks "Delete Workspace"
    Then a confirmation dialog appears
    When she confirms
    Then the workspace is deleted
    And she is redirected to the team page
    And "ws-1" no longer appears in the workspace list
```

### 2.2 Verification Steps (Manual)
- [ ] Create a workspace with skills, files, and channel bindings → delete it → verify all related rows gone
- [ ] Try deleting someone else's workspace → 404
- [ ] Delete the default workspace → team has no default, frontend handles gracefully

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Services Running** | Backend + frontend dev servers | [ ] |
| **Env Vars** | None new | [x] |

### 3.1 Test Implementation
- Add to `backend/tests/test_workspace_routes.py` (or create if not exists):
  - Test: DELETE returns 204, workspace row gone
  - Test: DELETE with non-owner returns 404
  - Test: DELETE with bad UUID returns 404
  - Test: unauthenticated returns 401

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/workspaces.py` |
| **Related Files** | `frontend/src/lib/api.ts`, `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` |
| **New Files Needed** | No |
| **ADR References** | ADR-024 (workspace schema) |
| **First-Use Pattern** | No |

### 3.3 Technical Logic

#### Backend — `workspaces.py`

Add after the `make_workspace_default` endpoint:

```python
@router.delete(
    "/workspaces/{workspace_id}",
    status_code=204,
)
async def delete_workspace(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Delete a workspace and all associated data.

    PostgreSQL ON DELETE CASCADE removes child rows from:
    teemo_skills, teemo_knowledge_index, teemo_workspace_channels.
    """
    sb = get_supabase()
    result = (
        sb.table("teemo_workspaces")
        .delete()
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")
```

#### Frontend — `api.ts`

Add:
```typescript
export async function deleteWorkspace(workspaceId: string): Promise<void> {
  await fetchApi(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
}
```

#### Frontend — workspace detail page

Add a "Delete Workspace" button (red, bottom of page or in a danger zone section). On click:
1. Show confirmation dialog: "Delete this workspace? All skills, files, and channel bindings will be permanently removed."
2. On confirm: call `deleteWorkspace(workspaceId)`
3. Invalidate `['workspaces', teamId]` query
4. Navigate to `/app/teams/${teamId}`

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 4 | 204 success + cascade, 404 non-owner, 404 not found, 401 unauth |
| Component tests | 0 | N/A |
| E2E / acceptance tests | 0 | Manual (§2.2) |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met — 4 tests.
- [ ] FLASHCARDS.md consulted.
- [ ] DELETE returns 204 with empty body.
- [ ] ON DELETE CASCADE verified (no orphaned rows).
- [ ] Frontend confirmation dialog prevents accidental deletion.
- [ ] Navigation back to team page on success.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 34 | 2,721 | 2,755 |
