import { createRootRoute, Outlet } from '@tanstack/react-router';

/**
 * Root route — wraps every page in the application shell.
 *
 * Provides the full-height slate-50 background specified in Design Guide §2.2.
 * All child routes are rendered via <Outlet />.
 *
 * Sprint 1 scope: shell only, no nav bar or auth guard yet.
 */
export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50">
      <Outlet />
    </div>
  ),
});
