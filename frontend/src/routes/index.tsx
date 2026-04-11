/**
 * Index route — landing page at `/`.
 *
 * Fetches `/api/health` on mount via TanStack Query and renders a System Status
 * card using the Button, Card, and Badge design-system primitives introduced in
 * STORY-001-04.
 *
 * Three render states:
 *   - Loading  — `neutral` Badge "loading…" while query is in-flight.
 *   - Success  — Green `success` Badge for each table reporting "ok"; `warning`
 *               (amber) Badge for the overall backend if `status === "degraded"`.
 *   - Error    — `danger` Badge "error"; all table rows show "unreachable".
 *
 * The "Continue to login" Button links to `/login` (enabled in Sprint 2, STORY-002-04).
 */
import { createFileRoute, Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

/**
 * Shape of the `/api/health` response.
 *
 * `database` is a map from table name → status string ("ok" or an error
 * message). It is optional here because STORY-001-01's initial endpoint does
 * not yet include the database field; STORY-001-02 adds it.
 */
interface HealthResponse {
  status: 'ok' | 'degraded';
  service: string;
  version: string;
  database?: Record<string, string>;
}

export const Route = createFileRoute('/')({
  component: Landing,
});

/** The four Tee-Mo database tables reported by the health endpoint. */
const TABLES = [
  'teemo_users',
  'teemo_workspaces',
  'teemo_knowledge_index',
  'teemo_skills',
] as const;

/**
 * Landing page — typography, design-token demo, and end-to-end smoke test.
 *
 * Heading and subtitle are preserved from STORY-001-03. The System Status Card
 * is new in STORY-001-04.
 */
function Landing() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/api/health'),
    retry: false,
  });

  const overallVariant = isError
    ? 'danger'
    : isLoading
      ? 'neutral'
      : data?.status === 'ok'
        ? 'success'
        : 'warning';

  const overallLabel = isError
    ? 'error'
    : isLoading
      ? 'loading\u2026'
      : data?.status ?? 'unknown';

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      {/* Brand swatch + heading — preserved from STORY-001-03 */}
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 rounded-md bg-brand-500" aria-hidden="true" />
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">Tee-Mo</h1>
      </div>
      <p className="mt-3 text-base text-slate-500">Your BYOK Slack assistant.</p>

      {/* System Status card */}
      <Card className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">System Status</h2>
          <Badge variant={overallVariant}>Backend: {overallLabel}</Badge>
        </div>

        {/* Per-table status rows */}
        <ul className="space-y-2">
          {TABLES.map((t) => {
            const tableStatus = data?.database?.[t] ?? (isError ? 'unreachable' : '\u2026');
            const ok = tableStatus === 'ok';
            const rowVariant = ok ? 'success' : isError ? 'danger' : 'warning';
            return (
              <li key={t} className="flex items-center justify-between">
                <code className="font-mono text-sm text-slate-700">{t}</code>
                <Badge variant={rowVariant}>{tableStatus}</Badge>
              </li>
            );
          })}
        </ul>

        {/* Error detail — shown only on fetch failure */}
        {isError && error instanceof Error && (
          <p className="mt-4 font-mono text-xs text-rose-600">{error.message}</p>
        )}
      </Card>

      {/* CTA — enabled in Sprint 2 (STORY-002-04). */}
      <div className="mt-6">
        <Link to="/login">
          <Button variant="primary">Continue to login</Button>
        </Link>
      </div>
    </main>
  );
}
