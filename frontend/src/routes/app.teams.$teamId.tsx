/**
 * /app/teams/$teamId — Layout route for team detail (STORY-006-05 refactor).
 *
 * This file was refactored from a page component to a layout route when
 * STORY-006-05 added `app.teams.$teamId.$workspaceId.tsx` as a child route.
 *
 * Per the TanStack Router file-based routing rule (FLASHCARDS.md "File-based
 * routes with children are layout routes — parent MUST render <Outlet>"):
 *   - The previous page content moved to `app.teams.$teamId.index.tsx`.
 *   - This file now renders a transparent <Outlet /> so nested routes
 *     (team index + workspace detail) can render into the same auth context.
 *
 * Auth protection is inherited from the grandparent `app.tsx` layout.
 */
import { createFileRoute, Outlet } from '@tanstack/react-router';

/**
 * TanStack Router file-based layout route for /app/teams/$teamId.
 * All child routes render through the <Outlet />.
 */
export const Route = createFileRoute('/app/teams/$teamId')({
  component: TeamLayout,
});

/**
 * TeamLayout — transparent layout; renders child routes via <Outlet>.
 *
 * All /app/teams/$teamId/* routes (index + workspace detail) render here.
 */
function TeamLayout() {
  return <Outlet />;
}
