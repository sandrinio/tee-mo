"""Hermetic unit tests for STORY-008-02 — is_member Enrichment on list_channel_bindings.

Uses bare ``TestClient(app, raise_server_exceptions=False)`` (no context manager)
to avoid triggering the FastAPI lifespan — which spawns drive/wiki/automation cron
tasks that deadlock the event loop under pytest-asyncio auto mode (flashcard
2026-04-24 #test-harness #fastapi).

Covers §2.1 Gherkin scenarios:

  Scenario: Backend enriches with is_member
    Given 2 bindings: #general (bot is member), #private (bot not member)
    When GET /api/workspaces/{id}/channels is called
    Then is_member=true for #general, is_member=false for #private

  Scenario: Fallback when conversations.info raises exception
    Given conversations.info raises SlackApiError for a channel
    Then the binding is returned with is_member=false and channel_name=slack_channel_id

  Scenario: channel_name populated from Slack API response
    Given conversations.info returns a channel with name="general"
    Then the enriched binding has channel_name="general"

Strategy:
- Supabase client is fully mocked with unittest.mock.patch — no live DB.
- get_current_user_id is overridden via FastAPI dependency_overrides.
- AsyncWebClient is mocked (at module level in channels.py) to return canned
  conversations.info responses.
- SlackApiError from slack_sdk.errors is imported to test the fallback path.
- All mock chains replicate the supabase-py call pattern:
    client.table(name).select(...).eq(...).limit(...).execute()
    client.table(name).select(...).eq(...).order(...).execute()

FLASHCARDS.md consulted:
- get_supabase() is the only DB entry point (service-role key, cached).
- teemo_workspace_channels has slack_channel_id PK (not id) — select("*") not select("id").
- Hermetic mocks hide column-name mismatches — this tests enrichment logic only;
  live schema verification is a QA responsibility.
- httpx/AsyncWebClient imported at module level so monkeypatch works via
  app.api.routes.channels.AsyncWebClient (same principle as httpx flashcard).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_WORKSPACE_ID = str(uuid.uuid4())
FAKE_TEAM_ID = "T_ENRICH_TEAM_001"

_NOW = datetime.now(timezone.utc).isoformat()

FAKE_WORKSPACE_ROW: dict[str, Any] = {
    "id": FAKE_WORKSPACE_ID,
    "user_id": FAKE_USER_ID,
    "name": "Test Workspace",
    "slack_team_id": FAKE_TEAM_ID,
}

FAKE_SLACK_TEAM_ROW: dict[str, Any] = {
    "slack_team_id": FAKE_TEAM_ID,
    "owner_user_id": FAKE_USER_ID,
    "encrypted_slack_bot_token": "encrypted-token-blob",
}

FAKE_BOT_TOKEN = "xoxb-fake-enrichment-token"

BINDING_GENERAL: dict[str, Any] = {
    "slack_channel_id": "C_GENERAL",
    "workspace_id": FAKE_WORKSPACE_ID,
    "bound_at": _NOW,
}

BINDING_PRIVATE: dict[str, Any] = {
    "slack_channel_id": "C_PRIVATE",
    "workspace_id": FAKE_WORKSPACE_ID,
    "bound_at": _NOW,
}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_execute_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data attribute holds the given list."""
    result = MagicMock()
    result.data = data
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client():
    """TestClient with get_current_user_id overridden to return FAKE_USER_ID."""
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_user_id() -> str:
        return FAKE_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user_id
    # Use TestClient WITHOUT context manager — avoids triggering lifespan cron tasks.
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


def _make_supabase_mock_for_list_bindings(bindings: list[dict]) -> MagicMock:
    """Build a Supabase mock that returns the given bindings for teemo_workspace_channels."""
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW])
            tbl.select.return_value = sel

        elif name == "teemo_workspace_channels":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result(bindings)
            tbl.select.return_value = sel

        elif name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table
    return mock_sb


# ---------------------------------------------------------------------------
# Scenario: is_member enrichment via conversations.info
# ---------------------------------------------------------------------------


def test_list_channel_bindings_enriches_is_member(app_client: TestClient) -> None:
    """Gherkin: Backend enriches list_channel_bindings with is_member via conversations.info.

    Given 2 bindings: C_GENERAL (bot is member) and C_PRIVATE (bot not member),
    When GET /api/workspaces/{id}/channels is called,
    Then the response includes is_member=True for C_GENERAL
    And is_member=False for C_PRIVATE.

    conversations.info is mocked to return is_member=True for C_GENERAL
    and is_member=False for C_PRIVATE.
    """
    mock_sb = _make_supabase_mock_for_list_bindings([BINDING_GENERAL, BINDING_PRIVATE])

    async def _fake_conversations_info(channel: str) -> dict:
        if channel == "C_GENERAL":
            return {
                "ok": True,
                "channel": {
                    "id": "C_GENERAL",
                    "name": "general",
                    "is_member": True,
                },
            }
        elif channel == "C_PRIVATE":
            return {
                "ok": True,
                "channel": {
                    "id": "C_PRIVATE",
                    "name": "private-channel",
                    "is_member": False,
                },
            }
        return {"ok": False}

    mock_slack_client = AsyncMock()
    mock_slack_client.conversations_info.side_effect = _fake_conversations_info

    with (
        patch("app.api.routes.channels.get_supabase", return_value=mock_sb),
        patch("app.core.encryption.decrypt", return_value=FAKE_BOT_TOKEN),
        patch("app.api.routes.channels.AsyncWebClient", return_value=mock_slack_client),
    ):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), f"Expected list, got {type(body)}"
    assert len(body) == 2, f"Expected 2 bindings, got {len(body)}"

    by_id = {item["slack_channel_id"]: item for item in body}

    # C_GENERAL: bot is member
    assert "C_GENERAL" in by_id, "C_GENERAL missing from response"
    assert by_id["C_GENERAL"].get("is_member") is True, (
        f"Expected is_member=True for C_GENERAL, got {by_id['C_GENERAL'].get('is_member')}"
    )

    # C_PRIVATE: bot is not a member
    assert "C_PRIVATE" in by_id, "C_PRIVATE missing from response"
    assert by_id["C_PRIVATE"].get("is_member") is False, (
        f"Expected is_member=False for C_PRIVATE, got {by_id['C_PRIVATE'].get('is_member')}"
    )


# ---------------------------------------------------------------------------
# Scenario: channel_name populated from Slack API response
# ---------------------------------------------------------------------------


def test_list_channel_bindings_populates_channel_name(app_client: TestClient) -> None:
    """Gherkin: channel_name is populated from conversations.info response.

    Given a binding for C_GENERAL,
    When GET /api/workspaces/{id}/channels is called
    And conversations.info returns name="general",
    Then the enriched binding has channel_name="general".
    """
    mock_sb = _make_supabase_mock_for_list_bindings([BINDING_GENERAL])

    mock_slack_client = AsyncMock()
    mock_slack_client.conversations_info.return_value = {
        "ok": True,
        "channel": {
            "id": "C_GENERAL",
            "name": "general",
            "is_member": True,
        },
    }

    with (
        patch("app.api.routes.channels.get_supabase", return_value=mock_sb),
        patch("app.core.encryption.decrypt", return_value=FAKE_BOT_TOKEN),
        patch("app.api.routes.channels.AsyncWebClient", return_value=mock_slack_client),
    ):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body) == 1

    binding = body[0]
    assert binding.get("channel_name") == "general", (
        f"Expected channel_name='general', got {binding.get('channel_name')}"
    )


# ---------------------------------------------------------------------------
# Scenario: Fallback when conversations.info raises an exception
# ---------------------------------------------------------------------------


def test_list_channel_bindings_fallback_on_conversations_info_error(
    app_client: TestClient,
) -> None:
    """Gherkin: Fallback when conversations.info raises an exception.

    Given a binding for C_PRIVATE where conversations.info raises SlackApiError,
    When GET /api/workspaces/{id}/channels is called,
    Then the binding is returned with is_member=False
    And channel_name equals the slack_channel_id (fallback value).

    R13: Fallback on error: is_member=False, channel_name=slack_channel_id.
    """
    from slack_sdk.errors import SlackApiError

    mock_sb = _make_supabase_mock_for_list_bindings([BINDING_PRIVATE])

    mock_slack_client = AsyncMock()
    # Simulate a Slack API error (e.g., bot not in channel, channel not found)
    mock_slack_client.conversations_info.side_effect = SlackApiError(
        message="channel_not_found",
        response={"ok": False, "error": "channel_not_found"},
    )

    with (
        patch("app.api.routes.channels.get_supabase", return_value=mock_sb),
        patch("app.core.encryption.decrypt", return_value=FAKE_BOT_TOKEN),
        patch("app.api.routes.channels.AsyncWebClient", return_value=mock_slack_client),
    ):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    # Must still return 200 — errors in enrichment are non-fatal
    assert resp.status_code == 200, (
        f"Expected 200 (enrichment errors are non-fatal), got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert len(body) == 1

    binding = body[0]
    # Fallback: is_member=False on error
    assert binding.get("is_member") is False, (
        f"Expected is_member=False on error, got {binding.get('is_member')}"
    )
    # Fallback: channel_name falls back to the slack_channel_id string
    assert binding.get("channel_name") == "C_PRIVATE", (
        f"Expected channel_name='C_PRIVATE' (fallback), got {binding.get('channel_name')}"
    )


# ---------------------------------------------------------------------------
# Scenario: Fallback when conversations.info returns ok=False (no exception)
# ---------------------------------------------------------------------------


def test_list_channel_bindings_fallback_on_ok_false(app_client: TestClient) -> None:
    """Fallback when conversations.info returns ok=False without raising.

    Some Slack API errors return {"ok": False, "error": "..."} without raising.
    The enrichment must handle this gracefully with the same fallback:
    is_member=False and channel_name=slack_channel_id.
    """
    mock_sb = _make_supabase_mock_for_list_bindings([BINDING_GENERAL])

    mock_slack_client = AsyncMock()
    mock_slack_client.conversations_info.return_value = {
        "ok": False,
        "error": "missing_scope",
    }

    with (
        patch("app.api.routes.channels.get_supabase", return_value=mock_sb),
        patch("app.core.encryption.decrypt", return_value=FAKE_BOT_TOKEN),
        patch("app.api.routes.channels.AsyncWebClient", return_value=mock_slack_client),
    ):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body) == 1

    binding = body[0]
    assert binding.get("is_member") is False, (
        f"Expected is_member=False on ok=False, got {binding.get('is_member')}"
    )
    assert binding.get("channel_name") == "C_GENERAL", (
        f"Expected fallback channel_name='C_GENERAL', got {binding.get('channel_name')}"
    )
