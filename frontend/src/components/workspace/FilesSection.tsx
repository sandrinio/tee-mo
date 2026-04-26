/**
 * FilesSection.tsx — Knowledge group module for Workspace v2 shell (STORY-025-03).
 *
 * Extracted from the inline PickerSection + KnowledgeList + TruncationToast
 * definitions in the route file. All existing hook logic is preserved verbatim;
 * only the visual chrome is updated to match the W01 §5.7 divider-list pattern.
 *
 * HOVER-REVEAL PATTERN (W01 §5.7):
 *   Row uses Tailwind `group` class. Remove button uses:
 *     `opacity-0 group-hover:opacity-100 transition-opacity duration-150`
 *   This pattern is intentionally documented here so STORY-025-04 SkillsSection
 *   does NOT accidentally copy the hover-reveal — skills are read-only (ADR-023),
 *   no row actions should hover-reveal on skill rows.
 *
 * CONTRACT (W01 §5.1):
 *   This component renders ONLY the body content. It does NOT render an h2
 *   or outer Card border — ModuleSection (provided by WorkspaceShell) wraps it.
 *
 * HELPERS (consolidated from route file — STORY-025-06 Option A):
 *   `loadGapiScript`, `docTypeLabel`, `sourceBadgeProps` were duplicated as `*Local`
 *   variants during 025-03 while the route still held the legacy stacked block.
 *   STORY-025-06 removed the legacy block; the `*Local` suffix is now dropped and
 *   the route-file copies are deleted. These helpers live here as the canonical copy.
 *
 * FILE CAP: MAX_FILES = 100 (not 15). The "15" boundary is the partial/ok status
 * resolver threshold only. The header strip count reads "{N} of 100 files indexed".
 * See W01 §3 STORY-025-03 risk note on R-CAP DRIFT.
 */

import { useState, useCallback, useRef } from 'react';

import { Badge } from '../ui/Badge';
import { FileText } from 'lucide-react';
import {
  useKnowledgeQuery,
  useAddKnowledgeMutation,
  useRemoveKnowledgeMutation,
  useReindexKnowledgeMutation,
  useUploadKnowledgeMutation,
} from '../../hooks/useKnowledge';
import { getPickerToken, type KnowledgeFile, type DocumentSource } from '../../lib/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum number of files that can be indexed per workspace (R5, W01 §3 R-CAP DRIFT note). */
const MAX_FILES = 100;

/** Google API client script URL for loading the Picker API. */
const GAPI_SCRIPT_URL = 'https://apis.google.com/js/api.js';

// ---------------------------------------------------------------------------
// Helpers (canonical copies — STORY-025-06 Option A: live here, route copies deleted)
// ---------------------------------------------------------------------------

/**
 * Loads the Google API client script into the document if it hasn't been
 * loaded yet. Resolves when the script is ready. Idempotent — safe to call
 * multiple times; only injects the script once.
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
 * or the legacy `mime_type` string (fallback).
 */
function docTypeLabel(
  docType: string | null | undefined,
  mimeType: string | null | undefined,
): string {
  if (docType) {
    switch (docType) {
      case 'google_doc':    return 'Doc';
      case 'google_sheet':  return 'Sheet';
      case 'google_slides': return 'Slide';
      case 'pdf':           return 'PDF';
      case 'docx':          return 'DOCX';
      case 'xlsx':          return 'XLSX';
      case 'markdown':      return 'MD';
      case 'text':          return 'TXT';
      default:              return docType.toUpperCase().slice(0, 6);
    }
  }
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
// TruncationToast
// ---------------------------------------------------------------------------

/**
 * TruncationToast — inline banner shown when a just-indexed file was truncated.
 *
 * Displayed after a successful file index where the response includes a
 * `warning` field (file content > 50,000 chars, R8).
 *
 * Moved from the route file into FilesSection (W01 §3 STORY-025-03: "TruncationToast
 * moves into FilesSection.tsx so the route doesn't need a truncationWarning prop").
 *
 * @param message   - Warning message text from the backend response.
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
      className="mx-4 mt-3 flex items-start justify-between gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800"
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
// Props
// ---------------------------------------------------------------------------

/** Props for FilesSection. */
export interface FilesSectionProps {
  /** UUID of the workspace. */
  workspaceId: string;
  /** Whether Google Drive is currently connected for this workspace. */
  driveConnected: boolean;
  /** Whether a BYOK key is configured for this workspace. */
  hasKey: boolean;
}

/** Result state for the reindex operation, shown inline after completion. */
interface ReindexFeedback {
  reindexed: number;
  skipped: number;
  failed: number;
}

// ---------------------------------------------------------------------------
// FilesSection
// ---------------------------------------------------------------------------

/**
 * FilesSection — Knowledge group module for the Workspace v2 shell.
 *
 * Renders:
 *   1. Header strip: "{N} of 100 files indexed" + "Add file" + "Upload" buttons.
 *   2. TruncationToast banner below header strip when active (R8).
 *   3. Indexing progress banner when a file is being indexed.
 *   4. Divider list (W01 §5.7) of indexed files with hover-reveal Remove button.
 *
 * Internally uses all existing useKnowledge* hooks unchanged.
 *
 * @param props - See FilesSectionProps.
 */
export function FilesSection({ workspaceId, driveConnected, hasKey }: FilesSectionProps) {
  const [truncationWarning, setTruncationWarning] = useState<string | null>(null);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reindexFeedback, setReindexFeedback] = useState<ReindexFeedback | null>(null);

  const uploadInputRef = useRef<HTMLInputElement>(null);

  // All existing hooks — preserved verbatim (STORY-025-03 §1.2: behavior preserved).
  const { data: knowledgeFiles, isLoading } = useKnowledgeQuery(workspaceId);
  const addMutation = useAddKnowledgeMutation(workspaceId);
  const removeMutation = useRemoveKnowledgeMutation(workspaceId);
  const reindexMutation = useReindexKnowledgeMutation(workspaceId);
  const uploadMutation = useUploadKnowledgeMutation(workspaceId);

  const files: KnowledgeFile[] = knowledgeFiles ?? [];
  const fileCount = files.length;
  const atCap = fileCount >= MAX_FILES;
  const pickerDisabled = !driveConnected || !hasKey || atCap || indexing;

  // --------------------------------------------------------------------------
  // Handlers
  // --------------------------------------------------------------------------

  /**
   * Opens the Google Picker dialog.
   * Handles token fetch, script load, and picker construction.
   * Preserved verbatim from the inline PickerSection in the route file.
   */
  const handleOpenPicker = useCallback(async () => {
    setError(null);
    try {
      const { access_token, picker_api_key } = await getPickerToken(workspaceId);
      await loadGapiScript();

      gapi.load('picker', () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const textView = new (google.picker as any).DocsView()
          .setMimeTypes('text/plain');

        const picker = new google.picker.PickerBuilder()
          .setOAuthToken(access_token)
          .setDeveloperKey(picker_api_key)
          .addView(google.picker.ViewId.DOCS)
          .addView(textView)
          .setCallback(async (data: google.picker.CallbackData) => {
            if (data.action !== google.picker.Action.PICKED) return;
            const doc = data.docs?.[0];
            if (!doc) return;

            setIndexing(true);
            try {
              const result = await addMutation.mutateAsync({
                drive_file_id: doc.id,
                title: doc.name,
                link: doc.url,
                mime_type: doc.mimeType,
                access_token,
              });
              if (result.warning) {
                setTruncationWarning(result.warning);
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to index file.');
            } finally {
              setIndexing(false);
            }
          })
          .build();

        picker.setVisible(true);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open file picker.');
    }
  }, [workspaceId, addMutation]);

  /** Handles the Re-index All Files button click. */
  const handleReindex = useCallback(async () => {
    setReindexFeedback(null);
    try {
      const result = await reindexMutation.mutateAsync();
      setReindexFeedback({
        reindexed: result.reindexed,
        skipped: result.skipped,
        failed: result.failed,
      });
    } catch {
      // error surfaced via reindexMutation.error
    }
  }, [reindexMutation]);

  /** Handles file selection from the hidden upload input. */
  const handleUploadSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setUploadError(null);
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) {
        setUploadError('File exceeds 10MB limit');
        e.target.value = '';
        return;
      }
      uploadMutation.mutate(file);
      e.target.value = '';
    },
    [uploadMutation],
  );

  const reindexDisabled =
    fileCount === 0 || !driveConnected || !hasKey || reindexMutation.isPending || indexing;

  // --------------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------------

  return (
    <>
      {/* Header strip — "{N} of 100 files indexed" left, action buttons right */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <span className="text-sm text-slate-500">
          {fileCount} of {MAX_FILES} files indexed
        </span>

        <div className="flex items-center gap-2 shrink-0">
          {/* Re-index All — only visible when files exist */}
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
              {reindexMutation.isPending ? 'Re-indexing…' : 'Re-index All'}
            </button>
          )}

          {/* Add file — primary CTA; requires Drive + BYOK + under cap */}
          <button
            type="button"
            onClick={handleOpenPicker}
            disabled={pickerDisabled}
            title={
              !driveConnected
                ? 'Connect Drive first'
                : atCap
                  ? `${MAX_FILES} file limit reached`
                  : undefined
            }
            className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {indexing ? 'Indexing…' : 'Add file'}
          </button>

          {/* Upload — does NOT require Drive connection (STORY-014-03) */}
          <button
            type="button"
            onClick={() => uploadInputRef.current?.click()}
            disabled={!hasKey || atCap || uploadMutation.isPending}
            title={
              !hasKey
                ? 'Configure an API key first'
                : atCap
                  ? `${MAX_FILES} file limit reached`
                  : undefined
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
          </button>

          {/* Hidden file input */}
          <input
            ref={uploadInputRef}
            type="file"
            accept=".pdf,.docx,.xlsx,.txt,.md,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain,text/markdown"
            onChange={handleUploadSelect}
            className="hidden"
            aria-hidden="true"
          />
        </div>
      </div>

      {/* Banners — render below header strip per story §1.2 */}

      {/* BYOK gate */}
      {driveConnected && !hasKey && (
        <p className="px-4 pt-2 text-xs text-amber-600">
          Configure an API key first to enable file indexing.
        </p>
      )}

      {/* Indexing progress */}
      {indexing && (
        <div className="mx-4 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 animate-pulse">
          Reading file from Google Drive and generating AI description... This may take a few seconds.
        </div>
      )}

      {/* Truncation warning */}
      {truncationWarning && (
        <TruncationToast
          message={truncationWarning}
          onDismiss={() => setTruncationWarning(null)}
        />
      )}

      {/* Picker error */}
      {error && (
        <p className="px-4 pt-2 text-xs text-rose-600" role="alert">
          {error}
        </p>
      )}

      {/* Upload error */}
      {(uploadError || uploadMutation.error) && (
        <p className="px-4 pt-2 text-xs text-rose-600" role="alert">
          {uploadError ?? uploadMutation.error?.message ?? 'Upload failed. Please try again.'}
        </p>
      )}

      {/* Re-index error */}
      {reindexMutation.error && (
        <p className="px-4 pt-2 text-xs text-rose-600" role="alert">
          {reindexMutation.error instanceof Error
            ? reindexMutation.error.message
            : 'Re-index failed. Please try again.'}
        </p>
      )}

      {/* Re-index success feedback */}
      {reindexFeedback && (
        <p className="px-4 pt-2 text-xs text-slate-600">
          Re-indexed {reindexFeedback.reindexed} file
          {reindexFeedback.reindexed !== 1 ? 's' : ''}
          {(reindexFeedback.skipped > 0 || reindexFeedback.failed > 0) && (
            <span>
              {' '}
              (
              {[
                reindexFeedback.skipped > 0 ? `${reindexFeedback.skipped} skipped` : null,
                reindexFeedback.failed > 0
                  ? `${reindexFeedback.failed} failed — check Drive permissions`
                  : null,
              ]
                .filter(Boolean)
                .join(', ')}
              )
            </span>
          )}
          {reindexFeedback.failed === 0 ? ' successfully.' : ''}
        </p>
      )}

      {/* File list — divider-list pattern (W01 §5.7) */}
      {isLoading ? (
        <div className="space-y-2 p-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="animate-pulse rounded-lg border border-slate-200 bg-white p-4"
            >
              <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
              <div className="h-3 w-2/3 rounded bg-slate-100" />
            </div>
          ))}
        </div>
      ) : files.length === 0 ? (
        <p className="px-4 py-8 text-center text-sm text-slate-500">
          No files indexed yet. Use the Add file button above to index from Drive.
        </p>
      ) : (
        /**
         * DIVIDER-LIST PATTERN (W01 §5.7, frozen markup).
         *
         * HOVER-REVEAL: rows use `group` class; Remove button is
         *   `opacity-0 group-hover:opacity-100 transition-opacity duration-150`
         *
         * NOTE FOR STORY-025-04 (SkillsSection):
         *   Skills are READ-ONLY (ADR-023) — do NOT copy the hover-reveal Remove
         *   button here. Skills rows have no row actions to hover-reveal.
         *   Use the same `divide-y divide-slate-100` container but omit `group`
         *   and the opacity-0 / group-hover:opacity-100 classes on skill rows.
         */
        <ul className="divide-y divide-slate-100">
          {files.map((file) => {
            // Resolve canonical link — prefer new `external_link`, fall back to legacy `link`.
            const externalLink = file.external_link ?? file.link ?? null;
            const effectiveSource: DocumentSource | null =
              file.source ?? (externalLink ? 'google_drive' : null);
            const { variant, label: badgeLabel, className: badgeClassName } =
              sourceBadgeProps(effectiveSource);

            return (
              <li
                key={file.id}
                className="group flex items-start gap-3 px-4 py-3"
              >
                {/* File icon */}
                <span className="mt-0.5 shrink-0 text-slate-400">
                  <FileText className="w-4 h-4" />
                </span>

                {/* File metadata */}
                <div className="min-w-0 flex-1">
                  {/* Source badge + doc-type chip + title */}
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <Badge variant={variant} className={`shrink-0 ${badgeClassName ?? ''}`}>
                      {badgeLabel}
                    </Badge>
                    <span className="text-xs bg-slate-100 text-slate-600 rounded px-1.5 py-0.5 font-semibold shrink-0">
                      {docTypeLabel(file.doc_type, file.mime_type)}
                    </span>
                    {externalLink ? (
                      <a
                        href={externalLink}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-slate-900 truncate hover:text-rose-500 min-w-0"
                      >
                        {file.title}
                      </a>
                    ) : (
                      <span className="text-sm font-medium text-slate-900 truncate min-w-0">
                        {file.title}
                      </span>
                    )}
                  </div>

                  {/* AI description — italic, 1 line, slate-500 (W01 §3 STORY-025-03 spec) */}
                  {file.ai_description && (
                    <p className="text-xs italic text-slate-500 line-clamp-1">
                      {file.ai_description}
                    </p>
                  )}
                </div>

                {/* Remove button — hover-revealed (W01 §5.7 + STORY-025-03 §1.2) */}
                <button
                  type="button"
                  onClick={() => removeMutation.mutate(file.id)}
                  disabled={removeMutation.isPending}
                  aria-label={`Remove ${file.title}`}
                  className="shrink-0 text-xs font-semibold text-rose-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hover:opacity-70 disabled:opacity-40"
                >
                  {removeMutation.isPending ? 'Removing…' : 'Remove'}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
