/**
 * DangerZoneSection.tsx — Danger zone module for Workspace v2 shell.
 *
 * STORY-025-05: extracted from the inline DeleteWorkspaceSection in
 * frontend/src/routes/app.teams.$teamId.$workspaceId.tsx.
 *
 * Single-row layout per W01 §3 STORY-025-05:
 *   Left: title "Danger zone" (text-base/font-semibold) + caption
 *   Right: danger-variant Delete button
 *
 * The div-based confirmation dialog is preserved verbatim from the
 * original DeleteWorkspaceSection (jsdom does not support showModal()).
 *
 * Rendered inside a <ModuleSection> — does NOT render its own h2 or
 * outer card border (ModuleSection provides those per W01 §5.1).
 */

import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { deleteWorkspace } from '../../lib/api';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DangerZoneSectionProps {
  workspaceId: string;
  workspaceName: string | undefined;
  teamId: string;
}

// ---------------------------------------------------------------------------
// DangerZoneSection
// ---------------------------------------------------------------------------

/**
 * DangerZoneSection — Danger zone card with a single-row layout and a
 * div-based confirmation dialog.
 *
 * Design: single-row flex layout with title+caption on the left and a
 * danger-variant Delete button on the right. The div-overlay confirmation
 * dialog is preserved verbatim from the original DeleteWorkspaceSection
 * (jsdom does not support native <dialog>.showModal()).
 *
 * On confirm:
 *   1. Calls `deleteWorkspace(workspaceId)` via `useMutation`.
 *   2. Invalidates the `['workspaces', teamId]` query cache.
 *   3. Navigates to `/app/teams/${teamId}`.
 *
 * On cancel: dialog is dismissed with no side-effects.
 */
export function DangerZoneSection({ workspaceId, workspaceName, teamId }: DangerZoneSectionProps) {
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
    <>
      {/* HOTFIX 2026-04-26: section title + caption removed — ModuleSection
          wrapper already provides them per W01 §5.1. Only the Delete action
          remains, right-aligned. */}
      <div className="flex items-center justify-end p-4">
        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          className="rounded-md bg-rose-500 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Delete
        </button>
      </div>

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
    </>
  );
}
