"""
Tests for STORY-007-05 — Slack Event Dispatch (app_mention + message.im handlers).

RED PHASE — all tests written before implementation exists. Tests WILL fail because:
  - ``app.services.slack_dispatch`` does not exist yet.
  - ``app.api.routes.slack_events`` still returns 202 (not 200) for event_callback.

Scenarios covered (9 total):
  1. app_mention in bound channel — agent built, thread fetched, reply posted
  2. app_mention in unbound channel — nudge posted, no agent built
  3. DM happy path — agent runs, reply posted
  4. DM self-message filter (user == UBOT) — early return, no processing
  5. DM self-message filter (bot_id field) — early return, no processing
  6. No BYOK key — bound channel, no key → error message posted
  7. No default workspace for DM — nudge message posted
  8. Slack events endpoint returns 200 immediately for event_callback (was 202)
  9. Mention prefix stripped — "<@UBOT123> what is X?" → agent receives "what is X?"

Mock strategy:
  - ``app.agents.agent.build_agent`` patched to return (mock_agent, mock_deps).
  - mock_agent.run is an AsyncMock returning an object with a ``.data`` attribute.
  - ``app.services.slack_thread.fetch_thread_history`` patched to return canned history.
  - ``app.core.db.get_supabase`` patched to return a MagicMock Supabase client.
  - ``app.core.encryption.decrypt`` patched to return a deterministic bot token.
  - ``slack_sdk.web.async_client.AsyncWebClient`` patched with FakeAsyncWebClient.
  - Supabase chain mocks simulate workspace_channels, teemo_workspaces,
    and teemo_slack_teams queries.

Sprint context: S-07
  - No asyncio.create_task in tests — test dispatch function directly.
  - Test endpoint separately for 200 response (scenario 8).

FLASHCARDS.md consulted:
  - [S-04] AsyncWebClient imported at module level in the module under test.
  - [S-07] No asyncio.create_task in tests — direct function calls.
  - [S-05] Worktree .env copy required before running backend tests.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio  # noqa: F401 — ensures pytest-asyncio is importable
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


# ---------------------------------------------------------------------------
# Deferred import — module under test does not exist yet in Red Phase.
# We capture ImportError so test collection succeeds; each test re-raises it.
# ---------------------------------------------------------------------------

try:
    from app.services.slack_dispatch import (  # type: ignore[import]
        handle_slack_event,
        _handle_app_mention,
        _handle_dm,
    )
    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    handle_slack_event = None  # type: ignore[assignment]
    _handle_app_mention = None  # type: ignore[assignment]
    _handle_dm = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc


# ---------------------------------------------------------------------------
# FakeAsyncWebClient — hand-rolled mock for slack_sdk.web.async_client.AsyncWebClient.
# Captures all chat.postMessage calls for assertion.
# ---------------------------------------------------------------------------


class FakeAsyncWebClient:
    """Minimal fake matching the AsyncWebClient interface used by slack_dispatch.

    Captures ``chat_postMessage`` calls in ``self.post_message_calls`` so tests
    can assert on the arguments passed (channel, text, thread_ts).

    ``users_info_response`` controls what ``users_info(user=...)`` returns.
    Set to a dict to return that response, to an Exception subclass instance
    to raise it, or leave as None to return a minimal default (no tz).
    """

    def __init__(self, users_info_response: Any = None) -> None:
        self.post_message_calls: list[dict[str, Any]] = []
        self.users_info_response = users_info_response

    async def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        """Capture kwargs and return a fake Slack API success response."""
        self.post_message_calls.append(kwargs)
        return {"ok": True, "ts": "9999.0001"}

    async def users_info(self, **kwargs: Any) -> dict[str, Any]:
        """Return the configured users_info response or raise if it is an Exception."""
        if isinstance(self.users_info_response, Exception):
            raise self.users_info_response
        if self.users_info_response is not None:
            return self.users_info_response
        return {"ok": True, "user": {"real_name": "Test User", "profile": {}}}


# ---------------------------------------------------------------------------
# Supabase mock builders
# ---------------------------------------------------------------------------


def _make_supabase_chain(data: list[dict] | dict | None) -> MagicMock:
    """Build a fluent Supabase query chain that returns ``data`` on .execute().

    Supports all chained methods used by slack_dispatch:
    .table().select().eq().limit().execute()
    .table().select().eq().maybe_single().execute()
    """
    mock_result = MagicMock()
    mock_result.data = data

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.maybe_single.return_value = chain
    chain.execute.return_value = mock_result

    return chain


def _make_supabase_mock(
    channel_binding: dict | None = None,
    workspace_row: dict | None = None,
    team_row: dict | None = None,
) -> MagicMock:
    """Build a Supabase mock that responds to table queries used by slack_dispatch.

    Routes .table("teemo_workspace_channels") → channel_binding data.
    Routes .table("teemo_workspaces") → workspace_row data.
    Routes .table("teemo_slack_teams") → team_row data.

    Args:
        channel_binding: Row dict from teemo_workspace_channels, or None if unbound.
        workspace_row: Row dict from teemo_workspaces (default workspace), or None.
        team_row: Row dict from teemo_slack_teams, or None if team not found.
    """
    # Channel binding: .data = [row] if found, else []
    channel_data = [channel_binding] if channel_binding is not None else []
    channel_chain = _make_supabase_chain(channel_data)

    # Workspace lookup: .data = workspace_row (maybe_single)
    workspace_chain = _make_supabase_chain(workspace_row)

    # Team lookup: .data = [team_row] if found, else []
    team_data = [team_row] if team_row is not None else []
    team_chain = _make_supabase_chain(team_data)

    supabase = MagicMock()

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspace_channels":
            return channel_chain
        elif table_name == "teemo_workspaces":
            return workspace_chain
        elif table_name == "teemo_slack_teams":
            return team_chain
        return MagicMock()

    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_STUB_SECRET = "dispatch_test_secret"


def _sign(body: bytes, secret: str = _STUB_SECRET) -> tuple[str, str]:
    """Return (timestamp_str, v0_signature) for ``body`` signed with ``secret``."""
    ts = str(int(time.time()))
    base = f"v0:{ts}:{body.decode()}".encode()
    sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return ts, sig


@pytest.fixture(autouse=True)
def _patch_slack_signing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override SLACK_SIGNING_SECRET so endpoint tests don't need the real .env value."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", _STUB_SECRET)
    get_settings.cache_clear()
    try:
        from app.core.slack import get_slack_app
        get_slack_app.cache_clear()
    except Exception:  # pragma: no cover
        pass
    yield
    get_settings.cache_clear()
    try:
        from app.core.slack import get_slack_app
        get_slack_app.cache_clear()
    except Exception:  # pragma: no cover
        pass


@pytest.fixture()
def client() -> TestClient:
    """Return a FastAPI TestClient bound to the main app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Shared event payload builders
# ---------------------------------------------------------------------------


def _app_mention_payload(
    channel: str = "C001",
    text: str = "<@UBOT> hello",
    user: str = "U001",
    team: str = "T001",
    ts: str = "1234.5678",
) -> dict:
    """Build a minimal app_mention event_callback payload."""
    return {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": channel,
            "ts": ts,
            "text": text,
            "team": team,
            "user": user,
        },
    }


def _dm_payload(
    channel: str = "D001",
    text: str = "hello",
    user: str = "U001",
    team: str = "T001",
    ts: str = "1234.5678",
    bot_id: str | None = None,
) -> dict:
    """Build a minimal message.im (DM) event_callback payload."""
    event: dict[str, Any] = {
        "type": "message",
        "channel_type": "im",
        "channel": channel,
        "ts": ts,
        "text": text,
        "team": team,
    }
    if bot_id is not None:
        event["bot_id"] = bot_id
    else:
        event["user"] = user
    return {"type": "event_callback", "event": event}


# ---------------------------------------------------------------------------
# Scenario 1: app_mention in bound channel — agent built, thread fetched, reply posted
#
# Given channel C001 is bound to workspace W1 with a BYOK key
# When handle_slack_event receives an app_mention event
# Then build_agent is called, fetch_thread_history is called,
#   and chat.postMessage is called with thread_ts and the agent's response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_mention_bound_channel_happy_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 1 — app_mention in bound channel → agent runs, reply posted.

    Verifies:
    - build_agent is called (agent factory invoked).
    - fetch_thread_history is called with the correct channel and thread_ts.
    - chat.postMessage is called with thread_ts=event["ts"] and the agent reply text.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    # --- Mock Supabase ---
    channel_row = {"slack_channel_id": "C001", "workspace_id": "ws-W1"}
    workspace_row = {
        "id": "ws-W1",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=channel_row,
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    # --- Mock decrypt ---
    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _ciphertext: "xoxb-fake-bot-token")

    # --- Mock agent ---
    mock_agent_result = MagicMock()
    mock_agent_result.output ="Hello from agent!"

    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    from app.agents.agent import AgentDeps
    mock_deps = AgentDeps(workspace_id="ws-W1", supabase=mock_supabase, user_id="UBOT")

    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", AsyncMock(return_value=(mock_agent, mock_deps)))

    # --- Mock fetch_thread_history ---
    from pydantic_ai.messages import ModelRequest, UserPromptPart
    canned_history = [ModelRequest(parts=[UserPromptPart(content="Alice: prior message")])]
    import app.services.slack_thread as thread_module
    monkeypatch.setattr(
        thread_module, "fetch_thread_history", AsyncMock(return_value=canned_history)
    )

    # --- Mock AsyncWebClient for chat.postMessage ---
    fake_slack_client = FakeAsyncWebClient()

    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(
        dispatch_module,
        "AsyncWebClient",
        lambda token: fake_slack_client,  # type: ignore[arg-type]
    )

    payload = _app_mention_payload(channel="C001", text="<@UBOT> hello", ts="1234.5678")
    await handle_slack_event(payload)

    # Assert agent was invoked
    assert mock_agent.run.called, "build_agent's agent.run() should have been called"

    # Assert chat.postMessage was called with thread_ts
    assert len(fake_slack_client.post_message_calls) == 1
    call_kwargs = fake_slack_client.post_message_calls[0]
    assert call_kwargs.get("channel") == "C001"
    assert call_kwargs.get("thread_ts") == "1234.5678"
    assert "Hello from agent!" in call_kwargs.get("text", "")


# ---------------------------------------------------------------------------
# Scenario 2: app_mention in unbound channel — nudge posted, no agent built
#
# Given channel C999 has no binding in teemo_workspace_channels
# When handle_slack_event receives an app_mention for C999
# Then chat.postMessage is called with a nudge/setup message
#   AND build_agent is NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_mention_unbound_channel_nudge_posted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 2 — app_mention in unbound channel → nudge posted, no agent built."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    # No channel binding — data is empty
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=None,
        workspace_row=None,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    # build_agent should NOT be called
    build_agent_mock = AsyncMock()
    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _app_mention_payload(channel="C999")
    await handle_slack_event(payload)

    # build_agent must NOT have been called
    assert not build_agent_mock.called, "build_agent should NOT be called for unbound channels"

    # A nudge/setup message must be posted
    assert len(fake_slack_client.post_message_calls) >= 1
    posted_text = fake_slack_client.post_message_calls[0].get("text", "")
    assert posted_text, "A nudge message text should have been posted"


# ---------------------------------------------------------------------------
# Scenario 3: DM happy path — agent runs, reply posted
#
# Given team T001 has a default workspace with a BYOK key
# When handle_slack_event receives a message.im event from U001
# Then agent runs and a reply is posted to the DM channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dm_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 3 — DM from real user → agent runs, reply posted."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    workspace_row = {
        "id": "ws-default",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
        "is_default": True,
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=None,  # DMs don't use channel binding
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    mock_agent_result = MagicMock()
    mock_agent_result.output ="DM reply from agent"
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    from app.agents.agent import AgentDeps
    mock_deps = AgentDeps(workspace_id="ws-default", supabase=mock_supabase, user_id="UBOT")

    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", AsyncMock(return_value=(mock_agent, mock_deps)))

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _dm_payload(user="U001", team="T001")
    await handle_slack_event(payload)

    # Agent should have run
    assert mock_agent.run.called, "agent.run() should have been called for DM"

    # Reply should be posted to DM channel
    assert len(fake_slack_client.post_message_calls) == 1
    call_kwargs = fake_slack_client.post_message_calls[0]
    assert call_kwargs.get("channel") == "D001"
    assert "DM reply from agent" in call_kwargs.get("text", "")


# ---------------------------------------------------------------------------
# Scenario 4: DM self-message filter (user field) — user == UBOT → no processing
#
# Given a message.im event with user=UBOT (the bot's own Slack user ID)
# When handle_slack_event receives it
# Then the event is silently discarded — no agent built, no message posted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dm_self_message_filter_user_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 4 — DM self-message (user==UBOT) → early return, no processing."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(team_row=team_row)

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    build_agent_mock = AsyncMock()
    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    # DM where user == UBOT (the bot itself)
    payload = _dm_payload(user="UBOT", team="T001")
    await handle_slack_event(payload)

    # Nothing should happen
    assert not build_agent_mock.called, "build_agent should NOT be called for bot self-messages"
    assert len(fake_slack_client.post_message_calls) == 0, "No message should be posted for self-messages"


# ---------------------------------------------------------------------------
# Scenario 5: DM self-message filter (bot_id field) — bot_id present → no processing
#
# Given a message.im event with bot_id="B123"
# When handle_slack_event receives it
# Then the event is silently discarded — no agent built, no message posted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dm_self_message_filter_bot_id_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 5 — DM with bot_id field → early return, no processing."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(team_row=team_row)

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    build_agent_mock = AsyncMock()
    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    # DM with bot_id field present — another bot's message or our own echo
    payload = _dm_payload(bot_id="B123", team="T001")
    await handle_slack_event(payload)

    assert not build_agent_mock.called, "build_agent should NOT be called when bot_id is set"
    assert len(fake_slack_client.post_message_calls) == 0, "No message should be posted when bot_id is set"


# ---------------------------------------------------------------------------
# Scenario 6: No BYOK key — bound channel, workspace has no key
#
# Given channel C001 is bound to workspace W1 but workspace has encrypted_api_key=None
# When handle_slack_event receives an app_mention
# Then a "No API key configured" message is posted to the thread
#   AND build_agent is NOT called (it would raise ValueError("no_key_configured"))
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_mention_no_byok_key_error_posted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 6 — bound channel but no BYOK key → error message posted."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    channel_row = {"slack_channel_id": "C001", "workspace_id": "ws-W1"}
    # Workspace exists but has no API key
    workspace_row = {
        "id": "ws-W1",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": None,
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=channel_row,
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    # build_agent raises ValueError("no_key_configured") — simulates the real behavior
    import app.agents.agent as agent_module
    monkeypatch.setattr(
        agent_module,
        "build_agent",
        AsyncMock(side_effect=ValueError("no_key_configured")),
    )

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _app_mention_payload(channel="C001")
    await handle_slack_event(payload)

    # An error/nudge message about missing API key should be posted
    assert len(fake_slack_client.post_message_calls) >= 1
    posted_text = fake_slack_client.post_message_calls[0].get("text", "").lower()
    # The message should reference API key configuration
    assert "key" in posted_text or "api" in posted_text or "configure" in posted_text, (
        f"Expected an API key error message but got: {posted_text!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 7: No default workspace for DM — team has no default workspace
#
# Given team T001 exists but has no workspace with is_default=True
# When handle_slack_event receives a message.im
# Then a "Set up a workspace" nudge is posted
#   AND build_agent is NOT called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dm_no_default_workspace_nudge_posted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 7 — DM but no default workspace → nudge message posted."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    # No workspace — data is None (maybe_single returns None)
    mock_supabase = _make_supabase_mock(
        channel_binding=None,
        workspace_row=None,  # no default workspace found
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    build_agent_mock = AsyncMock()
    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _dm_payload(user="U001", team="T001")
    await handle_slack_event(payload)

    # build_agent should not be called — no workspace configured
    assert not build_agent_mock.called, "build_agent should NOT be called when no default workspace"

    # A setup nudge should be posted
    assert len(fake_slack_client.post_message_calls) >= 1
    posted_text = fake_slack_client.post_message_calls[0].get("text", "")
    assert posted_text, "A nudge message about workspace setup should have been posted"


# ---------------------------------------------------------------------------
# Scenario 8: Slack events endpoint returns 200 immediately for event_callback
#
# Given a valid signed event_callback payload
# When POST /api/slack/events is called
# Then the response status is 200 (not 202 — changed from passthrough stub)
#
# NOTE: This test explicitly checks that the endpoint was updated to return
# 200 (dispatching via asyncio.create_task) rather than the old 202 passthrough.
# ---------------------------------------------------------------------------


def test_slack_events_endpoint_returns_200_for_event_callback(client: TestClient) -> None:
    """Scenario 8 — valid signed event_callback → 200 response (was 202 before)."""
    payload = {
        "type": "event_callback",
        "event": {
            "type": "app_mention",
            "channel": "C001",
            "ts": "1234.5678",
            "text": "<@UBOT> hello",
            "team": "T001",
            "user": "U001",
        },
    }
    body_bytes = json.dumps(payload).encode()
    ts, sig = _sign(body_bytes)

    response = client.post(
        "/api/slack/events",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )

    # The endpoint must return 200, not 202, after STORY-007-05 is implemented.
    # In Red Phase this will FAIL because the current endpoint still returns 202.
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Scenario 9: Mention prefix stripped
#
# Given an app_mention event with text="<@UBOT123> what is X?"
# When handle_slack_event processes it
# Then the agent receives "what is X?" (prefix stripped), not the raw text
#
# Asserts on the user_prompt argument passed to agent.run().
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mention_prefix_stripped_before_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario 9 — mention prefix in text is stripped before passing to agent.run()."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    channel_row = {"slack_channel_id": "C001", "workspace_id": "ws-W1"}
    workspace_row = {
        "id": "ws-W1",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT123",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=channel_row,
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    # Capture the argument passed to agent.run()
    mock_agent_result = MagicMock()
    mock_agent_result.output ="stripped prefix response"
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    from app.agents.agent import AgentDeps
    mock_deps = AgentDeps(workspace_id="ws-W1", supabase=mock_supabase, user_id="UBOT123")

    import app.agents.agent as agent_module
    monkeypatch.setattr(
        agent_module, "build_agent", AsyncMock(return_value=(mock_agent, mock_deps))
    )

    import app.services.slack_thread as thread_module
    monkeypatch.setattr(thread_module, "fetch_thread_history", AsyncMock(return_value=[]))

    fake_slack_client = FakeAsyncWebClient()
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    # Text includes the bot mention prefix
    raw_text = "<@UBOT123> what is X?"
    payload = _app_mention_payload(channel="C001", text=raw_text, ts="1234.5678")
    await handle_slack_event(payload)

    # agent.run() must have been called
    assert mock_agent.run.called, "agent.run() should have been called"

    # The first positional argument (user prompt) must NOT include the mention prefix
    call_args = mock_agent.run.call_args
    # agent.run(user_prompt, ...) — check first positional arg
    if call_args.args:
        user_prompt_arg = call_args.args[0]
    else:
        # Might be passed as keyword arg depending on implementation
        user_prompt_arg = call_args.kwargs.get(
            "user_prompt", call_args.kwargs.get("message_history", "")
        )

    assert "<@UBOT123>" not in str(user_prompt_arg), (
        f"Mention prefix must be stripped before passing to agent. Got: {user_prompt_arg!r}"
    )
    assert "what is X?" in str(user_prompt_arg), (
        f"Stripped prompt should contain 'what is X?'. Got: {user_prompt_arg!r}"
    )


# ---------------------------------------------------------------------------
# Integration test A (STORY-018-08):
# slack_dispatch extracts tz from users_info and wires to build_agent
#
# Given a Slack user whose profile tz is "America/Los_Angeles"
# When handle_slack_event receives an app_mention
# Then build_agent is called with sender_tz="America/Los_Angeles"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_mention_sender_tz_extracted_from_users_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration A (STORY-018-08) — users_info tz threaded to build_agent.

    Verifies that slack_dispatch plucks ``user["tz"]`` from the users_info
    response and forwards it as ``sender_tz`` kwarg to build_agent, so the
    agent's deps and system prompt reflect the sender's local timezone.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    channel_row = {"slack_channel_id": "C001", "workspace_id": "ws-W1"}
    workspace_row = {
        "id": "ws-W1",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=channel_row,
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    # Capture build_agent kwargs so we can assert sender_tz
    mock_agent_result = MagicMock()
    mock_agent_result.output = "Scheduled!"
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    from app.agents.agent import AgentDeps
    mock_deps = AgentDeps(workspace_id="ws-W1", supabase=mock_supabase, user_id="user-001")
    build_agent_mock = AsyncMock(return_value=(mock_agent, mock_deps))

    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    import app.services.slack_thread as thread_module
    monkeypatch.setattr(thread_module, "fetch_thread_history", AsyncMock(return_value=[]))

    # FakeAsyncWebClient returns "America/Los_Angeles" in users_info
    fake_slack_client = FakeAsyncWebClient(
        users_info_response={
            "ok": True,
            "user": {
                "tz": "America/Los_Angeles",
                "real_name": "Alice",
                "profile": {"display_name": "Alice"},
            },
        }
    )
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _app_mention_payload(channel="C001", text="<@UBOT> schedule 9am standup", ts="1234.5678")
    await handle_slack_event(payload)

    # build_agent must have been called with sender_tz="America/Los_Angeles"
    assert build_agent_mock.called, "build_agent should have been called"
    call_kwargs = build_agent_mock.call_args.kwargs
    assert call_kwargs.get("sender_tz") == "America/Los_Angeles", (
        f"Expected sender_tz='America/Los_Angeles' passed to build_agent. "
        f"Got call kwargs: {call_kwargs!r}. "
        "STORY-018-08 R1: slack_dispatch must thread users_info tz to build_agent."
    )


# ---------------------------------------------------------------------------
# Integration test B (STORY-018-08):
# users_info failure → sender_tz="UTC" + build_agent called with default
#
# Given users_info raises for the sender
# When handle_slack_event receives an app_mention
# Then build_agent is called with sender_tz="UTC" (no 500, no retry storm)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_mention_users_info_failure_falls_back_to_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration B (STORY-018-08) — users_info failure → sender_tz defaults to UTC.

    Verifies that when users_info raises (network error, Slack API error, etc.)
    slack_dispatch does NOT propagate the exception. Instead it falls back to
    sender_tz="UTC" and calls build_agent normally so the agent can still reply
    with the softer "timezone unknown, defaulting to UTC" prompt variant.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    channel_row = {"slack_channel_id": "C001", "workspace_id": "ws-W1"}
    workspace_row = {
        "id": "ws-W1",
        "ai_provider": "openai",
        "ai_model": "gpt-4o",
        "encrypted_api_key": "enc-key-blob",
    }
    team_row = {
        "slack_team_id": "T001",
        "owner_user_id": "user-001",
        "encrypted_slack_bot_token": "enc-bot-token",
        "slack_bot_user_id": "UBOT",
    }
    mock_supabase = _make_supabase_mock(
        channel_binding=channel_row,
        workspace_row=workspace_row,
        team_row=team_row,
    )

    import app.core.db as db_module
    monkeypatch.setattr(db_module, "get_supabase", lambda: mock_supabase)

    import app.core.encryption as enc_module
    monkeypatch.setattr(enc_module, "decrypt", lambda _: "xoxb-fake-bot-token")

    mock_agent_result = MagicMock()
    mock_agent_result.output = "Scheduled in UTC!"
    mock_agent = MagicMock()
    mock_agent.run = AsyncMock(return_value=mock_agent_result)

    from app.agents.agent import AgentDeps
    mock_deps = AgentDeps(workspace_id="ws-W1", supabase=mock_supabase, user_id="user-001")
    build_agent_mock = AsyncMock(return_value=(mock_agent, mock_deps))

    import app.agents.agent as agent_module
    monkeypatch.setattr(agent_module, "build_agent", build_agent_mock)

    import app.services.slack_thread as thread_module
    monkeypatch.setattr(thread_module, "fetch_thread_history", AsyncMock(return_value=[]))

    # FakeAsyncWebClient raises on users_info
    fake_slack_client = FakeAsyncWebClient(
        users_info_response=Exception("Slack API error")
    )
    import app.services.slack_dispatch as dispatch_module  # type: ignore[import]
    monkeypatch.setattr(dispatch_module, "AsyncWebClient", lambda token: fake_slack_client)

    payload = _app_mention_payload(channel="C001", text="<@UBOT> schedule 9am standup", ts="1234.5678")
    await handle_slack_event(payload)

    # build_agent must have been called with sender_tz="UTC" (fallback)
    assert build_agent_mock.called, "build_agent should have been called even when users_info fails"
    call_kwargs = build_agent_mock.call_args.kwargs
    assert call_kwargs.get("sender_tz") == "UTC", (
        f"Expected sender_tz='UTC' (fallback) when users_info raises. "
        f"Got call kwargs: {call_kwargs!r}. "
        "STORY-018-08 R7: users_info failure must not propagate; sender_tz must default to UTC."
    )
