"""MCP Server REST endpoints for the Tee-Mo API.

STORY-012-02 (EPIC-012 MCP Integration).

Implements 5 REST endpoints mounted under
``/api/workspaces/{workspace_id}/mcp-servers``:

  POST   /api/workspaces/{workspace_id}/mcp-servers           — create (201)
  GET    /api/workspaces/{workspace_id}/mcp-servers           — list (200)
  PATCH  /api/workspaces/{workspace_id}/mcp-servers/{name}    — update (200)
  DELETE /api/workspaces/{workspace_id}/mcp-servers/{name}    — remove (204)
  POST   /api/workspaces/{workspace_id}/mcp-servers/{name}/test — test (200)

Authorization pattern:
- All endpoints call ``assert_team_member(team_id, user_id)`` BEFORE any DB
  write. The ``team_id`` is resolved from ``workspace_id`` via a ``teemo_workspaces``
  lookup. A missing workspace returns 404 (existence-leak guard). A non-member
  returns 403 (assert_team_member behaviour from workspaces.py:79).

Security:
- ``McpServerPublic`` schema NEVER includes ``headers`` or ``headers_encrypted``.
  The schema-level omission is the primary guard; there is no runtime filter.
- The ``/test`` endpoint uses headers internally for the MCP handshake but
  NEVER echoes any header value in the response.

Error mapping:
- ``McpValidationError`` → 400 with ``{"detail": <message>}``
- Service-layer ``ValueError`` (not found) → 404
- Auth failure → 403 (assert_team_member) or 404 (workspace missing)
- HTTP 200 always for ``/test`` — sad-path result is body-encoded, not HTTP.

IMPORTANT: Do NOT add ``from __future__ import annotations`` to this file.
FastAPI resolves type annotations at runtime for dependency injection.
Stringifying annotations (PEP 563) breaks this. See FLASHCARDS.md #fastapi.

IMPORTANT: ``mcp_service`` is imported at MODULE LEVEL so tests can patch
specific functions via ``monkeypatch.setattr``. Same principle as
``automations.py`` imports (see FLASHCARDS.md #fastapi #test-harness).

ADR references: ADR-015 (Supabase via get_supabase), ADR-024 (workspace isolation).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.deps import get_current_user_id
from app.api.routes.workspaces import assert_team_member
from app.api.schemas.mcp_server import (
    McpServerCreate,
    McpServerPatch,
    McpServerPublic,
    McpTestResultPublic,
)
from app.core.db import get_supabase, execute_async
from app.services import mcp_service  # MODULE LEVEL — do not move inside handlers

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/mcp-servers",
    tags=["mcp-servers"],
)

# Sentinel re-exported from mcp_service — passed to update_mcp_server when
# the caller does NOT include a "headers" key in the PATCH body (leave existing).
_HEADERS_UNSET = mcp_service._HEADERS_UNSET


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_team_id(workspace_id: str, supabase) -> str:
    """Resolve workspace_id to its slack_team_id.

    Returns the ``slack_team_id`` string for the workspace. Raises 404 if the
    workspace does not exist (existence-leak guard per ADR-024).

    Args:
        workspace_id: UUID of the workspace (path parameter, as string).
        supabase:     Supabase service-role client.

    Returns:
        The ``slack_team_id`` string for the workspace.

    Raises:
        HTTPException(404): Workspace not found.
    """
    result = await execute_async(
        supabase.table("teemo_workspaces")
        .select("slack_team_id")
        .eq("id", workspace_id)
        .limit(1)
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    team_id = result.data[0].get("slack_team_id")
    if not team_id:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return team_id


def _record_to_public(record) -> McpServerPublic:
    """Convert a McpServerRecord to the public response schema (no headers)."""
    return McpServerPublic(
        name=record.name,
        transport=record.transport,
        url=record.url,
        is_active=record.is_active,
        created_at=record.created_at,
    )


async def _assert_workspace_access(
    workspace_id: str, user_id: str, supabase
) -> str:
    """Resolve team_id from workspace_id and verify the user is a member.

    Composes the two-hop auth chain into a single coroutine so it can be
    awaited as one ``asyncio.Task`` and run concurrently with a data fetch
    on read endpoints.

    Returns the slack_team_id if access is granted; raises HTTPException
    (403 non-member, 404 unknown workspace) otherwise.
    """
    team_id = await _resolve_team_id(workspace_id, supabase)
    await assert_team_member(team_id, user_id)
    return team_id


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/mcp-servers
# ---------------------------------------------------------------------------


@router.get("", response_model=list[McpServerPublic])
async def list_mcp_servers(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase=Depends(get_supabase),
) -> list[McpServerPublic]:
    """List all MCP servers for a workspace (active and inactive).

    Returns the public shape — ``headers`` and ``headers_encrypted`` are NEVER
    included (schema-level guard in ``McpServerPublic``).

    Args:
        workspace_id: UUID of the workspace from the path.
        user_id:      Injected by ``get_current_user_id``; raises 401 if invalid.
        supabase:     Injected Supabase service-role client.

    Returns:
        List of ``McpServerPublic`` objects. May be empty.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(403): Caller is not a member of this workspace's team.
        HTTPException(404): Workspace not found.
    """
    # Run the 2-hop auth chain (resolve team_id → assert membership) in
    # parallel with the data fetch. Each Supabase round trip costs ~80ms
    # against self-hosted Kong+PostgREST; sequential = ~240ms, parallel ≈
    # ~160ms. The fetch result is only returned if auth succeeds — on
    # failure we cancel the fetch task so it doesn't waste a connection.
    auth_task = asyncio.create_task(
        _assert_workspace_access(workspace_id, user_id, supabase)
    )
    fetch_task = asyncio.create_task(
        mcp_service.list_mcp_servers(workspace_id, supabase=supabase)
    )
    try:
        await auth_task
    except BaseException:
        fetch_task.cancel()
        raise

    records = await fetch_task
    return [_record_to_public(r) for r in records]


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/mcp-servers
# ---------------------------------------------------------------------------


@router.post("", response_model=McpServerPublic, status_code=201)
async def create_mcp_server(
    workspace_id: str,
    body: McpServerCreate,
    user_id: str = Depends(get_current_user_id),
    supabase=Depends(get_supabase),
) -> McpServerPublic:
    """Create a new MCP server registration for a workspace.

    Validates all fields (slug, transport, HTTPS URL, headers), encrypts
    header values at rest, and inserts the row into ``teemo_mcp_servers``.

    Args:
        workspace_id: UUID of the workspace from the path.
        body:         Request body — name, transport, url, optional headers.
        user_id:      Injected by ``get_current_user_id``; raises 401 if invalid.
        supabase:     Injected Supabase service-role client.

    Returns:
        ``McpServerPublic`` for the newly created server, HTTP 201.

    Raises:
        HTTPException(400):  Validation failure (McpValidationError).
        HTTPException(401):  No or invalid auth token.
        HTTPException(403):  Caller is not a member of this workspace's team.
        HTTPException(404):  Workspace not found.
    """
    team_id = await _resolve_team_id(workspace_id, supabase)
    await assert_team_member(team_id, user_id)

    try:
        record = await mcp_service.create_mcp_server(
            workspace_id,
            name=body.name,
            transport=body.transport,
            url=body.url,
            headers=body.headers,
            supabase=supabase,
        )
    except mcp_service.McpValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _record_to_public(record)


# ---------------------------------------------------------------------------
# PATCH /api/workspaces/{workspace_id}/mcp-servers/{name}
# ---------------------------------------------------------------------------


@router.patch("/{name}", response_model=McpServerPublic)
async def update_mcp_server(
    workspace_id: str,
    name: str,
    body: McpServerPatch,
    user_id: str = Depends(get_current_user_id),
    supabase=Depends(get_supabase),
) -> McpServerPublic:
    """Partially update an MCP server registration.

    Only fields present in the request body are updated. Headers semantics:
    - ``headers`` key absent in body → leave existing headers unchanged.
    - ``headers={}`` → clear all stored headers.
    - ``headers={"Foo": "bar"}`` → replace headers with the new dict.

    Args:
        workspace_id: UUID of the workspace from the path.
        name:         Slug name of the server to update.
        body:         Partial update body (all fields optional).
        user_id:      Injected by ``get_current_user_id``; raises 401 if invalid.
        supabase:     Injected Supabase service-role client.

    Returns:
        ``McpServerPublic`` with the updated state, HTTP 200.

    Raises:
        HTTPException(400):  Validation failure (McpValidationError).
        HTTPException(401):  No or invalid auth token.
        HTTPException(403):  Caller is not a member of this workspace's team.
        HTTPException(404):  Workspace or server not found.
    """
    team_id = await _resolve_team_id(workspace_id, supabase)
    await assert_team_member(team_id, user_id)

    # Determine headers argument: use sentinel when headers key was not in body.
    # Pydantic sets headers=None when the key IS present with null value, but
    # McpServerPatch defaults headers to None — we need to distinguish "not sent"
    # from "sent as null". Use body.model_fields_set for clean detection.
    if "headers" in body.model_fields_set:
        headers_arg = body.headers if body.headers is not None else {}
    else:
        headers_arg = _HEADERS_UNSET

    try:
        record = await mcp_service.update_mcp_server(
            workspace_id,
            name,
            transport=body.transport,
            url=body.url,
            headers=headers_arg,
            is_active=body.is_active,
            supabase=supabase,
        )
    except mcp_service.McpValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return _record_to_public(record)


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/mcp-servers/{name}
# ---------------------------------------------------------------------------


@router.delete("/{name}", status_code=204)
async def delete_mcp_server(
    workspace_id: str,
    name: str,
    user_id: str = Depends(get_current_user_id),
    supabase=Depends(get_supabase),
) -> Response:
    """Remove an MCP server registration.

    Args:
        workspace_id: UUID of the workspace from the path.
        name:         Slug name of the server to delete.
        user_id:      Injected by ``get_current_user_id``; raises 401 if invalid.
        supabase:     Injected Supabase service-role client.

    Returns:
        HTTP 204 (empty body) on success.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(403): Caller is not a member of this workspace's team.
        HTTPException(404): Workspace not found (or server not found).
    """
    team_id = await _resolve_team_id(workspace_id, supabase)
    await assert_team_member(team_id, user_id)

    deleted = await mcp_service.delete_mcp_server(workspace_id, name, supabase=supabase)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"MCP server {name!r} not found.")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/mcp-servers/{name}/test
# ---------------------------------------------------------------------------


@router.post("/{name}/test", response_model=McpTestResultPublic)
async def test_mcp_server(
    workspace_id: str,
    name: str,
    user_id: str = Depends(get_current_user_id),
    supabase=Depends(get_supabase),
) -> McpTestResultPublic:
    """Run a connectivity test against a registered MCP server.

    Performs the MCP handshake + ``tools/list`` call. Asserts that at least
    one tool is returned (Q4 = handshake + ≥1 tool). 10-second timeout (Q2).

    HTTP status is ALWAYS 200 — even when ``ok=False``. This is intentional:
    the HTTP call succeeded at the transport layer; only the upstream MCP
    handshake or tools enumeration may have failed. Frontend reads ``body.ok``,
    NOT the HTTP status code, to display green/red.

    Header values are decrypted internally for the handshake — they are NEVER
    echoed in the response body.

    Args:
        workspace_id: UUID of the workspace from the path.
        name:         Slug name of the server to test.
        user_id:      Injected by ``get_current_user_id``; raises 401 if invalid.
        supabase:     Injected Supabase service-role client.

    Returns:
        ``McpTestResultPublic`` — always HTTP 200.
        ``{ok: true, tool_count: N, error: null}`` on success.
        ``{ok: false, tool_count: 0, error: "<message>"}`` on failure.

    Raises:
        HTTPException(401): No or invalid auth token.
        HTTPException(403): Caller is not a member of this workspace's team.
        HTTPException(404): Workspace not found.
    """
    team_id = await _resolve_team_id(workspace_id, supabase)
    await assert_team_member(team_id, user_id)

    result = await mcp_service.test_connection(workspace_id, name, supabase=supabase)
    return McpTestResultPublic(
        ok=result.ok,
        tool_count=result.tool_count,
        error=result.error,
    )
