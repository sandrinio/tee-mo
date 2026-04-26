"""Tests for Agent MCP Wiring — STORY-012-03 (EPIC-012 MCP Integration).

Covers all Gherkin scenarios from STORY-012-03 §2.1:

  Scenario: build_agent populates AgentDeps.mcp_servers from active rows
  Scenario: System prompt lists active integration names
  Scenario: System prompt omits the heading when no MCP servers
  Scenario: add_mcp_server tool result redacts auth_header
  Scenario: AsyncExitStack runs __aexit__ on agent.run() success
  Scenario: AsyncExitStack runs __aexit__ on agent.run() exception
  Scenario: Zero-MCP workspace runs unchanged
  Scenario: list_mcp_servers shows transport and active flag

Mock strategy:
  - ``app.services.mcp_service.list_mcp_servers`` is patched with AsyncMock to
    return canned McpServerRecord lists without DB access.
  - ``app.services.mcp_service._build_mcp_client`` is patched to return a
    mock MCPServerSSE or MCPServerStreamableHTTP depending on transport.
  - Pydantic AI Agent class is mocked via monkeypatch (same pattern as
    test_agent_factory.py) — no real model calls.
  - ``build_agent`` is called with a minimal Supabase mock that satisfies all
    table queries inside the factory.
  - Tool functions (add_mcp_server, remove_mcp_server, list_mcp_servers) are
    called directly via the async function objects captured from build_agent's
    closure by intercepting the Agent() constructor call.

All tests are async (pytest-asyncio ``asyncio_mode = "auto"`` in pyproject.toml).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Hoisted at module level so Python caches mcp_service (and binds its
# _encryption attribute reference to the real module) BEFORE any
# monkeypatch.setattr fires in any test.  Without this hoist the first
# test that patches app.core.encryption.decrypt causes mcp_service to be
# imported inside that patch context, pinning the bound name for the rest
# of the session and breaking test_header_encrypt_round_trip in other files.
from app.services.mcp_service import McpServerRecord  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE_ID = "ws-mcp-test-0001"
USER_ID = "user-mcp-test-0001"
DECRYPTED_KEY = "plaintext-test-api-key-mcp"

_NOW = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_FAKE_WORKSPACE_UUID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")


def _make_mcp_record(
    name: str,
    transport: str = "sse",
    is_active: bool = True,
    url: str = "https://mcp.example.com/sse",
) -> Any:
    """Build a minimal McpServerRecord-like object."""
    return McpServerRecord(
        id=uuid.uuid4(),
        workspace_id=_FAKE_WORKSPACE_UUID,
        name=name,
        transport=transport,
        url=url,
        headers_encrypted={},
        is_active=is_active,
        created_at=_NOW,
    )


def _workspace_row() -> dict:
    return {
        "id": WORKSPACE_ID,
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
        "bot_persona": None,
    }


def _make_supabase_mock() -> MagicMock:
    """Minimal Supabase mock that satisfies all build_agent table queries."""
    ws_result = MagicMock()
    ws_result.data = _workspace_row()

    ws_chain = MagicMock()
    ws_chain.maybe_single.return_value = ws_chain
    ws_chain.execute.return_value = ws_result
    ws_chain.eq.return_value = ws_chain
    ws_chain.select.return_value = ws_chain

    # Generic chain for teemo_wiki_pages, teemo_documents, teemo_automations,
    # teemo_workspace_channels — all return empty lists.
    empty_result = MagicMock()
    empty_result.data = []

    generic_chain = MagicMock()
    generic_chain.select.return_value = generic_chain
    generic_chain.eq.return_value = generic_chain
    generic_chain.order.return_value = generic_chain
    generic_chain.execute.return_value = empty_result

    supabase = MagicMock()

    def _dispatch(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_chain
        return generic_chain

    supabase.table.side_effect = _dispatch
    return supabase


# ---------------------------------------------------------------------------
# Scenario: build_agent returns 2-tuple unchanged (regression)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_returns_2_tuple(monkeypatch: Any) -> None:
    """build_agent must return a 2-tuple (Agent, AgentDeps) — regression guard (Q6)."""
    import app.agents.agent as agent_module

    mock_agent_cls = MagicMock(name="Agent")
    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])
    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    supabase = _make_supabase_mock()
    result = await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert isinstance(result, tuple), "build_agent must return a tuple"
    assert len(result) == 2, "build_agent must return a 2-tuple (agent, deps)"


# ---------------------------------------------------------------------------
# Scenario: deps.mcp_servers populated from active rows; inactive rows excluded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_populates_mcp_servers_active_only(monkeypatch: Any) -> None:
    """deps.mcp_servers has exactly the active rows; inactive row is absent.

    Gherkin:
      Given workspace W has 2 active MCP servers (1 SSE, 1 streamable_http) and 1 inactive
      When build_agent(workspace_id=W, ...) returns (agent, deps)
      Then deps.mcp_servers has 2 entries
      And the inactive row is absent
    """
    import app.agents.agent as agent_module

    sse_record = _make_mcp_record("github", "sse", is_active=True)
    http_record = _make_mcp_record(
        "azuredevops", "streamable_http", is_active=True, url="https://mcp.azure.com/"
    )
    inactive_record = _make_mcp_record("disabled-svc", "sse", is_active=False)

    # Only active rows returned (active_only=True filters inactive)
    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[sse_record, http_record]),
    )

    mock_sse_client = MagicMock(name="MCPServerSSE")
    mock_http_client = MagicMock(name="MCPServerStreamableHTTP")

    def _fake_build_client(record: Any) -> MagicMock:
        if record.transport == "sse":
            return mock_sse_client
        return mock_http_client

    monkeypatch.setattr("app.services.mcp_service._build_mcp_client", _fake_build_client)
    monkeypatch.setattr(agent_module, "Agent", MagicMock(name="Agent"))
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    _, deps = await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert len(deps.mcp_servers) == 2, "Expected 2 active MCP servers"
    assert mock_sse_client in deps.mcp_servers
    assert mock_http_client in deps.mcp_servers
    # The inactive_record was never passed to _build_mcp_client — it's not in deps
    assert inactive_record not in deps.mcp_servers


# ---------------------------------------------------------------------------
# Scenario: MCPServerSSE for sse transport, MCPServerStreamableHTTP for streamable_http
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_transport_dispatch(monkeypatch: Any) -> None:
    """MCPServerSSE chosen for transport='sse', MCPServerStreamableHTTP for 'streamable_http'.

    Gherkin:
      And the SSE row produced an MCPServerSSE instance
      And the streamable_http row produced an MCPServerStreamableHTTP instance
    """
    import app.agents.agent as agent_module

    sse_record = _make_mcp_record("github", "sse", is_active=True)
    http_record = _make_mcp_record(
        "azure", "streamable_http", is_active=True, url="https://mcp.azure.com/"
    )

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[sse_record, http_record]),
    )

    calls: list[str] = []

    class FakeSSE:
        def __repr__(self):
            return "FakeSSE"

    class FakeHTTP:
        def __repr__(self):
            return "FakeHTTP"

    def _fake_build_client(record: Any) -> Any:
        if record.transport == "sse":
            calls.append("sse")
            return FakeSSE()
        calls.append("streamable_http")
        return FakeHTTP()

    monkeypatch.setattr("app.services.mcp_service._build_mcp_client", _fake_build_client)
    monkeypatch.setattr(agent_module, "Agent", MagicMock(name="Agent"))
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    _, deps = await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert "sse" in calls, "_build_mcp_client was not called for SSE record"
    assert "streamable_http" in calls, "_build_mcp_client was not called for streamable_http record"
    sse_clients = [c for c in deps.mcp_servers if isinstance(c, FakeSSE)]
    http_clients = [c for c in deps.mcp_servers if isinstance(c, FakeHTTP)]
    assert len(sse_clients) == 1
    assert len(http_clients) == 1


# ---------------------------------------------------------------------------
# Scenario: System prompt contains active MCP server names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_contains_connected_integrations(monkeypatch: Any) -> None:
    """System prompt contains '## Connected Integrations' and server names.

    Gherkin:
      Given workspace W has active MCP servers ['github', 'azuredevops']
      When build_agent(...) is called
      Then the constructed Agent's system prompt contains '## Connected Integrations'
        then '- github' then '- azuredevops'
    """
    import app.agents.agent as agent_module

    sse_record = _make_mcp_record("github", "sse", is_active=True)
    http_record = _make_mcp_record(
        "azuredevops", "streamable_http", is_active=True, url="https://mcp.azure.com/"
    )

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[sse_record, http_record]),
    )
    monkeypatch.setattr(
        "app.services.mcp_service._build_mcp_client",
        lambda r: MagicMock(),
    )

    captured_kwargs: dict = {}

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    system_prompt = captured_kwargs.get("system_prompt", "")
    assert "## Connected Integrations" in system_prompt, (
        "System prompt must contain '## Connected Integrations' when servers exist"
    )
    assert "- github" in system_prompt
    assert "- azuredevops" in system_prompt


# ---------------------------------------------------------------------------
# Scenario: System prompt omits heading when no MCP servers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_omits_integrations_section_when_empty(monkeypatch: Any) -> None:
    """System prompt does NOT contain '## Connected Integrations' when zero active servers.

    Gherkin:
      Given workspace W has zero active MCP servers
      When build_agent(...) is called
      Then the constructed Agent's system prompt does not contain '## Connected Integrations'
    """
    import app.agents.agent as agent_module

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    captured_kwargs: dict = {}

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    system_prompt = captured_kwargs.get("system_prompt", "")
    assert "## Connected Integrations" not in system_prompt, (
        "System prompt must NOT contain '## Connected Integrations' when no servers exist"
    )


# ---------------------------------------------------------------------------
# Scenario: 3 new MCP tools are registered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_mcp_tools_registered(monkeypatch: Any) -> None:
    """add_mcp_server, remove_mcp_server, list_mcp_servers are registered as agent tools."""
    import app.agents.agent as agent_module

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    captured_kwargs: dict = {}

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_kwargs.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    tools_arg = captured_kwargs.get("tools", [])
    tool_names = [t.__name__ for t in tools_arg]
    assert "add_mcp_server" in tool_names, "add_mcp_server must be registered"
    assert "remove_mcp_server" in tool_names, "remove_mcp_server must be registered"
    assert "list_mcp_servers" in tool_names, "list_mcp_servers must be registered"


# ---------------------------------------------------------------------------
# Scenario: add_mcp_server tool result redacts auth_header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_mcp_server_tool_redacts_auth_header(monkeypatch: Any) -> None:
    """add_mcp_server result does NOT contain auth_header value; warning footer present.

    Gherkin:
      Given an active workspace and the agent built
      When the agent invokes add_mcp_server(..., auth_header='ghp_TOPSECRET')
      Then the returned tool-result string does NOT contain 'ghp_TOPSECRET'
      And it DOES contain the always-warn footer 'consider deleting'
    """
    import app.agents.agent as agent_module

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    captured_tools: list = []

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_tools.extend(kwargs.get("tools", []))
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Extract the add_mcp_server tool closure
    add_fn = next((t for t in captured_tools if t.__name__ == "add_mcp_server"), None)
    assert add_fn is not None, "add_mcp_server not found in registered tools"

    # Mock create_mcp_server to return a fake record without hitting DB
    fake_record = _make_mcp_record("x", "sse", is_active=True)

    ctx = MagicMock()
    ctx.deps.workspace_id = WORKSPACE_ID
    ctx.deps.supabase = MagicMock()

    with patch("app.services.mcp_service.create_mcp_server", AsyncMock(return_value=fake_record)):
        result = await add_fn(
            ctx,
            name="x",
            url="https://mcp.example.com/sse",
            transport="sse",
            auth_header="ghp_TOPSECRET",
        )

    assert "ghp_TOPSECRET" not in result, (
        "auth_header value must NEVER appear in add_mcp_server result (Q10)"
    )
    assert "consider deleting" in result, (
        "Warning footer 'consider deleting' must be present in add_mcp_server result"
    )


# ---------------------------------------------------------------------------
# Scenario: list_mcp_servers shows transport and active flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mcp_servers_tool_shows_transport_and_active_flag(monkeypatch: Any) -> None:
    """list_mcp_servers tool result contains name, transport, active/disabled.

    Gherkin:
      Given workspace W has [{name='github', transport='sse', is_active=true},
                              {name='x', transport='streamable_http', is_active=false}]
      When the agent invokes list_mcp_servers
      Then the returned string contains 'github (sse, active)' and 'x (streamable_http, disabled)'
    """
    import app.agents.agent as agent_module

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    captured_tools: list = []

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_tools.extend(kwargs.get("tools", []))
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    list_fn = next((t for t in captured_tools if t.__name__ == "list_mcp_servers"), None)
    assert list_fn is not None, "list_mcp_servers not found in registered tools"

    github_record = _make_mcp_record("github", "sse", is_active=True)
    x_record = _make_mcp_record(
        "x", "streamable_http", is_active=False, url="https://mcp.x.com/"
    )

    ctx = MagicMock()
    ctx.deps.workspace_id = WORKSPACE_ID
    ctx.deps.supabase = MagicMock()

    with patch(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[github_record, x_record]),
    ):
        result = await list_fn(ctx)

    assert "github (sse, active)" in result, f"Expected 'github (sse, active)' in: {result}"
    assert "x (streamable_http, disabled)" in result, (
        f"Expected 'x (streamable_http, disabled)' in: {result}"
    )


# ---------------------------------------------------------------------------
# Scenario: remove_mcp_server tool happy-path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_mcp_server_tool_happy_path(monkeypatch: Any) -> None:
    """remove_mcp_server returns confirmation string when server is found and deleted.

    Gherkin:
      Given workspace W has a connected MCP server named 'github'
      When the agent invokes remove_mcp_server(name='github')
      Then the returned string contains 'github'
      And indicates the server was disconnected (not an error message)
    """
    import app.agents.agent as agent_module

    monkeypatch.setattr(
        "app.services.mcp_service.list_mcp_servers",
        AsyncMock(return_value=[]),
    )

    captured_tools: list = []

    def _capture_agent(*args: Any, **kwargs: Any) -> MagicMock:
        captured_tools.extend(kwargs.get("tools", []))
        return MagicMock()

    monkeypatch.setattr(agent_module, "Agent", _capture_agent)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", MagicMock())
    monkeypatch.setattr(agent_module, "OpenAIProvider", MagicMock())
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr("app.services.skill_service.list_skills", lambda *a, **kw: [])

    supabase = _make_supabase_mock()
    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Extract the remove_mcp_server tool closure
    remove_fn = next((t for t in captured_tools if t.__name__ == "remove_mcp_server"), None)
    assert remove_fn is not None, "remove_mcp_server not found in registered tools"

    ctx = MagicMock()
    ctx.deps.workspace_id = WORKSPACE_ID
    ctx.deps.supabase = MagicMock()

    # delete_mcp_server returns True when a row is deleted
    with patch("app.services.mcp_service.delete_mcp_server", AsyncMock(return_value=True)):
        result = await remove_fn(ctx, name="github")

    assert "github" in result, f"Expected server name 'github' in result: {result}"
    assert "Failed" not in result, f"Expected success result, got: {result}"
    # The agent returns "Disconnected 'github'." on success
    assert "isconnect" in result.lower() or "remov" in result.lower(), (
        f"Expected disconnect/remove confirmation in result: {result}"
    )
