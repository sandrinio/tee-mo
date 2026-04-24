---
story_id: "STORY-023-02-remove-landing-page"
parent_epic_ref: "EPIC-023"
status: "Shipped"
approved: true
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-023_ux_production_readiness/STORY-023-02-remove-landing-page.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-023-02: Remove Vestigial Landing Page

**Complexity: L1** — Trivial route rewrite to remove the old `/api/health` diagnostic landing page and redirect to the application entry.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> As a **Returning User**,
> I want to **go straight to the app when navigating to the root domain**,
> So that **I don't have to click 'Continue to login' on a diagnostic dummy page.**

### 1.2 Detailed Requirements
- **Requirement 1**: Re-write `frontend/src/routes/index.tsx`.
- **Requirement 2**: Remove all UI code, queries to `/api/health`, and UI imports.
- **Requirement 3**: Use `<Navigate to="/app" />` so any traffic to `/` is pushed to `/app`. (Assuming auth guards catch `/app` and route to `/login` if unauthenticated).

### 1.3 Out of Scope
- Deleting the `/api/health` backend endpoint. That remains available for server checks.

### TDD Red Phase: No
> Pure configuration file change.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Remove Diagnostic Landing Page

  Scenario: Immediate Redirect
    When a user visits `/`
    Then the browser immediately redirects to `/app`
```

### 2.2 Verification Steps (Manual)
- [ ] Spin up the frontend, navigate to `http://localhost:5173/`, and verify you land on `/login` (due to guards) or `/app`.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
N/A

### 3.1 Test Implementation
N/A

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/index.tsx` |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Open `frontend/src/routes/index.tsx`.
- Keep `import { createFileRoute, Navigate } from '@tanstack/react-router';`
- Strip the `Landing` UI component and query completely.
- Replace it with:
```typescript
export const Route = createFileRoute('/')({
  component: () => <Navigate to="/app" />,
});
```

### 3.4 API Contract (If applicable)
N/A

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |

### 4.2 Definition of Done (The Gate)
- [ ] Root path completely redirects.

---

## Token Usage
> Auto-populated by agents. Each agent runs `node .vbounce/scripts/count_tokens.mjs --self --append <this-file> --name <Agent>` before writing their report.

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
