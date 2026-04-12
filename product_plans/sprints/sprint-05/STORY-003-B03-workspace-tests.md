---
story_id: "STORY-003-B03-workspace-tests"
parent_epic_ref: "EPIC-003"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §5"
actor: "QA Agent / Developer Agent"
complexity_label: "L2"
---

# STORY-003-B03: Backend Integration Tests (Workspaces)

**Complexity: L2** — Comprehensive test suite for workspace routes and race condition checks.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a Developer,
I want a comprehensive integration test suite for the workspace API against a live database,
So that I can prevent regressions, ensure 403 cross-user safety, and validate transaction atomicity.

### 1.2 Detailed Requirements
Create tests for:
- Happy path workspace creation and fetching.
- 403 cross-user access (unowned team/workspace).
- 404 missing workspace handling.
- First-workspace auto-default logic.
- Second-workspace non-default logic.
- Partial-unique-constraint validation on `make-default` (preventing transient states).
- Cascade on team delete.
- Response-model secret-field omission.

### 1.3 Out of Scope
- Modifying route logic (unless the tests find bugs that need immediate fixing).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: API Integration test Suite
  Scenario: Cross-user 403 defense
    Given Alice owns team A and Bob owns team B
    When Alice tries to list workspaces for team B
    Then response is 403 Forbidden

  Scenario: Workspace secrets omission
    When a workspace is queried via GET /api/workspaces/{id}
    Then the response body does not include encrypted_api_key
```

### 2.2 Verification Steps (Manual)
- [ ] Run `pytest backend/tests/test_workspaces_routes.py` successfully against the live Supabase instance.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Routes** | B02 Routes fully completed | [ ] |

### 3.1 Test Implementation
- Write `backend/tests/test_workspaces_routes.py` and `backend/tests/test_slack_teams_routes.py`.
- Use the FastAPI TestClient.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/tests/test_workspaces_routes.py` |
| **New Files Needed** | Yes |
| **ADR References** | ADR-024 |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Make sure Pytest runs these synchronously or provides isolated test teams so random test orders (BUG-20260411 fix) remain stable.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Integration tests | 8 | Cover all requirements in §1.2 |

### 4.2 Definition of Done (The Gate)
- [ ] No flaky test executions when running `pytest-randomly`.
