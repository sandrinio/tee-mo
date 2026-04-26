/**
 * useMcpServers.ts — TanStack Query hooks for MCP server management (STORY-012-04).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching convention.
 *
 * Query key convention:
 *   ['mcp-servers', workspaceId]  — list of MCP servers for a workspace
 *
 * Mutations that change server state (create / update / delete) invalidate
 * the list key so the UI re-fetches the authoritative list from the backend.
 * The test mutation (useTestMcpServerMutation) does NOT invalidate — it is a
 * read-only side-effect probe that updates only local badge state in the component.
 *
 * Risk guard (W01 §cross-story risks): `/test` always returns HTTP 200;
 * the frontend must read `body.ok`, NOT the response status, to determine
 * green/red. This is enforced by `testMcpServer` in api.ts returning the
 * full McpTestResult body.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listMcpServers,
  createMcpServer,
  updateMcpServer,
  deleteMcpServer,
  testMcpServer,
  type McpServerCreate,
  type McpServerPatch,
} from '../lib/api';

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const mcpServerKeys = {
  all: ['mcp-servers'] as const,
  byWorkspace: (workspaceId: string) => ['mcp-servers', workspaceId] as const,
};

// ---------------------------------------------------------------------------
// Query
// ---------------------------------------------------------------------------

/**
 * Fetches the list of MCP servers for a workspace.
 *
 * Query key: `['mcp-servers', workspaceId]`
 * Disabled when workspaceId is empty to prevent spurious requests.
 *
 * @param workspaceId - UUID of the workspace to list MCP servers for.
 */
export function useMcpServersQuery(workspaceId: string) {
  return useQuery({
    queryKey: mcpServerKeys.byWorkspace(workspaceId),
    queryFn: () => listMcpServers(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Mutation: create a new MCP server for a workspace.
 *
 * On success, invalidates `['mcp-servers', workspaceId]` so the list re-fetches.
 *
 * @param workspaceId - UUID of the workspace to add the server to.
 */
export function useCreateMcpServerMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: McpServerCreate) => createMcpServer(workspaceId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: mcpServerKeys.byWorkspace(workspaceId) });
    },
  });
}

/**
 * Mutation: partially update an MCP server (toggle is_active, update URL/headers).
 *
 * On success, invalidates `['mcp-servers', workspaceId]` to avoid stale is_active toggles.
 * Do not optimistic-update without invalidate — the W01 blueprint explicitly calls this
 * out as a risk for stale status badges.
 *
 * @param workspaceId - UUID of the workspace that owns the server.
 */
export function useUpdateMcpServerMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, patch }: { name: string; patch: McpServerPatch }) =>
      updateMcpServer(workspaceId, name, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: mcpServerKeys.byWorkspace(workspaceId) });
    },
  });
}

/**
 * Mutation: delete an MCP server from a workspace.
 *
 * On success, invalidates `['mcp-servers', workspaceId]` so the card disappears.
 *
 * @param workspaceId - UUID of the workspace that owns the server.
 */
export function useDeleteMcpServerMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteMcpServer(workspaceId, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: mcpServerKeys.byWorkspace(workspaceId) });
    },
  });
}

/**
 * Mutation: test the connection to an MCP server.
 *
 * Does NOT invalidate the list — this is a read-only handshake probe.
 * The caller (IntegrationsSection) updates local badge state from the result.
 *
 * IMPORTANT: `/test` always returns HTTP 200. Read `result.ok`, NOT the
 * HTTP status code, to decide green/red badge state (W01 cross-story risk #6).
 *
 * @param workspaceId - UUID of the workspace that owns the server.
 */
export function useTestMcpServerMutation(workspaceId: string) {
  return useMutation({
    mutationFn: (name: string) => testMcpServer(workspaceId, name),
    // No onSuccess invalidation — test is read-only. Badge state managed locally.
  });
}
