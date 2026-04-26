/**
 * AutomationsSection.tsx — Automations list for the workspace detail page (STORY-018-05).
 *
 * Displays all workspace automations as cards. Each card shows:
 *   - Name + human-readable schedule summary (via getScheduleSummary)
 *   - Status badge: Active (emerald) or Paused (amber)
 *   - Next run timestamp label
 *   - Channel pills for each bound Slack channel
 *   - Action buttons: History, Dry Run, Toggle, Delete
 *
 * Delete uses the two-click confirmation pattern copied exactly from ChannelSection.tsx:
 *   - First click: button label changes to "Confirm?" (stored in `confirmingDelete` state)
 *   - Second click: mutation fires; `confirmingDelete` is cleared on success
 *
 * History button: sets `historyAutomationId` state in parent via `onHistoryClick` callback.
 * AutomationHistoryDrawer is mounted by the parent (WorkspaceDetailPage) — this component
 * only triggers the open.
 *
 * All data fetching goes through `useAutomationsQuery`, `useUpdateAutomationMutation`,
 * and `useDeleteAutomationMutation` — no raw fetch() calls (FLASHCARD 2026-04-11
 * #frontend #recipe).
 *
 * jsdom does NOT support HTMLDialogElement.showModal() — this component uses
 * div-based patterns only (FLASHCARD 2026-04-12 #vitest #frontend).
 */

import { useState } from 'react';
import { Zap } from 'lucide-react';
import { ModuleAvatarTile } from './SlackSection';
import { AddAutomationModal } from './AddAutomationModal';
import { DryRunModal } from './DryRunModal';
import { AutomationHistoryDrawer } from './AutomationHistoryDrawer';
import {
  useAutomationsQuery,
  useUpdateAutomationMutation,
  useDeleteAutomationMutation,
} from '../../hooks/useAutomations';
import { getScheduleSummary } from '../../types/automation';
import type { ChannelBinding } from '../../lib/api';
import type { Automation } from '../../types/automation';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for AutomationsSection.
 *
 * HOTFIX 2026-04-26: callback props (onAddClick / onDryRunClick / onHistoryClick)
 * removed. AutomationsSection now owns the modal state and renders the modals
 * itself — registry-driven shells can't easily inject parent callbacks, and
 * the modals only ever lived next to this section anyway.
 */
export interface AutomationsSectionProps {
  /** UUID of the workspace to list automations for. */
  workspaceId: string;
  /**
   * Channel bindings for the workspace — used to resolve channel names
   * from Slack channel IDs stored in `automation.slack_channel_ids`.
   */
  channelBindings: ChannelBinding[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AutomationsSection — the full automations management panel on the workspace detail page.
 *
 * Handles empty state, automation card list, toggle/delete mutations, and
 * delegates modal opening to parent via callbacks (onAddClick, onDryRunClick, onHistoryClick).
 *
 * @param props - workspaceId, channelBindings, and three callback props.
 */
export function AutomationsSection({
  workspaceId,
  channelBindings,
}: AutomationsSectionProps) {
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null);

  // HOTFIX 2026-04-26: self-contained modal state.
  const [addOpen, setAddOpen] = useState(false);
  const [dryRunCtx, setDryRunCtx] = useState<{ prompt: string; name: string } | null>(null);
  const [historyCtx, setHistoryCtx] = useState<{ id: string; name: string } | null>(null);

  const onAddClick = () => setAddOpen(true);
  const onDryRunClick = (prompt: string, name: string) => setDryRunCtx({ prompt, name });
  const onHistoryClick = (id: string, name: string) => setHistoryCtx({ id, name });

  const { data: automations = [], isLoading } = useAutomationsQuery(workspaceId);
  const updateMutation = useUpdateAutomationMutation(workspaceId);
  const deleteMutation = useDeleteAutomationMutation(workspaceId);

  // Build a channel name lookup map from bindings for fast O(1) access.
  const channelNameById = new Map(
    channelBindings.map((b) => [b.slack_channel_id, b.channel_name ?? b.slack_channel_id]),
  );

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  /**
   * Toggles the `is_active` flag on an automation.
   * Active → Paused, Paused → Active. Invalidates list cache on success.
   *
   * @param automation - The automation to toggle.
   */
  function handleToggle(automation: Automation) {
    updateMutation.mutate({
      automationId: automation.id,
      is_active: !automation.is_active,
    });
  }

  /**
   * First-click of the two-click delete: sets the confirming state.
   * Second-click fires the delete mutation and clears confirming state.
   *
   * @param automationId - UUID of the automation to delete.
   */
  function handleDeleteClick(automationId: string) {
    if (confirmingDelete === automationId) {
      // Second click — fire the mutation.
      deleteMutation.mutate(automationId, {
        onSuccess: () => {
          setConfirmingDelete(null);
        },
      });
    } else {
      // First click — enter confirmation mode.
      setConfirmingDelete(automationId);
    }
  }

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div data-testid="automations-loading" className="space-y-2">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="animate-pulse rounded-lg border border-slate-200 bg-white p-4"
          >
            <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
            <div className="h-3 w-2/3 rounded bg-slate-100" />
          </div>
        ))}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div data-testid="automations-section">
      {/* HOTFIX 2026-04-26: section title + caption removed — ModuleSection
          wrapper already provides them per W01 §5.1. Only the +Add action
          remains, right-aligned via an empty flex spacer. */}
      <div className="flex items-center justify-end mb-3">
        <button
          type="button"
          data-testid="add-automation-button"
          onClick={onAddClick}
          className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600"
        >
          + Add
        </button>
      </div>

      {/* Empty state — per W01 §3 STORY-025-04 handoff spec */}
      {automations.length === 0 && (
        <div
          data-testid="automations-empty-state"
          className="rounded-lg border border-slate-200 bg-white"
        >
          <div className="flex flex-col items-center gap-3 py-8">
            {/* 40×40 slate-100 zap-icon tile — shared primitive per W01 §5.6 */}
            <ModuleAvatarTile icon={Zap} data-testid="automations-empty-zap-tile" />
            <h3 className="text-base font-semibold text-slate-900">No automations yet</h3>
            <p className="text-sm text-slate-500 text-center px-4">
              Trigger Tee-Mo on a schedule, on a Slack event, or from a webhook.
            </p>
            <button
              type="button"
              data-testid="create-automation-button"
              onClick={onAddClick}
              className="rounded-md bg-white text-slate-900 border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 hover:border-slate-400"
            >
              Create automation
            </button>
          </div>
        </div>
      )}

      {/* Automation cards */}
      <div className="space-y-3">
        {automations.map((automation) => {
          const isConfirmingDelete = confirmingDelete === automation.id;
          const scheduleSummary = getScheduleSummary(automation.schedule, automation.timezone);

          return (
            <div
              key={automation.id}
              data-testid={`automation-card-${automation.id}`}
              className="rounded-lg border border-slate-200 bg-white p-4"
            >
              {/* Top row: name + status badge */}
              <div className="flex items-start justify-between gap-3 mb-2">
                <div className="min-w-0 flex-1">
                  {/* Automation name */}
                  <span
                    data-testid={`automation-name-${automation.id}`}
                    className="text-sm font-semibold text-slate-900"
                  >
                    {automation.name}
                  </span>

                  {/* Schedule summary */}
                  <p
                    data-testid={`automation-schedule-${automation.id}`}
                    className="text-xs text-slate-500 mt-0.5 capitalize-first"
                  >
                    {scheduleSummary.charAt(0).toUpperCase() + scheduleSummary.slice(1)}
                  </p>
                </div>

                {/* Status badge — emerald for Active, amber for Paused */}
                {automation.is_active ? (
                  <span
                    data-testid={`automation-status-${automation.id}`}
                    className="shrink-0 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700"
                  >
                    Active
                  </span>
                ) : (
                  <span
                    data-testid={`automation-status-${automation.id}`}
                    className="shrink-0 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700"
                  >
                    Paused
                  </span>
                )}
              </div>

              {/* Next run label */}
              {automation.next_run_at && (
                <p
                  data-testid={`automation-next-run-${automation.id}`}
                  className="text-xs text-slate-400 mb-2"
                >
                  Next run: {new Date(automation.next_run_at).toLocaleString()}
                </p>
              )}

              {/* Channel pills */}
              {automation.slack_channel_ids.length > 0 && (
                <div
                  data-testid={`automation-channels-${automation.id}`}
                  className="flex flex-wrap gap-1 mb-3"
                >
                  {automation.slack_channel_ids.map((cid) => (
                    <span
                      key={cid}
                      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                    >
                      #{channelNameById.get(cid) ?? cid}
                    </span>
                  ))}
                </div>
              )}

              {/* Action buttons row */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* History button */}
                <button
                  type="button"
                  data-testid={`history-button-${automation.id}`}
                  onClick={() => onHistoryClick(automation.id, automation.name)}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-700 border border-slate-200 rounded px-2 py-1"
                >
                  History
                </button>

                {/* Dry Run button */}
                <button
                  type="button"
                  data-testid={`dry-run-button-${automation.id}`}
                  onClick={() => onDryRunClick(automation.prompt, automation.name)}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-700 border border-slate-200 rounded px-2 py-1"
                >
                  Dry Run
                </button>

                {/* Toggle button */}
                <button
                  type="button"
                  data-testid={`toggle-button-${automation.id}`}
                  onClick={() => handleToggle(automation)}
                  disabled={updateMutation.isPending}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-700 border border-slate-200 rounded px-2 py-1 disabled:opacity-50"
                >
                  {automation.is_active ? 'Pause' : 'Resume'}
                </button>

                {/* Delete button — two-click confirm pattern */}
                <button
                  type="button"
                  data-testid={`delete-button-${automation.id}`}
                  onClick={() => handleDeleteClick(automation.id)}
                  disabled={deleteMutation.isPending}
                  className={`text-xs font-semibold border rounded px-2 py-1 disabled:opacity-50 ${
                    isConfirmingDelete
                      ? 'border-rose-300 text-rose-500 bg-rose-50'
                      : 'text-slate-500 hover:text-rose-500 border-slate-200'
                  }`}
                >
                  {isConfirmingDelete ? 'Confirm?' : 'Delete'}
                </button>

                {/* Cancel confirmation — shown only in confirm mode */}
                {isConfirmingDelete && (
                  <button
                    type="button"
                    data-testid={`delete-cancel-${automation.id}`}
                    onClick={() => setConfirmingDelete(null)}
                    className="text-xs text-slate-400"
                  >
                    Cancel
                  </button>
                )}
              </div>

              {/* Delete mutation error */}
              {deleteMutation.error && (
                <p
                  data-testid={`delete-error-${automation.id}`}
                  className="mt-1 text-xs text-rose-600"
                  role="alert"
                >
                  {deleteMutation.error instanceof Error
                    ? deleteMutation.error.message
                    : 'Failed to delete automation. Please try again.'}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* HOTFIX 2026-04-26: self-mounted modals + drawer (previously rendered
          by the legacy route — got dropped during 025-06 cutover). */}
      <AddAutomationModal
        workspaceId={workspaceId}
        open={addOpen}
        onClose={() => setAddOpen(false)}
        channelBindings={channelBindings}
      />
      <DryRunModal
        workspaceId={workspaceId}
        automationName={dryRunCtx?.name ?? ''}
        prompt={dryRunCtx?.prompt ?? ''}
        open={dryRunCtx !== null}
        onClose={() => setDryRunCtx(null)}
      />
      <AutomationHistoryDrawer
        workspaceId={workspaceId}
        automationId={historyCtx?.id ?? null}
        automationName={historyCtx?.name ?? ''}
        onClose={() => setHistoryCtx(null)}
        channelBindings={channelBindings}
      />
    </div>
  );
}
