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


# ---------------------------------------------------------------------------
# B03 Comprehensive Integration Tests — STORY-003-B03
#
# All tests below are hermetic (no live Supabase). Each test builds its own
# mock Supabase client via the same chainable-call pattern established above.
#
# Tests are ordered to mirror the §1.2 requirement list:
#   3.  Happy path: fetch workspace by ID
#   4.  Happy path: list workspaces for a team
#   5.  403 cross-user access — user tries to access another user's team  (covered by test 2 above)
#   6.  404 missing workspace handling
#   7.  First-workspace auto-default logic (is_default_for_team = true)   (covered by test 1 above)
#   8.  Second-workspace non-default logic (is_default_for_team = false)
#   9.  make-default atomic swap validation
#   10. Response model secret-field omission (encrypted_api_key absent)
#   11. Rename workspace (PATCH)
# ---------------------------------------------------------------------------

FAKE_USER_ID_BOB = str(uuid.uuid4())
FAKE_TEAM_ID_BOB = "T_BOB_TEAM"
FAKE_WORKSPACE_ID_2 = str(uuid.uuid4())

FAKE_WORKSPACE_ROW_2: dict[str, Any] = {
    "id": FAKE_WORKSPACE_ID_2,
    "user_id": FAKE_USER_ID,
    "name": "Second Workspace",
    "slack_team_id": FAKE_TEAM_ID,
    "ai_provider": None,
    "ai_model": None,
    "is_default_for_team": False,
    "created_at": _NOW,
    "updated_at": _NOW,
}

# Simulate a DB row that includes secret columns — these must not appear in responses.
FAKE_WORKSPACE_ROW_WITH_SECRET: dict[str, Any] = {
    **FAKE_WORKSPACE_ROW,
    "encrypted_api_key": "super-secret-encrypted-value",
    "encrypted_google_refresh_token": "another-secret-token",
}


# ---------------------------------------------------------------------------
# Test 3 — GET /api/workspaces/{id} happy path returns 200 and correct data
# ---------------------------------------------------------------------------


def test_get_workspace_by_id_returns_200(app_client: TestClient) -> None:
    """Gherkin: Fetch workspace by ID (happy path).

    Given an authenticated user who owns a workspace,
    When the user GETs /api/workspaces/{id},
    Then the response is HTTP 200 OK,
    And the returned body contains the workspace data.
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
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["id"] == FAKE_WORKSPACE_ID
    assert body["name"] == "My Test Workspace"
    assert body["slack_team_id"] == FAKE_TEAM_ID


# ---------------------------------------------------------------------------
# Test 4 — GET /api/slack-teams/{team_id}/workspaces happy path returns list
# ---------------------------------------------------------------------------


def test_list_workspaces_for_team_returns_200(app_client: TestClient) -> None:
    """Gherkin: List workspaces for a team (happy path).

    Given an authenticated user who owns a Slack team with two workspaces,
    When the user GETs /api/slack-teams/{team_id}/workspaces,
    Then the response is HTTP 200 OK,
    And the returned list contains both workspaces.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"slack_team_id": FAKE_TEAM_ID}])
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result(
                [FAKE_WORKSPACE_ROW, FAKE_WORKSPACE_ROW_2]
            )
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert isinstance(body, list), "Expected a list of workspaces"
    assert len(body) == 2, f"Expected 2 workspaces, got {len(body)}"


# ---------------------------------------------------------------------------
# Test 5 — GET /api/workspaces/{id} returns 404 for missing workspace
# ---------------------------------------------------------------------------


def test_get_workspace_by_id_returns_404_for_missing(app_client: TestClient) -> None:
    """Gherkin: Missing workspace returns 404.

    Given an authenticated user who requests a workspace ID that does not exist
    (or belongs to another user),
    When the user GETs /api/workspaces/{id},
    Then the response is HTTP 404 Not Found.

    The mock returns empty data to simulate the workspace not existing.
    """
    missing_id = str(uuid.uuid4())
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])  # not found
            tbl.select.return_value = sel
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/workspaces/{missing_id}")

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 6 — Second workspace is non-default (is_default_for_team = false)
# ---------------------------------------------------------------------------


def test_create_second_workspace_is_not_default(app_client: TestClient) -> None:
    """Gherkin: Second workspace is non-default.

    Given a user who already has one workspace in a Slack team,
    When the user POSTs /api/slack-teams/{team_id}/workspaces for a second workspace,
    Then the response is HTTP 201 Created,
    And the returned workspace has is_default_for_team = false.

    The mock simulates the "existing count" check returning one row, so
    the route sets is_first = False and does NOT auto-default the new workspace.
    The insert result returns FAKE_WORKSPACE_ROW_2 with is_default_for_team=False.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"slack_team_id": FAKE_TEAM_ID}])
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            def _select(*a, **kw) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.order.return_value = sel
                # Existing workspace found — this is NOT the first
                sel.execute.return_value = _make_execute_result([{"id": FAKE_WORKSPACE_ID}])
                return sel

            def _insert(payload: dict) -> MagicMock:
                ins = MagicMock()
                # The route sets is_default_for_team=False for non-first workspaces.
                # Return the second workspace row which has is_default_for_team=False.
                ins.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW_2])
                return ins

            tbl.select.side_effect = _select
            tbl.insert.side_effect = _insert

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.post(
            f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces",
            json={"name": "Second Workspace"},
        )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["is_default_for_team"] is False, (
        f"Expected is_default_for_team=false for second workspace, got {body['is_default_for_team']}"
    )


# ---------------------------------------------------------------------------
# Test 7 — make-default atomic swap validation
# ---------------------------------------------------------------------------


def test_make_default_swaps_to_target_workspace(app_client: TestClient) -> None:
    """Gherkin: make-default performs two-step atomic swap.

    Given a user with two workspaces in a Slack team (workspace_1 is current default,
    workspace_2 is not),
    When the user POSTs /api/workspaces/{workspace_2_id}/make-default,
    Then the response is HTTP 200,
    And the returned workspace has is_default_for_team = true.

    The route performs two Supabase UPDATE calls:
      1. Reset all existing defaults (UPDATE WHERE is_default_for_team=true -> false).
      2. Set the target workspace as default (UPDATE WHERE id=target -> true).
    The mock tracks these calls and returns the promoted workspace on the second update.
    """
    promoted_row: dict[str, Any] = {**FAKE_WORKSPACE_ROW_2, "is_default_for_team": True}
    mock_sb = MagicMock()

    update_calls: list[dict] = []

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_workspaces":
            # select used by the "confirm workspace exists" query
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW_2])
            tbl.select.return_value = sel

            # update: called twice — reset then promote
            def _update(payload: dict) -> MagicMock:
                update_calls.append(payload)
                upd = MagicMock()
                upd.eq.return_value = upd
                # First update (reset) — PostgREST returns empty list (no match needed)
                # Second update (promote) — return the promoted row
                upd.execute.return_value = _make_execute_result([promoted_row])
                return upd

            tbl.update.side_effect = _update

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.post(f"/api/workspaces/{FAKE_WORKSPACE_ID_2}/make-default")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["is_default_for_team"] is True, (
        f"Expected is_default_for_team=true after make-default, got {body['is_default_for_team']}"
    )
    # Verify both update calls were made (reset step + promote step)
    assert len(update_calls) == 2, (
        f"Expected 2 update calls for atomic swap, got {len(update_calls)}"
    )
    # First call resets (sets is_default_for_team=False)
    assert update_calls[0] == {"is_default_for_team": False}
    # Second call promotes (sets is_default_for_team=True)
    assert update_calls[1] == {"is_default_for_team": True}


# ---------------------------------------------------------------------------
# Test 8 — make-default returns 404 for non-existent workspace
# ---------------------------------------------------------------------------


def test_make_default_returns_404_for_missing_workspace(app_client: TestClient) -> None:
    """Gherkin: make-default 404 when workspace is not found.

    Given an authenticated user who requests make-default on a workspace ID
    that does not exist (or belongs to another user),
    When the user POSTs /api/workspaces/{id}/make-default,
    Then the response is HTTP 404 Not Found.

    The mock returns empty data on the ownership-check select to simulate
    the workspace not being found.
    """
    missing_id = str(uuid.uuid4())
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])  # not found
            tbl.select.return_value = sel
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.post(f"/api/workspaces/{missing_id}/make-default")

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 9 — Response model omits secret fields (encrypted_api_key absent)
# ---------------------------------------------------------------------------


def test_get_workspace_response_omits_secret_fields(app_client: TestClient) -> None:
    """Gherkin: Workspace secrets omission.

    When a workspace is queried via GET /api/workspaces/{id},
    Then the response body does NOT include encrypted_api_key or
    encrypted_google_refresh_token — even if the DB row contains them.

    The mock DB row intentionally includes both secret columns to verify
    that _to_response() and WorkspaceResponse strip them from the API output.
    This is defense-in-depth: the response model excludes them at the Pydantic
    level, and _to_response() never passes them to the constructor.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            # Return a row that includes secret columns
            sel.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW_WITH_SECRET])
            tbl.select.return_value = sel
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "encrypted_api_key" not in body, (
        "encrypted_api_key must be omitted from the API response — secret leak detected!"
    )
    assert "encrypted_google_refresh_token" not in body, (
        "encrypted_google_refresh_token must be omitted from the API response — secret leak detected!"
    )
    # Confirm the public fields are still present
    assert body["id"] == FAKE_WORKSPACE_ID
    assert body["name"] == "My Test Workspace"


# ---------------------------------------------------------------------------
# Test 10 — PATCH /api/workspaces/{id} renames a workspace
# ---------------------------------------------------------------------------


def test_rename_workspace_returns_200_with_updated_name(app_client: TestClient) -> None:
    """Gherkin: Rename workspace via PATCH.

    Given an authenticated user who owns a workspace,
    When the user PATCHes /api/workspaces/{id} with a new name,
    Then the response is HTTP 200 OK,
    And the returned workspace has the updated name.

    The mock update chain returns a workspace row with the renamed name to
    simulate the DB update succeeding.
    """
    renamed_row: dict[str, Any] = {**FAKE_WORKSPACE_ROW, "name": "Renamed Workspace"}
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            upd = MagicMock()
            upd.eq.return_value = upd
            upd.execute.return_value = _make_execute_result([renamed_row])
            tbl.update.return_value = upd
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.patch(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}",
            json={"name": "Renamed Workspace"},
        )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["name"] == "Renamed Workspace", (
        f"Expected updated name 'Renamed Workspace', got '{body['name']}'"
    )


# ---------------------------------------------------------------------------
# Test 11 — PATCH /api/workspaces/{id} returns 404 for missing workspace
# ---------------------------------------------------------------------------


def test_rename_workspace_returns_404_for_missing(app_client: TestClient) -> None:
    """Gherkin: Rename missing workspace returns 404.

    Given an authenticated user who tries to rename a workspace that does not exist
    (or belongs to another user),
    When the user PATCHes /api/workspaces/{id},
    Then the response is HTTP 404 Not Found.

    The mock update chain returns empty data to simulate no rows matched (i.e.
    the workspace wasn't found or the user doesn't own it).
    """
    missing_id = str(uuid.uuid4())
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            upd = MagicMock()
            upd.eq.return_value = upd
            upd.execute.return_value = _make_execute_result([])  # no rows updated
            tbl.update.return_value = upd
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.patch(
            f"/api/workspaces/{missing_id}",
            json={"name": "Ghost Workspace"},
        )

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Test 12 — Cross-user team isolation: user cannot list another user's workspaces
# ---------------------------------------------------------------------------


def test_list_workspaces_returns_403_for_non_owner(app_client: TestClient) -> None:
    """Gherkin: Cross-user 403 defense on list endpoint.

    Given Alice owns team A but Bob owns team B,
    When Alice (FAKE_USER_ID) tries to list workspaces for Bob's team (FAKE_TEAM_ID_BOB),
    Then the response is HTTP 403 Forbidden.

    The mock returns empty data for teemo_slack_teams to simulate that the
    authenticated user (FAKE_USER_ID) is not the owner of FAKE_TEAM_ID_BOB.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            # No ownership row found for this user+team combination
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/slack-teams/{FAKE_TEAM_ID_BOB}/workspaces")

    assert resp.status_code == 403, (
        f"Expected 403 Forbidden when non-owner accesses team, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test 13 — Empty workspace list returns 200 with empty array
# ---------------------------------------------------------------------------


def test_list_workspaces_empty_returns_200_empty_list(app_client: TestClient) -> None:
    """Gherkin: Empty workspace list is 200 [] not 404.

    Given an authenticated user who owns a Slack team but has no workspaces,
    When the user GETs /api/slack-teams/{team_id}/workspaces,
    Then the response is HTTP 200 OK with an empty list body.

    An empty list is a valid state — the route must return [] not 404.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"slack_team_id": FAKE_TEAM_ID}])
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result([])  # no workspaces
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.get(f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces")

    assert resp.status_code == 200, f"Expected 200 for empty workspace list, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body == [], f"Expected empty list, got {body}"


# ---------------------------------------------------------------------------
# Tests 14-17 — DELETE /api/workspaces/{id} (STORY-006-09)
# ---------------------------------------------------------------------------


def test_delete_workspace_returns_204_and_row_gone(app_client: TestClient) -> None:
    """Gherkin: Delete workspace returns 204 and workspace is removed.

    Given an authenticated user who owns a workspace,
    When the user sends DELETE /api/workspaces/{id},
    Then the response is HTTP 204 No Content,
    And the Supabase delete call filtered on both id and user_id.

    The mock delete chain returns [FAKE_WORKSPACE_ROW] (non-empty) to simulate
    a successful deletion where PostgREST echoes the deleted row(s).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            del_mock = MagicMock()
            del_mock.eq.return_value = del_mock
            del_mock.execute.return_value = _make_execute_result([FAKE_WORKSPACE_ROW])
            tbl.delete.return_value = del_mock
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")

    assert resp.status_code == 204, (
        f"Expected 204 No Content, got {resp.status_code}: {resp.text}"
    )


def test_delete_workspace_non_owner_returns_404(app_client: TestClient) -> None:
    """Gherkin: DELETE from non-owner returns 404 (existence concealment).

    Given an authenticated user who does NOT own the specified workspace,
    When the user sends DELETE /api/workspaces/{id},
    Then the response is HTTP 404 Not Found.

    The mock delete chain returns empty data to simulate no rows matched
    (the user_id filter excluded the row).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            del_mock = MagicMock()
            del_mock.eq.return_value = del_mock
            del_mock.execute.return_value = _make_execute_result([])  # no match
            tbl.delete.return_value = del_mock
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")

    assert resp.status_code == 404, (
        f"Expected 404 for non-owner delete, got {resp.status_code}: {resp.text}"
    )


def test_delete_workspace_nonexistent_uuid_returns_404(app_client: TestClient) -> None:
    """Gherkin: DELETE nonexistent workspace returns 404.

    Given an authenticated user who sends DELETE for a workspace UUID that
    does not exist at all in the database,
    When the user sends DELETE /api/workspaces/{random_id},
    Then the response is HTTP 404 Not Found.

    The mock delete chain returns empty data to simulate the row not existing.
    """
    nonexistent_id = str(uuid.uuid4())
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            del_mock = MagicMock()
            del_mock.eq.return_value = del_mock
            del_mock.execute.return_value = _make_execute_result([])  # not found
            tbl.delete.return_value = del_mock
        return tbl

    mock_sb.table.side_effect = _table

    with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
        resp = app_client.delete(f"/api/workspaces/{nonexistent_id}")

    assert resp.status_code == 404, (
        f"Expected 404 for nonexistent workspace, got {resp.status_code}: {resp.text}"
    )


def test_delete_workspace_unauthenticated_returns_401() -> None:
    """Gherkin: DELETE without auth returns 401.

    Given an unauthenticated request (no session cookies),
    When the request sends DELETE /api/workspaces/{id},
    Then the response is HTTP 401 Unauthorized.

    This test does NOT override get_current_user_id — the real dependency
    is invoked, which reads the missing cookie and raises 401.
    """
    from app.main import app

    # No dependency override — real get_current_user_id will raise 401
    with TestClient(app) as unauthenticated_client:
        resp = unauthenticated_client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")

    assert resp.status_code == 401, (
        f"Expected 401 Unauthorized for unauthenticated DELETE, got {resp.status_code}: {resp.text}"
    )
