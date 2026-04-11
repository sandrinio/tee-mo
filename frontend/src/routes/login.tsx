/**
 * /login — email + password sign-in.
 *
 * Uses the Zustand auth store's login() action. Redirects to /app on success.
 * Shows backend detail as an inline error on failure.
 *
 * If the user is already authenticated when this page mounts, they are
 * immediately redirected to /app — no double-login required.
 */
import { useEffect, useState } from 'react';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';

import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAuth } from '../stores/authStore';

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

/**
 * Login page component — renders the sign-in form and handles submission.
 *
 * Authentication flow:
 *   1. User submits email + password.
 *   2. Calls useAuth.getState().login() which proxies to POST /api/auth/login.
 *   3. On success: navigates to /app.
 *   4. On failure: renders the backend's detail message in a rose alert block.
 */
function LoginPage() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already logged in — bounce to /app.
  useEffect(() => {
    if (status === 'authed') {
      navigate({ to: '/app', replace: true });
    }
  }, [status, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await useAuth.getState().login(email, password);
      navigate({ to: '/app', replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Sign in to Tee-Mo
        </h1>
        <p className="mt-1 text-sm text-slate-600">Your BYOK Slack assistant.</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </label>

          {error && (
            <div
              role="alert"
              className="rounded-md bg-rose-50 border border-rose-200 px-3 py-2 text-sm text-rose-800"
            >
              {error}
            </div>
          )}

          <Button type="submit" disabled={submitting}>
            {submitting ? 'Signing in\u2026' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          No account?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </Link>
        </p>
      </Card>
    </div>
  );
}
