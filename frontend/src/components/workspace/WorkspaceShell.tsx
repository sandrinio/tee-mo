/**
 * WorkspaceShell.tsx — Workspace v2 shell: status strip + tab panels.
 *
 * HOTFIX 2026-04-26: pivoted from sticky-tab + scrollspy (Variation B as
 * specced in the design handoff) to true tab panels. Reason: live verification
 * showed the 9-module scrolling page felt overwhelming. The tab bar now acts
 * as a panel switcher — only the active group's modules render at any time.
 * Scrollspy plumbing (useScrollspy.ts, HEADER_OFFSET) is kept on disk but no
 * longer wired through this shell; it can be re-enabled if the product
 * direction reverses.
 *
 * Responsibilities:
 *   - Aggregates 7 useQuery calls into WorkspaceData.
 *   - Gates render on isLoading → renders skeleton while any query is loading.
 *   - Mounts StickyTabBar + StatusStrip + the active group's ModuleSection list.
 *   - Tab click: setActiveGroupId(group). No scroll.
 *   - Deep link cold load: parse #tm-{moduleId} → find which group contains
 *     that module → setActiveGroupId. The hash is preserved across panel swaps.
 *
 * Per W01 §5.2: WorkspaceData shape is frozen for follow-on stories.
 */

import { useState, useEffect, useCallback } from 'react';
import { Link } from '@tanstack/react-router';

import { useWorkspaceQuery } from '../../hooks/useWorkspaces';
import { useDriveStatusQuery } from '../../hooks/useDrive';
import { useKeyQuery } from '../../hooks/useKey';
import { useKnowledgeQuery } from '../../hooks/useKnowledge';
import { useChannelBindingsQuery } from '../../hooks/useChannels';
import { useSkillsQuery } from '../../hooks/useSkills';
import { useAutomationsQuery } from '../../hooks/useAutomations';

import { MODULE_REGISTRY, GROUP_ORDER, GROUP_LABELS } from './moduleRegistry';
import { ModuleSection } from './ModuleSection';
import { StatusStrip } from './StatusStrip';
import { StickyTabBar, type TabGroup } from './StickyTabBar';
import type { WorkspaceData, StatusCell, ModuleGroup } from './types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface WorkspaceShellProps {
  workspaceId: string;
  teamId: string;
}

// ---------------------------------------------------------------------------
// WorkspaceShell
// ---------------------------------------------------------------------------

/**
 * WorkspaceShell — top-level shell for the workspace v2 redesign.
 *
 * Renders a skeleton loader while data is fetching, then renders the full
 * sticky-tab + scrollspy page chrome with placeholder module bodies.
 */
export function WorkspaceShell({ workspaceId, teamId }: WorkspaceShellProps) {
  // ---------------------------------------------------------------------------
  // Data queries — fired in parallel; shell renders progressively as each lands.
  // ---------------------------------------------------------------------------
  //
  // HOTFIX 2026-04-26: previously the shell waited on `wLoading || dLoading
  // || ...` (all 7) before rendering anything — page stayed on skeleton until
  // the slowest query resolved (~600-1000ms tail). Now only `workspace` gates
  // the chrome (breadcrumb + h1 + tab bar shape). Other queries' isLoading
  // flags propagate into the StatusStrip cells so they show "—" until their
  // data lands instead of incorrectly showing the empty-state default.

  const { data: workspace }                          = useWorkspaceQuery(workspaceId);
  const { data: driveStatus }                        = useDriveStatusQuery(workspaceId);
  const { data: keyData,      isLoading: kLoading } = useKeyQuery(workspaceId);
  const { data: knowledge,    isLoading: knLoading }= useKnowledgeQuery(workspaceId);
  const { data: channels,     isLoading: chLoading }= useChannelBindingsQuery(workspaceId);
  const { data: skills }                             = useSkillsQuery(workspaceId);
  const { data: automations }                        = useAutomationsQuery(workspaceId);

  // ---------------------------------------------------------------------------
  // Scrollspy — group anchor ids are the first module id in each group.
  // Foundation ships an empty registry so we fall back to GROUP_ORDER ids.
  // ---------------------------------------------------------------------------

  // ---------------------------------------------------------------------------
  // Registry filter — STORY-025-05: suppress 'workspace' group for non-owners.
  // Computed early (before skeleton guard) so useCallback can close over it.
  // ---------------------------------------------------------------------------

  // Filter entries: workspace-group entries are visible only when is_owner === true.
  // All other group entries are always visible.
  const visibleEntries = MODULE_REGISTRY.filter(
    (entry) => entry.group !== 'workspace' || workspace?.is_owner === true,
  );

  // ---------------------------------------------------------------------------
  // Active group state — panel-mode tabs (HOTFIX 2026-04-26)
  // ---------------------------------------------------------------------------
  //
  // Initial value resolves from the URL hash on first render so deep links
  // like `/<route>#tm-files` open the page on the Knowledge panel directly.
  // Falls back to the first group in GROUP_ORDER ('connections').

  const initialGroup: ModuleGroup = (() => {
    if (typeof window === 'undefined') return GROUP_ORDER[0];
    const hash = window.location.hash;
    if (!hash.startsWith('#tm-')) return GROUP_ORDER[0];
    const moduleId = hash.slice('#tm-'.length);
    const entry = MODULE_REGISTRY.find((e) => e.id === moduleId);
    return entry ? entry.group : GROUP_ORDER[0];
  })();

  const [activeGroupId, setActiveGroupId] = useState<ModuleGroup>(initialGroup);

  // Late hash arrivals (rare — e.g. user pastes deep link after mount) — not
  // a sprint scope concern, but cheap to handle: react to popstate.
  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash;
      if (!hash.startsWith('#tm-')) return;
      const moduleId = hash.slice('#tm-'.length);
      const entry = MODULE_REGISTRY.find((e) => e.id === moduleId);
      if (entry) setActiveGroupId(entry.group);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  // Tab click: swap the panel. Update the hash to the first module of the
  // selected group so reload preserves the panel and copy-link works.
  const onTabClick = useCallback(
    (groupId: ModuleGroup) => {
      setActiveGroupId(groupId);
      const firstEntry = MODULE_REGISTRY.find((e) => e.group === groupId);
      const anchorId = firstEntry ? firstEntry.id : groupId;
      window.history.replaceState(null, '', `#tm-${anchorId}`);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Skeleton loader — only blocks until `workspace` resolves (HOTFIX 2026-04-26).
  // ---------------------------------------------------------------------------

  if (!workspace) {
    return (
      <div
        className="max-w-5xl mx-auto px-4 md:px-8 pt-6 pb-16"
        aria-busy="true"
        aria-label="Loading workspace"
      >
        {/* Header skeleton */}
        <div className="animate-pulse space-y-2 mb-6">
          <div className="h-3 w-24 rounded bg-slate-200" />
          <div className="h-7 w-48 rounded bg-slate-200" />
        </div>
        {/* Status strip skeleton */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="rounded-lg border border-slate-200 bg-white p-4 animate-pulse">
              <div className="h-2 w-12 rounded bg-slate-200 mb-2" />
              <div className="h-4 w-20 rounded bg-slate-200" />
            </div>
          ))}
        </div>
        {/* Tab bar skeleton */}
        <div className="h-12 bg-slate-100 rounded animate-pulse mb-6" />
        {/* Section skeletons */}
        {[0, 1, 2].map((i) => (
          <div key={i} className="animate-pulse mb-8">
            <div className="h-4 w-32 rounded bg-slate-200 mb-3" />
            <div className="rounded-lg border border-slate-200 bg-white h-24" />
          </div>
        ))}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Assemble WorkspaceData
  // ---------------------------------------------------------------------------

  const workspaceData: WorkspaceData = {
    workspace,
    drive: {
      connected: driveStatus?.connected ?? false,
      email: driveStatus?.email,
    },
    key: {
      has_key: keyData?.has_key ?? false,
      provider: keyData?.provider,
      key_hint: keyData?.key_mask,
    },
    channels: channels ?? [],
    files: knowledge ?? [],
    skills: skills ?? [],
    automations: automations ?? [],
  };

  // ---------------------------------------------------------------------------
  // StatusStrip cells — hard-coded 4-cell builder per W01 §5.4
  // ---------------------------------------------------------------------------

  const boundChannels = workspaceData.channels.length;
  const fileCount = workspaceData.files.length;

  // Per-cell isLoading flags differentiate "data not yet loaded" (show "—")
  // from "data loaded, value is empty" (show "Not configured" / "No files").
  // Without this distinction the page would briefly flash empty-state copy
  // before the real values land.
  const statusCells: StatusCell[] = [
    {
      kicker: 'Workspace',
      value: workspace.name,
      caption: workspace.is_default_for_team ? 'Default workspace' : undefined,
    },
    {
      kicker: 'Slack',
      value: workspace.slack_team_id,
      caption: chLoading
        ? '—'
        : boundChannels > 0
          ? `${boundChannels} channel${boundChannels === 1 ? '' : 's'} bound`
          : 'No channels bound',
    },
    {
      kicker: 'Provider',
      value: kLoading
        ? '—'
        : workspaceData.key.has_key
          ? (workspaceData.key.provider ?? 'Configured')
          : 'Not configured',
      caption: kLoading ? undefined : (workspaceData.key.key_hint ?? undefined),
    },
    {
      kicker: 'Knowledge',
      value: knLoading
        ? '—'
        : fileCount > 0
          ? `${fileCount} file${fileCount === 1 ? '' : 's'}`
          : 'No files',
      caption: knLoading
        ? undefined
        : fileCount > 0
          ? 'Files indexed'
          : 'Add files to get started',
    },
  ];

  // ---------------------------------------------------------------------------
  // Tab groups — computed from visible registry entries per group
  // ---------------------------------------------------------------------------

  const tabGroups: TabGroup[] = GROUP_ORDER
    .map((groupId): TabGroup => {
      const entries = visibleEntries.filter((e) => e.group === groupId);
      const okCount = entries.filter(
        (e) => e.statusResolver(workspaceData) === 'ok',
      ).length;
      return {
        id: groupId,
        label: GROUP_LABELS[groupId],
        okCount,
        total: entries.length,
      };
    })
    // Suppress groups with zero visible entries (e.g. 'workspace' for non-owners).
    // Foundation: when registry is totally empty, keep all groups so scrollspy works.
    .filter((group) => visibleEntries.length === 0 || group.total > 0);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-5xl mx-auto px-4 md:px-8 pt-6 pb-16">
      {/* Header */}
      <div className="flex items-end justify-between mb-4 gap-4">
        <div>
          {/* Breadcrumb */}
          <nav
            className="flex items-center gap-1 text-xs text-slate-500 mb-1.5"
            aria-label="Breadcrumb"
          >
            <Link to="/app" className="hover:text-slate-700 transition-colors">
              Teams
            </Link>
            <span className="text-slate-300">/</span>
            <Link
              to="/app/teams/$teamId"
              params={{ teamId }}
              className="hover:text-slate-700 transition-colors"
            >
              {teamId}
            </Link>
            <span className="text-slate-300">/</span>
            <span className="text-slate-700 font-medium">{workspace.name}</span>
          </nav>

          <h1
            className="text-2xl font-semibold text-slate-900"
            style={{ letterSpacing: '-0.015em' }}
          >
            {workspace.name}
          </h1>
        </div>
      </div>

      {/* Status strip */}
      <div className="mb-4">
        <StatusStrip cells={statusCells} />
      </div>

      {/* Sticky tab bar */}
      <StickyTabBar
        groups={tabGroups}
        activeGroupId={activeGroupId}
        onTabClick={onTabClick}
      />

      {/* Active group panel — HOTFIX 2026-04-26: only one group visible at a time. */}
      <div className="mt-6 space-y-5" data-testid={`panel-${activeGroupId}`}>
        {visibleEntries
          .filter((entry) => entry.group === activeGroupId)
          .map((entry) => (
            <ModuleSection
              key={entry.id}
              id={entry.id}
              title={entry.label}
              caption={entry.summary}
            >
              {entry.render({ workspace, workspaceId, teamId, data: workspaceData })}
            </ModuleSection>
          ))}
      </div>
    </div>
  );
}
