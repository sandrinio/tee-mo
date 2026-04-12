/**
 * /app/teams/$teamId — Team detail page showing workspace list (STORY-003-B05).
 *
 * This is the second level of the Tee-Mo dashboard: after a user sees their
 * Slack teams on `/app`, clicking a team card navigates here. The page shows
 * all workspaces for that team and lets the user create a new one.
 *
 * Design decisions:
 *   - `teamId` is read from TanStack Router route params — always a Slack team ID
 *     string (e.g. "T0123ABCDEF").
 *   - Data fetching uses `useWorkspacesQuery(teamId)` from `useWorkspaces.ts`.
 *   - Create workspace action uses `useCreateWorkspaceMutation(teamId)` inside
 *     `CreateWorkspaceModal` — the modal manages its own mutation state.
 *   - Loading/error/empty states mirror the `/app` page patterns for consistency.
 *   - No font-bold (700) anywhere — max weight is font-semibold (600) per Design Guide.
 *   - All slate/neutral classes are Tailwind 4 built-ins; no new @theme tokens.
 */
import { useState } from 'react';
import { createFileRoute, Link } from '@tanstack/react-router';

import { Card } from '../components/ui/Card';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { WorkspaceCard } from '../components/dashboard/WorkspaceCard';
import { CreateWorkspaceModal } from '../components/dashboard/CreateWorkspaceModal';
import { useWorkspacesQuery } from '../hooks/useWorkspaces';

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * TanStack Router file-based route for /app/teams/$teamId.
 * The `$teamId` segment maps to `Route.useParams().teamId`.
 */
export const Route = createFileRoute('/app/teams/$teamId')({
  component: TeamDetailPage,
});

// ---------------------------------------------------------------------------
// Page components
// ---------------------------------------------------------------------------

/**
 * TeamDetailPage — shell that wraps TeamDetailContent in ProtectedRoute.
 *
 * ProtectedRoute handles the spinner/redirect-to-login logic; content only
 * renders when the user session is active.
 */
function TeamDetailPage() {
  return (
    <ProtectedRoute>
      <TeamDetailContent />
    </ProtectedRoute>
  );
}

/**
 * TeamDetailContent — the visible workspace-list page for a specific Slack team.
 *
 * Exported as a named export so component tests can render it directly inside
 * a QueryClientProvider without going through ProtectedRoute.
 *
 * Rendering states:
 *   - isLoading → skeleton card
 *   - error     → inline error with retry button
 *   - workspaces.length === 0 → empty state with "+ New Workspace" button
 *   - workspaces.length > 0  → workspace grid + "+ New Workspace" button
 */
export function TeamDetailContent() {
  const { teamId } = Route.useParams();
  const [modalOpen, setModalOpen] = useState(false);

  const { data: workspaces, isLoading, error, refetch } = useWorkspacesQuery(teamId);

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl">

        {/* Breadcrumb + page header */}
        <div className="mb-6">
          <Link
            to="/app"
            className="mb-2 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700"
            aria-label="Back to Teams"
          >
            ← Teams
          </Link>
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
              {teamId}
            </h1>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="rounded-md bg-[#E94560] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              + New Workspace
            </button>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <Card data-testid="skeleton-card" className="animate-pulse">
            <div className="h-4 w-1/3 rounded bg-slate-200 mb-2" />
            <div className="h-3 w-1/2 rounded bg-slate-100" />
          </Card>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <Card>
            <p className="text-sm text-rose-700">
              Failed to load workspaces. Please try again.
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-3 text-sm font-semibold text-[#E94560] hover:opacity-80"
            >
              Retry
            </button>
          </Card>
        )}

        {/* Empty state */}
        {!isLoading && !error && workspaces && workspaces.length === 0 && (
          <Card className="py-12 text-center">
            <h2 className="text-lg font-semibold text-slate-900">
              No workspaces yet
            </h2>
            <p className="mt-2 text-sm text-slate-600">
              Create your first workspace to start organising your AI data.
            </p>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="mt-6 inline-block rounded-md bg-[#E94560] px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
            >
              + New Workspace
            </button>
          </Card>
        )}

        {/* Workspace grid */}
        {!isLoading && !error && workspaces && workspaces.length > 0 && (
          <div className="grid gap-3">
            {workspaces.map((ws) => (
              <WorkspaceCard key={ws.id} workspace={ws} teamId={teamId} />
            ))}
          </div>
        )}

      </div>

      {/* Create workspace modal */}
      <CreateWorkspaceModal
        teamId={teamId}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
