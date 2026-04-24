---
epic_id: "EPIC-023"
status: "Shipped"
approved: true
children:
  - "STORY-023-01-skills-list-ui"
  - "STORY-023-02-remove-landing-page"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Team Lead"
target_date: "TBD"
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-023_ux_production_readiness/EPIC-023_ux_production_readiness.md`. Carried forward during ClearGate migration 2026-04-24.

# EPIC-023: UX Production Readiness

## 1. Problem & Value

### 1.1 The Problem
Following a comprehensive UX Audit, two critical friction points were identified for the production release:
1. **Skill Amnesia**: Agent skills are created via Slack chat, but are completely invisible on the dashboard. Users have no way to see what the bot has been trained to do.
2. **Vestigial Landing Page**: The root path (`/`) displays a diagnostic system status page from Sprint 1, which provides no value to end-users and creates an unnecessary hop to get to the application.

### 1.2 The Solution
1. Introduce a read-only "Active Skills" widget on the Workspace Detail page.
2. Rip out the diagnostic landing page and replace it with a direct redirect to `/app` (which automatically routes unauthenticated users to `/login`).

### 1.3 Success Metrics (North Star)
- Users can view a list of active skills mapped to a knowledge base from the dashboard.
- Zero clicks required to reach the login/app page from the root domain.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)
- [x] Fetch skills via a new TanStack Query hook (`useSkillsQuery`).
- [x] Render a "SkillList" component in `/app/teams/$teamId/$workspaceId`.
- [x] Refactor `frontend/src/routes/index.tsx` to perform an immediate redirect to `/app`.

### ❌ OUT-OF-SCOPE (Do NOT Build This)
- UI for *editing* or *creating* skills (Skills remain chat-driven only).
- Complete uninstallation of the `/api/health` backend endpoint (keep it for DevOps/monitoring).

---

## 3. Context

### 3.1 Constraints
| Type | Constraint |
|------|------------|
| **UX** | Skills list must explicitly clarify that creation happens in Slack, to avoid confusing users looking for an "Add Skill" button. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: UX Production Readiness

  Scenario: Root Redirect
    Given a user navigates to the root domain
    When the app loads
    Then they are instantly redirected to `/app` (or `/login` via auth guard).

  Scenario: Skill Visibility
    Given the user is on a Workspace detail page
    When the page renders
    Then an 'Active Skills' card displays a list of the agent's learned behaviors with their names and descriptions.
```

---

## 8. Artifact Links

**Stories (Status Tracking):**
- [x] STORY-023-01-skills-list-ui -> Done
- [x] STORY-023-02-remove-landing-page -> Done

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-24 | Ported to ClearGate v0.2.1. Status mapped from "Done" → "Shipped". | ClearGate migration |
