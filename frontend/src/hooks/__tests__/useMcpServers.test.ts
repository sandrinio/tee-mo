/**
 * useMcpServers.test.ts — unit tests for TanStack Query hooks.
 *
 * Strategy: mock the api.ts functions; use a real QueryClient to verify
 * invalidateQueries is called with the correct key.
 *
 * FLASHCARD 2026-04-11 #vitest: vi.mock vars must be wrapped in vi.hoisted().
 * FLASHCARD 2026-04-11 #frontend: All fetches through TanStack Query / api.ts.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const {
  mockListMcpServers,
  mockCreateMcpServer,
  mockUpdateMcpServer,
  mockDeleteMcpServer,
  mockTestMcpServer,
} = vi.hoisted(() => ({
  mockListMcpServers: vi.fn(),
  mockCreateMcpServer: vi.fn(),
  mockUpdateMcpServer: vi.fn(),
  mockDeleteMcpServer: vi.fn(),
  mockTestMcpServer: vi.fn(),
}));

vi.mock('../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../lib/api')>();
  return {
    ...actual,
    listMcpServers: mockListMcpServers,
    createMcpServer: mockCreateMcpServer,
    updateMcpServer: mockUpdateMcpServer,
    deleteMcpServer: mockDeleteMcpServer,
    testMcpServer: mockTestMcpServer,
  };
});

// ---------------------------------------------------------------------------
// Import hooks after mocks
// ---------------------------------------------------------------------------

import {
  useMcpServersQuery,
  useCreateMcpServerMutation,
  useUpdateMcpServerMutation,
  useDeleteMcpServerMutation,
  useTestMcpServerMutation,
} from '../useMcpServers';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client }, children);
  };
}

const WORKSPACE_ID = 'ws-test-001';

const mockServers = [
  {
    name: 'github',
    transport: 'streamable_http' as const,
    url: 'https://api.githubcopilot.com/mcp/',
    is_active: true,
    created_at: '2026-04-26T00:00:00Z',
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useMcpServersQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches the MCP server list with the correct query key', async () => {
    mockListMcpServers.mockResolvedValue(mockServers);

    const client = makeClient();
    const { result } = renderHook(() => useMcpServersQuery(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockListMcpServers).toHaveBeenCalledWith(WORKSPACE_ID);
    expect(result.current.data).toEqual(mockServers);

    // Verify data is cached under the expected key
    const cached = client.getQueryData(['mcp-servers', WORKSPACE_ID]);
    expect(cached).toEqual(mockServers);
  });

  it('is disabled when workspaceId is empty', () => {
    const client = makeClient();
    const { result } = renderHook(() => useMcpServersQuery(''), {
      wrapper: makeWrapper(client),
    });

    // Query should not have fired
    expect(result.current.isLoading).toBe(false);
    expect(mockListMcpServers).not.toHaveBeenCalled();
  });
});

describe('useCreateMcpServerMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates ["mcp-servers", workspaceId] on success', async () => {
    const newServer = { ...mockServers[0] };
    mockCreateMcpServer.mockResolvedValue(newServer);
    mockListMcpServers.mockResolvedValue([newServer]);

    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useCreateMcpServerMutation(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      name: 'github',
      transport: 'streamable_http',
      url: 'https://api.githubcopilot.com/mcp/',
      headers: { Authorization: 'Bearer ghp_xxx' },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['mcp-servers', WORKSPACE_ID] }),
    );
  });
});

describe('useUpdateMcpServerMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates list key on success', async () => {
    const updated = { ...mockServers[0], is_active: false };
    mockUpdateMcpServer.mockResolvedValue(updated);

    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useUpdateMcpServerMutation(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ name: 'github', patch: { is_active: false } });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['mcp-servers', WORKSPACE_ID] }),
    );
  });
});

describe('useDeleteMcpServerMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('invalidates list key on success', async () => {
    mockDeleteMcpServer.mockResolvedValue(undefined);

    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useDeleteMcpServerMutation(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate('github');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['mcp-servers', WORKSPACE_ID] }),
    );
  });
});

describe('useTestMcpServerMutation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('does NOT invalidate the list on success (test is read-only)', async () => {
    mockTestMcpServer.mockResolvedValue({ ok: true, tool_count: 41, error: null });

    const client = makeClient();
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useTestMcpServerMutation(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate('github');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // No invalidation should have occurred
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it('returns the full McpTestResult including tool_count', async () => {
    const testResult = { ok: true, tool_count: 41, error: null };
    mockTestMcpServer.mockResolvedValue(testResult);

    const client = makeClient();

    const { result } = renderHook(() => useTestMcpServerMutation(WORKSPACE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate('github');

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(testResult);
  });
});
