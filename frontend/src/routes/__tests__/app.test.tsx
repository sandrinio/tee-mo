/**
 * app.test.tsx — Component tests for the /app Slack Teams page.
 *
 * Covers all 9 Gherkin scenarios from STORY-005A-06 §2:
 *   1. Empty state shows install anchor + "No Slack teams yet" heading
 *   2. Team list rendered when teams exist
 *   3-7. Flash banner variants (ok, cancelled, expired, error, session_lost)
 *   8. Banner dismiss clears the search query param
 *   9. Loading skeleton while query is in flight
 *
 * FLASHCARD [2026-04-11]: vi.hoisted is REQUIRED for Vitest 2.x when a vi.mock
 * factory closes over variables defined in the same test file. Plain top-level
 * vi.fn() declarations would be in TDZ when the hoisted vi.mock factory runs.
 */
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
          slack_bot_user_id: 'UBOT1',
          installed_at: '2026-04-10T12:00:00Z',
        },
      ],
    });
    renderWithQuery();
    await screen.findByText('T1');
    expect(screen.getByText('UBOT1')).toBeInTheDocument();
    const secondaryLink = screen.getByRole('link', { name: /install another team/i });
    expect(secondaryLink).toBeInTheDocument();
  });

  /**
   * Scenario 3: Success banner from slack_install=ok
   * Given mockSearch returns { slack_install: 'ok' }
   * And teams is []
   * Then a banner with role="status" and "Tee-Mo installed" is visible
   */
  test('success banner from slack_install=ok', async () => {
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const banner = screen.getByRole('status', { name: /flash banner/i });
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).toContain('Tee-Mo installed');
  });

  /**
   * Scenario 4: Cancelled banner
   * Given mockSearch returns { slack_install: 'cancelled' }
   * Then banner contains "Install cancelled"
   */
  test('cancelled banner', async () => {
    mockSearch.mockReturnValue({ slack_install: 'cancelled' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const banner = screen.getByRole('status', { name: /flash banner/i });
    expect(banner.textContent).toContain('Install cancelled');
  });

  /**
   * Scenario 5: Expired banner
   * Given mockSearch returns { slack_install: 'expired' }
   * Then banner contains "session expired"
   */
  test('expired banner', async () => {
    mockSearch.mockReturnValue({ slack_install: 'expired' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const banner = screen.getByRole('alert', { name: /flash banner/i });
    expect(banner.textContent).toContain('session expired');
  });

  /**
   * Scenario 6: Error banner with role=alert
   * Given mockSearch returns { slack_install: 'error' }
   * Then banner has role="alert" and contains "Install failed"
   */
  test('error banner with role=alert', async () => {
    mockSearch.mockReturnValue({ slack_install: 'error' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const banner = screen.getByRole('alert', { name: /flash banner/i });
    expect(banner.textContent).toContain('Install failed');
  });

  /**
   * Scenario 7: session_lost banner
   * Given mockSearch returns { slack_install: 'session_lost' }
   * Then banner contains "session expired during install"
   */
  test('session_lost banner', async () => {
    mockSearch.mockReturnValue({ slack_install: 'session_lost' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const banner = screen.getByRole('alert', { name: /flash banner/i });
    expect(banner.textContent).toContain('session expired during install');
  });

  /**
   * Scenario 8: Banner dismiss clears query param
   * Given slack_install=ok, banner is visible
   * When the dismiss (✕) button is clicked
   * Then mockNavigate is called to clear the search param
   */
  test('banner dismiss clears query param', async () => {
    const user = userEvent.setup();
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    mockListSlackTeams.mockResolvedValue({ teams: [] });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    const dismissBtn = screen.getByRole('button', { name: /dismiss banner/i });
    await user.click(dismissBtn);
    expect(mockNavigate).toHaveBeenCalledWith({ to: '/app', search: {} });
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
