/**
 * moduleRegistry.ts — Module registry for the Workspace v2 shell (STORY-025-01).
 *
 * Exports the typed registry array and related constants consumed by
 * WorkspaceShell, StickyTabBar, and all module section components.
 *
 * STORY-025-01 ships an EMPTY registry (no entries yet).
 * Follow-on stories append entries in group order:
 *   STORY-025-02 → 4 Connections entries (slack, drive, key, channels)
 *   STORY-025-03 → 1 Knowledge entry   (files)
 *   STORY-025-04 → 3 Behavior entries  (persona, skills, automations)
 *   STORY-025-05 → 1 Workspace entry   (danger-zone)
 *
 * CONVENTION FOR FOLLOW-ON STORIES:
 *   1. Import `ModuleEntry` from `./types`.
 *   2. Add your entries to the CORRECT append block below (one block per story).
 *   3. Do NOT reorder existing entries — ordering drives the scrollspy group order.
 *   4. StatusResolvers MUST use `?.` / `?? defaultValue` — never throw on missing data.
 *
 * Per W01 §5.3: WorkspaceData is passed to each statusResolver once per render.
 */

import { AlertTriangle, MessageSquare, FolderOpen, KeyRound, Hash, FileText, UserRound, Sparkles, Zap } from 'lucide-react';
import type { ModuleEntry, ModuleGroup } from './types';

// Section components — wired into entry.render() per HOTFIX 2026-04-26.
import { SlackSection } from './SlackSection';
import { DriveSection } from './DriveSection';
import { KeySection } from './KeySection';
import { ChannelSection } from './ChannelSection';
import { FilesSection } from './FilesSection';
import { PersonaSection } from './PersonaSection';
import { SkillsSection } from './SkillsSection';
import { AutomationsSection } from './AutomationsSection';
import { DangerZoneSection } from './DangerZoneSection';

// Re-export convenience types so follow-on stories import from a single file.
export type { ModuleEntry, ModuleGroup };
export type { ModuleStatus, StatusResolver, WorkspaceData, StatusCell, ModuleRenderContext } from './types';

// ---------------------------------------------------------------------------
// Group ordering and labels (frozen — consumed by StickyTabBar)
// ---------------------------------------------------------------------------

/**
 * Canonical render order for navigation groups.
 * StickyTabBar iterates this to build tabs in the correct order.
 */
export const GROUP_ORDER: ModuleGroup[] = [
  'connections',
  'knowledge',
  'behavior',
  'workspace',
];

/**
 * Human-readable group labels for the sticky tab bar pills.
 */
export const GROUP_LABELS: Record<ModuleGroup, string> = {
  connections: 'Connections',
  knowledge:   'Knowledge',
  behavior:    'Behavior',
  workspace:   'Workspace',
};

// ---------------------------------------------------------------------------
// Module registry
// ---------------------------------------------------------------------------

/**
 * MODULE_REGISTRY — the ordered list of all module entries.
 *
 * Foundation (STORY-025-01): empty array.
 * Follow-on stories push their entries in the blocks below.
 *
 * NOTE: exported as `const` — do NOT mutate at runtime. All appends happen
 * at module initialisation time (module-level push calls below).
 */
export const MODULE_REGISTRY: ModuleEntry[] = [
  // ---------------------------------------------------------------------------
  // STORY-025-02: connections group entries
  // ---------------------------------------------------------------------------
  {
    id: 'slack',
    group: 'connections',
    label: 'Slack',
    icon: MessageSquare,
    summary: 'Slack workspace connection',
    // Slack is ok when the workspace has a slack_team_id (i.e. is installed).
    statusResolver: (data) => (data.workspace.slack_team_id ? 'ok' : 'empty'),
    render: ({ workspace, teamId }) => <SlackSection workspace={workspace} teamId={teamId} />,
  },
  {
    id: 'channels',
    group: 'connections',
    label: 'Channels',
    icon: Hash,
    summary: 'Bound Slack channels',
    // Channels is ok when at least one channel is bound, empty otherwise.
    statusResolver: (data) => ((data.channels?.length ?? 0) > 0 ? 'ok' : 'empty'),
    render: ({ workspaceId, teamId }) => <ChannelSection workspaceId={workspaceId} teamId={teamId} />,
  },

  // ---------------------------------------------------------------------------
  // STORY-025-03: knowledge group entries
  // ---------------------------------------------------------------------------
  {
    id: 'files',
    group: 'knowledge',
    label: 'Files',
    icon: FileText,
    summary: 'Indexed knowledge files',
    /**
     * Status resolver for the Files module (STORY-025-03 §1.2):
     *   - ok      → files.length >= 15 (well-populated knowledge base)
     *   - partial → files.length >= 1 and < 15 (some files but under threshold)
     *   - empty   → files.length === 0 (no files indexed yet)
     *
     * The "15" boundary is the partial/ok threshold — NOT the file cap (cap = 100).
     * See W01 §3 STORY-025-03 risk note on R-CAP DRIFT.
     */
    statusResolver: (data) => {
      const count = data.files?.length ?? 0;
      if (count === 0)  return 'empty';
      if (count < 15)   return 'partial';
      return 'ok';
    },
    render: ({ workspaceId, data }) => (
      <FilesSection
        workspaceId={workspaceId}
        driveConnected={data.drive?.connected ?? false}
        hasKey={data.key?.has_key ?? false}
      />
    ),
  },

  // ---------------------------------------------------------------------------
  // STORY-025-04: behavior group entries
  // (persona, skills, automations)
  // ---------------------------------------------------------------------------
  {
    id: 'persona',
    group: 'behavior',
    label: 'Persona',
    icon: UserRound,
    summary: 'Bot persona and identity',
    /**
     * Status resolver for Persona (STORY-025-04 §1.2):
     *   - ok    → bot_persona is non-empty string
     *   - empty → bot_persona is empty, null, or undefined
     *
     * NEVER returns 'partial' (epic §6 Q5 — Persona is binary ok/empty).
     * Textarea always renders regardless of status; dot just reflects truth.
     */
    statusResolver: (data) =>
      (data.workspace.bot_persona?.trim() ?? '') !== '' ? 'ok' : 'empty',
    render: ({ workspace }) => <PersonaSection workspace={workspace} />,
  },
  {
    id: 'skills',
    group: 'behavior',
    label: 'Skills',
    icon: Sparkles,
    summary: 'Active skill catalog',
    // Skills ok if at least one skill exists, empty otherwise.
    statusResolver: (data) => ((data.skills?.length ?? 0) > 0 ? 'ok' : 'empty'),
    render: ({ workspaceId }) => <SkillsSection workspaceId={workspaceId} />,
  },
  {
    id: 'automations',
    group: 'behavior',
    label: 'Automations',
    icon: Zap,
    summary: 'Scheduled and event-driven automations',
    // Automations ok if at least one trigger exists, empty otherwise.
    statusResolver: (data) => ((data.automations?.length ?? 0) > 0 ? 'ok' : 'empty'),
    render: ({ workspaceId, data }) => (
      <AutomationsSection workspaceId={workspaceId} channelBindings={data.channels ?? []} />
    ),
  },

  // ---------------------------------------------------------------------------
  // Workspace group entries — admin-only (is_owner-gated by WorkspaceShell).
  // Drive + AI provider moved here from Connections (HOTFIX 2026-04-26 per
  // user request: workspace-level integrations belong with admin actions).
  // Order: drive (most-touched), key, danger-zone (destructive last).
  // ---------------------------------------------------------------------------
  {
    id: 'drive',
    group: 'workspace',
    label: 'Google Drive',
    icon: FolderOpen,
    summary: 'Google Drive connection',
    // Drive is ok when connected, empty otherwise.
    statusResolver: (data) => (data.drive?.connected ? 'ok' : 'empty'),
    render: ({ workspaceId }) => <DriveSection workspaceId={workspaceId} />,
  },
  {
    id: 'key',
    group: 'workspace',
    label: 'AI provider',
    icon: KeyRound,
    summary: 'BYOK API key',
    // Key is ok when a key is stored, empty otherwise.
    statusResolver: (data) => (data.key?.has_key ? 'ok' : 'empty'),
    render: ({ workspaceId, teamId }) => <KeySection workspaceId={workspaceId} teamId={teamId} />,
  },
  {
    id: 'danger-zone',
    group: 'workspace',
    label: 'Danger zone',
    icon: AlertTriangle,
    summary: 'Delete or transfer workspace',
    // Danger zone is action-only — always neutral, never carries a status.
    statusResolver: () => 'neutral',
    render: ({ workspaceId, workspace, teamId }) => (
      <DangerZoneSection
        workspaceId={workspaceId}
        workspaceName={workspace.name}
        teamId={teamId}
      />
    ),
  },
];
