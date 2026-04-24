---
story_id: "STORY-018-05-ui-list-history"
parent_epic_ref: "EPIC-018"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-018 §2, §3.3, §4.1; frontend/src/components/workspace/ChannelSection.tsx (section pattern); frontend/src/components/workspace/KeySection.tsx (section pattern); frontend/src/hooks/ (TanStack Query pattern); new_app frontend/src/hooks/useAutomations.ts + types/automation.ts (reference); STORY-018-02 REST endpoint shapes"
actor: "Workspace Admin (Dashboard)"
complexity_label: "L2"
---

# STORY-018-05: Dashboard UI — Automations Section + History Drawer

**Complexity: L2** — TypeScript types, TanStack Query hooks, API client wrappers, list section component with toggle/delete, history drawer. All patterns established by ChannelSection.tsx and KeySection.tsx.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin on the dashboard**, I want to **see all my workspace's automations at a glance, toggle them on/off, delete ones I no longer need, and inspect their execution history**, so that **I can audit and manage what the bot does automatically**.

### 1.2 Detailed Requirements

#### R1 — `frontend/src/types/automation.ts` (new file)

```typescript
export type ScheduleOccurrence = 'daily' | 'weekdays' | 'weekly' | 'monthly' | 'once';
export type ScheduleType = 'recurring' | 'once';
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'partial' | 'failed';

export interface AutomationSchedule {
  occurrence: ScheduleOccurrence;
  when?: string;           // "HH:MM"
  days?: number[];         // 0=Sun … 6=Sat  (for 'weekly')
  day_of_month?: number;   // 1–31            (for 'monthly')
  at?: string;             // ISO 8601        (for 'once')
}

export interface Automation {
  id: string;
  workspace_id: string;
  name: string;
  description?: string | null;
  prompt: string;
  slack_channel_ids: string[];
  schedule: AutomationSchedule;
  schedule_type: ScheduleType;
  timezone: string;
  is_active: boolean;
  owner_user_id: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface DeliveryResult {
  channel_id: string;
  ok: boolean;
  error?: string | null;
  ts?: string | null;
}

export interface AutomationExecution {
  id: string;
  automation_id: string;
  status: ExecutionStatus;
  was_dry_run: boolean;
  started_at: string;
  completed_at?: string | null;
  generated_content?: string | null;
  delivery_results?: DeliveryResult[] | null;
  error?: string | null;
  tokens_used?: number | null;
  execution_time_ms?: number | null;
}

export interface AutomationCreate {
  name: string;
  prompt: string;
  schedule: AutomationSchedule;
  slack_channel_ids: string[];
  timezone?: string;
  description?: string;
  schedule_type?: ScheduleType;
}

export interface AutomationUpdate {
  name?: string;
  prompt?: string;
  schedule?: AutomationSchedule;
  slack_channel_ids?: string[];
  timezone?: string;
  description?: string;
  is_active?: boolean;
}

export interface TestRunResult {
  success: boolean;
  output?: string | null;
  error?: string | null;
  tokens_used?: number | null;
  execution_time_ms?: number | null;
}

/** Returns a human-readable schedule summary. Pure function, no side effects. */
export function getScheduleSummary(schedule: AutomationSchedule, timezone: string): string {
  const tz = timezone !== 'UTC' ? ` ${timezone}` : ' UTC';
  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  switch (schedule.occurrence) {
    case 'daily':    return `Every day at ${schedule.when}${tz}`;
    case 'weekdays': return `Every weekday at ${schedule.when}${tz}`;
    case 'weekly': {
      const days = (schedule.days ?? []).map(d => dayNames[d]).join(', ');
      return `Every ${days} at ${schedule.when}${tz}`;
    }
    case 'monthly':  return `Monthly on day ${schedule.day_of_month} at ${schedule.when}${tz}`;
    case 'once':     return `Once at ${schedule.at}${tz}`;
    default:         return schedule.occurrence;
  }
}
```

---

#### R2 — `frontend/src/lib/api.ts` additions

Add these functions to the existing `api.ts` file (following existing patterns):

```typescript
// Automations
export const listAutomations = (workspaceId: string): Promise<Automation[]> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations`);

export const createAutomation = (workspaceId: string, payload: AutomationCreate): Promise<Automation> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations`, { method: 'POST', body: JSON.stringify(payload) });

export const updateAutomation = (workspaceId: string, automationId: string, patch: AutomationUpdate): Promise<Automation> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations/${automationId}`, { method: 'PATCH', body: JSON.stringify(patch) });

export const deleteAutomation = (workspaceId: string, automationId: string): Promise<void> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations/${automationId}`, { method: 'DELETE' });

export const getAutomationHistory = (workspaceId: string, automationId: string): Promise<AutomationExecution[]> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations/${automationId}/history`);

export const testRunAutomation = (workspaceId: string, prompt: string): Promise<TestRunResult> =>
  apiFetch(`/api/workspaces/${workspaceId}/automations/test-run`, { method: 'POST', body: JSON.stringify({ prompt }) });
```

---

#### R3 — `frontend/src/hooks/useAutomations.ts` (new file)

TanStack Query hooks following the pattern of `useChannelBindingsQuery`, `useBindChannelMutation`, etc.:

```typescript
export function useAutomationsQuery(workspaceId: string)         // → Automation[]
export function useCreateAutomationMutation(workspaceId: string) // → UseMutationResult
export function useUpdateAutomationMutation(workspaceId: string) // → UseMutationResult
export function useDeleteAutomationMutation(workspaceId: string) // → UseMutationResult
export function useAutomationHistoryQuery(workspaceId: string, automationId: string | null, enabled: boolean) // → AutomationExecution[]
export function useTestRunMutation(workspaceId: string)          // → UseMutationResult<TestRunResult>
```

Query key factory (consistent with repo pattern):
```typescript
export const automationsKey = (workspaceId: string) => ['automations', workspaceId] as const;
export const automationHistoryKey = (workspaceId: string, automationId: string) =>
  ['automations', workspaceId, automationId, 'history'] as const;
```

Mutations invalidate `automationsKey(workspaceId)` on success.

---

#### R4 — `frontend/src/components/workspace/AutomationsSection.tsx` (new component)

Props:
```typescript
interface AutomationsSectionProps {
  workspaceId: string;
  /** Already-bound channel list for display purposes (channel_id → name map). */
  channelBindings: Array<{ slack_channel_id: string; channel_name: string }>;
  /** Callback to open AddAutomationModal (provided by parent WorkspaceCard). */
  onAddClick: () => void;
  /** Callback to open DryRunModal with a specific prompt. */
  onDryRunClick: (prompt: string, automationName: string) => void;
}
```

**Layout** (matches ChannelSection card style):
- Section header: "Automations" label (same font/weight as "Channels") + "Add" button aligned right.
- Empty state: soft grey text "No automations yet. Click Add to create one."
- Automation card list: one card per automation, styled consistently with channel binding cards.

**Per-automation card contains**:
1. **Name** (bold) + schedule summary (`getScheduleSummary`) in muted text below.
2. **Status badge**: `Active` (emerald) or `Paused` (amber) — same badge style as ChannelSection.
3. **Next run** label: formatted `next_run_at` (e.g. "Next: Apr 16 09:00 UTC") or "—" if inactive/null.
4. **Channel pills**: compact list of channel names (looked up from `channelBindings` prop). Unknown IDs shown as channel_id truncated.
5. **Action buttons** (right-aligned, small, text style):
   - **History** → sets `historyAutomationId` state → opens `AutomationHistoryDrawer`.
   - **Dry Run** → calls `onDryRunClick(automation.prompt, automation.name)`.
   - **Toggle** → calls `useUpdateAutomationMutation` with `{ is_active: !automation.is_active }`. Shows spinner while pending.
   - **Delete** → inline confirm (same pattern as ChannelSection unbind confirm): first click shows "Confirm?" text + confirm button, second click calls `useDeleteAutomationMutation`.

**Delete confirmation pattern** (match ChannelSection exactly):
```typescript
const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null); // automation ID
// First click: setConfirmingDelete(id)
// Second click: deleteAutomation.mutate(...), setConfirmingDelete(null)
// Cancel: setConfirmingDelete(null) on blur/other click
```

**History drawer**: rendered at section bottom, conditionally when `historyAutomationId !== null`.

---

#### R5 — `frontend/src/components/workspace/AutomationHistoryDrawer.tsx` (new component)

Props:
```typescript
interface AutomationHistoryDrawerProps {
  workspaceId: string;
  automationId: string | null;   // null → closed
  automationName: string;
  onClose: () => void;
  channelBindings: Array<{ slack_channel_id: string; channel_name: string }>;
}
```

**Behaviour**:
- When `automationId` is non-null: call `useAutomationHistoryQuery(workspaceId, automationId, true)`.
- Render as a slide-in panel within the card (not a full-screen modal — same pattern as existing drawers in codebase, or a simple conditional div with border-t + max-h + overflow-y-auto).

**History list** (newest first):
Each row shows:
- Status badge: `success` (emerald), `partial` (amber), `failed` (red), `running` (blue), `pending` (grey).
- `started_at` formatted as date + time.
- Duration: `${execution_time_ms}ms` or "—".
- Tokens: `${tokens_used} tok` or "—".
- `was_dry_run` → show "dry run" chip in slate.
- Expand toggle (chevron icon) → reveals:
  - `generated_content` rendered as `<pre>` or markdown (use existing markdown renderer if in codebase, else `<pre className="whitespace-pre-wrap text-xs">`).
  - Per-channel delivery results table: channel name, ok/fail badge, error string if any.
  - Top-level `error` field if present.

**Loading state**: spinner + "Loading history…" text.
**Empty state**: "No executions yet."

---

#### R6 — `frontend/src/components/workspace/WorkspaceCard.tsx` modification

Import and mount `AutomationsSection` below the existing sections (Channels, BYOK Key, MCP):

```tsx
<AutomationsSection
  workspaceId={workspace.id}
  channelBindings={channelBindings}
  onAddClick={() => setAddAutomationOpen(true)}
  onDryRunClick={(prompt, name) => { setDryRunPrompt(prompt); setDryRunName(name); setDryRunOpen(true); }}
/>
```

State additions (to be used by 018-06 modals):
```typescript
const [addAutomationOpen, setAddAutomationOpen] = useState(false);
const [dryRunPrompt, setDryRunPrompt] = useState('');
const [dryRunName, setDryRunName] = useState('');
const [dryRunOpen, setDryRunOpen] = useState(false);
```

The modals themselves (`AddAutomationModal`, `DryRunModal`) are rendered by WorkspaceCard but implemented in STORY-018-06.

### 1.3 Out of Scope
- "Run Now" button — deferred per EPIC-018 §8.
- Inline automation editing (name, prompt, schedule) — create only in v1; update via Slack agent tools or delete+recreate.
- Pagination of history beyond 50 rows.
- Per-channel content customisation display.

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

### 2.2 Test File
`frontend/src/components/workspace/__tests__/AutomationsSection.test.tsx`
`frontend/src/components/workspace/__tests__/AutomationHistoryDrawer.test.tsx`

Use vitest + @testing-library/react. Mock `useAutomationsQuery` and `useAutomationHistoryQuery`.

---

## 3. Implementation Guide

### 3.1 File Map

| File | Action | Notes |
|------|--------|-------|
| `frontend/src/types/automation.ts` | **Create** | Types + `getScheduleSummary` |
| `frontend/src/lib/api.ts` | **Modify** | Add 6 automation API functions |
| `frontend/src/hooks/useAutomations.ts` | **Create** | TanStack Query hooks |
| `frontend/src/components/workspace/AutomationsSection.tsx` | **Create** | List + toggle + delete + history trigger |
| `frontend/src/components/workspace/AutomationHistoryDrawer.tsx` | **Create** | Execution history panel |
| `frontend/src/components/workspace/WorkspaceCard.tsx` | **Modify** | Mount AutomationsSection + state for 018-06 modals |

### 3.2 Status badge colour map

```typescript
const STATUS_BADGE: Record<ExecutionStatus, string> = {
  success: 'bg-emerald-100 text-emerald-700',
  partial:  'bg-amber-100  text-amber-700',
  failed:   'bg-red-100    text-red-700',
  running:  'bg-blue-100   text-blue-700',
  pending:  'bg-slate-100  text-slate-600',
};
```

### 3.3 Next-run display

```typescript
function formatNextRun(next_run_at: string | null | undefined): string {
  if (!next_run_at) return '—';
  const d = new Date(next_run_at);
  return `Next: ${d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}`;
}
```

### 3.4 Channel name resolution

`channelBindings` is an array from the parent. Build a lookup map at render time:

```typescript
const channelMap = useMemo(
  () => Object.fromEntries(channelBindings.map(b => [b.slack_channel_id, b.channel_name])),
  [channelBindings]
);
// Usage: channelMap[slack_channel_id] ?? slack_channel_id
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-04-15 | Claude (doc-manager) | Initial draft. TypeScript types ported from new_app (stripped: no delivery_method, single-adapter, slack_channel_ids array, was_dry_run flag, partial status). Section component matches ChannelSection/KeySection patterns. History drawer is inline panel, not full-screen modal. |
