/**
 * useChannels.ts — TanStack Query hooks for Slack channel binding (STORY-008-02).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern established in Sprint 1 (FLASHCARDS.md:
 * "All frontend fetches go through TanStack Query").
 *
 * Query key conventions:
 *   ['slack-channels', teamId]      — Slack channels for a team
 *   ['channel-bindings', workspaceId] — channel bindings for a workspace
 *
 * Mutations invalidate the channel-bindings cache on success so the UI
 * refreshes automatically without manual cache management at the call site.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  bindChannel,
  listChannelBindings,
  listSlackTeamChannels,
  unbindChannel,
} from '../lib/api';

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetches all Slack channels available in a team.
 *
 * Disabled when `teamId` is an empty string to prevent spurious API calls
 * before a team is selected. Enable condition: `teamId !== ''`.
 *
 * @param teamId - The Slack team ID to list channels for.
 * @returns TanStack Query result with `data: SlackChannel[]`.
 */
export function useSlackChannelsQuery(teamId: string) {
  return useQuery({
    queryKey: ['slack-channels', teamId],
    queryFn: () => listSlackTeamChannels(teamId),
    enabled: teamId !== '',
  });
}

/**
 * Fetches all channel bindings for a workspace (enriched with is_member + channel_name).
 *
 * Disabled when `workspaceId` is an empty string to prevent spurious API calls
 * before a workspace is selected. Enable condition: `workspaceId !== ''`.
 *
 * @param workspaceId - UUID of the workspace to fetch channel bindings for.
 * @returns TanStack Query result with `data: ChannelBinding[]`.
 */
export function useChannelBindingsQuery(workspaceId: string) {
  return useQuery({
    queryKey: ['channel-bindings', workspaceId],
    queryFn: () => listChannelBindings(workspaceId),
    enabled: workspaceId !== '',
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Mutation: bind a Slack channel to a workspace.
 *
 * On success, invalidates `['channel-bindings', workspaceId]` so the
 * channel list refreshes and the new binding appears with is_member status.
 *
 * The 409 conflict error (channel already bound to another workspace) is
 * propagated via the mutation's `error` state — the component can render it
 * inline without additional fetch calls.
 *
 * @param workspaceId - UUID of the workspace to bind channels to.
 * @returns TanStack Mutation object. Call `.mutate({ channelId })`.
 */
export function useBindChannelMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ channelId }: { channelId: string }) =>
      bindChannel(workspaceId, channelId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channel-bindings', workspaceId] });
    },
  });
}

/**
 * Mutation: unbind a Slack channel from a workspace.
 *
 * On success, invalidates `['channel-bindings', workspaceId]` so the
 * channel list refreshes and the removed binding disappears.
 *
 * @param workspaceId - UUID of the workspace to unbind channels from.
 * @returns TanStack Mutation object. Call `.mutate({ channelId })`.
 */
export function useUnbindChannelMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ channelId }: { channelId: string }) =>
      unbindChannel(workspaceId, channelId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['channel-bindings', workspaceId] });
    },
  });
}
