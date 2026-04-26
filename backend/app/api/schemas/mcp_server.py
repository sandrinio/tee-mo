"""Pydantic request/response schemas for MCP Server REST endpoints.

STORY-012-02 (EPIC-012 MCP Integration).

Security contract (hard rules):
- ``McpServerPublic`` intentionally does NOT include a ``headers`` or
  ``headers_encrypted`` field. This is the schema-level guard that prevents
  encrypted header values from leaking into any REST response — not a
  runtime filter. Adding those fields to this schema is the failure mode to
  prevent.
- ``McpTestResultPublic`` also never echoes auth header values.

IMPORTANT: Do NOT add ``from __future__ import annotations`` to this file.
FastAPI resolves type annotations at runtime for dependency injection and
response validation. Stringifying annotations (PEP 563) breaks this.
See FLASHCARDS.md #fastapi 2026-04-13 entry.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel


class McpServerCreate(BaseModel):
    """Request body for POST /mcp-servers — create a new MCP server registration.

    Attributes
    ----------
    name : str
        Server slug. Must match ``^[a-z0-9_-]{2,32}$`` and not be reserved.
        Validated server-side by ``mcp_service.validate_mcp_server_input``.
    transport : Literal["sse", "streamable_http"]
        MCP transport. Defaults to ``"streamable_http"`` (modern recommended).
    url : str
        HTTPS URL to the MCP server endpoint. ``http://`` URLs are rejected.
    headers : Optional[dict[str, str]]
        Optional HTTP headers (e.g. ``Authorization``) sent with every request.
        Values are encrypted at rest; they are NEVER returned in any response.
    """

    name: str
    transport: Literal["sse", "streamable_http"] = "streamable_http"
    url: str
    headers: Optional[dict[str, str]] = None


class McpServerPatch(BaseModel):
    """Request body for PATCH /mcp-servers/{name} — partial update.

    All fields are optional. Only keys present in the request body are updated.

    Notes
    -----
    ``headers={}`` clears all stored headers (write-only; values never returned).
    Omitting ``headers`` entirely leaves existing headers unchanged.
    """

    transport: Optional[Literal["sse", "streamable_http"]] = None
    url: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    is_active: Optional[bool] = None


class McpServerPublic(BaseModel):
    """Public response shape for a single MCP server.

    SECURITY: ``headers`` and ``headers_encrypted`` are intentionally absent.
    Auth header values are write-only over the API. Do NOT add them here.

    Attributes
    ----------
    name : str
        Server slug.
    transport : str
        ``"sse"`` or ``"streamable_http"``.
    url : str
        HTTPS URL of the server endpoint.
    is_active : bool
        Whether the server is currently enabled for agent use.
    created_at : datetime
        ISO-8601 creation timestamp.
    """

    name: str
    transport: Literal["sse", "streamable_http"]
    url: str
    is_active: bool
    created_at: datetime


class McpTestResultPublic(BaseModel):
    """Response shape for POST /mcp-servers/{name}/test.

    HTTP status is ALWAYS 200 (even on failure). Read ``ok`` to determine
    success — the HTTP call itself succeeded; only the MCP handshake may
    have failed.

    Attributes
    ----------
    ok : bool
        True if handshake + tools/list succeeded with at least 1 tool.
    tool_count : int
        Number of tools discovered. 0 on failure.
    error : Optional[str]
        Human-readable error message when ``ok=False``. Null on success.
    """

    ok: bool
    tool_count: int
    error: Optional[str] = None
