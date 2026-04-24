"""RED PHASE integration tests for STORY-018-01 — migration 012_teemo_automations.sql.

Covers all Gherkin scenarios from STORY-018-01 §2.1 that require a real
PostgreSQL / Supabase database:

  1. BEFORE INSERT trigger sets next_run_at on new active automation
  2. BEFORE UPDATE trigger clears next_run_at when is_active set to FALSE
  3. calculate_next_run_time correctly handles 'once' schedule in non-UTC timezone
  4. get_due_automations() returns only active automations with next_run_at <= NOW()

Test prerequisites:
  - Migration 001-011 must already be applied (teemo_workspaces,
    teemo_workspace_channels must exist).
  - Migration 012 (the one this story creates) must be applied before running.
  - Environment vars SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.

All tests are marked ``@pytest.mark.integration`` so they can be excluded
from offline CI runs with ``pytest -m 'not integration'``.

NOTE: These tests are written RED-first — the migration file
``012_teemo_automations.sql`` does NOT exist yet.  Every test will either
import-fail (if the migration helper is missing) or FAIL at the DB assertion
because the tables/functions/triggers don't exist.

ADR compliance:
  - ADR-015, ADR-020: Uses ``app.core.db.get_supabase`` for the live client.
  - ``teemo_`` prefix on all table names (FLASHCARDS rule).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skip_if_no_supabase():
    """Return a pytest.mark.skip if SUPABASE_URL / key are absent."""
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        return pytest.mark.skip(reason="No live Supabase env vars — integration test skipped")
    return pytest.mark.usefixtures()  # no-op marker


def _make_test_workspace(supabase) -> str:
    """Insert a minimal teemo_workspaces row and return its UUID.

    Cleans itself up after the test via the yielded id.
    """
    workspace_id = str(uuid.uuid4())
    supabase.table("teemo_workspaces").insert(
        {
            "id": workspace_id,
            "slack_team_id": f"T{workspace_id[:8].upper()}",
            "name": f"test-workspace-{workspace_id[:8]}",
            "ai_provider": "anthropic",
            "encrypted_api_key": "enc-test-key",
        }
    ).execute()
    return workspace_id


def _make_test_automation_payload(
    workspace_id: str,
    owner_user_id: str,
    channel_ids: list[str],
    schedule: dict | None = None,
    is_active: bool = True,
) -> dict:
    """Build a minimal teemo_automations insert payload.

    Deliberately omits ``created_at``, ``updated_at``, ``next_run_at``, and
    ``last_run_at`` — these are DEFAULT NOW() / trigger-managed columns (FLASHCARDS rule).
    """
    return {
        "workspace_id": workspace_id,
        "owner_user_id": owner_user_id,
        "name": f"test-auto-{uuid.uuid4().hex[:8]}",
        "prompt": "Test automation prompt",
        "slack_channel_ids": channel_ids,
        "schedule": schedule or {"occurrence": "daily", "when": "09:00"},
        "schedule_type": "recurring",
        "timezone": "UTC",
        "is_active": is_active,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def live_supabase():
    """Provide a live Supabase service-role client for integration tests.

    Skips the entire fixture (and test) when env vars are not set.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")

    # Import here so offline tests don't fail at collection time
    from supabase import create_client  # type: ignore[import]
    return create_client(url, key)


@pytest.fixture
def scratch_workspace(live_supabase):
    """Create a throwaway workspace and delete it after the test."""
    workspace_id = _make_test_workspace(live_supabase)
    yield workspace_id
    # Teardown — CASCADE deletes automations + executions
    live_supabase.table("teemo_workspaces").delete().eq("id", workspace_id).execute()


@pytest.fixture
def scratch_owner_user(live_supabase, scratch_workspace):
    """Create a throwaway teemo_users row and return its UUID."""
    user_id = str(uuid.uuid4())
    live_supabase.table("teemo_users").insert(
        {
            "id": user_id,
            "email": f"test-{user_id[:8]}@example.com",
            "password_hash": "not-a-real-hash",
        }
    ).execute()
    yield user_id
    live_supabase.table("teemo_users").delete().eq("id", user_id).execute()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTriggerSetsNextRunOnInsert:
    """Gherkin: 'Trigger sets next_run_at on insert'.

    Verifies that the BEFORE INSERT trigger ``set_automation_initial_next_run``
    automatically populates ``next_run_at`` when a new active automation is
    inserted with ``next_run_at`` NULL.
    """

    def test_trigger_sets_next_run_on_insert(self, live_supabase, scratch_workspace, scratch_owner_user):
        """INSERT with is_active=TRUE and no next_run_at → trigger fills it."""
        payload = _make_test_automation_payload(
            workspace_id=scratch_workspace,
            owner_user_id=scratch_owner_user,
            channel_ids=["C01TEST0001"],
            schedule={"occurrence": "daily", "when": "09:00"},
            is_active=True,
        )
        result = live_supabase.table("teemo_automations").insert(payload).execute()
        assert result.data, "Insert returned no data"

        row = result.data[0]
        automation_id = row["id"]

        # Teardown
        live_supabase.table("teemo_automations").delete().eq(
            "id", automation_id
        ).execute()

        # The trigger must have populated next_run_at
        assert row["next_run_at"] is not None, (
            "BEFORE INSERT trigger failed to set next_run_at for active automation"
        )

        # next_run_at should be in the future
        next_run = datetime.fromisoformat(row["next_run_at"].replace("Z", "+00:00"))
        assert next_run > datetime.now(timezone.utc), (
            f"next_run_at {row['next_run_at']} is not in the future"
        )


@pytest.mark.integration
class TestTriggerClearsNextRunOnDeactivate:
    """Gherkin: 'Trigger clears next_run_at when disabled'.

    Verifies that the BEFORE UPDATE trigger ``update_automation_next_run``
    sets ``next_run_at = NULL`` when ``is_active`` is set to FALSE.
    """

    def test_trigger_clears_next_run_on_deactivate(
        self, live_supabase, scratch_workspace, scratch_owner_user
    ):
        """UPDATE is_active=FALSE → next_run_at becomes NULL."""
        payload = _make_test_automation_payload(
            workspace_id=scratch_workspace,
            owner_user_id=scratch_owner_user,
            channel_ids=["C01TEST0002"],
            is_active=True,
        )
        insert_result = live_supabase.table("teemo_automations").insert(payload).execute()
        assert insert_result.data, "Insert returned no data"
        automation_id = insert_result.data[0]["id"]

        # Verify next_run_at is set after insert
        assert insert_result.data[0]["next_run_at"] is not None, (
            "INSERT trigger did not set next_run_at before deactivation test"
        )

        # Deactivate the automation
        update_result = (
            live_supabase.table("teemo_automations")
            .update({"is_active": False})
            .eq("id", automation_id)
            .execute()
        )

        # Teardown
        live_supabase.table("teemo_automations").delete().eq(
            "id", automation_id
        ).execute()

        assert update_result.data, "Update returned no data"
        updated_row = update_result.data[0]
        assert updated_row["next_run_at"] is None, (
            "BEFORE UPDATE trigger failed to clear next_run_at when is_active=FALSE"
        )


@pytest.mark.integration
class TestCalculateNextRunTimeOnceTimezone:
    """Gherkin: 'calculate_next_run_time — once in user's timezone'.

    Verifies the migration-034 version of calculate_next_run_time correctly
    interprets 'once' schedule timestamps in the user's timezone.

    Expected: {"occurrence": "once", "at": "2026-04-20T23:40:00"} with
    timezone Asia/Tbilisi (UTC+4) → 2026-04-20T19:40:00Z
    """

    def test_calculate_next_run_time_once_timezone(self, live_supabase):
        """calculate_next_run_time(once at 23:40 Tbilisi) → 19:40 UTC."""
        # Use the Supabase rpc mechanism to call the SQL function directly.
        # The function signature is calculate_next_run_time(schedule JSONB, from_time TIMESTAMPTZ)
        # We use a from_time in the past so the 'once' at-time is in the future.
        import json

        schedule = {"occurrence": "once", "at": "2026-04-20T23:40:00", "timezone": "Asia/Tbilisi"}
        from_time = "2026-04-14T00:00:00+00:00"

        result = live_supabase.rpc(
            "calculate_next_run_time",
            {"schedule": schedule, "from_time": from_time},
        ).execute()

        assert result.data is not None, "calculate_next_run_time returned NULL"

        # Parse the result — PostgREST returns a TIMESTAMPTZ string
        returned_ts_str = result.data
        if isinstance(returned_ts_str, str):
            returned_ts = datetime.fromisoformat(returned_ts_str.replace("Z", "+00:00"))
        else:
            # Some supabase-py versions return a datetime directly
            returned_ts = returned_ts_str

        # Expected: 2026-04-20T19:40:00+00:00 (23:40 Tbilisi = UTC+4 → 19:40 UTC)
        expected = datetime(2026, 4, 20, 19, 40, 0, tzinfo=timezone.utc)
        assert returned_ts == expected, (
            f"Expected {expected.isoformat()} but got {returned_ts}"
        )


@pytest.mark.integration
class TestGetDueAutomationsRPC:
    """Gherkin: 'get_due_automations returns only due+active'.

    Verifies the SQL function get_due_automations() returns only automations
    that are:
      - is_active = TRUE
      - next_run_at IS NOT NULL
      - next_run_at <= NOW()

    The test inserts 3 automations:
      A) active + next_run_at in the past   → SHOULD be returned
      B) active + next_run_at in the future → SHOULD NOT be returned
      C) inactive + next_run_at in the past  → SHOULD NOT be returned
    """

    def test_get_due_automations_returns_only_due_active(
        self, live_supabase, scratch_workspace, scratch_owner_user
    ):
        """Only the active+past automation appears in get_due_automations()."""
        past_ts = "2026-01-01T09:00:00+00:00"
        future_ts = "2099-01-01T09:00:00+00:00"

        inserted_ids: list[str] = []

        def _insert(name_suffix: str, is_active: bool, next_run_at: str | None) -> str:
            payload = _make_test_automation_payload(
                workspace_id=scratch_workspace,
                owner_user_id=scratch_owner_user,
                channel_ids=["C01TEST0003"],
                is_active=is_active,
            )
            payload["name"] = f"due-test-{name_suffix}"
            result = live_supabase.table("teemo_automations").insert(payload).execute()
            assert result.data, f"Insert of automation {name_suffix} failed"
            automation_id = result.data[0]["id"]

            # Force-set next_run_at bypassing the trigger (update after insert)
            if next_run_at is not None:
                live_supabase.table("teemo_automations").update(
                    {"next_run_at": next_run_at}
                ).eq("id", automation_id).execute()

            return automation_id

        try:
            id_a = _insert("active-past", is_active=True, next_run_at=past_ts)
            id_b = _insert("active-future", is_active=True, next_run_at=future_ts)
            id_c = _insert("inactive-past", is_active=False, next_run_at=past_ts)
            inserted_ids = [id_a, id_b, id_c]

            due_result = live_supabase.rpc("get_due_automations", {}).execute()
            due_rows = due_result.data or []

            # Filter to only the rows we just inserted (avoid interference from other tests)
            test_due = [r for r in due_rows if r["id"] in inserted_ids]

            assert len(test_due) == 1, (
                f"Expected exactly 1 due automation (active+past), got {len(test_due)}: "
                f"{[r['id'] for r in test_due]}"
            )
            assert test_due[0]["id"] == id_a, (
                f"Expected automation A ({id_a}) but got {test_due[0]['id']}"
            )

        finally:
            # Teardown all inserted rows
            for auto_id in inserted_ids:
                live_supabase.table("teemo_automations").delete().eq(
                    "id", auto_id
                ).execute()
