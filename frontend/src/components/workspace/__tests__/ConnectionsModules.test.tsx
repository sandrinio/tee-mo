/**
 * ConnectionsModules.test.tsx — 5 Vitest scenarios for STORY-025-02.
 *
 * One test per Gherkin scenario:
 *   1. Slack module renders info-only with team_id + domain
 *   2. Slack module degrades to team_id when domain absent
 *   3. Drive disconnect preserves existing behavior
 *   4. Provider segmented control persists selection
 *   5. Channels divider list renders bound badge
 *
 * Strategy:
 *   - All hooks mocked via vi.mock (hoisted above imports).
 *   - Mock variables wrapped in vi.hoisted() to avoid TDZ errors (Vitest 2.x).
 *   - QueryClientProvider mounted per-test to satisfy TanStack Query.
 *   - No real network calls.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables
// ---------------------------------------------------------------------------

const {
  mockUseDriveStatusQuery,
  mockUseDisconnectDriveMutation,
  mockUseKeyQuery,
  mockUseSaveKeyMutation,
  mockUseDeleteKeyMutation,
  mockUseSlackChannelsQuery,
  mockUseChannelBindingsQuery,
  mockUseBindChannelMutation,
  mockUseUnbindChannelMutation,
} = vi.hoisted(() => ({
  mockUseDriveStatusQuery: vi.fn(),
  mockUseDisconnectDriveMutation: vi.fn(),
  mockUseKeyQuery: vi.fn(),
  mockUseSaveKeyMutation: vi.fn(),
  mockUseDeleteKeyMutation: vi.fn(),
  mockUseSlackChannelsQuery: vi.fn(),
  mockUseChannelBindingsQuery: vi.fn(),
  mockUseBindChannelMutation: vi.fn(),
  mockUseUnbindChannelMutation: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useDrive', () => ({
  useDriveStatusQuery: mockUseDriveStatusQuery,
  useDisconnectDriveMutation: mockUseDisconnectDriveMutation,
}));

vi.mock('../../../hooks/useKey', () => ({
  useKeyQuery: mockUseKeyQuery,
  useSaveKeyMutation: mockUseSaveKeyMutation,
  useDeleteKeyMutation: mockUseDeleteKeyMutation,
}));

vi.mock('../../../lib/api', () => ({
  validateKey: vi.fn(),
}));

vi.mock('../../../hooks/useChannels', () => ({
  useSlackChannelsQuery: mockUseSlackChannelsQuery,
  useChannelBindingsQuery: mockUseChannelBindingsQuery,
  useBindChannelMutation: mockUseBindChannelMutation,
  useUnbindChannelMutation: mockUseUnbindChannelMutation,
}));

// ---------------------------------------------------------------------------
// Import components after mocks are registered
// ---------------------------------------------------------------------------

import { SlackSection } from '../SlackSection';
import { DriveSection } from '../DriveSection';
import { KeySection } from '../KeySection';
import { ChannelSection } from '../ChannelSection';
import type { Workspace } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const BASE_WORKSPACE: Workspace = {
  id: 'ws-001',
  name: 'Acme Corp',
  slack_team_id: 'T1',
  owner_user_id: 'u-001',
  is_default_for_team: false,
  bot_persona: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  is_owner: true,
  slack_team_name: null,
};

function idleMutation(overrides?: Record<string, unknown>) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
    ...overrides,
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('STORY-025-02 connections modules', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Scenario 1: Slack module renders info-only with team_id + domain
  // -------------------------------------------------------------------------

  it('Slack module renders info-only with team_id + domain', () => {
    const workspace: Workspace = {
      ...BASE_WORKSPACE,
      slack_team_id: 'T1',
      slack_team_name: 'Acme Slack',
    };

    render(
      <Wrapper>
        <SlackSection workspace={workspace} teamId="T1" />
      </Wrapper>,
    );

    // Avatar tile present (slate-100 rounded-md)
    const { container } = render(
      <Wrapper>
        <SlackSection workspace={workspace} teamId="T1" />
      </Wrapper>,
    );
    expect(container.querySelector('.bg-slate-100.rounded-md')).toBeInTheDocument();

    // Workspace name visible
    expect(screen.getAllByText('Acme Corp')[0]).toBeInTheDocument();

    // Mono caption text exactly "T1 · Acme Slack"
    const captions = screen.getAllByTestId('slack-caption');
    expect(captions[0]).toHaveTextContent('T1 · Acme Slack');

    // "Installed" badge present
    const installedBadges = screen.getAllByText('Installed');
    expect(installedBadges.length).toBeGreaterThan(0);

    // NO button matching /reinstall/i
    expect(screen.queryByRole('button', { name: /reinstall/i })).not.toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Scenario 2: Slack module degrades to team_id when team name absent
  // -------------------------------------------------------------------------

  it('Slack module degrades to team_id when team name absent', () => {
    const workspace: Workspace = {
      ...BASE_WORKSPACE,
      slack_team_id: 'T1',
      slack_team_name: null,
    };

    const { getByTestId } = render(
      <Wrapper>
        <SlackSection workspace={workspace} teamId="T1" />
      </Wrapper>,
    );

    // Caption shows "T1" only — no separator, no domain
    const caption = getByTestId('slack-caption');
    expect(caption.textContent).toBe('T1');
  });

  // -------------------------------------------------------------------------
  // Scenario 3: Drive disconnect preserves existing behavior
  // -------------------------------------------------------------------------

  it('Drive disconnect preserves existing behavior', () => {
    const mockMutate = vi.fn();
    mockUseDisconnectDriveMutation.mockReturnValue(idleMutation({ mutate: mockMutate }));
    mockUseDriveStatusQuery.mockReturnValue({
      data: { connected: true, email: 'a@b.com' },
      isLoading: false,
      isError: false,
    });

    const { getByTestId } = render(
      <Wrapper>
        <DriveSection workspaceId="w1" />
      </Wrapper>,
    );

    // Connected email visible
    expect(screen.getByText('a@b.com')).toBeInTheDocument();

    // Click Disconnect
    fireEvent.click(getByTestId('disconnect-drive-button'));

    // useDisconnectDriveMutation.mutate invoked once
    expect(mockMutate).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Scenario 4: Provider segmented control persists selection
  // -------------------------------------------------------------------------

  it('Provider segmented control persists selection', () => {
    mockUseSaveKeyMutation.mockReturnValue(idleMutation());
    mockUseDeleteKeyMutation.mockReturnValue(idleMutation());
    mockUseKeyQuery.mockReturnValue({
      data: { has_key: true, provider: 'openai', key_mask: 'sk-proj-••••G7vT', ai_model: 'gpt-4o' },
      isLoading: false,
      isSuccess: true,
      isError: false,
      error: null,
      status: 'success',
      fetchStatus: 'idle',
    });

    const { getByTestId } = render(
      <Wrapper>
        <KeySection workspaceId="w1" teamId="T1" />
      </Wrapper>,
    );

    // OpenAI segment is active (has brand-50 class subset)
    const openaiSegment = getByTestId('provider-segment-openai');
    expect(openaiSegment.className).toMatch(/brand-50/);

    // Click Google segment
    fireEvent.click(getByTestId('provider-segment-google'));

    // Google segment is now active
    expect(getByTestId('provider-segment-google').className).toMatch(/brand-50/);
    // OpenAI is no longer active
    expect(getByTestId('provider-segment-openai').className).not.toMatch(/brand-50/);
  });

  // -------------------------------------------------------------------------
  // Scenario 5: Channels divider list renders bound badge
  // -------------------------------------------------------------------------

  it('Channels divider list renders bound badge', () => {
    mockUseBindChannelMutation.mockReturnValue(idleMutation());
    mockUseUnbindChannelMutation.mockReturnValue(idleMutation());

    // 2 bound channels + 1 unbound
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [
        { id: 'C001', name: 'general', is_private: false },
        { id: 'C002', name: 'engineering', is_private: false },
        { id: 'C003', name: 'marketing', is_private: false },
      ],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [
        {
          slack_channel_id: 'C001',
          workspace_id: 'w1',
          bound_at: '2026-01-01T00:00:00Z',
          channel_name: 'general',
          is_member: true,
        },
        {
          slack_channel_id: 'C002',
          workspace_id: 'w1',
          bound_at: '2026-01-02T00:00:00Z',
          channel_name: 'engineering',
          is_member: true,
        },
      ],
      isLoading: false,
      isError: false,
    });

    const { container } = render(
      <Wrapper>
        <ChannelSection workspaceId="w1" teamId="T1" />
      </Wrapper>,
    );

    // HOTFIX 2026-04-26: list shows ONLY bound channels (was: all channels
    // with Bind/Unbind buttons mixed in). 2 channels bound → 2 rows.
    // The 3rd channel is unbound and lives in the + Add channel picker only.
    const rows = container.querySelectorAll('.divide-y > li');
    expect(rows.length).toBe(2);

    // HOTFIX 2026-04-26: redundant "Bound" badge removed — Active status is
    // sufficient. Bound channels are implicitly bound (they're in the list).
    expect(screen.queryByText('Bound')).not.toBeInTheDocument();

    // Both rows have "Unbind" button
    const unbindButtons = screen.getAllByText('Unbind');
    expect(unbindButtons.length).toBe(2);

    // No "Bind" button in the list anymore — bind is the picker's job.
    expect(screen.queryByText('Bind')).not.toBeInTheDocument();

    // No card border class between rows (using divide-y, not per-row Card)
    // The container should NOT have a .rounded-lg.border class wrapping individual rows.
    // Assert the ul uses divide-y instead.
    expect(container.querySelector('ul.divide-y')).toBeInTheDocument();
  });
});
