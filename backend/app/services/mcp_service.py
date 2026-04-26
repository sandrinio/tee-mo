"""MCP Server Service — STORY-012-01 (EPIC-012 MCP Integration).

CRUD layer for ``teemo_mcp_servers``. Provides async functions consumed by:
  - STORY-012-02 (REST endpoints) — thin HTTP wrappers over this service.
  - STORY-012-03 (agent factory) — ``list_mcp_servers`` + ``_build_mcp_client``
    populate ``AgentDeps.mcp_servers`` before each agent run.

Security:
  - URL validation enforces HTTPS + private-IP blacklist via ``is_safe_url``.
  - Header values are encrypted per-value (NOT the whole dict) before storage
    via AES-256-GCM (``app.core.encryption``). This allows individual header
    values to be rotated without re-encrypting all others.
  - Plaintext header values are NEVER persisted; they are decrypted only when
    a service consumer explicitly needs them (agent factory — NOT list endpoints).

Validation:
  - Name: regex ``^[a-z0-9_-]{2,32}$``.
  - Name deny-list: first-party Tee-Mo agent tool names that would silently
    collide with registered MCP servers.
  - Transport: must be ``"sse"`` or ``"streamable_http"``.
  - URL: must start ``https://``; ``is_safe_url`` must return ok.
  - Headers: keys and values must be non-empty strings.

Raises:
  McpValidationError (subclass of ValueError) for all input-validation failures.
  postgrest.exceptions.APIError (re-raised) for DB uniqueness violations etc.

ADR compliance:
  - ADR-015: all DB access via injected Supabase service-role client.
  - ADR-020: self-hosted Supabase; RLS disabled; app-layer workspace isolation.
  - ADR-024: every query filters by workspace_id.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

import app.core.encryption as _encryption

from app.core.db import execute_async
from app.core.url_safety import is_safe_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Slug pattern for MCP server names.
_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{2,32}$")

#: Names that collide with first-party Tee-Mo agent tools.
#: Update this set whenever a new first-party tool is added (flashcard #mcp #agent).
_RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "search",
        "skill",
        "skills",
        "knowledge",
        "automation",
        "automations",
        "http_request",
    }
)

#: Sentinel object used by update_mcp_server to distinguish "headers not provided"
#: from "headers=None" and "headers={}".
_HEADERS_UNSET: object = object()

_VALID_TRANSPORTS: frozenset[str] = frozenset({"sse", "streamable_http"})


# ---------------------------------------------------------------------------
# Public data-transfer types
# ---------------------------------------------------------------------------


@dataclass
class McpServerRecord:
    """Row from ``teemo_mcp_servers`` returned by service functions.

    ``headers_encrypted`` holds raw ciphertext blobs — callers that need
    plaintext headers (e.g. the agent factory) must decrypt them via
    ``_build_mcp_client`` or call ``decrypt()`` directly.
    REST list endpoints must NEVER expose ``headers_encrypted`` to clients.
    """

    id: UUID
    workspace_id: UUID
    name: str
    transport: Literal["sse", "streamable_http"]
    url: str
    headers_encrypted: dict[str, str]  # {"Header-Name": "<base64-ciphertext>"}
    is_active: bool
    created_at: datetime


@dataclass
class McpTestResult:
    """Result of a ``test_connection`` call."""

    ok: bool
    tool_count: int
    error: str | None


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class McpValidationError(ValueError):
    """Raised when MCP server input fails validation.

    Subclasses ``ValueError`` so existing error-handling in the REST layer
    (which catches ``ValueError`` for 400 responses) works without changes.
    """


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_mcp_server_input(
    name: str,
    transport: str,
    url: str,
    headers: dict[str, str] | None = None,
) -> None:
    """Validate MCP server fields — raises McpValidationError on any failure.

    Args:
        name:      Server slug. Must match ``^[a-z0-9_-]{2,32}$`` and not be
                   in the reserved deny-list.
        transport: Must be ``"sse"`` or ``"streamable_http"``.
        url:       Must start with ``https://`` and resolve to a public IP.
        headers:   Optional dict of header name→value. Keys and values must be
                   non-empty strings.

    Raises:
        McpValidationError: Descriptive message indicates which field failed.
    """
    # --- name ---
    if not _NAME_PATTERN.match(name):
        raise McpValidationError(
            f"Invalid name {name!r}: must match ^[a-z0-9_-]{{2,32}}$. "
            "Use only lowercase letters, digits, underscores, and hyphens (2–32 chars)."
        )
    if name in _RESERVED_NAMES:
        raise McpValidationError(
            f"Name {name!r} is reserved — it collides with a first-party Tee-Mo agent "
            "tool. Choose a different name."
        )

    # --- transport ---
    if transport not in _VALID_TRANSPORTS:
        raise McpValidationError(
            f"Invalid transport {transport!r}: must be 'sse' or 'streamable_http'."
        )

    # --- url ---
    if not url.startswith("https://"):
        raise McpValidationError(
            f"Invalid URL {url!r}: https is required. HTTP URLs are not allowed."
        )
    url_ok, url_reason = is_safe_url(url)
    if not url_ok:
        raise McpValidationError(
            f"Unsafe URL {url!r}: {url_reason or 'private/internal network address'}."
        )

    # --- headers ---
    if headers is not None:
        for k, v in headers.items():
            if not k or not isinstance(k, str):
                raise McpValidationError("Header keys must be non-empty strings.")
            if not v or not isinstance(v, str):
                raise McpValidationError(
                    f"Header value for {k!r} must be a non-empty string."
                )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _row_to_record(row: dict[str, Any]) -> McpServerRecord:
    """Convert a Supabase DB row dict to a McpServerRecord dataclass."""
    return McpServerRecord(
        id=UUID(row["id"]),
        workspace_id=UUID(row["workspace_id"]),
        name=row["name"],
        transport=row["transport"],
        url=row["url"],
        headers_encrypted=row.get("headers_encrypted") or {},
        is_active=row["is_active"],
        created_at=row["created_at"],
    )


def _encrypt_headers(headers: dict[str, str]) -> dict[str, str]:
    """Encrypt each header value individually. Returns a new dict of ciphertexts."""
    return {k: _encryption.encrypt(v) for k, v in headers.items()}


def _decrypt_headers(headers_encrypted: dict[str, str]) -> dict[str, str]:
    """Decrypt each header ciphertext individually. Returns plaintext dict.

    Uses attribute lookup (``_encryption.decrypt``) rather than a name bound
    at import time so that ``monkeypatch.setattr('app.core.encryption.decrypt', …)``
    in tests is reflected here without module-reload side-effects.
    """
    return {k: _encryption.decrypt(v) for k, v in headers_encrypted.items()}


def _build_mcp_client(record: McpServerRecord) -> Any:
    """Instantiate the correct Pydantic AI MCP client for a server record.

    Header values are decrypted inline — the caller (agent factory) is
    responsible for entering the returned object as an async context manager
    before passing it to ``Agent(..., mcp_servers=...)``.

    Returns:
        ``MCPServerSSE`` or ``MCPServerStreamableHTTP`` depending on transport.

    Raises:
        ValueError: If ``record.transport`` is not a recognised transport
                    (should never happen for validated DB rows).
    """
    # Lazy import — pydantic_ai.mcp is available in .venv (verified Q1).
    from pydantic_ai.mcp import MCPServerSSE, MCPServerStreamableHTTP  # noqa: PLC0415

    headers = _decrypt_headers(record.headers_encrypted)

    if record.transport == "sse":
        return MCPServerSSE(url=record.url, headers=headers)
    elif record.transport == "streamable_http":
        return MCPServerStreamableHTTP(url=record.url, headers=headers)
    raise ValueError(f"Unknown MCP transport: {record.transport!r}")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_mcp_server(
    workspace_id: UUID | str,
    *,
    name: str,
    transport: str,
    url: str,
    headers: dict[str, str] | None = None,
    supabase: Any,
) -> McpServerRecord:
    """Create and persist a new MCP server registration.

    Validates all fields, encrypts header values, then inserts a row into
    ``teemo_mcp_servers``.

    Args:
        workspace_id: UUID of the owning workspace.
        name:         Server slug (validated against name rules).
        transport:    ``"sse"`` or ``"streamable_http"``.
        url:          HTTPS URL to the MCP server endpoint.
        headers:      Optional auth/custom headers. Values are encrypted at rest.
        supabase:     Supabase service-role client.

    Returns:
        McpServerRecord for the newly created row.

    Raises:
        McpValidationError: Any field fails validation.
        postgrest.exceptions.APIError: DB uniqueness constraint violation
            (duplicate name within workspace).
    """
    headers = headers or {}
    validate_mcp_server_input(name, transport, url, headers)

    payload = {
        "workspace_id": str(workspace_id),
        "name": name,
        "transport": transport,
        "url": url,
        "headers_encrypted": _encrypt_headers(headers),
        "is_active": True,
    }

    result = await execute_async(
        supabase.table("teemo_mcp_servers").insert(payload)
    )
    return _row_to_record(result.data[0])


async def list_mcp_servers(
    workspace_id: UUID | str,
    *,
    active_only: bool = False,
    supabase: Any,
) -> list[McpServerRecord]:
    """Return all MCP servers for a workspace (optionally only active ones).

    Headers are NOT decrypted here — callers that need plaintext headers
    (agent factory) should call ``_build_mcp_client(record)`` which decrypts
    inline. REST list endpoints use this function and strip ``headers_encrypted``
    from the response schema.

    Args:
        workspace_id: UUID of the workspace to query.
        active_only:  If True, only rows with ``is_active=True`` are returned.
        supabase:     Supabase service-role client.

    Returns:
        List of McpServerRecord (may be empty). Ordered by ``created_at`` ASC.
    """
    query = (
        supabase.table("teemo_mcp_servers")
        .select("*")
        .eq("workspace_id", str(workspace_id))
        .order("created_at", desc=False)
    )
    if active_only:
        query = query.eq("is_active", True)

    result = await execute_async(query)
    return [_row_to_record(row) for row in (result.data or [])]


async def get_mcp_server(
    workspace_id: UUID | str,
    name: str,
    *,
    supabase: Any,
) -> McpServerRecord | None:
    """Fetch a single MCP server by workspace + name.

    Args:
        workspace_id: UUID of the workspace.
        name:         Exact slug name of the server.
        supabase:     Supabase service-role client.

    Returns:
        McpServerRecord if found; None otherwise.
    """
    result = await execute_async(
        supabase.table("teemo_mcp_servers")
        .select("*")
        .eq("workspace_id", str(workspace_id))
        .eq("name", name)
    )
    if not result.data:
        return None
    return _row_to_record(result.data[0])


async def update_mcp_server(
    workspace_id: UUID | str,
    name: str,
    *,
    transport: str | None = None,
    url: str | None = None,
    headers: Any = _HEADERS_UNSET,
    is_active: bool | None = None,
    supabase: Any,
) -> McpServerRecord:
    """Partially update an MCP server registration.

    Only provided fields are updated. For ``headers``:
      - Not passing ``headers`` (default) means "leave existing headers unchanged".
      - ``headers={}`` means "clear all headers".
      - ``headers={"Foo": "bar"}`` means "replace headers with this new dict".

    Validation is run on the patched fields. If ``url`` changes, ``is_safe_url``
    is re-checked.

    Args:
        workspace_id: UUID of the workspace.
        name:         Current name of the server (used to locate the row).
        transport:    New transport if changing; None to leave unchanged.
        url:          New URL if changing; None to leave unchanged.
        headers:      New headers dict or empty dict; omit entirely to leave unchanged.
        is_active:    New active state if changing; None to leave unchanged.
        supabase:     Supabase service-role client.

    Returns:
        McpServerRecord with the updated state.

    Raises:
        McpValidationError: Any patched field fails validation.
        ValueError: Server not found in the workspace.
    """
    patch: dict[str, Any] = {}

    if transport is not None:
        if transport not in _VALID_TRANSPORTS:
            raise McpValidationError(
                f"Invalid transport {transport!r}: must be 'sse' or 'streamable_http'."
            )
        patch["transport"] = transport

    if url is not None:
        if not url.startswith("https://"):
            raise McpValidationError(
                f"Invalid URL {url!r}: https is required."
            )
        url_ok, url_reason = is_safe_url(url)
        if not url_ok:
            raise McpValidationError(
                f"Unsafe URL {url!r}: {url_reason or 'private/internal network address'}."
            )
        patch["url"] = url

    # Only update headers when the caller explicitly provided the argument.
    if headers is not _HEADERS_UNSET:
        h = headers if headers else {}
        for k, v in h.items():
            if not k or not isinstance(k, str):
                raise McpValidationError("Header keys must be non-empty strings.")
            if not v or not isinstance(v, str):
                raise McpValidationError(
                    f"Header value for {k!r} must be a non-empty string."
                )
        patch["headers_encrypted"] = _encrypt_headers(h)

    if is_active is not None:
        patch["is_active"] = is_active

    if not patch:
        # Nothing to update — return current state.
        record = await get_mcp_server(workspace_id, name, supabase=supabase)
        if record is None:
            raise ValueError(f"MCP server {name!r} not found in workspace {workspace_id}")
        return record

    result = await execute_async(
        supabase.table("teemo_mcp_servers")
        .update(patch)
        .eq("workspace_id", str(workspace_id))
        .eq("name", name)
    )
    if not result.data:
        raise ValueError(f"MCP server {name!r} not found in workspace {workspace_id}")
    return _row_to_record(result.data[0])


async def delete_mcp_server(
    workspace_id: UUID | str,
    name: str,
    *,
    supabase: Any,
) -> bool:
    """Delete an MCP server registration.

    Args:
        workspace_id: UUID of the workspace.
        name:         Slug name of the server to delete.
        supabase:     Supabase service-role client.

    Returns:
        True if a row was deleted; False if the server was not found.
    """
    result = await execute_async(
        supabase.table("teemo_mcp_servers")
        .delete()
        .eq("workspace_id", str(workspace_id))
        .eq("name", name)
    )
    return bool(result.data)


async def test_connection(
    workspace_id: UUID | str,
    name: str,
    *,
    timeout_seconds: float = 10.0,
    supabase: Any,
) -> McpTestResult:
    """Test connectivity to a registered MCP server.

    Performs:
    1. Looks up the server record.
    2. Instantiates the MCP client via ``_build_mcp_client``.
    3. Enters the async context (handshake).
    4. Calls ``client.list_tools()`` — asserts ≥1 tool returned.
    5. Exits the async context.

    The entire operation is bounded by ``timeout_seconds``.

    Args:
        workspace_id:    UUID of the workspace.
        name:            Slug name of the server to test.
        timeout_seconds: Seconds before timing out (default: 10).
        supabase:        Supabase service-role client.

    Returns:
        McpTestResult(ok=True, tool_count=N, error=None) on success.
        McpTestResult(ok=False, tool_count=0, error=<message>) on failure.
    """
    record = await get_mcp_server(workspace_id, name, supabase=supabase)
    if record is None:
        return McpTestResult(ok=False, tool_count=0, error=f"MCP server {name!r} not found")

    client = _build_mcp_client(record)

    async def _handshake() -> McpTestResult:
        async with client:
            tools = await client.list_tools()
            tool_count = len(tools)
            if tool_count == 0:
                return McpTestResult(ok=False, tool_count=0, error="no tools returned")
            return McpTestResult(ok=True, tool_count=tool_count, error=None)

    try:
        return await asyncio.wait_for(_handshake(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return McpTestResult(
            ok=False,
            tool_count=0,
            error=f"timeout after {timeout_seconds}s connecting to {record.url}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP test_connection failed for %r: %s", name, exc)
        return McpTestResult(ok=False, tool_count=0, error=str(exc))
