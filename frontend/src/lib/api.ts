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

// ---------------------------------------------------------------------------
// Slack wrappers (STORY-005A-06)
// ---------------------------------------------------------------------------

/**
 * A single Slack workspace record returned by GET /api/slack/teams.
 * Mirrors backend/app/api/routes/slack.py::SlackTeamResponse (ADR-024).
 */
export interface SlackTeam {
  /** Slack-assigned team identifier, e.g. "T0123ABCDEF". */
  slack_team_id: string;
  /** Slack bot user ID associated with the installation. */
  slack_bot_user_id: string;
  /** ISO 8601 timestamp of when Tee-Mo was installed in this workspace. */
  installed_at: string;
}

/**
 * Response shape for GET /api/slack/teams.
 */
export interface SlackTeamsResponse {
  teams: SlackTeam[];
}

/**
 * Fetches all Slack teams where Tee-Mo is installed for the current user.
 *
 * Requires a valid session cookie (set by POST /api/auth/login). Throws an
 * Error with the HTTP status code on non-2xx responses so TanStack Query's
 * `isError` state is populated correctly.
 *
 * @returns List of installed Slack teams wrapped in a `SlackTeamsResponse`.
 */
export async function listSlackTeams(): Promise<SlackTeamsResponse> {
  return apiGet<SlackTeamsResponse>('/api/slack/teams');
}

// ---------------------------------------------------------------------------
// Workspace wrappers (STORY-003-B04)
// ---------------------------------------------------------------------------

/**
 * A single Tee-Mo workspace record returned by the workspace CRUD endpoints.
 * Mirrors backend/app/models/workspace.py::WorkspaceResponse (ADR-022).
 */
export interface Workspace {
  /** UUID primary key for this workspace. */
  id: string;
  /** Human-readable workspace name. */
  name: string;
  /** Slack team this workspace belongs to. */
  slack_team_id: string;
  /** UUID of the user who owns/created this workspace. */
  owner_user_id: string;
  /** Whether this workspace is the default for its Slack team. */
  is_default_for_team: boolean;
  /** ISO 8601 creation timestamp. */
  created_at: string;
}

/**
 * Generic PATCH helper with cookie forwarding and backend-detail error propagation.
 *
 * Functionally identical to `apiPost` but uses HTTP PATCH — suitable for
 * partial updates (rename, make-default) where only the changed fields are sent.
 *
 * @param path - Path relative to the API base, e.g. `/api/workspaces/123`.
 * @param body - Partial update payload to JSON-encode.
 * @returns Parsed JSON body cast to `TRes`.
 */
export async function apiPatch<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const r = await fetch(`${API_URL}${path}`, {
    method: 'PATCH',
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

/**
 * GET /api/workspaces?team_id={teamId} — fetches all workspaces for a Slack team.
 *
 * @param teamId - The Slack team ID to filter workspaces by.
 * @returns Array of workspace records belonging to the team.
 */
export async function listWorkspaces(teamId: string): Promise<Workspace[]> {
  return apiGet<Workspace[]>(`/api/workspaces?team_id=${encodeURIComponent(teamId)}`);
}

/**
 * GET /api/workspaces/{id} — fetches a single workspace by UUID.
 *
 * @param id - The workspace UUID.
 * @returns The workspace record.
 */
export async function getWorkspace(id: string): Promise<Workspace> {
  return apiGet<Workspace>(`/api/workspaces/${encodeURIComponent(id)}`);
}

/**
 * POST /api/workspaces — creates a new workspace under the given Slack team.
 *
 * @param teamId - The Slack team ID this workspace belongs to.
 * @param name   - The human-readable workspace name.
 * @returns The newly created workspace record.
 */
export async function createWorkspace(teamId: string, name: string): Promise<Workspace> {
  return apiPost<{ slack_team_id: string; name: string }, Workspace>(
    '/api/workspaces',
    { slack_team_id: teamId, name },
  );
}

/**
 * PATCH /api/workspaces/{id} — renames an existing workspace.
 *
 * @param id   - The workspace UUID to rename.
 * @param name - The new workspace name.
 * @returns The updated workspace record.
 */
export async function renameWorkspace(id: string, name: string): Promise<Workspace> {
  return apiPatch<{ name: string }, Workspace>(
    `/api/workspaces/${encodeURIComponent(id)}`,
    { name },
  );
}

/**
 * PATCH /api/workspaces/{id}/default — sets a workspace as the team default.
 *
 * The backend clears `is_default_for_team` on all other workspaces in the
 * same Slack team before setting the flag on the target workspace.
 *
 * @param id - The workspace UUID to promote as default.
 * @returns The updated workspace record with `is_default_for_team: true`.
 */
export async function makeWorkspaceDefault(id: string): Promise<Workspace> {
  return apiPatch<Record<string, never>, Workspace>(
    `/api/workspaces/${encodeURIComponent(id)}/default`,
    {},
  );
}
