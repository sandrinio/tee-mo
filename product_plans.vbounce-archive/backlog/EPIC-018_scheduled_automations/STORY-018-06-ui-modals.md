---
story_id: "STORY-018-06-ui-modals"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §3.3, §7; frontend/src/components/workspace/AutomationsSection.tsx (STORY-018-05); frontend/src/components/workspace/ChannelSection.tsx (modal pattern); new_app frontend/src/components/settings/AutomationsTab.tsx (schedule builder reference); STORY-018-02 REST endpoint shapes; MDN Intl.DateTimeFormat API"
actor: "Workspace Admin (Dashboard)"
complexity_label: "L2"
depends_on: ["STORY-018-05"]
---

# STORY-018-06: Dashboard UI — Add Modal + Schedule Builder + Dry Run

**Complexity: L2** — Two modals: `AddAutomationModal` (form with schedule builder + channel picker) and `DryRunModal` (loading → markdown output). `AddAutomationModal` is the most complex UI piece in this EPIC; the schedule builder has conditional fields per occurrence type.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **create a new automation through a guided form with a schedule builder and channel picker, and preview the prompt output before saving**, so that **I can confidently set up automations without trial-and-error in Slack**.

### 1.2 Detailed Requirements

#### R1 — `frontend/src/components/workspace/AddAutomationModal.tsx` (new component)

Props:
```typescript
interface AddAutomationModalProps {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
  /** Already-bound channel list for the channel picker. */
  channelBindings: Array<{ slack_channel_id: string; channel_name: string }>;
}
```

**Modal structure** (overlay + centred card, consistent with any existing modals in codebase):
- Title: "New Automation"
- Close button (X) top-right.
- Form fields in order:

| Field | Type | Validation |
|-------|------|-----------|
| **Name** | text input | Required, ≤100 chars |
| **Description** | textarea (2 rows) | Optional |
| **Prompt** | textarea (5 rows) | Required |
| **Schedule** | builder — see R2 | Required (valid occurrence) |
| **Timezone** | select | Required, defaults to `Intl.DateTimeFormat().resolvedOptions().timeZone` or `'UTC'` |
| **Channels** | checkbox list | Required, ≥1 selected |

- **"Preview" button** (secondary, below Prompt field): triggers `useTestRunMutation` inline. While loading: button text becomes "Previewing…" with spinner; Prompt textarea becomes read-only. On result: shows `DryRunResultInline` beneath the textarea (not a separate modal — just an expandable block within the form). On error: shows error in red below. This keeps the user in context while previewing.
- **Submit button**: "Save Automation". Disabled when form invalid or submit pending.
- **Cancel button**: closes modal, resets form.

On submit:
1. Validate all fields (client-side first).
2. Call `useCreateAutomationMutation.mutate(payload)`.
3. On success: close modal, invalidate automations query (hook handles this).
4. On error: show server error inline below form (e.g. "Automation with name 'X' already exists.").

**Form state**: use `useState` (not a form library) — the form is simple enough. One `errors` object keyed by field name.

---

#### R2 — Schedule Builder (embedded in AddAutomationModal)

The schedule builder is a sub-section of the form with a **schedule type tab selector** followed by **conditional fields**.

**Occurrence selector**: segmented control (button group) with 5 options:
`Daily | Weekdays | Weekly | Monthly | Once`

**Conditional fields per occurrence**:

| Occurrence | Shown fields |
|------------|-------------|
| `daily` | Time (HH:MM) |
| `weekdays` | Time (HH:MM) |
| `weekly` | Time (HH:MM) + Day picker (checkboxes: Mon Tue Wed Thu Fri Sat Sun) |
| `monthly` | Time (HH:MM) + Day of month (number input, 1–31) |
| `once` | Datetime-local input (browser native) |

**Time input**: `<input type="time" step="60" />` — renders as HH:MM in all modern browsers. Store as string `"HH:MM"`.

**Day picker for weekly** (circular order Mon–Sun, consistent with new_app):
```
[ ] Mon  [ ] Tue  [ ] Wed  [ ] Thu  [ ] Fri  [ ] Sat  [ ] Sun
```
Toggle checkboxes → push/pop from `days` array (0=Sun, 1=Mon, …, 6=Sat).

**Validation**:
- `daily`/`weekdays`: require `when` (non-empty).
- `weekly`: require `when` + `days.length >= 1`.
- `monthly`: require `when` + `day_of_month` ∈ [1, 31].
- `once`: require `at` (non-empty) + `at` must be a future datetime (compare to `new Date()`).

**Schedule output** maps to `AutomationSchedule`:
```typescript
// daily example:
{ occurrence: 'daily', when: '09:00' }

// weekly example:
{ occurrence: 'weekly', when: '09:00', days: [1, 3, 5] }  // Mon, Wed, Fri

// once example:
{ occurrence: 'once', at: '2026-04-20T17:00:00' }
```

The `schedule_type` field in the API payload is derived: `'once'` if occurrence is `'once'`, else `'recurring'`.

---

#### R3 — Channel Picker (embedded in AddAutomationModal)

If `channelBindings` is empty:
- Show: "No channels bound to this workspace yet. Add channels in the Channels section above." (grey muted text, no checkboxes).
- Submit button disabled.

If non-empty:
```
□ #general      □ #updates      □ #standup
```
Checkbox list — one per bound channel. At least one must be checked to enable Submit.

Selected `slack_channel_id`s flow into `payload.slack_channel_ids`.

---

#### R4 — `DryRunResultInline` (sub-component within AddAutomationModal)

Renders the result of `useTestRunMutation` inline below the Prompt textarea.

States:
- `loading`: spinner + "Running preview…" muted text.
- `success`: light blue card with:
  - Caption: "Preview output (not posted to Slack)"
  - `<pre className="whitespace-pre-wrap text-sm font-mono max-h-48 overflow-y-auto">` with `output`.
  - Token count: `${tokens_used} tokens · ${execution_time_ms}ms` in muted text.
- `error`: red card with error message. Special case: `error === 'no_key_configured'` → "No BYOK key configured for this workspace. Add one in the BYOK Key section above."
- `timeout`: amber card "The preview timed out after 30s. The prompt may be too complex."

---

#### R5 — `frontend/src/components/workspace/DryRunModal.tsx` (new component)

This is the **standalone dry-run modal** triggered from existing automation cards (History → Dry Run path from AutomationsSection). Different from the inline preview above — this one is modal because the automation already exists; user wants to re-run its current prompt.

Props:
```typescript
interface DryRunModalProps {
  workspaceId: string;
  automationName: string;
  prompt: string;   // pre-filled with the automation's prompt
  open: boolean;
  onClose: () => void;
}
```

**Behaviour**:
1. When `open` becomes `true`, immediately fire `useTestRunMutation.mutate({ workspaceId, prompt })`.
2. Show loading state (spinner + "Running '${automationName}' preview…") while pending.
3. On result: show output or error using the same card styles as `DryRunResultInline`.
4. Footer: "Close" button.
5. Note banner at top: "This preview runs your prompt now. No message will be posted to Slack."

---

#### R6 — WorkspaceCard wiring (completing STORY-018-05 stubs)

STORY-018-05 added the state variables and callbacks. This story adds the actual modal renders:

```tsx
{addAutomationOpen && (
  <AddAutomationModal
    workspaceId={workspace.id}
    open={addAutomationOpen}
    onClose={() => setAddAutomationOpen(false)}
    channelBindings={channelBindings}
  />
)}
{dryRunOpen && (
  <DryRunModal
    workspaceId={workspace.id}
    automationName={dryRunName}
    prompt={dryRunPrompt}
    open={dryRunOpen}
    onClose={() => { setDryRunOpen(false); setDryRunPrompt(''); setDryRunName(''); }}
  />
)}
```

### 1.3 Out of Scope
- Automation editing via modal (update) — update is via agent tools or delete+recreate in v1.
- "Run now" button — deferred per EPIC-018 §8.
- Cron expression input — structured JSONB schedule only.
- Timezone search/filter — simple `<select>` with a curated list of common IANA timezones (see §3.2).

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

### 2.2 Test File
`frontend/src/components/workspace/__tests__/AddAutomationModal.test.tsx`
`frontend/src/components/workspace/__tests__/DryRunModal.test.tsx`

Use vitest + @testing-library/react. Mock `useCreateAutomationMutation` and `useTestRunMutation`.

---

## 3. Implementation Guide

### 3.1 File Map

| File | Action | Notes |
|------|--------|-------|
| `frontend/src/components/workspace/AddAutomationModal.tsx` | **Create** | Form + schedule builder + channel picker + inline preview |
| `frontend/src/components/workspace/DryRunModal.tsx` | **Create** | Standalone dry-run modal for existing automations |
| `frontend/src/components/workspace/WorkspaceCard.tsx` | **Modify** | Add `<AddAutomationModal>` and `<DryRunModal>` renders (completing 018-05 stubs) |

### 3.2 Curated timezone list

Avoid loading the full IANA database. Use a short curated list of ~20 common timezones for the `<select>`:

```typescript
const COMMON_TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles',
  'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Tbilisi', 'Europe/Istanbul',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Singapore', 'Asia/Tokyo', 'Asia/Seoul',
  'Australia/Sydney', 'Pacific/Auckland',
];
```

Default: `Intl.DateTimeFormat().resolvedOptions().timeZone`, falling back to `'UTC'` if not in the list (still allow any value — just don't show it in the picker by default).

### 3.3 Schedule builder state shape

Manage the entire schedule as a single state object plus an `occurrence` field:

```typescript
const [occurrence, setOccurrence] = useState<ScheduleOccurrence>('daily');
const [when, setWhen] = useState('09:00');
const [days, setDays] = useState<number[]>([1]); // Mon default
const [dayOfMonth, setDayOfMonth] = useState(1);
const [at, setAt] = useState('');

// Build the final schedule on submit:
function buildSchedule(): AutomationSchedule {
  switch (occurrence) {
    case 'daily':    return { occurrence, when };
    case 'weekdays': return { occurrence, when };
    case 'weekly':   return { occurrence, when, days };
    case 'monthly':  return { occurrence, when, day_of_month: dayOfMonth };
    case 'once':     return { occurrence, at };
  }
}
```

### 3.4 Form reset on close

When the modal closes (either Cancel or success), reset all fields to defaults:

```typescript
function handleClose() {
  setName(''); setDescription(''); setPrompt('');
  setOccurrence('daily'); setWhen('09:00'); setDays([1]);
  setDayOfMonth(1); setAt('');
  setSelectedChannels([]);
  setErrors({});
  setPreviewResult(null);
  onClose();
}
```

### 3.5 Modal overlay pattern

Check for an existing modal/dialog pattern in the codebase (search for `fixed inset-0` or `<dialog>`). Reuse it. If none exists, implement:

```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={handleClose}>
  <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto p-6"
       onClick={e => e.stopPropagation()}>
    {/* content */}
  </div>
</div>
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-15 | Claude (doc-manager) | Initial draft. Inline preview in AddAutomationModal (not a separate modal); DryRunModal auto-fires on open for existing automation re-preview. Schedule builder matches new_app reference but uses simpler state (no form library). Curated timezone list (no full IANA DB). |
