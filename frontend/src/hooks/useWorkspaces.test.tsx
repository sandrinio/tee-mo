/**
 * useWorkspaces.test.tsx — Unit tests for TanStack Query workspace hooks.
 *
 * Uses vi.mock (hoisted by Vitest AST) to stub api module functions.
 * Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *
 * Covers STORY-003-B04 acceptance criteria:
 *   - useCreateWorkspaceMutation calls API and invalidates list on success
 *   - useMakeDefaultMutation invalidates the workspaces list for the team
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

// Pre-hoist mocks before imports
vi.mock('../lib/api', () => ({
  listSlackTeams: vi.fn(),
  listWorkspaces: vi.fn(),
  getWorkspace: vi.fn(),
  createWorkspace: vi.fn(),
  renameWorkspace: vi.fn(),
  makeWorkspaceDefault: vi.fn(),
}));

import * as api from '../lib/api';
import { useCreateWorkspaceMutation, useMakeDefaultMutation } from './useWorkspaces';

describe('useWorkspaces hooks', () => {
  it('useCreateWorkspaceMutation calls api and invalidates on success', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    // Mock API success
    const mockWorkspace = { id: 'w1', name: 'Test WS', slack_team_id: 't1' };
    vi.mocked(api.createWorkspace).mockResolvedValueOnce(mockWorkspace as any);

    // Spy on invalidateQueries
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useCreateWorkspaceMutation('t1'), { wrapper });

    // Call the mutation
    result.current.mutate('Test WS');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.createWorkspace).toHaveBeenCalledWith('t1', 'Test WS');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['workspaces', 't1'] });
  });

  it('useMakeDefaultMutation invalidates the workspaces list for the team on success', async () => {
    const queryClient = new QueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    // Mock the backend returning the updated workspace with is_default_for_team: true
    const updatedWorkspace = {
      id: 'w2',
      name: 'My Workspace',
      slack_team_id: 't1',
      owner_user_id: 'u1',
      is_default_for_team: true,
      created_at: '2026-01-01T00:00:00Z',
    };
    vi.mocked(api.makeWorkspaceDefault).mockResolvedValueOnce(updatedWorkspace as any);

    // Spy on invalidateQueries to assert the list key is invalidated
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useMakeDefaultMutation(), { wrapper });

    // Trigger the mutation with the workspace id
    result.current.mutate('w2');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.makeWorkspaceDefault).toHaveBeenCalledWith('w2');
    // The list for the team that owns this workspace must be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['workspaces', 't1'],
    });
  });
});
