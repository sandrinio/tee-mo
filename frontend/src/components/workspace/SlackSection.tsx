/**
 * SlackSection.tsx — Info-only Slack connection card (STORY-025-02).
 *
 * Pure presentational. Props: workspace + teamId.
 * Renders the avatar tile + workspace name + mono caption + Installed badge.
 * NO Reinstall button (epic §6 Q1 owner directive).
 *
 * Caption source (OQ-3 = C; hotfix 2026-04-26 swapped from slack_domain to
 * slack_team_name since teemo_slack_teams has no `domain` column):
 *   `${workspace.slack_team_id}${workspace.slack_team_name ? ` · ${workspace.slack_team_name}` : ''}`
 *   Degrades gracefully when slack_team_name is null/undefined.
 *
 * Does NOT render its own h2 or outer card border — that is ModuleSection's job.
 */

import { MessageSquare } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { Workspace } from '../../lib/api';

// ---------------------------------------------------------------------------
// ModuleAvatarTile — reusable 40×40 icon tile (W01 §5.6)
// ---------------------------------------------------------------------------

/**
 * Reusable 40×40 slate-100 avatar tile with a centred lucide icon.
 * Extracted here per W01 §5.6 to prevent CSS drift across 025-02/03/04.
 * Re-exported for consumption by DriveSection (and future 025-03/04 tiles).
 */
export function ModuleAvatarTile({
  icon: Icon,
  'data-testid': testId,
}: {
  icon: React.ElementType;
  'data-testid'?: string;
}) {
  return (
    <div
      className="h-10 w-10 rounded-md bg-slate-100 flex items-center justify-center shrink-0"
      data-testid={testId}
    >
      <Icon className="h-5 w-5 text-slate-500" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SlackSection
// ---------------------------------------------------------------------------

export interface SlackSectionProps {
  workspace: Workspace;
  teamId: string;
}

/**
 * SlackSection — info-only view of the Slack workspace connection.
 *
 * Rendered inside ModuleSection (which provides the card border).
 * Intentionally read-only: no Reinstall, no disconnect.
 */
export function SlackSection({ workspace }: SlackSectionProps) {
  const caption =
    workspace.slack_team_id +
    (workspace.slack_team_name ? ` · ${workspace.slack_team_name}` : '');

  return (
    <div className="p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <ModuleAvatarTile icon={MessageSquare} />
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-900 truncate">{workspace.name}</div>
          <div
            className="text-xs text-slate-500 font-mono truncate"
            data-testid="slack-caption"
          >
            {caption}
          </div>
        </div>
      </div>
      <div className="shrink-0">
        <Badge variant="success">Installed</Badge>
      </div>
    </div>
  );
}
