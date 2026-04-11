---
story_id: "STORY-003-B02-workspace-routes"
parent_epic_ref: "EPIC-003"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Epic §5, §4"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-003-B02: Backend Workspace Routes

**Complexity: L2** — REST endpoints for Workspace CRUD execution.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a User,
I want to create, rename, and manage my workspaces via the API,
So that I can organize my AI tools within my Slack teams.

### 1.2 Detailed Requirements
- `GET /api/slack-teams/{team_id}/workspaces`: list scoped to current user.
- `POST /api/slack-teams/{team_id}/workspaces`: create. Auto-set `is_default_for_team=TRUE` if it's the first workspace under that team.
- `GET /api/workspaces/{id}`: fetch single.
- `PATCH /api/workspaces/{id}`: rename only (accepts `{name}`).
- `POST /api/workspaces/{id}/make-default`: atomic default swap in a transaction.
- Create an authorization helper `assert_team_owner(team_id, user_id)` to prevent cross-user access (returns 403).

### 1.3 Out of Scope
- Full Integration tests (these are handled and expanded heavily in B03).
- Frontend changes.
- Delete workspace endpoint.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Workspace Routes

  Scenario: Create first workspace
    Given a user with a valid Slack team and zero workspaces
    When the user POSTs to create a new workspace
    Then the response is 201 Created
    And the workspace has is_default_for_team = true
```

### 2.2 Verification Steps (Manual)
- [ ] Create a workspace using raw Swagger / curl and visually inspect DB state.
- [ ] Verify `assert_team_owner` properly returns 403 when trying to fetch a workspace ID not owned by the user.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Models** | STORY-003-B01 models merged | [ ] |

### 3.1 Test Implementation
- Add basic route validation tests in `test_workspaces_routes.py` (B03 will extend this heavily).

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/workspaces.py` |
| **Related Files** | `backend/app/api/deps.py`, `backend/app/main.py` |
| **New Files Needed** | Yes — `backend/app/api/routes/workspaces.py` |
| **ADR References** | ADR-024 |
| **First-Use Pattern** | Yes — "Supabase Atomic Transaction for Default Swap" |

### 3.3 Technical Logic
- Mount the new router in `backend/app/main.py`.
- The `make-default` atomic logic: In a single transactional block: `UPDATE ... SET is_default_for_team = FALSE WHERE slack_team_id = $1 AND is_default_for_team = TRUE` followed by `UPDATE ... SET is_default_for_team = TRUE WHERE id = $2`.

### 3.4 API Contract (If applicable)
| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/slack-teams/{team_id}/workspaces` | GET | Bearer | null | `Workspace[]` |
| `/api/slack-teams/{team_id}/workspaces` | POST | Bearer | `{ name: string }` | `Workspace` |
| `/api/workspaces/{id}` | GET | Bearer | null | `Workspace` |
| `/api/workspaces/{id}` | PATCH | Bearer | `{ name: string }` | `Workspace` |
| `/api/workspaces/{id}/make-default` | POST | Bearer | null | `Workspace` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 | N/A |
| Integration tests | 2 | Minimum happy path (B03 covers edge cases) |

### 4.2 Definition of Done (The Gate)
- [ ] `assert_team_owner` reliably stops all cross-user leakage.
- [ ] `make-default` maintains the partial unique constraints correctly.
