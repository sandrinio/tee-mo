/**
 * useKey.test.tsx — Unit tests for TanStack Query BYOK key hooks.
 *
 * Uses vi.mock (hoisted by Vitest AST) to stub api module functions.
 * Mock variables that are referenced inside the vi.mock factory use vi.hoisted()
 * to avoid TDZ errors (FLASHCARDS.md: "Vitest 2.x vi.mock hoisting TDZ").
 *
 * Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *
 * Covers STORY-004-03 acceptance criteria (§2):
 *   1. useKeyQuery returns data when key exists
 *   2. useKeyQuery returns has_key false when no key configured
 *   3. useSaveKeyMutation invalidates key cache on success
 *   4. useDeleteKeyMutation invalidates key cache on success
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

// vi.mock is hoisted by Vitest's AST transform — the factory runs before any
// import statements. Variables referenced inside the factory must be declared
// via vi.hoisted() to avoid TDZ errors.
vi.mock('../lib/api', () => ({
  getKey: vi.fn(),
  saveKey: vi.fn(),
  deleteWorkspaceKey: vi.fn(),
  validateKey: vi.fn(),
}));

import { beforeEach } from 'vitest';
import * as api from '../lib/api';
import { keyKeys, useDeleteKeyMutation, useKeyQuery, useSaveKeyMutation } from './useKey';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Creates a fresh QueryClient per test to prevent cross-test cache pollution. */
function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useKeyQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns data when key exists', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const mockKey = {
      has_key: true,
      provider: 'openai',
      key_mask: 'sk-a...xyz9',
      ai_model: 'gpt-4o',
    };
    vi.mocked(api.getKey).mockResolvedValueOnce(mockKey);

    const { result } = renderHook(() => useKeyQuery('W1'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockKey);
    expect(api.getKey).toHaveBeenCalledWith('W1');
  });

  it('returns has_key false when no key configured', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const mockKey = {
      has_key: false,
      provider: null,
      key_mask: null,
      ai_model: null,
    };
    vi.mocked(api.getKey).mockResolvedValueOnce(mockKey);

    const { result } = renderHook(() => useKeyQuery('W2'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.has_key).toBe(false);
    expect(result.current.data?.provider).toBeNull();
    expect(api.getKey).toHaveBeenCalledWith('W2');
  });

  it('is disabled when workspaceId is empty', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const { result } = renderHook(() => useKeyQuery(''), { wrapper });

    // Query should not fire — status remains 'pending' with fetchStatus 'idle'
    expect(result.current.fetchStatus).toBe('idle');
    expect(api.getKey).not.toHaveBeenCalled();
  });
});

describe('useSaveKeyMutation', () => {
  it('invalidates key cache and workspace cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const mockKey = {
      has_key: true,
      provider: 'openai' as const,
      key_mask: 'sk-a...xyz9',
      ai_model: 'gpt-4o',
    };
    vi.mocked(api.saveKey).mockResolvedValueOnce(mockKey);

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useSaveKeyMutation('T1'), { wrapper });

    result.current.mutate({
      workspaceId: 'W1',
      provider: 'openai',
      key: 'sk-valid-key',
      ai_model: 'gpt-4o',
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Key cache for this workspace must be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: keyKeys.byWorkspace('W1'),
    });

    // Workspace list cache for the parent team must also be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['workspaces', 'T1'],
    });
  });
});

describe('useDeleteKeyMutation', () => {
  it('invalidates key cache and workspace cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.deleteWorkspaceKey).mockResolvedValueOnce({ message: 'Key deleted' });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteKeyMutation('T1'), { wrapper });

    result.current.mutate('W1');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Key cache for this workspace must be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: keyKeys.byWorkspace('W1'),
    });

    // Workspace list cache for the parent team must also be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['workspaces', 'T1'],
    });
  });
});
