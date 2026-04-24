/**
 * AddAutomationModal.tsx — Guided form for creating a new workspace automation (STORY-018-06).
 *
 * Renders a div-based overlay modal (NOT native `<dialog>`) so it works in jsdom test
 * environments. jsdom does not implement HTMLDialogElement.showModal(), and a `<dialog>`
 * that silently no-ops under Vitest would produce false-green tests for a modal that
 * never visually rendered. (FLASHCARD 2026-04-12 #vitest #frontend)
 *
 * Form sections:
 *   1. Name (required)
 *   2. Description (optional)
 *   3. Prompt (required) + inline Preview button
 *   4. Schedule builder — occurrence picker + conditional time/day fields
 *   5. Timezone selector
 *   6. Channel picker (checkbox list from `channelBindings` prop)
 *
 * Schedule payload shapes — MUST match backend `_AUTOMATIONS_PROMPT_SECTION`
 * at backend/app/agents/agent.py:124-143:
 *   - daily:    { occurrence:"daily",    when:"HH:MM" }
 *   - weekdays: { occurrence:"weekdays", when:"HH:MM" }
 *   - weekly:   { occurrence:"weekly",   when:"HH:MM", days:[0..6] }  (0=Sun…6=Sat)
 *   - monthly:  { occurrence:"monthly",  when:"HH:MM", day_of_month:1..31 }
 *   - once:     { occurrence:"once",     at:"ISO8601-future" }
 *
 * Top-level schedule_type = "once" if occurrence is "once", else "recurring".
 *
 * Preview: fires `useTestRunMutation.mutate(prompt)` inline and renders
 * `DryRunResultInline` below the prompt textarea. No post to Slack.
 *
 * All data fetching goes through TanStack hooks — no raw fetch() calls
 * (FLASHCARD 2026-04-11 #frontend #recipe). `channelBindings` is passed in
 * as a prop (already fetched by parent via useChannelBindingsQuery).
 *
 * Form state is fully reset to defaults on close (DoD §4.2).
 */
import { useState } from 'react';
import {
  useCreateAutomationMutation,
  useTestRunMutation,
} from '../../hooks/useAutomations';
import type { ChannelBinding } from '../../lib/api';
import type { AutomationSchedule, ScheduleOccurrence, TestRunResult } from '../../types/automation';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Curated list of ~20 common IANA timezone values for the selector (out-of-scope: no search). */
const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Anchorage',
  'America/Honolulu',
  'America/Sao_Paulo',
  'America/Toronto',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Kiev',
  'Europe/Moscow',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Pacific/Auckland',
];

/**
 * Browser-detected IANA timezone, computed once at module load.
 * Falls back to 'UTC' if Intl is unavailable or returns an empty string
 * (e.g. older runtimes, jsdom without locale data).
 * (STORY-018-07 R1)
 */
const DETECTED_TZ = (() => {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return tz || 'UTC';
  } catch {
    return 'UTC';
  }
})();

/**
 * Dropdown options for the Timezone selector.
 * Detected zone is prepended so it's visible + pre-selected without duplicating when already in TIMEZONES.
 * (STORY-018-07 R2)
 */
const tzOptions = TIMEZONES.includes(DETECTED_TZ)
  ? TIMEZONES
  : [DETECTED_TZ, ...TIMEZONES];

/** Labels for day-of-week checkboxes. Index 0 = Sunday … 6 = Saturday (matches backend). */
const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// ---------------------------------------------------------------------------
// Default form state
// ---------------------------------------------------------------------------

interface ScheduleState {
  occurrence: ScheduleOccurrence;
  /** HH:MM — used for daily/weekdays/weekly/monthly */
  when: string;
  /** Selected days of week (0=Sun…6=Sat) — weekly only */
  days: number[];
  /** Day of month 1-31 — monthly only */
  dayOfMonth: string;
  /** ISO datetime-local string — once only */
  at: string;
}

const DEFAULT_SCHEDULE: ScheduleState = {
  occurrence: 'daily',
  when: '09:00',
  days: [],
  dayOfMonth: '1',
  at: '',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for AddAutomationModal.
 */
export interface AddAutomationModalProps {
  /** UUID of the workspace to create the automation in. */
  workspaceId: string;
  /** Whether the modal is currently open. */
  open: boolean;
  /** Callback invoked when the modal should close (success or cancel). */
  onClose: () => void;
  /**
   * Channel bindings for the workspace — passed in from parent (already fetched via
   * useChannelBindingsQuery). Modal does NOT re-fetch.
   */
  channelBindings: ChannelBinding[];
}

// ---------------------------------------------------------------------------
// Sub-component: DryRunResultInline
// ---------------------------------------------------------------------------

/**
 * DryRunResultInline — renders the result of an inline preview (test-run).
 *
 * States:
 *   - loading  — spinner + "Running preview…"
 *   - success  — light blue card with agent output + token count
 *   - error    — red card; special case for `'no_key_configured'`
 *   - timeout  — amber card (error === "timeout")
 */
interface DryRunResultInlineProps {
  isPending: boolean;
  result: TestRunResult | null;
  error: Error | null;
}

function DryRunResultInline({ isPending, result, error }: DryRunResultInlineProps) {
  if (!isPending && !result && !error) return null;

  if (isPending) {
    return (
      <div className="mt-2 flex items-center gap-2 text-sm text-slate-500">
        <span
          className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent"
          aria-label="Running preview"
        />
        <span>Running preview…</span>
      </div>
    );
  }

  if (error) {
    const isTimeout = error.message?.toLowerCase().includes('timeout');
    return (
      <div
        className={`mt-2 rounded-md border p-3 text-sm ${
          isTimeout
            ? 'border-amber-300 bg-amber-50 text-amber-800'
            : 'border-rose-300 bg-rose-50 text-rose-800'
        }`}
        role="alert"
      >
        {isTimeout ? 'Preview timed out.' : `Preview error: ${error.message}`}
      </div>
    );
  }

  if (result) {
    if (!result.success) {
      const isNoKey = result.error === 'no_key_configured';
      return (
        <div
          className="mt-2 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800"
          role="alert"
        >
          {isNoKey
            ? 'No API key configured. Configure a key in the Key section first.'
            : `Preview failed: ${result.error ?? 'Unknown error'}`}
        </div>
      );
    }
    return (
      <div className="mt-2 rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-slate-700">
        <p className="mb-1 font-semibold text-sky-700">Preview output</p>
        <pre className="whitespace-pre-wrap text-xs">{result.output}</pre>
        {result.tokens_used != null && (
          <p className="mt-1 text-xs text-slate-400">{result.tokens_used} tokens</p>
        )}
      </div>
    );
  }

  return null;
}

// ---------------------------------------------------------------------------
// Sub-component: ScheduleBuilder
// ---------------------------------------------------------------------------

interface ScheduleBuilderProps {
  value: ScheduleState;
  onChange: (next: ScheduleState) => void;
  error?: string | null;
}

/**
 * ScheduleBuilder — occurrence picker + conditional sub-fields for each schedule type.
 *
 * Occurrence buttons: Daily | Weekdays | Weekly | Monthly | Once.
 * Renders only the fields relevant to the selected occurrence:
 *   - daily/weekdays: HH:MM time
 *   - weekly: HH:MM + day-of-week checkboxes
 *   - monthly: HH:MM + day-of-month number
 *   - once: datetime-local input
 */
function ScheduleBuilder({ value, onChange, error }: ScheduleBuilderProps) {
  const occurrences: ScheduleOccurrence[] = ['daily', 'weekdays', 'weekly', 'monthly', 'once'];
  const occurrenceLabels: Record<ScheduleOccurrence, string> = {
    daily: 'Daily',
    weekdays: 'Weekdays',
    weekly: 'Weekly',
    monthly: 'Monthly',
    once: 'Once',
  };

  function setOccurrence(occ: ScheduleOccurrence) {
    onChange({ ...value, occurrence: occ });
  }

  function toggleDay(dayIndex: number) {
    const next = value.days.includes(dayIndex)
      ? value.days.filter((d) => d !== dayIndex)
      : [...value.days, dayIndex].sort((a, b) => a - b);
    onChange({ ...value, days: next });
  }

  return (
    <div>
      <label className="mb-1 block text-sm font-semibold text-slate-700">Schedule</label>

      {/* Occurrence segmented control */}
      <div className="mb-3 flex flex-wrap gap-1">
        {occurrences.map((occ) => (
          <button
            key={occ}
            type="button"
            onClick={() => setOccurrence(occ)}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
              value.occurrence === occ
                ? 'bg-brand-500 text-white'
                : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
            }`}
          >
            {occurrenceLabels[occ]}
          </button>
        ))}
      </div>

      {/* Conditional fields */}
      {(value.occurrence === 'daily' || value.occurrence === 'weekdays') && (
        <div>
          <label className="mb-1 block text-xs font-semibold text-slate-600">
            Time (HH:MM)
          </label>
          <input
            type="time"
            value={value.when}
            onChange={(e) => onChange({ ...value, when: e.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      )}

      {value.occurrence === 'weekly' && (
        <div className="space-y-2">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              Time (HH:MM)
            </label>
            <input
              type="time"
              value={value.when}
              onChange={(e) => onChange({ ...value, when: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">Days</label>
            <div className="flex flex-wrap gap-1">
              {DAY_LABELS.map((label, idx) => (
                <label key={idx} className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={value.days.includes(idx)}
                    onChange={() => toggleDay(idx)}
                    className="rounded"
                  />
                  <span className="text-xs text-slate-700">{label}</span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}

      {value.occurrence === 'monthly' && (
        <div className="flex gap-3">
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              Time (HH:MM)
            </label>
            <input
              type="time"
              value={value.when}
              onChange={(e) => onChange({ ...value, when: e.target.value })}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-slate-600">
              Day of month
            </label>
            <input
              type="number"
              min={1}
              max={31}
              value={value.dayOfMonth}
              onChange={(e) => onChange({ ...value, dayOfMonth: e.target.value })}
              className="w-20 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>
        </div>
      )}

      {value.occurrence === 'once' && (
        <div>
          <label htmlFor="schedule-at" className="mb-1 block text-xs font-semibold text-slate-600">Date & Time</label>
          <input
            id="schedule-at"
            type="datetime-local"
            value={value.at}
            onChange={(e) => onChange({ ...value, at: e.target.value })}
            className="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      )}

      {error && (
        <p className="mt-1 text-xs text-rose-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component: AddAutomationModal
// ---------------------------------------------------------------------------

/**
 * AddAutomationModal — guided form modal for creating a workspace automation.
 *
 * Pure consumer of STORY-018-05 hooks — does not add entries to api.ts or useAutomations.ts.
 *
 * @example
 * ```tsx
 * <AddAutomationModal
 *   workspaceId={workspaceId}
 *   open={addAutomationOpen}
 *   onClose={() => setAddAutomationOpen(false)}
 *   channelBindings={channelBindings}
 * />
 * ```
 */
export function AddAutomationModal({
  workspaceId,
  open,
  onClose,
  channelBindings,
}: AddAutomationModalProps) {
  // ---------------------------------------------------------------------------
  // Form state
  // ---------------------------------------------------------------------------
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [prompt, setPrompt] = useState('');
  const [schedule, setSchedule] = useState<ScheduleState>(DEFAULT_SCHEDULE);
  // STORY-018-07 R3: initialize to DETECTED_TZ — no runtime gate needed because
  // tzOptions always contains the detected value (see module-scope tzOptions).
  const [timezone, setTimezone] = useState(DETECTED_TZ);
  const [selectedChannelIds, setSelectedChannelIds] = useState<string[]>([]);

  // ---------------------------------------------------------------------------
  // Validation errors (only shown after submit attempt)
  // ---------------------------------------------------------------------------
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Hooks
  // ---------------------------------------------------------------------------
  const createMutation = useCreateAutomationMutation(workspaceId);
  const testRunMutation = useTestRunMutation(workspaceId);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /** Reset all form state to defaults. Called on close and after successful submit. */
  function resetForm() {
    setName('');
    setDescription('');
    setPrompt('');
    setSchedule(DEFAULT_SCHEDULE);
    setTimezone(DETECTED_TZ); // STORY-018-07 R3: reset to detected zone, not hard-coded UTC
    setSelectedChannelIds([]);
    setErrors({});
    setServerError(null);
    createMutation.reset();
    testRunMutation.reset();
  }

  function handleClose() {
    resetForm();
    onClose();
  }

  /**
   * Builds the AutomationSchedule payload that matches backend `_AUTOMATIONS_PROMPT_SECTION`.
   * Returns null if validation fails (callers should not proceed).
   */
  function buildSchedulePayload(): AutomationSchedule | null {
    const occ = schedule.occurrence;
    if (occ === 'daily' || occ === 'weekdays') {
      return { occurrence: occ, when: schedule.when };
    }
    if (occ === 'weekly') {
      return { occurrence: 'weekly', when: schedule.when, days: schedule.days };
    }
    if (occ === 'monthly') {
      return {
        occurrence: 'monthly',
        when: schedule.when,
        day_of_month: parseInt(schedule.dayOfMonth, 10),
      };
    }
    if (occ === 'once') {
      return { occurrence: 'once', at: schedule.at };
    }
    return null;
  }

  /** Returns an error map; empty map = valid. */
  function validate(): Record<string, string> {
    const errs: Record<string, string> = {};

    if (!name.trim()) {
      errs.name = 'Name is required';
    }

    if (!prompt.trim()) {
      errs.prompt = 'Prompt is required';
    }

    // Schedule validation
    const occ = schedule.occurrence;
    if (occ === 'daily' || occ === 'weekdays') {
      if (!schedule.when) errs.schedule = 'Time is required';
    } else if (occ === 'weekly') {
      if (!schedule.when) errs.schedule = 'Time is required';
      else if (schedule.days.length === 0) errs.schedule = 'Select at least one day';
    } else if (occ === 'monthly') {
      if (!schedule.when) errs.schedule = 'Time is required';
      else if (!schedule.dayOfMonth || isNaN(parseInt(schedule.dayOfMonth, 10))) {
        errs.schedule = 'Day of month is required';
      }
    } else if (occ === 'once') {
      if (!schedule.at) {
        errs.schedule = "'At' time must be in the future";
      } else {
        const atDate = new Date(schedule.at);
        if (isNaN(atDate.getTime()) || atDate <= new Date()) {
          errs.schedule = "'At' time must be in the future";
        }
      }
    }

    // Channel validation
    if (channelBindings.length === 0) {
      errs.channels = 'No channels bound to this workspace';
    } else if (selectedChannelIds.length === 0) {
      errs.channels = 'Select at least one channel';
    }

    return errs;
  }

  function toggleChannel(channelId: string) {
    setSelectedChannelIds((prev) =>
      prev.includes(channelId) ? prev.filter((id) => id !== channelId) : [...prev, channelId],
    );
  }

  /** Fires the inline preview (test-run). */
  function handlePreview() {
    if (!prompt.trim()) return;
    testRunMutation.reset();
    testRunMutation.mutate({ prompt, timezone });
  }

  /** Handles form submission — validates, then calls createAutomation mutation. */
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }
    setErrors({});
    setServerError(null);

    const schedulePayload = buildSchedulePayload();
    if (!schedulePayload) return;

    const scheduleType = schedule.occurrence === 'once' ? 'once' : 'recurring';

    try {
      await createMutation.mutateAsync({
        name: name.trim(),
        prompt: prompt.trim(),
        description: description.trim() || null,
        schedule: schedulePayload,
        schedule_type: scheduleType,
        timezone,
        slack_channel_ids: selectedChannelIds,
      });
      resetForm();
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save automation';
      setServerError(message);
    }
  }

  if (!open) return null;

  const noChannels = channelBindings.length === 0;
  const submitDisabled = createMutation.isPending || noChannels;

  return (
    /* Backdrop overlay — div-based (FLASHCARD 2026-04-12 #vitest #frontend) */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Add Automation"
    >
      {/* Modal panel */}
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-lg max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">New Automation</h2>

          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              {/* Name */}
              <div>
                <label
                  htmlFor="automation-name"
                  className="mb-1 block text-sm font-semibold text-slate-700"
                >
                  Name <span className="text-rose-500">*</span>
                </label>
                <input
                  id="automation-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Weekly Standup Digest"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                {errors.name && (
                  <p className="mt-1 text-xs text-rose-600" role="alert">
                    {errors.name}
                  </p>
                )}
              </div>

              {/* Description (optional) */}
              <div>
                <label
                  htmlFor="automation-description"
                  className="mb-1 block text-sm font-semibold text-slate-700"
                >
                  Description{' '}
                  <span className="text-xs font-normal text-slate-400">(optional)</span>
                </label>
                <input
                  id="automation-description"
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What does this automation do?"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              {/* Prompt */}
              <div>
                <label
                  htmlFor="automation-prompt"
                  className="mb-1 block text-sm font-semibold text-slate-700"
                >
                  Prompt <span className="text-rose-500">*</span>
                </label>
                <textarea
                  id="automation-prompt"
                  rows={4}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. Summarise this week's project updates and flag any blockers."
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                {errors.prompt && (
                  <p className="mt-1 text-xs text-rose-600" role="alert">
                    {errors.prompt}
                  </p>
                )}

                {/* Preview button */}
                <button
                  type="button"
                  onClick={handlePreview}
                  disabled={testRunMutation.isPending || !prompt.trim()}
                  className="mt-2 rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {testRunMutation.isPending ? 'Previewing…' : 'Preview'}
                </button>

                {/* Inline dry-run result */}
                <DryRunResultInline
                  isPending={testRunMutation.isPending}
                  result={testRunMutation.data ?? null}
                  error={testRunMutation.error instanceof Error ? testRunMutation.error : null}
                />
              </div>

              {/* Schedule builder */}
              <ScheduleBuilder
                value={schedule}
                onChange={setSchedule}
                error={errors.schedule}
              />

              {/* Timezone */}
              <div>
                <label
                  htmlFor="automation-timezone"
                  className="mb-1 block text-sm font-semibold text-slate-700"
                >
                  Timezone
                </label>
                <select
                  id="automation-timezone"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  className="rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  {tzOptions.map((tz) => (
                    <option key={tz} value={tz}>
                      {tz}
                    </option>
                  ))}
                </select>
              </div>

              {/* Channel picker */}
              <div>
                <label className="mb-1 block text-sm font-semibold text-slate-700">
                  Channels <span className="text-rose-500">*</span>
                </label>

                {noChannels ? (
                  <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                    No channels bound. Bind a Slack channel first in the Channels section.
                  </p>
                ) : (
                  <div className="space-y-1 rounded-md border border-slate-200 p-2 max-h-36 overflow-y-auto">
                    {channelBindings.map((binding) => (
                      <label
                        key={binding.slack_channel_id}
                        className="flex items-center gap-2 cursor-pointer hover:bg-slate-50 rounded px-1 py-0.5"
                      >
                        <input
                          type="checkbox"
                          checked={selectedChannelIds.includes(binding.slack_channel_id)}
                          onChange={() => toggleChannel(binding.slack_channel_id)}
                          className="rounded"
                        />
                        <span className="text-sm text-slate-700">
                          #{binding.channel_name ?? binding.slack_channel_id}
                        </span>
                      </label>
                    ))}
                  </div>
                )}

                {errors.channels && !noChannels && (
                  <p className="mt-1 text-xs text-rose-600" role="alert">
                    {errors.channels}
                  </p>
                )}
              </div>

              {/* Server error */}
              {serverError && (
                <p className="text-sm text-rose-600" role="alert">
                  {serverError}
                </p>
              )}
            </div>

            {/* Action buttons */}
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={handleClose}
                disabled={createMutation.isPending}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitDisabled}
                className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {createMutation.isPending ? 'Saving…' : 'Save Automation'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
