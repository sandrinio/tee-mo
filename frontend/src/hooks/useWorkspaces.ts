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
  renameWorkspace,
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
 * Renames an existing workspace.
 *
 * On success:
 *   1. Updates the individual `['workspace', id]` cache entry directly.
 *   2. Invalidates the `['workspaces', teamId]` list so the new name
 *      propagates to any workspace list views.
 *
 * @returns TanStack Mutation object. Call `.mutate({ id, name })` to rename.
 */
export function useRenameWorkspaceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => renameWorkspace(id, name),
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
 * Promotes a workspace as the default for its Slack team.
 *
 * On success:
 *   1. Updates the individual `['workspace', id]` cache entry directly.
 *   2. Invalidates the `['workspaces', teamId]` list so the "Default" badge
 *      moves correctly across all workspace cards without a manual refetch.
 *
 * @returns TanStack Mutation object. Call `.mutate(id)` to make a workspace default.
 */
export function useMakeDefaultMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => makeWorkspaceDefault(id),
    onSuccess: (updatedWorkspace) => {
      queryClient.setQueryData(['workspace', updatedWorkspace.id], updatedWorkspace);
      if (updatedWorkspace.slack_team_id) {
        // Force refresh the list so the "Default" badge moves correctly
        queryClient.invalidateQueries({
          queryKey: ['workspaces', updatedWorkspace.slack_team_id],
        });
      }
    },
  });
}
