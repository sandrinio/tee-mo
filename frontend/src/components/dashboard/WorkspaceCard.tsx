/**
 * WorkspaceCard — displays a single Tee-Mo workspace within the team detail page.
 *
 * Design Guide §9.2: Uses the `Card` primitive with `bg-white rounded-lg shadow-sm
 * border border-slate-200 p-6`. Displays workspace name, an optional "Default"
 * badge when `is_default_for_team` is true, and the creation date.
 *
 * Action buttons:
 *   - "Rename" — opens the RenameWorkspaceModal, available on all workspaces.
 *   - "Make Default" — triggers `useMakeDefaultMutation` with optimistic UI update.
 *     Only shown on non-default workspaces (no-op to show it on the current default).
 *
 * Error handling:
 *   - Inline error message below the action row when make-default mutation fails.
 *   - No external toast library (Design Guide §9.2 / STORY-003-B06).
 *
 * Max font weight is `font-semibold` (600) — never `font-bold` (700) per sprint
 * design rules in sprint-context-S-05.md.
 *
 * Date formatting uses `Intl.DateTimeFormat` (locale-aware, zero extra deps).
 */
import { useState } from 'react';
import { Card } from '../ui/Card';
import type { Workspace } from '../../lib/api';
import { useMakeDefaultMutation } from '../../hooks/useWorkspaces';
import { RenameWorkspaceModal } from './RenameWorkspaceModal';

/** Props accepted by WorkspaceCard. */
export interface WorkspaceCardProps {
  /** The workspace record to display. */
  workspace: Workspace;
  /**
   * Slack team ID the workspace belongs to.
   * Required so `useMakeDefaultMutation` can target the correct query cache key
   * for its optimistic update.
   */
  teamId: string;
}

/**
 * WorkspaceCard — card UI for one workspace record.
 *
 * Shows:
 *   - Workspace name (semibold)
 *   - "Default" badge when `workspace.is_default_for_team === true`
 *   - Human-readable creation date (locale-aware via Intl)
 *   - "Rename" action button (all workspaces)
 *   - "Make Default" action button (non-default workspaces only)
 *   - Inline error if the make-default mutation fails
 *
 * @example
 * ```tsx
 * <WorkspaceCard workspace={ws} teamId={teamId} />
 * ```
 */
export function WorkspaceCard({ workspace, teamId }: WorkspaceCardProps) {
  const [renameOpen, setRenameOpen] = useState(false);

  const makeDefaultMutation = useMakeDefaultMutation(teamId);

  const createdDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(workspace.created_at));

  return (
    <>
      <Card className="shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1 min-w-0">
            {/* Workspace name */}
            <div className="font-semibold text-slate-900 truncate">
              {workspace.name}
            </div>

            {/* Creation date */}
            <div className="text-xs text-slate-400">
              Created {createdDate}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {/* Default badge — only shown when this workspace is the team default */}
            {workspace.is_default_for_team && (
              <span
                className="rounded-full bg-[#E94560] px-2 py-0.5 text-xs font-semibold text-white"
                aria-label="Default workspace"
              >
                Default
              </span>
            )}

            {/* Action buttons */}
            <button
              type="button"
              onClick={() => setRenameOpen(true)}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800"
            >
              Rename
            </button>

            {/* Make Default — only shown on non-default workspaces */}
            {!workspace.is_default_for_team && (
              <button
                type="button"
                onClick={() => makeDefaultMutation.mutate(workspace.id)}
                disabled={makeDefaultMutation.isPending}
                className="text-xs font-semibold text-[#E94560] hover:opacity-70 disabled:opacity-40"
              >
                {makeDefaultMutation.isPending ? 'Saving…' : 'Make Default'}
              </button>
            )}
          </div>
        </div>

        {/* Inline error if make-default mutation fails */}
        {makeDefaultMutation.error != null && (
          <p
            role="alert"
            className="mt-2 text-xs text-rose-700"
          >
            {makeDefaultMutation.error instanceof Error
              ? makeDefaultMutation.error.message
              : 'An error occurred. Please try again.'}
          </p>
        )}
      </Card>

      {/* Rename modal — mounted outside Card so it renders above everything */}
      <RenameWorkspaceModal
        workspace={workspace}
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
      />
    </>
  );
}
