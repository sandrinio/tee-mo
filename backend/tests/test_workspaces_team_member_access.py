"""BUG-002 regression tests — Team members can access workspaces they created.

Covers 3 Gherkin scenarios from BUG-002 §5:

  Scenario 1 — Member GET 200 empty
    Given a Slack team owned by user A with one of user A's workspaces,
    And user B joined the team as "member" via OAuth callback
    (i.e. teemo_slack_team_members has a row for user B, teemo_slack_teams
    does NOT have owner_user_id = user_B),
    When user B calls GET /api/slack-teams/{team_id}/workspaces,
    Then the response is 200 OK with an empty list (not 403).

  Scenario 2 — Member POST 201
    Given user B is a member of the Slack team (same setup as Scenario 1),
    When user B calls POST /api/slack-teams/{team_id}/workspaces {"name": "B-ws"},
    Then the response is 201 Created.

  Scenario 3 — Owner unaffected
    Given user A is the owner of the Slack team (has a membership row with role=owner
    AND is also the owner_user_id in teemo_slack_teams),
    When user A calls GET /api/slack-teams/{team_id}/workspaces,
    Then the response still shows only user A's workspaces (not user B's).

Root cause fixed:
  ``assert_team_owner`` in workspaces.py queried ``teemo_slack_teams.owner_user_id``
  — only matched the installing owner. Renamed to ``assert_team_member`` and now
  queries ``teemo_slack_team_members.(slack_team_id, user_id)`` which matches any
  role (owner or member). See BUG-002 for full trace.

Mock strategy:
  - ``get_current_user_id`` overridden via FastAPI dependency_overrides.
  - ``get_supabase`` patched at ``app.api.routes.workspaces.get_supabase`` level
    so route-level DB calls are intercepted hermetically.
  - CRITICAL: Each mock explicitly sets ``teemo_slack_teams`` to return EMPTY data
    (simulating user B not being an owner) and ``teemo_slack_team_members`` to
    return a membership row (simulating user B being a member). This makes tests
    RED on pre-fix code (403 from owner check) and GREEN on post-fix code (200
    from membership check).
  - TestClient used WITHOUT the ``with`` context manager to avoid triggering the
    FastAPI lifespan (cron tasks would hang in the test environment).

ADR compliance:
  - ADR-024: workspace rows are still scoped by user_id; multi-user coexistence
    per S-09 multi-user membership design.
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

FAKE_TEAM_ID = "T0AS4M2U93L"

# User A is the owner of the Slack team.
USER_A_ID = str(uuid.uuid4())

# User B registered later and joined as "member" (NOT the team owner).
USER_B_ID = str(uuid.uuid4())

_NOW = datetime.now(timezone.utc).isoformat()

# User A's workspace row (owned by A, scoped to the team).
WORKSPACE_A_ROW: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "user_id": USER_A_ID,
    "name": "A's Workspace",
    "slack_team_id": FAKE_TEAM_ID,
    "ai_provider": None,
    "ai_model": None,
    "is_default_for_team": True,
    "bot_persona": None,
    "created_at": _NOW,
    "updated_at": _NOW,
}

# Workspace row that will be returned after user B creates one.
WORKSPACE_B_ROW: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "user_id": USER_B_ID,
    "name": "B-ws",
    "slack_team_id": FAKE_TEAM_ID,
    "ai_provider": None,
    "ai_model": None,
    "is_default_for_team": True,
    "bot_persona": None,
    "created_at": _NOW,
    "updated_at": _NOW,
}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_execute_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data attribute holds the given list."""
    result = MagicMock()
    result.data = data
    return result


def _make_member_get_supabase_mock() -> MagicMock:
    """Build a Supabase mock representing user B's state as a non-owner member.

    Table behaviour:
    - ``teemo_slack_teams``: returns EMPTY (user B is NOT the team owner).
    - ``teemo_slack_team_members``: returns a membership row (user B IS a member).
    - ``teemo_workspaces`` SELECT: returns empty (user B has no workspaces yet).

    Impact on tests:
    - Pre-fix code queries ``teemo_slack_teams.owner_user_id`` → empty → 403 (RED).
    - Post-fix code queries ``teemo_slack_team_members.user_id`` → row found → 200 (GREEN).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            # User B is NOT the owner — no row matches (owner_user_id != user_B).
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])  # empty → pre-fix 403
            tbl.select.return_value = sel

        elif name == "teemo_slack_team_members":
            # User B IS a member — membership row exists.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result(
                [{"slack_team_id": FAKE_TEAM_ID}]
            )
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            # User B has no workspaces yet.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        else:
            # Any other table: return empty by default to avoid accidental truthy.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table
    return mock_sb


def _make_member_post_supabase_mock() -> MagicMock:
    """Build a Supabase mock for user B's POST (create workspace) flow.

    Table behaviour:
    - ``teemo_slack_teams``: returns EMPTY (user B is NOT the team owner).
    - ``teemo_slack_team_members``: returns a membership row (user B IS a member).
    - ``teemo_workspaces`` SELECT: returns empty (no existing workspaces → is_first=True).
    - ``teemo_workspaces`` INSERT: returns the new workspace row.

    Impact:
    - Pre-fix: ``assert_team_owner`` queries ``teemo_slack_teams`` → empty → 403 (RED).
    - Post-fix: ``assert_team_member`` queries ``teemo_slack_team_members`` → row → 201 (GREEN).
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])  # user B not owner
            tbl.select.return_value = sel

        elif name == "teemo_slack_team_members":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result(
                [{"slack_team_id": FAKE_TEAM_ID}]
            )
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            def _select(*args, **kwargs) -> MagicMock:
                sel = MagicMock()
                sel.eq.return_value = sel
                sel.limit.return_value = sel
                sel.order.return_value = sel
                sel.execute.return_value = _make_execute_result([])  # no existing workspaces
                return sel

            def _insert(payload: dict) -> MagicMock:
                ins = MagicMock()
                ins.execute.return_value = _make_execute_result([WORKSPACE_B_ROW])
                return ins

            tbl.select.side_effect = _select
            tbl.insert.side_effect = _insert

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table
    return mock_sb


def _make_owner_get_supabase_mock() -> MagicMock:
    """Build a Supabase mock representing user A (owner) listing their workspaces.

    Owner (user A) has both:
    - A row in ``teemo_slack_teams`` with ``owner_user_id = USER_A_ID``.
    - A row in ``teemo_slack_team_members`` with ``role="owner"``.

    This mock satisfies BOTH the pre-fix assertion (teemo_slack_teams) and the
    post-fix assertion (teemo_slack_team_members), so Scenario 3 remains GREEN
    before and after the fix.

    The workspaces SELECT returns only user A's workspace.
    """
    mock_sb = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        if name == "teemo_slack_teams":
            # User A IS the owner.
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result(
                [{"slack_team_id": FAKE_TEAM_ID}]
            )
            tbl.select.return_value = sel

        elif name == "teemo_slack_team_members":
            # User A also has a membership row (role=owner).
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result(
                [{"slack_team_id": FAKE_TEAM_ID}]
            )
            tbl.select.return_value = sel

        elif name == "teemo_workspaces":
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.order.return_value = sel
            sel.execute.return_value = _make_execute_result([WORKSPACE_A_ROW])
            tbl.select.return_value = sel

        else:
            sel = MagicMock()
            sel.eq.return_value = sel
            sel.limit.return_value = sel
            sel.execute.return_value = _make_execute_result([])
            tbl.select.return_value = sel

        return tbl

    mock_sb.table.side_effect = _table
    return mock_sb


# ---------------------------------------------------------------------------
# Scenario 1 — Member GET returns 200 with empty list (not 403)
# ---------------------------------------------------------------------------


def test_member_get_workspaces_returns_200_empty_list() -> None:
    """BUG-002 §5 Scenario 1 — Member GET 200 empty.

    Given user B is a member (not owner) of the Slack team,
    When user B calls GET /api/slack-teams/{team_id}/workspaces,
    Then the response is 200 OK with an empty list — NOT 403.

    Pre-fix (RED): assert_team_owner queries teemo_slack_teams.owner_user_id.
    The mock returns empty for teemo_slack_teams → 403 raised.

    Post-fix (GREEN): assert_team_member queries teemo_slack_team_members.user_id.
    The mock returns a membership row → passes → 200 [].
    """
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_user_b() -> str:
        return USER_B_ID

    app.dependency_overrides[get_current_user_id] = _fake_user_b
    # Use TestClient WITHOUT context manager — avoids triggering lifespan cron tasks.
    client = TestClient(app, raise_server_exceptions=False)

    mock_sb = _make_member_get_supabase_mock()

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.get(f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, (
        f"Expected 200 for team member GET workspaces, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body == [], f"Expected empty list for new member, got {body}"


# ---------------------------------------------------------------------------
# Scenario 2 — Member POST returns 201 Created
# ---------------------------------------------------------------------------


def test_member_post_workspace_returns_201() -> None:
    """BUG-002 §5 Scenario 2 — Member POST 201.

    Given user B is a member (not owner) of the Slack team,
    When user B calls POST /api/slack-teams/{team_id}/workspaces {"name": "B-ws"},
    Then the response is 201 Created.

    Pre-fix (RED): assert_team_owner blocks user B with 403.
    Post-fix (GREEN): assert_team_member allows user B to create a workspace.
    """
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_user_b() -> str:
        return USER_B_ID

    app.dependency_overrides[get_current_user_id] = _fake_user_b
    client = TestClient(app, raise_server_exceptions=False)

    mock_sb = _make_member_post_supabase_mock()

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.post(
                f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces",
                json={"name": "B-ws"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 201, (
        f"Expected 201 for team member POST workspace, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body["name"] == "B-ws", f"Expected workspace name 'B-ws', got {body.get('name')}"
    assert body["slack_team_id"] == FAKE_TEAM_ID


# ---------------------------------------------------------------------------
# Scenario 3 — Owner is unaffected (still sees their own workspaces)
# ---------------------------------------------------------------------------


def test_owner_get_workspaces_still_returns_200_with_own_workspaces() -> None:
    """BUG-002 §5 Scenario 3 — Owner unaffected.

    Given user A is the owner of the Slack team (rows in both teemo_slack_teams
    and teemo_slack_team_members with role=owner),
    When user A calls GET /api/slack-teams/{team_id}/workspaces,
    Then the response still shows only user A's workspaces (not user B's).

    This confirms the fix does not break the existing owner use-case.
    Both pre-fix and post-fix code return 200 for owners because:
    - Pre-fix: teemo_slack_teams returns owner row → passes → 200.
    - Post-fix: teemo_slack_team_members returns owner row → passes → 200.
    """
    from app.main import app
    from app.api.deps import get_current_user_id

    async def _fake_user_a() -> str:
        return USER_A_ID

    app.dependency_overrides[get_current_user_id] = _fake_user_a
    client = TestClient(app, raise_server_exceptions=False)

    mock_sb = _make_owner_get_supabase_mock()

    try:
        with patch("app.api.routes.workspaces.get_supabase", return_value=mock_sb):
            resp = client.get(f"/api/slack-teams/{FAKE_TEAM_ID}/workspaces")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200, (
        f"Expected 200 for owner GET workspaces, got {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert isinstance(body, list), "Expected a list"
    assert len(body) == 1, f"Expected 1 workspace for owner, got {len(body)}"
    assert body[0]["user_id"] == USER_A_ID, (
        f"Expected workspace owned by user A ({USER_A_ID}), got user_id={body[0].get('user_id')}"
    )
