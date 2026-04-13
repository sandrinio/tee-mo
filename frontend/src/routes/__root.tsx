import { createRootRoute, Outlet } from '@tanstack/react-router';
import { Toaster } from 'sonner';

/**
 * Root route — wraps every page in the application shell.
 *
 * Provides the full-height slate-50 background specified in Design Guide §2.2.
 * All child routes are rendered via <Outlet />.
 *
 * STORY-008-04: Added <Toaster /> from sonner for toast notifications.
 * The Toaster is mounted once at the root so all routes can fire toasts
 * without needing to re-mount the toaster component.
 */
export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50">
      <Outlet />
      <Toaster position="bottom-right" richColors duration={4000} />
    </div>
  ),
});
