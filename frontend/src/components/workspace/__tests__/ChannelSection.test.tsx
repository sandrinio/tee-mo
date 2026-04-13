/**
 * ChannelSection.test.tsx — unit tests for the ChannelSection component (STORY-008-02).
 *
 * Covers all Gherkin scenarios from §2.1:
 *   1. Empty state — no channels bound shows guidance text
 *   2. Active channel — is_member=true shows green "Active" badge
 *   3. Pending channel — is_member=false shows amber "Pending /invite" chip
 *   4. Add channel — picker opens, bound channels are filtered out
 *   5. Bind flow — selecting a channel triggers mutation
 *   6. Unbind — x click shows confirmation, confirm triggers delete
 *   7. 409 error — displays "already bound to another workspace" message
 *
 * Strategy:
 *   - All hooks (useSlackChannelsQuery, useChannelBindingsQuery,
 *     useBindChannelMutation, useUnbindChannelMutation) are mocked via vi.mock.
 *   - Mock variables are wrapped in vi.hoisted() to avoid TDZ errors (Vitest 2.x
 *     hoists vi.mock() calls above const declarations — see FLASHCARDS.md).
 *   - jsdom does not implement HTMLDialogElement.showModal() — ChannelSection
 *     MUST use div-based modal patterns (not <dialog>) per FLASHCARDS.md.
 *   - QueryClientProvider is mounted per-test to satisfy any ambient TQ usage.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables (vi.hoisted prevents TDZ errors in Vitest 2.x)
// ---------------------------------------------------------------------------

const {
  mockUseSlackChannelsQuery,
  mockUseChannelBindingsQuery,
  mockUseBindChannelMutation,
  mockUseUnbindChannelMutation,
} = vi.hoisted(() => ({
  mockUseSlackChannelsQuery: vi.fn(),
  mockUseChannelBindingsQuery: vi.fn(),
  mockUseBindChannelMutation: vi.fn(),
  mockUseUnbindChannelMutation: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useChannels', () => ({
  useSlackChannelsQuery: mockUseSlackChannelsQuery,
  useChannelBindingsQuery: mockUseChannelBindingsQuery,
  useBindChannelMutation: mockUseBindChannelMutation,
  useUnbindChannelMutation: mockUseUnbindChannelMutation,
}));

// ---------------------------------------------------------------------------
// Import component after mocks are registered
// ---------------------------------------------------------------------------

import { ChannelSection } from '../ChannelSection';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const WORKSPACE_ID = 'ws-abc-123';
const TEAM_ID = 'T_TEAM_001';

const CHANNEL_GENERAL = { id: 'C001', name: 'general', is_private: false };
const CHANNEL_ENGINEERING = { id: 'C002', name: 'engineering', is_private: false };
const CHANNEL_MARKETING = { id: 'C003', name: 'marketing', is_private: false };

const BINDING_GENERAL_ACTIVE = {
  slack_channel_id: 'C001',
  workspace_id: WORKSPACE_ID,
  bound_at: '2026-01-01T00:00:00Z',
  channel_name: 'general',
  is_member: true,
};

const BINDING_ENGINEERING_PENDING = {
  slack_channel_id: 'C002',
  workspace_id: WORKSPACE_ID,
  bound_at: '2026-01-02T00:00:00Z',
  channel_name: 'engineering',
  is_member: false,
};

/** Default no-op mutation stubs */
const stubBindMutation = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  isError: false,
};

const stubUnbindMutation = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  isError: false,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Fresh QueryClient per test to prevent cache bleed-over. */
function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;
}

function renderChannelSection() {
  return render(
    <Wrapper>
      <ChannelSection workspaceId={WORKSPACE_ID} teamId={TEAM_ID} />
    </Wrapper>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ChannelSection', () => {
  beforeEach(() => {
    mockUseBindChannelMutation.mockReturnValue(stubBindMutation);
    mockUseUnbindChannelMutation.mockReturnValue(stubUnbindMutation);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // Scenario: Empty state
  // -------------------------------------------------------------------------

  it('shows empty state message when no channels are bound', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_ENGINEERING, CHANNEL_MARKETING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Empty state guidance text must appear
    expect(screen.getByTestId('channel-empty-state')).toBeInTheDocument();
    // The empty state should suggest adding a channel
    expect(screen.getByTestId('channel-empty-state')).toHaveTextContent(/no channels/i);
  });

  // -------------------------------------------------------------------------
  // Scenario: Active channel — is_member=true shows green "Active" badge
  // -------------------------------------------------------------------------

  it('renders Active badge (green) for channels where is_member=true', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_ENGINEERING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_GENERAL_ACTIVE],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Active badge should appear for #general
    expect(screen.getByTestId('channel-status-C001')).toHaveTextContent(/active/i);
    // The badge should have emerald/green styling class
    const badge = screen.getByTestId('channel-status-C001');
    expect(badge.className).toMatch(/emerald|green/i);
  });

  // -------------------------------------------------------------------------
  // Scenario: Pending channel — is_member=false shows "Pending /invite" chip
  // -------------------------------------------------------------------------

  it('renders Pending /invite chip (amber) for channels where is_member=false', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_ENGINEERING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_ENGINEERING_PENDING],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Pending status badge
    expect(screen.getByTestId('channel-status-C002')).toHaveTextContent(/pending/i);
    // Amber styling
    const badge = screen.getByTestId('channel-status-C002');
    expect(badge.className).toMatch(/amber|yellow/i);
  });

  // -------------------------------------------------------------------------
  // Scenario: Copy snippet shows for Pending channel
  // -------------------------------------------------------------------------

  it('shows copy snippet with /invite command for pending channels', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_ENGINEERING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_ENGINEERING_PENDING],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // The /invite snippet should appear for pending channels
    expect(screen.getByTestId('invite-snippet-C002')).toBeInTheDocument();
    expect(screen.getByTestId('invite-snippet-C002')).toHaveTextContent(/\/invite.*@tee-mo/i);
  });

  // -------------------------------------------------------------------------
  // Scenario: Picker filters out already-bound channels
  // -------------------------------------------------------------------------

  it('filters out already-bound channels from the picker', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_ENGINEERING, CHANNEL_MARKETING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_GENERAL_ACTIVE],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Click "Add channel" button to open picker
    fireEvent.click(screen.getByTestId('add-channel-button'));

    // Picker is now open — engineering and marketing are clickable, general is shown as "bound" (disabled)
    expect(screen.getByTestId('channel-picker')).toBeInTheDocument();
    expect(screen.getByText('#engineering')).toBeInTheDocument();
    expect(screen.getByText('#marketing')).toBeInTheDocument();
    // #general is visible but not clickable (no pick-channel button for it)
    expect(screen.queryByTestId('pick-channel-C001')).not.toBeInTheDocument();
    expect(screen.getByText('bound')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Scenario: Bind flow — selecting a channel triggers mutation
  // -------------------------------------------------------------------------

  it('calls bindChannel mutation when user selects a channel from picker', async () => {
    const mockMutate = vi.fn();
    mockUseBindChannelMutation.mockReturnValue({
      ...stubBindMutation,
      mutate: mockMutate,
    });

    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_ENGINEERING, CHANNEL_MARKETING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_GENERAL_ACTIVE],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Open picker
    fireEvent.click(screen.getByTestId('add-channel-button'));

    // Select #engineering from the picker
    fireEvent.click(screen.getByTestId('pick-channel-C002'));

    // Bind mutation must have been called with engineering channel id
    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({ channelId: 'C002' }),
        expect.anything(),
      );
    });
  });

  // -------------------------------------------------------------------------
  // Scenario: After binding — "Pending /invite" chip appears (amber)
  // -------------------------------------------------------------------------

  it('shows Pending /invite chip after binding a channel', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_ENGINEERING],
      isLoading: false,
      isError: false,
    });
    // Simulate state after binding (is_member=false because bot not yet invited)
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_ENGINEERING_PENDING],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    expect(screen.getByTestId('channel-status-C002')).toHaveTextContent(/pending/i);
  });

  // -------------------------------------------------------------------------
  // Scenario: Unbind — x click shows confirmation dialog
  // -------------------------------------------------------------------------

  it('shows confirmation before unbinding a channel', () => {
    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_GENERAL_ACTIVE],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Click the unbind "x" button for #general
    fireEvent.click(screen.getByTestId('unbind-button-C001'));

    // Confirmation prompt must appear
    expect(screen.getByTestId('unbind-confirm-C001')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Scenario: Unbind — confirming fires DELETE mutation
  // -------------------------------------------------------------------------

  it('calls unbindChannel mutation on confirm', async () => {
    const mockUnbindMutate = vi.fn();
    mockUseUnbindChannelMutation.mockReturnValue({
      ...stubUnbindMutation,
      mutate: mockUnbindMutate,
    });

    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [BINDING_GENERAL_ACTIVE],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Click the x button to initiate unbind
    fireEvent.click(screen.getByTestId('unbind-button-C001'));

    // Confirm the unbind
    fireEvent.click(screen.getByTestId('unbind-confirm-btn-C001'));

    await waitFor(() => {
      expect(mockUnbindMutate).toHaveBeenCalledWith(
        expect.objectContaining({ channelId: 'C001' }),
        expect.anything(),
      );
    });
  });

  // -------------------------------------------------------------------------
  // Scenario: 409 conflict error — "already bound to another workspace"
  // -------------------------------------------------------------------------

  it('displays conflict message when binding fails with 409 detail', async () => {
    const conflictError = new Error('This channel is already bound to another workspace. Unbind it there first.');
    const mockMutate = vi.fn((_vars: unknown, options: { onError?: (err: Error) => void }) => {
      options?.onError?.(conflictError);
    });

    mockUseBindChannelMutation.mockReturnValue({
      ...stubBindMutation,
      mutate: mockMutate,
      error: conflictError,
      isError: true,
    });

    mockUseSlackChannelsQuery.mockReturnValue({
      data: [CHANNEL_GENERAL, CHANNEL_MARKETING],
      isLoading: false,
      isError: false,
    });
    mockUseChannelBindingsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderChannelSection();

    // Open picker
    fireEvent.click(screen.getByTestId('add-channel-button'));

    // Select #marketing (triggers 409)
    fireEvent.click(screen.getByTestId('pick-channel-C003'));

    // Conflict message must be visible
    await waitFor(() => {
      const errorEl = screen.getByTestId('channel-bind-error');
      expect(errorEl).toBeInTheDocument();
      expect(errorEl).toHaveTextContent(
        /already bound to another workspace/i,
      );
    });
  });
});
