---
story_id: "STORY-018-05-ui-list-history"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "TBD"
target_date: "TBD"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-15T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-05-ui-list-history.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-05: Dashboard UI — Automations Section + History Drawer

**Complexity: L2** — TypeScript types, TanStack Query hooks, API client wrappers, list section component with toggle/delete, history drawer. All patterns established by ChannelSection.tsx and KeySection.tsx.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **see all my workspace's automations at a glance, toggle them on/off, delete ones I no longer need, and inspect their execution history**, so that **I can audit and manage what the bot does automatically**.

### 1.2 Detailed Requirements

#### R1 — `frontend/src/types/automation.ts` (new file)

Types: `ScheduleOccurrence`, `ScheduleType`, `ExecutionStatus`, `AutomationSchedule`, `Automation`, `DeliveryResult`, `AutomationExecution`, `AutomationCreate`, `AutomationUpdate`, `TestRunResult`. Plus `getScheduleSummary(schedule, timezone) -> string` pure function.

#### R2 — `frontend/src/lib/api.ts` additions

Add 6 functions: `listAutomations`, `createAutomation`, `updateAutomation`, `deleteAutomation`, `getAutomationHistory`, `testRunAutomation`.

#### R3 — `frontend/src/hooks/useAutomations.ts` (new file)

TanStack Query hooks: `useAutomationsQuery`, `useCreateAutomationMutation`, `useUpdateAutomationMutation`, `useDeleteAutomationMutation`, `useAutomationHistoryQuery`, `useTestRunMutation`. Mutations invalidate `automationsKey(workspaceId)` on success.

#### R4 — `frontend/src/components/workspace/AutomationsSection.tsx` (new component)

Props: `workspaceId`, `channelBindings`, `onAddClick`, `onDryRunClick`.

Per-automation card shows: name + schedule summary, status badge (Active/Paused), next run label, channel pills, action buttons (History, Dry Run, Toggle, Delete). Delete uses two-click confirmation pattern matching ChannelSection exactly.

#### R5 — `frontend/src/components/workspace/AutomationHistoryDrawer.tsx` (new component)

Props: `workspaceId`, `automationId | null`, `automationName`, `onClose`, `channelBindings`.

Slide-in panel within the card. History list newest-first. Each row: status badge, `started_at`, duration, tokens, `was_dry_run` chip. Expand toggle reveals `generated_content` and per-channel delivery results.

#### R6 — `frontend/src/components/workspace/WorkspaceCard.tsx` modification

Import and mount `AutomationsSection` below existing sections. Add state: `addAutomationOpen`, `dryRunPrompt`, `dryRunName`, `dryRunOpen`.

### 1.3 Out of Scope
- "Run Now" button.
- Inline automation editing.
- Pagination of history beyond 50 rows.

### TDD Red Phase: Lightweight — render tests only (no Gherkin).

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Automations Section UI

  Scenario: Empty state renders correctly
    Given workspace W has no automations
    When AutomationsSection renders
    Then the user sees "No automations yet" text
    And the "Add" button is visible

  Scenario: Automation card renders key info
    Given automation A: name="Daily Standup", daily 09:00 UTC, Active, channels=[C1]
    When AutomationsSection renders with A
    Then the card shows "Daily Standup"
    And shows "Every day at 09:00 UTC"
    And shows an Active badge (emerald)
    And shows the channel name for C1
    And shows "History", "Dry Run", "Toggle", "Delete" buttons

  Scenario: Toggle automation off
    Given automation A is Active
    When user clicks "Toggle" on A's card
    Then useUpdateAutomationMutation is called with { is_active: false }
    And the card shows Paused badge after mutation settles

  Scenario: Delete with confirmation
    Given automation A exists
    When user clicks "Delete"
    Then the button changes to "Confirm?"
    When user clicks "Confirm?"
    Then useDeleteAutomationMutation is called
    And the card is removed from the list

  Scenario: History drawer opens on click
    Given automation A exists
    When user clicks "History"
    Then AutomationHistoryDrawer renders with automationId=A.id

  Scenario: History drawer shows executions
    Given 3 execution rows for automation A (success, partial, failed)
    When AutomationHistoryDrawer renders
    Then 3 rows are shown newest-first
    And each row shows status badge, started_at, duration, tokens

  Scenario: Expanding history row shows generated content
    Given execution E has generated_content="Hello world"
    When user clicks the expand chevron on E
    Then the generated content "Hello world" is visible
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 7 | One per Gherkin scenario, vitest + @testing-library/react |

### 4.2 Definition of Done (The Gate)
- [ ] All 7 Gherkin scenarios have component tests.
- [ ] Types file exported and imported cleanly.
- [ ] No ADR violations.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
