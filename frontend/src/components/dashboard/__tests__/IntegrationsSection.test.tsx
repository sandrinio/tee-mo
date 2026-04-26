/**
 * IntegrationsSection.test.tsx — unit tests for the IntegrationsSection component.
 *
 * Covers STORY-012-04 §4.1 Section tests (3+) and §2.1 Gherkin scenarios:
 *   - Empty state
 *   - List renders cards with status badges
 *   - Test button success → badge flips to "Active (N tools)"
 *   - Test button failure → badge red
 *   - Toggle disable → PATCH fires with is_active:false
 *   - Delete confirms before mutating; confirmed → mutation fires
 *
 * FLASHCARD 2026-04-11 #vitest: vi.hoisted() for TDZ safety.
 * FLASHCARD 2026-04-11 #frontend #recipe: All fetches via hooks → api.ts wrappers.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mocks
// ---------------------------------------------------------------------------

const {
  mockUseMcpServersQuery,
  mockUseCreateMcpServerMutation,
  mockUseUpdateMcpServerMutation,
  mockUseDeleteMcpServerMutation,
  mockUseTestMcpServerMutation,
} = vi.hoisted(() => ({
  mockUseMcpServersQuery: vi.fn(),
  mockUseCreateMcpServerMutation: vi.fn(),
  mockUseUpdateMcpServerMutation: vi.fn(),
  mockUseDeleteMcpServerMutation: vi.fn(),
  mockUseTestMcpServerMutation: vi.fn(),
}));

vi.mock('../../../hooks/useMcpServers', () => ({
  useMcpServersQuery: mockUseMcpServersQuery,
  useCreateMcpServerMutation: mockUseCreateMcpServerMutation,
  useUpdateMcpServerMutation: mockUseUpdateMcpServerMutation,
  useDeleteMcpServerMutation: mockUseDeleteMcpServerMutation,
  useTestMcpServerMutation: mockUseTestMcpServerMutation,
}));

// ---------------------------------------------------------------------------
// Import component AFTER mocks
// ---------------------------------------------------------------------------

import { IntegrationsSection } from '../IntegrationsSection';
import type { McpServer } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderSection(workspaceId = 'ws-001') {
  const client = makeClient();
  render(
    React.createElement(
      QueryClientProvider,
      { client },
      React.createElement(IntegrationsSection, { workspaceId, teamId: 'T-TEAM' }),
    ),
  );
}

const serverActive: McpServer = {
  name: 'github',
  transport: 'streamable_http',
  url: 'https://api.githubcopilot.com/mcp/',
  is_active: true,
  created_at: '2026-04-26T00:00:00Z',
};

const serverDisabled: McpServer = {
  ...serverActive,
  name: 'linear',
  is_active: false,
};

/** Default stubs for mutations — override per test. */
function makeStubMutation(mutateFn = vi.fn()) {
  return {
    mutate: mutateFn,
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
    data: undefined,
    variables: undefined,
    status: 'idle' as const,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    context: undefined,
  };
}

// ---------------------------------------------------------------------------
// Setup default mocks
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockUseCreateMcpServerMutation.mockReturnValue(makeStubMutation());
  mockUseUpdateMcpServerMutation.mockReturnValue(makeStubMutation());
  mockUseDeleteMcpServerMutation.mockReturnValue(makeStubMutation());
  mockUseTestMcpServerMutation.mockReturnValue(makeStubMutation());
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe('Empty state', () => {
  it('shows empty-state copy and Add Integration button when no servers', () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [], isLoading: false });
    renderSection();

    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    expect(screen.getByTestId('add-integration-button')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Server list / cards
// ---------------------------------------------------------------------------

describe('Server list', () => {
  it('renders server cards with transport badges and status badges', () => {
    mockUseMcpServersQuery.mockReturnValue({
      data: [serverActive, serverDisabled],
      isLoading: false,
    });
    renderSection();

    const cards = screen.getAllByTestId('mcp-server-card');
    expect(cards).toHaveLength(2);

    // Transport badges
    const transportBadges = screen.getAllByTestId('transport-badge');
    expect(transportBadges).toHaveLength(2);
    expect(transportBadges[0]).toHaveTextContent('Streamable HTTP');

    // Status badges: active server → "Untested" (no test run yet); disabled → "Disabled"
    const statusBadges = screen.getAllByTestId('status-badge');
    expect(statusBadges[0]).toHaveTextContent('Untested');
    expect(statusBadges[1]).toHaveTextContent('Disabled');
  });

  it('shows SSE badge for SSE transport', () => {
    const sseServer: McpServer = { ...serverActive, transport: 'sse', name: 'legacy' };
    mockUseMcpServersQuery.mockReturnValue({ data: [sseServer], isLoading: false });
    renderSection();

    expect(screen.getByTestId('transport-badge')).toHaveTextContent('SSE');
  });
});

// ---------------------------------------------------------------------------
// Test button
// ---------------------------------------------------------------------------

describe('Test button', () => {
  it('flips badge to "Active (N tools)" green on ok:true', async () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [serverActive], isLoading: false });

    // Make test mutation call onSuccess with tool_count:41
    const testMutateFn = vi.fn().mockImplementation(
      (_name: string, callbacks?: { onSuccess?: (data: unknown) => void }) => {
        callbacks?.onSuccess?.({ ok: true, tool_count: 41, error: null });
      },
    );
    mockUseTestMcpServerMutation.mockReturnValue(makeStubMutation(testMutateFn));

    renderSection();

    fireEvent.click(screen.getByTestId('test-button'));

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Active (41 tools)');
    });
  });

  it('flips badge to "Failed" red on ok:false', async () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [serverActive], isLoading: false });

    const testMutateFn = vi.fn().mockImplementation(
      (_name: string, callbacks?: { onSuccess?: (data: unknown) => void }) => {
        callbacks?.onSuccess?.({ ok: false, tool_count: 0, error: 'connection refused' });
      },
    );
    mockUseTestMcpServerMutation.mockReturnValue(makeStubMutation(testMutateFn));

    renderSection();

    fireEvent.click(screen.getByTestId('test-button'));

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Failed');
    });
  });
});

// ---------------------------------------------------------------------------
// Toggle
// ---------------------------------------------------------------------------

describe('Toggle', () => {
  it('fires PATCH with is_active:false when toggling an active server off', async () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [serverActive], isLoading: false });

    const updateMutateFn = vi.fn();
    mockUseUpdateMcpServerMutation.mockReturnValue(makeStubMutation(updateMutateFn));

    renderSection();

    fireEvent.click(screen.getByTestId('toggle-button'));

    await waitFor(() => {
      expect(updateMutateFn).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'github',
          patch: { is_active: false },
        }),
        expect.any(Object),
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Delete confirm flow
// ---------------------------------------------------------------------------

describe('Delete confirm', () => {
  it('does NOT fire delete mutation when user cancels confirm dialog', async () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [serverActive], isLoading: false });

    const deleteMutateFn = vi.fn();
    mockUseDeleteMcpServerMutation.mockReturnValue(makeStubMutation(deleteMutateFn));

    renderSection();

    // Click Delete — shows confirm UI
    fireEvent.click(screen.getByTestId('delete-button'));
    expect(screen.getByTestId('delete-confirm-button')).toBeInTheDocument();

    // Cancel
    fireEvent.click(screen.getByTestId('delete-cancel-button'));

    expect(deleteMutateFn).not.toHaveBeenCalled();
  });

  it('fires delete mutation when user confirms', async () => {
    mockUseMcpServersQuery.mockReturnValue({ data: [serverActive], isLoading: false });

    const deleteMutateFn = vi.fn();
    mockUseDeleteMcpServerMutation.mockReturnValue(makeStubMutation(deleteMutateFn));

    renderSection();

    fireEvent.click(screen.getByTestId('delete-button'));
    fireEvent.click(screen.getByTestId('delete-confirm-button'));

    await waitFor(() => {
      expect(deleteMutateFn).toHaveBeenCalledWith('github', expect.any(Object));
    });
  });
});
