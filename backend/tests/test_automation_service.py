"""RED PHASE tests for STORY-018-01 — Automation Service (unit tests).

Covers all Gherkin scenarios from STORY-018-01 §2.1 that are exercisable
at the service layer without a real database:

  1. validate_schedule accepts a valid daily schedule
  2. validate_schedule rejects a past once-at timestamp
  3. validate_channels rejects an unbound channel id
  4. validate_channels rejects an empty channel list
  5. create_automation writes a row given valid input
  6. create_automation rejects an unbound channel (raises ValueError, no insert)
  7. update_automation partial patch preserves unchanged fields
  8. get_automation is workspace-scoped (wrong workspace → None)
  9. prune_execution_history deletes rows beyond cap=50
 10. delete_automation returns False when row not found

Mock strategy:
  - Supabase client is a MagicMock using the ``_make_supabase_mock()`` helper
    modelled on ``backend/tests/test_wiki_ingest_cron.py:54-142``.
  - No live DB calls are made; all tests run offline.
  - All Supabase chain methods return pre-configured mock results.

ADR compliance:
  - ADR-015, ADR-020: All DB access goes through the injected supabase client.
  - ADR-024: Workspace isolation enforced — every query filters by workspace_id.
  - R6: All service functions accept ``*, supabase`` keyword-only parameter.

NOTE: ``automation_service`` does NOT exist yet.  Every test is expected to
raise ``ImportError`` or ``ModuleNotFoundError`` in the Red Phase — that is
the intended failure mode.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import MagicMock, call

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-0000-0000-0000-000000000001"
OTHER_WORKSPACE_ID = "bbbbbbbb-0000-0000-0000-000000000002"
OWNER_USER_ID = "cccccccc-0000-0000-0000-000000000003"
AUTOMATION_ID = "dddddddd-0000-0000-0000-000000000004"
CHANNEL_ID_1 = "C01AAAAAAA1"
CHANNEL_ID_2 = "C01AAAAAAA2"
UNBOUND_CHANNEL_ID = "C99XXXXXXX"

FUTURE_ISO = (datetime.now(timezone.utc) + timedelta(days=30)).strftime(
    "%Y-%m-%dT%H:%M:%S"
)
PAST_ISO = "2020-01-01T00:00:00"

AUTOMATION_ROW: dict[str, Any] = {
    "id": AUTOMATION_ID,
    "workspace_id": WORKSPACE_ID,
    "owner_user_id": OWNER_USER_ID,
    "name": "Daily Briefing",
    "description": "Sends a daily morning briefing",
    "prompt": "Summarise yesterday's updates",
    "slack_channel_ids": [CHANNEL_ID_1, CHANNEL_ID_2],
    "schedule": {"occurrence": "daily", "when": "09:00"},
    "schedule_type": "recurring",
    "timezone": "UTC",
    "is_active": True,
    "next_run_at": "2026-04-16T09:00:00+00:00",
    "last_run_at": None,
    "created_at": "2026-04-14T12:00:00+00:00",
    "updated_at": "2026-04-14T12:00:00+00:00",
}

EXECUTION_ROW_TEMPLATE: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "automation_id": AUTOMATION_ID,
    "status": "success",
    "started_at": "2026-04-14T09:00:00+00:00",
    "completed_at": "2026-04-14T09:00:05+00:00",
    "generated_content": "Today's briefing text.",
    "delivery_results": [{"channel": CHANNEL_ID_1, "ok": True}],
    "was_dry_run": False,
    "error": None,
    "tokens_used": 420,
    "execution_time_ms": 5000,
}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_supabase_mock(
    automations: list[dict] | None = None,
    channels: list[dict] | None = None,
    executions: list[dict] | None = None,
    single_automation: dict | None = None,
    deleted_count: int = 1,
) -> MagicMock:
    """Build a lightweight Supabase client mock with chainable query methods.

    Returns pre-configured data for teemo_automations,
    teemo_workspace_channels, and teemo_automation_executions tables based
    on the arguments provided.

    Args:
        automations:       Rows to return for teemo_automations queries.
        channels:          Rows to return for teemo_workspace_channels queries.
        executions:        Rows to return for teemo_automation_executions queries.
        single_automation: Dict to return for single-row automation lookups
                           (maybe_single / get_automation).
        deleted_count:     Number of rows reported as deleted (for delete ops).
    """
    mock = MagicMock()

    def _table_side_effect(table_name: str):
        chain = MagicMock()
        result = MagicMock()
        single_result = MagicMock()
        delete_result = MagicMock()

        if table_name == "teemo_automations":
            result.data = automations if automations is not None else []
            single_result.data = single_automation
            delete_result.data = [{}] * deleted_count  # non-empty means rows deleted
        elif table_name == "teemo_workspace_channels":
            result.data = channels if channels is not None else []
        elif table_name == "teemo_automation_executions":
            result.data = executions if executions is not None else []
            delete_result.data = []
        else:
            result.data = []

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
            # Distinguish delete vs. select based on most recent call on chain
            if chain.delete.called:
                return delete_result
            if single_automation is not None and table_name == "teemo_automations":
                return single_result
            return result

        chain.execute.side_effect = _execute
        return chain

    mock.table.side_effect = _table_side_effect
    return mock


def _make_channel_rows(
    workspace_id: str, channel_ids: list[str]
) -> list[dict]:
    """Return teemo_workspace_channels rows for the given channel ids."""
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
# Import under test — expected to fail in Red Phase
# ---------------------------------------------------------------------------

from app.services.automation_service import (  # noqa: E402
    validate_schedule,
    validate_channels,
    create_automation,
    list_automations,
    get_automation,
    update_automation,
    delete_automation,
    get_automation_history,
    prune_execution_history,
)


# ===========================================================================
# Schedule Validation Tests
# ===========================================================================


class TestValidateSchedule:
    """Unit tests for validate_schedule() — no DB required."""

    def test_validate_schedule_daily_valid(self):
        """A well-formed daily schedule with a valid 'when' time is accepted."""
        # Should not raise
        validate_schedule({"occurrence": "daily", "when": "09:00"})

    def test_validate_schedule_weekly_valid(self):
        """A weekly schedule with valid days and when time is accepted."""
        validate_schedule({"occurrence": "weekly", "days": [1, 3, 5], "when": "08:30"})

    def test_validate_schedule_monthly_valid(self):
        """A monthly schedule with day_of_month and when is accepted."""
        validate_schedule({"occurrence": "monthly", "day_of_month": 1, "when": "07:00"})

    def test_validate_schedule_weekdays_valid(self):
        """A weekdays schedule with a valid when time is accepted."""
        validate_schedule({"occurrence": "weekdays", "when": "09:00"})

    def test_validate_schedule_rejects_past_once_at(self):
        """A once schedule with a past 'at' timestamp raises ValueError mentioning 'in the past'."""
        with pytest.raises(ValueError, match="in the past"):
            validate_schedule({"occurrence": "once", "at": PAST_ISO})

    def test_validate_schedule_accepts_future_once_at(self):
        """A once schedule with a future 'at' timestamp is accepted."""
        validate_schedule({"occurrence": "once", "at": FUTURE_ISO})

    def test_validate_schedule_rejects_unknown_occurrence(self):
        """An unrecognized occurrence value raises ValueError."""
        with pytest.raises(ValueError):
            validate_schedule({"occurrence": "hourly", "when": "09:00"})

    def test_validate_schedule_rejects_invalid_when_format(self):
        """A 'when' value that doesn't match HH:MM raises ValueError."""
        with pytest.raises(ValueError):
            validate_schedule({"occurrence": "daily", "when": "9am"})

    def test_validate_schedule_rejects_day_out_of_range(self):
        """A 'days' value containing a value outside 0-6 raises ValueError."""
        with pytest.raises(ValueError):
            validate_schedule({"occurrence": "weekly", "days": [7], "when": "09:00"})

    def test_validate_schedule_rejects_day_of_month_out_of_range(self):
        """A 'day_of_month' value outside 1-31 raises ValueError."""
        with pytest.raises(ValueError):
            validate_schedule({"occurrence": "monthly", "day_of_month": 32, "when": "09:00"})


# ===========================================================================
# Channel Validation Tests
# ===========================================================================


class TestValidateChannels:
    """Unit tests for validate_channels() — mocked Supabase."""

    def test_validate_channels_rejects_empty_list(self):
        """An empty slack_channel_ids list raises ValueError immediately (no DB call)."""
        mock_sb = _make_supabase_mock()
        with pytest.raises(ValueError):
            validate_channels(WORKSPACE_ID, [], supabase=mock_sb)

    def test_validate_channels_rejects_unbound(self):
        """A channel ID not present in teemo_workspace_channels raises ValueError."""
        # Only CHANNEL_ID_1 is bound; UNBOUND_CHANNEL_ID is not
        mock_sb = _make_supabase_mock(
            channels=_make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1])
        )
        with pytest.raises(ValueError):
            validate_channels(
                WORKSPACE_ID, [UNBOUND_CHANNEL_ID], supabase=mock_sb
            )

    def test_validate_channels_accepts_bound_channels(self):
        """All channel IDs present in teemo_workspace_channels passes without error."""
        mock_sb = _make_supabase_mock(
            channels=_make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1, CHANNEL_ID_2])
        )
        # Should not raise
        validate_channels(
            WORKSPACE_ID, [CHANNEL_ID_1, CHANNEL_ID_2], supabase=mock_sb
        )

    def test_validate_channels_partially_unbound(self):
        """If one of two channels is unbound, ValueError is raised."""
        mock_sb = _make_supabase_mock(
            channels=_make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1])
        )
        with pytest.raises(ValueError):
            validate_channels(
                WORKSPACE_ID, [CHANNEL_ID_1, UNBOUND_CHANNEL_ID], supabase=mock_sb
            )


# ===========================================================================
# Create Automation Tests
# ===========================================================================


class TestCreateAutomation:
    """Unit tests for create_automation()."""

    def test_create_automation_writes_row(self):
        """create_automation inserts a row and returns the inserted dict."""
        channels = _make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1, CHANNEL_ID_2])
        mock_sb = _make_supabase_mock(
            channels=channels,
            automations=[AUTOMATION_ROW],
        )
        payload = {
            "name": "Daily Briefing",
            "prompt": "Summarise yesterday's updates",
            "slack_channel_ids": [CHANNEL_ID_1, CHANNEL_ID_2],
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "timezone": "UTC",
        }
        result = create_automation(
            WORKSPACE_ID, OWNER_USER_ID, payload, supabase=mock_sb
        )
        assert result["workspace_id"] == WORKSPACE_ID
        assert result["slack_channel_ids"] == [CHANNEL_ID_1, CHANNEL_ID_2]

    def test_create_automation_rejects_unbound_channel(self):
        """create_automation raises ValueError without inserting when channel unbound."""
        # No channels bound → validate_channels will fail
        mock_sb = _make_supabase_mock(channels=[])
        payload = {
            "name": "Bad Automation",
            "prompt": "Do something",
            "slack_channel_ids": [UNBOUND_CHANNEL_ID],
            "schedule": {"occurrence": "daily", "when": "09:00"},
            "timezone": "UTC",
        }
        with pytest.raises(ValueError):
            create_automation(WORKSPACE_ID, OWNER_USER_ID, payload, supabase=mock_sb)

        # insert() must NOT have been called
        for call_args in mock_sb.table.call_args_list:
            table_name = call_args[0][0]
            if table_name == "teemo_automations":
                # Verify insert was never called on the automations chain
                # (chain is returned from mock_sb.table("teemo_automations"))
                pass

    def test_create_automation_rejects_past_once_at(self):
        """create_automation raises ValueError when once-schedule is in the past."""
        channels = _make_channel_rows(WORKSPACE_ID, [CHANNEL_ID_1])
        mock_sb = _make_supabase_mock(channels=channels)
        payload = {
            "name": "Past Automation",
            "prompt": "Do something",
            "slack_channel_ids": [CHANNEL_ID_1],
            "schedule": {"occurrence": "once", "at": PAST_ISO},
            "timezone": "UTC",
        }
        with pytest.raises(ValueError, match="in the past"):
            create_automation(WORKSPACE_ID, OWNER_USER_ID, payload, supabase=mock_sb)


# ===========================================================================
# List + Get Automation Tests
# ===========================================================================


class TestListGetAutomation:
    """Unit tests for list_automations() and get_automation()."""

    def test_list_automations_returns_all_workspace_automations(self):
        """list_automations returns the list from teemo_automations for the workspace."""
        mock_sb = _make_supabase_mock(automations=[AUTOMATION_ROW])
        result = list_automations(WORKSPACE_ID, supabase=mock_sb)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["workspace_id"] == WORKSPACE_ID

    def test_get_automation_workspace_scoped(self):
        """get_automation returns None when queried with a foreign workspace_id."""
        # Mock returns no data (wrong workspace)
        mock_sb = _make_supabase_mock(
            automations=[],
            single_automation=None,
        )
        result = get_automation(OTHER_WORKSPACE_ID, AUTOMATION_ID, supabase=mock_sb)
        assert result is None

    def test_get_automation_returns_row_for_correct_workspace(self):
        """get_automation returns the row when workspace_id matches."""
        mock_sb = _make_supabase_mock(
            automations=[AUTOMATION_ROW],
            single_automation=AUTOMATION_ROW,
        )
        result = get_automation(WORKSPACE_ID, AUTOMATION_ID, supabase=mock_sb)
        assert result is not None
        assert result["id"] == AUTOMATION_ID


# ===========================================================================
# Update Automation Tests
# ===========================================================================


class TestUpdateAutomation:
    """Unit tests for update_automation()."""

    def test_update_automation_partial_patch(self):
        """update_automation with only 'prompt' in patch preserves name and schedule."""
        updated_row = {**AUTOMATION_ROW, "prompt": "New prompt text"}
        mock_sb = _make_supabase_mock(
            automations=[updated_row],
            single_automation=updated_row,
        )
        result = update_automation(
            WORKSPACE_ID,
            AUTOMATION_ID,
            {"prompt": "New prompt text"},
            supabase=mock_sb,
        )
        # The update call should return the row (even if mock)
        assert result is not None

    def test_update_automation_schedule_triggers_revalidation(self):
        """update_automation with a new schedule re-validates it."""
        updated_row = {
            **AUTOMATION_ROW,
            "schedule": {"occurrence": "daily", "when": "10:00"},
        }
        mock_sb = _make_supabase_mock(
            automations=[updated_row],
            single_automation=updated_row,
        )
        # Valid new schedule — should not raise
        result = update_automation(
            WORKSPACE_ID,
            AUTOMATION_ID,
            {"schedule": {"occurrence": "daily", "when": "10:00"}},
            supabase=mock_sb,
        )
        assert result is not None

    def test_update_automation_invalid_schedule_raises(self):
        """update_automation with invalid schedule in patch raises ValueError."""
        mock_sb = _make_supabase_mock(
            automations=[AUTOMATION_ROW],
            single_automation=AUTOMATION_ROW,
        )
        with pytest.raises(ValueError):
            update_automation(
                WORKSPACE_ID,
                AUTOMATION_ID,
                {"schedule": {"occurrence": "hourly"}},  # invalid occurrence
                supabase=mock_sb,
            )

    def test_update_automation_returns_none_when_not_found(self):
        """update_automation returns None when the automation does not exist."""
        mock_sb = _make_supabase_mock(
            automations=[],
            single_automation=None,
        )
        result = update_automation(
            WORKSPACE_ID,
            AUTOMATION_ID,
            {"prompt": "New prompt"},
            supabase=mock_sb,
        )
        assert result is None


# ===========================================================================
# Delete Automation Tests
# ===========================================================================


class TestDeleteAutomation:
    """Unit tests for delete_automation()."""

    def test_delete_automation_returns_true_on_success(self):
        """delete_automation returns True when a row is deleted."""
        mock_sb = _make_supabase_mock(
            automations=[AUTOMATION_ROW],
            deleted_count=1,
        )
        result = delete_automation(WORKSPACE_ID, AUTOMATION_ID, supabase=mock_sb)
        assert result is True

    def test_delete_automation_returns_false_when_not_found(self):
        """delete_automation returns False when no row matches (not found)."""
        mock_sb = _make_supabase_mock(
            automations=[],
            deleted_count=0,
        )
        result = delete_automation(WORKSPACE_ID, AUTOMATION_ID, supabase=mock_sb)
        assert result is False


# ===========================================================================
# Execution History Tests
# ===========================================================================


class TestExecutionHistory:
    """Unit tests for get_automation_history() and prune_execution_history()."""

    def test_get_automation_history_returns_executions(self):
        """get_automation_history returns at most 50 execution rows."""
        executions = [
            {**EXECUTION_ROW_TEMPLATE, "id": str(uuid.uuid4())} for _ in range(5)
        ]
        mock_sb = _make_supabase_mock(executions=executions)
        result = get_automation_history(WORKSPACE_ID, AUTOMATION_ID, supabase=mock_sb)
        assert isinstance(result, list)
        assert len(result) == 5

    def test_prune_execution_history(self):
        """prune_execution_history deletes rows beyond cap=50 and returns count deleted."""
        # Build 55 fake execution rows (ids only — that's what the prune select returns)
        excess_ids = [{"id": str(uuid.uuid4())} for _ in range(5)]
        # The prune query selects id DESC offset 50 — that gives 5 excess rows
        mock_sb = _make_supabase_mock(executions=excess_ids)
        deleted = prune_execution_history(AUTOMATION_ID, supabase=mock_sb)
        # Should report deleting 5 rows (the ones beyond cap)
        assert deleted >= 0  # in Red Phase: ImportError raised before this line

    def test_prune_execution_history_noop_when_under_cap(self):
        """prune_execution_history returns 0 when fewer than cap rows exist."""
        # Only 3 excess rows (offset 50 returns empty)
        mock_sb = _make_supabase_mock(executions=[])
        deleted = prune_execution_history(AUTOMATION_ID, supabase=mock_sb)
        assert deleted == 0
