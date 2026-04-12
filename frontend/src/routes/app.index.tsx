/**
 * /app (index) — Slack Teams dashboard (STORY-005A-06, refactored in S-05).
 *
 * This is the first screen a user sees after logging in; it shows all Slack
 * workspaces where Tee-Mo is installed for their account, plus an install button
 * to add new workspaces.
 *
 * Previously lived in app.tsx, but was extracted to app.index.tsx so that
 * app.tsx can serve as a layout route with <Outlet> for child routes like
 * /app/teams/$teamId.
 *
 * Design decisions:
 *   - Install button is always an `<a href>` — NOT an onClick handler. The browser
 *     must perform a full-page navigation so the session cookie rides along to the
 *     backend's OAuth initiation endpoint, which then redirects to Slack.
 *   - Flash banners are driven by the `slack_install` search param set by the OAuth
 *     callback. BANNER_VARIANTS is the SINGLE source of banner copy — never spread
 *     strings across the component body.
 *   - All data fetching goes through TanStack Query + listSlackTeams() in lib/api.ts.
 *     No raw fetch() calls in this file.
 *   - validateSearch narrows the `slack_install` param to a union type so useSearch
 *     returns typed data without any runtime overhead.
 */
import { useState } from 'react';
import { createFileRoute, useSearch, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';

import { Card } from '../components/ui/Card';
import { SignOutButton } from '../components/auth/SignOutButton';
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
 * Used in validateSearch and as the key type for BANNER_VARIANTS.
 */
const ALLOWED_INSTALL_STATES = ['ok', 'cancelled', 'expired', 'error', 'session_lost'] as const;
type SlackInstallState = (typeof ALLOWED_INSTALL_STATES)[number];

/**
 * Single source of truth for all flash banner copy, role attributes, and
 * Tailwind colour classes. Never spread banner strings into component body.
 *
 * `role` follows ARIA: "status" for informational banners, "alert" for
 * warnings/errors that require user attention.
 */
const BANNER_VARIANTS: Record<
  SlackInstallState,
  { text: string; role: 'status' | 'alert'; className: string }
> = {
  ok: {
    text: 'Tee-Mo installed.',
    role: 'status',
    className: 'bg-emerald-50 text-emerald-900 border-emerald-200',
  },
  cancelled: {
    text: 'Install cancelled.',
    role: 'status',
    className: 'bg-slate-50 text-slate-700 border-slate-200',
  },
  expired: {
    text: 'Install session expired — please try again.',
    role: 'alert',
    className: 'bg-amber-50 text-amber-900 border-amber-200',
  },
  error: {
    text: 'Install failed. Please try again or check the logs.',
    role: 'alert',
    className: 'bg-rose-50 text-rose-900 border-rose-200',
  },
  session_lost: {
    text: 'Your session expired during install. Please log in and try again.',
    role: 'alert',
    className: 'bg-amber-50 text-amber-900 border-amber-200',
  },
};

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * Index route for /app. validateSearch narrows the `slack_install` query param
 * to the SlackInstallState union so useSearch() returns typed data in AppContent.
 *
 * Any value outside the allowed set is coerced to `undefined` at parse time —
 * no runtime exceptions, no unrecognised banner variants.
 */
export const Route = createFileRoute('/app/')({
  component: AppContent,
  validateSearch: (
    search: Record<string, unknown>,
  ): { slack_install?: SlackInstallState } => {
    const v = search.slack_install;
    return {
      slack_install:
        typeof v === 'string' &&
        (ALLOWED_INSTALL_STATES as readonly string[]).includes(v)
          ? (v as SlackInstallState)
          : undefined,
    };
  },
});

// ---------------------------------------------------------------------------
// Inner components
// ---------------------------------------------------------------------------

/** Props for FlashBanner. */
interface FlashBannerProps {
  /** Install state key — looked up in BANNER_VARIANTS. */
  variant: SlackInstallState;
  /** Callback invoked when the user clicks the dismiss (✕) button. */
  onDismiss: () => void;
}

/**
 * FlashBanner — inline notification rendered when the OAuth callback appends
 * a `?slack_install=<state>` param. Reads all copy and styling from
 * BANNER_VARIANTS so strings are never scattered across the component.
 *
 * Uses `aria-label="Flash banner"` so tests can locate it via
 * `getByRole('status'/'alert', { name: /flash banner/i })`.
 */
function FlashBanner({ variant, onDismiss }: FlashBannerProps) {
  const { text, role, className } = BANNER_VARIANTS[variant];
  return (
    <div
      role={role}
      aria-label="Flash banner"
      className={`mb-4 flex items-center justify-between rounded-md border px-4 py-2 text-sm ${className}`}
    >
      <span>{text}</span>
      <button
        type="button"
        aria-label="Dismiss banner"
        onClick={onDismiss}
        className="ml-4 text-current opacity-60 hover:opacity-100"
      >
        ✕
      </button>
    </div>
  );
}

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
 *   - teams.length === 0 → empty state with primary install anchor
 *   - teams.length > 0  → team list + secondary install anchor
 *
 * Flash banner is shown whenever the `slack_install` search param is set.
 * Dismissing the banner calls navigate({ to: '/app', search: {} }) to strip
 * the param from the URL.
 */
export function AppContent() {
  const search = useSearch({ from: '/app/' });
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['slack-teams'],
    queryFn: listSlackTeams,
    staleTime: 0,
  });

  const bannerVariant =
    !dismissed && search.slack_install ? search.slack_install : null;

  const handleDismiss = () => {
    setDismissed(true);
    navigate({ to: '/app', search: {} });
  };

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl">
        {/* Page header */}
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Slack Teams
          </h1>
          <SignOutButton />
        </div>

        {/* Flash banner — shown when OAuth callback sets slack_install param */}
        {bannerVariant && (
          <FlashBanner variant={bannerVariant} onDismiss={handleDismiss} />
        )}

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
          <Card className="py-12 text-center">
            <h2 className="text-lg font-semibold text-slate-900">
              No Slack teams yet
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Install Tee-Mo into a Slack workspace to get started
            </p>
            <a
              href={`${API_URL}/api/slack/install`}
              className="mt-6 inline-block rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Install Slack
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
