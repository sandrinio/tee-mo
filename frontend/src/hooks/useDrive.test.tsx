/**
 * useDrive.test.tsx — Unit tests for TanStack Query Drive hooks (STORY-006-05).
 *
 * Uses vi.mock (hoisted by Vitest AST) to stub api module functions.
 * Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *
 * FLASHCARDS.md: Vitest 2.x vi.mock hoisting TDZ — mock variables inside the
 * factory must be declared via vi.hoisted() to avoid ReferenceError. Here all
 * mocked functions are created as vi.fn() directly in the factory (no closures
 * over external variables) so no vi.hoisted() is needed.
 *
 * Covers STORY-006-05 acceptance criteria (§2):
 *   1. useDriveStatusQuery returns drive status data
 *   2. useDriveStatusQuery is disabled when workspaceId is empty
 *   3. useDisconnectDriveMutation invalidates drive-status cache on success
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// vi.mock is hoisted above all imports by Vitest's AST transform.
vi.mock('../lib/api', () => ({
  getDriveStatus: vi.fn(),
  disconnectDrive: vi.fn(),
}));

import * as api from '../lib/api';
import { useDriveStatusQuery, useDisconnectDriveMutation } from './useDrive';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Creates a fresh React QueryClientProvider wrapper per test. */
function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useDriveStatusQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns drive status data when Drive is connected', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const mockStatus = { connected: true, email: 'user@example.com' };
    vi.mocked(api.getDriveStatus).mockResolvedValueOnce(mockStatus);

    const { result } = renderHook(() => useDriveStatusQuery('ws-1'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockStatus);
    expect(api.getDriveStatus).toHaveBeenCalledWith('ws-1');
  });

  it('returns connected: false when Drive is not connected', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const mockStatus = { connected: false, email: null };
    vi.mocked(api.getDriveStatus).mockResolvedValueOnce(mockStatus);

    const { result } = renderHook(() => useDriveStatusQuery('ws-2'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.connected).toBe(false);
    expect(result.current.data?.email).toBeNull();
  });

  it('is disabled when workspaceId is empty', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const { result } = renderHook(() => useDriveStatusQuery(''), { wrapper });

    // Query must not fire — fetchStatus stays idle
    expect(result.current.fetchStatus).toBe('idle');
    expect(api.getDriveStatus).not.toHaveBeenCalled();
  });
});

describe('useDisconnectDriveMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates drive-status cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.disconnectDrive).mockResolvedValueOnce({ status: 'ok' });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useDisconnectDriveMutation('ws-1'), { wrapper });

    result.current.mutate();

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Drive-status cache for this workspace must be invalidated
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['drive-status', 'ws-1'],
    });
  });
});
