/**
 * useKnowledge.ts — TanStack Query hooks for knowledge file management (STORY-006-05).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern established in Sprint 1 (FLASHCARDS.md:
 * "All frontend fetches go through TanStack Query").
 *
 * Query key conventions:
 *   ['knowledge', workspaceId]  — all indexed knowledge files for a workspace
 *
 * Mutations invalidate the knowledge list cache on success so the UI stays
 * fresh after add/remove operations without manual cache management at the
 * component level.
 *
 * Performance note: `indexKnowledgeFile` is a long-running operation (the
 * backend fetches Drive content and generates an AI description). The caller
 * should show a loading state while `useAddKnowledgeMutation.isPending` is true.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listKnowledgeFiles,
  indexKnowledgeFile,
  removeKnowledgeFile,
  reindexKnowledge,
  type IndexFileRequest,
} from '../lib/api';

// -----------------------------------------------------------------------------
// Queries
// -----------------------------------------------------------------------------

/**
 * Fetches all indexed knowledge files for a workspace.
 *
 * The query is disabled when `workspaceId` is empty to prevent spurious
 * requests before the route params are resolved.
 *
 * @param workspaceId - UUID of the workspace whose knowledge files to list.
 * @returns TanStack Query result with `data: KnowledgeFile[]`.
 */
export function useKnowledgeQuery(workspaceId: string) {
  return useQuery({
    queryKey: ['knowledge', workspaceId],
    queryFn: () => listKnowledgeFiles(workspaceId),
    enabled: !!workspaceId,
  });
}

// -----------------------------------------------------------------------------
// Mutations
// -----------------------------------------------------------------------------

/**
 * Indexes a Google Drive file into the workspace knowledge base.
 *
 * This mutation calls the backend which: fetches the file content from Drive,
 * generates an AI description, and stores the result. It can take several
 * seconds — show `isPending` state while waiting.
 *
 * On success:
 *   - Invalidates `['knowledge', workspaceId]` so the file list refreshes.
 *
 * If the response includes a `warning` field, the caller is responsible for
 * displaying a truncation notice to the user (R8: file >50K chars warning).
 *
 * @param workspaceId - UUID of the workspace to index the file into.
 * @returns TanStack Mutation object. Call `.mutate(body)` with IndexFileRequest.
 */
export function useAddKnowledgeMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: IndexFileRequest) => indexKnowledgeFile(workspaceId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge', workspaceId] });
    },
  });
}

/**
 * Removes an indexed knowledge file from the workspace knowledge base.
 *
 * On success, invalidates `['knowledge', workspaceId]` so the file list
 * immediately reflects the deletion without a manual refetch.
 *
 * @param workspaceId - UUID of the workspace the file belongs to.
 * @returns TanStack Mutation object. Call `.mutate(knowledgeId)` with the file UUID.
 */
export function useRemoveKnowledgeMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (knowledgeId: string) => removeKnowledgeFile(workspaceId, knowledgeId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge', workspaceId] });
    },
  });
}

/**
 * Re-indexes all knowledge files for a workspace.
 *
 * Calls POST /api/workspaces/{workspaceId}/knowledge/reindex which re-fetches
 * every indexed file from Google Drive, recomputes its content hash, regenerates
 * its AI description, and updates ``cached_content`` / ``last_scanned_at``.
 *
 * This is a potentially long-running operation (depends on file count and AI latency).
 * Show `isPending` state to the user while waiting.
 *
 * On success:
 *   - Invalidates `['knowledge', workspaceId]` so the file list refreshes with
 *     updated AI descriptions and timestamps.
 *
 * Requires both a BYOK key and Google Drive to be connected — the mutation will
 * error (400) if either precondition is missing.
 *
 * @param workspaceId - UUID of the workspace whose files to re-index.
 * @returns TanStack Mutation object. Call `.mutate()` (no arguments).
 */
export function useReindexKnowledgeMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => reindexKnowledge(workspaceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge', workspaceId] });
    },
  });
}
