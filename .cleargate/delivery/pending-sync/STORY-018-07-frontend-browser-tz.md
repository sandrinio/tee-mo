---
story_id: "STORY-018-07-frontend-browser-tz"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢"
context_source: "EPIC-018-scheduled-automations.md"
actor: "Workspace User (dashboard)"
complexity_label: "L1"
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-post-sprint-13"
updated_at_version: "cleargate-post-sprint-13"
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

# STORY-018-07: Dashboard automation modal — honor browser timezone
**Complexity:** L1 — single component, ~15 lines, known pattern.

## 1. The Spec (The Contract)

### 1.1 User Story
As a **dashboard user creating an automation**, I want the modal's timezone field to default to **my browser's detected IANA zone** (not silently fall back to UTC when my zone isn't in a curated list), so that my "9am daily" automation fires at 09:00 local — not 09:00 UTC.

### 1.2 Detailed Requirements
- **R1.** On modal open (create path), the Timezone field defaults to `Intl.DateTimeFormat().resolvedOptions().timeZone`. If detection throws or returns empty, fall back to `'UTC'`.
- **R2.** If the detected zone is not in the existing `TIMEZONES` curated list, it is still selected as the default **and** merged into the dropdown options so the user can see and re-select it.
- **R3.** `resetForm()` resets the tz field to the detected zone (not hard-coded `'UTC'`).
- **R4.** Edit path (if/when added): preserves the saved `automation.timezone` as-is — detection only applies to create.
- **R5.** No regression to the submit payload shape — backend still receives an IANA string via `timezone` field of `createAutomation`.

### 1.3 Out of Scope
- Replacing the curated dropdown with a full IANA searchable selector (e.g. `react-timezone-select`). Tracked separately if needed.
- Slack-chat agent tz awareness — see STORY-018-08.
- Workspace-level default tz setting.

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: Browser-detected default timezone in AddAutomationModal

  Scenario: Browser zone is in the curated list
    Given my browser timezone is "Europe/Berlin"
    And "Europe/Berlin" appears in the curated TIMEZONES list
    When I open the Add Automation modal
    Then the Timezone field is preselected to "Europe/Berlin"
    And "Europe/Berlin" is not duplicated in the dropdown

  Scenario: Browser zone is NOT in the curated list
    Given my browser timezone is "America/Phoenix"
    And "America/Phoenix" is not in the curated TIMEZONES list
    When I open the Add Automation modal
    Then the Timezone field is preselected to "America/Phoenix"
    And "America/Phoenix" is present as a selectable option in the dropdown

  Scenario: Detection fails (jsdom / older runtime)
    Given Intl.DateTimeFormat().resolvedOptions().timeZone throws or returns ""
    When I open the Add Automation modal
    Then the Timezone field is preselected to "UTC"
    And no exception bubbles into the render

  Scenario: Form reset after successful submit
    Given my browser timezone is "Asia/Tokyo"
    And I have just submitted an automation successfully
    When the modal re-opens
    Then the Timezone field is again preselected to "Asia/Tokyo" (not "UTC")
```

### 2.2 Verification Steps (Manual)
- [ ] Open the Add Automation modal in a local browser — Timezone defaults to your actual zone.
- [ ] Temporarily override `Intl.DateTimeFormat().resolvedOptions` in devtools to return a non-curated zone (e.g. `"America/Phoenix"`) — option appears, is selected.
- [ ] Submit and reopen — zone is still detected, not reset to UTC.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary File | `frontend/src/components/workspace/AddAutomationModal.tsx` |
| Related Files | `frontend/src/components/workspace/__tests__/AutomationsSection.test.tsx` (add or extend modal test), `frontend/src/types/automation.ts` (no shape change expected) |
| New Files Needed | No |

### 3.2 Technical Logic
- Extract a module-level `DETECTED_TZ` constant computed via a `try/catch` around `Intl.DateTimeFormat().resolvedOptions().timeZone`. Mirror new_app's pattern at `new_app/frontend/src/components/settings/AutomationsTab.tsx:94`.
- Build the dropdown `options` array from `TIMEZONES` with `DETECTED_TZ` merged in when absent (and kept first or in original order — pick one, document).
- `useState` initializer returns `DETECTED_TZ` directly — drop the `Object.fromEntries(...)` gate at line 391-397.
- `resetForm()` (line 422) sets `setTimezone(DETECTED_TZ)`.

### 3.3 API Contract
No backend contract change. `createAutomation` payload keeps `timezone: string` (IANA).

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Unit / component tests | 2 | (a) default value reflects mocked `Intl.DateTimeFormat`, (b) non-curated zone is added to options |
| E2E / acceptance tests | 0 | Covered by manual verification in §2.2 |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] All Gherkin scenarios from §2.1 covered.
- [ ] Lint + typecheck pass.
- [ ] Peer / Architect review passed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low Ambiguity** — single file, contract unchanged, requirements concrete.
