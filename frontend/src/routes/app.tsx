/**
 * /app — Layout route for all /app/* pages (STORY-005A-06, STORY-008-04).
 *
 * This is a pure layout route. It:
 *   1. Wraps all /app/* child routes in ProtectedRoute (auth guard).
 *   2. Renders AppNav at the top with the logged-in user's email.
 *   3. Wraps the child Outlet in a centered <main> container.
 *
 * STORY-008-04: Added AppNav and main content wrapper.
 * User email is sourced from the Zustand auth store (useAuth) — same store
 * used by ProtectedRoute and AuthInitializer.
 */
import { createFileRoute, Outlet } from '@tanstack/react-router';

import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { AppNav } from '../components/layout/AppNav';
import { useAuth } from '../stores/authStore';

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
 * AppLayout — wraps child routes in ProtectedRoute + AppNav + Outlet.
 *
 * Reads the authenticated user's email from the Zustand auth store to pass
 * to AppNav. Falls back to empty string during the 'unknown' auth init phase
 * (ProtectedRoute shows a spinner in that case, so AppNav is not visible).
 */
function AppLayout() {
  const user = useAuth((s) => s.user);
  const userEmail = user?.email ?? '';

  return (
    <ProtectedRoute>
      <AppNav userEmail={userEmail} />
      <main className="px-6 lg:px-8 py-8 lg:py-12 max-w-7xl mx-auto">
        <Outlet />
      </main>
    </ProtectedRoute>
  );
}
