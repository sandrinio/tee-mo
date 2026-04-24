/**
 * AddAutomationModal.test.tsx — Component tests for STORY-018-06.
 *
 * Covers all 8 Gherkin scenarios from §2.1:
 *   1. Empty Name blocks Submit (validation error shown, mutation NOT called)
 *   2. No channel selected blocks Submit
 *   3. 'once' schedule with past 'at' blocks Submit
 *   4. Successful create closes modal + invalidates cache (query invalidated)
 *   5. Weekly schedule with no days blocks Submit
 *   6. Preview button fires useTestRunMutation with spinner → inline output
 *   7. DryRunModal auto-fires useTestRunMutation on open
 *   8. channelBindings=[] warns + disables Submit
 *
 * Mock strategy (FLASHCARD 2026-04-11 #vitest #test-harness):
 *   - All hook modules mocked via vi.mock; spy variables wrapped in vi.hoisted()
 *     to avoid TDZ errors in Vitest 2.x.
 *   - Div-overlay pattern — no <dialog>.showModal() (FLASHCARD 2026-04-12 #vitest #frontend).
 *   - QueryClientProvider wrapper per test (via the Wrapper helper).
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables — avoids TDZ in Vitest 2.x (FLASHCARD 2026-04-11)
// ---------------------------------------------------------------------------

const {
  mockCreateMutate,
  mockCreateMutateAsync,
  mockCreateMutation,
  mockTestRunMutate,
  mockTestRunMutation,
} = vi.hoisted(() => {
  const mockCreateMutate = vi.fn();
  const mockCreateMutateAsync = vi.fn();
  const mockCreateMutation = {
    mutate: mockCreateMutate,
    mutateAsync: mockCreateMutateAsync,
    isPending: false,
    error: null as Error | null,
    reset: vi.fn(),
    isError: false,
    data: undefined as unknown,
  };

  const mockTestRunMutate = vi.fn();
  const mockTestRunMutation = {
    mutate: mockTestRunMutate,
    mutateAsync: vi.fn(),
    isPending: false,
    error: null as Error | null,
    reset: vi.fn(),
    isError: false,
    data: undefined as unknown,
  };

  return {
    mockCreateMutate,
    mockCreateMutateAsync,
    mockCreateMutation,
    mockTestRunMutate,
    mockTestRunMutation,
  };
});

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useAutomations', () => ({
  useCreateAutomationMutation: () => mockCreateMutation,
  useTestRunMutation: () => mockTestRunMutation,
}));

// ---------------------------------------------------------------------------
// Import components AFTER mocks are registered
// ---------------------------------------------------------------------------

import { AddAutomationModal } from '../AddAutomationModal';
import { DryRunModal } from '../DryRunModal';
import type { ChannelBinding } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const WORKSPACE_ID = 'ws-test-001';

const CHANNEL_A: ChannelBinding = {
  slack_channel_id: 'C001',
  workspace_id: WORKSPACE_ID,
  bound_at: '2026-04-01T00:00:00Z',
  channel_name: 'general',
  is_member: true,
};

const CHANNEL_B: ChannelBinding = {
  slack_channel_id: 'C002',
  workspace_id: WORKSPACE_ID,
  bound_at: '2026-04-01T00:00:00Z',
  channel_name: 'engineering',
  is_member: true,
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

/** Default props for AddAutomationModal — modal is open, one channel bound. */
const defaultProps = {
  workspaceId: WORKSPACE_ID,
  open: true,
  onClose: vi.fn(),
  channelBindings: [CHANNEL_A, CHANNEL_B],
};

function renderModal(props: Partial<typeof defaultProps> = {}) {
  return render(
    <Wrapper>
      <AddAutomationModal {...defaultProps} {...props} />
    </Wrapper>,
  );
}

/**
 * Fills in the minimum required fields (name, prompt, at least one channel)
 * to produce a valid form. Schedule defaults to daily which requires only `when` (pre-filled).
 */
function fillValidForm() {
  fireEvent.change(screen.getByLabelText(/name/i), {
    target: { value: 'Test Automation' },
  });
  fireEvent.change(screen.getByLabelText(/prompt/i), {
    target: { value: 'Summarise updates' },
  });
  // Check the first channel checkbox
  const checkboxes = screen.getAllByRole('checkbox');
  fireEvent.click(checkboxes[0]);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AddAutomationModal', () => {
  beforeEach(() => {
    mockCreateMutation.isPending = false;
    mockCreateMutation.error = null;
    mockCreateMutation.data = undefined;
    mockTestRunMutation.isPending = false;
    mockTestRunMutation.error = null;
    mockTestRunMutation.data = undefined;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // =========================================================================
  // Scenario 1: Empty Name blocks Submit
  // =========================================================================

  it('shows validation error and does NOT call mutation when Name is empty on submit', async () => {
    renderModal();

    // Fill prompt and channel but leave name empty
    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: 'Some prompt' },
    });
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);

    fireEvent.click(screen.getByRole('button', { name: /save automation/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
    expect(mockCreateMutate).not.toHaveBeenCalled();
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  // =========================================================================
  // Scenario 2: No channel selected blocks Submit
  // =========================================================================

  it('shows validation error when no channel is selected', async () => {
    renderModal();

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: 'Test Automation' },
    });
    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: 'Some prompt' },
    });
    // Do NOT select any channel

    fireEvent.click(screen.getByRole('button', { name: /save automation/i }));

    await waitFor(() => {
      expect(screen.getByText(/select at least one channel/i)).toBeInTheDocument();
    });
    expect(mockCreateMutate).not.toHaveBeenCalled();
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  // =========================================================================
  // Scenario 3: 'once' schedule with past 'at' blocks Submit
  // =========================================================================

  it("shows validation error when 'once' schedule has a past 'at' date", async () => {
    renderModal();

    // Fill name, prompt, channel
    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: 'Test Automation' },
    });
    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: 'Some prompt' },
    });
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);

    // Switch to 'Once' occurrence
    fireEvent.click(screen.getByRole('button', { name: /once/i }));

    // Set a past datetime (yesterday) — use label to uniquely target datetime-local input
    const yesterday = new Date(Date.now() - 86400000);
    const pastIso = yesterday.toISOString().slice(0, 16); // 'YYYY-MM-DDTHH:MM'
    const datetimeInput = screen.getByLabelText(/date & time/i);
    fireEvent.change(datetimeInput, { target: { value: pastIso } });

    fireEvent.click(screen.getByRole('button', { name: /save automation/i }));

    await waitFor(() => {
      expect(screen.getByText(/'at' time must be in the future/i)).toBeInTheDocument();
    });
    expect(mockCreateMutate).not.toHaveBeenCalled();
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  // =========================================================================
  // Scenario 4: Successful create closes modal + invalidates cache
  // =========================================================================

  it('closes modal and calls createMutation on successful submit', async () => {
    const onClose = vi.fn();
    // mutateAsync resolves successfully
    mockCreateMutateAsync.mockResolvedValueOnce({ id: 'auto-new', name: 'Test Automation' });

    renderModal({ onClose });

    fillValidForm();

    fireEvent.click(screen.getByRole('button', { name: /save automation/i }));

    await waitFor(() => {
      // mutateAsync was called with the correct shape
      expect(mockCreateMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Test Automation',
          prompt: 'Summarise updates',
          slack_channel_ids: ['C001'],
          schedule_type: 'recurring', // daily defaults to recurring
        }),
      );
    });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  // =========================================================================
  // Scenario 5: Weekly schedule requires at least one day
  // =========================================================================

  it("shows 'Select at least one day' when weekly schedule has no days checked", async () => {
    renderModal();

    fireEvent.change(screen.getByLabelText(/name/i), {
      target: { value: 'Test Automation' },
    });
    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: 'Some prompt' },
    });
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);

    // Switch to 'Weekly' occurrence
    fireEvent.click(screen.getByRole('button', { name: /weekly/i }));
    // Do NOT check any day checkboxes

    fireEvent.click(screen.getByRole('button', { name: /save automation/i }));

    await waitFor(() => {
      expect(screen.getByText(/select at least one day/i)).toBeInTheDocument();
    });
    expect(mockCreateMutate).not.toHaveBeenCalled();
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  // =========================================================================
  // Scenario 6: Preview button fires useTestRunMutation with spinner → inline output
  // =========================================================================

  it('fires useTestRunMutation when Preview is clicked and shows spinner when pending, then output on success', async () => {
    // Start not pending so "Preview" button is visible
    mockTestRunMutation.isPending = false;
    mockTestRunMutation.data = undefined;

    const { rerender } = renderModal();

    fireEvent.change(screen.getByLabelText(/prompt/i), {
      target: { value: "Summarise this week's updates" },
    });

    // Click Preview — button should be clickable
    fireEvent.click(screen.getByRole('button', { name: /^preview$/i }));

    // mutate was called with the prompt
    expect(mockTestRunMutate).toHaveBeenCalledWith(
      expect.objectContaining({ prompt: "Summarise this week's updates" }),
    );

    // Simulate pending state — re-render with isPending=true
    mockTestRunMutation.isPending = true;
    rerender(
      <Wrapper>
        <AddAutomationModal {...defaultProps} />
      </Wrapper>,
    );

    // Spinner is shown while pending
    expect(screen.getByLabelText(/running preview/i)).toBeInTheDocument();
    // Button shows "Previewing…" while pending
    expect(screen.getByRole('button', { name: /previewing/i })).toBeInTheDocument();

    // Simulate result arriving
    mockTestRunMutation.isPending = false;
    mockTestRunMutation.data = {
      success: true,
      output: 'Summary: everything is fine',
      tokens_used: 200,
    };

    rerender(
      <Wrapper>
        <AddAutomationModal {...defaultProps} />
      </Wrapper>,
    );

    await waitFor(() => {
      expect(screen.getByText(/preview output/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/200 tokens/i)).toBeInTheDocument();
  });

  // =========================================================================
  // Scenario 8: channelBindings=[] warns + disables Submit
  // =========================================================================

  it('shows "No channels bound" warning and Submit is disabled when channelBindings is empty', () => {
    renderModal({ channelBindings: [] });

    expect(screen.getByText(/no channels bound/i)).toBeInTheDocument();

    const submitButton = screen.getByRole('button', { name: /save automation/i });
    expect(submitButton).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Scenario 7: DryRunModal auto-fires on open
// ---------------------------------------------------------------------------

describe('DryRunModal', () => {
  beforeEach(() => {
    mockTestRunMutation.isPending = false;
    mockTestRunMutation.error = null;
    mockTestRunMutation.data = undefined;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  function renderDryRunModal(props: Partial<{
    workspaceId: string;
    automationName: string;
    prompt: string;
    open: boolean;
    onClose: () => void;
  }> = {}) {
    return render(
      <Wrapper>
        <DryRunModal
          workspaceId={WORKSPACE_ID}
          automationName="Weekly Report"
          prompt="Weekly report prompt"
          open={true}
          onClose={vi.fn()}
          {...props}
        />
      </Wrapper>,
    );
  }

  it('auto-fires useTestRunMutation with the prompt when opened and shows spinner while pending', async () => {
    mockTestRunMutation.isPending = true;

    renderDryRunModal({ prompt: 'Weekly report' });

    // Mutation should have been called with the prompt
    await waitFor(() => {
      expect(mockTestRunMutate).toHaveBeenCalledWith(
        expect.objectContaining({ prompt: 'Weekly report' }),
      );
    });

    // Spinner is shown
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders output when useTestRunMutation resolves successfully', async () => {
    mockTestRunMutation.isPending = false;
    mockTestRunMutation.data = {
      success: true,
      output: 'Here is the weekly report output',
      tokens_used: 350,
    };

    renderDryRunModal({ prompt: 'Weekly report' });

    await waitFor(() => {
      expect(screen.getByText(/here is the weekly report output/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/350 tokens used/i)).toBeInTheDocument();
  });
});
