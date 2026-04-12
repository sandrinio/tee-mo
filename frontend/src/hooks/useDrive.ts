/**
 * useDrive.ts — TanStack Query hooks for Google Drive connection management (STORY-006-05).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern established in Sprint 1 (FLASHCARDS.md:
 * "All frontend fetches go through TanStack Query").
 *
 * Query key conventions:
 *   ['drive-status', workspaceId]  — Drive connection status for a specific workspace
 *
 * Mutations invalidate the drive-status cache on success so the UI reflects
 * the new connection state without manual refetch at the component level.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getDriveStatus, disconnectDrive } from '../lib/api';

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

/**
 * Fetches the Google Drive connection status for a workspace.
 *
 * Returns `{ connected: boolean, email: string | null }`.
 * The query is disabled when `workspaceId` is empty to prevent spurious
 * requests before the route params are resolved.
 *
 * @param workspaceId - UUID of the workspace to check Drive status for.
 * @returns TanStack Query result with `data: DriveStatus`.
 */
export function useDriveStatusQuery(workspaceId: string) {
  return useQuery({
    queryKey: ['drive-status', workspaceId],
    queryFn: () => getDriveStatus(workspaceId),
    enabled: !!workspaceId,
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

/**
 * Disconnects Google Drive for a workspace.
 *
 * On success, invalidates the `['drive-status', workspaceId]` query so the
 * Drive section in the workspace detail page reflects the disconnected state.
 *
 * @param workspaceId - UUID of the workspace whose Drive connection to revoke.
 * @returns TanStack Mutation object. Call `.mutate()` to disconnect.
 */
export function useDisconnectDriveMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => disconnectDrive(workspaceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['drive-status', workspaceId] });
    },
  });
}
