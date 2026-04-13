/**
 * app.index.toast.test.tsx — Tests for sonner toast migration in /app index route.
 *
 * Covers STORY-008-04 §2 Gherkin scenarios:
 *   - slack_install=ok fires toast.success('Tee-Mo installed.')
 *   - slack_install=cancelled fires toast (informational, not error)
 *   - slack_install=expired fires toast.error('Install session expired — please try again.')
 *   - slack_install=error fires toast.error('Install failed. Please try again or check the logs.')
 *   - slack_install=session_lost fires toast.error('Your session expired during install...')
 *   - drive_connect=ok fires toast.success('Google Drive connected')
 *   - After toast fires, URL params are stripped from the URL
 *   - No FlashBanner component is rendered (FlashBanner replaced by sonner toasts)
 *
 * FLASHCARD [2026-04-11]: vi.hoisted is REQUIRED for Vitest 2.x when a vi.mock
 * factory closes over variables defined in the same test file.
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
  logoutUser: vi.fn(),
  getMe: vi.fn(),
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

// Mock AppNav — not testing nav in these tests.
vi.mock('../../components/layout/AppNav', () => ({
  AppNav: () => <nav aria-label="app nav mock" />,
}));

// Mock useAuth to return a dummy user.
vi.mock('../../stores/authStore', () => ({
  useAuth: () => ({ email: 'test@example.com' }),
}));

// ---------------------------------------------------------------------------
// Hoist the sonner toast mock so we can spy on its calls.
// ---------------------------------------------------------------------------

const { mockToast } = vi.hoisted(() => ({
  mockToast: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

vi.mock('sonner', () => ({
  toast: mockToast,
  Toaster: () => null,
}));

// ---------------------------------------------------------------------------
// Import the component AFTER mocks are declared
// ---------------------------------------------------------------------------
import { AppContent } from '../app.index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wraps AppContent in a fresh QueryClient for each test to avoid cache
 * contamination across tests. retry: false speeds up error states.
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
  // Default: resolve with an empty teams list so the component renders fully.
  mockListSlackTeams.mockResolvedValue({ teams: [] });
});

describe('AppContent — sonner toast migration (STORY-008-04)', () => {
  /**
   * Scenario: Slack OAuth toast replaces FlashBanner (slack_install=ok)
   * Given a redirect to /app?slack_install=ok
   * When the page loads
   * Then toast.success('Tee-Mo installed.') is called
   * And no FlashBanner component is rendered
   */
  test('slack_install=ok fires toast.success with correct message', async () => {
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.success).toHaveBeenCalledWith('Tee-Mo installed.');
  });

  test('slack_install=ok: no FlashBanner rendered (aria-label "Flash banner" absent)', async () => {
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(screen.queryByLabelText('Flash banner')).not.toBeInTheDocument();
  });

  /**
   * Scenario: slack_install=cancelled fires informational toast (not error)
   * The cancelled state is informational — toast() not toast.error().
   */
  test('slack_install=cancelled fires plain toast (informational)', async () => {
    mockSearch.mockReturnValue({ slack_install: 'cancelled' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast).toHaveBeenCalledWith('Install cancelled.');
    // Must NOT be called as an error for the cancelled case.
    expect(mockToast.error).not.toHaveBeenCalledWith('Install cancelled.');
  });

  /**
   * Scenario: slack_install=expired fires toast.error
   */
  test('slack_install=expired fires toast.error with session expired message', async () => {
    mockSearch.mockReturnValue({ slack_install: 'expired' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.error).toHaveBeenCalledWith(
      'Install session expired — please try again.',
    );
  });

  /**
   * Scenario: Error toast on OAuth failure (slack_install=error)
   * Given a redirect to /app?slack_install=error
   * When the page loads
   * Then an error toast appears with the appropriate message
   */
  test('slack_install=error fires toast.error with install failed message', async () => {
    mockSearch.mockReturnValue({ slack_install: 'error' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.error).toHaveBeenCalledWith(
      'Install failed. Please try again or check the logs.',
    );
  });

  /**
   * Scenario: slack_install=session_lost fires toast.error
   */
  test('slack_install=session_lost fires toast.error with session expired during install message', async () => {
    mockSearch.mockReturnValue({ slack_install: 'session_lost' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.error).toHaveBeenCalledWith(
      'Your session expired during install. Please log in and try again.',
    );
  });

  /**
   * Scenario: Drive OAuth toast
   * Given a redirect to /app?drive_connect=ok
   * When the page loads
   * Then toast.success('Google Drive connected') is called
   */
  test('drive_connect=ok fires toast.success with Google Drive connected message', async () => {
    mockSearch.mockReturnValue({ drive_connect: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.success).toHaveBeenCalledWith('Google Drive connected');
  });

  /**
   * Scenario: Params stripped from URL after toast fires
   * Given ?slack_install=ok in the URL
   * When the page loads and toast fires
   * Then mockNavigate is called to strip params from the URL
   */
  test('slack_install param is stripped from URL after toast fires', async () => {
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.objectContaining({ to: '/app', search: {} }),
    );
  });

  test('drive_connect param is stripped from URL after toast fires', async () => {
    mockSearch.mockReturnValue({ drive_connect: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.objectContaining({ to: '/app', search: {} }),
    );
  });

  /**
   * Ensure toast is only fired once per render — not on every re-render.
   */
  test('toast fires exactly once per page load for slack_install=ok', async () => {
    mockSearch.mockReturnValue({ slack_install: 'ok' });
    renderWithQuery();
    await screen.findByText('No Slack teams yet');
    expect(mockToast.success).toHaveBeenCalledTimes(1);
  });
});
