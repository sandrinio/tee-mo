/**
 * authStore.ts — Global auth state for Tee-Mo (Zustand).
 *
 * Responsibilities:
 *   - Stores the authenticated user and tri-state auth status.
 *   - Exposes login / register / logout / fetchMe actions that proxy to
 *     the typed wrappers in ../lib/api.
 *
 * Design notes:
 *   - Cookie-based session. No token is stored in JS — all auth state is
 *     derived from calling GET /api/auth/me or the Set-Cookie headers on
 *     login/register.
 *   - The store starts in 'unknown' status. AuthInitializer transitions it
 *     to 'authed' or 'anon' on app mount. ProtectedRoute shows a spinner
 *     for 'unknown' and redirects to /login for 'anon'.
 *   - A boolean "is logged in" flag is intentionally NOT stored — derive it
 *     from `status === 'authed'` in components to avoid the two-field sync bug.
 */
import { create } from 'zustand';

import {
  type AuthUser,
  getMe,
  loginUser,
  logoutUser,
  registerUser,
} from '../lib/api';

/**
 * Lazily resolves the TanStack Query singleton from main.tsx.
 *
 * Using a lazy import avoids a module-load-time circular dependency
 * (main.tsx → AuthInitializer → authStore → main.tsx) and ensures the
 * mock for `../main` set up in unit tests is resolved AFTER the test's
 * `clearMock` variable is initialized. The returned promise always
 * resolves to the same `queryClient` instance.
 *
 * @returns The exported `queryClient` singleton.
 */
async function getQueryClient() {
  const mod = await import('../main');
  return mod.queryClient;
}

/**
 * Tri-state authentication status.
 * - 'unknown' — initial state; fetchMe has not completed yet.
 * - 'authed'  — a valid session cookie exists and getMe() succeeded.
 * - 'anon'    — no valid session (401 or network error from getMe).
 */
export type AuthStatus = 'unknown' | 'authed' | 'anon';

/**
 * Shape of the global Zustand auth store.
 */
export interface AuthState {
  /** Currently authenticated user, or null when unauthenticated. */
  user: AuthUser | null;
  /** Current auth status — see AuthStatus for semantics. */
  status: AuthStatus;
  /** Directly set the user; null transitions to 'anon'. */
  setUser: (user: AuthUser | null) => void;
  /** Email + password login. Throws on failure with backend detail message. */
  login: (email: string, password: string) => Promise<void>;
  /** Email + password registration. Auto-logs the user in on success. */
  register: (email: string, password: string) => Promise<void>;
  /** Clear cookies server-side, then clear store and TanStack Query cache. */
  logout: () => Promise<void>;
  /** Rehydrate from the session cookie; never throws — sets anon on network or auth failure. */
  fetchMe: () => Promise<void>;
}

/**
 * Global Zustand auth store.
 *
 * Use `useAuth.getState()` in non-React contexts (e.g., AuthInitializer,
 * route guards). Use `useAuth(selector)` in React components.
 */
export const useAuth = create<AuthState>((set) => ({
  user: null,
  status: 'unknown',

  setUser: (user) => set({ user, status: user ? 'authed' : 'anon' }),

  login: async (email, password) => {
    const { user } = await loginUser(email, password);
    set({ user, status: 'authed' });
  },

  register: async (email, password) => {
    const { user } = await registerUser(email, password);
    set({ user, status: 'authed' });
  },

  logout: async () => {
    try {
      await logoutUser();
    } finally {
      const qc = await getQueryClient();
      qc.clear();
      set({ user: null, status: 'anon' });
    }
  },

  fetchMe: async () => {
    try {
      const user = await getMe();
      set({ user, status: 'authed' });
    } catch {
      set({ user: null, status: 'anon' });
    }
  },
}));
