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

// ---------------------------------------------------------------------------
// fetchWithAuth — singleton refresh lock + 401 interceptor (STORY-022-01)
// ---------------------------------------------------------------------------

/**
 * Module-level promise used as a mutex so that multiple concurrent 401s
 * only trigger a single POST /api/auth/refresh. All callers await the same
 * promise; after it settles the lock is cleared for the next expiry cycle.
 */
let refreshPromise: Promise<void> | null = null;

/**
 * Core fetch wrapper that transparently renews expired access tokens.
 *
 * On a 401 (and only if the URL is not the refresh endpoint itself):
 *   1. Acquires the singleton refresh lock (or reuses an in-flight one).
 *   2. Awaits POST /api/auth/refresh — backend sets a new access_token cookie.
 *   3. On refresh success: replays the original request.
 *   4. On refresh failure (7-day refresh_token expired): lazily imports
 *      authStore and calls logout() to transition status → 'anon'.
 *
 * @param url     Fully-qualified URL (`API_URL` already prepended by caller).
 * @param options Standard RequestInit. `credentials: 'include'` is always forced.
 */
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const opts: RequestInit = { ...options, credentials: 'include' };
  let response = await fetch(url, opts);

  if (response.status === 401 && !url.includes('/api/auth/refresh')) {
    if (!refreshPromise) {
      refreshPromise = fetch(`${API_URL}/api/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
        .then((res) => {
          if (!res.ok) throw new Error('refresh_failed');
        })
        .finally(() => {
          refreshPromise = null;
        });
    }

    try {
      await refreshPromise;
      // Refresh succeeded — replay with the new cookie.
      response = await fetch(url, opts);
    } catch {
      // Refresh token also expired — eject the user.
      // Lazy import avoids circular: api.ts → authStore → api.ts.
      try {
        const { useAuth } = await import('../stores/authStore');
        await useAuth.getState().logout();
      } catch {
        // Network down or store unavailable — ignore, let callers handle the 401.
      }
    }
  }

  return response;
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetchWithAuth(`${API_URL}${path}`);
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
  const r = await fetchWithAuth(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  /** Human-readable Slack team/company name from OAuth. */
  slack_team_name?: string;
  /** Slack bot user ID associated with the installation. */
  slack_bot_user_id: string;
  /** ISO 8601 timestamp of when Tee-Mo was installed in this workspace. */
  installed_at: string;
  /** User's role in this team — 'owner' or 'member'. */
  role?: string;
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

/**
 * Deletes a Slack team and ALL related data (workspaces, channels, files, skills).
 * Owner-only — returns 403 if the caller is not the team owner.
 */
export async function deleteSlackTeam(teamId: string): Promise<void> {
  const res = await fetchWithAuth(`${API_URL}/api/slack/teams/${teamId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(await res.text());
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
  bot_persona?: string | null;
  created_at: string;
  updated_at: string;
  /**
   * Detail-only fields (STORY-025-05) — present on GET /api/workspaces/{id} only.
   * List endpoint (GET /api/slack-teams/{id}/workspaces) omits these; optional here.
   */
  /** True when the authenticated user has role='owner' in the workspace's Slack team. */
  is_owner?: boolean;
  /** Human-readable Slack workspace name from teemo_slack_teams.slack_team_name (set at OAuth install). Null when no install row found. */
  slack_team_name?: string | null;
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
  const r = await fetchWithAuth(`${API_URL}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
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
 * GET /api/slack-teams/{teamId}/workspaces — fetches all workspaces for a Slack team.
 *
 * @param teamId - The Slack team ID to filter workspaces by.
 * @returns Array of workspace records belonging to the team.
 */
export async function listWorkspaces(teamId: string): Promise<Workspace[]> {
  return apiGet<Workspace[]>(`/api/slack-teams/${encodeURIComponent(teamId)}/workspaces`);
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
 * POST /api/slack-teams/{teamId}/workspaces — creates a new workspace under the given Slack team.
 *
 * @param teamId - The Slack team ID this workspace belongs to.
 * @param name   - The human-readable workspace name.
 * @returns The newly created workspace record.
 */
export async function createWorkspace(teamId: string, name: string): Promise<Workspace> {
  return apiPost<{ name: string }, Workspace>(
    `/api/slack-teams/${encodeURIComponent(teamId)}/workspaces`,
    { name },
  );
}

/**
 * PATCH /api/workspaces/{id}
 * Updates a workspace's name and/or bot persona.
 *
 * @param id - Workspace UUID.
 * @param updates - Fields to update. `name` is required by the backend model;
 *   `bot_persona` is optional (pass `null` or `""` to clear).
 * @returns The updated Workspace object.
 */
export async function updateWorkspace(
  id: string,
  updates: { name: string; bot_persona?: string | null }
): Promise<Workspace> {
  return apiPatch<{ name: string; bot_persona?: string | null }, Workspace>(
    `/api/workspaces/${encodeURIComponent(id)}`,
    updates
  );
}

/** Legacy wrapper for updateWorkspace (renames only). */
export async function renameWorkspace(id: string, name: string): Promise<Workspace> {
  return updateWorkspace(id, { name });
}

/**
 * DELETE /api/workspaces/{workspaceId} — permanently deletes a workspace and all
 * associated data (skills, knowledge files, channel bindings) via ON DELETE CASCADE.
 *
 * Owner-only — the backend filters on both workspace id and user_id, returning 404
 * if the workspace does not exist or the caller is not the owner.
 *
 * @param workspaceId - UUID of the workspace to delete.
 * @returns void (HTTP 204 No Content on success).
 * @throws Error with backend `detail` message on non-2xx responses.
 */
export async function deleteWorkspace(workspaceId: string): Promise<void> {
  const r = await fetchWithAuth(`${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'DELETE',
  });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
}

/**
 * POST /api/workspaces/{id}/make-default — sets a workspace as the team default.
 *
 * The backend clears `is_default_for_team` on all other workspaces in the
 * same Slack team before setting the flag on the target workspace.
 *
 * @param id - The workspace UUID to promote as default.
 * @returns The updated workspace record with `is_default_for_team: true`.
 */
export async function makeWorkspaceDefault(id: string): Promise<Workspace> {
  return apiPost<Record<string, never>, Workspace>(
    `/api/workspaces/${encodeURIComponent(id)}/make-default`,
    {},
  );
}

// ---------------------------------------------------------------------------
// BYOK Key wrappers (STORY-004-03)
// ---------------------------------------------------------------------------

/**
 * Response shape for GET /api/workspaces/{id}/keys.
 * Mirrors backend/app/models/key.py::KeyResponse (ADR-002).
 * The plaintext key is NEVER returned — only the mask.
 */
export interface ProviderKey {
  /** true if an encrypted key is stored for this workspace */
  has_key: boolean;
  /** 'google' | 'openai' | 'anthropic' — null if has_key is false */
  provider: string | null;
  /** Masked key string e.g. "sk-a...xyz9" — null if has_key is false */
  key_mask: string | null;
  /** User-selected conversation-tier model ID */
  ai_model: string | null;
}

/** Request body for POST /api/workspaces/{id}/keys */
export interface SaveKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
  ai_model?: string;
}

/** Request body for POST /api/keys/validate */
export interface ValidateKeyRequest {
  provider: 'google' | 'openai' | 'anthropic';
  key: string;
}

/** Response from POST /api/keys/validate */
export interface ValidateKeyResponse {
  valid: boolean;
  message: string;
}

/**
 * GET /api/workspaces/{workspaceId}/keys
 * Returns key status for a workspace — never returns the plaintext key.
 *
 * @param workspaceId - UUID of the workspace to fetch key status for.
 * @returns Key status including has_key, provider, key_mask, and ai_model.
 */
export function getKey(workspaceId: string): Promise<ProviderKey> {
  return apiGet<ProviderKey>(`/api/workspaces/${encodeURIComponent(workspaceId)}/keys`);
}

/**
 * POST /api/workspaces/{workspaceId}/keys
 * Encrypt and store the user's BYOK API key for this workspace.
 *
 * @param workspaceId - UUID of the workspace to associate the key with.
 * @param body        - Provider, plaintext key, and optional model selection.
 * @returns Updated key status (plaintext key stripped — returns mask only).
 */
export function saveKey(workspaceId: string, body: SaveKeyRequest): Promise<ProviderKey> {
  return apiPost<SaveKeyRequest, ProviderKey>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/keys`,
    body,
  );
}

/**
 * DELETE /api/workspaces/{workspaceId}/keys
 * Clears the stored key, ai_provider, and ai_model for this workspace.
 *
 * Uses raw fetch (no apiDelete helper — keeping the change additive per §3.4).
 * Throws an Error with the backend `detail` message on non-2xx responses.
 *
 * @param workspaceId - UUID of the workspace whose key should be deleted.
 * @returns Confirmation message from the backend.
 */
export async function deleteWorkspaceKey(workspaceId: string): Promise<{ message: string }> {
  const r = await fetch(`${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/keys`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

/**
 * POST /api/keys/validate
 * Probes the provider API with the key to verify it is valid — does NOT store it.
 *
 * @param body - Provider and plaintext key to validate.
 * @returns Validation result with `valid` flag and human-readable `message`.
 */
export function validateKey(body: ValidateKeyRequest): Promise<ValidateKeyResponse> {
  return apiPost<ValidateKeyRequest, ValidateKeyResponse>('/api/keys/validate', body);
}

// ---------------------------------------------------------------------------
// Drive wrappers (STORY-006-05)
// ---------------------------------------------------------------------------

/**
 * Google Drive connection status for a workspace.
 * Mirrors backend DriveStatusResponse: connected flag + connected account email.
 */
export interface DriveStatus {
  /** Whether a Google Drive OAuth token is stored for this workspace. */
  connected: boolean;
  /** The Google account email address if connected, or null if not connected. */
  email: string | null;
}

/**
 * Document source — where the document originated.
 *
 * - `google_drive` — indexed from Google Drive via the Picker widget.
 * - `upload`       — uploaded directly by the user (EPIC-014).
 * - `agent`        — created by the Tee-Mo agent tool (STORY-015-03).
 */
export type DocumentSource = 'google_drive' | 'upload' | 'agent';

/**
 * A single knowledge document record returned by the knowledge CRUD endpoints.
 * Mirrors backend/app/models/knowledge.py::KnowledgeIndexResponse (STORY-015-02).
 *
 * STORY-015-02 shape changes vs original STORY-006-03:
 *   - Added `source` (google_drive | upload | agent).
 *   - Added `doc_type` (google_doc, pdf, docx, xlsx, google_sheet, google_slides).
 *   - `external_id` is the canonical Drive file ID (replaces `drive_file_id`).
 *   - `external_link` is the canonical URL (replaces `link`).
 *   - `mime_type` removed from backend response — use `doc_type` instead.
 *   - Backward-compat fields kept optional for any cached responses.
 */
export interface KnowledgeFile {
  /** UUID primary key for this knowledge file record. */
  id: string;
  /** UUID of the workspace this file belongs to. */
  workspace_id: string;
  /** Human-readable file title. */
  title: string;
  /**
   * Document source — determines badge and link rendering behavior.
   * Only `google_drive` documents have an `external_link`.
   * Optional for backward-compat with records created before STORY-015-02.
   */
  source?: DocumentSource | null;
  /**
   * Document type derived from MIME type.
   * e.g. "google_doc", "pdf", "docx", "xlsx", "google_sheet", "google_slides".
   * Optional for backward-compat with records created before STORY-015-02.
   */
  doc_type?: string | null;
  /**
   * Google Drive file ID (canonical column in teemo_documents).
   * Null for upload/agent documents that have no external file ID.
   * Optional for backward-compat with records created before STORY-015-02.
   */
  external_id?: string | null;
  /**
   * Direct URL to the source document.
   * Only present for `google_drive` documents — null for upload/agent.
   * Use this (not the legacy `link` field) to render external link icons.
   * Optional for backward-compat with records created before STORY-015-02.
   */
  external_link?: string | null;
  /** AI-generated description of the document content. */
  ai_description: string | null;
  /** SHA-256 hash of the extracted content for change detection. */
  content_hash: string | null;
  /** ISO 8601 timestamp when this record was created. */
  created_at: string | null;
  /** ISO 8601 timestamp of the last successful content scan. */
  last_scanned_at: string | null;
  /**
   * Optional warning message when file content was truncated.
   * Present when the file exceeded 50,000 characters and was cut short.
   */
  warning?: string;
  // ---------------------------------------------------------------------------
  // Backward-compat fields (STORY-006-03 shape) — kept optional so cached API
  // responses do not break before the backend migration is fully deployed.
  // ---------------------------------------------------------------------------
  /** @deprecated Use `external_id`. Kept for backward compatibility. */
  drive_file_id?: string | null;
  /** @deprecated Use `external_link`. Kept for backward compatibility. */
  link?: string | null;
  /** @deprecated Use `doc_type`. Kept for backward compatibility. */
  mime_type?: string | null;
}

/**
 * Short-lived access token pair returned by the picker-token endpoint.
 * Used to initialise the Google Picker API widget without exposing
 * long-lived OAuth tokens to the frontend.
 */
export interface PickerToken {
  /** Short-lived Google OAuth access token scoped to Google Picker. */
  access_token: string;
  /** Google Cloud project API key — controls Picker API quota. */
  picker_api_key: string;
}

/**
 * Request body for indexing a Google Drive file into the knowledge base.
 * Sent to POST /api/workspaces/{id}/knowledge after the user picks a file.
 */
export interface IndexFileRequest {
  /** Google Drive file ID from the Picker callback. */
  drive_file_id: string;
  /** File title from the Picker callback. */
  title: string;
  /** Direct link to the file in Google Drive. */
  link: string;
  /** MIME type from the Picker callback. */
  mime_type: string;
  /** Short-lived access token from picker-token endpoint. Used for initial file fetch
   *  since drive.file scope ties access to the Picker session, not the refresh token. */
  access_token?: string;
}

/**
 * GET /api/workspaces/{workspaceId}/drive/status
 * Returns whether Google Drive is connected for this workspace and which
 * Google account was used.
 *
 * @param workspaceId - UUID of the workspace to check Drive status for.
 * @returns Drive connection status including connected flag and email.
 */
export function getDriveStatus(workspaceId: string): Promise<DriveStatus> {
  return apiGet<DriveStatus>(`/api/workspaces/${encodeURIComponent(workspaceId)}/drive/status`);
}

/**
 * POST /api/workspaces/{workspaceId}/drive/disconnect
 * Revokes the stored Google Drive OAuth token and clears the Drive connection.
 *
 * @param workspaceId - UUID of the workspace whose Drive connection should be cleared.
 * @returns Confirmation with status field.
 */
export function disconnectDrive(workspaceId: string): Promise<{ status: string }> {
  return apiPost<Record<string, never>, { status: string }>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/drive/disconnect`,
    {},
  );
}

/**
 * GET /api/workspaces/{workspaceId}/drive/picker-token
 * Returns a short-lived access token and API key for initialising the Google Picker.
 *
 * The token is scoped to the connected Google account and expires in ~1 hour.
 * Must only be called when Drive is connected (getDriveStatus.connected === true).
 *
 * @param workspaceId - UUID of the workspace whose Drive OAuth token to use.
 * @returns Short-lived access token + Picker API key.
 */
export function getPickerToken(workspaceId: string): Promise<PickerToken> {
  return apiGet<PickerToken>(`/api/workspaces/${encodeURIComponent(workspaceId)}/drive/picker-token`);
}

/**
 * GET /api/workspaces/{workspaceId}/knowledge
 * Returns all indexed knowledge files for a workspace.
 *
 * @param workspaceId - UUID of the workspace whose knowledge files to list.
 * @returns Array of indexed knowledge file records.
 */
export function listKnowledgeFiles(workspaceId: string): Promise<KnowledgeFile[]> {
  return apiGet<KnowledgeFile[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge`);
}

/**
 * POST /api/workspaces/{workspaceId}/knowledge
 * Triggers AI description generation and indexes a Google Drive file into the
 * workspace knowledge base.
 *
 * This is a long-running operation (seconds to tens of seconds) while the
 * backend fetches the file content and generates an AI description.
 * The response includes a `warning` field if the file content was truncated.
 *
 * @param workspaceId - UUID of the workspace to index the file into.
 * @param body        - Drive file metadata from the Google Picker callback.
 * @returns The newly created knowledge file record, potentially with a truncation warning.
 */
export function indexKnowledgeFile(workspaceId: string, body: IndexFileRequest): Promise<KnowledgeFile> {
  return apiPost<IndexFileRequest, KnowledgeFile>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge`,
    body,
  );
}

// ---------------------------------------------------------------------------
// Channel Binding wrappers (STORY-008-02)
// ---------------------------------------------------------------------------

/**
 * A Slack channel returned by GET /api/slack/teams/{teamId}/channels.
 * Mirrors the Slack conversations.list response shape (id, name, is_private).
 */
export interface SlackChannel {
  /** Slack-assigned channel identifier, e.g. "C001". */
  id: string;
  /** Human-readable channel name without the "#" prefix. */
  name: string;
  /** Whether the channel is private (true) or public (false). */
  is_private: boolean;
  /** Workspace ID this channel is bound to, or null/undefined if unbound. */
  bound_workspace_id?: string | null;
}

/**
 * A channel binding record returned by GET /api/workspaces/{workspaceId}/channels.
 * Enriched server-side with channel_name and is_member from the Slack API.
 */
export interface ChannelBinding {
  /** Slack channel ID bound to this workspace. */
  slack_channel_id: string;
  /** UUID of the workspace this binding belongs to. */
  workspace_id: string;
  /** ISO 8601 timestamp when the channel was bound. */
  bound_at: string;
  /** Human-readable channel name (from Slack API enrichment). */
  channel_name?: string;
  /** Whether the Tee-Mo bot is a member of the channel (from conversations.info). */
  is_member?: boolean;
}

/**
 * GET /api/slack/teams/{teamId}/channels — lists all Slack channels in a team.
 *
 * Returns channels the bot token can see (public + private where bot is member).
 * Requires a valid session cookie and ownership of the Slack team.
 *
 * @param teamId - The Slack team ID (e.g. "T0123ABCDEF").
 * @returns Array of Slack channel records.
 */
export function listSlackTeamChannels(teamId: string): Promise<SlackChannel[]> {
  return apiGet<SlackChannel[]>(`/api/slack/teams/${encodeURIComponent(teamId)}/channels`);
}

/**
 * GET /api/workspaces/{workspaceId}/channels — lists all channel bindings for a workspace.
 *
 * Results are enriched server-side with channel_name and is_member fields
 * via Slack conversations.info calls.
 *
 * @param workspaceId - UUID of the workspace to list channel bindings for.
 * @returns Array of enriched channel binding records.
 */
export function listChannelBindings(workspaceId: string): Promise<ChannelBinding[]> {
  return apiGet<ChannelBinding[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/channels`);
}

/**
 * POST /api/workspaces/{workspaceId}/channels — binds a Slack channel to a workspace.
 *
 * The bot must be invited to the channel separately (hence is_member may be false
 * immediately after binding). Throws a 409 error if the channel is already bound.
 *
 * @param workspaceId - UUID of the workspace to bind the channel to.
 * @param channelId   - The Slack channel ID to bind (e.g. "C001").
 * @returns The created channel binding record.
 */
export function bindChannel(workspaceId: string, channelId: string): Promise<ChannelBinding> {
  return apiPost<{ slack_channel_id: string }, ChannelBinding>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/channels`,
    { slack_channel_id: channelId },
  );
}

/**
 * DELETE /api/workspaces/{workspaceId}/channels/{channelId} — unbinds a Slack channel.
 *
 * Uses raw fetch (no apiDelete helper) to match existing delete pattern.
 * Throws an Error with the backend `detail` message on non-2xx responses.
 *
 * @param workspaceId - UUID of the workspace the channel is bound to.
 * @param channelId   - The Slack channel ID to unbind (e.g. "C001").
 * @returns void (HTTP 204 No Content).
 */
export async function unbindChannel(workspaceId: string, channelId: string): Promise<void> {
  const r = await fetchWithAuth(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/channels/${encodeURIComponent(channelId)}`,
    { method: 'DELETE' },
  );
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
}

/**
 * DELETE /api/workspaces/{workspaceId}/knowledge/{knowledgeId}
 * Removes an indexed knowledge file from the workspace knowledge base.
 *
 * Uses raw fetch (no apiDelete helper) to match the pattern established by
 * `deleteWorkspaceKey` — keeping the change additive per story scope.
 * Throws an Error with the backend `detail` message on non-2xx responses.
 *
 * @param workspaceId - UUID of the workspace the file belongs to.
 * @param knowledgeId - UUID of the knowledge file record to remove.
 * @returns Confirmation with status field.
 */
export async function removeKnowledgeFile(workspaceId: string, knowledgeId: string): Promise<{ status: string }> {
  const r = await fetchWithAuth(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/${encodeURIComponent(knowledgeId)}`,
    { method: 'DELETE' },
  );
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}

/**
 * Response shape returned by POST /api/workspaces/{workspaceId}/knowledge/reindex.
 * Indicates how many files were successfully re-indexed and how many failed.
 */
export interface ReindexResult {
  /** Number of files successfully re-extracted and updated. */
  reindexed: number;
  /** Number of files that were skipped (unchanged on Drive). */
  skipped: number;
  /** Number of files that failed during re-indexing. */
  failed: number;
  /** Per-file error details for each failure. */
  errors: Array<{ file_id: string; error: string }>;
}

/**
 * POST /api/workspaces/{workspaceId}/knowledge/reindex
 * Re-extracts all indexed files from Google Drive, regenerates AI descriptions,
 * and updates ``cached_content``, ``content_hash``, ``ai_description``, and
 * ``last_scanned_at`` for each row.
 *
 * This is a long-running operation (seconds to minutes depending on file count).
 * Requires both a BYOK key and Google Drive to be connected — returns a 400 error
 * otherwise. Per-file failures do not abort the run; they are collected in ``errors``.
 *
 * @param workspaceId - UUID of the workspace whose files to re-index.
 * @returns ReindexResult with counts and any per-file errors.
 * @throws Error with backend ``detail`` message on non-2xx (e.g. 400, 401, 404).
 */
export function reindexKnowledge(workspaceId: string): Promise<ReindexResult> {
  return apiPost<Record<string, never>, ReindexResult>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/reindex`,
    {},
  );
}

// ---------------------------------------------------------------------------
// Automation wrappers (STORY-018-05)
// ---------------------------------------------------------------------------

import type {
  Automation,
  AutomationCreate,
  AutomationUpdate,
  AutomationExecution,
  TestRunResult,
} from '../types/automation';

// Re-export so consumers can import from api.ts directly.
export type { Automation, AutomationCreate, AutomationUpdate, AutomationExecution, TestRunResult };

/**
 * GET /api/workspaces/{workspaceId}/automations
 * Returns all automations configured for a workspace, newest first.
 *
 * @param workspaceId - UUID of the workspace to list automations for.
 * @returns Array of Automation records.
 */
export function listAutomations(workspaceId: string): Promise<Automation[]> {
  return apiGet<Automation[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/automations`);
}

/**
 * POST /api/workspaces/{workspaceId}/automations
 * Creates a new automation for the given workspace.
 *
 * Throws HTTP 409 if an automation with the same name already exists.
 * Throws HTTP 422 if the schedule dict is invalid.
 *
 * @param workspaceId - UUID of the workspace to create the automation in.
 * @param body        - Automation creation payload.
 * @returns The newly created Automation record.
 */
export function createAutomation(workspaceId: string, body: AutomationCreate): Promise<Automation> {
  return apiPost<AutomationCreate, Automation>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/automations`,
    body,
  );
}

/**
 * PATCH /api/workspaces/{workspaceId}/automations/{automationId}
 * Partially updates an automation (toggle is_active, rename, reschedule, etc.).
 *
 * Only fields present in the body are updated. Throws HTTP 404 if not found.
 *
 * @param workspaceId  - UUID of the workspace that owns the automation.
 * @param automationId - UUID of the automation to update.
 * @param body         - Partial update payload.
 * @returns The updated Automation record.
 */
export function updateAutomation(
  workspaceId: string,
  automationId: string,
  body: AutomationUpdate,
): Promise<Automation> {
  return apiPatch<AutomationUpdate, Automation>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/automations/${encodeURIComponent(automationId)}`,
    body,
  );
}

/**
 * DELETE /api/workspaces/{workspaceId}/automations/{automationId}
 * Permanently deletes an automation and its execution history.
 *
 * Returns void (HTTP 204 No Content) on success.
 * Throws an Error with backend `detail` on non-2xx responses.
 *
 * @param workspaceId  - UUID of the workspace that owns the automation.
 * @param automationId - UUID of the automation to delete.
 */
export async function deleteAutomation(workspaceId: string, automationId: string): Promise<void> {
  const r = await fetchWithAuth(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/automations/${encodeURIComponent(automationId)}`,
    { method: 'DELETE' },
  );
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
}

/**
 * GET /api/workspaces/{workspaceId}/automations/{automationId}/history
 * Returns the execution history for a specific automation, newest first.
 *
 * @param workspaceId  - UUID of the workspace that owns the automation.
 * @param automationId - UUID of the automation to fetch history for.
 * @returns Array of AutomationExecution records, newest first.
 */
export function getAutomationHistory(
  workspaceId: string,
  automationId: string,
): Promise<AutomationExecution[]> {
  return apiGet<AutomationExecution[]>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/automations/${encodeURIComponent(automationId)}/history`,
  );
}

/**
 * POST /api/workspaces/{workspaceId}/automations/test-run
 * Runs a prompt against the workspace's BYOK model without persisting to Slack.
 *
 * NOTE (FLASHCARD 2026-04-24 #frontend #epic-018): endpoint is
 * `/automations/test-run` — NOT `/{automation_id}/dry-run`.
 * Body shape: `{ prompt, timezone?, description? }`.
 *
 * Always returns HTTP 200; check `result.success` for failure conditions.
 *
 * @param workspaceId - UUID of the workspace to run the test against.
 * @param body        - Test-run request with prompt (required), timezone, description.
 * @returns TestRunResult with success flag, output, error, and token/timing info.
 */
export function testRunAutomation(
  workspaceId: string,
  body: { prompt: string; timezone?: string; description?: string },
): Promise<TestRunResult> {
  return apiPost<{ prompt: string; timezone?: string; description?: string }, TestRunResult>(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/automations/test-run`,
    body,
  );
}

/**
 * POST /api/workspaces/{workspaceId}/documents/upload
 * Uploads a local file to the workspace knowledge base (STORY-014-03).
 *
 * Sends a multipart/form-data request with a single `file` field.
 * The Content-Type header is intentionally NOT set manually — the browser
 * automatically sets `multipart/form-data` with the correct boundary when
 * the body is a FormData instance.
 *
 * @param workspaceId - UUID of the workspace to upload the file into.
 * @param file        - File object selected by the user.
 * @returns The created KnowledgeFile record (same shape as the Drive index rows).
 * @throws Error with backend `detail` message on non-2xx (e.g. 400, 409, 413).
 */
export async function uploadKnowledgeFile(workspaceId: string, file: File): Promise<KnowledgeFile> {
  const form = new FormData();
  form.append('file', file);
  const r = await fetchWithAuth(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/documents/upload`,
    {
      method: 'POST',
      body: form,
      // Content-Type is NOT set — browser sets multipart/form-data with boundary automatically.
    },
  );
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
  return r.json() as Promise<KnowledgeFile>;
}

// ---------------------------------------------------------------------------
// Skills wrappers (STORY-023-01)
// ---------------------------------------------------------------------------

/**
 * A single active skill record returned by GET /api/workspaces/{id}/skills.
 * Mirrors the L1 catalog shape from backend skill_service.list_skills:
 * only ``name`` and ``summary`` are included — instructions are server-only.
 */
export interface Skill {
  /** Slug identifier, e.g. "daily-standup". */
  name: string;
  /** Short "Use when..." description. Max 160 chars. */
  summary: string;
}

/**
 * GET /api/workspaces/{workspaceId}/skills
 * Returns all active skills configured for a workspace.
 *
 * Skills are created via Slack chat (chat-only CRUD per ADR-023) and are
 * read-only in the dashboard.
 *
 * @param workspaceId - UUID of the workspace to list skills for.
 * @returns Array of Skill records (name + summary). Empty array if none.
 */
export function listWorkspaceSkills(workspaceId: string): Promise<Skill[]> {
  return apiGet<Skill[]>(`/api/workspaces/${encodeURIComponent(workspaceId)}/skills`);
}
