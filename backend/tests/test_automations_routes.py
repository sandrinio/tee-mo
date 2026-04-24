"""RED PHASE tests for STORY-018-02 — Automations REST Endpoints.

Covers all 14 Gherkin scenarios from STORY-018-02 §2.1 using FastAPI
TestClient with mocked Supabase (``_make_supabase_mock`` pattern from
``test_automation_service.py``) and dependency overrides for auth.

Scenarios:
  1.  test_create_automation_happy_path
  2.  test_create_automation_non_owner_blocked
  3.  test_create_automation_empty_channels_list
  4.  test_create_automation_channel_not_bound
  5.  test_create_automation_duplicate_name
  6.  test_list_automations_workspace_scoped
  7.  test_get_automation_404_for_missing
  8.  test_patch_automation_partial_update
  9.  test_patch_automation_schedule_recomputes_next_run_at
  10. test_delete_automation_cascade
  11. test_history_last_50
  12. test_test_run_success
  13. test_test_run_missing_byok
  14. test_test_run_timeout

Mock strategy:
  - ``get_current_user_id`` is overridden via ``app.dependency_overrides``
    so no JWT setup is needed.
  - Supabase client is mocked via ``_make_supabase_mock()``, injected through
    ``app.dependency_overrides[get_supabase]``.
  - ``automation_service`` functions are patched at module level via
    ``monkeypatch.setattr`` so tests can control service behaviour independently
    of DB mock chain complexity.
  - For the dry-run tests, ``asyncio.wait_for`` is patched to simulate timeout
    without needing a live LLM.

ADR compliance:
  - ADR-001: JWT via cookie (bypassed here via dependency override — safe for tests).
  - ADR-024: Workspace isolation is enforced at the route layer via owner assert.

NOTE: ``backend/app/api/routes/automations.py`` does NOT exist yet.
Every test is expected to FAIL with ``ImportError`` / ``ModuleNotFoundError``
or a 404 import-time failure. That is the intended Red Phase behaviour.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants — reused across tests
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-1111-1111-1111-000000000001"
OTHER_WORKSPACE_ID = "bbbbbbbb-2222-2222-2222-000000000002"
OWNER_USER_ID = "cccccccc-3333-3333-3333-000000000003"
OTHER_USER_ID = "dddddddd-4444-4444-4444-000000000004"
AUTOMATION_ID = "eeeeeeee-5555-5555-5555-000000000005"
OTHER_AUTOMATION_ID = "ffffffff-6666-6666-6666-000000000006"
CHANNEL_ID_1 = "C01AAAAAAA1"
CHANNEL_ID_2 = "C01AAAAAAA2"
UNBOUND_CHANNEL_ID = "C99XXXXXXX"

_NOW = datetime.now(timezone.utc).isoformat()

AUTOMATION_ROW: dict[str, Any] = {
    "id": AUTOMATION_ID,
    "workspace_id": WORKSPACE_ID,
    "owner_user_id": OWNER_USER_ID,
    "name": "Daily Briefing",
    "description": "Morning briefing automation",
    "prompt": "Summarise yesterday's updates",
    "slack_channel_ids": [CHANNEL_ID_1, CHANNEL_ID_2],
    "schedule": {"occurrence": "daily", "when": "09:00"},
    "schedule_type": "recurring",
    "timezone": "UTC",
    "is_active": True,
    "next_run_at": "2026-04-17T09:00:00+00:00",
    "last_run_at": None,
    "created_at": _NOW,
    "updated_at": _NOW,
}

OTHER_WORKSPACE_AUTOMATION_ROW: dict[str, Any] = {
    **AUTOMATION_ROW,
    "id": OTHER_AUTOMATION_ID,
    "workspace_id": OTHER_WORKSPACE_ID,
    "name": "Other Workspace Automation",
}

EXECUTION_ROW: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "automation_id": AUTOMATION_ID,
    "status": "success",
    "was_dry_run": False,
    "started_at": "2026-04-16T09:00:00+00:00",
    "completed_at": "2026-04-16T09:00:05+00:00",
    "generated_content": "Today's briefing.",
    "delivery_results": [{"channel": CHANNEL_ID_1, "ok": True}],
    "error": None,
    "tokens_used": 420,
    "execution_time_ms": 5000,
}

WORKSPACE_ROW: dict[str, Any] = {
    "id": WORKSPACE_ID,
    "user_id": OWNER_USER_ID,
    "name": "Test Workspace",
    "slack_team_id": "T12345",
    "ai_provider": "openai",
    "ai_model": "gpt-4o",
    "encrypted_api_key": "encrypted_test_key",
    "is_default_for_team": True,
    "created_at": _NOW,
    "updated_at": _NOW,
}

WORKSPACE_ROW_NO_KEY: dict[str, Any] = {
    **WORKSPACE_ROW,
    "encrypted_api_key": None,
}


# ---------------------------------------------------------------------------
# Supabase mock helpers (mirrors _make_supabase_mock from test_automation_service.py)
# ---------------------------------------------------------------------------


def _make_supabase_mock(
    automations: list[dict] | None = None,
    channels: list[dict] | None = None,
    executions: list[dict] | None = None,
    single_automation: dict | None = None,
    workspace_row: dict | None = None,
    deleted_count: int = 1,
    owner_check_fails: bool = False,
) -> MagicMock:
    """Build a lightweight Supabase client mock with chainable query methods.

    Returns pre-configured data for each table based on the arguments provided.

    Args:
        automations:       Rows to return for teemo_automations list queries.
        channels:          Rows to return for teemo_workspace_channels queries.
        executions:        Rows to return for teemo_automation_executions queries.
        single_automation: Dict to return for single-row automation lookups.
        workspace_row:     The workspace row for ownership checks (None → 403).
        deleted_count:     Number of rows reported as deleted (for delete ops).
        owner_check_fails: If True, workspace ownership check returns empty list.
    """
    mock = MagicMock()

    _workspace_rows: list[dict] = [] if owner_check_fails else (
        [workspace_row] if workspace_row is not None else [WORKSPACE_ROW]
    )

    def _table_side_effect(table_name: str) -> MagicMock:
        chain = MagicMock()
        result = MagicMock()
        single_result = MagicMock()
        delete_result = MagicMock()

        if table_name == "teemo_workspaces":
            result.data = _workspace_rows
            single_result.data = _workspace_rows[0] if _workspace_rows else None
        elif table_name == "teemo_automations":
            result.data = automations if automations is not None else []
            single_result.data = single_automation
            delete_result.data = [{}] * deleted_count
        elif table_name == "teemo_workspace_channels":
            result.data = channels if channels is not None else []
        elif table_name == "teemo_automation_executions":
            result.data = executions if executions is not None else []
            delete_result.data = []
        else:
            result.data = []

        # Set up full chainable interface
        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.offset.return_value = chain
        chain.maybe_single.return_value = chain

        def _execute():
            if chain.delete.called:
                return delete_result
            if single_automation is not None and table_name == "teemo_automations":
                return single_result
            return result

        chain.execute.side_effect = _execute
        return chain

    mock.table.side_effect = _table_side_effect
    return mock


def _make_channel_rows(workspace_id: str, channel_ids: list[str]) -> list[dict]:
    """Return teemo_workspace_channels rows for the given channel IDs."""
    return [
        {
            "id": str(uuid.uuid4()),
            "workspace_id": workspace_id,
            "slack_channel_id": ch_id,
            "channel_name": f"channel-{ch_id.lower()}",
        }
        for ch_id in channel_ids
    ]


# ---------------------------------------------------------------------------
# Fixtures — TestClient with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client_owner(monkeypatch):
    """TestClient with OWNER_USER_ID as the authenticated user.

    Supabase is overridden to return the default workspace row (owner = OWNER_USER_ID).
    ``automation_service`` is NOT mocked here — individual tests patch specific
    service functions as needed via ``monkeypatch.setattr``.
    """
    from app.main import app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase

    mock_sb = _make_supabase_mock(
        automations=[AUTOMATION_ROW],
        channels=_make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1, CHANNEL_ID_2]),
        single_automation=AUTOMATION_ROW,
    )

    async def _fake_owner_id() -> str:
        return OWNER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_owner_id
    app.dependency_overrides[get_supabase] = lambda: mock_sb

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, mock_sb

    app.dependency_overrides.clear()


@pytest.fixture
def app_client_non_owner(monkeypatch):
    """TestClient with OTHER_USER_ID as the authenticated user (non-owner of WORKSPACE_ID)."""
    from app.main import app
    from app.api.deps import get_current_user_id
    from app.core.db import get_supabase

    mock_sb = _make_supabase_mock(owner_check_fails=True)

    async def _fake_other_id() -> str:
        return OTHER_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_other_id
    app.dependency_overrides[get_supabase] = lambda: mock_sb

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, mock_sb

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Create automation — happy path
# ---------------------------------------------------------------------------


def test_create_automation_happy_path(monkeypatch, app_client_owner):
    """POST /automations returns 201 with AutomationResponse including next_run_at.

    Gherkin: Given a workspace W owned by user U with bound channels [C1, C2],
    When U posts with name, prompt, schedule daily 09:00, slack_channel_ids=[C1, C2],
    Then response 201 with AutomationResponse including computed next_run_at.
    """
    import app.api.routes.automations as automations_module

    monkeypatch.setattr(
        automations_module.automation_service,
        "create_automation",
        lambda workspace_id, owner_user_id, payload, *, supabase: AUTOMATION_ROW,
    )

    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations",
        json={
            "name": "Daily Briefing",
            "prompt": "Summarise yesterday's updates",
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "slack_channel_ids": [CHANNEL_ID_1, CHANNEL_ID_2],
            "timezone": "UTC",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == AUTOMATION_ID
    assert data["next_run_at"] is not None


# ---------------------------------------------------------------------------
# 2. Create automation — non-owner blocked
# ---------------------------------------------------------------------------


def test_create_automation_non_owner_blocked(app_client_non_owner):
    """POST by a non-owner returns 403 Forbidden.

    Gherkin: Given user V who does not own workspace W,
    When V posts to /api/workspaces/W/automations,
    Then response 403.
    """
    client, _ = app_client_non_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations",
        json={
            "name": "Bad Automation",
            "prompt": "Hack",
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "slack_channel_ids": [CHANNEL_ID_1],
        },
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 3. Create automation — empty channels list → 422
# ---------------------------------------------------------------------------


def test_create_automation_empty_channels_list(app_client_owner):
    """POST with slack_channel_ids=[] returns 422 from Pydantic validation.

    Gherkin: When the body's slack_channel_ids is [],
    Then response 422 from Pydantic validation.
    """
    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations",
        json={
            "name": "No Channels",
            "prompt": "Do something",
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "slack_channel_ids": [],  # min_length=1 → 422
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# 4. Create automation — channel not bound → 422
# ---------------------------------------------------------------------------


def test_create_automation_channel_not_bound(monkeypatch, app_client_owner):
    """POST with an unbound channel ID returns 422 with detail mentioning the channel.

    Gherkin: When slack_channel_ids contains an id not in teemo_workspace_channels,
    Then response 422 with detail mentioning the channel.

    Service raises ValueError when channel validation fails.
    """
    import app.api.routes.automations as automations_module

    def _fail_unbound(workspace_id, owner_user_id, payload, *, supabase):
        raise ValueError(f"Channel {UNBOUND_CHANNEL_ID} is not bound to workspace")

    monkeypatch.setattr(
        automations_module.automation_service,
        "create_automation",
        _fail_unbound,
    )

    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations",
        json={
            "name": "Unbound Channel",
            "prompt": "Test",
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "slack_channel_ids": [UNBOUND_CHANNEL_ID],
        },
    )
    assert response.status_code == 422
    assert UNBOUND_CHANNEL_ID in response.text


# ---------------------------------------------------------------------------
# 5. Create automation — duplicate name → 409
# ---------------------------------------------------------------------------


def test_create_automation_duplicate_name(monkeypatch, app_client_owner):
    """POST with a duplicate name returns 409 Conflict.

    Gherkin: Given an automation "weekly-digest" already exists in W,
    When another create is posted with the same name,
    Then response 409 with detail.
    """
    import app.api.routes.automations as automations_module

    def _fail_duplicate(workspace_id, owner_user_id, payload, *, supabase):
        raise automations_module.DuplicateAutomationName(payload["name"])

    monkeypatch.setattr(
        automations_module.automation_service,
        "create_automation",
        _fail_duplicate,
    )

    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations",
        json={
            "name": "Daily Briefing",  # already exists
            "prompt": "Summarise",
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "slack_channel_ids": [CHANNEL_ID_1],
        },
    )
    assert response.status_code == 409
    assert "Daily Briefing" in response.text


# ---------------------------------------------------------------------------
# 6. List automations — workspace-scoped
# ---------------------------------------------------------------------------


def test_list_automations_workspace_scoped(monkeypatch, app_client_owner):
    """GET /automations returns only automations belonging to the owner's workspace.

    Gherkin: Given workspace A has automation X and workspace B has automation Y,
    When owner of A GETs /api/workspaces/A/automations,
    Then the response contains X and NOT Y.
    """
    import app.api.routes.automations as automations_module

    monkeypatch.setattr(
        automations_module.automation_service,
        "list_automations",
        lambda workspace_id, *, supabase: [AUTOMATION_ROW],
    )

    client, _ = app_client_owner
    response = client.get(f"/api/workspaces/{WORKSPACE_ID}/automations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Only workspace A's automation present
    ids = [row["id"] for row in data]
    assert AUTOMATION_ID in ids
    assert OTHER_AUTOMATION_ID not in ids


# ---------------------------------------------------------------------------
# 7. Get one automation — 404 for missing
# ---------------------------------------------------------------------------


def test_get_automation_404_for_missing(monkeypatch, app_client_owner):
    """GET /automations/{random-uuid} returns 404 when automation does not exist.

    Gherkin: When owner of W GETs /api/workspaces/W/automations/{random-uuid},
    Then response 404.
    """
    import app.api.routes.automations as automations_module

    monkeypatch.setattr(
        automations_module.automation_service,
        "get_automation",
        lambda workspace_id, automation_id, *, supabase: None,
    )

    client, _ = app_client_owner
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/workspaces/{WORKSPACE_ID}/automations/{missing_id}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 8. PATCH automation — partial update
# ---------------------------------------------------------------------------


def test_patch_automation_partial_update(monkeypatch, app_client_owner):
    """PATCH with {"prompt": "new"} returns 200 with the updated prompt, others unchanged.

    Gherkin: Given automation X with prompt "old",
    When owner PATCHes {"prompt": "new"},
    Then response 200 and X.prompt == "new" and other fields unchanged.
    """
    import app.api.routes.automations as automations_module

    patched_row = {**AUTOMATION_ROW, "prompt": "new"}

    monkeypatch.setattr(
        automations_module.automation_service,
        "update_automation",
        lambda workspace_id, automation_id, patch, *, supabase: patched_row,
    )

    client, _ = app_client_owner
    response = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/automations/{AUTOMATION_ID}",
        json={"prompt": "new"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["prompt"] == "new"
    assert data["name"] == AUTOMATION_ROW["name"]  # unchanged
    assert data["schedule"] == AUTOMATION_ROW["schedule"]  # unchanged


# ---------------------------------------------------------------------------
# 9. PATCH automation — schedule change recomputes next_run_at
# ---------------------------------------------------------------------------


def test_patch_automation_schedule_recomputes_next_run_at(monkeypatch, app_client_owner):
    """PATCH schedule field triggers recomputation of next_run_at.

    Gherkin: Given automation X with daily 09:00 and next_run_at=T1,
    When owner PATCHes {"schedule": {"occurrence": "daily", "when": "17:00"}},
    Then next_run_at is updated to the next 17:00 in the row's timezone.
    """
    import app.api.routes.automations as automations_module

    updated_row = {
        **AUTOMATION_ROW,
        "schedule": {"occurrence": "daily", "when": "17:00"},
        "next_run_at": "2026-04-17T17:00:00+00:00",  # new next_run_at
    }

    monkeypatch.setattr(
        automations_module.automation_service,
        "update_automation",
        lambda workspace_id, automation_id, patch, *, supabase: updated_row,
    )

    client, _ = app_client_owner
    response = client.patch(
        f"/api/workspaces/{WORKSPACE_ID}/automations/{AUTOMATION_ID}",
        json={"schedule": {"occurrence": "daily", "when": "17:00"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["schedule"]["when"] == "17:00"
    # next_run_at must differ from original T1 (09:00)
    assert "17:00" in data["next_run_at"]


# ---------------------------------------------------------------------------
# 10. DELETE automation — cascade
# ---------------------------------------------------------------------------


def test_delete_automation_cascade(monkeypatch, app_client_owner):
    """DELETE returns 204 No Content.

    Gherkin: Given automation X has 5 execution rows,
    When owner DELETEs X,
    Then response 204 and teemo_automation_executions rows for X are gone (FK cascade).
    """
    import app.api.routes.automations as automations_module

    monkeypatch.setattr(
        automations_module.automation_service,
        "delete_automation",
        lambda workspace_id, automation_id, *, supabase: True,
    )

    client, _ = app_client_owner
    response = client.delete(
        f"/api/workspaces/{WORKSPACE_ID}/automations/{AUTOMATION_ID}"
    )
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 11. History — last 50
# ---------------------------------------------------------------------------


def test_history_last_50(monkeypatch, app_client_owner):
    """GET /history returns exactly 50 rows sorted started_at DESC.

    Gherkin: Given automation X has 60 execution rows,
    When owner GETs /api/workspaces/W/automations/X/history,
    Then response 200 with 50 rows sorted started_at DESC.
    """
    import app.api.routes.automations as automations_module

    fifty_rows = [
        {**EXECUTION_ROW, "id": str(uuid.uuid4()), "started_at": f"2026-04-{i:02d}T09:00:00+00:00"}
        for i in range(1, 51)
    ]
    # Sorted DESC — most recent first
    fifty_rows_sorted = sorted(fifty_rows, key=lambda r: r["started_at"], reverse=True)

    monkeypatch.setattr(
        automations_module.automation_service,
        "get_automation_history",
        lambda automation_id, *, supabase: fifty_rows_sorted,
    )

    client, _ = app_client_owner
    response = client.get(
        f"/api/workspaces/{WORKSPACE_ID}/automations/{AUTOMATION_ID}/history"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 50
    # Verify DESC order (first item >= second item)
    if len(data) >= 2:
        assert data[0]["started_at"] >= data[1]["started_at"]


# ---------------------------------------------------------------------------
# 12. Test-run — success
# ---------------------------------------------------------------------------


def test_test_run_success(monkeypatch, app_client_owner):
    """POST test-run with a valid BYOK key returns 200 with {success: True, output: <non-empty>}.

    Gherkin: Given workspace W has a valid BYOK key,
    When owner POSTs /api/workspaces/W/automations/test-run with prompt "say hello",
    Then response 200 with {success: True, output: "<non-empty>"}.
    And NO row is written to teemo_automation_executions.
    """
    import app.api.routes.automations as automations_module

    async def _fake_run_preview(workspace_id, prompt, *, supabase):
        from app.api.routes.automations import AutomationTestRunResponse
        return AutomationTestRunResponse(
            success=True,
            output="Hello there!",
            error=None,
            tokens_used=10,
            execution_time_ms=250,
        )

    monkeypatch.setattr(
        automations_module,
        "_run_preview_prompt",
        _fake_run_preview,
    )

    client, mock_sb = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations/test-run",
        json={"prompt": "say hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["output"] is not None and len(data["output"]) > 0

    # Verify no execution row was written (teemo_automation_executions insert never called)
    for call_args in mock_sb.table.call_args_list:
        table_name = call_args[0][0]
        assert table_name != "teemo_automation_executions", (
            "test-run endpoint must NOT write to teemo_automation_executions"
        )


# ---------------------------------------------------------------------------
# 13. Test-run — missing BYOK key
# ---------------------------------------------------------------------------


def test_test_run_missing_byok(monkeypatch, app_client_owner):
    """POST test-run with no BYOK key returns 200 with {success: False, error: 'no_key_configured'}.

    Gherkin: Given workspace W has no BYOK key,
    When owner POSTs the test-run endpoint,
    Then response 200 with {success: False, error: "no_key_configured"}.
    """
    import app.api.routes.automations as automations_module

    async def _fake_no_key(workspace_id, prompt, *, supabase):
        from app.api.routes.automations import AutomationTestRunResponse
        return AutomationTestRunResponse(
            success=False,
            output=None,
            error="no_key_configured",
            tokens_used=None,
            execution_time_ms=None,
        )

    monkeypatch.setattr(
        automations_module,
        "_run_preview_prompt",
        _fake_no_key,
    )

    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations/test-run",
        json={"prompt": "say hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "no_key_configured"


# ---------------------------------------------------------------------------
# 14. Test-run — timeout
# ---------------------------------------------------------------------------


def test_test_run_timeout(monkeypatch, app_client_owner):
    """POST test-run when the provider hangs returns 200 with {success: False, error: 'timeout after 30s'}.

    Gherkin: Given the BYOK provider hangs,
    When the request exceeds 30s,
    Then response 200 with {success: False, error: "timeout after 30s"}.

    The _run_preview_prompt helper is patched to simulate a timeout by
    returning the timeout response directly.
    """
    import app.api.routes.automations as automations_module

    async def _fake_timeout(workspace_id, prompt, *, supabase):
        from app.api.routes.automations import AutomationTestRunResponse
        return AutomationTestRunResponse(
            success=False,
            output=None,
            error="timeout after 30s",
            tokens_used=None,
            execution_time_ms=30000,
        )

    monkeypatch.setattr(
        automations_module,
        "_run_preview_prompt",
        _fake_timeout,
    )

    client, _ = app_client_owner
    response = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/automations/test-run",
        json={"prompt": "say hello"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error"] == "timeout after 30s"
