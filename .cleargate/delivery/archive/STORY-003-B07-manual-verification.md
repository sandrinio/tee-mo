---
story_id: "STORY-003-B07-manual-verification"
parent_epic_ref: "EPIC-003"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-05/STORY-003-B07-manual-verification.md`. Shipped in sprint S-05, carried forward during ClearGate migration 2026-04-24.

# STORY-003-B07: Manual Verification (Release 1 Exit)

**Complexity: L1** — Final manual QA walkthrough for Release 1.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As the Product Owner,
I want a full manual end-to-end walkthrough of the app,
So we can declare Release 1 officially complete and bug-free.

### 1.2 Detailed Requirements
- Execute an end-to-end user registration and team setup flow:
  - Register new account.
  - Traverse the S-04 real Slack OAuth installation flow.
  - Land on `/app` and see the new real team.
  - Access `/app/teams/$teamId`.
  - Create workspace.
  - Rename it.
  - Create another workspace, make it default.
  - Sign out, sign in (verify state persists).
- Verify `npm run build` exits cleanly.
- Verify existing Vitest E2E suites and Backend Pytests pass 100%.

### 1.3 Out of Scope
- Code changes (unless regressions are found).

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: E2E Release Verification
  Scenario: Full End User Journey
    Given a fresh DB
    When user registers, connects Slack, manages workspaces
    Then all steps complete without 500s or UI errors
```

### 2.2 Verification Steps (Manual)
- [ ] As per the detailed requirements in §1.2.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Release** | All previous S-05 and S-04 stories completed. | [ ] |

### 3.1 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | Verification only |
| **New Files Needed** | No |

### 3.2 Technical Logic
- Any failures found here should be raised as bugs and fixed immediately within the Sprint context before declaring it complete.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| E2E | 1 | Full manual walkthrough |

### 4.2 Definition of Done (The Gate)
- [ ] No regression bugs discovered.
- [ ] Build process verifies green locally.
