---
story_id: "STORY-003-B01-workspace-models"
parent_epic_ref: "EPIC-003"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §5, §4"
actor: "Developer Agent"
complexity_label: "L1"
---

# STORY-003-B01: Backend Workspace Models

**Complexity: L1** — Backend model schemas for workspace CRUD.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a Developer,
I need the Pydantic data schemas for workspaces,
So that I can implement CRUD routes safely without leaking secret tokens.

### 1.2 Detailed Requirements
- Create `Workspace` response model. EXPLICITLY OMIT `encrypted_api_key`, `encrypted_google_refresh_token`, and any other secrets.
- Create `WorkspaceCreate` request model (requires `name` and `slack_team_id`).
- Create `WorkspaceUpdate` request model (requires `name` only).

### 1.3 Out of Scope
- Actually implementing the API routes (deferred to B02).

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Workspace Response Model Security

  Scenario: Model omits secrets
    Given a Workspace internal data object with encrypted_api_key
    When it is serialized using the Workspace response model
    Then the output JSON does not contain encrypted_api_key
```

### 2.2 Verification Steps (Manual)
- [ ] Inspect `backend/app/models/workspace.py` to ensure secrets are completely absent from the main response model structure.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Migrations** | DB migrated to at least 007 (S-03 completed) | [ ] |

### 3.0a Salvage Source (Sprint S-05 — from aborted S-05-fasttrack)
All three files below are pre-validated and SHOULD be copied verbatim via `git show e98d378:<path>`:
- `backend/app/models/workspace.py` — 52 lines, `WorkspaceBase`, `WorkspaceCreate`, `WorkspaceUpdate`, `WorkspaceResponse`
- `backend/tests/test_workspace_models.py` — 38 lines, `test_workspace_response_omits_secrets`
- `backend/app/models/__init__.py` — adds `WorkspaceCreate`, `WorkspaceResponse`, `WorkspaceUpdate` to `__all__`

### 3.1 Test Implementation
- Add schema unit tests in `backend/tests/test_workspace_models.py` to explicitly enforce secret exclusion.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/models/workspace.py` |
| **Related Files** | `backend/app/models/__init__.py` |
| **New Files Needed** | Yes — `backend/app/models/workspace.py` |
| **ADR References** | ADR-024, ADR-026 |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Ensure that the primary response model allows parsing from the DB (`orm_mode` / `from_attributes = True`) but fields like `encrypted_api_key` are either absent from the Pydantic model completely or explicitly excluded in serialization logic.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 1 | Serialize test verifying no secret leaks |
| Component tests | 0 | N/A |
| E2E / acceptance tests | 0 | N/A |
| Integration tests | 0 | N/A |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] FLASHCARDS.md + Sprint Context consulted before implementation.
- [ ] Models exported properly in `backend/app/models/__init__.py`.
