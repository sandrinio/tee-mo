/**
 * useSkills.ts — TanStack Query hook for the workspace skill catalog (STORY-023-01).
 *
 * Exposes useSkillsQuery which fetches GET /api/workspaces/{id}/skills.
 * Skills are read-only in the dashboard (chat-only CRUD, ADR-023).
 *
 * Query key: ['skills', workspaceId]
 * Stale time: 60 s — skills change infrequently (only via Slack chat).
 */
import { useQuery } from '@tanstack/react-query';
import { listWorkspaceSkills, type Skill } from '../lib/api';

/**
 * Fetch the active skill catalog for a workspace.
 *
 * @param workspaceId - UUID of the workspace. Must be a non-empty string.
 * @returns TanStack Query result with `data: Skill[] | undefined`.
 */
export function useSkillsQuery(workspaceId: string) {
  return useQuery<Skill[]>({
    queryKey: ['skills', workspaceId],
    queryFn: () => listWorkspaceSkills(workspaceId),
    enabled: Boolean(workspaceId),
    staleTime: 60_000,
  });
}
