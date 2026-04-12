/**
 * WorkspaceCard.test.tsx — component tests for WorkspaceCard action buttons.
 *
 * Tests:
 *   1. "Rename" button opens the RenameWorkspaceModal overlay.
 *   2. "Make Default" button triggers the useMakeDefaultMutation.
 *
 * Mocking strategy:
 *   - `useWorkspaces` hooks are mocked at module level so no real QueryClient
 *     is needed and no network calls are made.
 *   - `vi.hoisted(...)` is used for mock function variables that are referenced
 *     inside `vi.mock` factories — required by Vitest 2.x TDZ hoisting rules
 *     (see FLASHCARDS.md: "Vitest 2.x vi.mock hoisting TDZ").
 *   - `globals: true` is set in vitest.config.ts so `@testing-library/react`
 *     auto-cleanup runs after each test.
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import type { Workspace } from '../../lib/api';

// ---------------------------------------------------------------------------
// Hoisted mock variables (FLASHCARDS.md TDZ rule)
// ---------------------------------------------------------------------------

const { makeDefaultMutateFn, renameMutateFn } = vi.hoisted(() => ({
  makeDefaultMutateFn: vi.fn(),
  renameMutateFn: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../hooks/useWorkspaces', () => ({
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

// ---------------------------------------------------------------------------
// Test data
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

/** A default workspace fixture (Make Default button should be hidden). */
const defaultWorkspace: Workspace = {
  ...nonDefaultWorkspace,
  id: 'ws-002',
  name: 'Default Workspace',
  is_default_for_team: true,
};

// ---------------------------------------------------------------------------
// Import the component under test AFTER mocks are set up
// ---------------------------------------------------------------------------
import { WorkspaceCard } from './WorkspaceCard';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WorkspaceCard', () => {
  beforeEach(() => {
    makeDefaultMutateFn.mockClear();
    renameMutateFn.mockClear();
  });

  it('opens the rename modal when the Rename button is clicked', () => {
    render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

    // The rename modal overlay should NOT be visible before clicking.
    expect(screen.queryByRole('dialog', { name: /rename workspace/i })).toBeNull();

    // Click the Rename button.
    fireEvent.click(screen.getByRole('button', { name: /rename/i }));

    // The rename modal overlay should now be in the DOM.
    expect(
      screen.getByRole('dialog', { name: /rename workspace/i })
    ).toBeInTheDocument();
  });

  it('calls the make-default mutation when Make Default is clicked', () => {
    render(<WorkspaceCard workspace={nonDefaultWorkspace} teamId="T-TEAM-001" />);

    // Click the Make Default button.
    fireEvent.click(screen.getByRole('button', { name: /make default/i }));

    // Mutation should have been called with the workspace id.
    expect(makeDefaultMutateFn).toHaveBeenCalledOnce();
    expect(makeDefaultMutateFn).toHaveBeenCalledWith(nonDefaultWorkspace.id);
  });

  it('hides the Make Default button on the current default workspace', () => {
    render(<WorkspaceCard workspace={defaultWorkspace} teamId="T-TEAM-001" />);

    // Make Default should NOT appear for the already-default workspace.
    expect(screen.queryByRole('button', { name: /make default/i })).toBeNull();

    // Rename button should still be present.
    expect(screen.getByRole('button', { name: /rename/i })).toBeInTheDocument();
  });
});
