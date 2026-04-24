"""Hermetic unit tests for STORY-007-04 — Channel Binding REST Endpoints.

Uses bare ``TestClient(app, raise_server_exceptions=False)`` (no context manager)
to avoid triggering the FastAPI lifespan — which spawns drive/wiki/automation cron
tasks that deadlock the event loop under pytest-asyncio auto mode (flashcard
2026-04-24 #test-harness #fastapi).

Covers all 6 Gherkin scenarios from §2.1:
  1. Bind a channel to a workspace — POST 201 with binding record
  2. Bind channel already bound — POST 409 with detail "channel_already_bound"
  3. Bind channel to workspace not owned by user — POST 403
  4. Unbind a channel — DELETE 204
  5. List bindings — GET 200 with list of bindings
  6. List Slack channels for a team — GET 200 with channel list from Slack API

Strategy:
- Supabase client is fully mocked with unittest.mock.patch — no live DB.
- get_current_user_id is overridden via FastAPI's dependency_overrides to
  control the authenticated user_id without JWT setup.
- AsyncWebClient (Slack SDK) is mocked to return a canned channel list for
  the conversations.list call.
- app.core.encryption.decrypt is mocked to return a deterministic bot token
  so the Slack call does not require a real encryption key.
- All mock chains replicate the supabase-py call pattern:
    client.table(name).select(...).eq(...).limit(...).execute()
    client.table(name).insert(...).execute()
    client.table(name).delete(...).eq(...).execute()

Table schema (ADR-024):
    teemo_workspace_channels: slack_channel_id (PK), workspace_id (FK),
    bound_at (DEFAULT NOW() — omitted from upsert payloads per FLASHCARDS.md).

FLASHCARDS.md consulted:
- get_supabase() is the only DB entry point (service-role key, cached).
- teemo_workspace_channels has slack_channel_id PK (not id) — use select("*")
  not select("id") per the S-03 hotfix flashcard.
- Supabase upsert omits DEFAULT NOW() columns (bound_at) from payloads.
- Agent Edit/Write uses worktree-relative paths — NOT absolute paths.
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
FAKE_OTHER_USER_ID = str(uuid.uuid4())
FAKE_WORKSPACE_ID = str(uuid.uuid4())
FAKE_TEAM_ID = "T_CHAN_TEAM_001"
FAKE_CHANNEL_ID = "C001"
FAKE_BOT_TOKEN = "xoxb-fake-bot-token"

_NOW = datetime.now(timezone.utc).isoformat()

FAKE_BINDING_ROW: dict[str, Any] = {
    "slack_channel_id": FAKE_CHANNEL_ID,
    "workspace_id": FAKE_WORKSPACE_ID,
    "bound_at": _NOW,
}

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

FAKE_SLACK_CHANNELS = [
    {"id": "C001", "name": "general", "is_private": False},
    {"id": "C002", "name": "random", "is_private": False},
    {"id": "C003", "name": "secret-channel", "is_private": True},
]


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
    """TestClient with get_current_user_id overridden to return FAKE_USER_ID.

    Clears dependency_overrides after the test to avoid test pollution.
    """
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


@pytest.fixture
def app_client_other_user():
    """TestClient authenticated as FAKE_OTHER_USER_ID — does NOT own the workspace.

    Used for ownership-enforcement tests (Scenario 3).
    """
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_other_user_id() -> str:
        return FAKE_OTHER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_other_user_id
    # Use TestClient WITHOUT context manager — avoids triggering lifespan cron tasks.
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Scenario 1 — POST /api/workspaces/{workspace_id}/channels → 201
# ---------------------------------------------------------------------------


def test_bind_channel_to_workspace_returns_201(app_client: TestClient) -> None:
    """Gherkin Scenario 1: Bind a channel to a workspace.

    Given an authenticated user who owns workspace W,
    When the user POSTs /api/workspaces/{workspace_id}/channels
    with body {"slack_channel_id": "C001"},
    Then the response is HTTP 201 Created,
    And the body contains the binding record with slack_channel_id and workspace_id.

    Supabase mock:
    - teemo_workspaces: ownership confirmed (user_id matches).
    - teemo_workspace_channels: no existing binding (empty result on duplicate check).
    - teemo_workspace_channels: insert returns FAKE_BINDING_ROW.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_workspaces":
            # Ownership check: workspace belongs to FAKE_USER_ID
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW])
            tbl.select.return_value = sel

        elif name == "teemo_workspace_channels":
            # Duplicate check returns empty (channel not yet bound)
            def _select(*args, **kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.execute.return_value = _make_execute_result([])
                return sel

            # Insert returns the new binding row
            def _insert(payload: dict) -> MagicMock:
                ins = MagicMock()
                ins.execute.return_value = _make_execute_result([FAKE_BINDING_ROW])
                return ins

            tbl.select.side_effect = _select
            tbl.insert.side_effect = _insert

        elif name == "teemo_slack_teams":
            # Seed a real slack-teams row so any decrypt path gets a string, not a MagicMock.
            # Prevents TypeError: argument should be a bytes-like object or ASCII string.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels",
            json={"slack_channel_id": FAKE_CHANNEL_ID},
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["slack_channel_id"] == FAKE_CHANNEL_ID
    assert body["workspace_id"] == FAKE_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Scenario 2 — POST with duplicate channel → 409 channel_already_bound
# ---------------------------------------------------------------------------


def test_bind_channel_already_bound_returns_409(app_client: TestClient) -> None:
    """Gherkin Scenario 2: Bind a channel that is already bound.

    Given an authenticated user who owns workspace W,
    And channel C001 is already bound to workspace W,
    When the user POSTs /api/workspaces/{workspace_id}/channels
    with body {"slack_channel_id": "C001"},
    Then the response is HTTP 409 Conflict,
    And the body detail is "channel_already_bound".

    Supabase mock:
    - teemo_workspaces: ownership confirmed.
    - teemo_workspace_channels: duplicate check returns an existing row.
    """
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
            # Duplicate check returns an existing binding row
            def _select(*args, **kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.execute.return_value = _make_execute_result([FAKE_BINDING_ROW])
                return sel

            tbl.select.side_effect = _select

        elif name == "teemo_slack_teams":
            # Seed a real row so any decrypt path gets a string, not a MagicMock.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels",
            json={"slack_channel_id": FAKE_CHANNEL_ID},
        )

    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("detail") == "channel_already_bound", (
        f"Expected detail 'channel_already_bound', got: {body.get('detail')}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — POST to workspace not owned by user → 403
# ---------------------------------------------------------------------------


def test_bind_channel_to_workspace_not_owned_returns_403(
    app_client_other_user: TestClient,
) -> None:
    """Gherkin Scenario 3: Bind channel to a workspace the user does not own.

    Given user FAKE_OTHER_USER_ID is authenticated,
    And workspace W is owned by FAKE_USER_ID (different user),
    When FAKE_OTHER_USER_ID POSTs /api/workspaces/{workspace_id}/channels,
    Then the response is HTTP 403 Forbidden.

    Supabase mock:
    - teemo_workspaces: ownership check returns empty (other user doesn't own it).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_workspaces":
            # No row found for this user+workspace combination
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        elif name == "teemo_slack_teams":
            # Seed a real row so any decrypt path gets a string, not a MagicMock.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client_other_user.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels",
            json={"slack_channel_id": FAKE_CHANNEL_ID},
        )

    assert resp.status_code == 403, (
        f"Expected 403 Forbidden for non-owner, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — DELETE /api/workspaces/{workspace_id}/channels/{channel_id} → 204
# ---------------------------------------------------------------------------


def test_unbind_channel_returns_204(app_client: TestClient) -> None:
    """Gherkin Scenario 4: Unbind a channel.

    Given an authenticated user who owns workspace W,
    And channel C001 is bound to workspace W,
    When the user sends DELETE /api/workspaces/{workspace_id}/channels/C001,
    Then the response is HTTP 204 No Content.

    Supabase mock:
    - teemo_workspaces: ownership confirmed.
    - teemo_workspace_channels: delete returns the deleted binding row
      (supabase-py returns the deleted row(s) from DELETE operations).
    """
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
            # Delete chain: .delete().eq().eq().execute()
            def _delete() -> MagicMock:
                dlt = MagicMock()
                dlt.eq.return_value = dlt
                dlt.execute.return_value = _make_execute_result([FAKE_BINDING_ROW])
                return dlt

            tbl.delete.side_effect = lambda: _delete()

        elif name == "teemo_slack_teams":
            # Seed a real row so any decrypt path gets a string, not a MagicMock.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client.delete(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels/{FAKE_CHANNEL_ID}",
        )

    assert resp.status_code == 204, f"Expected 204, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Scenario 5 — GET /api/workspaces/{workspace_id}/channels → 200 with list
# ---------------------------------------------------------------------------


def test_list_channel_bindings_returns_200_with_list(app_client: TestClient) -> None:
    """Gherkin Scenario 5: List channel bindings for a workspace.

    Given an authenticated user who owns workspace W,
    And workspace W has two channels bound to it,
    When the user sends GET /api/workspaces/{workspace_id}/channels,
    Then the response is HTTP 200 OK,
    And the body is a list containing both binding records.

    Supabase mock:
    - teemo_workspaces: ownership confirmed.
    - teemo_workspace_channels: select returns two binding rows.
    """
    binding_two: dict[str, Any] = {
        "slack_channel_id": "C002",
        "workspace_id": FAKE_WORKSPACE_ID,
        "bound_at": _NOW,
    }

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
            sel.execute.return_value = _make_execute_result([FAKE_BINDING_ROW, binding_two])
            tbl.select.return_value = sel

        elif name == "teemo_slack_teams":
            # Seed a real row so the enrichment path gets a string token, not a MagicMock.
            # Prevents TypeError: argument should be a bytes-like object or ASCII string.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), f"Expected a list, got: {type(body)}"
    assert len(body) == 2, f"Expected 2 bindings, got {len(body)}"
    channel_ids = {item["slack_channel_id"] for item in body}
    assert FAKE_CHANNEL_ID in channel_ids
    assert "C002" in channel_ids


# ---------------------------------------------------------------------------
# Scenario 5b — GET list when no channels bound returns 200 with empty list
# ---------------------------------------------------------------------------


def test_list_channel_bindings_empty_returns_200_empty_list(app_client: TestClient) -> None:
    """Gherkin Scenario 5 edge case: workspace with no bound channels.

    Given an authenticated user who owns workspace W,
    And no channels are bound to workspace W,
    When the user sends GET /api/workspaces/{workspace_id}/channels,
    Then the response is HTTP 200 OK with an empty list body.

    An empty binding list is valid — the route must return [] not 404.
    """
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
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        elif name == "teemo_slack_teams":
            # Seed a real row so any decrypt path gets a string, not a MagicMock.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/channels")

    assert resp.status_code == 200, f"Expected 200 for empty list, got {resp.status_code}: {resp.text}"
    assert resp.json() == [], f"Expected empty list, got {resp.json()}"


# ---------------------------------------------------------------------------
# Scenario 6 — GET /api/slack/teams/{team_id}/channels → 200 with Slack API list
# ---------------------------------------------------------------------------


def test_list_slack_channels_for_team_returns_200(app_client: TestClient) -> None:
    """Gherkin Scenario 6: List Slack channels for a team via Slack API.

    Given an authenticated user who owns Slack team T_CHAN_TEAM_001,
    When the user sends GET /api/slack/teams/{team_id}/channels,
    Then the route decrypts the bot token from teemo_slack_teams,
    And calls Slack conversations.list with types="public_channel,private_channel",
    And the response is HTTP 200 OK,
    And the body contains the channel list returned by Slack.

    Mocks:
    - teemo_slack_teams: returns FAKE_SLACK_TEAM_ROW with encrypted token.
    - app.core.encryption.decrypt: returns FAKE_BOT_TOKEN deterministically.
    - AsyncWebClient.conversations_list: returns FAKE_SLACK_CHANNELS.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            # Ownership check: team belongs to FAKE_USER_ID
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_SLACK_TEAM_ROW])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    # Build a mock AsyncWebClient that returns FAKE_SLACK_CHANNELS from conversations_list
    mock_slack_client = AsyncMock()
    mock_slack_client.conversations_list.return_value = {
        "ok": True,
        "channels": FAKE_SLACK_CHANNELS,
    }

    with (
        patch("app.api.routes.channels.get_supabase", return_value=mock_sb),
        patch("app.core.encryption.decrypt", return_value=FAKE_BOT_TOKEN),
        patch("app.api.routes.channels.AsyncWebClient", return_value=mock_slack_client),
    ):
        resp = app_client.get(f"/api/slack/teams/{FAKE_TEAM_ID}/channels")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), f"Expected a list of channels, got: {type(body)}"
    assert len(body) == len(FAKE_SLACK_CHANNELS), (
        f"Expected {len(FAKE_SLACK_CHANNELS)} channels, got {len(body)}"
    )
    # Verify the Slack API was called with correct channel types
    mock_slack_client.conversations_list.assert_called_once()
    call_kwargs = mock_slack_client.conversations_list.call_args
    assert "types" in call_kwargs.kwargs or (
        call_kwargs.args and "public_channel" in str(call_kwargs.args)
    ), "conversations_list must be called with types parameter"


# ---------------------------------------------------------------------------
# Scenario 6b — GET Slack channels for team not owned by user → 403
# ---------------------------------------------------------------------------


def test_list_slack_channels_for_team_not_owned_returns_403(
    app_client_other_user: TestClient,
) -> None:
    """Gherkin Scenario 6 ownership check: non-owner cannot list Slack channels.

    Given user FAKE_OTHER_USER_ID is authenticated,
    And Slack team T_CHAN_TEAM_001 is owned by FAKE_USER_ID,
    When FAKE_OTHER_USER_ID sends GET /api/slack/teams/{team_id}/channels,
    Then the response is HTTP 403 Forbidden.

    Supabase mock:
    - teemo_slack_teams: ownership check returns empty (other user doesn't own team).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.channels.get_supabase", return_value=mock_sb):
        resp = app_client_other_user.get(f"/api/slack/teams/{FAKE_TEAM_ID}/channels")

    assert resp.status_code == 403, (
        f"Expected 403 Forbidden for non-owner of Slack team, got {resp.status_code}: {resp.text}"
    )
