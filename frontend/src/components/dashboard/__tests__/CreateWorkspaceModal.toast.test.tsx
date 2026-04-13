/**
 * CreateWorkspaceModal.toast.test.tsx — Tests for toast-on-error behavior in CreateWorkspaceModal.
 *
 * Covers STORY-008-04 §2 Gherkin scenario:
 *   "Modal errors use toasts"
 *   Given a user submitting the Create Workspace modal
 *   When the creation fails
 *   Then a toast.error appears
 *   And no inline error paragraph is rendered
 *
 * FLASHCARD [2026-04-11]: vi.hoisted is REQUIRED for Vitest 2.x when a vi.mock
 * factory closes over variables defined in the same test file.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CreateWorkspaceModal } from '../CreateWorkspaceModal';

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
  useCreateWorkspaceMutation: () => mockMutation,
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
// Tests
// ---------------------------------------------------------------------------

describe('CreateWorkspaceModal — toast on error (STORY-008-04)', () => {
  const defaultProps = {
    teamId: 'T0123ABCDEF',
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
   * Given a user submitting the Create Workspace modal
   * When the creation fails
   * Then a toast.error appears
   * And no inline error paragraph is rendered
   */
  it('calls toast.error when mutation fails', async () => {
    mockMutateAsync.mockRejectedValue(new Error('Failed to create workspace'));
    render(<CreateWorkspaceModal {...defaultProps} />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'My Workspace' } });

    const form = nameInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalledWith('Failed to create workspace');
    });
  });

  it('does not render an inline error paragraph on mutation failure', async () => {
    mockMutateAsync.mockRejectedValue(new Error('Server error'));
    render(<CreateWorkspaceModal {...defaultProps} />);

    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'My Workspace' } });

    const form = nameInput.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(mockToastError).toHaveBeenCalled();
    });

    // No inline <p role="alert"> should exist in the DOM
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
