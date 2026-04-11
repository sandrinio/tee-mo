/**
 * authStore.test.ts — Red-phase unit tests for the Zustand auth store.
 *
 * Tests verify state transitions for all 10 Gherkin scenarios in
 * STORY-002-03 §2.1. All fetch calls are mocked via vi.spyOn so no
 * live backend is needed. The queryClient singleton is module-mocked
 * so logout assertions can verify queryClient.clear() was called.
 *
 * These tests MUST fail during Red phase because authStore.ts and the
 * AuthUser type in lib/api.ts do not yet exist.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock queryClient singleton BEFORE the store import resolves, so the
// store's import of `queryClient` from '../../main' gets this mock object.
const clearMock = vi.fn();
vi.mock('../../main', () => ({
  queryClient: { clear: clearMock },
}));

// These imports will fail during Red phase (files don't exist yet).
import { useAuth } from '../authStore';
import type { AuthUser } from '../../lib/api';

/** Canonical AuthUser fixture used across multiple tests. */
const FIXTURE: AuthUser = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'alice@example.com',
  created_at: '2026-04-11T00:00:00Z',
};

beforeEach(() => {
  // Reset store to initial state between tests so each test is isolated.
  useAuth.setState({ user: null, status: 'unknown' });
  // Clear the queryClient mock call history.
  clearMock.mockClear();
  // Restore any per-test spies to their originals.
  vi.restoreAllMocks();
});

describe('authStore', () => {
  /**
   * Scenario: Initial state is 'unknown' with no user
   * Given the authStore module is freshly imported
   * Then useAuth.getState().user is null
   * And useAuth.getState().status equals 'unknown'
   */
  it('starts in "unknown" status with no user', () => {
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe('unknown');
  });

  /**
   * Scenario: setUser(user) flips status to 'authed'
   * Given an AuthUser fixture {id, email, created_at}
   * When I call useAuth.getState().setUser(fixture)
   * Then useAuth.getState().user equals the fixture
   * And useAuth.getState().status equals 'authed'
   */
  it('setUser(user) flips status to "authed"', () => {
    useAuth.getState().setUser(FIXTURE);
    expect(useAuth.getState().user).toEqual(FIXTURE);
    expect(useAuth.getState().status).toBe('authed');
  });

  /**
   * Scenario: setUser(null) flips status to 'anon'
   * Given the store currently has a user set
   * When I call useAuth.getState().setUser(null)
   * Then useAuth.getState().user is null
   * And useAuth.getState().status equals 'anon'
   */
  it('setUser(null) flips status to "anon"', () => {
    // Pre-seed: set a user first so the transition is observable.
    useAuth.setState({ user: FIXTURE, status: 'authed' });
    useAuth.getState().setUser(null);
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe('anon');
  });

  /**
   * Scenario: fetchMe success populates the store
   * Given fetch is mocked to return 200 with a user JSON body
   * When I call useAuth.getState().fetchMe()
   * Then useAuth.getState().status equals 'authed'
   * And useAuth.getState().user matches the mocked body
   */
  it('fetchMe success populates the store', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(FIXTURE), { status: 200 }),
    );
    await useAuth.getState().fetchMe();
    expect(useAuth.getState().status).toBe('authed');
    expect(useAuth.getState().user).toEqual(FIXTURE);
  });

  /**
   * Scenario: fetchMe 401 sets status to 'anon'
   * Given fetch is mocked to return 401
   * When I call useAuth.getState().fetchMe()
   * Then useAuth.getState().status equals 'anon'
   * And useAuth.getState().user is null
   * And the call does not throw
   */
  it('fetchMe 401 sets status to "anon" without throwing', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    );
    await expect(useAuth.getState().fetchMe()).resolves.toBeUndefined();
    expect(useAuth.getState().status).toBe('anon');
    expect(useAuth.getState().user).toBeNull();
  });

  /**
   * Scenario: fetchMe network error sets status to 'anon'
   * Given fetch is mocked to reject with a TypeError
   * When I call useAuth.getState().fetchMe()
   * Then useAuth.getState().status equals 'anon'
   * And the call does not throw
   */
  it('fetchMe network error sets status to "anon" without throwing', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new TypeError('network'));
    await expect(useAuth.getState().fetchMe()).resolves.toBeUndefined();
    expect(useAuth.getState().status).toBe('anon');
  });

  /**
   * Scenario: login success populates the store
   * Given fetch is mocked: POST /api/auth/login → 200 {user: {...}}
   * When I call useAuth.getState().login('a@b.co', 'correcthorse')
   * Then useAuth.getState().status equals 'authed'
   * And useAuth.getState().user.email equals 'a@b.co'
   */
  it('login success populates the store', async () => {
    const loginUser: AuthUser = { ...FIXTURE, email: 'a@b.co' };
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ user: loginUser }), { status: 200 }),
    );
    await useAuth.getState().login('a@b.co', 'correcthorse');
    expect(useAuth.getState().status).toBe('authed');
    expect(useAuth.getState().user?.email).toBe('a@b.co');
  });

  /**
   * Scenario: login failure throws with backend detail
   * Given fetch is mocked: POST /api/auth/login → 401 {detail: 'Invalid credentials'}
   * When I call useAuth.getState().login('a@b.co', 'wrong')
   * Then the promise rejects with message 'Invalid credentials'
   * And useAuth.getState().status remains 'unknown' or 'anon' (unchanged)
   */
  it('login failure throws with backend detail and does not set authed', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Invalid credentials' }), { status: 401 }),
    );
    await expect(useAuth.getState().login('a@b.co', 'wrong')).rejects.toThrow(
      'Invalid credentials',
    );
    // Status must NOT be 'authed' after a failed login.
    expect(useAuth.getState().status).not.toBe('authed');
  });

  /**
   * Scenario: register success populates the store
   * Given fetch is mocked: POST /api/auth/register → 201 {user: {...}}
   * When I call useAuth.getState().register('new@b.co', 'correcthorse')
   * Then useAuth.getState().status equals 'authed'
   * And useAuth.getState().user.email equals 'new@b.co'
   */
  it('register success populates the store', async () => {
    const newUser: AuthUser = { ...FIXTURE, email: 'new@b.co' };
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ user: newUser }), { status: 201 }),
    );
    await useAuth.getState().register('new@b.co', 'correcthorse');
    expect(useAuth.getState().status).toBe('authed');
    expect(useAuth.getState().user?.email).toBe('new@b.co');
  });

  /**
   * Scenario: logout clears the store and query cache
   * Given the store currently has a user set
   * And fetch is mocked: POST /api/auth/logout → 200
   * When I call useAuth.getState().logout()
   * Then useAuth.getState().user is null
   * And useAuth.getState().status equals 'anon'
   * And queryClient.clear has been called
   */
  it('logout clears the store and calls queryClient.clear()', async () => {
    // Pre-seed: a logged-in user so the transition is observable.
    useAuth.setState({ user: FIXTURE, status: 'authed' });
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ message: 'Logged out' }), { status: 200 }),
    );
    await useAuth.getState().logout();
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe('anon');
    expect(clearMock).toHaveBeenCalledOnce();
  });
});
