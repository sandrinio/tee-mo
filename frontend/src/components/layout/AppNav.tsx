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
    <nav className="sticky top-0 z-10 bg-white/70 backdrop-blur-md border-b border-slate-200 px-6 h-14 flex items-center justify-between transition-colors duration-300">
      {/* Left: Logo & Primary Navigation */}
      <div className="flex items-center gap-8 md:gap-10">
        <Link to="/app" className="flex items-center gap-2 text-xl font-bold text-brand-500 hover:text-brand-600 transition-colors">
          Tee-Mo
        </Link>

        {/* Primary navigation list */}
        <ul className="flex items-center gap-1 hidden sm:flex">
          <li>
            <Link 
              to="/app" 
              className="px-3 py-1.5 rounded-md text-sm font-medium text-slate-600 hover:text-brand-600 hover:bg-brand-50 transition-all duration-200"
              activeProps={{ className: '!text-brand-600 bg-brand-50/50' }}
            >
              Workspaces
            </Link>
          </li>
        </ul>
      </div>

      {/* Right: User Controls */}
      <div className="flex items-center gap-4">
        {/* Profile representation */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-sm font-medium text-slate-700 leading-tight">{userEmail.split('@')[0]}</span>
            <span className="text-xs text-slate-500 leading-tight">{userEmail}</span>
          </div>
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-brand-400 to-amber-300 flex items-center justify-center text-white font-bold shadow-sm ring-2 ring-white">
            {userEmail.charAt(0).toUpperCase()}
          </div>
        </div>
        
        <Button 
          variant="ghost" 
          size="sm" 
          type="button" 
          onClick={handleLogout}
          className="text-slate-500 hover:text-red-600 hover:bg-red-50"
        >
          Log out
        </Button>
      </div>
    </nav>
  );
}
