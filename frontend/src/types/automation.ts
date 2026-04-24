/**
 * automation.ts — TypeScript types for the Tee-Mo automations feature (STORY-018-05).
 *
 * Mirrors the backend Pydantic models from:
 *   backend/app/api/routes/automations.py — AutomationCreate, AutomationUpdate,
 *   AutomationResponse, AutomationExecutionResponse, AutomationTestRunResponse.
 *
 * `getScheduleSummary()` is a pure function that mirrors the backend
 * `_schedule_summary()` at backend/app/agents/agent.py:177 exactly —
 * same 5 occurrence shapes, same tz labels. Kept in sync so dashboard
 * schedule text matches what Slack replies show.
 */

// ---------------------------------------------------------------------------
// Enums / Literal types
// ---------------------------------------------------------------------------

/**
 * Schedule occurrence type — how often the automation fires.
 * Mirrors the backend `occurrence` key in the schedule dict.
 */
export type ScheduleOccurrence = 'daily' | 'weekdays' | 'weekly' | 'monthly' | 'once';

/**
 * Top-level schedule type that groups occurrences.
 * - `recurring` — daily, weekdays, weekly, monthly
 * - `once` — one-shot at a specific ISO 8601 datetime
 */
export type ScheduleType = 'recurring' | 'once';

/**
 * Execution status values returned by the backend.
 * Matches teemo_automation_executions.status column.
 */
export type ExecutionStatus = 'success' | 'partial' | 'failed' | 'running';

// ---------------------------------------------------------------------------
// Schedule shape
// ---------------------------------------------------------------------------

/**
 * Automation schedule configuration dict.
 * One of five shapes depending on `occurrence`:
 *
 *   - daily:    `{ occurrence: "daily",    when: "HH:MM" }`
 *   - weekdays: `{ occurrence: "weekdays", when: "HH:MM" }`
 *   - weekly:   `{ occurrence: "weekly",   when: "HH:MM", days: number[] }` (0=Sun…6=Sat)
 *   - monthly:  `{ occurrence: "monthly",  when: "HH:MM", day_of_month: number }`
 *   - once:     `{ occurrence: "once",     at: string }` (ISO 8601 future datetime)
 */
export interface AutomationSchedule {
  occurrence: ScheduleOccurrence;
  /** Time of day in HH:MM format — present for all recurring occurrences. */
  when?: string;
  /** Days of week (0=Sun…6=Sat) — only for occurrence="weekly". */
  days?: number[];
  /** Day of month (1–31) — only for occurrence="monthly". */
  day_of_month?: number;
  /** ISO 8601 future datetime string — only for occurrence="once". */
  at?: string;
}

// ---------------------------------------------------------------------------
// Core automation record
// ---------------------------------------------------------------------------

/**
 * A single workspace automation record.
 * Mirrors backend AutomationResponse (automations.py) and the
 * teemo_automations table schema (migration 012).
 */
export interface Automation {
  /** UUID primary key. */
  id: string;
  /** UUID of the workspace this automation belongs to. */
  workspace_id: string;
  /** UUID of the user who created the automation. */
  owner_user_id: string;
  /** Human-readable name — unique within the workspace. */
  name: string;
  /** Optional free-text description. */
  description?: string | null;
  /** The AI prompt that runs on schedule. */
  prompt: string;
  /** Slack channel IDs to deliver results to. */
  slack_channel_ids: string[];
  /** Schedule configuration object. */
  schedule: AutomationSchedule;
  /** Top-level schedule type — "recurring" or "once". */
  schedule_type: ScheduleType;
  /** IANA timezone string (e.g. "UTC", "Europe/Tbilisi"). */
  timezone: string;
  /** Whether the automation is currently enabled. */
  is_active: boolean;
  /** ISO 8601 timestamp of the last successful run, or null. */
  last_run_at?: string | null;
  /** ISO 8601 timestamp of the next scheduled run, or null. */
  next_run_at?: string | null;
  /** ISO 8601 creation timestamp. */
  created_at: string;
  /** ISO 8601 last-updated timestamp. */
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Execution record
// ---------------------------------------------------------------------------

/**
 * Per-channel delivery result included in an execution record.
 * Shape mirrors the backend's delivery_results JSON column.
 */
export interface DeliveryResult {
  /** Slack channel ID the message was sent to. */
  channel_id: string;
  /** Whether delivery to this channel succeeded. */
  ok: boolean;
  /** Error message if delivery failed. */
  error?: string | null;
}

/**
 * A single automation execution record.
 * Mirrors backend AutomationExecutionResponse (automations.py) and
 * the teemo_automation_executions table schema (migration 012).
 */
export interface AutomationExecution {
  /** UUID primary key. */
  id: string;
  /** UUID of the parent automation. */
  automation_id: string;
  /** Execution status — success, partial, failed, or running. */
  status: ExecutionStatus;
  /** True if this was a dry-run preview (never delivered to Slack). */
  was_dry_run: boolean;
  /** ISO 8601 timestamp when execution started, or null. */
  started_at?: string | null;
  /** ISO 8601 timestamp when execution completed, or null. */
  completed_at?: string | null;
  /** The text output generated by the AI agent, or null on failure. */
  generated_content?: string | null;
  /** Per-channel delivery results array, or null if not delivered. */
  delivery_results?: DeliveryResult[] | null;
  /** Error message if execution failed, or null. */
  error?: string | null;
  /** Number of LLM tokens consumed, or null. */
  tokens_used?: number | null;
  /** Wall-clock execution time in milliseconds, or null. */
  execution_time_ms?: number | null;
}

// ---------------------------------------------------------------------------
// Request bodies
// ---------------------------------------------------------------------------

/**
 * Request body for creating a new automation.
 * Sent to POST /api/workspaces/{id}/automations.
 */
export interface AutomationCreate {
  /** Human-readable name — must be unique within the workspace. */
  name: string;
  /** AI prompt to run on schedule. */
  prompt: string;
  /** Schedule configuration. */
  schedule: AutomationSchedule;
  /** Slack channel IDs to deliver results to (at least 1). */
  slack_channel_ids: string[];
  /** Top-level schedule type. Defaults to "recurring". */
  schedule_type?: ScheduleType;
  /** IANA timezone. Defaults to "UTC". */
  timezone?: string;
  /** Optional human-readable description. */
  description?: string | null;
}

/**
 * Request body for partially updating an automation.
 * Sent to PATCH /api/workspaces/{id}/automations/{automation_id}.
 * All fields are optional — only present keys are updated.
 */
export interface AutomationUpdate {
  name?: string;
  prompt?: string;
  schedule?: AutomationSchedule;
  slack_channel_ids?: string[];
  schedule_type?: ScheduleType;
  timezone?: string;
  description?: string | null;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// Test-run response
// ---------------------------------------------------------------------------

/**
 * Response from POST /api/workspaces/{id}/automations/test-run.
 * Always HTTP 200 — success=false indicates a handled failure.
 */
export interface TestRunResult {
  /** True if the agent produced output; false on any failure. */
  success: boolean;
  /** The agent's text output, or null on failure. */
  output?: string | null;
  /** Error description when success=false. */
  error?: string | null;
  /** Token count, or null on failure. */
  tokens_used?: number | null;
  /** Wall-clock time in ms, even on failure. */
  execution_time_ms?: number | null;
}

// ---------------------------------------------------------------------------
// Pure helper — mirrors backend _schedule_summary() exactly
// ---------------------------------------------------------------------------

/**
 * Produces a human-readable schedule summary string.
 *
 * Exact mirror of backend `_schedule_summary()` at
 * `backend/app/agents/agent.py:177`. Same 5 occurrence shapes,
 * same tz labels — dashboard text matches Slack replies.
 *
 * @param schedule  - Automation schedule configuration object.
 * @param timezone  - IANA timezone string (e.g. "UTC", "Europe/Tbilisi").
 * @returns Short human-readable summary, e.g. "every day at 09:00 UTC".
 *
 * @example
 * ```ts
 * getScheduleSummary({ occurrence: "daily", when: "09:00" }, "UTC")
 * // → "every day at 09:00 UTC"
 *
 * getScheduleSummary({ occurrence: "weekly", when: "10:00", days: [1, 3] }, "UTC")
 * // → "every Mon, Wed at 10:00 UTC"
 * ```
 */
export function getScheduleSummary(schedule: AutomationSchedule, timezone: string): string {
  const occ = schedule.occurrence ?? '';
  const when = schedule.when ?? '';
  // Backend: tz_label = timezone if timezone != "UTC" else "UTC" — always shows "UTC"
  const tzLabel = timezone !== 'UTC' ? timezone : 'UTC';

  if (occ === 'daily') {
    return `every day at ${when} ${tzLabel}`;
  } else if (occ === 'weekdays') {
    return `every weekday at ${when} ${tzLabel}`;
  } else if (occ === 'weekly') {
    const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const days = (schedule.days ?? []).map((d) => dayNames[d]).join(', ');
    return `every ${days} at ${when} ${tzLabel}`;
  } else if (occ === 'monthly') {
    return `monthly on day ${schedule.day_of_month} at ${when} ${tzLabel}`;
  } else if (occ === 'once') {
    return `once at ${schedule.at} ${tzLabel}`;
  }
  return occ;
}
