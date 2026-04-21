/**
 * Index route — `/`.
 *
 * STORY-023-02: The Sprint 1 health-check diagnostic page has been removed.
 * The root path now immediately redirects to `/app`. Unauthenticated users
 * are caught by the ProtectedRoute guard in `app.tsx` and pushed to `/login`.
 */
import { createFileRoute, Navigate } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: () => <Navigate to="/app" />,
});

