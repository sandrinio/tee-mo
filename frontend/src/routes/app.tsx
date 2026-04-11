// EPIC-003 will replace the body of this route with <WorkspaceList />.
// Keep the route path "/app" stable so the router does not need refactoring.

/**
 * /app — post-login placeholder (EPIC-002).
 *
 * Wraps content in <ProtectedRoute>, shows the signed-in email, and renders
 * a SignOutButton. EPIC-003 replaces the body with the real workspace list.
 */
import { createFileRoute } from '@tanstack/react-router';

import { Card } from '../components/ui/Card';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { SignOutButton } from '../components/auth/SignOutButton';
import { useAuth } from '../stores/authStore';

export const Route = createFileRoute('/app')({
  component: AppPage,
});

/**
 * AppPage — shell component that wraps the authenticated content in ProtectedRoute.
 *
 * ProtectedRoute handles the spinner and redirect logic; AppContent only
 * renders when status is 'authed'.
 */
function AppPage() {
  return (
    <ProtectedRoute>
      <AppContent />
    </ProtectedRoute>
  );
}

/**
 * AppContent — the visible content for the /app placeholder.
 *
 * Reads the user from the Zustand store using optional chaining (`user?.email`)
 * because the user field is technically nullable until ProtectedRoute completes
 * its guard — even though in practice ProtectedRoute ensures user is set before
 * rendering children.
 */
function AppContent() {
  const user = useAuth((s) => s.user);
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md p-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Welcome to Tee-Mo
        </h1>
        <p className="mt-2 text-slate-600">
          Signed in as <span className="font-medium text-slate-900">{user?.email}</span>.
        </p>
        <div className="mt-6 flex justify-center">
          <SignOutButton />
        </div>
      </Card>
    </div>
  );
}
