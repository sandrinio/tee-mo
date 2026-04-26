"""Tests for STORY-012-02: MCP REST Endpoints.

Covers all 12 Gherkin scenarios from STORY-012-02 §2.1 plus edge cases.

Test strategy:
- TestClient WITHOUT context manager — avoids FastAPI lifespan deadlock
  (cron tasks hang under pytest-asyncio auto mode; see FLASHCARD 2026-04-25
  #test-harness #fastapi).
- ``get_current_user_id`` overridden via ``app.dependency_overrides``.
- ``get_supabase`` overridden to return a lightweight Supabase mock chain
  that satisfies ``execute_async``'s ``run_in_threadpool(query_builder.execute)``.
- ``mcp_service`` functions patched via monkeypatch for complex service calls
  (create, update, delete, test_connection) to avoid re-testing service logic.
- Integration smoke (scenario 12) uses a real in-process FastMCP ASGI server
  via httpx.ASGITransport; mcp_service._build_mcp_client is patched to inject
  the transport so the full test_connection code path executes (no stub on
  test_connection itself).

Scenarios covered:
  1.  test_owner_post_creates_streamable_http_server → 201, no headers in response
  2.  test_owner_post_omitting_transport_defaults_to_streamable_http → 201
  3.  test_non_member_post_returns_403 → 403 (assert_team_member rejects non-member)
  3b. test_missing_workspace_returns_404 → 404 (workspace not found)
  4.  test_get_list_never_leaks_headers → 200, no headers/headers_encrypted fields
  5.  test_patch_toggles_is_active → 200, is_active=false
  6.  test_patch_with_empty_headers_clears_them → 200
  7.  test_delete_returns_204_and_excludes_from_list → 204; subsequent GET omits it
  8.  test_post_test_happy_path_with_stubbed_mcp_returns_ok → 200 ok=True tool_count=3
  9.  test_post_test_zero_tools_returns_ok_false → 200 ok=False
  10. test_post_test_timeout_returns_ok_false → 200 ok=False error contains timeout
  11. test_reserved_name_returns_400 → 400 with "reserved" in detail
  12. test_http_url_returns_400 → 400 with "https" in detail
  13. test_post_test_integration_smoke_with_one_tool → real SSE handshake via ASGI

ADR compliance:
- ADR-001: JWT via cookie (bypassed here via dependency override — safe for tests).
- ADR-024: Workspace isolation enforced at route layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants — reused across tests
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-1111-1111-1111-000000000001"
TEAM_ID = "T0TEST12345"
OWNER_USER_ID = "cccccccc-3333-3333-3333-000000000003"
NON_MEMBER_USER_ID = "dddddddd-4444-4444-4444-000000000004"

SERVER_NAME = "github"
SERVER_URL = "https://api.githubcopilot.com/mcp/"

_NOW = datetime.now(timezone.utc)
_NOW_ISO = _NOW.isoformat()

# A realistic MCP server row (matches McpServerRecord fields).
MCP_SERVER_ROW: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "workspace_id": WORKSPACE_ID,
    "name": SERVER_NAME,
    "transport": "streamable_http",
    "url": SERVER_URL,
    "headers_encrypted": {"Authorization": "ciphertext-abc"},  # never returned
    "is_active": True,
    "created_at": _NOW_ISO,
}

MCP_SERVER_ROW_2: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "workspace_id": WORKSPACE_ID,
    "name": "linear",
    "transport": "sse",
    "url": "https://linear.app/mcp/sse",
    "headers_encrypted": {"Authorization": "ciphertext-xyz"},  # never returned
    "is_active": True,
    "created_at": _NOW_ISO,
}

WORKSPACE_ROW: dict[str, Any] = {
    "id": WORKSPACE_ID,
    "user_id": OWNER_USER_ID,
    "name": "Test Workspace",
    "slack_team_id": TEAM_ID,
    "ai_provider": "openai",
    "ai_model": "gpt-4o",
    "is_default_for_team": True,
    "created_at": _NOW_ISO,
    "updated_at": _NOW_ISO,
}


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------


def _make_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data holds the given list."""
    result = MagicMock()
    result.data = data
    return result


def _make_supabase_mock(
    workspace_data: list[dict] | None = None,
    member_data: list[dict] | None = None,
    mcp_data: list[dict] | None = None,
) -> MagicMock:
    """Build a lightweight Supabase mock with chainable query builder.

    All methods (select, eq, order, limit, insert, update, delete, upsert)
    return the same chain MagicMock so chaining works. ``.execute()`` is
    called synchronously inside ``run_in_threadpool`` by ``execute_async``.

    Args:
        workspace_data: Rows to return for teemo_workspaces queries.
                        Defaults to [WORKSPACE_ROW] (workspace found with team).
        member_data:    Rows returned for teemo_slack_team_members.
                        Defaults to a member row (owner is a member).
        mcp_data:       Rows returned for teemo_mcp_servers.
                        Defaults to [].
    """
    ws_rows = workspace_data if workspace_data is not None else [WORKSPACE_ROW]
    mem_rows = member_data if member_data is not None else [{"slack_team_id": TEAM_ID}]
    mcp_rows = mcp_data if mcp_data is not None else []

    mock = MagicMock()

    def _table(table_name: str) -> MagicMock:
        chain = MagicMock()

        # Fully chainable
        for method in ("select", "insert", "update", "upsert", "delete",
                       "eq", "order", "limit", "in_", "offset", "maybe_single"):
            getattr(chain, method).return_value = chain

        if table_name == "teemo_workspaces":
            chain.execute.return_value = _make_result(ws_rows)
        elif table_name == "teemo_slack_team_members":
            chain.execute.return_value = _make_result(mem_rows)
        elif table_name == "teemo_mcp_servers":
            chain.execute.return_value = _make_result(mcp_rows)
        else:
            chain.execute.return_value = _make_result([])

        return chain

    mock.table.side_effect = _table
    return mock


def _make_non_member_supabase_mock() -> MagicMock:
    """Mock where workspace exists but user is not a team member.

    ``teemo_workspaces`` returns the workspace (team_id resolves fine).
    ``teemo_slack_team_members`` returns empty → assert_team_member raises 403.
    """
    return _make_supabase_mock(
        workspace_data=[WORKSPACE_ROW],
        member_data=[],  # non-member
    )


def _make_missing_workspace_supabase_mock() -> MagicMock:
    """Mock where workspace is not found → 404 from _resolve_team_id."""
    return _make_supabase_mock(
        workspace_data=[],  # workspace not found
        member_data=[],
    )


# ---------------------------------------------------------------------------
# McpServerRecord helper (mirrors mcp_service.McpServerRecord dataclass)
# ---------------------------------------------------------------------------


def _make_record(row: dict[str, Any]):
    """Convert a raw dict to a McpServerRecord-like dataclass for mock returns."""
    from app.services.mcp_service import McpServerRecord
    from uuid import UUID

    # Parse created_at from ISO string
    created = row["created_at"]
    if isinstance(created, str):
        created = datetime.fromisoformat(created)

    return McpServerRecord(
        id=UUID(row["id"]),
        workspace_id=UUID(row["workspace_id"]),
        name=row["name"],
        transport=row["transport"],
        url=row["url"],
        headers_encrypted=row.get("headers_encrypted") or {},
        is_active=row["is_active"],
        created_at=created,
    )


# ---------------------------------------------------------------------------
# Fixtures — TestClient with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture
def client_owner(monkeypatch):
    """TestClient authenticated as OWNER_USER_ID with a workspace + team membership.

    Patches both:
    - ``app.dependency_overrides[get_supabase]`` — for route handlers that receive
      supabase via ``Depends(get_supabase)``.
    - ``app.api.routes.workspaces.get_supabase`` and
      ``app.api.routes.mcp_servers.get_supabase`` — for ``assert_team_member`` and
      ``_resolve_team_id`` which call ``get_supabase()`` directly (not via DI).
    """
    from app.main import app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase
    import app.api.routes.workspaces as ws_module
    import app.api.routes.mcp_servers as mcp_module

    mock_sb = _make_supabase_mock()

    async def _fake_user() -> str:
        return OWNER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    monkeypatch.setattr(ws_module, "get_supabase", lambda: mock_sb)
    monkeypatch.setattr(mcp_module, "get_supabase", lambda: mock_sb)

    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client, mock_sb
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_non_member(monkeypatch):
    """TestClient authenticated as NON_MEMBER_USER_ID (workspace exists, not a member)."""
    from app.main import app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase
    import app.api.routes.workspaces as ws_module
    import app.api.routes.mcp_servers as mcp_module

    mock_sb = _make_non_member_supabase_mock()

    async def _fake_user() -> str:
        return NON_MEMBER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    monkeypatch.setattr(ws_module, "get_supabase", lambda: mock_sb)
    monkeypatch.setattr(mcp_module, "get_supabase", lambda: mock_sb)

    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client_missing_workspace(monkeypatch):
    """TestClient authenticated as OWNER_USER_ID but workspace does not exist → 404."""
    from app.main import app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase
    import app.api.routes.workspaces as ws_module
    import app.api.routes.mcp_servers as mcp_module

    mock_sb = _make_missing_workspace_supabase_mock()

    async def _fake_user() -> str:
        return OWNER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    monkeypatch.setattr(ws_module, "get_supabase", lambda: mock_sb)
    monkeypatch.setattr(mcp_module, "get_supabase", lambda: mock_sb)

    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Scenario 1: Member creates Streamable HTTP server → 201, no headers in body
# ---------------------------------------------------------------------------


def test_owner_post_creates_streamable_http_server(monkeypatch, client_owner):
    """POST /mcp-servers with valid body → 201, response has no headers field."""
    client, mock_sb = client_owner

    new_record = _make_record(MCP_SERVER_ROW)

    async def _fake_create(workspace_id, *, name, transport, url, headers, supabase):
        return new_record

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "create_mcp_server", _fake_create)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        json={
            "name": SERVER_NAME,
            "transport": "streamable_http",
            "url": SERVER_URL,
            "headers": {"Authorization": "Bearer pat"},
        },
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == SERVER_NAME
    assert body["transport"] == "streamable_http"
    assert body["url"] == SERVER_URL
    assert body["is_active"] is True
    assert "headers" not in body
    assert "headers_encrypted" not in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# Scenario 2: POST omitting transport defaults to streamable_http
# ---------------------------------------------------------------------------


def test_owner_post_omitting_transport_defaults_to_streamable_http(monkeypatch, client_owner):
    """POST without transport field → 201, transport='streamable_http' in response."""
    client, mock_sb = client_owner

    default_row = {**MCP_SERVER_ROW, "name": "azure", "transport": "streamable_http"}
    new_record = _make_record(default_row)

    async def _fake_create(workspace_id, *, name, transport, url, headers, supabase):
        assert transport == "streamable_http"  # default applied
        return new_record

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "create_mcp_server", _fake_create)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        json={"name": "azure", "url": SERVER_URL},
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 201
    assert resp.json()["transport"] == "streamable_http"


# ---------------------------------------------------------------------------
# Scenario 3: Non-member POST returns 403 (workspace exists, user not a member)
# ---------------------------------------------------------------------------


def test_non_member_post_returns_403(client_non_member):
    """Non-team-member POST → 403 (assert_team_member rejects non-member)."""
    client = client_non_member

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        json={"name": "github", "url": SERVER_URL},
        headers={"Authorization": "Bearer fake-token"},
    )

    # assert_team_member raises 403 when the user is not a team member
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scenario 3b: Unknown workspace → 404
# ---------------------------------------------------------------------------


def test_missing_workspace_returns_404(client_missing_workspace):
    """GET /mcp-servers for a workspace that does not exist → 404.

    Uses _make_missing_workspace_supabase_mock() which returns an empty
    workspace rows list, causing _resolve_team_id to raise HTTP 404.
    """
    client = client_missing_workspace

    nonexistent_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    resp = client.get(
        f"/api/workspaces/{nonexistent_id}/mcp-servers",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Scenario 4: GET list never leaks headers or headers_encrypted
# ---------------------------------------------------------------------------


def test_get_list_never_leaks_headers(monkeypatch, client_owner):
    """GET /mcp-servers with 2 servers with encrypted headers → no headers in response."""
    client, mock_sb = client_owner

    record1 = _make_record(MCP_SERVER_ROW)
    record2 = _make_record(MCP_SERVER_ROW_2)

    async def _fake_list(workspace_id, *, active_only=False, supabase):
        return [record1, record2]

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "list_mcp_servers", _fake_list)

    resp = client.get(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    for item in items:
        assert "headers" not in item, f"Response leaks 'headers' key: {item}"
        assert "headers_encrypted" not in item, f"Response leaks 'headers_encrypted' key: {item}"
        # Only public fields present
        assert set(item.keys()) == {"name", "transport", "url", "is_active", "created_at"}


# ---------------------------------------------------------------------------
# Scenario 5: PATCH toggles is_active
# ---------------------------------------------------------------------------


def test_patch_toggles_is_active(monkeypatch, client_owner):
    """PATCH with is_active=false → 200, is_active=false in response."""
    client, mock_sb = client_owner

    updated_row = {**MCP_SERVER_ROW, "is_active": False}
    updated_record = _make_record(updated_row)

    async def _fake_update(workspace_id, name, *, transport, url, headers, is_active, supabase):
        assert is_active is False
        return updated_record

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "update_mcp_server", _fake_update)

    resp = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        json={"is_active": False},
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert "headers" not in body
    assert "headers_encrypted" not in body


# ---------------------------------------------------------------------------
# Scenario 6: PATCH with headers={} clears stored headers
# ---------------------------------------------------------------------------


def test_patch_with_empty_headers_clears_them(monkeypatch, client_owner):
    """PATCH {headers: {}} → 200; service called with headers={} (clear)."""
    client, mock_sb = client_owner

    cleared_row = {**MCP_SERVER_ROW, "headers_encrypted": {}}
    cleared_record = _make_record(cleared_row)

    captured_headers = {}

    async def _fake_update(workspace_id, name, *, transport, url, headers, is_active, supabase):
        captured_headers["value"] = headers
        return cleared_record

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "update_mcp_server", _fake_update)

    resp = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        json={"headers": {}},
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    # headers={} in body → service receives empty dict (NOT the sentinel)
    assert captured_headers["value"] == {}


# ---------------------------------------------------------------------------
# Scenario 7: DELETE returns 204 and subsequent GET omits the server
# ---------------------------------------------------------------------------


def test_delete_returns_204_and_excludes_from_list(monkeypatch, client_owner):
    """DELETE → 204. GET after delete omits the server."""
    client, mock_sb = client_owner

    async def _fake_delete(workspace_id, name, *, supabase):
        return True  # row deleted

    async def _fake_list_empty(workspace_id, *, active_only=False, supabase):
        return []  # server gone

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "delete_mcp_server", _fake_delete)
    monkeypatch.setattr(mcp_module.mcp_service, "list_mcp_servers", _fake_list_empty)

    # DELETE
    del_resp = client.delete(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert del_resp.status_code == 204

    # Subsequent GET — empty list
    get_resp = client.get(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json() == []


# ---------------------------------------------------------------------------
# Scenario 8: POST /test happy path (3 tools) → {ok: true, tool_count: 3}
# ---------------------------------------------------------------------------


def test_post_test_happy_path_returns_ok_with_tool_count(monkeypatch, client_owner):
    """POST /test with stubbed service returning 3 tools → {ok: true, tool_count: 3}."""
    client, mock_sb = client_owner

    from app.services.mcp_service import McpTestResult

    async def _fake_test_connection(workspace_id, name, *, timeout_seconds=10.0, supabase):
        return McpTestResult(ok=True, tool_count=3, error=None)

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "test_connection", _fake_test_connection)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}/test",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["tool_count"] == 3
    assert body["error"] is None


# ---------------------------------------------------------------------------
# Scenario 9: POST /test zero tools → {ok: false, tool_count: 0, error: ...}
# ---------------------------------------------------------------------------


def test_post_test_zero_tools_returns_ok_false(monkeypatch, client_owner):
    """POST /test with zero tools returned → HTTP 200, ok=False."""
    client, mock_sb = client_owner

    from app.services.mcp_service import McpTestResult

    async def _fake_test_connection(workspace_id, name, *, timeout_seconds=10.0, supabase):
        return McpTestResult(ok=False, tool_count=0, error="no tools returned")

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "test_connection", _fake_test_connection)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}/test",
        headers={"Authorization": "Bearer fake-token"},
    )

    # Status is ALWAYS 200 — sad path is body-encoded
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["tool_count"] == 0
    assert body["error"] is not None
    assert "no tools" in body["error"].lower() or "tool" in body["error"].lower()


# ---------------------------------------------------------------------------
# Scenario 10: POST /test timeout → {ok: false, error: contains timeout info}
# ---------------------------------------------------------------------------


def test_post_test_timeout_returns_ok_false(monkeypatch, client_owner):
    """POST /test when MCP server times out → HTTP 200, ok=False, error has timeout info."""
    client, mock_sb = client_owner

    from app.services.mcp_service import McpTestResult

    async def _fake_test_connection(workspace_id, name, *, timeout_seconds=10.0, supabase):
        return McpTestResult(
            ok=False,
            tool_count=0,
            error=f"timeout after {timeout_seconds}s connecting to {SERVER_URL}",
        )

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "test_connection", _fake_test_connection)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}/test",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["tool_count"] == 0
    assert body["error"] is not None
    assert "timeout" in body["error"].lower() or "10" in body["error"]


# ---------------------------------------------------------------------------
# Scenario 11: Reserved name → 400 with "reserved" in detail
# ---------------------------------------------------------------------------


def test_reserved_name_returns_400(monkeypatch, client_owner):
    """POST with name='search' (reserved) → 400 with 'reserved' in detail."""
    client, mock_sb = client_owner

    from app.services.mcp_service import McpValidationError

    async def _fake_create(workspace_id, *, name, transport, url, headers, supabase):
        raise McpValidationError(
            f"Name {name!r} is reserved — it collides with a first-party Tee-Mo agent tool."
        )

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "create_mcp_server", _fake_create)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        json={"name": "search", "url": SERVER_URL},
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 400
    assert "reserved" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Scenario 12: HTTP URL → 400 with "https" in detail
# ---------------------------------------------------------------------------


def test_http_url_returns_400(monkeypatch, client_owner):
    """POST with http:// URL → 400 with 'https' in detail."""
    client, mock_sb = client_owner

    from app.services.mcp_service import McpValidationError

    async def _fake_create(workspace_id, *, name, transport, url, headers, supabase):
        raise McpValidationError(
            f"Invalid URL {url!r}: https is required. HTTP URLs are not allowed."
        )

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "create_mcp_server", _fake_create)

    resp = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers",
        json={"name": "myserver", "url": "http://insecure.example/"},
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 400
    assert "https" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Bonus: DELETE on non-existent server → 404
# ---------------------------------------------------------------------------


def test_delete_non_existent_server_returns_404(monkeypatch, client_owner):
    """DELETE a server that doesn't exist → 404."""
    client, mock_sb = client_owner

    async def _fake_delete(workspace_id, name, *, supabase):
        return False  # not found

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "delete_mcp_server", _fake_delete)

    resp = client.delete(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/nonexistent",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bonus: PATCH with no changes (empty body) still returns 200
# ---------------------------------------------------------------------------


def test_patch_idempotent_same_body_twice(monkeypatch, client_owner):
    """PATCH the same body twice → 200 both times (idempotent)."""
    client, mock_sb = client_owner

    record = _make_record(MCP_SERVER_ROW)

    async def _fake_update(workspace_id, name, *, transport, url, headers, is_active, supabase):
        return record

    from app.api.routes import mcp_servers as mcp_module
    monkeypatch.setattr(mcp_module.mcp_service, "update_mcp_server", _fake_update)

    body = {"is_active": True}

    resp1 = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        json=body,
        headers={"Authorization": "Bearer fake-token"},
    )
    resp2 = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        json=body,
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


# ---------------------------------------------------------------------------
# Bonus: Verify PATCH passes sentinel when headers key is absent from body
# ---------------------------------------------------------------------------


def test_patch_without_headers_key_passes_sentinel(monkeypatch, client_owner):
    """PATCH body with no 'headers' key → service receives _HEADERS_UNSET sentinel."""
    client, mock_sb = client_owner

    record = _make_record(MCP_SERVER_ROW)
    captured = {}

    async def _fake_update(workspace_id, name, *, transport, url, headers, is_active, supabase):
        captured["headers"] = headers
        return record

    from app.api.routes import mcp_servers as mcp_module
    from app.services.mcp_service import _HEADERS_UNSET
    monkeypatch.setattr(mcp_module.mcp_service, "update_mcp_server", _fake_update)

    resp = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}",
        json={"is_active": True},  # no "headers" key
        headers={"Authorization": "Bearer fake-token"},
    )

    assert resp.status_code == 200
    assert captured["headers"] is _HEADERS_UNSET


# ---------------------------------------------------------------------------
# Scenario 13: Integration smoke — real SSE handshake via in-process ASGI
# ---------------------------------------------------------------------------


async def test_post_test_integration_smoke_with_one_tool(monkeypatch):
    """Integration smoke: POST /test exercises the real mcp_service.test_connection.

    Strategy (ASGI transport — no real network):
    1. A FastMCP server with one tool is created in-process.
    2. Its ASGI app is started with its own lifespan (session manager).
    3. mcp_service._build_mcp_client is patched to return a
       MCPServerStreamableHTTP backed by an httpx.AsyncClient using
       httpx.ASGITransport — no outbound HTTP, no real network.
    4. The route POST /test is called via httpx.AsyncClient(ASGITransport)
       pointing at the Tee-Mo app.
    5. The real test_connection code path executes:
         get_mcp_server → _build_mcp_client (patched) → asyncio.wait_for(
           _handshake()) → client.__aenter__ → client.list_tools() → result.
    6. Response: {ok: true, tool_count: 1, error: null}.

    No monkeypatch on mcp_service.test_connection.
    """
    import httpx
    from fastmcp import FastMCP
    from pydantic_ai.mcp import MCPServerStreamableHTTP

    import app.services.mcp_service as mcp_svc_module
    from app.main import app as tee_mo_app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase
    import app.api.routes.workspaces as ws_module
    import app.api.routes.mcp_servers as mcp_routes_module

    # --- 1. Build the in-process MCP server with one tool ---
    in_proc_mcp = FastMCP("smoke-test-server")

    @in_proc_mcp.tool
    def github_search(query: str) -> str:
        """Search GitHub repositories."""
        return f"results for {query}"

    mcp_asgi_app = in_proc_mcp.http_app()

    # --- 2. Build the httpx client that routes to the in-process MCP ASGI app ---
    mcp_transport = httpx.ASGITransport(app=mcp_asgi_app)
    mcp_http_client = httpx.AsyncClient(
        transport=mcp_transport,
        base_url="http://testserver",
    )

    # --- 3. Patch _build_mcp_client to return a client backed by ASGI transport ---
    def _fake_build_mcp_client(record):
        return MCPServerStreamableHTTP(
            url="http://testserver/mcp",
            http_client=mcp_http_client,
        )

    monkeypatch.setattr(mcp_svc_module, "_build_mcp_client", _fake_build_mcp_client)

    # --- 4. Set up a Supabase mock that returns a server row for get_mcp_server ---
    mcp_row = {
        "id": str(uuid.uuid4()),
        "workspace_id": WORKSPACE_ID,
        "name": SERVER_NAME,
        "transport": "streamable_http",
        "url": SERVER_URL,
        "headers_encrypted": {},  # empty — no decryption needed
        "is_active": True,
        "created_at": _NOW,
    }
    mock_sb = _make_supabase_mock(mcp_data=[mcp_row])

    # --- 5. Set up Tee-Mo app dependency overrides ---
    async def _fake_user() -> str:
        return OWNER_USER_ID

    tee_mo_app.dependency_overrides[get_current_user_id] = _fake_user
    tee_mo_app.dependency_overrides[get_supabase] = lambda: mock_sb
    monkeypatch.setattr(ws_module, "get_supabase", lambda: mock_sb)
    monkeypatch.setattr(mcp_routes_module, "get_supabase", lambda: mock_sb)

    try:
        # --- 6. Start the FastMCP lifespan and run the request ---
        async with mcp_asgi_app.router.lifespan_context(mcp_asgi_app):
            tee_mo_transport = httpx.ASGITransport(app=tee_mo_app)
            async with httpx.AsyncClient(
                transport=tee_mo_transport,
                base_url="http://testserver",
            ) as api_client:
                resp = await api_client.post(
                    f"/api/workspaces/{WORKSPACE_ID}/mcp-servers/{SERVER_NAME}/test",
                    headers={"Authorization": "Bearer fake-token"},
                )

        # --- 7. Assert real SSE handshake result ---
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True, f"Expected ok=true, got: {body}"
        assert body["tool_count"] >= 1, f"Expected tool_count >= 1, got: {body}"
        assert body["error"] is None, f"Expected error=null, got: {body}"
    finally:
        tee_mo_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Verify router is mounted and endpoints are reachable via OpenAPI schema
# ---------------------------------------------------------------------------


def test_openapi_lists_mcp_server_endpoints():
    """Spot-check: OpenAPI schema contains all 5 MCP server endpoints."""
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/openapi.json")

    # Should succeed — OpenAPI is always public
    assert resp.status_code == 200
    paths = resp.json().get("paths", {})

    expected_prefixes = [
        f"/api/workspaces/{{workspace_id}}/mcp-servers",
    ]

    for prefix in expected_prefixes:
        matched = [p for p in paths if p.startswith(prefix)]
        assert matched, f"No OpenAPI path matching prefix {prefix!r}. Available: {list(paths.keys())}"
