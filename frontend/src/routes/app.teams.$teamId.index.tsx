/**
 * /app/teams/$teamId (index) — Team detail page showing workspace list.
 *
 * This file was extracted from `app.teams.$teamId.tsx` during STORY-006-05
 * when that file became a layout route (required by TanStack Router file-based
 * routing rules: any file whose name is a prefix of another route file becomes
 * a layout and must render <Outlet>).
 *
 * STORY-008-03 changes:
 *   - Grid layout: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6` (R5).
 *   - After creating workspace, navigate to guided setup at
 *     `/app/teams/$teamId/$workspaceId` (R6).
 *   - Empty state uses dashed border: `border-2 border-dashed border-slate-200 bg-slate-50` (R7).
 *   - All hardcoded hex replaced with `brand-500`/`brand-600` tokens (R8).
 *   - Ad-hoc `<button>` elements replaced with `<Button>` component (R9).
 *   - Redundant layout styles removed — parent `app.tsx` already provides
 *     `px-6 lg:px-8 py-8 lg:py-12 max-w-7xl mx-auto`.
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
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';

import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { WorkspaceCard } from '../components/dashboard/WorkspaceCard';
import { CreateWorkspaceModal } from '../components/dashboard/CreateWorkspaceModal';
import { useWorkspacesQuery } from '../hooks/useWorkspaces';
import type { Workspace } from '../lib/api';

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * TanStack Router file-based index route for /app/teams/$teamId.
 * The `$teamId` segment maps to `Route.useParams().teamId`.
 */
export const Route = createFileRoute('/app/teams/$teamId/')({
  component: TeamDetailPage,
});

// ---------------------------------------------------------------------------
// Page components
// ---------------------------------------------------------------------------

/**
 * TeamDetailPage — renders TeamDetailContent directly.
 *
 * Auth protection is handled by the grandparent layout route (app.tsx) which
 * wraps all /app/* routes in ProtectedRoute.
 */
function TeamDetailPage() {
  return <TeamDetailContent />;
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
 *   - workspaces.length === 0 → dashed-border empty state with "+ New Workspace" CTA
 *   - workspaces.length > 0  → 3-column responsive grid + "+ New Workspace" header button
 *
 * After creating a workspace, navigates to `/app/teams/$teamId/$workspaceId`
 * (guided setup mode — STORY-008-03 R6).
 *
 * Each workspace card links to `/app/teams/$teamId/$workspaceId` for the
 * workspace detail page added in STORY-006-05.
 *
 * The parent layout (app.tsx) already provides:
 *   `px-6 lg:px-8 py-8 lg:py-12 max-w-7xl mx-auto`
 * so this component does NOT add its own outer padding or max-width wrapper.
 */
export function TeamDetailContent() {
  const { teamId } = Route.useParams();
  const [modalOpen, setModalOpen] = useState(false);
  const navigate = useNavigate();

  const { data: workspaces, isLoading, error, refetch } = useWorkspacesQuery(teamId);

  /**
   * handleCreated — called by CreateWorkspaceModal on successful creation.
   * Navigates to the newly created workspace's guided setup page (R6).
   *
   * @param newWorkspace - The workspace record returned by the create mutation.
   */
  function handleCreated(newWorkspace: Workspace) {
    navigate({
      to: '/app/teams/$teamId/$workspaceId',
      params: { teamId, workspaceId: newWorkspace.id },
    });
  }

  return (
    <div>
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
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={() => setModalOpen(true)}
          >
            + New Workspace
          </Button>
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
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => refetch()}
            className="mt-3"
          >
            Retry
          </Button>
        </Card>
      )}

      {/* Empty state — dashed border (R7) */}
      {!isLoading && !error && workspaces && workspaces.length === 0 && (
        <div className="rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 py-16 text-center">
          <h2 className="text-lg font-semibold text-slate-900">
            No workspaces yet
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Create your first workspace to start organising your AI data.
          </p>
          <p className="mt-4 text-sm text-slate-500">
            Use the "+ New Workspace" button above to get started.
          </p>
        </div>
      )}

      {/* Workspace grid — R5: 3-column responsive grid */}
      {!isLoading && !error && workspaces && workspaces.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {workspaces.map((ws) => (
            <WorkspaceCard key={ws.id} workspace={ws} teamId={teamId} />
          ))}
        </div>
      )}

      {/* Create workspace modal — R6: passes onCreated for navigate-on-create */}
      <CreateWorkspaceModal
        teamId={teamId}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={handleCreated}
      />
    </div>
  );
}
