/**
 * /app/teams/$teamId/$workspaceId — Workspace detail page.
 *
 * STORY-025-06 cutover: legacy stacked layout + setup wizard guard removed.
 * The route is now a thin wrapper that mounts WorkspaceShell (which owns all
 * module bodies, status strip, sticky tab bar, breadcrumb, and modal orchestration
 * via the module registry introduced in STORY-025-01..05).
 *
 * Route params:
 *   - `teamId`      — Slack team ID (e.g. "T0123ABCDEF")
 *   - `workspaceId` — workspace UUID
 *
 * All business logic lives in WorkspaceShell + the module components under
 * frontend/src/components/workspace/.
 */
import { createFileRoute } from '@tanstack/react-router';

import { WorkspaceShell } from '../components/workspace/WorkspaceShell';

// ---------------------------------------------------------------------------
// Route declaration
// ---------------------------------------------------------------------------

/**
 * TanStack Router file-based route for /app/teams/$teamId/$workspaceId.
 * Params available via `Route.useParams()`.
 */
export const Route = createFileRoute('/app/teams/$teamId/$workspaceId')({
  component: WorkspaceDetailPage,
});

// ---------------------------------------------------------------------------
// WorkspaceDetailPage
// ---------------------------------------------------------------------------

/**
 * WorkspaceDetailPage — thin wrapper; all UI lives inside WorkspaceShell.
 *
 * Auth protection is inherited from the grandparent `app.tsx` layout route.
 */
function WorkspaceDetailPage() {
  const { teamId, workspaceId } = Route.useParams();

  return <WorkspaceShell workspaceId={workspaceId} teamId={teamId} />;
}
