/**
 * AppNav — persistent top navigation bar for all /app pages (STORY-008-04).
 *
 * Renders a sticky nav with:
 *   - Left: "Tee-Mo" text logo linked to /app
 *   - Center: "Workspaces" link to /app
 *   - Right: user email + "Log out" ghost button
 *
 * Logout flow uses try/finally so navigation to /login fires even when the
 * server-side logoutUser() call fails (e.g. network error). This matches the
 * principle that the UI must always let users escape even if the server is down.
 *
 * Design tokens used:
 *   - bg-white, border-b border-slate-200 — nav background/border
 *   - text-brand-500 — logo coral color
 *   - text-slate-600, text-slate-700 — nav text
 *   - h-14, px-6 — layout dimensions from Design Guide §6
 */
import { Link, useNavigate } from '@tanstack/react-router';
import { logoutUser } from '../../lib/api';
import { Button } from '../ui/Button';

/** Props accepted by AppNav. */
export interface AppNavProps {
  /** The logged-in user's email address, displayed in the right section of the nav. */
  userEmail: string;
}

/**
 * AppNav — top navigation bar rendered on all /app pages.
 *
 * @example
 * ```tsx
 * <AppNav userEmail={user.email} />
 * ```
 */
export function AppNav({ userEmail }: AppNavProps) {
  const navigate = useNavigate();

  /**
   * Handle logout click. Calls logoutUser() then navigates to /login.
   * Uses try/finally so the redirect happens even if the API call fails.
   */
  async function handleLogout() {
    try {
      await logoutUser();
    } catch {
      /* intentional: navigate to /login regardless of logout API result */
    } finally {
      navigate({ to: '/login' });
    }
  }

  return (
    <nav className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 h-14 flex items-center justify-between">
      {/* Left: logo */}
      <Link to="/app" className="text-lg font-semibold text-brand-500">
        Tee-Mo
      </Link>

      {/* Center: primary navigation */}
      <Link to="/app" className="text-sm font-medium text-slate-600">
        Workspaces
      </Link>

      {/* Right: user email + logout */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-700">{userEmail}</span>
        <Button variant="ghost" size="sm" type="button" onClick={handleLogout}>
          Log out
        </Button>
      </div>
    </nav>
  );
}
