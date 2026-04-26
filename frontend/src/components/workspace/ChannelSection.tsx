/**
 * ChannelSection.tsx — Channel binding management (STORY-025-02 re-skin).
 *
 * Re-skinned to a divider list per the workspace v2 design handoff.
 *
 * HOTFIX 2026-04-26 (per user feedback): the main divider list now shows
 * ONLY bound channels. Unbound channels are no longer mixed in with Bind
 * buttons — they're added via the + Add channel picker. The picker shows
 * ONLY unbound channels (already-bound ones are filtered out, not greyed).
 *
 * Each row in the list: #channel-name + Active/Pending badge + Bound badge +
 * /invite snippet (if pending) + Unbind button.
 *
 * Empty states:
 *   - allChannels is empty → "No channels found in Slack team" guidance.
 *   - allChannels has channels but boundChannels is empty → "No channels
 *     bound yet" guidance pointing at + Add channel.
 *
 * Behaviour preserved verbatim:
 *   - useChannelBindingsQuery, useBindChannelMutation, useUnbindChannelMutation unchanged.
 *   - useSlackChannelsQuery unchanged.
 *   - 409 conflict error handling unchanged.
 *   - Unbind confirmation flow unchanged.
 *
 * Picker overlay markup preserved: CR-001 will add a search input above the
 * existing allChannels.map. The overlay starts at the "Channel picker" comment below.
 *
 * jsdom does NOT implement HTMLDialogElement.showModal() — div-based overlay kept.
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

export interface ChannelSectionProps {
  /** UUID of the workspace this section manages channels for. */
  workspaceId: string;
  /** Slack team ID used to fetch available channels for the picker. */
  teamId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChannelSection({ workspaceId, teamId }: ChannelSectionProps) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [confirmingUnbind, setConfirmingUnbind] = useState<string | null>(null);
  const [bindError, setBindError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const { data: allChannels = [] } = useSlackChannelsQuery(teamId);
  const { data: bindings = [] } = useChannelBindingsQuery(workspaceId);
  const bindMutation = useBindChannelMutation(workspaceId);
  const unbindMutation = useUnbindChannelMutation(workspaceId);

  // IDs of channels already bound — used to split allChannels into list vs picker.
  const boundIds = new Set(bindings.map((b) => b.slack_channel_id));
  // Lookup map for binding details (is_member, channel_name, etc.)
  const bindingByChannelId = new Map(bindings.map((b) => [b.slack_channel_id, b]));
  // HOTFIX 2026-04-26: split for the new "list = bound only, picker = unbound only" UX.
  const boundChannels = allChannels.filter((c) => boundIds.has(c.id));
  const unboundChannels = allChannels.filter((c) => !boundIds.has(c.id));

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

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
      {/* Empty state — no channels in the Slack team at all */}
      {allChannels.length === 0 && (
        <div data-testid="channel-empty-state" className="text-slate-500 text-sm py-4 px-5">
          No channels found. Add a channel to get started.
        </div>
      )}

      {/* Empty state — channels exist but none bound yet (HOTFIX 2026-04-26) */}
      {allChannels.length > 0 && boundChannels.length === 0 && (
        <div
          data-testid="channel-no-bindings-state"
          className="text-slate-500 text-sm py-4 px-5"
        >
          No channels bound yet. Click <span className="text-brand-500 font-semibold">+ Add channel</span> below to bind one.
        </div>
      )}

      {/* Divider list — BOUND channels only (HOTFIX 2026-04-26) */}
      {boundChannels.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {boundChannels.map((channel) => {
            const binding = bindingByChannelId.get(channel.id);

            return (
              <li
                key={channel.id}
                className="flex items-center justify-between px-5 py-3"
              >
                {/* Channel name + status */}
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-sm text-slate-900">#{channel.name}</span>
                  {/* Active/Pending status for bound channels */}
                  {binding && (
                    binding.is_member ? (
                      <div
                        data-testid={`channel-status-${channel.id}`}
                        className="bg-emerald-100 text-emerald-700 text-xs px-2 py-0.5 rounded"
                      >
                        Active
                      </div>
                    ) : (
                      <div
                        data-testid={`channel-status-${channel.id}`}
                        className="bg-amber-100 text-amber-700 text-xs px-2 py-0.5 rounded"
                      >
                        Pending
                      </div>
                    )
                  )}
                  {/* /invite snippet for pending channels */}
                  {binding && !binding.is_member && (
                    <code
                      data-testid={`invite-snippet-${channel.id}`}
                      className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono"
                    >
                      /invite @tee-mo
                    </code>
                  )}
                </div>

                {/* Right side: unbind confirm or unbind button */}
                <div className="flex items-center gap-2 shrink-0">
                  {confirmingUnbind === channel.id && (
                    <div
                      data-testid={`unbind-confirm-${channel.id}`}
                      className="flex items-center gap-2 text-sm"
                    >
                      <span className="text-slate-600">Remove this channel?</span>
                      <button
                        data-testid={`unbind-confirm-btn-${channel.id}`}
                        onClick={() => handleConfirmUnbind(channel.id)}
                        className="text-brand-500 font-semibold text-xs"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setConfirmingUnbind(null)}
                        className="text-slate-400 text-xs"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  <button
                    data-testid={`unbind-button-${channel.id}`}
                    onClick={() => setConfirmingUnbind(channel.id)}
                    className="text-xs font-medium text-slate-600 border border-slate-200 bg-white rounded-md px-3 py-1.5 hover:bg-slate-50"
                    aria-label={`Unbind ${channel.name}`}
                  >
                    Unbind
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {/* 409 conflict error — shown when bind fails with "already bound" detail */}
      {bindMutation.isError && (
        <div
          data-testid="channel-bind-error"
          className="text-sm text-red-600 mt-2 px-5"
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
          className="text-sm text-red-600 mt-2 px-5"
        >
          {bindError}
        </div>
      )}

      {/* Add channel button */}
      <div className="px-5 py-3 border-t border-slate-100">
        <button
          data-testid="add-channel-button"
          onClick={() => {
            setBindError(null);
            setPickerOpen(true);
          }}
          className="text-sm text-brand-500 font-semibold"
        >
          + Add channel
        </button>
      </div>

      {/* Channel picker — UNBOUND channels only (HOTFIX 2026-04-26) */}
      {pickerOpen && (
        <div
          data-testid="channel-picker"
          className="mx-5 mb-3 border border-slate-200 rounded-lg bg-white shadow-sm p-3"
        >
          {unboundChannels.length === 0 ? (
            <p className="text-slate-500 text-sm" data-testid="channel-picker-empty">
              {allChannels.length === 0
                ? 'No channels found in this Slack team.'
                : 'All channels are already bound.'}
            </p>
          ) : (
            <>
              {/* CR-001: search input + count badge */}
              <input
                type="text"
                placeholder="Search channels…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full mb-2 px-3 py-1.5 border border-slate-200 rounded-md text-sm"
                data-testid="channel-search-input"
              />
              {(() => {
                const matched = unboundChannels.filter((ch) =>
                  ch.name.toLowerCase().includes(query.trim().toLowerCase()),
                );
                return (
                  <>
                    <div
                      className="text-xs text-slate-500 mb-1"
                      data-testid="channel-count-badge"
                    >
                      {query.trim()
                        ? `${matched.length} of ${unboundChannels.length} channels`
                        : `${unboundChannels.length} channels`}
                    </div>
                    {matched.length === 0 && (
                      <p className="text-slate-500 text-sm" data-testid="channel-search-empty">
                        No channels match &quot;{query}&quot;
                      </p>
                    )}
                    <ul>
                      {matched.map((channel) => {
                        const isBoundElsewhere =
                          !!channel.bound_workspace_id &&
                          channel.bound_workspace_id !== workspaceId;
                        return (
                          <li key={channel.id}>
                            {isBoundElsewhere ? (
                              <div
                                className="w-full text-left py-1 px-2 text-sm rounded flex items-center gap-2 opacity-50 cursor-not-allowed"
                              >
                                <span className="h-2 w-2 rounded-full bg-rose-400 shrink-0" />
                                <span className="text-slate-400">#{channel.name}</span>
                                <span className="text-xs text-slate-400 ml-auto">
                                  other workspace
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
                  </>
                );
              })()}
            </>
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
