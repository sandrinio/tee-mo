/**
 * DangerZoneSection.test.tsx — Vitest tests for STORY-025-05.
 *
 * Covers 2 Gherkin scenarios from STORY-025-05 §2.1:
 *   Scenario 6 — Danger zone visible to owner (is_owner=true)
 *   Scenario 7 — Danger zone hidden from non-owner (is_owner=false)
 *
 * Strategy:
 *   - Mock useWorkspaceQuery to return workspace with is_owner=true / false.
 *   - Render WorkspaceShell.
 *   - Assert StickyTabBar contains/omits the "Workspace" tab.
 *   - Assert DangerZoneSection text is present/absent.
 *
 * Per W01 §3 STORY-025-05 Vitest scenarios:
 *   1. Workspace tab visible for owner — render shell with is_owner=true;
 *      assert tab "Workspace" in StickyTabBar; assert DangerZoneSection rendered.
 *   2. Workspace tab absent for member — same with is_owner=false;
 *      assert tab NOT present; assert no DangerZoneSection in DOM.
 */

import { render, screen, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

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
} = vi.hoisted(() => ({
  mockUseWorkspaceQuery:       vi.fn(),
  mockUseDriveStatusQuery:     vi.fn(),
  mockUseKeyQuery:             vi.fn(),
  mockUseKnowledgeQuery:       vi.fn(),
  mockUseChannelBindingsQuery: vi.fn(),
  mockUseSkillsQuery:          vi.fn(),
  mockUseAutomationsQuery:     vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
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

// TanStack Router mock — WorkspaceShell uses Link; DangerZoneSection uses useNavigate
vi.mock('@tanstack/react-router', () => ({
  Link: ({ children, ...props }: { children: React.ReactNode; to: string; params?: object }) =>
    React.createElement('a', { href: props.to }, children),
  useNavigate: () => vi.fn(),
}));

// Section component mocks — HOTFIX 2026-04-26: registry now renders real
// section bodies, but most don't need their internal hooks for shell tests.
// Mock to lightweight stubs that render an identifying marker. DangerZoneSection
// renders the literal "Danger zone" text so existing screen.queryByText('Danger zone')
// assertions still work.
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

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

import { WorkspaceShell } from '../WorkspaceShell';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return React.createElement(
    QueryClientProvider,
    { client: makeQueryClient() },
    children,
  );
}

const BASE_WORKSPACE = {
  id: 'ws-1',
  name: 'Acme Corp',
  slack_team_id: 'T0ABC',
  owner_user_id: 'u-1',
  is_default_for_team: true,
  bot_persona: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

function setupMocks(workspaceOverrides: object) {
  mockUseWorkspaceQuery.mockReturnValue({
    data: { ...BASE_WORKSPACE, ...workspaceOverrides },
    isLoading: false,
  });
  mockUseDriveStatusQuery.mockReturnValue({
    data: { connected: false, email: null },
    isLoading: false,
  });
  mockUseKeyQuery.mockReturnValue({
    data: { has_key: false, provider: null, key_mask: null, ai_model: null },
    isLoading: false,
  });
  mockUseKnowledgeQuery.mockReturnValue({ data: [], isLoading: false });
  mockUseChannelBindingsQuery.mockReturnValue({ data: [], isLoading: false });
  mockUseSkillsQuery.mockReturnValue({ data: [], isLoading: false });
  mockUseAutomationsQuery.mockReturnValue({ data: [], isLoading: false });
}

// ---------------------------------------------------------------------------
// Scenario: Workspace tab visible when is_owner=true
// ---------------------------------------------------------------------------

describe('Scenario: Workspace tab visible when is_owner=true', () => {
  beforeEach(() => {
    setupMocks({ is_owner: true });
  });

  it('renders the Workspace tab and DangerZoneSection when is_owner is true', async () => {
    await act(async () => {
      render(
        React.createElement(
          Wrapper,
          null,
          React.createElement(WorkspaceShell, { workspaceId: 'ws-1', teamId: 'T0ABC' }),
        ),
      );
    });

    // The Workspace tab should be present in the StickyTabBar.
    const workspaceTab = screen.queryByRole('button', { name: /workspace/i });
    expect(workspaceTab).not.toBeNull();

    // HOTFIX 2026-04-26 panel mode: default panel is 'connections'; the
    // Workspace panel mounts only after the Workspace tab is clicked.
    await act(async () => {
      workspaceTab!.click();
    });

    // The DangerZoneSection should now be rendered. Use testid since "Danger zone"
    // text appears in both the ModuleSection h2 wrapper AND the mock body.
    const dangerSection = screen.queryByTestId('mock-danger');
    expect(dangerSection).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Scenario: Workspace tab absent when is_owner=false
// ---------------------------------------------------------------------------

describe('Scenario: Workspace tab absent when is_owner=false', () => {
  beforeEach(() => {
    setupMocks({ is_owner: false });
  });

  it('hides the Workspace tab and DangerZoneSection when is_owner is false', async () => {
    await act(async () => {
      render(
        React.createElement(
          Wrapper,
          null,
          React.createElement(WorkspaceShell, { workspaceId: 'ws-1', teamId: 'T0ABC' }),
        ),
      );
    });

    // The Workspace tab should NOT be present in the StickyTabBar.
    const workspaceTab = screen.queryByRole('button', { name: /^workspace$/i });
    expect(workspaceTab).toBeNull();

    // The DangerZoneSection should NOT be rendered (registry filtered it out
    // because is_owner=false).
    const dangerSection = screen.queryByTestId('mock-danger');
    expect(dangerSection).toBeNull();
  });
});
