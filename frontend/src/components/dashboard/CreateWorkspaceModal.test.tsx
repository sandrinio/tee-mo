/**
 * CreateWorkspaceModal.test.tsx — component tests for the workspace creation modal.
 *
 * Tests cover:
 *   1. Modal renders with a visible name input when `open` is true.
 *   2. Submitting the form calls the create mutation and closes the modal on success.
 *
 * Mock strategy:
 *   - `useCreateWorkspaceMutation` is mocked at module level using `vi.hoisted`
 *     (FLASHCARDS.md: "Vitest 2.x vi.mock hoisting TDZ — use vi.hoisted(...)").
 *   - The mock returns a controllable `mutateAsync` spy so each test can verify
 *     the call arguments and simulate success/failure responses.
 *
 * Rendering setup:
 *   - `CreateWorkspaceModal` calls `useCreateWorkspaceMutation` which ultimately
 *     needs a `QueryClientProvider`. Since the hook is fully mocked here, no
 *     actual QueryClient is needed — the component renders inside a plain
 *     React tree.
 *   - `globals: true` in vitest.config.ts provides automatic afterEach cleanup
 *     (FLASHCARDS.md: "@testing-library/react auto-cleanup requires globals: true").
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CreateWorkspaceModal } from './CreateWorkspaceModal';

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

vi.mock('../../hooks/useWorkspaces', () => ({
  useCreateWorkspaceMutation: () => mockMutation,
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('CreateWorkspaceModal', () => {
  const defaultProps = {
    teamId: 'T0123ABCDEF',
    open: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockMutation.isPending = false;
    mockMutation.error = null;
    // Default: mutateAsync resolves successfully
    mockMutateAsync.mockResolvedValue({
      id: 'ws-1',
      name: 'My Workspace',
      slack_team_id: 'T0123ABCDEF',
      owner_user_id: 'u-1',
      is_default_for_team: false,
      created_at: '2026-04-12T00:00:00Z',
    });
  });

  // -------------------------------------------------------------------------
  // Test 1: Modal renders with name input when open
  // -------------------------------------------------------------------------
  it('renders with a name input field when open is true', () => {
    render(<CreateWorkspaceModal {...defaultProps} />);

    // The heading should be visible
    expect(screen.getByText('New Workspace')).toBeInTheDocument();

    // The name input should be present and accessible
    const nameInput = screen.getByLabelText('Name');
    expect(nameInput).toBeInTheDocument();
    expect(nameInput).toHaveAttribute('type', 'text');

    // The Create submit button should be present
    expect(screen.getByRole('button', { name: 'Create' })).toBeInTheDocument();

    // The Cancel button should be present
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Test 2: Form submit calls mutation and invokes onClose on success
  // -------------------------------------------------------------------------
  it('calls the create mutation with the input name and closes modal on success', async () => {
    const onClose = vi.fn();
    render(<CreateWorkspaceModal {...defaultProps} onClose={onClose} />);

    // Type a workspace name into the input
    const nameInput = screen.getByLabelText('Name');
    fireEvent.change(nameInput, { target: { value: 'My New Workspace' } });

    // Submit the form
    const form = nameInput.closest('form')!;
    fireEvent.submit(form);

    // The mutation should have been called with the trimmed name
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith('My New Workspace');
    });

    // onClose should be called after successful mutation
    await waitFor(() => {
      expect(onClose).toHaveBeenCalledOnce();
    });
  });
});
