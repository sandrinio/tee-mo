/**
 * WorkspaceCard — displays a single Tee-Mo workspace within the team detail page.
 *
 * Design Guide §9.2: Uses the `Card` primitive with `bg-white rounded-lg shadow-sm
 * border border-slate-200 p-6`. Displays workspace name, an optional "Default"
 * badge when `is_default_for_team` is true, and the creation date.
 *
 * Max font weight is `font-semibold` (600) — never `font-bold` (700) per sprint
 * design rules in sprint-context-S-05.md.
 *
 * Date formatting uses `Intl.DateTimeFormat` (locale-aware, zero extra deps).
 */
import { Card } from '../ui/Card';
import type { Workspace } from '../../lib/api';

/** Props accepted by WorkspaceCard. */
export interface WorkspaceCardProps {
  /** The workspace record to display. */
  workspace: Workspace;
}

/**
 * WorkspaceCard — card UI for one workspace record.
 *
 * Shows:
 *   - Workspace name (semibold)
 *   - "Default" badge when `workspace.is_default_for_team === true`
 *   - Human-readable creation date (locale-aware via Intl)
 *
 * @example
 * ```tsx
 * <WorkspaceCard workspace={ws} />
 * ```
 */
export function WorkspaceCard({ workspace }: WorkspaceCardProps) {
  const createdDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(workspace.created_at));

  return (
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

        {/* Default badge — only shown when this workspace is the team default */}
        {workspace.is_default_for_team && (
          <span
            className="shrink-0 rounded-full bg-[#E94560] px-2 py-0.5 text-xs font-semibold text-white"
            aria-label="Default workspace"
          >
            Default
          </span>
        )}
      </div>
    </Card>
  );
}
