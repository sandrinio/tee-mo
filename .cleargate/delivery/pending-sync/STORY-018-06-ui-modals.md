---
story_id: "STORY-018-06-ui-modals"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-018_scheduled_automations/STORY-018-06-ui-modals.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-018-06: Dashboard UI — Add Modal + Schedule Builder + Dry Run

**Complexity: L2** — Two modals: `AddAutomationModal` (form with schedule builder + channel picker) and `DryRunModal` (loading → markdown output). Depends on STORY-018-05.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **create a new automation through a guided form with a schedule builder and channel picker, and preview the prompt output before saving**, so that **I can confidently set up automations without trial-and-error in Slack**.

### 1.2 Detailed Requirements

#### R1 — `frontend/src/components/workspace/AddAutomationModal.tsx` (new component)

Props: `workspaceId`, `open`, `onClose`, `channelBindings`.

Form fields: Name (required), Description (optional), Prompt (required), Schedule (builder, required), Timezone (select, defaults to browser tz), Channels (checkbox list, ≥1 required).

**"Preview" button** below Prompt field: triggers `useTestRunMutation` inline. While loading: shows "Previewing…" + spinner. On result: shows `DryRunResultInline` beneath textarea. On error: shows error inline.

**Submit**: "Save Automation". Calls `useCreateAutomationMutation`. On success, closes modal and invalidates query. On error, shows server error inline.

Form state managed with `useState`. Reset all fields to defaults on close.

#### R2 — Schedule Builder (embedded in AddAutomationModal)

Occurrence selector: segmented control `Daily | Weekdays | Weekly | Monthly | Once`.

Conditional fields:
- `daily`/`weekdays`: Time (HH:MM)
- `weekly`: Time (HH:MM) + Day checkboxes (Mon–Sun)
- `monthly`: Time (HH:MM) + Day of month (1–31)
- `once`: datetime-local input

Validation: `daily`/`weekdays` require `when`; `weekly` requires `when` + `days.length >= 1`; `monthly` requires `when` + `day_of_month`; `once` requires `at` in the future.

`schedule_type` in payload: `'once'` if occurrence is `'once'`, else `'recurring'`.

#### R3 — Channel Picker (embedded in AddAutomationModal)

If `channelBindings` is empty: show "No channels bound" warning, disable Submit.

If non-empty: checkbox list of bound channels. At least one must be checked.

#### R4 — `DryRunResultInline` (sub-component within AddAutomationModal)

States: loading (spinner + "Running preview…"), success (light blue card with output + token count), error (red card; special case `'no_key_configured'`), timeout (amber card).

#### R5 — `frontend/src/components/workspace/DryRunModal.tsx` (new component)

Props: `workspaceId`, `automationName`, `prompt`, `open`, `onClose`.

When `open` becomes `true`, immediately fires `useTestRunMutation.mutate(...)`. Shows loading → output or error. Banner: "This preview runs your prompt now. No message will be posted to Slack." Footer: "Close" button.

#### R6 — WorkspaceCard wiring (completing STORY-018-05 stubs)

Add `<AddAutomationModal>` and `<DryRunModal>` renders guarded by their open state booleans.

### 1.3 Out of Scope
- Automation editing via modal.
- "Run now" button.
- Cron expression input.
- Timezone search/filter — simple `<select>` with ~20 curated IANA timezones.

### TDD Red Phase: Lightweight — form validation + schedule builder unit tests.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Add Automation Modal

  Scenario: Form blocks submit when name is empty
    Given AddAutomationModal is open
    When user clicks "Save Automation" without filling Name
    Then validation error "Name is required" appears
    And useCreateAutomationMutation is NOT called

  Scenario: Form blocks submit when no channel selected
    Given form has name + prompt + schedule filled
    And no channel is checked
    When user clicks "Save Automation"
    Then validation error "Select at least one channel" appears

  Scenario: Form blocks submit for 'once' schedule in the past
    Given occurrence=once with 'at' set to yesterday
    When user clicks "Save Automation"
    Then validation error "'At' time must be in the future" appears

  Scenario: Successful create closes modal
    Given all form fields are valid
    When user clicks "Save Automation"
    And useCreateAutomationMutation resolves successfully
    Then the modal closes
    And the automations list refreshes (query invalidated)

  Scenario: Weekly schedule requires at least one day
    Given occurrence=weekly with 'when' set but no days checked
    When user clicks "Save Automation"
    Then validation error "Select at least one day" appears

  Scenario: Preview button fires test-run
    Given prompt field contains "Summarise this week's updates"
    When user clicks "Preview"
    Then useTestRunMutation is called with that prompt
    And while pending the button shows "Previewing…"
    And on success the output renders inline below the textarea

  Scenario: Dry Run Modal auto-fires on open
    Given DryRunModal opens with prompt="Weekly report"
    Then useTestRunMutation is called immediately with that prompt
    And spinner is shown while pending
    And on success the output renders in the modal

  Scenario: No channels bound — form warns and blocks submit
    Given channelBindings=[]
    When AddAutomationModal renders
    Then "No channels bound" message is shown
    And Submit is disabled
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 8 | One per Gherkin scenario, vitest + @testing-library/react |

### 4.2 Definition of Done (The Gate)
- [ ] All 8 Gherkin scenarios have component tests.
- [ ] Form resets on close.
- [ ] No ADR violations.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
