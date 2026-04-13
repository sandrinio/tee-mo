/**
 * useChannels.test.ts — Unit tests for TanStack Query channel hooks (STORY-008-02).
 *
 * Covers all Gherkin hook scenarios from §2.1:
 *   R5: useSlackChannelsQuery — disabled when teamId is empty string
 *   R6: useChannelBindingsQuery — disabled when workspaceId is empty string
 *   R7: useBindChannelMutation — invalidates ['channel-bindings', workspaceId] on success
 *   R8: useUnbindChannelMutation — invalidates ['channel-bindings', workspaceId] on success
 *
 * Strategy:
 *   - api module functions are mocked via vi.mock so no HTTP calls are made.
 *   - Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *   - renderHook + waitFor from @testing-library/react are used to test async behaviour.
 *
 * FLASHCARDS.md compliance:
 *   - `globals: true` in vitest.config.ts enables RTL auto-cleanup — no manual cleanup needed.
 *   - vi.mock factory does NOT close over locally-declared variables (no hoisted() needed here).
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Module mocks — stub the api layer so no real HTTP calls are made.
// The vi.mock factory is hoisted by Vitest; no external variable references here
// so no vi.hoisted() is needed for these stubs.
// ---------------------------------------------------------------------------

vi.mock('../../lib/api', () => ({
  listSlackTeamChannels: vi.fn(),
  listChannelBindings: vi.fn(),
  bindChannel: vi.fn(),
  unbindChannel: vi.fn(),
}));

import * as api from '../../lib/api';
import {
  useSlackChannelsQuery,
  useChannelBindingsQuery,
  useBindChannelMutation,
  useUnbindChannelMutation,
} from '../useChannels';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fresh QueryClient per test — no retry to avoid spurious async delays. */
function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/** Hook wrapper that provides a fresh QueryClient per test. */
function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client }, children);
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useSlackChannelsQuery', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = makeClient();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * R5: useSlackChannelsQuery — disabled when teamId is empty string.
   * The query must NOT fire a network call when teamId is ''.
   */
  it('is disabled (does not fetch) when teamId is an empty string', () => {
    const { result } = renderHook(() => useSlackChannelsQuery(''), {
      wrapper: makeWrapper(queryClient),
    });

    // status should be 'pending' (no data yet) but fetchStatus should be 'idle'
    // because `enabled: false` prevents any fetch from starting.
    expect(result.current.fetchStatus).toBe('idle');
    expect(api.listSlackTeamChannels).not.toHaveBeenCalled();
  });

  /**
   * R5: useSlackChannelsQuery — enabled when teamId is non-empty.
   * Verifies that listSlackTeamChannels is called when a real teamId is provided.
   */
  it('fetches channels when teamId is non-empty', async () => {
    const mockChannels = [
      { id: 'C001', name: 'general', is_private: false },
      { id: 'C002', name: 'engineering', is_private: false },
    ];
    vi.mocked(api.listSlackTeamChannels).mockResolvedValueOnce(mockChannels);

    const { result } = renderHook(() => useSlackChannelsQuery('T_TEAM_001'), {
      wrapper: makeWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.listSlackTeamChannels).toHaveBeenCalledWith('T_TEAM_001');
    expect(result.current.data).toEqual(mockChannels);
  });
});

// ---------------------------------------------------------------------------

describe('useChannelBindingsQuery', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = makeClient();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * R6: useChannelBindingsQuery — disabled when workspaceId is empty string.
   */
  it('is disabled (does not fetch) when workspaceId is an empty string', () => {
    const { result } = renderHook(() => useChannelBindingsQuery(''), {
      wrapper: makeWrapper(queryClient),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(api.listChannelBindings).not.toHaveBeenCalled();
  });

  /**
   * R6: useChannelBindingsQuery — fetches when workspaceId is provided.
   */
  it('fetches bindings when workspaceId is non-empty', async () => {
    const mockBindings = [
      {
        slack_channel_id: 'C001',
        workspace_id: 'ws-abc',
        bound_at: '2026-01-01T00:00:00Z',
        channel_name: 'general',
        is_member: true,
      },
    ];
    vi.mocked(api.listChannelBindings).mockResolvedValueOnce(mockBindings);

    const { result } = renderHook(() => useChannelBindingsQuery('ws-abc'), {
      wrapper: makeWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.listChannelBindings).toHaveBeenCalledWith('ws-abc');
    expect(result.current.data).toEqual(mockBindings);
  });
});

// ---------------------------------------------------------------------------

describe('useBindChannelMutation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = makeClient();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * R7: useBindChannelMutation — invalidates ['channel-bindings', workspaceId] on success.
   */
  it('invalidates channel-bindings query after successful bind', async () => {
    const mockBinding = {
      slack_channel_id: 'C002',
      workspace_id: 'ws-abc',
      bound_at: '2026-01-02T00:00:00Z',
    };
    vi.mocked(api.bindChannel).mockResolvedValueOnce(mockBinding);

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useBindChannelMutation('ws-abc'), {
      wrapper: makeWrapper(queryClient),
    });

    result.current.mutate({ channelId: 'C002' });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.bindChannel).toHaveBeenCalledWith('ws-abc', 'C002');
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['channel-bindings', 'ws-abc'] }),
    );
  });
});

// ---------------------------------------------------------------------------

describe('useUnbindChannelMutation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = makeClient();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * R8: useUnbindChannelMutation — invalidates ['channel-bindings', workspaceId] on success.
   */
  it('invalidates channel-bindings query after successful unbind', async () => {
    vi.mocked(api.unbindChannel).mockResolvedValueOnce(undefined);

    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

    const { result } = renderHook(() => useUnbindChannelMutation('ws-abc'), {
      wrapper: makeWrapper(queryClient),
    });

    result.current.mutate({ channelId: 'C001' });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.unbindChannel).toHaveBeenCalledWith('ws-abc', 'C001');
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['channel-bindings', 'ws-abc'] }),
    );
  });
});
