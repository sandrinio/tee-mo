/**
 * WorkspaceCard — displays a single Tee-Mo workspace within the team detail page.
 *
 * Design Guide §9.2: Uses the `Card` primitive with `bg-white rounded-lg shadow-sm
 * border border-slate-200 p-6`. Displays workspace name, an optional "Default"
 * badge when `is_default_for_team` is true, and the creation date.
 *
 * STORY-008-03 additions:
 *   - Channel chips row: shows up to 3 bound channels from `useChannelBindingsQuery`.
 *     Active channels (is_member=true) render with emerald styling; Pending with amber.
 *     If >3 bindings, an overflow "+N more" label is shown.
 *   - "DMs route here" badge when `workspace.is_default_for_team === true`.
 *     Styled: `text-xs font-medium text-brand-600 bg-brand-50 rounded-full px-2 py-0.5`.
 *   - Setup completeness strip: Drive (green/slate), Key (green/slate), Files N/15 (green/slate).
 *   - All design tokens updated from hardcoded hex to `brand-500`/`brand-600` (R8).
 *   - Ad-hoc `<button>` elements replaced with `<Button>` component (R9).
 *
 * Action buttons:
 *   - "Rename" — opens the RenameWorkspaceModal, available on all workspaces.
 *   - "Make Default" — triggers `useMakeDefaultMutation` with optimistic UI update.
 *     Only shown on non-default workspaces (no-op to show it on the current default).
 *
 * Error handling:
 *   - Inline error message below the action row when make-default mutation fails.
 *
 * Max font weight is `font-semibold` (600) — never `font-bold` (700) per sprint
 * design rules in sprint-context-S-05.md.
 *
 * Date formatting uses `Intl.DateTimeFormat` (locale-aware, zero extra deps).
 *
 * STORY-004-04: Adds inline `KeySection` component for BYOK key management.
 */
import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import type { Workspace } from '../../lib/api';
import { useMakeDefaultMutation } from '../../hooks/useWorkspaces';
import { useChannelBindingsQuery } from '../../hooks/useChannels';
import { useDriveStatusQuery } from '../../hooks/useDrive';
import { useKeyQuery } from '../../hooks/useKey';
import { useKnowledgeQuery } from '../../hooks/useKnowledge';
import { RenameWorkspaceModal } from './RenameWorkspaceModal';
import { KeySection } from '../workspace/KeySection';
import { useMcpServersQuery } from '../../hooks/useMcpServers';
import { Plug } from 'lucide-react';

// ---------------------------------------------------------------------------
// Add File placeholder guard (EPIC-006 wires the real button)
// ---------------------------------------------------------------------------

/**
 * canAddFile — evaluates whether the workspace has a configured BYOK key.
 *
 * This function exists as a placeholder so EPIC-006 can import it and wire
 * the real "Add File" button without re-reading the key status.
 *
 * @param hasKey - The `has_key` field from `ProviderKey`.
 * @returns `true` when an API key is configured and the Add File action is allowed.
 */
export function canAddFile(hasKey: boolean | undefined): boolean {
  return hasKey === true;
}

// ---------------------------------------------------------------------------
// WorkspaceCard props
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// SetupStrip — completeness indicators (Drive / Key / Files N/15)
// ---------------------------------------------------------------------------

/**
 * SetupStripProps — data needed to render the three setup completeness pills.
 */
interface SetupStripProps {
  /** Whether Google Drive is connected for this workspace. */
  driveConnected: boolean;
  /** Whether a BYOK key is configured for this workspace. */
  hasKey: boolean;
  /** Number of indexed knowledge files. */
  fileCount: number;
}

/**
 * SetupStrip — a compact row of three colored pills showing workspace readiness.
 *
 * Each pill is green when the corresponding feature is configured, slate when not.
 * Uses `text-xs` per Design Guide §9.2 spec for the strip.
 */
function SetupStrip({ driveConnected, hasKey, fileCount }: SetupStripProps) {
  const driveCls = driveConnected
    ? 'text-xs font-medium text-green-700 bg-green-50 rounded px-1.5 py-0.5'
    : 'text-xs font-medium text-slate-500 bg-slate-100 rounded px-1.5 py-0.5';

  const keyCls = hasKey
    ? 'text-xs font-medium text-green-700 bg-green-50 rounded px-1.5 py-0.5'
    : 'text-xs font-medium text-slate-500 bg-slate-100 rounded px-1.5 py-0.5';

  const filesCls =
    fileCount > 0
      ? 'text-xs font-medium text-green-700 bg-green-50 rounded px-1.5 py-0.5'
      : 'text-xs font-medium text-slate-500 bg-slate-100 rounded px-1.5 py-0.5';

  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2">
      <span data-testid="setup-drive" className={driveCls}>
        Drive
      </span>
      <span data-testid="setup-key" className={keyCls}>
        Key
      </span>
      <span data-testid="setup-files" className={filesCls}>
        Files {fileCount}/15
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChannelChipsRow — up to 3 channel chips + overflow label
// ---------------------------------------------------------------------------

/**
 * ChannelBinding shape used internally — mirrors the API type.
 */
interface ChannelChipData {
  slack_channel_id: string;
  channel_name?: string;
  is_member?: boolean;
}

/**
 * ChannelChipsRow — renders bound channel chips (max 3) with overflow count.
 *
 * Active channels (is_member === true) → emerald styling.
 * Pending channels (is_member !== true) → amber styling.
 * When more than 3 bindings exist, shows "+N more" overflow label.
 *
 * @param bindings - Channel binding records from useChannelBindingsQuery.
 */
function ChannelChipsRow({ bindings }: { bindings: ChannelChipData[] }) {
  if (!bindings.length) return null;

  const visible = bindings.slice(0, 3);
  const overflow = bindings.length - 3;

  return (
    <div className="flex flex-wrap items-center gap-1.5 mt-2">
      {visible.map((b) => {
        const isActive = b.is_member === true;
        const chipCls = isActive
          ? 'text-xs font-medium text-emerald-700 bg-emerald-50 rounded-full px-2 py-0.5'
          : 'text-xs font-medium text-amber-700 bg-amber-50 rounded-full px-2 py-0.5';
        return (
          <span key={b.slack_channel_id} data-testid="channel-chip" className={chipCls}>
            #{b.channel_name ?? b.slack_channel_id}
          </span>
        );
      })}
      {overflow > 0 && (
        <span
          data-testid="channel-overflow"
          className="text-xs text-slate-400"
        >
          +{overflow} more
        </span>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// WorkspaceCard
// ---------------------------------------------------------------------------

/**
 * WorkspaceCard — card UI for one workspace record.
 *
 * Shows:
 *   - Workspace name (semibold) linking to the workspace detail page
 *   - "DMs route here" badge when `workspace.is_default_for_team === true`
 *   - Human-readable creation date (locale-aware via Intl)
 *   - Channel chips row (up to 3 Active/Pending chips + overflow)
 *   - Setup completeness strip (Drive / Key / Files N/15)
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

  // Channel bindings for the chip row (R1, R4)
  const { data: channelBindings = [] } = useChannelBindingsQuery(workspace.id);

  // Drive status for the setup strip (R3)
  const { data: driveStatus } = useDriveStatusQuery(workspace.id);

  // Key status for the setup strip (R3) — share data with KeySection below
  const { data: keyData } = useKeyQuery(workspace.id);

  // Knowledge files count for the setup strip (R3)
  const { data: knowledgeFiles = [] } = useKnowledgeQuery(workspace.id);

  const createdDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(workspace.created_at));

  return (
    <>
      <Card className="shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1 min-w-0">
            {/* Workspace name — links to detail page */}
            <Link
              to="/app/teams/$teamId/$workspaceId"
              params={{ teamId, workspaceId: workspace.id }}
              className="font-semibold text-slate-900 truncate hover:text-brand-500 transition-colors"
            >
              {workspace.name}
            </Link>

            {/* Creation date */}
            <div className="text-xs text-slate-400">
              Created {createdDate}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {/* "DMs route here" badge — only shown when this workspace is the team default (R2) */}
            {workspace.is_default_for_team && (
              <span
                data-testid="dm-badge"
                className="text-xs font-medium text-brand-600 bg-brand-50 rounded-full px-2 py-0.5"
              >
                DMs route here
              </span>
            )}

            {/* Action buttons — R9: use Button component */}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setRenameOpen(true)}
            >
              Rename
            </Button>

            {/* Make Default — only shown on non-default workspaces */}
            {!workspace.is_default_for_team && (
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => makeDefaultMutation.mutate(workspace.id)}
                disabled={makeDefaultMutation.isPending}
              >
                {makeDefaultMutation.isPending ? 'Saving…' : 'Make Default'}
              </Button>
            )}
          </div>
        </div>

        {/* Channel chips row — R1 */}
        <ChannelChipsRow bindings={channelBindings} />

        {/* Setup completeness strip — R3 */}
        <SetupStrip
          driveConnected={driveStatus?.connected ?? false}
          hasKey={keyData?.has_key ?? false}
          fileCount={knowledgeFiles.length}
        />

        {/* BYOK Key Section — STORY-004-04 */}
        <KeySection workspaceId={workspace.id} teamId={teamId} />

        {/* Integrations status chip — full wizard lives on the workspace page. */}
        <IntegrationsChip workspaceId={workspace.id} teamId={teamId} />

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

// ---------------------------------------------------------------------------
// IntegrationsChip — compact status row on the dashboard card
// ---------------------------------------------------------------------------

/**
 * Single-line status chip for MCP integrations on the workspace card.
 *
 * Shows connected count + a deep link to the workspace page's integrations
 * panel. The full add/test/toggle/delete wizard lives on the workspace page
 * (moduleRegistry entry `integrations` under the `workspace` group).
 */
function IntegrationsChip({
  workspaceId,
  teamId,
}: {
  workspaceId: string;
  teamId: string;
}) {
  const { data: servers = [] } = useMcpServersQuery(workspaceId);
  const activeCount = servers.filter((s) => s.is_active).length;

  let label: string;
  if (servers.length === 0) {
    label = 'No integrations connected';
  } else if (activeCount === servers.length) {
    label = `${activeCount} integration${activeCount === 1 ? '' : 's'} connected`;
  } else {
    label = `${activeCount} of ${servers.length} integrations active`;
  }

  return (
    <Link
      to="/app/teams/$teamId/$workspaceId"
      params={{ teamId, workspaceId }}
      hash="tm-integrations"
      className="flex items-center gap-2 text-xs text-slate-500 hover:text-brand-600 transition-colors"
      data-testid="integrations-chip"
    >
      <Plug className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{label}</span>
      <span className="ml-auto text-brand-600 font-semibold">Manage →</span>
    </Link>
  );
}
