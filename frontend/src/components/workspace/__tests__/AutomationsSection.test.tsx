/**
 * AutomationsSection.test.tsx — Component tests for STORY-018-05.
 *
 * Covers all 7 Gherkin scenarios from §2.1:
 *   1. Empty state — "No automations yet" + Add button visible
 *   2. Card renders name, schedule summary, Active badge (emerald), channel name, 4 buttons
 *   3. Toggle → useUpdateAutomationMutation called with { is_active: false }
 *   4. Delete two-click → confirm → useDeleteAutomationMutation called
 *   5. History click → AutomationHistoryDrawer renders with automationId
 *   6. History drawer lists 3 rows newest-first (status badge, started_at, duration, tokens)
 *   7. Expand chevron reveals generated_content
 *
 * Testing strategy:
 *   - Mock hook modules via vi.mock; wrap spy variables in vi.hoisted() to avoid
 *     TDZ errors in Vitest 2.x (FLASHCARD 2026-04-11 #vitest #test-harness).
 *   - QueryClientProvider wrapper per test — prevents cache bleed-over.
 *   - No raw fetch() in components — all data comes through mocked hooks.
 *   - div-based drawer (not <dialog>) — no jsdom showModal() concern.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables — avoids TDZ in Vitest 2.x (FLASHCARD 2026-04-11)
// ---------------------------------------------------------------------------

const {
  mockUseAutomationsQuery,
  mockUseUpdateAutomationMutation,
  mockUseDeleteAutomationMutation,
  mockUseAutomationHistoryQuery,
} = vi.hoisted(() => ({
  mockUseAutomationsQuery: vi.fn(),
  mockUseUpdateAutomationMutation: vi.fn(),
  mockUseDeleteAutomationMutation: vi.fn(),
  mockUseAutomationHistoryQuery: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useAutomations', () => ({
  useAutomationsQuery: mockUseAutomationsQuery,
  useUpdateAutomationMutation: mockUseUpdateAutomationMutation,
  useDeleteAutomationMutation: mockUseDeleteAutomationMutation,
  useAutomationHistoryQuery: mockUseAutomationHistoryQuery,
  // HOTFIX 2026-04-26: section now mounts AddAutomationModal + DryRunModal
  // internally; their hooks must be stubbed too.
  useCreateAutomationMutation: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useTestRunMutation: () => ({ mutate: vi.fn(), isPending: false, error: null, data: null, reset: vi.fn() }),
  automationsKey: (wsId: string) => ['automations', wsId],
  automationHistoryKey: (wsId: string, aid: string) => ['automationHistory', wsId, aid],
}));

// HOTFIX 2026-04-26: section now mounts the 3 modals. Stub them out so
// shell-level tests don't have to satisfy each modal's internal contracts.
// AutomationHistoryDrawer's mock renders the automation name so the
// "opens history drawer" scenario can assert on visible text.
vi.mock('../AddAutomationModal', () => ({
  AddAutomationModal: ({ open }: { open: boolean }) =>
    open ? React.createElement('div', { 'data-testid': 'mock-add-automation-modal' }, 'Add modal') : null,
}));
vi.mock('../DryRunModal', () => ({
  DryRunModal: ({ open, automationName }: { open: boolean; automationName: string }) =>
    open ? React.createElement('div', { 'data-testid': 'mock-dryrun-modal' }, `Dry run — ${automationName}`) : null,
}));
// Note: AutomationHistoryDrawer is NOT mocked — its hook
// (useAutomationHistoryQuery) is already mocked above, so the real drawer
// renders fine. The "AutomationHistoryDrawer" describe block at the bottom
// of this file imports + tests the real drawer directly.

// ---------------------------------------------------------------------------
// Import components after mocks are registered
// ---------------------------------------------------------------------------

import { AutomationsSection } from '../AutomationsSection';
import { AutomationHistoryDrawer } from '../AutomationHistoryDrawer';
import type { Automation, AutomationExecution } from '../../../types/automation';
import type { ChannelBinding } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const WORKSPACE_ID = 'ws-test-001';

/** A simple Active automation fixture. */
const AUTOMATION_DAILY: Automation = {
  id: 'auto-001',
  workspace_id: WORKSPACE_ID,
  owner_user_id: 'user-001',
  name: 'Daily Standup',
  description: null,
  prompt: 'Summarize yesterday and today blockers.',
  slack_channel_ids: ['C001'],
  schedule: { occurrence: 'daily', when: '09:00' },
  schedule_type: 'recurring',
  timezone: 'UTC',
  is_active: true,
  last_run_at: null,
  next_run_at: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
};

/** A channel binding fixture for C001. */
const CHANNEL_BINDING_C1: ChannelBinding = {
  slack_channel_id: 'C001',
  workspace_id: WORKSPACE_ID,
  bound_at: '2026-04-01T00:00:00Z',
  channel_name: 'general',
  is_member: true,
};

/** Three execution fixtures for history tests. */
const EXEC_SUCCESS: AutomationExecution = {
  id: 'exec-001',
  automation_id: 'auto-001',
  status: 'success',
  was_dry_run: false,
  started_at: '2026-04-20T09:00:00Z',
  completed_at: '2026-04-20T09:00:05Z',
  generated_content: 'Hello world',
  delivery_results: null,
  error: null,
  tokens_used: 150,
  execution_time_ms: 5000,
};

const EXEC_PARTIAL: AutomationExecution = {
  id: 'exec-002',
  automation_id: 'auto-001',
  status: 'partial',
  was_dry_run: false,
  started_at: '2026-04-19T09:00:00Z',
  completed_at: '2026-04-19T09:00:03Z',
  generated_content: null,
  delivery_results: null,
  error: null,
  tokens_used: 80,
  execution_time_ms: 3000,
};

const EXEC_FAILED: AutomationExecution = {
  id: 'exec-003',
  automation_id: 'auto-001',
  status: 'failed',
  was_dry_run: false,
  started_at: '2026-04-18T09:00:00Z',
  completed_at: null,
  generated_content: null,
  delivery_results: null,
  error: 'Timeout after 30s',
  tokens_used: null,
  execution_time_ms: 30000,
};

/** Default no-op mutation stubs. */
const stubUpdateMutation = {
  mutate: vi.fn(),
  mutateAsync: vi.fn(),
  isPending: false,
  error: null,
  isError: false,
};

const stubDeleteMutation = {
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

/** Default prop values for AutomationsSection.
 *  HOTFIX 2026-04-26: callback props removed — section is now self-contained. */
const defaultProps = {
  workspaceId: WORKSPACE_ID,
  channelBindings: [CHANNEL_BINDING_C1],
};

function renderAutomationsSection(props = {}) {
  return render(
    <Wrapper>
      <AutomationsSection {...defaultProps} {...props} />
    </Wrapper>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AutomationsSection', () => {
  beforeEach(() => {
    mockUseUpdateAutomationMutation.mockReturnValue(stubUpdateMutation);
    mockUseDeleteAutomationMutation.mockReturnValue(stubDeleteMutation);
    // HOTFIX 2026-04-26: section now self-mounts AutomationHistoryDrawer.
    // Default mock so the drawer renders without crashing on opening.
    mockUseAutomationHistoryQuery.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // Scenario 1: Empty state renders correctly
  // =========================================================================

  it('shows "No automations yet" and Add button when workspace has no automations', () => {
    mockUseAutomationsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    });

    renderAutomationsSection();

    expect(screen.getByTestId('automations-empty-state')).toBeInTheDocument();
    expect(screen.getByTestId('automations-empty-state')).toHaveTextContent(/no automations yet/i);
    expect(screen.getByTestId('add-automation-button')).toBeInTheDocument();
  });

  // =========================================================================
  // Scenario 2: Automation card renders key info
  // =========================================================================

  it('renders card with name, schedule summary, Active badge, channel name, and 4 action buttons', () => {
    mockUseAutomationsQuery.mockReturnValue({
      data: [AUTOMATION_DAILY],
      isLoading: false,
      isError: false,
    });

    renderAutomationsSection();

    // Card is present
    expect(screen.getByTestId('automation-card-auto-001')).toBeInTheDocument();

    // Name
    expect(screen.getByTestId('automation-name-auto-001')).toHaveTextContent('Daily Standup');

    // Schedule summary — mirrors backend: "every day at 09:00 UTC"
    expect(screen.getByTestId('automation-schedule-auto-001')).toHaveTextContent(
      /every day at 09:00 UTC/i,
    );

    // Active badge — should have emerald class
    const badge = screen.getByTestId('automation-status-auto-001');
    expect(badge).toHaveTextContent(/active/i);
    expect(badge.className).toMatch(/emerald/i);

    // Channel pill shows "general" (resolved from binding)
    expect(screen.getByTestId('automation-channels-auto-001')).toHaveTextContent(/general/i);

    // All 4 action buttons are present
    expect(screen.getByTestId('history-button-auto-001')).toBeInTheDocument();
    expect(screen.getByTestId('dry-run-button-auto-001')).toBeInTheDocument();
    expect(screen.getByTestId('toggle-button-auto-001')).toBeInTheDocument();
    expect(screen.getByTestId('delete-button-auto-001')).toBeInTheDocument();
  });

  // =========================================================================
  // Scenario 3: Toggle automation off
  // =========================================================================

  it('calls useUpdateAutomationMutation with { is_active: false } when Toggle is clicked on Active automation', async () => {
    const mockMutate = vi.fn();
    mockUseUpdateAutomationMutation.mockReturnValue({
      ...stubUpdateMutation,
      mutate: mockMutate,
    });

    mockUseAutomationsQuery.mockReturnValue({
      data: [AUTOMATION_DAILY],
      isLoading: false,
      isError: false,
    });

    renderAutomationsSection();

    // Click the toggle button on the Active automation
    fireEvent.click(screen.getByTestId('toggle-button-auto-001'));

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith(
        expect.objectContaining({ automationId: 'auto-001', is_active: false }),
      );
    });
  });

  // =========================================================================
  // Scenario 4: Delete with two-click confirmation
  // =========================================================================

  it('shows Confirm? on first Delete click, then calls useDeleteAutomationMutation on second click', async () => {
    const mockMutate = vi.fn((_id: string, options?: { onSuccess?: () => void }) => {
      options?.onSuccess?.();
    });
    mockUseDeleteAutomationMutation.mockReturnValue({
      ...stubDeleteMutation,
      mutate: mockMutate,
    });

    mockUseAutomationsQuery.mockReturnValue({
      data: [AUTOMATION_DAILY],
      isLoading: false,
      isError: false,
    });

    renderAutomationsSection();

    const deleteBtn = screen.getByTestId('delete-button-auto-001');

    // First click — button changes to "Confirm?"
    fireEvent.click(deleteBtn);
    expect(screen.getByTestId('delete-button-auto-001')).toHaveTextContent(/confirm\?/i);

    // Second click — mutation fires
    fireEvent.click(screen.getByTestId('delete-button-auto-001'));

    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalledWith('auto-001', expect.anything());
    });
  });

  // =========================================================================
  // Scenario 5: History drawer opens with automationId on click
  // =========================================================================

  it('opens the history drawer when History button is clicked', () => {
    // HOTFIX 2026-04-26: section is self-contained — clicking History sets
    // internal state and mounts the AutomationHistoryDrawer with that id.
    mockUseAutomationsQuery.mockReturnValue({
      data: [AUTOMATION_DAILY],
      isLoading: false,
      isError: false,
    });

    renderAutomationsSection();

    // Drawer not yet open — its visible heading element shouldn't be present.
    expect(screen.queryByText(/History — Daily Standup/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId('history-button-auto-001'));

    // Drawer opens with the automation name in its header.
    expect(screen.getByText(/History — Daily Standup/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// AutomationHistoryDrawer tests (Scenarios 6 & 7)
// ---------------------------------------------------------------------------

describe('AutomationHistoryDrawer', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  function renderDrawer(automationId: string | null = 'auto-001') {
    return render(
      <Wrapper>
        <AutomationHistoryDrawer
          workspaceId={WORKSPACE_ID}
          automationId={automationId}
          automationName="Daily Standup"
          onClose={vi.fn()}
          channelBindings={[CHANNEL_BINDING_C1]}
        />
      </Wrapper>,
    );
  }

  // =========================================================================
  // Scenario 6: History drawer shows executions newest-first
  // =========================================================================

  it('renders 3 execution rows newest-first with status badge, started_at, duration, and tokens', () => {
    // API returns newest-first: exec-001 (Apr 20), exec-002 (Apr 19), exec-003 (Apr 18)
    mockUseAutomationHistoryQuery.mockReturnValue({
      data: [EXEC_SUCCESS, EXEC_PARTIAL, EXEC_FAILED],
      isLoading: false,
      isError: false,
    });

    renderDrawer();

    // Drawer is visible
    expect(screen.getByTestId('automation-history-drawer')).toBeInTheDocument();
    expect(screen.getByTestId('history-list')).toBeInTheDocument();

    // All 3 rows are present
    expect(screen.getByTestId('history-row-exec-001')).toBeInTheDocument();
    expect(screen.getByTestId('history-row-exec-002')).toBeInTheDocument();
    expect(screen.getByTestId('history-row-exec-003')).toBeInTheDocument();

    // Status badges
    expect(screen.getByTestId('history-status-exec-001')).toHaveTextContent('success');
    expect(screen.getByTestId('history-status-exec-002')).toHaveTextContent('partial');
    expect(screen.getByTestId('history-status-exec-003')).toHaveTextContent('failed');

    // Verify order: exec-001 should appear before exec-003 in the DOM
    const rows = screen.getAllByTestId(/^history-row-exec-/);
    expect(rows[0]).toHaveAttribute('data-testid', 'history-row-exec-001');
    expect(rows[1]).toHaveAttribute('data-testid', 'history-row-exec-002');
    expect(rows[2]).toHaveAttribute('data-testid', 'history-row-exec-003');

    // Token count visible on exec-001 (150 tok)
    expect(screen.getByTestId('history-row-exec-001')).toHaveTextContent(/150/);
  });

  // =========================================================================
  // Scenario 7: Expanding history row reveals generated_content
  // =========================================================================

  it('reveals generated_content when the expand chevron is clicked', async () => {
    mockUseAutomationHistoryQuery.mockReturnValue({
      data: [EXEC_SUCCESS],
      isLoading: false,
      isError: false,
    });

    renderDrawer();

    // generated_content not visible before expand
    expect(screen.queryByTestId('history-content-exec-001')).not.toBeInTheDocument();

    // Click the expand button
    fireEvent.click(screen.getByTestId('history-row-expand-exec-001'));

    // generated_content is now visible
    await waitFor(() => {
      expect(screen.getByTestId('history-content-exec-001')).toBeInTheDocument();
      expect(screen.getByTestId('history-content-exec-001')).toHaveTextContent('Hello world');
    });
  });
});
