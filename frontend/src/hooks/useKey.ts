/**
 * useKey.ts — TanStack Query hooks for BYOK key management (STORY-004-03).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern established in Sprint 1 (FLASHCARDS.md:
 * "All frontend fetches go through TanStack Query").
 *
 * Query key conventions:
 *   ['keys', workspaceId]  — key status for a specific workspace
 *
 * Mutations invalidate both the key cache and the parent workspace list cache
 * so that any provider badge in the workspace list stays in sync without
 * manual cache management at the component level.
 *
 * ADR-002 hard rule: the plaintext key is NEVER exposed in responses or logs.
 * These hooks only surface `ProviderKey` (has_key / key_mask / provider / ai_model).
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { deleteWorkspaceKey, getKey, saveKey, type SaveKeyRequest } from '../lib/api';

// -----------------------------------------------------------------------------
// Query key factory
// -----------------------------------------------------------------------------

/**
 * Centralized query key factory for key-related cache entries.
 * Keeps cache invalidation consistent across hooks and components.
 */
export const keyKeys = {
  /** All key cache entries — use for broad invalidation. */
  all: ['keys'] as const,
  /** Cache key for a specific workspace's key status. */
  byWorkspace: (workspaceId: string) => ['keys', workspaceId] as const,
};

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

/**
 * Fetches the key status for a workspace.
 *
 * Returns `{has_key, provider, key_mask, ai_model}` — the plaintext key is
 * never returned by the backend (ADR-002).
 *
 * The query is disabled when `workspaceId` is an empty string to prevent
 * spurious requests before a workspace is selected.
 *
 * @param workspaceId - UUID of the workspace to fetch key status for.
 * @returns TanStack Query result with `data: ProviderKey`.
 */
export function useKeyQuery(workspaceId: string) {
  return useQuery({
    queryKey: keyKeys.byWorkspace(workspaceId),
    queryFn: () => getKey(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

/**
 * Mutation: encrypt and store a BYOK key for a workspace.
 *
 * On success, invalidates:
 *   1. `['keys', workspaceId]` — so the key status display refreshes.
 *   2. `['workspaces', teamId]` — so provider badges in the workspace list update.
 *
 * @param teamId - Slack team ID whose workspace list cache is also invalidated on success.
 * @returns TanStack Mutation object. Call `.mutate({ workspaceId, provider, key, ai_model })`.
 */
export function useSaveKeyMutation(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, ...body }: { workspaceId: string } & SaveKeyRequest) =>
      saveKey(workspaceId, body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: keyKeys.byWorkspace(variables.workspaceId) });
      // Invalidate workspace list so provider badge updates in WorkspaceCard
      qc.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}

/**
 * Mutation: delete the BYOK key for a workspace.
 *
 * On success, invalidates:
 *   1. `['keys', workspaceId]` — so the key status display clears.
 *   2. `['workspaces', teamId]` — so provider badges in the workspace list clear.
 *
 * @param teamId - Slack team ID whose workspace list cache is also invalidated on success.
 * @returns TanStack Mutation object. Call `.mutate(workspaceId)`.
 */
export function useDeleteKeyMutation(teamId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (workspaceId: string) => deleteWorkspaceKey(workspaceId),
    onSuccess: (_data, workspaceId) => {
      qc.invalidateQueries({ queryKey: keyKeys.byWorkspace(workspaceId) });
      qc.invalidateQueries({ queryKey: ['workspaces', teamId] });
    },
  });
}
