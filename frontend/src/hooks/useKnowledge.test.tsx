/**
 * useKnowledge.test.tsx — Unit tests for TanStack Query knowledge hooks (STORY-006-05).
 *
 * Uses vi.mock (hoisted by Vitest AST) to stub api module functions.
 * Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *
 * FLASHCARDS.md: Vitest 2.x vi.mock hoisting TDZ — mock variables inside the
 * factory must be declared via vi.hoisted() to avoid ReferenceError. Here all
 * mocked functions are created as vi.fn() directly in the factory so no
 * vi.hoisted() is needed.
 *
 * Covers STORY-006-05 acceptance criteria (§2):
 *   1. useKnowledgeQuery returns file list
 *   2. useKnowledgeQuery is disabled when workspaceId is empty
 *   3. useAddKnowledgeMutation invalidates knowledge cache on success
 *   4. useRemoveKnowledgeMutation invalidates knowledge cache on success
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// vi.mock is hoisted above all imports by Vitest's AST transform.
vi.mock('../lib/api', () => ({
  listKnowledgeFiles: vi.fn(),
  indexKnowledgeFile: vi.fn(),
  removeKnowledgeFile: vi.fn(),
}));

import * as api from '../lib/api';
import {
  useKnowledgeQuery,
  useAddKnowledgeMutation,
  useRemoveKnowledgeMutation,
} from './useKnowledge';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Minimal KnowledgeFile fixture for testing. */
const MOCK_FILE = {
  id: 'f1',
  workspace_id: 'ws-1',
  drive_file_id: 'drive-abc',
  title: 'My Doc',
  link: 'https://docs.google.com/document/d/abc',
  mime_type: 'application/vnd.google-apps.document',
  ai_description: 'A document about testing.',
  content_hash: 'abc123',
  created_at: '2026-04-12T00:00:00Z',
  last_scanned_at: '2026-04-12T00:00:00Z',
};

/** Creates a fresh React QueryClientProvider wrapper per test. */
function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useKnowledgeQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns knowledge file list', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.listKnowledgeFiles).mockResolvedValueOnce([MOCK_FILE]);

    const { result } = renderHook(() => useKnowledgeQuery('ws-1'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].title).toBe('My Doc');
    expect(api.listKnowledgeFiles).toHaveBeenCalledWith('ws-1');
  });

  it('returns empty array when workspace has no files', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.listKnowledgeFiles).mockResolvedValueOnce([]);

    const { result } = renderHook(() => useKnowledgeQuery('ws-2'), { wrapper });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual([]);
  });

  it('is disabled when workspaceId is empty', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    const { result } = renderHook(() => useKnowledgeQuery(''), { wrapper });

    // Query must not fire — fetchStatus stays idle
    expect(result.current.fetchStatus).toBe('idle');
    expect(api.listKnowledgeFiles).not.toHaveBeenCalled();
  });
});

describe('useAddKnowledgeMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates knowledge cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.indexKnowledgeFile).mockResolvedValueOnce(MOCK_FILE);

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useAddKnowledgeMutation('ws-1'), { wrapper });

    result.current.mutate({
      drive_file_id: 'drive-abc',
      title: 'My Doc',
      link: 'https://docs.google.com/document/d/abc',
      mime_type: 'application/vnd.google-apps.document',
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Knowledge list cache must be invalidated so the UI refreshes
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['knowledge', 'ws-1'],
    });
  });

  it('exposes the indexed file in mutation result on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.indexKnowledgeFile).mockResolvedValueOnce(MOCK_FILE);

    const { result } = renderHook(() => useAddKnowledgeMutation('ws-1'), { wrapper });

    result.current.mutate({
      drive_file_id: 'drive-abc',
      title: 'My Doc',
      link: 'https://docs.google.com/document/d/abc',
      mime_type: 'application/vnd.google-apps.document',
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(MOCK_FILE);
  });
});

describe('useRemoveKnowledgeMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates knowledge cache on success', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const wrapper = makeWrapper(queryClient);

    vi.mocked(api.removeKnowledgeFile).mockResolvedValueOnce({ status: 'deleted' });

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useRemoveKnowledgeMutation('ws-1'), { wrapper });

    result.current.mutate('f1');

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    // Knowledge list cache must be invalidated after deletion
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ['knowledge', 'ws-1'],
    });
  });
});
