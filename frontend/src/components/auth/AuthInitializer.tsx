/**
 * AuthInitializer — fires the initial auth rehydration on app mount.
 *
 * Calls `useAuth.getState().fetchMe()` exactly once, giving ProtectedRoute
 * the auth state it needs before rendering children. Renderless.
 *
 * Mounted once in main.tsx inside <QueryClientProvider> and above
 * <RouterProvider> so the fetch kicks off before routes mount.
 */
import { useEffect } from 'react';

import { useAuth } from '../../stores/authStore';

/**
 * Renderless component that rehydrates auth state on app mount.
 * Renders null — exists solely to call fetchMe() once in a useEffect.
 */
export function AuthInitializer() {
  useEffect(() => {
    // Stable Zustand action — safe to call from an empty-deps effect.
    useAuth.getState().fetchMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return null;
}
