"""Hermetic unit tests for STORY-003-B02 — Workspace REST routes.

Covers the minimum 2 acceptance criteria from STORY-003-B02 §4.1:
  1. POST /api/slack-teams/{team_id}/workspaces returns 201 for the first workspace
     and auto-sets is_default_for_team=True.
  2. assert_team_owner returns 403 when the authenticated user does not own the team.

Strategy:
- Supabase client is fully mocked with unittest.mock.patch so no live DB is needed.
- get_current_user_id is overridden via FastAPI's dependency_overrides so we can
  control the user_id in each test without JWT setup.
- All mock chains replicate the supabase-py call pattern:
    client.table(name).select(...).eq(...).limit(...).execute()
    client.table(name).insert(...).execute()
    client.table(name).update(...).eq(...).execute()

B03 will provide full integration tests against a live Supabase instance.
These tests are deliberately hermetic and minimal (spec §1.3).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Build mock helpers
# ---------------------------------------------------------------------------

FAKE_USER_ID = str(uuid.uuid4())
FAKE_TEAM_ID = "T_TEST_TEAM"
FAKE_WORKSPACE_ID = str(uuid.uuid4())

_NOW = datetime.now(timezone.utc).isoformat()

FAKE_WORKSPACE_ROW: dict[str, Any] = {
    "id": FAKE_WORKSPACE_ID,
    "user_id": FAKE_USER_ID,
    "name": "My Test Workspace",
    "slack_team_id": FAKE_TEAM_ID,
    "ai_provider": None,
    "ai_model": None,
    "is_default_for_team": True,
    "created_at": _NOW,
    "updated_at": _NOW,
}


def _make_execute_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data attribute holds the given list."""
    result = MagicMock()
    result.data = data
    return result


def _make_supabase_mock() -> MagicMock:
    """Build a supabase-py mock whose .table().select/insert/update chains succeed."""
    mock = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        # select chain: .select().eq().eq().limit().execute() or .eq().limit().execute()
        def _select(*args, **kwargs) -> MagicMock:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            return sel

        # insert chain: .insert(payload).execute()
        def _insert(payload: dict) -> MagicMock:
            ins = MagicMock()
            ins.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW])
            return ins

        # update chain: .update(payload).eq().eq().execute()
        def _update(payload: dict) -> MagicMock:
            upd = MagicMock()
            upd.eq.return_value = upd
            upd.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW])
            return upd

        tbl.select.side_effect = _select
        tbl.insert.side_effect = _insert
        tbl.update.side_effect = _update
        return tbl

    mock.table.side_effect = _table
    return mock


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
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1 — POST creates first workspace and returns 201 with is_default_for_team=True
# ---------------------------------------------------------------------------


def test_create_first_workspace_returns_201_and_is_default(app_client: TestClient) -> None:
    """Gherkin: Create first workspace.

    Given a user with a valid Slack team and zero existing workspaces,
    When the user POSTs to /api/slack-teams/{team_id}/workspaces with a valid name,
    Then the response is HTTP 201 Created,
    And the returned workspace has is_default_for_team = true.

    Supabase mock:
    - teemo_slack_teams check returns one row (user owns the team) for assert_team_owner.
    - teemo_workspaces "existing count" check returns empty list (first workspace).
    - teemo_workspaces insert returns FAKE_WORKSPACE_ROW with is_default_for_team=True.
    """
    mock_sb = _make_supabase_mock()

    # teemo_slack_teams: ownership confirmed (non-empty data)
    team_ownership_result = _make_execute_result([{"slack_team_id": FAKE_TEAM_ID}])
    # teemo_workspaces: no existing workspaces (is_first = True)
    no_workspaces_result = _make_execute_result([])
    # teemo_workspaces insert: returns the new workspace row
    insert_result = _make_execute_result([FAKE_WORKSPACE_ROW])

    call_count = [0]

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            # assert_team_owner query
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = team_ownership_result
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            # Two calls: first is the count check, second is insert
            def _select(*a, **kw) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.order.return_value = sel
                sel.execute.return_value = no_workspaces_result
                return sel

            def _insert(payload: dict) -> MagicMock:
                ins = MagicMock()
                ins.execute.return_value = insert_result
                return ins

            tbl.select.side_effect = _select
            tbl.insert.side_effect = _insert

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.post(
            f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces",
            json={"name": "My Test Workspace"},
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["is_default_for_team"] is True, (
        f"Expected is_default_for_team=true for first workspace, got {body['is_default_for_team']}"
    )
    assert body["name"] == "My Test Workspace"
    assert body["slack_team_id"] == FAKE_TEAM_ID


# ---------------------------------------------------------------------------
# Test 2 — assert_team_owner returns 403 for cross-user access
# ---------------------------------------------------------------------------


def test_assert_team_owner_returns_403_for_wrong_user(app_client: TestClient) -> None:
    """Gherkin: Cross-user access is blocked with 403.

    Given an authenticated user who does NOT own the specified Slack team,
    When the user GETs /api/slack-teams/{team_id}/workspaces,
    Then the response is HTTP 403 Forbidden.

    Supabase mock:
    - teemo_slack_teams check returns empty data (user does not own team).
    This simulates a cross-user access attempt — the route must return 403.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            # Empty result: this user does not own the team
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces")

    assert resp.status_code == 403, (
        f"Expected 403 Forbidden for cross-user access, got {resp.status_code}: {resp.text}"
    )
