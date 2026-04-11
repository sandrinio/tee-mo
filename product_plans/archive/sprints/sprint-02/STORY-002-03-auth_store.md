---
story_id: "STORY-002-03-auth_store"
parent_epic_ref: "EPIC-002"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Charter §10 Epic Seed Map (Authentication — frontend row) + new_app useAuth.ts + AuthInitializer.tsx"
actor: "Frontend Dev (Solo)"
complexity_label: "L2"
---

# STORY-002-03: Frontend Auth Store + API Client + AuthInitializer

**Complexity: L2** — Extend `lib/api.ts` with 5 auth wrappers, create a stripped-down Zustand `useAuth` store, mount `AuthInitializer` in `main.tsx`. 4 files touched (2 new, 2 edited), ~1 hour.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Tee-Mo frontend**, I want to **track the current user in a global Zustand store, rehydrate on every hard refresh via `GET /api/auth/me`, and expose `login`/`register`/`logout` actions that hit the backend from STORY-002-02**, So that **STORY-002-04's login page, register page, ProtectedRoute, and SignOutButton can plug in with zero boilerplate**.

### 1.2 Detailed Requirements

- **R1 — Extend `frontend/src/lib/api.ts`** with a generic `apiPost<TReq, TRes>(path, body)` helper and 5 typed auth wrappers:
  - `registerUser(email: string, password: string): Promise<{ user: AuthUser }>`
  - `loginUser(email: string, password: string): Promise<{ user: AuthUser }>`
  - `logoutUser(): Promise<{ message: string }>`
  - `refreshToken(): Promise<{ message: string }>`
  - `getMe(): Promise<AuthUser>`
  - All wrappers must keep `credentials: "include"` (already set on the existing `apiGet`) so httpOnly cookies flow.
  - All wrappers must reach backend errors by reading the JSON body's `detail` field on any non-2xx response and throwing `new Error(detail)`. Tests and form code can then show the `detail` directly.
  - Export an `AuthUser` TypeScript type matching the backend `UserResponse`: `{ id: string; email: string; created_at: string }`. **Do not include** `full_name`, `avatar_url`, or `auth_provider` — those fields do not exist in `teemo_users`.
- **R2 — Create `frontend/src/stores/authStore.ts`** — Zustand store with this shape:
  ```ts
  interface AuthState {
    user: AuthUser | null;
    status: 'unknown' | 'authed' | 'anon';  // 'unknown' = initial fetchMe in flight
    setUser: (user: AuthUser | null) => void;
    login: (email: string, password: string) => Promise<void>;
    register: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    fetchMe: () => Promise<void>;
  }
  ```
  - Strip everything related to Supabase Realtime (`setRealtimeAuth`, `clearRealtimeAuth`) from the new_app copy — Tee-Mo has no Realtime.
  - Strip `loginWithGoogle` — no Google OAuth.
  - Strip `fullName` from the `register` signature — the backend does not accept it.
  - `isAuthenticated` is NOT a stored field — derive it by comparing `status === 'authed'` in components. This avoids the two-field sync bug where `user` and `isAuthenticated` can disagree.
  - `logout()` must call `logoutUser()`, then call `queryClient.clear()` (import the singleton from `main.tsx` — see R4), then set `{user: null, status: 'anon'}`.
  - `fetchMe()` must:
    1. Start in whatever status it is (no pre-set — the store starts in `'unknown'`).
    2. Call `getMe()`; on success, set `{user, status: 'authed'}`.
    3. On failure (401, network error, JSON parse failure), set `{user: null, status: 'anon'}`.
    4. Never throw — always resolve so callers don't need try/catch.
- **R3 — Create `frontend/src/components/auth/AuthInitializer.tsx`** — renderless component that calls `useAuth.getState().fetchMe()` exactly once on mount. Copy structurally from `new_app/frontend/src/components/auth/AuthInitializer.tsx`, swap the import path to the Tee-Mo store location, and keep the empty dependency array + ESLint disable comment.
- **R4 — Mount `AuthInitializer` in `frontend/src/main.tsx`** inside the `<QueryClientProvider>` and **above** `<RouterProvider>`. Also export the `queryClient` singleton so the auth store can import it for `queryClient.clear()` in `logout()`.
- **R5 — TypeScript strictness**: all new files must type-check with zero `any` and zero `@ts-ignore`. Use `import type { AuthUser }` where appropriate to avoid runtime import cycles.
- **R6 — Self-documenting code**: every exported function, every Zustand action, every TypeScript type MUST have a JSDoc comment (per CLAUDE.md §6).
- **R7 — Vitest setup**: add a `frontend/src/stores/__tests__/authStore.test.ts` unit test file covering the state transitions in §2.1. If `vitest` is not yet in `frontend/package.json`, install `vitest@^2.1.0` as a devDependency and add a `"test"` script (`vitest run`). Do NOT add `@testing-library/react` in this story — store tests are pure-function and don't need rendering.

### 1.3 Out of Scope
- Any route components — STORY-002-04 builds `/login`, `/register`, `/app`, ProtectedRoute, SignOutButton.
- Any form UI, form validation, error display — STORY-002-04.
- Automatic refresh-on-401 retry logic — not in EPIC-002 (the 15-min access token is long enough for the hackathon demo; users can re-login if expired).
- Token interceptors / axios-style middleware — we stay on native `fetch`.
- Google OAuth store actions — not in Tee-Mo.
- Supabase Realtime wiring — not used by Tee-Mo.

### TDD Red Phase: Yes
Rationale: Zustand store is pure logic with well-defined state transitions; Red tests are cheap and lock down the 'unknown' → 'authed' / 'anon' transitions that ProtectedRoute (STORY-002-04) depends on.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Frontend auth store

  Scenario: Initial state is 'unknown' with no user
    Given the authStore module is freshly imported
    Then useAuth.getState().user is null
    And useAuth.getState().status equals 'unknown'

  Scenario: setUser(user) flips status to 'authed'
    Given an AuthUser fixture {id, email, created_at}
    When I call useAuth.getState().setUser(fixture)
    Then useAuth.getState().user equals the fixture
    And useAuth.getState().status equals 'authed'

  Scenario: setUser(null) flips status to 'anon'
    Given the store currently has a user set
    When I call useAuth.getState().setUser(null)
    Then useAuth.getState().user is null
    And useAuth.getState().status equals 'anon'

  Scenario: fetchMe success populates the store
    Given fetch is mocked to return 200 with a user JSON body
    When I call useAuth.getState().fetchMe()
    Then useAuth.getState().status equals 'authed'
    And useAuth.getState().user matches the mocked body

  Scenario: fetchMe 401 sets status to 'anon'
    Given fetch is mocked to return 401
    When I call useAuth.getState().fetchMe()
    Then useAuth.getState().status equals 'anon'
    And useAuth.getState().user is null
    And the call does not throw

  Scenario: fetchMe network error sets status to 'anon'
    Given fetch is mocked to reject with a TypeError
    When I call useAuth.getState().fetchMe()
    Then useAuth.getState().status equals 'anon'
    And the call does not throw

  Scenario: login success populates the store
    Given fetch is mocked: POST /api/auth/login → 200 {user: {...}}
    When I call useAuth.getState().login('a@b.co', 'correcthorse')
    Then useAuth.getState().status equals 'authed'
    And useAuth.getState().user.email equals 'a@b.co'

  Scenario: login failure throws with backend detail
    Given fetch is mocked: POST /api/auth/login → 401 {detail: 'Invalid credentials'}
    When I call useAuth.getState().login('a@b.co', 'wrong')
    Then the promise rejects with message 'Invalid credentials'
    And useAuth.getState().status remains 'unknown' or 'anon' (unchanged)

  Scenario: register success populates the store
    Given fetch is mocked: POST /api/auth/register → 201 {user: {...}}
    When I call useAuth.getState().register('new@b.co', 'correcthorse')
    Then useAuth.getState().status equals 'authed'
    And useAuth.getState().user.email equals 'new@b.co'

  Scenario: logout clears the store and query cache
    Given the store currently has a user set
    And fetch is mocked: POST /api/auth/logout → 200
    When I call useAuth.getState().logout()
    Then useAuth.getState().user is null
    And useAuth.getState().status equals 'anon'
    And queryClient.clear has been called
```

### 2.2 Verification Steps (Manual)
- [ ] `cd frontend && npm test` runs the Vitest suite and all scenarios above pass.
- [ ] `npm run build` succeeds with zero TypeScript errors.
- [ ] `npm run dev` starts Vite; opening `http://localhost:5173/` in the browser shows no console errors from `AuthInitializer` (it will 401 silently on `/api/auth/me` and set status to 'anon').
- [ ] Open DevTools → Network: confirm the first page load fires exactly one `GET /api/auth/me` request.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-002-02** | Backend auth routes live and reachable at `http://localhost:8000/api/auth/*`. Either the backend is running, OR tests mock `fetch`. | [ ] |
| **Node / npm** | Node 22 already installed from S-01 frontend scaffold | [x] |
| **Zustand** | `zustand@^5.0.12` already in `frontend/package.json` from S-01 | [x] |
| **TanStack Query** | `@tanstack/react-query` already installed and provider mounted in S-01 | [x] |
| **Vitest** | May need `vitest@^2.1.0` added as devDependency; also add `"test": "vitest run"` script | [ ] |
| **Env Vars** | `VITE_API_URL` defaults to `http://localhost:8000` per S-01 `lib/api.ts` — no new env vars needed | [x] |

### 3.1 Test Implementation

Create `frontend/src/stores/__tests__/authStore.test.ts`. Use `vi.stubGlobal('fetch', ...)` or `vi.spyOn(global, 'fetch')` to mock. Reset the store between tests with `useAuth.setState({ user: null, status: 'unknown' })` in a `beforeEach`.

Mock the queryClient via module mocking so you can assert `queryClient.clear()` was called on logout:

```ts
// authStore.test.ts (skeleton — fill in all 10 scenarios)
import { beforeEach, describe, expect, it, vi } from 'vitest';

const clearMock = vi.fn();
vi.mock('../../main', () => ({
  queryClient: { clear: clearMock },
}));

import { useAuth } from '../authStore';
import type { AuthUser } from '../../lib/api';

const FIXTURE: AuthUser = {
  id: '11111111-1111-1111-1111-111111111111',
  email: 'alice@example.com',
  created_at: '2026-04-11T00:00:00Z',
};

beforeEach(() => {
  useAuth.setState({ user: null, status: 'unknown' });
  clearMock.mockClear();
  vi.restoreAllMocks();
});

describe('authStore', () => {
  it('starts in "unknown" status with no user', () => {
    expect(useAuth.getState().user).toBeNull();
    expect(useAuth.getState().status).toBe('unknown');
  });

  it('setUser(user) flips to authed', () => {
    useAuth.getState().setUser(FIXTURE);
    expect(useAuth.getState().status).toBe('authed');
    expect(useAuth.getState().user).toEqual(FIXTURE);
  });

  it('fetchMe success populates the store', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(FIXTURE), { status: 200 }),
    );
    await useAuth.getState().fetchMe();
    expect(useAuth.getState().status).toBe('authed');
    expect(useAuth.getState().user?.email).toBe('alice@example.com');
  });

  it('fetchMe 401 sets anon without throwing', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 }),
    );
    await expect(useAuth.getState().fetchMe()).resolves.toBeUndefined();
    expect(useAuth.getState().status).toBe('anon');
  });

  // ... remaining scenarios
});
```

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/stores/authStore.ts` (new) |
| **Related Files** | `frontend/src/lib/api.ts` (edit — add `apiPost` + 5 wrappers + `AuthUser` type), `frontend/src/components/auth/AuthInitializer.tsx` (new), `frontend/src/main.tsx` (edit — export `queryClient`, mount `AuthInitializer`), `frontend/src/stores/__tests__/authStore.test.ts` (new), `frontend/package.json` (edit — add vitest if missing) |
| **New Files Needed** | Yes — `stores/authStore.ts`, `components/auth/AuthInitializer.tsx`, `stores/__tests__/authStore.test.ts` |
| **ADR References** | ADR-001 (cookie-based auth — store reads nothing from localStorage), ADR-014 (Zustand for client state) |
| **First-Use Pattern** | Yes — this is Tee-Mo's first Zustand store and first Vitest test. Reference: `/Users/ssuladze/Documents/Dev/new_app/frontend/src/hooks/useAuth.ts` (strip Realtime + Google) and any existing Vitest test in new_app. After completion, record any setup gotchas in FLASHCARDS.md. |

### 3.3 Technical Logic

**Step 1 — Extend `frontend/src/lib/api.ts`:**

Add the `apiPost` helper, the 5 typed wrappers, and the `AuthUser` type. Keep the existing `apiGet` untouched. Result:

```ts
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

/**
 * Public user profile returned by the Tee-Mo backend.
 * Mirrors backend/app/models/user.py::UserResponse (STORY-002-02).
 */
export interface AuthUser {
  id: string;
  email: string;
  created_at: string;
}

/**
 * Generic GET (unchanged from S-01).
 */
export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!r.ok) throw new Error(`API ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

/**
 * Generic POST with cookie forwarding and backend-detail error propagation.
 *
 * On any non-2xx response, reads the JSON body and throws an Error whose
 * message is the backend's `detail` field (falling back to `"HTTP <status>"`
 * if the body is not JSON). Form code can surface err.message directly.
 */
export async function apiPost<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const r = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail: string;
    try {
      const payload = await r.json();
      detail = payload?.detail ?? `HTTP ${r.status}`;
    } catch {
      detail = `HTTP ${r.status}`;
    }
    throw new Error(detail);
  }
  return r.json() as Promise<TRes>;
}

// ---------------------------------------------------------------------------
// Auth wrappers (STORY-002-03)
// ---------------------------------------------------------------------------

/** POST /api/auth/register — auto-logs the user in via Set-Cookie. */
export function registerUser(email: string, password: string) {
  return apiPost<{ email: string; password: string }, { user: AuthUser }>(
    '/api/auth/register',
    { email, password },
  );
}

/** POST /api/auth/login. */
export function loginUser(email: string, password: string) {
  return apiPost<{ email: string; password: string }, { user: AuthUser }>(
    '/api/auth/login',
    { email, password },
  );
}

/** POST /api/auth/logout — backend clears both cookies. */
export function logoutUser() {
  return apiPost<Record<string, never>, { message: string }>('/api/auth/logout', {});
}

/** POST /api/auth/refresh — renews the access_token cookie. */
export function refreshToken() {
  return apiPost<Record<string, never>, { message: string }>('/api/auth/refresh', {});
}

/** GET /api/auth/me — returns the current user or throws on 401. */
export function getMe(): Promise<AuthUser> {
  return apiGet<AuthUser>('/api/auth/me');
}
```

**Step 2 — Create `frontend/src/stores/authStore.ts`:**

```ts
/**
 * Global auth state for Tee-Mo (Zustand).
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
 *   - `isAuthenticated` is intentionally NOT a stored field — derive it
 *     from `status === 'authed'` in components.
 */
import { create } from 'zustand';

import {
  type AuthUser,
  getMe,
  loginUser,
  logoutUser,
  registerUser,
} from '../lib/api';
import { queryClient } from '../main';

export type AuthStatus = 'unknown' | 'authed' | 'anon';

export interface AuthState {
  user: AuthUser | null;
  status: AuthStatus;
  /** Directly set the user; null transitions to 'anon'. */
  setUser: (user: AuthUser | null) => void;
  /** Email + password login. Throws on failure with backend detail. */
  login: (email: string, password: string) => Promise<void>;
  /** Email + password registration. Auto-logs the user in. */
  register: (email: string, password: string) => Promise<void>;
  /** Clear cookies server-side, then clear store and query cache. */
  logout: () => Promise<void>;
  /** Rehydrate from the session cookie; never throws. */
  fetchMe: () => Promise<void>;
}

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
      queryClient.clear();
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
```

**Step 3 — Create `frontend/src/components/auth/AuthInitializer.tsx`:**

```tsx
/**
 * AuthInitializer — fires the initial auth rehydration on app mount.
 *
 * Calls `useAuth.getState().fetchMe()` exactly once, giving ProtectedRoute
 * the auth state it needs before rendering children. Renderless.
 *
 * Mounted once in main.tsx inside <QueryClientProvider> and above
 * <RouterProvider> so the fetch kicks off before any route mounts.
 */
import { useEffect } from 'react';

import { useAuth } from '../../stores/authStore';

export function AuthInitializer() {
  useEffect(() => {
    // Stable Zustand action — safe to call from an empty-deps effect.
    useAuth.getState().fetchMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
```

**Step 4 — Edit `frontend/src/main.tsx`:**

- Change `const queryClient = new QueryClient();` to `export const queryClient = new QueryClient();`.
- Import `AuthInitializer`.
- Render `<AuthInitializer />` as the first child inside `<QueryClientProvider>`, immediately before `<RouterProvider>`.

```tsx
import { AuthInitializer } from './components/auth/AuthInitializer';

// ... existing router + queryClient setup ...
export const queryClient = new QueryClient();

// Render:
<StrictMode>
  <QueryClientProvider client={queryClient}>
    <AuthInitializer />
    <RouterProvider router={router} />
  </QueryClientProvider>
</StrictMode>
```

**Step 5 — Wire Vitest** (if not already present):

```bash
cd frontend && npm install --save-dev vitest@^2.1.0
```

Add to `package.json` scripts: `"test": "vitest run"`. Vitest auto-discovers `**/*.test.ts` files — no `vitest.config.ts` needed unless a default clashes.

### 3.4 API Contract

This story consumes the API contracts defined in STORY-002-02 §3.4. No new backend endpoints are introduced.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 10 | One per Gherkin scenario in §2.1 (authStore) |
| Component tests | 0 — N/A (no React components with visible output in this story; AuthInitializer is renderless) | |
| E2E / acceptance tests | 0 — covered manually in STORY-002-04 | |
| Integration tests | 0 — N/A | |

### 4.2 Definition of Done
- [ ] TDD Red phase: all 10 tests written and verified failing before implementation.
- [ ] Green phase: `npm test` passes in `frontend/`.
- [ ] `npm run build` succeeds with zero TypeScript errors.
- [ ] `npm run dev` + visit `http://localhost:5173/` shows exactly one `GET /api/auth/me` network call on mount, and no console errors.
- [ ] `frontend/src/stores/authStore.ts` has no reference to `setRealtimeAuth`, `clearRealtimeAuth`, `loginWithGoogle`, or `fullName`.
- [ ] `frontend/src/lib/api.ts` exports `AuthUser`, `apiPost`, `registerUser`, `loginUser`, `logoutUser`, `refreshToken`, `getMe`.
- [ ] `queryClient` is exported from `main.tsx` and imported by `authStore.ts`.
- [ ] FLASHCARDS.md `TanStack Query` entry respected — wrappers live in `lib/api.ts`, components never call `fetch` directly.
- [ ] No ADR violations.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 16 | 572 | 588 |
| Developer | 131 | 13,771 | 13,902 |
| DevOps | 23 | 516 | 539 |
