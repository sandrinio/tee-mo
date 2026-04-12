/**
 * /app — Slack Teams dashboard (STORY-005A-06).
 *
 * Replaces the Sprint 2 welcome-card placeholder with the real Slack Teams page.
 * This is the first screen a user sees after logging in; it shows all Slack
 * workspaces where Tee-Mo is installed for their account, plus an install button
 * to add new workspaces.
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
import { createFileRoute, Outlet } from '@tanstack/react-router';

import { ProtectedRoute } from '../components/auth/ProtectedRoute';

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * Layout route for /app. Wraps all /app/* child routes in ProtectedRoute
 * and renders them via <Outlet>.
 *
 * The teams list content that previously lived here is now in app.index.tsx.
 * This file is a pure layout — it adds auth protection to every /app child
 * route so individual pages don't need to wrap themselves in ProtectedRoute.
 */
export const Route = createFileRoute('/app')({
  component: AppLayout,
});

/**
 * AppLayout — wraps child routes in ProtectedRoute + Outlet.
 */
function AppLayout() {
  return (
    <ProtectedRoute>
      <Outlet />
    </ProtectedRoute>
  );
}
