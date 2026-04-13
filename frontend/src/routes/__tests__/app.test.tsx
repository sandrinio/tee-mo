/**
 * app.test.tsx — Component tests for the /app Slack Teams page.
 *
 * Covers non-toast Gherkin scenarios from STORY-005A-06 §2:
 *   1. Empty state shows install anchor + "No Slack teams yet" heading
 *   2. Team list rendered when teams exist
 *   3. Loading skeleton while query is in flight
 *
 * FlashBanner tests (scenarios 3-8) removed — FlashBanner was replaced by
 * sonner toasts in STORY-008-04. Toast tests live in app.index.toast.test.tsx.
 *
 * FLASHCARD [2026-04-11]: vi.hoisted is REQUIRED for Vitest 2.x when a vi.mock
 * factory closes over variables defined in the same test file. Plain top-level
 * vi.fn() declarations would be in TDZ when the hoisted vi.mock factory runs.
 */
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// ---------------------------------------------------------------------------
// Hoisted mocks — MUST use vi.hoisted to avoid TDZ errors in Vitest 2.x
// ---------------------------------------------------------------------------

const { mockListSlackTeams } = vi.hoisted(() => ({
  mockListSlackTeams: vi.fn(),
}));

vi.mock('../../lib/api', () => ({
  listSlackTeams: mockListSlackTeams,
}));

const { mockSearch, mockNavigate } = vi.hoisted(() => ({
  mockSearch: vi.fn(() => ({})),
  mockNavigate: vi.fn(),
}));

vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router');
  return {
    ...actual,
    useSearch: () => mockSearch(),
    useNavigate: () => mockNavigate,
  };
});

// Mock ProtectedRoute to just render children — avoids auth store complexity.
vi.mock('../../components/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock SignOutButton — we don't test sign-out here.
vi.mock('../../components/auth/SignOutButton', () => ({
  SignOutButton: () => <button type="button">Sign out</button>,
}));

// Mock useAuth to return a dummy user — ProtectedRoute is mocked but app.tsx still calls useAuth.
vi.mock('../../stores/authStore', () => ({
  useAuth: () => ({ email: 'test@example.com' }),
}));

// ---------------------------------------------------------------------------
// Import the component AFTER mocks are declared
// ---------------------------------------------------------------------------
import { AppContent } from '../app.index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wraps the component in a fresh QueryClient for each test to avoid cache
 * contamination across tests. staleTime 0 ensures queries execute immediately.
 */
function renderWithQuery() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <AppContent />
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockSearch.mockReturnValue({});
});

describe('AppContent — /app Slack Teams page', () => {
  /**
   * Scenario 1: Empty state when no teams
   * Given listSlackTeams resolves with { teams: [] }
   * Then "No Slack teams yet" heading is visible
   * And an anchor tag with href containing /api/slack/install is present
   */
  test('empty state when no teams', async () => {
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const installLink = screen.getByRole('link', { name: /install slack/i });
    expect(installLink.getAttribute('href')).toContain('/api/slack/install');
  });

  /**
   * Scenario 2: Team list when teams exist
   * Given listSlackTeams resolves with one team
   * Then the team_id and bot_user_id are visible
   * And the "Install another team" secondary link is present
   */
  test('team list when teams exist', async () => {
    mockListSlackTeams.mockResolvedValue({
      teams: [
        {
          slack_team_id: 'T1',
          slack_team_name: 'Acme Corp',
          slack_bot_user_id: 'UBOT1',
          installed_at: '2026-04-10T12:00:00Z',
        },
      ],
    });
    renderWithQuery();
    // Team name is shown instead of raw ID
    await screen.findByText('Acme Corp');
    const secondaryLink = screen.getByRole('link', { name: /install another team/i });
    expect(secondaryLink).toBeInTheDocument();
  });

  /**
   * Scenario 9: Loading skeleton while query is in flight
   * Given listSlackTeams never resolves
   * Then a skeleton element (data-testid="skeleton-card") is visible
   * And the "No Slack teams yet" heading is NOT visible
   */
  test('loading skeleton while query is in flight', () => {
    mockListSlackTeams.mockImplementation(() => new Promise(() => {}));
    renderWithQuery();
    expect(screen.getByTestId('skeleton-card')).toBeInTheDocument();
    expect(screen.queryByText('No Slack teams yet')).not.toBeInTheDocument();
  });
});
