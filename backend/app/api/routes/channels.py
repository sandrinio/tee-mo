"""Channel binding REST endpoints for the Tee-Mo API.

STORY-007-04: Channel Binding REST Endpoints

Implements 4 REST endpoints for binding Slack channels to workspaces,
and listing available Slack channels for a team:

  POST   /api/workspaces/{workspace_id}/channels          — bind channel (201)
  DELETE /api/workspaces/{workspace_id}/channels/{channel_id} — unbind (204)
  GET    /api/workspaces/{workspace_id}/channels          — list bindings (200)
  GET    /api/slack/teams/{team_id}/channels              — list Slack channels (200)

Authorization pattern:
- All endpoints require authentication via ``get_current_user_id``.
- Workspace-scoped routes verify ownership via ``teemo_workspaces`` lookup;
  non-owners receive HTTP 403.
- The Slack team channels endpoint verifies ownership via ``teemo_slack_teams``
  lookup; non-owners receive HTTP 403.

DB access:
- All Supabase operations go through ``get_supabase()`` — NEVER ad-hoc
  ``create_client()`` calls (see FLASHCARDS.md, Backend Health Contract).

Table schema (ADR-024):
- ``teemo_workspace_channels``: slack_channel_id (PK), workspace_id (FK),
  bound_at (DEFAULT NOW() — OMITTED from insert payloads per FLASHCARDS.md
  Supabase .upsert() rule).
- ``teemo_slack_teams``: slack_team_id (PK), owner_user_id, encrypted_slack_bot_token.

Slack SDK:
- ``AsyncWebClient`` is imported at MODULE LEVEL so tests can patch it via
  ``app.api.routes.channels.AsyncWebClient``. Do NOT move it inside a function
  body — the monkeypatch pattern requires module-level resolution (see
  FLASHCARDS.md, httpx module-level import rule, same principle applies here).

ADR references: ADR-024 (table schema).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from slack_sdk.web.async_client import AsyncWebClient

from app.api.deps import get_current_user_id
from app.core import encryption as encryption_module
from app.core.db import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["channels"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ChannelBindRequest(BaseModel):
    """Request body for POST /api/workspaces/{workspace_id}/channels.

    Attributes
    ----------
    slack_channel_id : str
        The Slack channel ID to bind (e.g. ``"C001"``).
    """

    slack_channel_id: str


# ---------------------------------------------------------------------------
# Authorization helpers
# ---------------------------------------------------------------------------


def _assert_workspace_owner(workspace_id: str, user_id: str) -> dict[str, Any]:
    """Verify that the authenticated user owns the given workspace.

    Queries ``teemo_workspaces`` for a row matching both ``id`` and ``user_id``.
    Raises HTTP 403 if no match — prevents cross-user channel binding.

    Parameters
    ----------
    workspace_id : str
        The workspace UUID from the path parameter.
    user_id : str
        The authenticated caller's UUID (from JWT sub claim).

    Returns
    -------
    dict
        The raw Supabase workspace row.

    Raises
    ------
    HTTPException(403)
        If the user does not own the specified workspace.
    """
    sb = get_supabase()
    result = (
        sb.table("teemo_workspaces")
        .select("*")
        .eq("id", workspace_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=403, detail="Forbidden")
    return result.data[0]


def _assert_slack_team_owner(team_id: str, user_id: str) -> dict[str, Any]:
    """Verify that the authenticated user owns the given Slack team.

    Queries ``teemo_slack_teams`` for a row matching both ``slack_team_id``
    and ``owner_user_id``. Raises HTTP 403 if no match — prevents cross-user
    access to Slack team data.

    Parameters
    ----------
    team_id : str
        The Slack team ID from the path parameter (e.g. ``"T12345"``).
    user_id : str
        The authenticated caller's UUID (from JWT sub claim).

    Returns
    -------
    dict
        The raw Supabase slack team row (includes ``encrypted_slack_bot_token``).

    Raises
    ------
    HTTPException(403)
        If the user does not own the specified Slack team.
    """
    sb = get_supabase()
    result = (
        sb.table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", team_id)
        .eq("owner_user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=403, detail="Forbidden")
    return result.data[0]


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/channels — bind a channel
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/channels",
    status_code=201,
)
async def bind_channel(
    workspace_id: str,
    body: ChannelBindRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Bind a Slack channel to a workspace.

    Verifies workspace ownership, checks for an existing binding (returns 409
    if already bound), then inserts the new binding record.

    ``bound_at`` is intentionally omitted from the insert payload — it uses
    ``DEFAULT NOW()`` in the migration (see FLASHCARDS.md, Supabase upsert rule).

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    body : ChannelBindRequest
        Request body containing the Slack channel ID.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    dict
        The created binding record with ``slack_channel_id``, ``workspace_id``,
        and ``bound_at`` — HTTP 201 Created.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    HTTPException(409)
        The channel is already bound to this workspace (``detail="channel_already_bound"``).
    """
    # 1. Verify workspace ownership — raises 403 for non-owners.
    _assert_workspace_owner(workspace_id, user_id)

    sb = get_supabase()

    # 2. Check for existing binding (duplicate guard — avoids relying on PK violation).
    existing = (
        sb.table("teemo_workspace_channels")
        .select("*")
        .eq("slack_channel_id", body.slack_channel_id)
        .eq("workspace_id", workspace_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="channel_already_bound")

    # 3. Insert the new binding.
    # bound_at is intentionally excluded — DEFAULT NOW() on the DB side (ADR-024).
    payload: dict[str, Any] = {
        "slack_channel_id": body.slack_channel_id,
        "workspace_id": workspace_id,
    }
    result = sb.table("teemo_workspace_channels").insert(payload).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to bind channel.")

    return result.data[0]


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/channels/{channel_id} — unbind
# ---------------------------------------------------------------------------


@router.delete(
    "/workspaces/{workspace_id}/channels/{channel_id}",
    status_code=204,
)
async def unbind_channel(
    workspace_id: str,
    channel_id: str,
    user_id: str = Depends(get_current_user_id),
) -> Response:
    """Remove a Slack channel binding from a workspace.

    Verifies workspace ownership, then deletes the binding record.

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    channel_id : str
        The Slack channel ID to unbind (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    Response
        HTTP 204 No Content.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    # 1. Verify workspace ownership — raises 403 for non-owners.
    _assert_workspace_owner(workspace_id, user_id)

    sb = get_supabase()

    # 2. Delete the binding row by both channel_id and workspace_id.
    (
        sb.table("teemo_workspace_channels")
        .delete()
        .eq("slack_channel_id", channel_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )

    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/channels — list bindings
# ---------------------------------------------------------------------------


@router.get("/workspaces/{workspace_id}/channels")
async def list_channel_bindings(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    """List all Slack channels bound to a workspace, enriched with is_member.

    Returns an empty list (not 404) when no channels are bound.
    Results are ordered by ``bound_at`` ascending for a stable display order.

    Enrichment (STORY-008-02):
    - Looks up the workspace's ``slack_team_id`` from ``teemo_workspaces``.
    - Fetches the encrypted bot token from ``teemo_slack_teams``.
    - Decrypts the token via ``encryption_module.decrypt``.
    - Calls ``conversations.info`` per binding to populate ``is_member``
      and ``channel_name``.
    - Fallback: on any exception OR ``ok=False``, sets ``is_member=False``
      and ``channel_name=slack_channel_id`` — enrichment errors are non-fatal.

    ``AsyncWebClient`` is imported at MODULE LEVEL so that test suite can patch
    it via ``app.api.routes.channels.AsyncWebClient``. Do NOT move it inside
    this function body (see FLASHCARDS.md, httpx module-level import rule).

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    list[dict]
        Ordered list of binding records enriched with ``is_member`` and
        ``channel_name``. May be empty.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    # 1. Verify workspace ownership — raises 403 for non-owners.
    workspace_row = _assert_workspace_owner(workspace_id, user_id)

    sb = get_supabase()

    # 2. Fetch all bindings for this workspace.
    result = (
        sb.table("teemo_workspace_channels")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("bound_at", desc=False)
        .execute()
    )
    bindings: list[dict[str, Any]] = result.data or []

    if not bindings:
        return bindings

    # 3. Resolve the Slack team ID from the workspace row.
    slack_team_id: str = workspace_row.get("slack_team_id", "")

    # 4. Fetch the encrypted bot token from teemo_slack_teams.
    team_result = (
        sb.table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", slack_team_id)
        .limit(1)
        .execute()
    )
    if not team_result.data:
        # No team row means we cannot enrich — return bindings with fallback values.
        for binding in bindings:
            binding["is_member"] = False
            binding["channel_name"] = binding["slack_channel_id"]
        return bindings

    encrypted_token: str = team_result.data[0]["encrypted_slack_bot_token"]
    bot_token: str = encryption_module.decrypt(encrypted_token)

    # 5. Create an AsyncWebClient with the decrypted token.
    #    AsyncWebClient is module-level — tests monkeypatch it at
    #    app.api.routes.channels.AsyncWebClient.
    client = AsyncWebClient(token=bot_token)

    # 6. Enrich each binding with is_member and channel_name via conversations.info.
    enriched: list[dict[str, Any]] = []
    for binding in bindings:
        channel_id: str = binding["slack_channel_id"]
        try:
            info = await client.conversations_info(channel=channel_id)
            if info.get("ok"):
                channel_data = info.get("channel", {})
                binding["is_member"] = bool(channel_data.get("is_member", False))
                binding["channel_name"] = channel_data.get("name", channel_id)
            else:
                # ok=False but no exception — apply fallback (R13).
                binding["is_member"] = False
                binding["channel_name"] = channel_id
        except Exception:
            # Any exception (SlackApiError, network error, etc.) — apply fallback (R13).
            logger.warning(
                "conversations.info failed for channel %s — falling back to is_member=False",
                channel_id,
            )
            binding["is_member"] = False
            binding["channel_name"] = channel_id
        enriched.append(binding)

    return enriched


# ---------------------------------------------------------------------------
# GET /api/slack/teams/{team_id}/channels — list available Slack channels
# ---------------------------------------------------------------------------


@router.get("/slack/teams/{team_id}/channels")
async def list_slack_team_channels(
    team_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    """List all Slack channels available in a team via the Slack API.

    Verifies team ownership, decrypts the bot token, and calls
    ``conversations.list`` with ``types="public_channel,private_channel"``
    to return all channels the bot can see.

    ``AsyncWebClient`` is imported at module level (NOT inside this function)
    so that the test suite can patch ``app.api.routes.channels.AsyncWebClient``
    at import time. See FLASHCARDS.md httpx module-level import rule.

    Parameters
    ----------
    team_id : str
        The Slack team ID (path parameter, e.g. ``"T12345"``).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    list[dict]
        List of channel dicts from the Slack API response (``id``, ``name``,
        ``is_private``, etc.).

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the specified Slack team.
    HTTPException(500)
        Slack API call failed or returned ``ok: false``.
    """
    # 1. Verify team ownership — raises 403 for non-owners.
    team_row = _assert_slack_team_owner(team_id, user_id)

    # 2. Decrypt the bot token stored in teemo_slack_teams.
    #    Called via encryption_module.decrypt (not a direct binding) so that
    #    tests patching app.core.encryption.decrypt are effective at call time.
    encrypted_token: str = team_row["encrypted_slack_bot_token"]
    bot_token = encryption_module.decrypt(encrypted_token)

    # 3. Call the Slack API to list channels.
    #    AsyncWebClient is module-level so tests can patch it.
    client = AsyncWebClient(token=bot_token)
    response = await client.conversations_list(
        types="public_channel,private_channel"
    )

    if not response.get("ok"):
        raise HTTPException(status_code=500, detail="Slack API call failed.")

    return response.get("channels", [])
