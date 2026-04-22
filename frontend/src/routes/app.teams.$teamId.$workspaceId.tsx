/**
 * /app/teams/$teamId/$workspaceId — Workspace detail page (STORY-006-05).
 *
 * Displays Drive connection status, a Google Picker button for indexing files,
 * and the list of indexed knowledge files for a specific workspace.
 *
 * Route params:
 *   - `teamId`      — Slack team ID (e.g. "T0123ABCDEF")
 *   - `workspaceId` — workspace UUID
 *
 * Layout sections:
 *   1. DriveSection   — Connect / Disconnect Google Drive
 *   2. PickerSection  — "Add File" button (gated by Drive + BYOK) + file count
 *   3. KnowledgeList  — table of indexed files with Remove action
 *
 * Design system (ADR-022):
 *   - Coral brand: text-rose-500, bg-brand-500
 *   - Slate neutrals for backgrounds and text
 *   - Inter font (inherited from app.css)
 *   - Max font weight: font-semibold (600) — never font-bold
 *   - Tailwind 4 built-ins only — no new @theme tokens
 *
 * Google Picker integration:
 *   - `gapi` script loaded dynamically once (checked via `window.gapi`)
 *   - On "Add File" click: fetch picker token → gapi.load('picker') → PickerBuilder
 *   - File select callback → POST to /api/workspaces/{id}/knowledge
 *   - Shows loading state while AI description is generated (backend is ~5-30s)
 *   - Shows truncation warning toast if response.warning is present (R8)
 *
 * BYOK gate (R6): picker button disabled with explanatory message when
 *   `useKeyQuery(workspaceId).data.has_key !== true`.
 * 15-file cap (R5): picker button disabled with count badge when files.length >= 15.
 */
import { useState, useCallback } from 'react';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Badge } from '../components/ui/Badge';
import { Card } from '../components/ui/Card';
import { useWorkspaceQuery } from '../hooks/useWorkspaces';
import { useKeyQuery } from '../hooks/useKey';
import { useDriveStatusQuery, useDisconnectDriveMutation } from '../hooks/useDrive';
import { useKnowledgeQuery, useAddKnowledgeMutation, useRemoveKnowledgeMutation, useReindexKnowledgeMutation } from '../hooks/useKnowledge';
import { useSkillsQuery } from '../hooks/useSkills';
import { getPickerToken, deleteWorkspace, type KnowledgeFile, type DocumentSource, type Skill } from '../lib/api';
import { SetupStepper } from '../components/workspace/SetupStepper';
import { ChannelSection } from '../components/workspace/ChannelSection';

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * TanStack Router file-based route for /app/teams/$teamId/$workspaceId.
 * Params available via `Route.useParams()`.
 */
export const Route = createFileRoute('/app/teams/$teamId/$workspaceId')({
  component: WorkspaceDetailPage,
});

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum number of files that can be indexed per workspace (R5). */
const MAX_FILES = 100;

/** Google API client script URL for loading the Picker API. */
const GAPI_SCRIPT_URL = 'https://apis.google.com/js/api.js';

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

/**
 * Loads the Google API client script into the document if it hasn't been
 * loaded yet. Resolves when the script is ready. Idempotent — safe to call
 * multiple times; only injects the script once.
 *
 * @returns A promise that resolves once the gapi global is available.
 */
function loadGapiScript(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof gapi !== 'undefined') {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = GAPI_SCRIPT_URL;
    script.onload = () => resolve();
    document.head.appendChild(script);
  });
}

/**
 * Returns a human-readable file type label derived from the `doc_type` field
 * (STORY-015-02 canonical field) or the legacy `mime_type` string (fallback for
 * records created before the teemo_documents migration).
 *
 * @param docType  - doc_type value from the new API shape, e.g. "google_doc".
 * @param mimeType - MIME type string from the legacy API shape (fallback).
 * @returns Short label string, e.g. "Doc", "Sheet", "Slide", "PDF", "MD", "File".
 */
function docTypeLabel(docType: string | null | undefined, mimeType: string | null | undefined): string {
  // Prefer new canonical doc_type field
  if (docType) {
    switch (docType) {
      case 'google_doc':     return 'Doc';
      case 'google_sheet':   return 'Sheet';
      case 'google_slides':  return 'Slide';
      case 'pdf':            return 'PDF';
      case 'docx':           return 'DOCX';
      case 'xlsx':           return 'XLSX';
      case 'markdown':       return 'MD';
      default:               return docType.toUpperCase().slice(0, 6);
    }
  }
  // Fall back to legacy mime_type for old records
  if (mimeType) {
    if (mimeType.includes('document'))     return 'Doc';
    if (mimeType.includes('spreadsheet'))  return 'Sheet';
    if (mimeType.includes('presentation')) return 'Slide';
    if (mimeType === 'application/pdf')    return 'PDF';
  }
  return 'File';
}

/**
 * Returns the Badge variant and label text for a document source.
 *
 * Source badge design (Design Guide §2.2 — functional color only):
 *   - `google_drive` → neutral/slate — understated, already has a link icon
 *   - `upload`       → info/sky — subtle blue to distinguish from Drive
 *   - `agent`        → no built-in brand variant, so we use `info` with a
 *                       purple-ish override via className (brand is reserved
 *                       for primary CTAs — using a separate `agent` visual
 *                       without violating the "one accent per screen" rule)
 *
 * NOTE: The Badge component only supports 5 semantic variants (success, warning,
 * danger, info, neutral). `agent` maps to `info` variant with a className override
 * so as not to add a new variant to the shared component.
 *
 * @param source - DocumentSource value from the API response.
 * @returns Object with Badge `variant` and `label` string.
 */
function sourceBadgeProps(source: DocumentSource | null): {
  variant: 'neutral' | 'info';
  label: string;
  className?: string;
} {
  switch (source) {
    case 'google_drive':
      return { variant: 'neutral', label: 'Drive' };
    case 'upload':
      return { variant: 'info', label: 'Upload' };
    case 'agent':
      // Purple tint for agent-created docs without adding a new Badge variant.
      // Uses inline Tailwind overrides — stays within Tailwind 4 built-ins.
      return {
        variant: 'info',
        label: 'Agent',
        className: '!bg-purple-50 !text-purple-700 [&>span]:!bg-purple-400',
      };
    default:
      return { variant: 'neutral', label: 'File' };
  }
}

// ---------------------------------------------------------------------------
// DriveSection
// ---------------------------------------------------------------------------

/** Props for DriveSection. */
interface DriveSectionProps {
  workspaceId: string;
}

/**
 * DriveSection — shows Google Drive connection status with Connect/Disconnect actions.
 *
 * Connected state: "Connected as user@example.com" + "Disconnect" button.
 *   Disconnect calls useDisconnectDriveMutation which invalidates the drive-status
 *   cache so the section re-renders immediately.
 *
 * Not connected state: "Google Drive not connected" + "Connect Google Drive" button.
 *   The connect button performs a full-page redirect to the backend OAuth initiation
 *   endpoint (same pattern as Slack install — browser must carry the session cookie).
 *
 * @param workspaceId - UUID of the workspace to check/modify Drive connection for.
 */
function DriveSection({ workspaceId }: DriveSectionProps) {
  const { data: driveStatus, isLoading } = useDriveStatusQuery(workspaceId);
  const disconnectMutation = useDisconnectDriveMutation(workspaceId);

  if (isLoading) {
    return (
      <Card className="animate-pulse">
        <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
        <div className="h-3 w-1/2 rounded bg-slate-100" />
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900 mb-3">Google Drive</h2>

      {driveStatus?.connected ? (
        /* Connected state */
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-slate-700">
            Connected as{' '}
            <span className="font-semibold text-slate-900">{driveStatus.email}</span>
          </span>
          <button
            type="button"
            onClick={() => disconnectMutation.mutate()}
            disabled={disconnectMutation.isPending}
            className="text-sm font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
          >
            {disconnectMutation.isPending ? 'Disconnecting…' : 'Disconnect'}
          </button>
          {disconnectMutation.error && (
            <p className="w-full text-xs text-rose-600" role="alert">
              {disconnectMutation.error instanceof Error
                ? disconnectMutation.error.message
                : 'Failed to disconnect. Please try again.'}
            </p>
          )}
        </div>
      ) : (
        /* Not connected state */
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm text-slate-500">Google Drive not connected.</span>
          {/* Full-page redirect: browser must carry session cookie to OAuth endpoint */}
          <a
            href={`/api/workspaces/${encodeURIComponent(workspaceId)}/drive/connect`}
            className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600"
          >
            Connect Google Drive
          </a>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// PickerSection
// ---------------------------------------------------------------------------

/** Props for PickerSection. */
interface PickerSectionProps {
  workspaceId: string;
  /** Whether Google Drive is currently connected for this workspace. */
  driveConnected: boolean;
  /** Whether a BYOK key is configured for this workspace. */
  hasKey: boolean;
  /** Current count of indexed knowledge files. */
  fileCount: number;
  /**
   * Callback invoked after a file is successfully indexed.
   * Receives the new KnowledgeFile record (including any warning).
   */
  onFileIndexed: (file: KnowledgeFile) => void;
  /** Callback when indexing state changes — for showing a visible progress banner. */
  onIndexingChange?: (indexing: boolean) => void;
}

/** Result state for the reindex operation, shown inline after completion. */
interface ReindexFeedback {
  reindexed: number;
  skipped: number;
  failed: number;
}

/**
 * PickerSection — "Add File" button with Google Picker integration.
 *
 * Button disabled conditions (in priority order):
 *   1. Drive not connected — shows "Connect Drive first" tooltip
 *   2. No BYOK key — shows "Configure an API key first" message below button
 *   3. File cap reached (fileCount >= 15) — button text shows "15/15 files"
 *
 * On click:
 *   1. Fetches a short-lived picker token from the backend
 *   2. Loads gapi script if not already present
 *   3. gapi.load('picker') → builds PickerBuilder with OAuth token + API key
 *   4. User selects a file → callback fires → POST to /knowledge endpoint
 *   5. Shows loading state while backend generates AI description
 *   6. Calls onFileIndexed with the result (caller handles truncation warning)
 *
 * @param props - See PickerSectionProps.
 */
function PickerSection({
  workspaceId,
  driveConnected,
  hasKey,
  fileCount,
  onFileIndexed,
  onIndexingChange,
}: PickerSectionProps) {
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reindexFeedback, setReindexFeedback] = useState<ReindexFeedback | null>(null);

  const addKnowledgeMutation = useAddKnowledgeMutation(workspaceId);
  const reindexMutation = useReindexKnowledgeMutation(workspaceId);

  const atCap = fileCount >= MAX_FILES;
  const buttonDisabled = !driveConnected || !hasKey || atCap || indexing;

  /**
   * Opens the Google Picker dialog.
   * Handles token fetch, script load, and picker construction.
   */
  const handleOpenPicker = useCallback(async () => {
    setError(null);
    try {
      // Fetch short-lived picker token from backend
      const { access_token, picker_api_key } = await getPickerToken(workspaceId);

      // Load gapi script if needed
      await loadGapiScript();

      // Load the picker module then build and open the picker
      gapi.load('picker', () => {
        const picker = new google.picker.PickerBuilder()
          .setOAuthToken(access_token)
          .setDeveloperKey(picker_api_key)
          .addView(google.picker.ViewId.DOCS)
          .setCallback(async (data: google.picker.CallbackData) => {
            if (data.action !== google.picker.Action.PICKED) return;
            const doc = data.docs?.[0];
            if (!doc) return;

            setIndexing(true);
            onIndexingChange?.(true);
            try {
              const result = await addKnowledgeMutation.mutateAsync({
                drive_file_id: doc.id,
                title: doc.name,
                link: doc.url,
                mime_type: doc.mimeType,
                access_token,
              });
              onFileIndexed(result);
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to index file.');
            } finally {
              setIndexing(false);
              onIndexingChange?.(false);
            }
          })
          .build();

        picker.setVisible(true);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open file picker.');
    }
  }, [workspaceId, addKnowledgeMutation, onFileIndexed]);

  /** Handles the Re-index All Files button click. */
  const handleReindex = useCallback(async () => {
    setReindexFeedback(null);
    try {
      const result = await reindexMutation.mutateAsync();
      setReindexFeedback({ reindexed: result.reindexed, skipped: result.skipped, failed: result.failed });
    } catch {
      // error surfaced via reindexMutation.error
    }
  }, [reindexMutation]);

  /** Re-index button is disabled when there are no files, Drive/key missing, or pending. */
  const reindexDisabled =
    fileCount === 0 || !driveConnected || !hasKey || reindexMutation.isPending || indexing;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
        <h2 className="text-base font-semibold text-slate-900">Knowledge Files</h2>

        {/* File count indicator + action buttons */}
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">
            {fileCount}/{MAX_FILES} files
          </span>
          {/* Re-index All Files button — only shown when files exist */}
          {fileCount > 0 && (
            <button
              type="button"
              onClick={handleReindex}
              disabled={reindexDisabled}
              title={
                !driveConnected
                  ? 'Connect Drive first'
                  : !hasKey
                    ? 'Configure an API key first'
                    : undefined
              }
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {reindexMutation.isPending ? 'Re-indexing…' : 'Re-index All Files'}
            </button>
          )}
          <button
            type="button"
            onClick={handleOpenPicker}
            disabled={buttonDisabled}
            title={
              !driveConnected
                ? 'Connect Drive first'
                : atCap
                  ? `${MAX_FILES} file limit reached`
                  : undefined
            }
            className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {indexing ? 'Indexing…' : 'Add File'}
          </button>
        </div>
      </div>

      {/* BYOK gate message (R6) */}
      {driveConnected && !hasKey && (
        <p className="text-xs text-amber-600 mt-1">
          Configure an API key first to enable file indexing.
        </p>
      )}

      {/* Indexing error */}
      {error && (
        <p className="text-xs text-rose-600 mt-1" role="alert">
          {error}
        </p>
      )}

      {/* Re-index error */}
      {reindexMutation.error && (
        <p className="text-xs text-rose-600 mt-1" role="alert">
          {reindexMutation.error instanceof Error
            ? reindexMutation.error.message
            : 'Re-index failed. Please try again.'}
        </p>
      )}

      {/* Re-index success feedback */}
      {reindexFeedback && (
        <p className="text-xs text-slate-600 mt-1">
          Re-indexed {reindexFeedback.reindexed} file{reindexFeedback.reindexed !== 1 ? 's' : ''}
          { (reindexFeedback.skipped > 0 || reindexFeedback.failed > 0) && (
            <span>
              {' '}
              ({[
                reindexFeedback.skipped > 0 ? `${reindexFeedback.skipped} skipped` : null,
                reindexFeedback.failed > 0 ? `${reindexFeedback.failed} failed — check Drive permissions` : null
              ].filter(Boolean).join(', ')})
            </span>
          )}
          {reindexFeedback.failed === 0 ? ' successfully.' : ''}
        </p>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// KnowledgeList
// ---------------------------------------------------------------------------

/** Props for KnowledgeList. */
interface KnowledgeListProps {
  workspaceId: string;
  files: KnowledgeFile[];
  isLoading: boolean;
}

/**
 * KnowledgeList — cards of indexed knowledge documents with source badges and Remove actions.
 *
 * Each document card shows (STORY-015-06):
 *   - Source badge (Drive / Upload / Agent) derived from `file.source`.
 *   - Title as an external link when `file.external_link` is present (Drive docs only).
 *     Upload and agent documents render the title as plain text — no link icon.
 *   - AI description truncated to ~100 characters.
 *   - Remove button (all document types deletable — backend enforces ownership).
 *
 * Legacy `mime_type` / `link` fields from STORY-006-03 are supported via the
 * backward-compat fields on `KnowledgeFile` — the component prefers the new
 * fields (`external_link`, `source`) and falls back to old ones gracefully.
 *
 * Empty state: "No files indexed yet. Use the picker above to add files."
 * Loading state: skeleton rows.
 *
 * @param workspaceId - UUID of the workspace (used by remove mutation).
 * @param files       - Array of knowledge document records to display.
 * @param isLoading   - Whether the knowledge query is loading.
 */
function KnowledgeList({ workspaceId, files, isLoading }: KnowledgeListProps) {
  const removeMutation = useRemoveKnowledgeMutation(workspaceId);

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse rounded-lg border border-slate-200 bg-white p-4">
            <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
            <div className="h-3 w-2/3 rounded bg-slate-100" />
          </div>
        ))}
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <Card className="py-10 text-center">
        <p className="text-sm text-slate-500">
          No files indexed yet. Use the picker above to add files.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      {files.map((file) => {
        // Resolve canonical link — prefer new `external_link`, fall back to legacy `link`.
        const externalLink = file.external_link ?? file.link ?? null;
        // Resolve source badge props. Fall back to 'google_drive' when source is missing
        // and a legacy link exists (old Drive records pre-015-02 migration).
        const effectiveSource: DocumentSource | null =
          file.source ?? (externalLink ? 'google_drive' : null);
        const { variant, label, className: badgeClassName } = sourceBadgeProps(effectiveSource);

        return (
          <Card key={file.id} className="p-4">
            <div className="flex items-start justify-between gap-4">
              {/* Document info */}
              <div className="min-w-0 flex-1">
                {/* Source badge + title row (R2, R3) */}
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  {/* Source badge — Drive / Upload / Agent (R2) */}
                  <Badge variant={variant} className={`shrink-0 ${badgeClassName ?? ''}`}>
                    {label}
                  </Badge>

                  {/* Document type label — Doc / Sheet / Slide / PDF / MD / etc. */}
                  <span className="text-xs bg-slate-100 text-slate-600 rounded px-1.5 py-0.5 font-semibold shrink-0">
                    {docTypeLabel(file.doc_type, file.mime_type)}
                  </span>

                  {/* Title: link for Drive docs (external_link present), plain text otherwise */}
                  {externalLink ? (
                    <a
                      href={externalLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-semibold text-slate-900 truncate hover:text-rose-500 min-w-0"
                    >
                      {file.title}
                    </a>
                  ) : (
                    <span className="text-sm font-semibold text-slate-900 truncate min-w-0">
                      {file.title}
                    </span>
                  )}
                </div>

                {/* AI description (truncated to ~100 chars) */}
                {file.ai_description && (
                  <p className="text-xs text-slate-500 line-clamp-2">
                    {file.ai_description.length > 100
                      ? `${file.ai_description.slice(0, 100)}…`
                      : file.ai_description}
                  </p>
                )}
              </div>

              {/* Remove button — all document types are deletable (R4) */}
              <button
                type="button"
                onClick={() => removeMutation.mutate(file.id)}
                disabled={removeMutation.isPending}
                className="shrink-0 text-xs font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
                aria-label={`Remove ${file.title}`}
              >
                {removeMutation.isPending ? 'Removing…' : 'Remove'}
              </button>
            </div>

            {/* Remove error */}
            {removeMutation.error && (
              <p className="mt-1 text-xs text-rose-600" role="alert">
                {removeMutation.error instanceof Error
                  ? removeMutation.error.message
                  : 'Failed to remove file.'}
              </p>
            )}
          </Card>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TruncationToast
// ---------------------------------------------------------------------------

/**
 * TruncationToast — inline banner shown when a just-indexed file was truncated.
 *
 * Displayed for 10 seconds after a successful file index where the response
 * includes a `warning` field (file content > 50,000 chars, R8).
 *
 * @param message - Warning message text from the backend response.
 * @param onDismiss - Callback to dismiss the banner.
 */
function TruncationToast({
  message,
  onDismiss,
}: {
  message: string;
  onDismiss: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex items-start justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800"
    >
      <span>⚠ {message}</span>
      <button
        type="button"
        onClick={onDismiss}
        className="shrink-0 text-xs font-semibold text-amber-700 hover:opacity-70"
        aria-label="Dismiss warning"
      >
        Dismiss
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkillsSection (STORY-023-01)
// ---------------------------------------------------------------------------

/** Props for SkillsSection. */
interface SkillsSectionProps {
  workspaceId: string;
}

/**
 * SkillsSection — read-only list of agent skills configured for a workspace.
 *
 * Skills are created and managed exclusively via Slack chat (ADR-023 chat-only
 * CRUD). This section surfaces the skill catalog so dashboard users can see
 * what the bot has been trained to do without leaving the UI.
 *
 * States:
 *   - Loading  — skeleton cards while the query is in-flight.
 *   - Empty    — helper text explaining skills are created via Slack.
 *   - Populated — one card per skill with name slug + summary.
 *
 * @param workspaceId - UUID of the workspace to list skills for.
 */
function SkillsSection({ workspaceId }: SkillsSectionProps) {
  const { data: skills, isLoading } = useSkillsQuery(workspaceId);

  return (
    <Card>
      <div className="mb-3">
        <h2 className="text-base font-semibold text-slate-900">Active Skills</h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Skills are created by chatting with Tee-Mo in Slack. They appear here automatically.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="animate-pulse rounded-lg border border-slate-100 bg-slate-50 p-3">
              <div className="h-3 w-1/4 rounded bg-slate-200 mb-2" />
              <div className="h-3 w-2/3 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      ) : !skills || skills.length === 0 ? (
        <p className="text-sm text-slate-400 py-4 text-center">
          No skills yet. Teach Tee-Mo new behaviors directly in Slack.
        </p>
      ) : (
        <ul className="space-y-2">
          {skills.map((skill: Skill) => (
            <li
              key={skill.name}
              className="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3"
            >
              <div className="flex items-center gap-2 mb-1">
                <span className="font-mono text-xs font-semibold text-rose-500 bg-rose-50 px-1.5 py-0.5 rounded">
                  {skill.name}
                </span>
              </div>
              <p className="text-xs text-slate-600">{skill.summary}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// DeleteWorkspaceSection
// ---------------------------------------------------------------------------

/** Props for DeleteWorkspaceSection. */
interface DeleteWorkspaceSectionProps {
  workspaceId: string;
  workspaceName: string | undefined;
  teamId: string;
}

/**
 * DeleteWorkspaceSection — danger zone card with a Delete Workspace button and
 * a div-based confirmation dialog.
 *
 * Design: red/danger button matching the coral brand palette. The confirmation
 * dialog uses a div overlay (NOT native `<dialog>`) because jsdom does not
 * support `showModal()` (sprint-context S-10 rule).
 *
 * On confirm:
 *   1. Calls `deleteWorkspace(workspaceId)` via `useMutation`.
 *   2. Invalidates the `['workspaces', teamId]` query cache so the team page
 *      reflects the deletion immediately after redirect.
 *   3. Navigates to `/app/teams/${teamId}` using `useNavigate`.
 *
 * On cancel: dialog is dismissed with no side-effects.
 *
 * @param workspaceId    - UUID of the workspace to delete.
 * @param workspaceName  - Human-readable name for the confirmation message.
 * @param teamId         - Slack team ID for post-delete navigation.
 */
function DeleteWorkspaceSection({ workspaceId, workspaceName, teamId }: DeleteWorkspaceSectionProps) {
  const [showConfirm, setShowConfirm] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => deleteWorkspace(workspaceId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workspaces', teamId] });
      await navigate({ to: '/app/teams/$teamId', params: { teamId } });
    },
  });

  return (
    <Card>
      <h2 className="text-base font-semibold text-slate-900 mb-3">Danger Zone</h2>
      <p className="text-sm text-slate-500 mb-4">
        Permanently delete this workspace and all its knowledge files, channel
        bindings, and API keys. This action cannot be undone.
      </p>
      <button
        type="button"
        onClick={() => setShowConfirm(true)}
        className="rounded-md bg-rose-500 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Delete Workspace
      </button>

      {/* Div-based confirmation dialog overlay (no native <dialog> — jsdom limitation) */}
      {showConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
        >
          <div className="mx-4 w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
            <h3
              id="delete-dialog-title"
              className="text-lg font-semibold text-slate-900 mb-2"
            >
              Delete workspace?
            </h3>
            <p className="text-sm text-slate-600 mb-6">
              Are you sure you want to delete{' '}
              <span className="font-semibold text-slate-900">
                {workspaceName ?? 'this workspace'}
              </span>
              ? All knowledge files, channel bindings, and keys will be permanently removed.
            </p>

            {deleteMutation.error && (
              <p className="mb-4 text-xs text-rose-600" role="alert">
                {deleteMutation.error instanceof Error
                  ? deleteMutation.error.message
                  : 'Failed to delete workspace. Please try again.'}
              </p>
            )}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowConfirm(false)}
                disabled={deleteMutation.isPending}
                className="rounded-md px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="rounded-md bg-rose-500 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// WorkspaceDetailPage
// ---------------------------------------------------------------------------

/**
 * WorkspaceDetailPage — top-level page component for the workspace detail route.
 *
 * Composes DriveSection, PickerSection, and KnowledgeList with shared state
 * for the truncation warning toast. Route params are read via `Route.useParams()`.
 *
 * Auth protection is inherited from the grandparent `app.tsx` layout route.
 */
function WorkspaceDetailPage() {
  const { teamId, workspaceId } = Route.useParams();
  const [truncationWarning, setTruncationWarning] = useState<string | null>(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [wizardSkipped, setWizardSkipped] = useState(false);

  // Data queries
  const { data: workspace, isLoading: workspaceLoading } = useWorkspaceQuery(workspaceId);
  const { data: keyData, isLoading: keyLoading } = useKeyQuery(workspaceId);
  const { data: driveStatus, isLoading: driveLoading } = useDriveStatusQuery(workspaceId);
  const {
    data: knowledgeFiles,
    isLoading: knowledgeLoading,
  } = useKnowledgeQuery(workspaceId);

  const files = knowledgeFiles ?? [];
  const driveConnected = driveStatus?.connected ?? false;
  const hasKey = keyData?.has_key === true;

  /**
   * Whether all three setup prerequisites are met.
   * When false, show the guided SetupStepper instead of the normal detail view.
   * Step 4 (Channels) is NOT part of this check per STORY-008-01 R5.
   */
  const isSetupComplete = driveConnected && hasKey;

  /**
   * Handles the result of a successful file indexing operation.
   * Shows a truncation warning banner if the response includes a warning field.
   */
  const handleFileIndexed = useCallback((file: KnowledgeFile) => {
    if (file.warning) {
      setTruncationWarning(file.warning);
    }
  }, []);

  // Show a full-screen spinner while prerequisite data is loading
  if (workspaceLoading || keyLoading || driveLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div
          role="status"
          aria-label="Loading workspace setup status"
          className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent"
        />
      </div>
    );
  }

  // Show guided setup mode when setup is incomplete and user hasn't skipped
  if (!isSetupComplete && !wizardSkipped) {
    return (
      <SetupStepper
        workspaceId={workspaceId}
        teamId={teamId}
        onSkip={() => setWizardSkipped(true)}
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl space-y-6">

        {/* Breadcrumb */}
        <div>
          <nav className="flex items-center gap-1 text-sm text-slate-500 mb-2" aria-label="Breadcrumb">
            <Link to="/app" className="hover:text-slate-700">Teams</Link>
            <span className="text-slate-300">/</span>
            <Link
              to="/app/teams/$teamId"
              params={{ teamId }}
              className="hover:text-slate-700"
            >
              {teamId}
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-slate-700 font-semibold">
              {workspace?.name ?? workspaceId}
            </span>
          </nav>

          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {workspace?.name ?? 'Workspace'}
          </h1>
        </div>

        {/* Truncation warning banner (R8) */}
        {truncationWarning && (
          <TruncationToast
            message={truncationWarning}
            onDismiss={() => setTruncationWarning(null)}
          />
        )}

        {/* Drive connection section */}
        <DriveSection workspaceId={workspaceId} />

        {/* Picker section (file count + Add File button) */}
        <PickerSection
          workspaceId={workspaceId}
          driveConnected={driveConnected}
          hasKey={hasKey}
          fileCount={files.length}
          onFileIndexed={handleFileIndexed}
          onIndexingChange={setIsIndexing}
        />

        {/* Visible indexing progress banner */}
        {isIndexing && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 animate-pulse">
            Reading file from Google Drive and generating AI description... This may take a few seconds.
          </div>
        )}

        {/* Knowledge file list */}
        <KnowledgeList
          workspaceId={workspaceId}
          files={files}
          isLoading={knowledgeLoading}
        />

        {/* Active skills catalog (STORY-023-01) */}
        <SkillsSection workspaceId={workspaceId} />

        {/* Channel binding section (STORY-008-02) */}
        <ChannelSection workspaceId={workspaceId} teamId={teamId} />

        {/* Danger zone — delete workspace (STORY-006-09) */}
        <DeleteWorkspaceSection
          workspaceId={workspaceId}
          workspaceName={workspace?.name}
          teamId={teamId}
        />

      </div>
    </div>
  );
}
