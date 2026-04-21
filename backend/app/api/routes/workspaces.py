"""Workspace CRUD routes for the Tee-Mo API.

STORY-003-B02 implements the five REST endpoints for workspace management:

  GET  /api/slack-teams/{team_id}/workspaces  — list workspaces for current user
  POST /api/slack-teams/{team_id}/workspaces  — create a workspace
  GET  /api/workspaces/{id}                   — fetch a single workspace
  PATCH /api/workspaces/{id}                  — rename a workspace
  POST /api/workspaces/{id}/make-default      — atomically set workspace as default

Authorization pattern:
- All endpoints require Bearer/cookie auth via ``get_current_user_id``.
- Routes scoped to a team_id call ``assert_team_owner`` first to prevent
  cross-user data leakage.

DB access:
- All Supabase operations go through ``get_supabase()`` — NEVER ad-hoc
  ``create_client()`` calls (see FLASHCARDS.md, Backend Health Contract).

Transaction note:
- supabase-py does not support native transactions. The ``make-default`` swap
  is implemented as two sequential UPDATE calls: first reset all existing
  defaults for the team, then mark the target workspace as default.
  This is the documented pattern for Supabase atomic swaps via PostgREST.

ADR references: ADR-024 (workspace table schema).
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.core.db import get_supabase, execute_async
from app.models.workspace import WorkspaceCreate, WorkspaceResponse, WorkspaceUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Authorization helper
# ---------------------------------------------------------------------------


async def assert_team_owner(team_id: str, user_id: str) -> None:
    """Verify that the authenticated user owns the given Slack team.

    Queries ``teemo_slack_teams`` for a row matching both ``slack_team_id``
    and ``owner_user_id``. Raises HTTP 403 if no match is found, preventing
    cross-user access to workspaces scoped to a team.

    Args:
        team_id: The Slack team ID from the path parameter (e.g. ``"T12345"``).
        user_id: The authenticated user's UUID string from the JWT ``sub`` claim.

    Raises:
        HTTPException(403): If the user does not own (or has not installed) the
            specified Slack team.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_slack_teams")
        .select("slack_team_id")
        .eq("slack_team_id", team_id)
        .eq("owner_user_id", user_id)
        .limit(1)
        )
    )
    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this Slack team.",
        )


# ---------------------------------------------------------------------------
# Helper: coerce a raw Supabase dict to WorkspaceResponse
# ---------------------------------------------------------------------------


def _to_response(row: dict[str, Any]) -> WorkspaceResponse:
    """Deserialize a raw Supabase row dict into a WorkspaceResponse.

    Explicitly passes only the fields declared on WorkspaceResponse, so that
    secret columns (``encrypted_api_key``, ``encrypted_google_refresh_token``)
    present in the DB row are silently discarded — defense in depth on top of
    the model-level guard (see WorkspaceResponse docstring).

    Args:
        row: Raw dict returned by PostgREST / supabase-py.

    Returns:
        A validated WorkspaceResponse instance.
    """
    return WorkspaceResponse(
        id=row["id"],
        user_id=row["user_id"],
        name=row["name"],
        slack_team_id=row.get("slack_team_id"),
        ai_provider=row.get("ai_provider"),
        ai_model=row.get("ai_model"),
        is_default_for_team=row.get("is_default_for_team", False),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# GET /api/slack-teams/{team_id}/workspaces
# ---------------------------------------------------------------------------


@router.get(
    "/slack-teams/{team_id}/workspaces",
    response_model=list[WorkspaceResponse],
)
async def list_workspaces(
    team_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list[WorkspaceResponse]:
    """List all workspaces owned by the current user within a Slack team.

    Results are ordered by creation time (oldest first) for a stable display
    order. An empty list is HTTP 200 ``[]`` — NOT 404.

    Args:
        team_id: Slack team ID from the path (e.g. ``"T12345"``).
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        A list of ``WorkspaceResponse`` objects. May be empty.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(403): Authenticated user does not own this Slack team.
    """
    await assert_team_owner(team_id, user_id)
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .select("*")
        .eq("slack_team_id", team_id)
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        )
    )
    return [_to_response(row) for row in (result.data or [])]


# ---------------------------------------------------------------------------
# POST /api/slack-teams/{team_id}/workspaces
# ---------------------------------------------------------------------------


@router.post(
    "/slack-teams/{team_id}/workspaces",
    response_model=WorkspaceResponse,
    status_code=201,
)
async def create_workspace(
    team_id: str,
    body: WorkspaceUpdate,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Create a new workspace within a Slack team.

    If this is the first workspace for the (user, team) pair, it is
    automatically set as the default (``is_default_for_team=True``).

    ``created_at`` and ``updated_at`` are intentionally omitted from the
    insert payload — they use ``DEFAULT NOW()`` in the migration and must
    not be overridden (see FLASHCARDS.md — Supabase .upsert() rule).

    Args:
        team_id: Slack team ID from the path.
        body: Request body — only ``name`` is accepted.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        The newly created ``WorkspaceResponse`` with HTTP 201.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(403): Authenticated user does not own this Slack team.
    """
    await assert_team_owner(team_id, user_id)

    sb = get_supabase()

    # Determine if this is the first workspace for this (user, team) pair.
    existing = (
        await execute_async(sb.table("teemo_workspaces")
        .select("id")
        .eq("slack_team_id", team_id)
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    is_first = not existing.data

    payload: dict[str, Any] = {
        "name": body.name,
        "slack_team_id": team_id,
        "user_id": user_id,
        "is_default_for_team": is_first,
    }
    # created_at and updated_at intentionally excluded — DEFAULT NOW() on the DB side.

    result = await execute_async(sb.table("teemo_workspaces").insert(payload))
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create workspace.")

    return _to_response(result.data[0])


# ---------------------------------------------------------------------------
# GET /api/workspaces/{id}
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def get_workspace(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Fetch a single workspace by ID.

    The ``user_id`` filter ensures users can only retrieve their own workspaces,
    preventing cross-user data access without requiring a separate team ownership check.

    Args:
        workspace_id: UUID of the workspace from the path.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        The ``WorkspaceResponse`` for the requested workspace.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(404): Workspace not found or not owned by the current user.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .select("*")
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return _to_response(result.data[0])


# ---------------------------------------------------------------------------
# PATCH /api/workspaces/{id}
# ---------------------------------------------------------------------------


@router.patch(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
)
async def rename_workspace(
    workspace_id: uuid.UUID,
    body: WorkspaceUpdate,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Rename a workspace (update name only).

    Only the ``name`` field is accepted. All other fields (``ai_provider``,
    ``ai_model``, ``is_default_for_team``, etc.) are out of scope for this
    endpoint (see §1.3 Out of Scope).

    ``updated_at`` is NOT included in the update payload — the DB trigger or
    DEFAULT handles it. If the schema uses a manual ``updated_at``, this should
    be revisited; for now, the migration defines ``updated_at DEFAULT NOW()``
    which is preserved server-side.

    Args:
        workspace_id: UUID of the workspace from the path.
        body: Request body — only ``name`` is accepted.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        The updated ``WorkspaceResponse``.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(404): Workspace not found or not owned by the current user.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .update({"name": body.name})
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        )
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return _to_response(result.data[0])


# ---------------------------------------------------------------------------
# POST /api/workspaces/{id}/make-default
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/make-default",
    response_model=WorkspaceResponse,
)
async def make_workspace_default(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> WorkspaceResponse:
    """Atomically swap the default workspace for a Slack team.

    Two sequential Supabase UPDATE calls simulate a transaction:
      1. Reset all existing defaults for the user+team to FALSE.
      2. Set the target workspace's ``is_default_for_team`` to TRUE.

    supabase-py does not support native PostgreSQL transactions, so this is
    the documented pattern for atomic default swaps via PostgREST. In the
    unlikely event of a crash between the two writes, the team will have no
    default workspace — which is a safe-fail state (the frontend can handle
    it by prompting the user to re-set a default).

    Args:
        workspace_id: UUID of the workspace to promote to default.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        The updated ``WorkspaceResponse`` for the new default workspace.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(404): Workspace not found or not owned by the current user.
    """
    sb = get_supabase()

    # First: confirm the workspace exists and belongs to this user, and get its team.
    existing = (
        await execute_async(sb.table("teemo_workspaces")
        .select("*")
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    workspace_row = existing.data[0]
    team_id = workspace_row.get("slack_team_id")

    # Step 1: Reset all existing defaults for this user+team.
    await execute_async(sb.table("teemo_workspaces").update({"is_default_for_team": False}).eq(
        "user_id", user_id
    ).eq("slack_team_id", team_id).eq("is_default_for_team", True))

    # Step 2: Mark the target workspace as the new default.
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .update({"is_default_for_team": True})
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        )
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to set default workspace.")

    return _to_response(result.data[0])


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{id}
# ---------------------------------------------------------------------------


@router.delete(
    "/workspaces/{workspace_id}",
    status_code=204,
)
async def delete_workspace(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Delete a workspace and all associated data.

    PostgreSQL ON DELETE CASCADE removes child rows from:
    teemo_skills, teemo_knowledge_index, teemo_workspace_channels.

    Authorization is enforced by filtering on both ``id`` AND ``user_id`` —
    if the workspace does not exist or is owned by another user, the Supabase
    DELETE returns empty data and we raise HTTP 404. Returning 404 (rather than
    403) for cross-user access is intentional: it avoids leaking existence
    information (ADR-024).

    Args:
        workspace_id: UUID of the workspace to delete.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(404): Workspace not found or not owned by the current user.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .delete()
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        )
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")


# ---------------------------------------------------------------------------
# GET /api/workspaces/{id}/skills  (STORY-023-01)
# ---------------------------------------------------------------------------


@router.get(
    "/workspaces/{workspace_id}/skills",
    status_code=200,
)
async def list_workspace_skills(
    workspace_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
) -> list[dict]:
    """Return the active skill catalog for a workspace.

    Reuses ``skill_service.list_skills`` which returns ``name`` and ``summary``
    only — instructions are never included in the catalog listing.

    Authorization mirrors ``get_workspace``: filtering on both ``id`` AND
    ``user_id`` on the workspaces table ensures users can only list skills
    for their own workspaces.

    Args:
        workspace_id: UUID of the workspace from the path.
        user_id: Injected by ``get_current_user_id``; raises 401 if invalid.

    Returns:
        List of dicts with ``name`` and ``summary``. Empty list if none exist.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(404): Workspace not found or not owned by the current user.
    """
    from app.services.skill_service import list_skills  # local import — avoids circular risk

    sb = get_supabase()

    # Confirm workspace ownership before exposing skill data.
    ownership_check = (
        await execute_async(sb.table("teemo_workspaces")
        .select("id")
        .eq("id", str(workspace_id))
        .eq("user_id", user_id)
        .limit(1)
        )
    )
    if not ownership_check.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")

    return list_skills(str(workspace_id), sb)

