/**
 * AutomationHistoryDrawer.tsx — Inline slide-in history panel for an automation (STORY-018-05).
 *
 * Displayed as a div-based slide-in within the workspace detail page — NOT a <dialog>
 * (FLASHCARD 2026-04-12 #vitest #frontend: jsdom lacks HTMLDialogElement.showModal()).
 *
 * Renders when `automationId` is non-null. Fetches execution history via
 * `useAutomationHistoryQuery(workspaceId, automationId)` and displays rows newest-first
 * (the API returns them newest-first; we render in order).
 *
 * Each row shows:
 *   - Status badge (success=emerald, partial=amber, failed=rose, running=blue)
 *   - started_at timestamp
 *   - Duration computed from started_at → completed_at (or execution_time_ms)
 *   - Token count from tokens_used
 *   - was_dry_run chip
 *
 * Expand toggle reveals:
 *   - generated_content text
 *   - Per-channel delivery results
 *
 * All data comes from the hook — no raw fetch() calls.
 */

import { useState } from 'react';
import { useAutomationHistoryQuery } from '../../hooks/useAutomations';
import type { AutomationExecution, ExecutionStatus } from '../../types/automation';
import type { ChannelBinding } from '../../lib/api';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for AutomationHistoryDrawer.
 */
export interface AutomationHistoryDrawerProps {
  /** UUID of the workspace that owns the automation. */
  workspaceId: string;
  /**
   * UUID of the automation whose history to show.
   * null = drawer is closed (renders nothing).
   */
  automationId: string | null;
  /** Human-readable automation name shown in the drawer header. */
  automationName: string;
  /** Callback to close the drawer — parent clears its automationId state. */
  onClose: () => void;
  /**
   * Channel bindings for the workspace — used to resolve channel names in
   * per-channel delivery result rows.
   */
  channelBindings: ChannelBinding[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns Tailwind classes for the status badge based on execution status.
 *
 * @param status - ExecutionStatus value from the API response.
 * @returns Tailwind className string for the badge.
 */
function statusBadgeClass(status: ExecutionStatus | string): string {
  switch (status) {
    case 'success':
      return 'bg-emerald-100 text-emerald-700';
    case 'partial':
      return 'bg-amber-100 text-amber-700';
    case 'failed':
      return 'bg-rose-100 text-rose-700';
    case 'running':
      return 'bg-blue-100 text-blue-700';
    default:
      return 'bg-slate-100 text-slate-700';
  }
}

/**
 * Formats a duration from ms into a human-readable string like "1.2s" or "850ms".
 *
 * @param ms - Duration in milliseconds.
 * @returns Short duration string.
 */
function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.round(ms)}ms`;
}

/**
 * Computes execution duration from the execution record.
 * Prefers `execution_time_ms` if available; falls back to computing
 * the difference between `started_at` and `completed_at`.
 *
 * @param execution - Automation execution record.
 * @returns Human-readable duration string, or "—" if unavailable.
 */
function computeDuration(execution: AutomationExecution): string {
  if (execution.execution_time_ms != null) {
    return formatDuration(execution.execution_time_ms);
  }
  if (execution.started_at && execution.completed_at) {
    const ms =
      new Date(execution.completed_at).getTime() -
      new Date(execution.started_at).getTime();
    if (!isNaN(ms) && ms >= 0) return formatDuration(ms);
  }
  return '—';
}

// ---------------------------------------------------------------------------
// HistoryRow sub-component
// ---------------------------------------------------------------------------

/** Props for HistoryRow. */
interface HistoryRowProps {
  execution: AutomationExecution;
  channelNameById: Map<string, string>;
}

/**
 * HistoryRow — a single execution entry in the history list.
 *
 * Renders a collapsed summary row with a chevron toggle.
 * On expand, shows generated_content and per-channel delivery results.
 *
 * @param execution      - The execution record to display.
 * @param channelNameById - Map from channel ID → channel name for delivery results.
 */
function HistoryRow({ execution, channelNameById }: HistoryRowProps) {
  const [expanded, setExpanded] = useState(false);

  const duration = computeDuration(execution);

  return (
    <div
      data-testid={`history-row-${execution.id}`}
      className="border border-slate-100 rounded-lg overflow-hidden"
    >
      {/* Collapsed summary row */}
      <button
        type="button"
        data-testid={`history-row-expand-${execution.id}`}
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center gap-3 px-3 py-2 text-left hover:bg-slate-50"
        aria-expanded={expanded}
      >
        {/* Status badge */}
        <span
          data-testid={`history-status-${execution.id}`}
          className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(execution.status)}`}
        >
          {execution.status}
        </span>

        {/* started_at timestamp */}
        <span className="text-xs text-slate-500 min-w-0 truncate">
          {execution.started_at
            ? new Date(execution.started_at).toLocaleString()
            : '—'}
        </span>

        {/* Duration */}
        <span className="text-xs text-slate-400 shrink-0">{duration}</span>

        {/* Token count */}
        {execution.tokens_used != null && (
          <span className="text-xs text-slate-400 shrink-0">
            {execution.tokens_used.toLocaleString()} tok
          </span>
        )}

        {/* Dry run chip */}
        {execution.was_dry_run && (
          <span className="shrink-0 rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-600">
            dry run
          </span>
        )}

        {/* Chevron expand indicator */}
        <span
          className={`ml-auto text-slate-300 text-xs transition-transform ${expanded ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          ▼
        </span>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div
          data-testid={`history-expanded-${execution.id}`}
          className="px-3 py-3 border-t border-slate-100 bg-slate-50 space-y-3"
        >
          {/* Generated content */}
          {execution.generated_content ? (
            <div>
              <p className="text-xs font-semibold text-slate-700 mb-1">Generated content</p>
              <pre
                data-testid={`history-content-${execution.id}`}
                className="text-xs text-slate-600 whitespace-pre-wrap bg-white border border-slate-100 rounded p-2"
              >
                {execution.generated_content}
              </pre>
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">No content generated.</p>
          )}

          {/* Per-channel delivery results */}
          {execution.delivery_results && execution.delivery_results.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-700 mb-1">Delivery results</p>
              <ul className="space-y-1">
                {execution.delivery_results.map((result, idx) => (
                  <li
                    key={`${result.channel_id}-${idx}`}
                    className="flex items-center gap-2 text-xs"
                  >
                    <span
                      className={`rounded-full w-1.5 h-1.5 shrink-0 ${result.ok ? 'bg-emerald-400' : 'bg-rose-400'}`}
                    />
                    <span className="text-slate-600">
                      #{channelNameById.get(result.channel_id) ?? result.channel_id}
                    </span>
                    {!result.ok && result.error && (
                      <span className="text-rose-500">{result.error}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Error message */}
          {execution.error && (
            <div>
              <p className="text-xs font-semibold text-slate-700 mb-1">Error</p>
              <p className="text-xs text-rose-600">{execution.error}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AutomationHistoryDrawer
// ---------------------------------------------------------------------------

/**
 * AutomationHistoryDrawer — inline slide-in panel showing execution history.
 *
 * Conditionally renders when `automationId` is non-null. Uses a div-based
 * slide-in pattern (NOT a native <dialog>) per the jsdom constraint.
 *
 * @param props - workspaceId, automationId, automationName, onClose, channelBindings.
 */
export function AutomationHistoryDrawer({
  workspaceId,
  automationId,
  automationName,
  onClose,
  channelBindings,
}: AutomationHistoryDrawerProps) {
  // Don't render when closed.
  if (automationId === null) return null;

  const { data: history = [], isLoading } = useAutomationHistoryQuery(workspaceId, automationId);

  // Build channel name lookup map.
  const channelNameById = new Map(
    channelBindings.map((b) => [b.slack_channel_id, b.channel_name ?? b.slack_channel_id]),
  );

  return (
    <div
      data-testid="automation-history-drawer"
      className="rounded-lg border border-slate-200 bg-white"
    >
      {/* Drawer header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
        <h3 className="text-sm font-semibold text-slate-900">
          History — {automationName}
        </h3>
        <button
          type="button"
          data-testid="history-drawer-close"
          onClick={onClose}
          className="text-slate-400 hover:text-slate-600 text-sm"
          aria-label="Close history drawer"
        >
          ×
        </button>
      </div>

      {/* Drawer body */}
      <div className="p-4">
        {isLoading ? (
          <div
            data-testid="history-loading"
            className="space-y-2"
          >
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded border border-slate-100 bg-slate-50 h-10"
              />
            ))}
          </div>
        ) : history.length === 0 ? (
          <p
            data-testid="history-empty"
            className="text-sm text-slate-500 py-4 text-center"
          >
            No execution history yet.
          </p>
        ) : (
          <div
            data-testid="history-list"
            className="space-y-2"
          >
            {history.map((execution) => (
              <HistoryRow
                key={execution.id}
                execution={execution}
                channelNameById={channelNameById}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
