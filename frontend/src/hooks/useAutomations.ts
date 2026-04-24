/**
 * useAutomations.ts — TanStack Query hooks for workspace automations (STORY-018-05).
 *
 * All data fetching goes through typed wrappers in `../lib/api` per the
 * frontend data-fetching pattern (FLASHCARD 2026-04-11 #frontend #recipe:
 * "All frontend fetches go through TanStack Query — no raw fetch()").
 *
 * Query key conventions:
 *   ['automations', workspaceId]                     — list of automations
 *   ['automationHistory', workspaceId, automationId] — execution history
 *
 * All mutations that change automation state invalidate `['automations', workspaceId]`
 * on success so the list refreshes automatically.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  listAutomations,
  createAutomation,
  updateAutomation,
  deleteAutomation,
  getAutomationHistory,
  testRunAutomation,
  type AutomationCreate,
  type AutomationUpdate,
} from '../lib/api';

// ---------------------------------------------------------------------------
// Query key factories
// ---------------------------------------------------------------------------

/**
 * Returns the stable TanStack Query key for the automations list of a workspace.
 * All mutations that modify automations invalidate this key on success.
 *
 * @param workspaceId - UUID of the workspace.
 */
export function automationsKey(workspaceId: string) {
  return ['automations', workspaceId] as const;
}

/**
 * Returns the stable TanStack Query key for the execution history of a specific
 * automation. History is keyed by both workspace and automation IDs so caches
 * for different automations don't collide.
 *
 * @param workspaceId  - UUID of the workspace that owns the automation.
 * @param automationId - UUID of the automation.
 */
export function automationHistoryKey(workspaceId: string, automationId: string) {
  return ['automationHistory', workspaceId, automationId] as const;
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

/**
 * Fetches all automations for a workspace.
 *
 * Disabled when `workspaceId` is empty to prevent spurious API calls
 * before a workspace is selected.
 *
 * @param workspaceId - UUID of the workspace to list automations for.
 * @returns TanStack Query result with `data: Automation[]`.
 */
export function useAutomationsQuery(workspaceId: string) {
  return useQuery({
    queryKey: automationsKey(workspaceId),
    queryFn: () => listAutomations(workspaceId),
    enabled: workspaceId !== '',
  });
}

/**
 * Fetches the execution history for a specific automation, newest first.
 *
 * Disabled when either `workspaceId` or `automationId` is empty/null.
 * This means the drawer can safely pass `automationId | null` and the
 * query will not fire until a real automation is selected.
 *
 * @param workspaceId  - UUID of the workspace.
 * @param automationId - UUID of the automation whose history to fetch, or null.
 * @returns TanStack Query result with `data: AutomationExecution[]`.
 */
export function useAutomationHistoryQuery(
  workspaceId: string,
  automationId: string | null,
) {
  return useQuery({
    queryKey: automationHistoryKey(workspaceId, automationId ?? ''),
    queryFn: () => getAutomationHistory(workspaceId, automationId!),
    enabled: workspaceId !== '' && automationId !== null && automationId !== '',
  });
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

/**
 * Mutation: create a new automation in a workspace.
 *
 * On success, invalidates `['automations', workspaceId]` so the list refreshes.
 * HTTP 409 (duplicate name) is propagated via the mutation's `error` state.
 *
 * @param workspaceId - UUID of the workspace to create the automation in.
 * @returns TanStack Mutation object. Call `.mutate(automationCreate)`.
 */
export function useCreateAutomationMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: AutomationCreate) => createAutomation(workspaceId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: automationsKey(workspaceId) });
    },
  });
}

/**
 * Mutation: partially update an existing automation (toggle, rename, reschedule).
 *
 * On success, invalidates `['automations', workspaceId]` so the list refreshes
 * and the updated automation card re-renders with the new state.
 *
 * @param workspaceId - UUID of the workspace that owns the automation.
 * @returns TanStack Mutation object. Call `.mutate({ automationId, ...patch })`.
 */
export function useUpdateAutomationMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      automationId,
      ...body
    }: AutomationUpdate & { automationId: string }) =>
      updateAutomation(workspaceId, automationId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: automationsKey(workspaceId) });
    },
  });
}

/**
 * Mutation: permanently delete an automation.
 *
 * On success, invalidates `['automations', workspaceId]` so the card disappears
 * from the list immediately.
 *
 * @param workspaceId - UUID of the workspace that owns the automation.
 * @returns TanStack Mutation object. Call `.mutate(automationId)`.
 */
export function useDeleteAutomationMutation(workspaceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (automationId: string) => deleteAutomation(workspaceId, automationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: automationsKey(workspaceId) });
    },
  });
}

/**
 * Mutation: fire a test-run (dry-run preview) for a prompt.
 *
 * Maps to POST /api/workspaces/{id}/automations/test-run (FLASHCARD 2026-04-24
 * #frontend #epic-018 — NOT /{aid}/dry-run).
 *
 * Does NOT invalidate any cache — test-runs are ephemeral and do not affect
 * the automation list or history.
 *
 * @param workspaceId - UUID of the workspace to run the test against.
 * @returns TanStack Mutation object. Call `.mutate({ prompt, timezone?, description? })`.
 */
export function useTestRunMutation(workspaceId: string) {
  return useMutation({
    mutationFn: (body: { prompt: string; timezone?: string; description?: string }) =>
      testRunAutomation(workspaceId, body),
  });
}
