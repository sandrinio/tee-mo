/**
 * RenameWorkspaceModal.toast.test.tsx — Tests for toast-on-error behavior in RenameWorkspaceModal.
 *
 * Covers STORY-008-04 §2 Gherkin scenario:
 *   "Modal errors use toasts"
 *   Given a user submitting the Rename Workspace modal
 *   When the rename fails
 *   Then a toast.error appears
 *   And no inline error paragraph is rendered
 *
 * FLASHCARD [2026-04-11]: vi.hoisted is REQUIRED for Vitest 2.x when a vi.mock
 * factory closes over variables defined in the same test file.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { RenameWorkspaceModal } from '../RenameWorkspaceModal';
import type { Workspace } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Hoisted mock variables (must use vi.hoisted per FLASHCARDS.md)
// ---------------------------------------------------------------------------

const { mockMutateAsync, mockMutation } = vi.hoisted(() => {
  const mockMutateAsync = vi.fn();
  const mockMutation = {
    mutateAsync: mockMutateAsync,
    reset: vi.fn(),
    isPending: false,
    error: null as Error | null,
  };
  return { mockMutateAsync, mockMutation };
});

vi.mock('../../../hooks/useWorkspaces', () => ({
  useRenameWorkspaceMutation: () => mockMutation,
}));

// Hoist sonner mock so toast.error can be inspected.
const { mockToastError } = vi.hoisted(() => ({
  mockToastError: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: mockToastError,
  }),
  Toaster: () => null,
}));

// ---------------------------------------------------------------------------
// Test fixture
// ---------------------------------------------------------------------------

const TEST_WORKSPACE: Workspace = {
  id: 'ws-1',
  name: 'My Workspace',
  slack_team_id: 'T0123ABCDEF',
  owner_user_id: 'u-1',
  is_default_for_team: false,
  created_at: '2026-04-12T00:00:00Z',
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('RenameWorkspaceModal — toast on error (STORY-008-04)', () => {
  const defaultProps = {
    workspace: TEST_WORKSPACE,
    open: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockMutation.isPending = false;
    mockMutation.error = null;
  });

  /**
   * Scenario: Modal errors use toasts
   * Given a user submitting the Rename Workspace modal
   * When the rename fails
   * Then a toast.error appears
   * And no inline error paragraph is rendered
   */
  it('calls toast.error when rename mutation fails', async () => {
    mockMutateAsync.mockRejectedValue(new Error('Failed to rename workspace'));
    render(<RenameWorkspaceModal {...defaultProps} />);

    const nameInput = screen.getByLabelText('Name');
    // Clear and retype a new name to ensure the input has a value
    fireEvent.change(nameInput, { target: { value: 'Renamed Workspace' } });

    const form = nameInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to rename workspace');
    });
  });

  it('does not render an inline error paragraph on rename failure', async () => {
    mockMutateAsync.mockRejectedValue(new Error('Server error'));
    render(<RenameWorkspaceModal {...defaultProps} />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'Renamed Workspace' } });

    const form = nameInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalled();
    });

    // No inline <p role="alert"> should exist in the DOM
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
