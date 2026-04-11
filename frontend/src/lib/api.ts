/**
 * api.ts — thin HTTP client for the Tee-Mo backend.
 *
 * Reads the API base URL from the `VITE_API_URL` environment variable at
 * build time (Vite replaces `import.meta.env.*` at bundle time). Falls back
 * to `''` (empty string = same origin) for production same-origin deploys
 * (STORY-003-01). Local dev uses either `VITE_API_URL=http://localhost:8000`
 * in `frontend/.env` OR the Vite dev-server proxy configured in vite.config.ts.
 *
 * `credentials: 'include'` is set on every request so that session cookies
 * established by future auth stories are forwarded automatically — no change
 * needed at the call site when auth lands in Sprint 2.
 */

const API_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Public user profile returned by the Tee-Mo backend.
 * Mirrors backend/app/models/user.py::UserResponse (STORY-002-02).
 * Does NOT include avatar_url or auth_provider — those fields
 * do not exist in teemo_users.
 */
export interface AuthUser {
  id: string;
  email: string;
  created_at: string;
}

/**
 * Generic GET helper. Throws an `Error` with the HTTP status code on all
 * non-2xx responses so TanStack Query's `isError` state is populated correctly.
 *
 * @param path - Path relative to the API base, e.g. `/api/health`.
 * @returns Parsed JSON body cast to `T`.
 *
 * @example
 * ```ts
 * const health = await apiGet<HealthResponse>('/api/health');
 * ```
 */
export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!r.ok) throw new Error(`API ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}

/**
 * Generic POST with cookie forwarding and backend-detail error propagation.
 *
 * On non-2xx responses, reads the JSON body and throws an Error whose
 * message is the backend's `detail` field (falling back to `"HTTP <status>"`
 * if the body is not JSON). Form code can surface err.message directly.
 *
 * @param path - Path relative to the API base, e.g. `/api/auth/login`.
 * @param body - Request body to JSON-encode.
 * @returns Parsed JSON body cast to `TRes`.
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

/** POST /api/auth/register — creates account and auto-logs the user in via Set-Cookie. */
export function registerUser(email: string, password: string) {
  return apiPost<{ email: string; password: string }, { user: AuthUser }>(
    '/api/auth/register',
    { email, password },
  );
}

/** POST /api/auth/login — authenticates via email+password and sets session cookies. */
export function loginUser(email: string, password: string) {
  return apiPost<{ email: string; password: string }, { user: AuthUser }>(
    '/api/auth/login',
    { email, password },
  );
}

/** POST /api/auth/logout — instructs the backend to clear both auth cookies. */
export function logoutUser() {
  return apiPost<Record<string, never>, { message: string }>('/api/auth/logout', {});
}

/** POST /api/auth/refresh — renews the access_token cookie using the refresh_token cookie. */
export function refreshToken() {
  return apiPost<Record<string, never>, { message: string }>('/api/auth/refresh', {});
}

/** GET /api/auth/me — returns the current authenticated user or throws on 401. */
export function getMe(): Promise<AuthUser> {
  return apiGet<AuthUser>('/api/auth/me');
}
