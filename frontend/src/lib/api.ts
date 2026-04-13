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
  const res = await fetch(`${API_URL}/api/slack/teams/${teamId}`, {
    method: 'DELETE',
    credentials: 'include',
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
  const r = await fetch(`${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'DELETE',
    credentials: 'include',
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
 * A single indexed knowledge file record returned by the knowledge CRUD endpoints.
 * Mirrors backend/app/models/knowledge.py::KnowledgeFileResponse (STORY-006-03).
 */
export interface KnowledgeFile {
  /** UUID primary key for this knowledge file record. */
  id: string;
  /** UUID of the workspace this file belongs to. */
  workspace_id: string;
  /** Google Drive file ID. */
  drive_file_id: string;
  /** Human-readable file title from Google Drive. */
  title: string;
  /** Direct link to the file in Google Drive. */
  link: string;
  /** MIME type of the file (e.g. "application/vnd.google-apps.document"). */
  mime_type: string;
  /** AI-generated description of the file content. */
  ai_description: string;
  /** SHA-256 hash of the extracted file content for change detection. */
  content_hash: string;
  /** ISO 8601 timestamp when this record was created. */
  created_at: string | null;
  /** ISO 8601 timestamp of the last successful content scan. */
  last_scanned_at: string | null;
  /**
   * Optional warning message when file content was truncated.
   * Present when the file exceeded 50,000 characters and was cut short.
   */
  warning?: string;
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
  const r = await fetch(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/channels/${encodeURIComponent(channelId)}`,
    {
      method: 'DELETE',
      credentials: 'include',
    },
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
  const r = await fetch(
    `${API_URL}/api/workspaces/${encodeURIComponent(workspaceId)}/knowledge/${encodeURIComponent(knowledgeId)}`,
    {
      method: 'DELETE',
      credentials: 'include',
    },
  );
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    throw new Error(payload?.detail ?? `HTTP ${r.status}`);
  }
  return r.json();
}
