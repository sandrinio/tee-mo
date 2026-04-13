/**
 * /app (index) — Slack Teams dashboard (STORY-005A-06, refactored in S-05, S-09).
 *
 * This is the first screen a user sees after logging in; it shows all Slack
 * workspaces where Tee-Mo is installed for their account, plus an install button
 * to add new workspaces.
 *
 * Previously lived in app.tsx, but was extracted to app.index.tsx so that
 * app.tsx can serve as a layout route with <Outlet> for child routes like
 * /app/teams/$teamId.
 *
 * STORY-008-04 changes:
 *   - FlashBanner and BANNER_VARIANTS removed — replaced with sonner toasts.
 *   - useEffect fires the appropriate toast variant once on mount when
 *     slack_install or drive_connect search params are present.
 *   - validateSearch extended to also accept drive_connect='ok'.
 *   - URL params are stripped after toast fires via navigate({ replace: true }).
 *
 * Design decisions:
 *   - Install button is always an `<a href>` — NOT an onClick handler. The browser
 *     must perform a full-page navigation so the session cookie rides along to the
 *     backend's OAuth initiation endpoint, which then redirects to Slack.
 *   - All data fetching goes through TanStack Query + listSlackTeams() in lib/api.ts.
 *     No raw fetch() calls in this file.
 *   - validateSearch narrows the `slack_install` param to a union type so useSearch
 *     returns typed data without any runtime overhead.
 */
import { useEffect } from 'react';
import { createFileRoute, useSearch, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { listSlackTeams } from '../lib/api';
import type { SlackTeam } from '../lib/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * API base URL from Vite environment. Defaults to empty string (same origin)
 * for production same-origin deploys (STORY-003-01).
 */
const API_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Valid values for the `slack_install` search param set by the OAuth callback.
 * Used in validateSearch and as the key type for toast message mapping.
 */
const ALLOWED_INSTALL_STATES = ['ok', 'cancelled', 'expired', 'error', 'session_lost'] as const;
type SlackInstallState = (typeof ALLOWED_INSTALL_STATES)[number];

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * Index route for /app. validateSearch narrows the `slack_install` query param
 * to the SlackInstallState union and accepts `drive_connect='ok'` for Google
 * Drive OAuth callback, so useSearch() returns typed data in AppContent.
 *
 * Any value outside the allowed set is coerced to `undefined` at parse time —
 * no runtime exceptions, no unrecognised toast variants.
 */
export const Route = createFileRoute('/app/')({
  component: AppContent,
  validateSearch: (
    search: Record<string, unknown>,
  ): { slack_install?: SlackInstallState; drive_connect?: 'ok' } => {
    const v = search.slack_install;
    const d = search.drive_connect;
    return {
      slack_install:
        typeof v === 'string' &&
        (ALLOWED_INSTALL_STATES as readonly string[]).includes(v)
          ? (v as SlackInstallState)
          : undefined,
      drive_connect: d === 'ok' ? 'ok' : undefined,
    };
  },
});

// ---------------------------------------------------------------------------
// Inner components
// ---------------------------------------------------------------------------

/** Props for TeamCard. */
interface TeamCardProps {
  team: SlackTeam;
}

/**
 * TeamCard — renders a single installed Slack workspace.
 * Displays team ID, bot user ID, and a human-readable install date.
 * Uses Intl.DateTimeFormat for locale-aware date formatting without adding
 * a date-fns/dayjs dependency.
 *
 * Clicking the card navigates to the team detail page at `/app/teams/$teamId`
 * via `useNavigate` (STORY-003-B05).
 */
function TeamCard({ team }: TeamCardProps) {
  const navigate = useNavigate();

  const installedDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(team.installed_at));

  function handleClick() {
    navigate({ to: '/app/teams/$teamId', params: { teamId: team.slack_team_id } });
  }

  return (
    <Card
      className="mb-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={handleClick}
      role="button"
      tabIndex={0}
      aria-label={`View workspaces for team ${team.slack_team_id}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') handleClick();
      }}
    >
      <div className="flex flex-col gap-1">
        <div className="font-mono text-sm font-medium text-slate-900">
          {team.slack_team_id}
        </div>
        <div className="text-xs text-slate-500">
          <span className="text-slate-400">Bot:</span>{' '}
          <span>{team.slack_bot_user_id}</span>
        </div>
        <div className="text-xs text-slate-400">
          Installed {installedDate}
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * AppContent — the visible content for the /app Slack Teams page.
 *
 * Exported as a named export so component tests can render it directly
 * inside a QueryClientProvider without going through ProtectedRoute.
 *
 * Rendering states:
 *   - isLoading → skeleton card
 *   - error     → inline error with retry button
 *   - teams.length === 0 → empty state with primary install button
 *   - teams.length > 0  → team list + secondary install anchor
 *
 * Toast notifications fire once on mount when OAuth callback params are present:
 *   - slack_install=ok        → toast.success('Tee-Mo installed.')
 *   - slack_install=cancelled → toast('Install cancelled.')  [informational]
 *   - slack_install=expired   → toast.error('Install session expired — please try again.')
 *   - slack_install=error     → toast.error('Install failed. Please try again or check the logs.')
 *   - slack_install=session_lost → toast.error('Your session expired during install. Please log in and try again.')
 *   - drive_connect=ok        → toast.success('Google Drive connected')
 *
 * After firing, navigate() strips the params from the URL (replace: true so
 * the back button doesn't re-show the toast).
 */
export function AppContent() {
  const search = useSearch({ from: '/app/' });
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['slack-teams'],
    queryFn: listSlackTeams,
    staleTime: 0,
  });

  // Fire toast once when OAuth callback params are present, then strip params.
  useEffect(() => {
    const { slack_install, drive_connect } = search;

    if (!slack_install && !drive_connect) return;

    if (slack_install === 'ok') {
      toast.success('Tee-Mo installed.');
    } else if (slack_install === 'cancelled') {
      toast('Install cancelled.');
    } else if (slack_install === 'expired') {
      toast.error('Install session expired — please try again.');
    } else if (slack_install === 'error') {
      toast.error('Install failed. Please try again or check the logs.');
    } else if (slack_install === 'session_lost') {
      toast.error('Your session expired during install. Please log in and try again.');
    }

    if (drive_connect === 'ok') {
      toast.success('Google Drive connected');
    }

    // Strip OAuth params from URL so the toast doesn't re-fire on refresh.
    navigate({ to: '/app', search: {}, replace: true });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps — fire once on mount only. search values are stable at mount time.

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl">
        {/* Page header */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Slack Teams
          </h1>
        </div>

        {/* Loading state */}
        {isLoading && (
          <Card data-testid="skeleton-card" className="animate-pulse">
            <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
            <div className="h-3 w-1/2 rounded bg-slate-100" />
          </Card>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <Card>
            <p className="text-sm text-rose-700">
              Failed to load Slack teams. Please try again.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-3 text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Retry
            </button>
          </Card>
        )}

        {/* Empty state */}
        {!isLoading && !error && data && data.teams.length === 0 && (
          <Card className="py-12 text-center border-dashed">
            <h2 className="text-lg font-semibold text-slate-900">
              No Slack teams yet
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Install Tee-Mo into a Slack workspace to get started
            </p>
            <a
              href={`${API_URL}/api/slack/install`}
              className="mt-6 inline-block"
            >
              <Button variant="primary">
                Install Slack
              </Button>
            </a>
          </Card>
        )}

        {/* Team list */}
        {!isLoading && !error && data && data.teams.length > 0 && (
          <>
            {data.teams.map((team) => (
              <TeamCard key={team.slack_team_id} team={team} />
            ))}
            <div className="mt-4 text-center">
              <a
                href={`${API_URL}/api/slack/install`}
                className="inline-block rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Install another team
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
