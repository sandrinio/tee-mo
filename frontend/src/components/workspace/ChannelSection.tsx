/**
 * ChannelSection.tsx — Channel binding management UI for a workspace (STORY-008-02).
 *
 * Displays the list of Slack channels bound to a workspace, their membership
 * status, and provides controls for binding and unbinding channels.
 *
 * Key behaviours:
 * - Empty state: when no channels are bound, shows guidance text.
 * - Active badge (emerald): channel where the bot is a member (is_member=true).
 * - Pending badge (amber): channel where the bot is not yet a member (is_member=false).
 * - /invite snippet: shown for pending channels so the user can copy-paste the command.
 * - Channel picker: opens on "Add channel" click, filtered to exclude already-bound channels.
 * - Bind flow: select a channel → mutation fires → picker closes.
 * - 409 error: "already bound to another workspace" message shown inline.
 * - Unbind flow: x click → confirm prompt → confirm click → mutation fires.
 *
 * All hooks come from `../../../hooks/useChannels` — no direct fetch calls.
 * jsdom does NOT implement HTMLDialogElement.showModal() so we use div overlays
 * (see FLASHCARDS.md, Sprint S-05 lesson). The picker is a div, not a <dialog>.
 */

import { useState } from 'react';
import {
  useBindChannelMutation,
  useChannelBindingsQuery,
  useSlackChannelsQuery,
  useUnbindChannelMutation,
} from '../../hooks/useChannels';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for the ChannelSection component.
 */
export interface ChannelSectionProps {
  /** UUID of the workspace this section manages channels for. */
  workspaceId: string;
  /** Slack team ID used to fetch available channels for the picker. */
  teamId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Channel binding management section for the workspace settings view.
 *
 * Renders the list of bound channels with their membership status badges,
 * /invite copy snippets for pending channels, and an "Add channel" button
 * that opens a channel picker filtered to unbound channels only.
 *
 * @param props - workspaceId and teamId to scope all API calls.
 */
export function ChannelSection({ workspaceId, teamId }: ChannelSectionProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [confirmingUnbind, setConfirmingUnbind] = useState<string | null>(null);
  const [bindError, setBindError] = useState<string | null>(null);

  const { data: allChannels = [] } = useSlackChannelsQuery(teamId);
  const { data: bindings = [] } = useChannelBindingsQuery(workspaceId);
  const bindMutation = useBindChannelMutation(workspaceId);
  const unbindMutation = useUnbindChannelMutation(workspaceId);

  // IDs of channels already bound — used to filter the picker
  const boundIds = new Set(bindings.map((b) => b.slack_channel_id));

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  /**
   * Handles a channel selection from the picker.
   * Fires the bind mutation and closes the picker on success.
   * On error (e.g. 409), shows inline error message.
   */
  function handlePickChannel(channelId: string) {
    setBindError(null);
    bindMutation.mutate(
      { channelId },
      {
        onSuccess: () => {
          setPickerOpen(false);
        },
        onError: (err: Error) => {
          setBindError(err.message);
        },
      },
    );
  }

  /**
   * Handles the unbind confirmation button click.
   * Fires the unbind mutation and clears the confirmation state.
   */
  function handleConfirmUnbind(channelId: string) {
    unbindMutation.mutate(
      { channelId },
      {
        onSuccess: () => {
          setConfirmingUnbind(null);
        },
      },
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div>
      {/* Empty state — shown when no channels are bound */}
      {bindings.length === 0 && (
        <div data-testid="channel-empty-state" className="text-slate-500 text-sm py-4">
          No channels bound yet. Add a channel to get started.
        </div>
      )}

      {/* Bound channel list */}
      {bindings.map((binding) => (
        <div
          key={binding.slack_channel_id}
          className="flex items-start gap-3 py-2"
        >
          {/* Channel name — displayed without "#" prefix to avoid clash with picker text */}
          <span className="text-slate-700 font-semibold">
            {binding.channel_name ?? binding.slack_channel_id}
          </span>

          {/* Status badge — emerald for Active (is_member=true), amber for Pending */}
          {binding.is_member ? (
            <div
              data-testid={`channel-status-${binding.slack_channel_id}`}
              className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded"
            >
              Active
            </div>
          ) : (
            <div
              data-testid={`channel-status-${binding.slack_channel_id}`}
              className="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded"
            >
              Pending
            </div>
          )}

          {/* /invite snippet — only shown for pending (is_member=false) channels */}
          {!binding.is_member && (
            <code
              data-testid={`invite-snippet-${binding.slack_channel_id}`}
              className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono"
            >
              /invite @tee-mo
            </code>
          )}

          {/* Unbind button */}
          <button
            data-testid={`unbind-button-${binding.slack_channel_id}`}
            onClick={() => setConfirmingUnbind(binding.slack_channel_id)}
            className="ml-auto text-slate-400 hover:text-brand-500 text-sm"
            aria-label={`Unbind ${binding.channel_name ?? binding.slack_channel_id}`}
          >
            ×
          </button>

          {/* Unbind confirmation — shown after clicking the x button */}
          {confirmingUnbind === binding.slack_channel_id && (
            <div
              data-testid={`unbind-confirm-${binding.slack_channel_id}`}
              className="flex items-center gap-2 text-sm"
            >
              <span className="text-slate-600">Remove this channel?</span>
              <button
                data-testid={`unbind-confirm-btn-${binding.slack_channel_id}`}
                onClick={() => handleConfirmUnbind(binding.slack_channel_id)}
                className="text-brand-500 font-semibold"
              >
                Confirm
              </button>
              <button
                onClick={() => setConfirmingUnbind(null)}
                className="text-slate-400"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      ))}

      {/* 409 conflict error — shown when bind fails with "already bound" detail */}
      {bindMutation.isError && (
        <div
          data-testid="channel-bind-error"
          className="text-sm text-red-600 mt-2"
        >
          {bindMutation.error instanceof Error
            ? bindMutation.error.message
            : 'This channel is already bound to another workspace. Unbind it there first.'}
        </div>
      )}

      {/* Inline bind error from onError callback (before mutation state settles) */}
      {bindError && !bindMutation.isError && (
        <div
          data-testid="channel-bind-error"
          className="text-sm text-red-600 mt-2"
        >
          {bindError}
        </div>
      )}

      {/* Add channel button */}
      <button
        data-testid="add-channel-button"
        onClick={() => {
          setBindError(null);
          setPickerOpen(true);
        }}
        className="mt-4 text-sm text-brand-500 font-semibold"
      >
        + Add channel
      </button>

      {/* Channel picker — div-based overlay (jsdom does not support showModal()) */}
      {pickerOpen && (
        <div
          data-testid="channel-picker"
          className="mt-2 border border-slate-200 rounded-lg bg-white shadow-sm p-3"
        >
          {allChannels.length === 0 ? (
            <p className="text-slate-500 text-sm">No channels found in this Slack team.</p>
          ) : (
            <ul>
              {allChannels.map((channel) => {
                const isBoundHere = boundIds.has(channel.id);
                const isBoundElsewhere =
                  !isBoundHere &&
                  !!channel.bound_workspace_id &&
                  channel.bound_workspace_id !== workspaceId;
                const isUnavailable = isBoundHere || isBoundElsewhere;
                return (
                  <li key={channel.id}>
                    {isUnavailable ? (
                      <div
                        className="w-full text-left py-1 px-2 text-sm rounded flex items-center gap-2 opacity-50 cursor-not-allowed"
                      >
                        <span className="h-2 w-2 rounded-full bg-rose-400 shrink-0" />
                        <span className="text-slate-400">#{channel.name}</span>
                        <span className="text-xs text-slate-400 ml-auto">
                          {isBoundElsewhere ? 'other workspace' : 'bound'}
                        </span>
                      </div>
                    ) : (
                      <button
                        data-testid={`pick-channel-${channel.id}`}
                        onClick={() => handlePickChannel(channel.id)}
                        className="w-full text-left py-1 px-2 text-sm hover:bg-slate-50 rounded flex items-center gap-2"
                      >
                        <span className="h-2 w-2 rounded-full bg-emerald-400 shrink-0" />
                        #{channel.name}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          <button
            onClick={() => setPickerOpen(false)}
            className="mt-2 text-xs text-slate-400"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
