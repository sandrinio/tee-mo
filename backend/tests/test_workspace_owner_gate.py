"""STORY-025-05 — Workspace owner gate tests.

Covers 5 Gherkin scenarios from STORY-025-05 §2.1:

  Scenario 1 — Team owner can delete any workspace (not creator, but owner)
    Given caller has role='owner' in the Slack team
    And workspace.user_id != caller
    When DELETE /api/workspaces/{id} is called
    Then 204

  Scenario 2 — Workspace creator can delete their own workspace (not owner)
    Given workspace.user_id == caller
    And caller is NOT a team owner
    When DELETE /api/workspaces/{id} is called
    Then 204

  Scenario 3 — Member who is neither creator nor owner receives 403
    Given workspace.user_id != caller
    And caller is NOT a team owner
    And caller IS a member of the team
    When DELETE /api/workspaces/{id} is called
    Then 403
    And body == {"detail": "Only the workspace creator or a team owner can delete this workspace."}

  Scenario 4 — Non-team-member receives 404 (existence-leak guard)
    Given workspace.user_id != caller
    And caller is NOT a team owner
    And caller is NOT a member of the team
    When DELETE /api/workspaces/{id} is called
    Then 404
    And body == {"detail": "Workspace not found."}

  Scenario 5 — GET /api/workspaces/{id} surfaces is_owner and slack_team_name
    Given workspace.user_id == caller (so GET 200 succeeds)
    And caller has role='owner' in the Slack team
    And team domain is 'acme.slack.com'
    When GET /api/workspaces/{id} is called
    Then 200
    And JSON contains "is_owner": true
    And JSON contains "slack_team_name": "acme.slack.com"

Mock strategy:
  - ``get_current_user_id`` overridden via FastAPI dependency_overrides.
  - ``get_supabase`` patched at the route module level.
  - TestClient used WITHOUT the ``with`` context manager — avoids lifespan
    deadlock under pytest-asyncio auto mode (flashcard 2026-04-25 #lifespan).
  - ``is_team_owner`` is tested by controlling the teemo_slack_team_members
    query response (role='owner' vs empty), NOT by patching the helper directly.
    This tests the full code path end-to-end.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CALLER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())
FAKE_TEAM_ID = "T025_OWNER_GATE"
FAKE_WORKSPACE_ID = str(uuid.uuid4())
_NOW = datetime.now(timezone.utc).isoformat()

WORKSPACE_ROW: dict[str, Any] = {
    "id": FAKE_WORKSPACE_ID,
    "user_id": OTHER_USER_ID,  # default: workspace owned by someone else
    "name": "Test Workspace",
    "slack_team_id": FAKE_TEAM_ID,
    "ai_provider": None,
    "ai_model": None,
    "is_default_for_team": False,
    "bot_persona": None,
    "created_at": _NOW,
    "updated_at": _NOW,
}

# Workspace row where CALLER_ID is the creator.
WORKSPACE_ROW_CREATOR: dict[str, Any] = {
    **WORKSPACE_ROW,
    "user_id": CALLER_ID,  # caller IS the creator
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_execute_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data attribute holds the given list."""
    result = MagicMock()
    result.data = data
    return result


def _app_client(user_id: str = CALLER_ID):
    """Return a TestClient with get_current_user_id overridden."""
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_user() -> str:
        return user_id

    app.dependency_overrides[get_current_user_id] = _fake_user
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Scenario 1 — Team owner (not creator) can delete → 204
# ---------------------------------------------------------------------------


def test_delete_workspace_owner_not_creator_succeeds() -> None:
    """STORY-025-05 Scenario 1: Team owner with role='owner' can delete a workspace
    they did not create. Workspace row has user_id != CALLER_ID; membership probe
    returns role='owner' → is_team_owner returns True → 204.
    """
    client = _app_client()
    mock_sb = MagicMock()

    # Call sequence for DELETE with owner privileges:
    # 1. teemo_workspaces SELECT (fetch row by id) → returns row (user_id=OTHER_USER_ID)
    # 2. teemo_slack_team_members SELECT (is_team_owner check) → returns [role='owner']
    # 3. teemo_workspaces DELETE → returns deleted row (success)

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            call_count = {"n": 0}

            def _select(*_args, **_kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.execute.return_value = _make_execute_result([WORKSPACE_ROW])
                return sel

            def _delete() -> MagicMock:
                d = MagicMock()
                d.eq.return_value = d
                d.execute.return_value = _make_execute_result([WORKSPACE_ROW])
                return d

            tbl.select.side_effect = _select
            tbl.delete.side_effect = _delete

        elif name == "teemo_slack_team_members":
            # is_team_owner check: returns owner row → True
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"role": "owner"}])
            tbl.select.return_value = sel

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")
    finally:
        from app.main import app
        app.dependency_overrides.clear()

    assert resp.status_code == 204, (
        f"Expected 204 for team owner deleting another user's workspace, "
        f"got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Creator (not team owner) can delete their own workspace → 204
# ---------------------------------------------------------------------------


def test_delete_workspace_creator_not_owner_succeeds() -> None:
    """STORY-025-05 Scenario 2: Workspace creator (user_id == CALLER_ID) can delete
    their own workspace even if they are not a team owner. is_team_owner returns False
    (no owner row) but is_creator is True → 204.
    """
    client = _app_client()
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            def _select(*_args, **_kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                # Creator's workspace: user_id == CALLER_ID
                sel.execute.return_value = _make_execute_result([WORKSPACE_ROW_CREATOR])
                return sel

            def _delete() -> MagicMock:
                d = MagicMock()
                d.eq.return_value = d
                d.execute.return_value = _make_execute_result([WORKSPACE_ROW_CREATOR])
                return d

            tbl.select.side_effect = _select
            tbl.delete.side_effect = _delete

        elif name == "teemo_slack_team_members":
            # is_team_owner check: no owner row → False
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")
    finally:
        from app.main import app
        app.dependency_overrides.clear()

    assert resp.status_code == 204, (
        f"Expected 204 for creator deleting their own workspace, "
        f"got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Member (neither creator nor owner) receives 403
# ---------------------------------------------------------------------------


def test_delete_workspace_member_neither_returns_403() -> None:
    """STORY-025-05 Scenario 3: Caller is a team member but is neither the workspace
    creator nor a team owner → 403 with the exact detail message.

    Workspace row has user_id != CALLER_ID; is_team_owner returns False (no owner row);
    membership probe returns a 'member' role row → 403.
    """
    client = _app_client()
    mock_sb = MagicMock()

    # Track teemo_slack_team_members call count so we can distinguish:
    #   call 1: is_team_owner (queries .eq("role", "owner")) → should return []
    #   call 2: membership probe (no role filter) → should return [{"role": "member"}]
    member_call_count: dict[str, int] = {"n": 0}

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            def _select(*_args, **_kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.execute.return_value = _make_execute_result([WORKSPACE_ROW])
                return sel

            tbl.select.side_effect = _select

        elif name == "teemo_slack_team_members":
            # Both is_team_owner and membership probe query this table.
            # is_team_owner adds .eq("role","owner") before .limit — returns []
            # membership probe adds only .eq("slack_team_id") + .eq("user_id") — returns member row
            # We model this by using a counter: first call → [], second call → member row.
            def _select(*_args, **_kwargs) -> MagicMock:
                member_call_count["n"] += 1
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                if member_call_count["n"] == 1:
                    # is_team_owner call: returns empty (caller is not owner)
                    sel.execute.return_value = _make_execute_result([])
                else:
                    # membership probe: returns member row
                    sel.execute.return_value = _make_execute_result([{"role": "member"}])
                return sel

            tbl.select.side_effect = _select

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")
    finally:
        from app.main import app
        app.dependency_overrides.clear()

    assert resp.status_code == 403, (
        f"Expected 403 for team member who is neither creator nor owner, "
        f"got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body == {
        "detail": "Only the workspace creator or a team owner can delete this workspace."
    }, f"Unexpected 403 body: {body}"


# ---------------------------------------------------------------------------
# Scenario 4 — Non-team-member receives 404 (ADR-024 existence-leak guard)
# ---------------------------------------------------------------------------


def test_delete_workspace_non_member_returns_404() -> None:
    """STORY-025-05 Scenario 4: Caller is not a member of the Slack team → 404.

    Workspace row exists with user_id != CALLER_ID; is_team_owner returns False;
    membership probe returns empty → 404 (ADR-024 existence-leak guard).
    """
    client = _app_client()
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            def _select(*_args, **_kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.execute.return_value = _make_execute_result([WORKSPACE_ROW])
                return sel

            tbl.select.side_effect = _select

        elif name == "teemo_slack_team_members":
            # Both is_team_owner and membership probe return empty → no membership
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.delete(f"/api/workspaces/{FAKE_WORKSPACE_ID}")
    finally:
        from app.main import app
        app.dependency_overrides.clear()

    assert resp.status_code == 404, (
        f"Expected 404 for non-team-member (existence-leak guard), "
        f"got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body == {"detail": "Workspace not found."}, (
        f"Unexpected 404 body: {body}"
    )


# ---------------------------------------------------------------------------
# Scenario 5 — GET workspace surfaces is_owner and slack_team_name
# ---------------------------------------------------------------------------


def test_get_workspace_surfaces_is_owner_and_slack_team_name() -> None:
    """STORY-025-05 Scenario 5 (hotfix 2026-04-26): GET /api/workspaces/{id}
    returns is_owner=true and slack_team_name='Acme Slack' when the caller has
    role='owner' and the teemo_slack_teams row has slack_team_name='Acme Slack'.

    Hotfix swapped slack_team_name → slack_team_name since teemo_slack_teams has no
    `domain` column in the current schema. slack_team_name is populated at OAuth
    install (slack_oauth.py:207).

    GET uses user_id filter so WORKSPACE_ROW_CREATOR (user_id=CALLER_ID) is used.
    """
    client = _app_client()
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()
        if name == "teemo_workspaces":
            def _select(*_args, **_kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                # GET filters by user_id — use creator row so it matches
                sel.execute.return_value = _make_execute_result([WORKSPACE_ROW_CREATOR])
                return sel

            tbl.select.side_effect = _select

        elif name == "teemo_slack_team_members":
            # is_team_owner check: caller has role='owner'
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"role": "owner"}])
            tbl.select.return_value = sel

        elif name == "teemo_slack_teams":
            # Team name lookup for slack_team_name field
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([{"slack_team_name": "Acme Slack"}])
            tbl.select.return_value = sel

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}")
    finally:
        from app.main import app
        app.dependency_overrides.clear()

    assert resp.status_code == 200, (
        f"Expected 200 for GET workspace, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body.get("is_owner") is True, (
        f"Expected is_owner=true in GET response, got: {body.get('is_owner')}"
    )
    assert body.get("slack_team_name") == "Acme Slack", (
        f"Expected slack_team_name='Acme Slack' in GET response, got: {body.get('slack_team_name')}"
    )
