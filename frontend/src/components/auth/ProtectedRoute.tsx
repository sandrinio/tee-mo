/**
 * ProtectedRoute — guards a route behind the Zustand auth store.
 *
 * Behavior:
 *   - status === 'unknown' → centered spinner (AuthInitializer hasn't resolved yet).
 *   - status === 'anon'    → redirect to /login preserving the current path in ?redirect.
 *   - status === 'authed'  → render children.
 *
 * The ?redirect search param is populated for future stories (EPIC-003) to
 * consume. This story's /login does not read it yet.
 */
import { useEffect } from 'react';
import { useLocation, useNavigate } from '@tanstack/react-router';

import { useAuth } from '../../stores/authStore';

/** Props for ProtectedRoute. */
interface ProtectedRouteProps {
  /** Child content to render when the user is authenticated. */
  children: React.ReactNode;
}

/**
 * Route guard component that checks the Zustand auth store status.
 *
 * Renders a full-screen spinner while status is 'unknown', redirects to
 * /login (with ?redirect=<current-path>) when status is 'anon', and
 * renders children when status is 'authed'.
 */
export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const status = useAuth((s) => s.status);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === 'anon') {
      navigate({
        to: '/login',
        search: { redirect: location.pathname },
        replace: true,
      });
    }
  }, [status, navigate, location.pathname]);

  if (status !== 'authed') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div
          role="status"
          aria-label="Checking authentication"
          className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent"
        />
      </div>
    );
  }

  return <>{children}</>;
}
