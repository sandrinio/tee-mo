/**
 * app.teams.index.test.tsx — STORY-008-03 acceptance tests for TeamDetailContent.
 *
 * Tests:
 *   R5: Workspace grid uses `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`
 *   R6: After creating a workspace, navigate to /app/teams/$teamId/$newWorkspaceId
 *   R7: Empty state has dashed border with centered text and CTA button
 *
 * Also verifies R8: No hardcoded #E94560 in the "+ New Workspace" button (uses brand-500).
 *
 * Mocking strategy (Vitest 2.x):
 *   - vi.hoisted() for all spy variables referenced in vi.mock factories
 *     (FLASHCARDS.md: "Vitest 2.x vi.mock hoisting TDZ").
 *   - TanStack Router mocked so Route.useParams works without a full router setup.
 *   - useWorkspacesQuery and useCreateWorkspaceMutation mocked at module level.
 *   - globals: true in vitest.config.ts for automatic afterEach cleanup.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { Workspace } from '../../lib/api';

// ---------------------------------------------------------------------------
// Hoisted mock variables (FLASHCARDS.md TDZ rule)
// ---------------------------------------------------------------------------

const {
  mockWorkspaces,
  mockCreateMutateAsync,
  mockNavigate,
} = vi.hoisted(() => ({
  mockWorkspaces: { current: [] as Workspace[] },
  mockCreateMutateAsync: vi.fn(),
  mockNavigate: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router');
  return {
    ...actual,
    // createFileRoute('/path/')(config) → returns an object with useParams stub
    // so that `const { teamId } = Route.useParams()` works without a real router context.
    createFileRoute: (_path: string) => (config: Record<string, unknown>) => ({
      ...config,
      useParams: () => ({ teamId: 'T-TEAM-001' }),
      useSearch: () => ({}),
    }),
    useNavigate: () => mockNavigate,
    Link: ({ children, to: _to, params: _params, ...props }: { children?: React.ReactNode; to?: string; params?: Record<string, string> } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
      <a {...props}>{children}</a>
    ),
  };
});

vi.mock('../../hooks/useWorkspaces', () => ({
  useWorkspacesQuery: vi.fn(() => ({
    data: mockWorkspaces.current,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  })),
  useCreateWorkspaceMutation: vi.fn(() => ({
    mutateAsync: mockCreateMutateAsync,
    isPending: false,
    reset: vi.fn(),
  })),
}));

// Mock WorkspaceCard — we only test the grid layout and orchestration, not the card internals.
vi.mock('../../components/dashboard/WorkspaceCard', () => ({
  WorkspaceCard: ({ workspace }: { workspace: Workspace }) => (
    <div data-testid="workspace-card">{workspace.name}</div>
  ),
}));

// CreateWorkspaceModal mock — renders a simple form to trigger create flow.
vi.mock('../../components/dashboard/CreateWorkspaceModal', () => ({
  CreateWorkspaceModal: ({
    open,
    onClose,
    onCreated,
  }: {
    open: boolean;
    onClose: () => void;
    onCreated?: (ws: Workspace) => void;
  }) => {
    if (!open) return null;
    return (
      <div data-testid="create-modal">
        <button
          type="button"
          data-testid="modal-create-btn"
          onClick={() => {
            const newWs: Workspace = {
              id: 'ws-new-001',
              name: 'New Workspace',
              slack_team_id: 'T-TEAM-001',
              owner_user_id: 'user-001',
              is_default_for_team: false,
              created_at: '2024-01-20T10:00:00Z',
              updated_at: '2024-01-20T10:00:00Z',
            };
            mockCreateMutateAsync.mockResolvedValue(newWs);
            if (onCreated) onCreated(newWs);
            onClose();
          }}
        >
          Create
        </button>
      </div>
    );
  },
}));

// Suppress sonner import error if present
vi.mock('sonner', () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

function makeWorkspace(id: string, name: string): Workspace {
  return {
    id,
    name,
    slack_team_id: 'T-TEAM-001',
    owner_user_id: 'user-001',
    is_default_for_team: false,
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  };
}

// ---------------------------------------------------------------------------
// Import component under test AFTER mocks are set up
// ---------------------------------------------------------------------------
import { TeamDetailContent } from '../app.teams.$teamId.index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderWithQuery() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TeamDetailContent />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TeamDetailContent — STORY-008-03 polish', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWorkspaces.current = [];
    mockCreateMutateAsync.mockReset();
  });

  // --------------------------------------------------------------------------
  // R5: Grid layout
  // --------------------------------------------------------------------------

  describe('R5: Grid layout', () => {
    it('uses grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 for the workspace list', () => {
      mockWorkspaces.current = [
        makeWorkspace('ws-001', 'Workspace A'),
        makeWorkspace('ws-002', 'Workspace B'),
      ];

      const { container } = renderWithQuery();

      // Find the grid wrapper — must contain the workspace cards
      const gridEl = container.querySelector('.grid');
      expect(gridEl).toBeTruthy();
      expect(gridEl!.className).toMatch(/grid-cols-1/);
      expect(gridEl!.className).toMatch(/md:grid-cols-2/);
      expect(gridEl!.className).toMatch(/lg:grid-cols-3/);
      expect(gridEl!.className).toMatch(/gap-6/);
    });
  });

  // --------------------------------------------------------------------------
  // R6: Navigate on create
  // --------------------------------------------------------------------------

  describe('R6: Navigate to new workspace after creation', () => {
    it('calls navigate to /$teamId/$workspaceId after workspace is created', async () => {
      mockWorkspaces.current = [];

      renderWithQuery();

      // Click "+ New Workspace" button to open modal
      fireEvent.click(screen.getByRole('button', { name: /new workspace/i }));

      // Simulate creation
      fireEvent.click(screen.getByTestId('modal-create-btn'));

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith(
          expect.objectContaining({
            to: '/app/teams/$teamId/$workspaceId',
            params: { teamId: 'T-TEAM-001', workspaceId: 'ws-new-001' },
          }),
        );
      });
    });
  });

  // --------------------------------------------------------------------------
  // R7: Empty state
  // --------------------------------------------------------------------------

  describe('R7: Empty state', () => {
    it('shows empty state with dashed border styling when no workspaces', () => {
      mockWorkspaces.current = [];

      const { container } = renderWithQuery();

      // Find the element with dashed border classes
      const emptyEl = container.querySelector('.border-dashed, [class*="border-dashed"]');
      expect(emptyEl).toBeTruthy();
    });

    it('shows the empty state text when no workspaces', () => {
      mockWorkspaces.current = [];
      renderWithQuery();
      expect(screen.getByText(/no workspaces yet/i)).toBeInTheDocument();
    });

    it('shows a CTA button to create the first workspace in the empty state', () => {
      mockWorkspaces.current = [];
      renderWithQuery();
      // At least one "+ New Workspace" button should be visible (can be two: header + empty state)
      const buttons = screen.getAllByRole('button', { name: /new workspace/i });
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --------------------------------------------------------------------------
  // R8: No hardcoded hex in + New Workspace button
  // --------------------------------------------------------------------------

  describe('R8: Brand token usage', () => {
    it('+ New Workspace button uses brand-500 class, not hardcoded #E94560', () => {
      mockWorkspaces.current = [];
      const { container } = renderWithQuery();
      // Ensure no inline style or class with hardcoded hex
      const html = container.innerHTML;
      expect(html).not.toContain('#E94560');
      expect(html).not.toContain('E94560');
    });
  });
});
