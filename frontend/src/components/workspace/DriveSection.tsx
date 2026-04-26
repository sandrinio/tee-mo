/**
 * DriveSection.tsx — Google Drive connection module (STORY-025-02).
 *
 * Extracted from the inline `function DriveSection` in the route file (lines 197-252).
 * Behaviour preserved verbatim: connected state shows email + Disconnect button;
 * not-connected state shows Connect link.
 *
 * Re-skin per W01 §3: swap inner <Card> for <div className="p-5"> —
 * the <ModuleSection> parent already provides the rounded bordered card.
 * Avatar tile uses the shared <ModuleAvatarTile> helper from SlackSection.
 *
 * Does NOT render its own h2 or outer card border — that is ModuleSection's job.
 */

import { FolderOpen } from 'lucide-react';
import { useDriveStatusQuery, useDisconnectDriveMutation } from '../../hooks/useDrive';
import { ModuleAvatarTile } from './SlackSection';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DriveSectionProps {
  workspaceId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Drive connection module — avatar tile + connected email + caption + Disconnect.
 *
 * @param workspaceId - UUID of the workspace whose Drive connection to display.
 */
export function DriveSection({ workspaceId }: DriveSectionProps) {
  const { data: driveStatus, isLoading } = useDriveStatusQuery(workspaceId);
  const disconnectMutation = useDisconnectDriveMutation(workspaceId);

  if (isLoading) {
    return (
      <div className="p-5 animate-pulse">
        <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
        <div className="h-3 w-1/2 rounded bg-slate-100" />
      </div>
    );
  }

  return (
    <div className="p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <ModuleAvatarTile icon={FolderOpen} />
        <div className="min-w-0">
          {driveStatus?.connected ? (
            <>
              <div className="text-sm font-medium text-slate-900 truncate">
                {driveStatus.email}
              </div>
              <div className="text-xs text-slate-500 truncate">
                Read-only access · scoped to selected files
              </div>
            </>
          ) : (
            <>
              <div className="text-sm font-medium text-slate-900">Google Drive</div>
              <div className="text-xs text-slate-500">Not connected</div>
            </>
          )}
        </div>
      </div>

      <div className="shrink-0">
        {driveStatus?.connected ? (
          <div className="flex flex-col items-end gap-1">
            <button
              type="button"
              onClick={() => disconnectMutation.mutate()}
              disabled={disconnectMutation.isPending}
              className="text-sm font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
              data-testid="disconnect-drive-button"
            >
              {disconnectMutation.isPending ? 'Disconnecting…' : 'Disconnect'}
            </button>
            {disconnectMutation.error && (
              <p className="text-xs text-rose-600" role="alert">
                {disconnectMutation.error instanceof Error
                  ? disconnectMutation.error.message
                  : 'Failed to disconnect. Please try again.'}
              </p>
            )}
          </div>
        ) : (
          <a
            href={`/api/workspaces/${encodeURIComponent(workspaceId)}/drive/connect`}
            className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600"
          >
            Connect Google Drive
          </a>
        )}
      </div>
    </div>
  );
}
