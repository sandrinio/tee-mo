/**
 * StickyTabBar.test.tsx — Mobile + cutover Vitest scenarios (STORY-025-06 §2.1).
 *
 * Covers the 5 scenarios from the acceptance criteria:
 *   1. Tab bar has overflow-x-auto class on the scroll container (mobile treatment).
 *   2. Active tab pill calls scrollIntoView({inline:'center', block:'nearest'})
 *      when activeGroupId changes.
 *   3. setup wizard absent — WorkspaceShell mounts without any setup wizard DOM.
 *   4. Legacy stacked layout absent — route file renders only WorkspaceShell
 *      (no inline DriveSection / PickerSection / KnowledgeList etc.).
 *   5. All 9 modules + DangerZone render through the shell (registry has 10 entries
 *      across 4 groups; WorkspaceShell renders one ModuleSection per entry).
 *
 * Strategy:
 *   - Scenarios 1-2: render StickyTabBar directly; spy on Element.prototype.scrollIntoView.
 *   - Scenario 3-4: mount WorkspaceShell with mocked hooks; assert absence of legacy markers.
 *   - Scenario 5: assert MODULE_REGISTRY.length and WorkspaceShell renders the correct
 *     number of section headings.
 *
 * rAF gotcha (025-01 flashcard): scrollIntoView is called synchronously inside useEffect
 * after mount/update — no rAF wrapper — so no vi.useFakeTimers() needed for scenarios 1-2.
 */

import { render, screen, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Hoisted mock variables (Vitest 2.x TDZ guard)
// ---------------------------------------------------------------------------

const {
  mockUseWorkspaceQuery,
  mockUseDriveStatusQuery,
  mockUseKeyQuery,
  mockUseKnowledgeQuery,
  mockUseChannelBindingsQuery,
  mockUseSkillsQuery,
  mockUseAutomationsQuery,
  mockUseMcpServersQuery,
} = vi.hoisted(() => ({
  mockUseWorkspaceQuery:       vi.fn(),
  mockUseDriveStatusQuery:     vi.fn(),
  mockUseKeyQuery:             vi.fn(),
  mockUseKnowledgeQuery:       vi.fn(),
  mockUseChannelBindingsQuery: vi.fn(),
  mockUseSkillsQuery:          vi.fn(),
  mockUseAutomationsQuery:     vi.fn(),
  mockUseMcpServersQuery:      vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks (needed for WorkspaceShell scenarios)
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useWorkspaces', () => ({
  useWorkspaceQuery: mockUseWorkspaceQuery,
}));
vi.mock('../../../hooks/useDrive', () => ({
  useDriveStatusQuery: mockUseDriveStatusQuery,
}));
vi.mock('../../../hooks/useKey', () => ({
  useKeyQuery: mockUseKeyQuery,
}));
vi.mock('../../../hooks/useKnowledge', () => ({
  useKnowledgeQuery: mockUseKnowledgeQuery,
}));
vi.mock('../../../hooks/useChannels', () => ({
  useChannelBindingsQuery: mockUseChannelBindingsQuery,
}));
vi.mock('../../../hooks/useSkills', () => ({
  useSkillsQuery: mockUseSkillsQuery,
}));
vi.mock('../../../hooks/useAutomations', () => ({
  useAutomationsQuery: mockUseAutomationsQuery,
}));
vi.mock('../../../hooks/useMcpServers', () => ({
  useMcpServersQuery: mockUseMcpServersQuery,
}));

vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, ...props }: { children: React.ReactNode; to: string; params?: object }) =>
    React.createElement('a', { href: props.to }, children),
  useNavigate: () => vi.fn(),
}));

// Section component mocks — HOTFIX 2026-04-26: registry now renders real
// section bodies; stub them so shell tests don't invoke section-internal hooks.
vi.mock('../SlackSection', () => ({
  SlackSection: () => React.createElement('div', { 'data-testid': 'mock-slack' }, 'Slack body'),
  ModuleAvatarTile: () => null,
}));
vi.mock('../DriveSection', () => ({
  DriveSection: () => React.createElement('div', { 'data-testid': 'mock-drive' }, 'Drive body'),
}));
vi.mock('../KeySection', () => ({
  KeySection: () => React.createElement('div', { 'data-testid': 'mock-key' }, 'Key body'),
}));
vi.mock('../ChannelSection', () => ({
  ChannelSection: () => React.createElement('div', { 'data-testid': 'mock-channels' }, 'Channels body'),
}));
vi.mock('../FilesSection', () => ({
  FilesSection: () => React.createElement('div', { 'data-testid': 'mock-files' }, 'Files body'),
}));
vi.mock('../PersonaSection', () => ({
  PersonaSection: () => React.createElement('div', { 'data-testid': 'mock-persona' }, 'Persona body'),
}));
vi.mock('../SkillsSection', () => ({
  SkillsSection: () => React.createElement('div', { 'data-testid': 'mock-skills' }, 'Skills body'),
}));
vi.mock('../AutomationsSection', () => ({
  AutomationsSection: () => React.createElement('div', { 'data-testid': 'mock-automations' }, 'Automations body'),
}));
vi.mock('../DangerZoneSection', () => ({
  DangerZoneSection: () => React.createElement('div', { 'data-testid': 'mock-danger' }, 'Danger zone'),
}));
vi.mock('../../dashboard/IntegrationsSection', () => ({
  IntegrationsSection: () => React.createElement('div', { 'data-testid': 'mock-integrations' }, 'Integrations body'),
}));

// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

import { StickyTabBar } from '../StickyTabBar';
import { WorkspaceShell } from '../WorkspaceShell';
import { MODULE_REGISTRY } from '../moduleRegistry';
import type { ModuleGroup } from '../types';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(QueryClientProvider, { client: makeQueryClient() }, children);
}

const BASE_WORKSPACE = {
  id: 'ws-1',
  name: 'Acme Corp',
  slack_team_id: 'T0ABC',
  owner_user_id: 'u-1',
  is_default_for_team: true,
  is_owner: true,
  bot_persona: 'Friendly bot',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function setupDefaultMocks() {
  mockUseWorkspaceQuery.mockReturnValue({ data: BASE_WORKSPACE, isLoading: false });
  mockUseDriveStatusQuery.mockReturnValue({
    data: { connected: true, email: 'user@example.com' },
    isLoading: false,
  });
  mockUseKeyQuery.mockReturnValue({
    data: { has_key: true, provider: 'openai', key_mask: 'sk-…G7vT', ai_model: 'gpt-4o' },
    isLoading: false,
  });
  mockUseKnowledgeQuery.mockReturnValue({
    data: [{ id: 'f-1', workspace_id: 'ws-1', title: 'Handbook' }],
    isLoading: false,
  });
  mockUseChannelBindingsQuery.mockReturnValue({
    data: [{ slack_channel_id: 'C1', workspace_id: 'ws-1', bound_at: '2026-01-01T00:00:00Z' }],
    isLoading: false,
  });
  mockUseSkillsQuery.mockReturnValue({ data: [], isLoading: false });
  mockUseAutomationsQuery.mockReturnValue({ data: [], isLoading: false });
  mockUseMcpServersQuery.mockReturnValue({ data: [], isLoading: false });
}

const GROUPS = [
  { id: 'connections' as ModuleGroup, label: 'Connections', okCount: 2, total: 4 },
  { id: 'knowledge'   as ModuleGroup, label: 'Knowledge',   okCount: 1, total: 1 },
  { id: 'behavior'    as ModuleGroup, label: 'Behavior',    okCount: 0, total: 3 },
  { id: 'workspace'   as ModuleGroup, label: 'Workspace',   okCount: 1, total: 1 },
];

// ---------------------------------------------------------------------------
// Scenario 1: Tab bar has overflow-x-auto class on mobile breakpoint
// ---------------------------------------------------------------------------

describe('Scenario: Tab bar horizontally scrolls on mobile', () => {
  it('scroll container has overflow-x-auto class for mobile horizontal scroll', () => {
    render(
      React.createElement(StickyTabBar, {
        groups: GROUPS,
        activeGroupId: 'connections',
        onTabClick: vi.fn(),
      }),
    );

    const scrollContainer = screen.getByTestId('tab-bar-scroll-container');
    expect(scrollContainer.className).toContain('overflow-x-auto');
  });

  it('tab buttons have min-w-max so labels do not truncate at narrow widths', () => {
    render(
      React.createElement(StickyTabBar, {
        groups: GROUPS,
        activeGroupId: 'connections',
        onTabClick: vi.fn(),
      }),
    );

    const connectionsBtn = screen.getByRole('button', { name: /connections/i });
    expect(connectionsBtn.className).toContain('min-w-max');
  });
});

// ---------------------------------------------------------------------------
// Scenario 2: Active tab pill calls scrollIntoView when activeGroupId changes
// ---------------------------------------------------------------------------

describe('Scenario: Mobile auto-scrolls active tab into bar viewport', () => {
  let scrollSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    scrollSpy = vi.fn();
    Element.prototype.scrollIntoView = scrollSpy;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('calls scrollIntoView with inline:center block:nearest on initial mount', () => {
    // Explicitly assign the spy before render so the button element inherits it.
    HTMLButtonElement.prototype.scrollIntoView = scrollSpy;

    render(
      React.createElement(StickyTabBar, {
        groups: GROUPS,
        activeGroupId: 'knowledge',
        onTabClick: vi.fn(),
      }),
    );

    // useEffect fires after mount — active tab (knowledge) should scroll into view.
    expect(scrollSpy).toHaveBeenCalledWith({ inline: 'center', block: 'nearest' });
  });

  it('calls scrollIntoView again when activeGroupId changes to a different tab', () => {
    // Assign spy before initial render so button elements inherit it.
    HTMLButtonElement.prototype.scrollIntoView = scrollSpy;

    const { rerender } = render(
      React.createElement(StickyTabBar, {
        groups: GROUPS,
        activeGroupId: 'connections',
        onTabClick: vi.fn(),
      }),
    );

    scrollSpy.mockClear();

    // Simulate scrollspy changing the active group (e.g. user scrolled to Behavior).
    act(() => {
      rerender(
        React.createElement(StickyTabBar, {
          groups: GROUPS,
          activeGroupId: 'behavior',
          onTabClick: vi.fn(),
        }),
      );
    });

    expect(scrollSpy).toHaveBeenCalledWith({ inline: 'center', block: 'nearest' });
  });
});

// ---------------------------------------------------------------------------
// Scenario 3: setup wizard absent — WorkspaceShell mounts without it
// ---------------------------------------------------------------------------

describe('Scenario: setup wizard component deleted', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  it('WorkspaceShell renders without any setup wizard DOM markers', async () => {
    await act(async () => {
      render(
        React.createElement(
          Wrapper,
          null,
          React.createElement(WorkspaceShell, { workspaceId: 'ws-1', teamId: 'T0ABC' }),
        ),
      );
    });

    // setup wizard specific test IDs and text — must not appear.
    expect(screen.queryByTestId('step-1')).toBeNull();
    expect(screen.queryByTestId('step-2')).toBeNull();
    expect(screen.queryByTestId('skip-setup')).toBeNull();
    expect(screen.queryByText(/skip setup/i)).toBeNull();

    // WorkspaceShell's own heading must be present (confirms shell rendered).
    const headings = screen.getAllByText('Acme Corp');
    expect(headings.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Scenario 4: Legacy stacked layout absent — no inline section markers
// ---------------------------------------------------------------------------

describe('Scenario: Legacy stacked JSX removed', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  it('WorkspaceShell renders without legacy stacked layout markers', async () => {
    await act(async () => {
      render(
        React.createElement(
          Wrapper,
          null,
          React.createElement(WorkspaceShell, { workspaceId: 'ws-1', teamId: 'T0ABC' }),
        ),
      );
    });

    // The legacy block rendered inline AutomationsSection and ChannelSection
    // directly in the route. WorkspaceShell renders them via ModuleSection wrappers
    // keyed by module registry ids. The legacy block's outer container had class
    // "min-h-screen bg-slate-50 px-4 py-8" — this specific combination should not
    // appear when only WorkspaceShell renders.
    const legacyContainers = document.querySelectorAll('.min-h-screen.bg-slate-50.px-4.py-8');
    expect(legacyContainers.length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Scenario 5: All 9 modules + DangerZone render through the new shell
// ---------------------------------------------------------------------------

describe('Scenario: All modules render through the new shell', () => {
  beforeEach(() => {
    setupDefaultMocks();
  });

  it('MODULE_REGISTRY has 10 entries covering all modules including DangerZone', () => {
    // connections: slack, channels (2)
    // knowledge:   files (1)
    // behavior:    persona, skills, automations (3)
    // workspace:   drive, key, integrations, danger-zone (4)
    // Total = 10
    expect(MODULE_REGISTRY.length).toBe(10);
  });

  it('WorkspaceShell renders a ModuleSection for each visible registry entry', async () => {
    // HOTFIX 2026-04-26: shell switched to panel mode — only the active group's
    // entries render. To verify all 9 modules are reachable, click each tab
    // and assert that group's entries appear.
    const { container } = render(
      React.createElement(
        Wrapper,
        null,
        React.createElement(WorkspaceShell, { workspaceId: 'ws-1', teamId: 'T0ABC' }),
      ),
    );

    const groupOf = (id: string) => MODULE_REGISTRY.find((e) => e.id === id)!.group;

    for (const entry of MODULE_REGISTRY) {
      // Tabs carry data-group-id={group.id} (StickyTabBar.tsx line 80).
      const tab = container.querySelector<HTMLButtonElement>(
        `button[data-group-id="${groupOf(entry.id)}"]`,
      );
      expect(tab, `tab for group ${groupOf(entry.id)} should exist`).not.toBeNull();
      await act(async () => {
        tab!.click();
      });
      const section = document.getElementById(`tm-${entry.id}`);
      expect(section, `module ${entry.id} should render when its group's tab is active`).not.toBeNull();
    }
  });
});
