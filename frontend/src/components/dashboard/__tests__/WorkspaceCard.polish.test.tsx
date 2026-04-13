/**
 * WorkspaceCard.polish.test.tsx — STORY-008-03 acceptance tests.
 *
 * Tests added by this story:
 *   R1: Channel chips row — up to 3 chips (emerald Active / amber Pending),
 *       "+N more" overflow when >3 bindings.
 *   R2: "DMs route here" badge when workspace.is_default_for_team === true.
 *   R3: Setup completeness indicators — Drive (green/slate), Key (green/slate),
 *       Files N/15 (green/slate).
 *   R4: Channel bindings are fetched via useChannelBindingsQuery(workspace.id).
 *
 * Mocking strategy (Vitest 2.x):
 *   - vi.hoisted() for all spy variables referenced inside vi.mock factories
 *     (FLASHCARDS.md: "Vitest 2.x vi.mock hoisting TDZ").
 *   - globals: true in vitest.config.ts provides automatic afterEach cleanup.
 */
import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import type { Workspace, ChannelBinding, ProviderKey, DriveStatus } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Hoisted mock variables (FLASHCARDS.md TDZ rule)
// ---------------------------------------------------------------------------

const {
  makeDefaultMutateFn,
  renameMutateFn,
  channelBindingsMockData,
  keyDataMock,
  driveStatusMock,
  knowledgeFilesMock,
} = vi.hoisted(() => ({
  makeDefaultMutateFn: vi.fn(),
  renameMutateFn: vi.fn(),
  channelBindingsMockData: { current: [] as ChannelBinding[] },
  keyDataMock: { current: { has_key: false, provider: null, key_mask: null, ai_model: null } as ProviderKey },
  driveStatusMock: { current: { connected: false, email: null } as DriveStatus },
  knowledgeFilesMock: { current: [] as { id: string }[] },
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

// Mock TanStack Router Link to avoid needing a RouterProvider.
vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router');
  return {
    ...actual,
    Link: ({ children, to: _to, params: _params, ...props }: { children?: React.ReactNode; to?: string; params?: Record<string, string> } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
      <a {...props}>{children}</a>
    ),
  };
});

vi.mock('../../../hooks/useKey', () => ({
  useKeyQuery: vi.fn(() => ({
    data: keyDataMock.current,
    isLoading: false,
  })),
  useSaveKeyMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false, error: null })),
  useDeleteKeyMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false, error: null })),
}));

vi.mock('../../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../lib/api')>();
  return { ...actual, validateKey: vi.fn() };
});

vi.mock('../../../hooks/useWorkspaces', () => ({
  useMakeDefaultMutation: (_teamId: string) => ({
    mutate: makeDefaultMutateFn,
    isPending: false,
    error: null,
  }),
  useRenameWorkspaceMutation: () => ({
    mutateAsync: renameMutateFn,
    isPending: false,
    error: null,
    reset: vi.fn(),
  }),
}));

vi.mock('../../../hooks/useChannels', () => ({
  useChannelBindingsQuery: vi.fn(() => ({
    data: channelBindingsMockData.current,
    isLoading: false,
  })),
}));

vi.mock('../../../hooks/useDrive', () => ({
  useDriveStatusQuery: vi.fn(() => ({
    data: driveStatusMock.current,
    isLoading: false,
  })),
}));

vi.mock('../../../hooks/useKnowledge', () => ({
  useKnowledgeQuery: vi.fn(() => ({
    data: knowledgeFilesMock.current,
    isLoading: false,
  })),
}));

// ---------------------------------------------------------------------------
// Test data helpers
// ---------------------------------------------------------------------------

/** A non-default workspace fixture. */
const nonDefaultWorkspace: Workspace = {
  id: 'ws-001',
  name: 'My Workspace',
  slack_team_id: 'T-TEAM-001',
  owner_user_id: 'user-001',
  is_default_for_team: false,
  created_at: '2024-01-15T10:00:00Z',
};

/** A default workspace fixture. */
const defaultWorkspace: Workspace = {
  ...nonDefaultWorkspace,
  id: 'ws-002',
  name: 'Default Workspace',
  is_default_for_team: true,
};

/** Build a channel binding fixture with given is_member status. */
function makeBinding(id: string, name: string, isMember: boolean): ChannelBinding {
  return {
    slack_channel_id: id,
    workspace_id: 'ws-001',
    bound_at: '2024-01-15T10:00:00Z',
    channel_name: name,
    is_member: isMember,
  };
}

// ---------------------------------------------------------------------------
// Import component under test AFTER mocks are set up
// ---------------------------------------------------------------------------
import { WorkspaceCard } from '../WorkspaceCard';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkspaceCard — STORY-008-03 polish', () => {
  beforeEach(() => {
    makeDefaultMutateFn.mockClear();
    renameMutateFn.mockClear();
    // Reset to defaults
    channelBindingsMockData.current = [];
    keyDataMock.current = { has_key: false, provider: null, key_mask: null, ai_model: null };
    driveStatusMock.current = { connected: false, email: null };
    knowledgeFilesMock.current = [];
  });

  // --------------------------------------------------------------------------
  // R1: Channel chips
  // --------------------------------------------------------------------------

  describe('R1: Channel chips', () => {
    it('shows no chip row when there are no channel bindings', () => {
      channelBindingsMockData.current = [];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);
      // No channel chips rendered
      expect(screen.queryByTestId('channel-chip')).toBeNull();
    });

    it('renders an emerald chip for an Active (is_member=true) channel binding', () => {
      channelBindingsMockData.current = [makeBinding('C001', 'general', true)];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const chip = screen.getByTestId('channel-chip');
      expect(chip).toBeInTheDocument();
      expect(chip).toHaveTextContent('general');
      // Emerald styling for active channel
      expect(chip.className).toMatch(/emerald/);
    });

    it('renders an amber chip for a Pending (is_member=false) channel binding', () => {
      channelBindingsMockData.current = [makeBinding('C002', 'private-channel', false)];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const chip = screen.getByTestId('channel-chip');
      expect(chip).toBeInTheDocument();
      expect(chip).toHaveTextContent('private-channel');
      // Amber styling for pending channel
      expect(chip.className).toMatch(/amber/);
    });

    it('shows at most 3 chips and a "+N more" label when bindings exceed 3', () => {
      channelBindingsMockData.current = [
        makeBinding('C001', 'general', true),
        makeBinding('C002', 'announcements', true),
        makeBinding('C003', 'random', false),
        makeBinding('C004', 'dev', true),
        makeBinding('C005', 'design', false),
      ];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const chips = screen.getAllByTestId('channel-chip');
      expect(chips).toHaveLength(3);

      // Overflow label "+2 more" (5 bindings - 3 shown = 2)
      expect(screen.getByTestId('channel-overflow')).toHaveTextContent('+2 more');
    });

    it('does not show overflow label when bindings are exactly 3', () => {
      channelBindingsMockData.current = [
        makeBinding('C001', 'general', true),
        makeBinding('C002', 'random', true),
        makeBinding('C003', 'dev', false),
      ];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const chips = screen.getAllByTestId('channel-chip');
      expect(chips).toHaveLength(3);
      expect(screen.queryByTestId('channel-overflow')).toBeNull();
    });
  });

  // --------------------------------------------------------------------------
  // R2: "DMs route here" badge
  // --------------------------------------------------------------------------

  describe('R2: DMs route here badge', () => {
    it('shows the "DMs route here" badge on the default workspace', () => {
      render(<WorkspaceCard workspace={defaultWorkspace} teamId="T-TEAM-001" />);
      expect(screen.getByTestId('dm-badge')).toBeInTheDocument();
      expect(screen.getByTestId('dm-badge')).toHaveTextContent('DMs route here');
    });

    it('does NOT show the "DMs route here" badge on non-default workspaces', () => {
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);
      expect(screen.queryByTestId('dm-badge')).toBeNull();
    });

    it('"DMs route here" badge uses brand-600 text on brand-50 background', () => {
      render(<WorkspaceCard workspace={defaultWorkspace} teamId="T-TEAM-001" />);
      const badge = screen.getByTestId('dm-badge');
      expect(badge.className).toMatch(/text-brand-600/);
      expect(badge.className).toMatch(/bg-brand-50/);
    });
  });

  // --------------------------------------------------------------------------
  // R3: Setup completeness indicators
  // --------------------------------------------------------------------------

  describe('R3: Setup completeness indicators', () => {
    it('shows "Drive" indicator in slate when Drive is not connected', () => {
      driveStatusMock.current = { connected: false, email: null };
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const driveIndicator = screen.getByTestId('setup-drive');
      expect(driveIndicator).toBeInTheDocument();
      expect(driveIndicator).toHaveTextContent('Drive');
      expect(driveIndicator.className).toMatch(/slate/);
    });

    it('shows "Drive" indicator in green when Drive is connected', () => {
      driveStatusMock.current = { connected: true, email: 'user@example.com' };
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const driveIndicator = screen.getByTestId('setup-drive');
      expect(driveIndicator).toBeInTheDocument();
      expect(driveIndicator).toHaveTextContent('Drive');
      expect(driveIndicator.className).toMatch(/green/);
    });

    it('shows "Key" indicator in slate when no key is configured', () => {
      keyDataMock.current = { has_key: false, provider: null, key_mask: null, ai_model: null };
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const keyIndicator = screen.getByTestId('setup-key');
      expect(keyIndicator).toBeInTheDocument();
      expect(keyIndicator).toHaveTextContent('Key');
      expect(keyIndicator.className).toMatch(/slate/);
    });

    it('shows "Key" indicator in green when a key is configured', () => {
      keyDataMock.current = { has_key: true, provider: 'openai', key_mask: 'sk-a...xyz', ai_model: null };
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const keyIndicator = screen.getByTestId('setup-key');
      expect(keyIndicator).toBeInTheDocument();
      expect(keyIndicator).toHaveTextContent('Key');
      expect(keyIndicator.className).toMatch(/green/);
    });

    it('shows "Files 0/15" indicator in slate when no files are indexed', () => {
      knowledgeFilesMock.current = [];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const filesIndicator = screen.getByTestId('setup-files');
      expect(filesIndicator).toBeInTheDocument();
      expect(filesIndicator).toHaveTextContent('Files 0/15');
      expect(filesIndicator.className).toMatch(/slate/);
    });

    it('shows "Files N/15" indicator in green when at least 1 file is indexed', () => {
      knowledgeFilesMock.current = [{ id: 'f1' }, { id: 'f2' }, { id: 'f3' }];
      render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

      const filesIndicator = screen.getByTestId('setup-files');
      expect(filesIndicator).toBeInTheDocument();
      expect(filesIndicator).toHaveTextContent('Files 3/15');
      expect(filesIndicator.className).toMatch(/green/);
    });
  });
});
