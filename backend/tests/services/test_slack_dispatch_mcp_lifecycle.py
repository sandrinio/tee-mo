"""Tests for AsyncExitStack MCP lifecycle in slack_dispatch — STORY-012-03.

Covers the dispatch-lifecycle Gherkin scenarios from STORY-012-03 §2.1:

  Scenario: AsyncExitStack runs __aexit__ on agent.run() success
  Scenario: AsyncExitStack runs __aexit__ on agent.run() exception
  Scenario: Zero-MCP workspace runs unchanged

Mock strategy:
  - ``_stream_agent_to_slack`` is tested in isolation with a mock agent that
    exposes a ``run_stream`` async context manager.
  - MCP server objects are async context manager mocks that record
    __aenter__ and __aexit__ call counts.
  - Slack client (AsyncWebClient) is fully mocked — no real Slack calls.

All tests are async (pytest-asyncio ``asyncio_mode = "auto"`` in pyproject.toml).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockMcpServer:
    """Async context manager mock that records aenter/aexit calls."""

    def __init__(self) -> None:
        self.aenter_count = 0
        self.aexit_count = 0
        self.aexit_exc: BaseException | None = None

    async def __aenter__(self) -> "_MockMcpServer":
        self.aenter_count += 1
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> bool | None:
        self.aexit_count += 1
        self.aexit_exc = exc_val
        return None  # do not suppress exceptions


def _make_stream_context(text: str = "hello") -> Any:
    """Return an async context manager whose stream yields a single chunk."""

    class _FakeStream:
        async def stream_text(self, delta: bool = True):
            yield text

        def get_output(self) -> str:
            return text

    @asynccontextmanager
    async def _ctx(*args: Any, **kwargs: Any):
        yield _FakeStream()

    return _ctx


def _make_agent_mock(stream_ctx: Any) -> MagicMock:
    """Return a mock agent whose run_stream returns the given async context manager."""
    agent = MagicMock()
    agent.run_stream = stream_ctx
    return agent


def _make_slack_client() -> MagicMock:
    """Return a minimal mock Slack AsyncWebClient."""
    client = MagicMock()
    client.chat_postMessage = AsyncMock(return_value={"ts": "1234567890.123456"})
    client.chat_update = AsyncMock(return_value={})
    return client


def _make_deps(mcp_servers: list) -> MagicMock:
    """Return a minimal deps object with mcp_servers and citations."""
    deps = MagicMock()
    deps.mcp_servers = mcp_servers
    deps.citations = []
    return deps


# ---------------------------------------------------------------------------
# Scenario: AsyncExitStack runs __aexit__ on success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_exit_stack_aexit_on_success() -> None:
    """__aenter__ and __aexit__ are called exactly once on the MCP server on success.

    Gherkin:
      Given a Slack dispatch with 1 active MCP server (mock recording calls)
      When the dispatch completes successfully
      Then __aenter__ was called exactly once
      And __aexit__ was called exactly once
    """
    import app.services.slack_dispatch as dispatch_module

    mcp_server = _MockMcpServer()
    deps = _make_deps(mcp_servers=[mcp_server])
    client = _make_slack_client()
    agent = _make_agent_mock(_make_stream_context("response text"))

    with patch.object(
        dispatch_module,
        "markdown_to_mrkdwn",
        side_effect=lambda x: x,
    ):
        await dispatch_module._stream_agent_to_slack(
            agent=agent,
            user_prompt="hello",
            client=client,
            channel="C001",
            thread_ts="1234.5678",
            deps=deps,
        )

    assert mcp_server.aenter_count == 1, f"Expected __aenter__ called 1 time, got {mcp_server.aenter_count}"
    assert mcp_server.aexit_count == 1, f"Expected __aexit__ called 1 time, got {mcp_server.aexit_count}"
    assert mcp_server.aexit_exc is None, "__aexit__ should receive no exception on success"


# ---------------------------------------------------------------------------
# Scenario: AsyncExitStack runs __aexit__ on agent.run_stream exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_exit_stack_aexit_on_run_stream_exception() -> None:
    """__aexit__ is still called when agent.run_stream raises RuntimeError.

    Gherkin:
      Given a Slack dispatch where agent.run_stream raises RuntimeError mid-execution
      When the dispatch is invoked
      Then __aexit__ was still called exactly once on the MCP server
      And the original RuntimeError propagates (or is caught by fallback)
    """
    import app.services.slack_dispatch as dispatch_module

    mcp_server = _MockMcpServer()
    deps = _make_deps(mcp_servers=[mcp_server])
    client = _make_slack_client()

    # run_stream raises RuntimeError when entered
    @asynccontextmanager
    async def _failing_stream(*args: Any, **kwargs: Any):
        raise RuntimeError("stream failed mid-execution")
        yield  # noqa: unreachable — needed for asynccontextmanager

    agent = _make_agent_mock(_failing_stream)

    with patch.object(
        dispatch_module,
        "markdown_to_mrkdwn",
        side_effect=lambda x: x,
    ):
        # The outer except block in _stream_agent_to_slack re-raises when
        # accumulated is empty — so RuntimeError propagates
        with pytest.raises(RuntimeError, match="stream failed"):
            await dispatch_module._stream_agent_to_slack(
                agent=agent,
                user_prompt="hello",
                client=client,
                channel="C001",
                thread_ts="1234.5678",
                deps=deps,
            )

    assert mcp_server.aexit_count == 1, (
        f"__aexit__ must be called even when run_stream raises, got {mcp_server.aexit_count}"
    )


# ---------------------------------------------------------------------------
# Scenario: Zero-MCP workspace runs unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_mcp_servers_dispatch_unchanged() -> None:
    """When deps.mcp_servers == [], the existing slack_dispatch path is unchanged.

    Gherkin:
      Given workspace W with no MCP servers
      When the existing slack-dispatch happy-path test runs
      Then it passes with no behavioural change vs. before this story
    """
    import app.services.slack_dispatch as dispatch_module

    deps = _make_deps(mcp_servers=[])
    client = _make_slack_client()
    agent = _make_agent_mock(_make_stream_context("bot response"))

    with patch.object(
        dispatch_module,
        "markdown_to_mrkdwn",
        side_effect=lambda x: x,
    ):
        await dispatch_module._stream_agent_to_slack(
            agent=agent,
            user_prompt="ping",
            client=client,
            channel="C002",
            thread_ts="9999.0000",
            deps=deps,
        )

    # Verify Slack was posted to — dispatch worked normally
    assert client.chat_postMessage.call_count == 1
    assert client.chat_update.call_count >= 1  # at least the final update


# ---------------------------------------------------------------------------
# Scenario: Multiple MCP servers — all enter and exit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_mcp_servers_all_enter_and_exit() -> None:
    """All MCP servers in deps.mcp_servers get __aenter__ and __aexit__ called."""
    import app.services.slack_dispatch as dispatch_module

    server_a = _MockMcpServer()
    server_b = _MockMcpServer()
    deps = _make_deps(mcp_servers=[server_a, server_b])
    client = _make_slack_client()
    agent = _make_agent_mock(_make_stream_context("multi-server response"))

    with patch.object(
        dispatch_module,
        "markdown_to_mrkdwn",
        side_effect=lambda x: x,
    ):
        await dispatch_module._stream_agent_to_slack(
            agent=agent,
            user_prompt="hello",
            client=client,
            channel="C003",
            thread_ts="1111.2222",
            deps=deps,
        )

    assert server_a.aenter_count == 1
    assert server_a.aexit_count == 1
    assert server_b.aenter_count == 1
    assert server_b.aexit_count == 1


# ---------------------------------------------------------------------------
# Scenario: deps without mcp_servers attribute (bare-bones fake deps)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bare_bones_deps_without_mcp_servers_attr() -> None:
    """Dispatch works with deps that have no mcp_servers attribute (getattr guard).

    This covers the case where existing test fixtures build SimpleNamespace or
    minimal fake deps that don't set mcp_servers. The getattr(deps, 'mcp_servers', [])
    guard in slack_dispatch must prevent AttributeError.
    """
    import app.services.slack_dispatch as dispatch_module
    from types import SimpleNamespace

    # Bare-bones deps without mcp_servers
    deps = SimpleNamespace(citations=[])
    client = _make_slack_client()
    agent = _make_agent_mock(_make_stream_context("bare response"))

    with patch.object(
        dispatch_module,
        "markdown_to_mrkdwn",
        side_effect=lambda x: x,
    ):
        # Should not raise AttributeError
        await dispatch_module._stream_agent_to_slack(
            agent=agent,
            user_prompt="test",
            client=client,
            channel="C004",
            thread_ts="2222.3333",
            deps=deps,
        )

    assert client.chat_postMessage.call_count == 1
