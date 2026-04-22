/**
 * useWorkspaces.ts — TanStack Query hooks for workspace CRUD operations.
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern established in Sprint 1 (FLASHCARDS.md:
 * "All frontend fetches go through TanStack Query").
 *
 * Query key conventions:
 *   ['slack-teams']           — all Slack teams for the current user
 *   ['workspaces', teamId]    — all workspaces under a given Slack team
 *   ['workspace', id]         — a single workspace by UUID
 *
 * Mutations invalidate the relevant list queries on success so UI stays fresh
 * without manual cache management at the component level.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createWorkspace,
  getWorkspace,
  listSlackTeams,
  listWorkspaces,
  makeWorkspaceDefault,
  updateWorkspace,
  SlackTeam,
  Workspace,
} from '../lib/api';

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

/**
 * Fetches the list of Slack teams where Tee-Mo is installed for the current user.
 *
 * Maps the `SlackTeamsResponse` envelope to the `teams` array so consumers
 * work directly with `SlackTeam[]` rather than unwrapping the response shape.
 *
 * @returns TanStack Query result with `data: SlackTeam[]`.
 */
export function useSlackTeamsQuery() {
  return useQuery<SlackTeam[]>({
    queryKey: ['slack-teams'],
    queryFn: async () => {
      const response = await listSlackTeams();
      return response.teams;
    },
  });
}

/**
 * Fetches all workspaces belonging to the given Slack team.
 *
 * The query is disabled when `teamId` is an empty string to prevent
 * spurious requests before a team is selected.
 *
 * @param teamId - Slack team ID to load workspaces for.
 * @returns TanStack Query result with `data: Workspace[]`.
 */
export function useWorkspacesQuery(teamId: string) {
  return useQuery<Workspace[]>({
    queryKey: ['workspaces', teamId],
    queryFn: () => listWorkspaces(teamId),
    enabled: !!teamId,
  });
}

/**
 * Fetches a single workspace by its UUID.
 *
 * The query is disabled when `id` is an empty string.
 *
 * @param id - Workspace UUID.
 * @returns TanStack Query result with `data: Workspace`.
 */
export function useWorkspaceQuery(id: string) {
  return useQuery<Workspace>({
    queryKey: ['workspace', id],
    queryFn: () => getWorkspace(id),
    enabled: !!id,
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

/**
 * Creates a new workspace under the given Slack team.
 *
 * On success, invalidates the `['workspaces', teamId]` query so the new
 * workspace appears in any list views without a manual refetch.
 *
 * @param teamId - Slack team ID the new workspace will belong to.
 * @returns TanStack Mutation object. Call `.mutate(name)` to create a workspace.
 */
export function useCreateWorkspaceMutation(teamId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name: string) => createWorkspace(teamId, name),
    onSuccess: () => {
      // Invalidate the list so the new workspace shows up
      queryClient.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}

/**
 * Updates a workspace (name and/or persona).
 *
 * On success:
 *   1. Updates the individual `['workspace', id]` cache entry directly.
 *   2. Invalidates the `['workspaces', teamId]` list so the updates
 *      propagate to any workspace list views.
 *
 * @returns TanStack Mutation object. Call `.mutate({ id, name, bot_persona })` to update.
 */
export function useUpdateWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      name,
      bot_persona,
    }: {
      id: string;
      name: string;
      bot_persona?: string | null;
    }) => updateWorkspace(id, { name, bot_persona }),
    onSuccess: (updatedWorkspace) => {
      // Update individual workspace cache if present
      queryClient.setQueryData(['workspace', updatedWorkspace.id], updatedWorkspace);

      // Invalidate the list for the team it belongs to, so UI gets fresh names
      if (updatedWorkspace.slack_team_id) {
        queryClient.invalidateQueries({
          queryKey: ['workspaces', updatedWorkspace.slack_team_id],
        });
      }
    },
  });
}

/**
 * Legacy wrapper for renaming a workspace.
 *
 * @returns TanStack Mutation object. Call `.mutate({ id, name })` to rename.
 */
export function useRenameWorkspaceMutation() {
  const updateMutation = useUpdateWorkspaceMutation();

  return {
    ...updateMutation,
    mutate: ({ id, name }: { id: string; name: string }) =>
      updateMutation.mutate({ id, name }),
    mutateAsync: ({ id, name }: { id: string; name: string }) =>
      updateMutation.mutateAsync({ id, name }),
  };
}

/**
 * Promotes a workspace as the default for its Slack team.
 *
 * When `teamId` is provided (recommended), uses TanStack Query optimistic updates
 * for instant UI feedback:
 *   - `onMutate`: snapshots the current workspace list and immediately flips
 *     `is_default_for_team` flags so only the targeted workspace shows as default.
 *   - `onError`: rolls back to the snapshot if the server call fails.
 *   - `onSettled`: invalidates `['workspaces', teamId]` to sync with the server.
 *
 * When `teamId` is omitted (legacy / test usage), falls back to the original
 * `onSuccess` behaviour: reads `slack_team_id` from the server response and
 * invalidates the list for that team. No optimistic update is applied.
 *
 * @param teamId - Slack team ID whose workspace list will be optimistically updated.
 *   Pass a non-empty string to enable optimistic UI. Omit (or pass `''`) for the
 *   non-optimistic fallback path used by unit tests and legacy call sites.
 * @returns TanStack Mutation object. Call `.mutate(id)` to make a workspace default.
 */
export function useMakeDefaultMutation(teamId?: string) {
  const queryClient = useQueryClient();

  // Whether to engage the optimistic update path.
  const optimistic = !!teamId;

  return useMutation({
    mutationFn: (id: string) => makeWorkspaceDefault(id),

    /**
     * Optimistically update the workspace list before the server responds.
     * Only runs when `teamId` is provided. Returns a rollback snapshot.
     */
    onMutate: optimistic
      ? async (id: string) => {
          // Cancel any in-flight refetches so they don't overwrite the optimistic update.
          await queryClient.cancelQueries({ queryKey: ['workspaces', teamId] });

          // Snapshot the current list for rollback on error.
          const previous = queryClient.getQueryData<Workspace[]>(['workspaces', teamId]);

          // Flip is_default_for_team: only the targeted workspace is default.
          queryClient.setQueryData<Workspace[]>(['workspaces', teamId], (old) =>
            old?.map((ws) => ({ ...ws, is_default_for_team: ws.id === id }))
          );

          return { previous };
        }
      : undefined,

    /**
     * On error, roll back the optimistic update using the snapshot from onMutate.
     * Only active in the optimistic path.
     */
    onError: optimistic
      ? (
          _err: unknown,
          _id: string,
          context: { previous: Workspace[] | undefined } | undefined
        ) => {
          if (context?.previous !== undefined) {
            queryClient.setQueryData(['workspaces', teamId], context.previous);
          }
        }
      : undefined,

    /**
     * On settle (success or error): invalidate the list query to sync with the server.
     * - Optimistic path: invalidates `['workspaces', teamId]`.
     * - Legacy path: reads `slack_team_id` from the resolved value and invalidates
     *   that team's list (mirrors the original B04 behaviour, keeps existing tests green).
     */
    onSettled: optimistic
      ? () => {
          queryClient.invalidateQueries({ queryKey: ['workspaces', teamId] });
        }
      : undefined,

    /**
     * Legacy (non-optimistic) success handler.
     * Updates the individual workspace cache entry and invalidates the team's list
     * using `slack_team_id` from the server response. Only active when `teamId`
     * is not provided.
     */
    onSuccess: optimistic
      ? undefined
      : (updatedWorkspace: Workspace) => {
          queryClient.setQueryData(['workspace', updatedWorkspace.id], updatedWorkspace);
          if (updatedWorkspace.slack_team_id) {
            queryClient.invalidateQueries({
              queryKey: ['workspaces', updatedWorkspace.slack_team_id],
            });
          }
        },
  });
}
