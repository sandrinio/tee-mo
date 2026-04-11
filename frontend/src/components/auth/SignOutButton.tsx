/**
 * SignOutButton — calls useAuth.logout() then redirects to /login.
 * Ghost-variant button; safe to drop into any authenticated layout.
 */
import { useNavigate } from '@tanstack/react-router';

import { Button } from '../ui/Button';
import { useAuth } from '../../stores/authStore';

/**
 * A ghost-variant button that signs the current user out and navigates to /login.
 *
 * Calls the Zustand store's logout() action (which clears the server-side
 * cookie and the TanStack Query cache) then immediately navigates to /login
 * with replace: true so the browser history entry for /app is gone.
 */
export function SignOutButton() {
  const navigate = useNavigate();

  const handleClick = async () => {
    await useAuth.getState().logout();
    navigate({ to: '/login', replace: true });
  };

  return (
    <Button variant="ghost" onClick={handleClick}>
      Sign out
    </Button>
  );
}
