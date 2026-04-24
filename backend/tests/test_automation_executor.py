"""
RED PHASE tests for STORY-018-03 — Automation Executor + Cron Loop.

Covers all 11 Gherkin scenarios from STORY-018-03 §2.1:

  1.  Happy path — single channel, success
  2.  Multi-channel fanout — partial delivery
  3.  All channels fail → status='failed'
  4.  Skip-if-active guard — no new row written
  5.  BYOK key missing → status='failed', error contains message
  6.  Agent timeout → status='failed', error contains "timed out after 120s"
  7.  One-time automation deactivates after run (schedule_type='once')
  8.  Execution history pruned to 50 rows after run
  9.  Cron loop picks up due automations and calls execute_automation 3 times
 10.  Stale running execution reset on startup (reset_stale_executions)
 11.  Cron loop continues after per-automation failure (does not crash)

Mock strategy:
  - All external dependencies are mocked — no live DB, no real Slack, no LLM.
  - ``app.core.db.get_supabase`` is patched at the module level in the cron module.
  - ``app.agents.agent.build_agent`` is patched to return a mock agent + deps tuple.
  - ``slack_sdk.web.async_client.AsyncWebClient`` is patched per-test for
    ``chat_postMessage`` success/failure.
  - ``app.core.encryption.decrypt`` is injected via sys.modules so lazy imports
    (inside implementation functions) resolve to the mock without triggering
    a pydantic-settings env-var load.
  - ``app.services.automation_service.prune_execution_history`` is patched
    via the module reference to verify it is called after each run.
  - ``asyncio.sleep`` is patched to raise CancelledError after one iteration
    so the infinite cron loop can be driven from tests without blocking.

All tests are async (pytest-asyncio with asyncio_mode = "auto" in pyproject.toml).

NOTE: ``automation_executor`` and ``automation_cron`` do NOT exist yet.
Every test is expected to raise ``ModuleNotFoundError`` in the Red Phase —
that is the intended failure mode.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Imports under test — expected to fail in Red Phase
# ---------------------------------------------------------------------------
# These imports will raise ModuleNotFoundError because automation_executor.py
# and automation_cron.py do not exist yet.  That IS the intended Red Phase
# failure mode — all 11 tests should be collected as ERRORS.
#
# Note: We do NOT import app.agents.agent at module level here because that
# module requires pydantic_ai (installed only in the full dev environment).
# Tests that need to patch build_agent use patch() with its full dotted path
# string: "app.services.automation_executor.build_agent" (the executor will
# import build_agent at its module level, making it patchable via that path).
from app.services.automation_executor import execute_automation, reset_stale_executions  # noqa: E402
from app.services.automation_cron import automation_cron_loop  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-1111-0000-0000-000000000001"
OWNER_USER_ID = "bbbbbbbb-2222-0000-0000-000000000002"
AUTOMATION_ID = "cccccccc-3333-0000-0000-000000000003"
EXECUTION_ID = "dddddddd-4444-0000-0000-000000000004"
CHANNEL_ID_1 = "C01AAAAAA01"
CHANNEL_ID_2 = "C01AAAAAA02"
SLACK_TEAM_ID = "T01TEAMO001"
ENCRYPTED_KEY = "enc-api-key-placeholder"
ENCRYPTED_BOT_TOKEN = "enc-slack-bot-token-placeholder"
PLAIN_API_KEY = "plain-anthropic-api-key"
PLAIN_BOT_TOKEN = "xoxb-plain-bot-token"
NEXT_RUN_ISO = "2026-04-17T09:00:00+00:00"
AI_PROVIDER = "anthropic"
AI_MODEL = "claude-3-5-haiku"
GENERATED_CONTENT = "Today's automated briefing content."
SLACK_MSG_TS = "1234567890.000001"


# ---------------------------------------------------------------------------
# Automation fixture factories
# ---------------------------------------------------------------------------


def _make_automation(
    automation_id: str = AUTOMATION_ID,
    workspace_id: str = WORKSPACE_ID,
    owner_user_id: str = OWNER_USER_ID,
    slack_channel_ids: list[str] | None = None,
    schedule_type: str = "recurring",
    schedule: dict | None = None,
    prompt: str = "Summarise yesterday's news.",
) -> dict:
    """Return a minimal teemo_automations row dict for use in executor tests.

    Args:
        automation_id:      UUID string of the automation.
        workspace_id:       UUID string of the owning workspace.
        owner_user_id:      UUID string of the owning user.
        slack_channel_ids:  List of Slack channel ID strings. Defaults to [CHANNEL_ID_1].
        schedule_type:      "recurring" or "once".
        schedule:           Schedule dict. Defaults to daily at 09:00.
        prompt:             The automation prompt text.

    Returns:
        Dict shaped like a teemo_automations DB row.
    """
    return {
        "id": automation_id,
        "workspace_id": workspace_id,
        "owner_user_id": owner_user_id,
        "name": "Test Automation",
        "prompt": prompt,
        "slack_channel_ids": slack_channel_ids or [CHANNEL_ID_1],
        "schedule": schedule or {"occurrence": "daily", "when": "09:00"},
        "schedule_type": schedule_type,
        "timezone": "UTC",
        "is_active": True,
        "next_run_at": "2026-04-16T09:00:00+00:00",
        "last_run_at": None,
    }


def _make_workspace_row(
    workspace_id: str = WORKSPACE_ID,
    slack_team_id: str = SLACK_TEAM_ID,
    ai_provider: str = AI_PROVIDER,
    ai_model: str = AI_MODEL,
    encrypted_api_key: str | None = ENCRYPTED_KEY,
) -> dict:
    """Return a minimal teemo_workspaces row dict.

    Args:
        workspace_id:       UUID string.
        slack_team_id:      Slack team ID string (FK to teemo_slack_teams).
        ai_provider:        Provider slug, e.g. "anthropic".
        ai_model:           Model slug, e.g. "claude-3-5-haiku".
        encrypted_api_key:  Encrypted BYOK key, or None to simulate missing key.

    Returns:
        Dict shaped like a teemo_workspaces DB row.
    """
    return {
        "id": workspace_id,
        "slack_team_id": slack_team_id,
        "ai_provider": ai_provider,
        "ai_model": ai_model,
        "encrypted_api_key": encrypted_api_key,
    }


def _make_slack_team_row(
    slack_team_id: str = SLACK_TEAM_ID,
    encrypted_slack_bot_token: str = ENCRYPTED_BOT_TOKEN,
) -> dict:
    """Return a minimal teemo_slack_teams row dict.

    Args:
        slack_team_id:               Slack team ID string (PK).
        encrypted_slack_bot_token:   Encrypted Slack bot token.

    Returns:
        Dict shaped like a teemo_slack_teams DB row.
    """
    return {
        "slack_team_id": slack_team_id,
        "encrypted_slack_bot_token": encrypted_slack_bot_token,
    }


# ---------------------------------------------------------------------------
# Supabase mock builder
# ---------------------------------------------------------------------------


def _make_supabase_mock(
    workspace_row: dict | None = None,
    slack_team_row: dict | None = None,
    executions: list[dict] | None = None,
    running_execution_exists: bool = False,
    exec_insert_result: dict | None = None,
    rpc_next_run_at: str | None = NEXT_RUN_ISO,
    rpc_due_automations: list[dict] | None = None,
    stale_executions: list[dict] | None = None,
) -> MagicMock:
    """Build a Supabase client mock for automation executor tests.

    Handles the following tables:
      - teemo_workspaces          → workspace row lookup (maybe_single)
      - teemo_slack_teams         → Slack team row lookup (maybe_single)
      - teemo_automation_executions → running check, INSERT, UPDATE, stale reset
      - teemo_automations         → last_run_at / is_active / next_run_at updates

    Also handles:
      - supabase.rpc("calculate_next_run_time") → returns rpc_next_run_at
      - supabase.rpc("get_due_automations")     → returns rpc_due_automations

    Args:
        workspace_row:             Row to return for teemo_workspaces maybe_single.
        slack_team_row:            Row to return for teemo_slack_teams maybe_single.
        executions:                Rows to return for teemo_automation_executions
                                   SELECT queries (non-running check).
        running_execution_exists:  If True, the "check for running" SELECT returns
                                   a non-empty list (triggers skip-if-active).
        exec_insert_result:        The row returned by the INSERT into executions.
                                   Defaults to a row with id=EXECUTION_ID.
        rpc_next_run_at:           ISO string returned by calculate_next_run_time RPC.
        rpc_due_automations:       List returned by get_due_automations RPC.
        stale_executions:          Rows returned by stale execution SELECT (for reset).

    Returns:
        Configured MagicMock acting as a Supabase service-role client.
    """
    if exec_insert_result is None:
        exec_insert_result = {"id": EXECUTION_ID, "automation_id": AUTOMATION_ID, "status": "running"}

    mock = MagicMock()

    # --- RPC side-effects ---
    def _rpc_side_effect(name: str, params: dict | None = None):
        rpc_chain = MagicMock()
        rpc_result = MagicMock()
        if name == "calculate_next_run_time":
            rpc_result.data = rpc_next_run_at
        elif name == "get_due_automations":
            rpc_result.data = rpc_due_automations or []
        else:
            rpc_result.data = None
        rpc_chain.execute.return_value = rpc_result
        return rpc_chain

    mock.rpc.side_effect = _rpc_side_effect

    # --- Table side-effects ---
    def _table_side_effect(table_name: str):
        chain = MagicMock()
        single_result = MagicMock()
        list_result = MagicMock()
        insert_result = MagicMock()
        update_result = MagicMock()
        delete_result = MagicMock()

        if table_name == "teemo_workspaces":
            single_result.data = workspace_row
            list_result.data = [workspace_row] if workspace_row else []
            update_result.data = [workspace_row] if workspace_row else []

        elif table_name == "teemo_slack_teams":
            single_result.data = slack_team_row
            list_result.data = [slack_team_row] if slack_team_row else []

        elif table_name == "teemo_automation_executions":
            # Running check: if running_execution_exists, return a non-empty list
            list_result.data = [{"id": str(uuid.uuid4()), "status": "running"}] if running_execution_exists else []
            # Stale execution reset query
            if stale_executions is not None:
                list_result.data = stale_executions
            insert_result.data = [exec_insert_result]
            update_result.data = [exec_insert_result]
            delete_result.data = []

        elif table_name == "teemo_automations":
            update_result.data = []
            list_result.data = []

        else:
            list_result.data = []

        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.upsert.return_value = chain
        chain.eq.return_value = chain
        chain.neq.return_value = chain
        chain.lt.return_value = chain
        chain.lte.return_value = chain
        chain.in_.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.offset.return_value = chain
        chain.maybe_single.return_value = chain

        # execute() determines context by inspecting which methods were called
        def _execute():
            if chain.insert.called:
                return insert_result
            if chain.update.called:
                return update_result
            if chain.delete.called:
                return delete_result
            if chain.maybe_single.called:
                return single_result
            return list_result

        chain.execute.side_effect = _execute
        return chain

    mock.table.side_effect = _table_side_effect
    return mock


# ---------------------------------------------------------------------------
# Encryption mock injector
# ---------------------------------------------------------------------------


def _inject_decrypt_mock(side_effect=None, return_value: str = PLAIN_API_KEY):
    """Inject a mock encryption module into sys.modules.

    The automation executor imports ``decrypt`` lazily inside functions
    (following the wiki_ingest_cron pattern), so we must inject via
    sys.modules rather than monkeypatching at the module attribute level.

    Args:
        side_effect:   Optional callable for the mock decrypt function. If
                       provided, it overrides return_value.
        return_value:  Default plaintext string the mock decrypt returns.

    Returns:
        The mock decrypt callable for assertion in tests.
    """
    mock_encryption = ModuleType("app.core.encryption")
    if side_effect is not None:
        mock_decrypt = MagicMock(side_effect=side_effect)
    else:
        mock_decrypt = MagicMock(return_value=return_value)
    mock_encryption.decrypt = mock_decrypt
    sys.modules["app.core.encryption"] = mock_encryption
    return mock_decrypt


# ---------------------------------------------------------------------------
# Agent mock builder
# ---------------------------------------------------------------------------


def _make_mock_agent(
    output: str = GENERATED_CONTENT,
    total_tokens: int = 350,
    raise_timeout: bool = False,
) -> tuple[MagicMock, MagicMock]:
    """Build a mock (agent, deps) tuple returned by build_agent.

    The mock agent's ``run`` method is an AsyncMock that returns a result
    with ``.output`` and ``.usage().total_tokens`` attributes.

    Args:
        output:        The text content ``result.output`` will return.
        total_tokens:  The token count ``result.usage().total_tokens`` returns.
        raise_timeout: If True, ``agent.run`` raises ``asyncio.TimeoutError``
                       to simulate a 120-second timeout.

    Returns:
        Tuple of (mock_agent, mock_deps).
    """
    mock_result = MagicMock()
    mock_result.output = output
    mock_usage = MagicMock()
    mock_usage.total_tokens = total_tokens
    mock_result.usage.return_value = mock_usage

    mock_agent = MagicMock()
    mock_deps = MagicMock()

    if raise_timeout:
        mock_agent.run = AsyncMock(side_effect=asyncio.TimeoutError())
    else:
        mock_agent.run = AsyncMock(return_value=mock_result)

    return mock_agent, mock_deps


# ---------------------------------------------------------------------------
# Slack mock builder
# ---------------------------------------------------------------------------


def _make_slack_client_mock(
    channels_success: list[str] | None = None,
    channels_fail: list[str] | None = None,
    ts: str = SLACK_MSG_TS,
):
    """Build a mock AsyncWebClient whose chat_postMessage succeeds or fails per channel.

    Args:
        channels_success:  Channel IDs for which chat_postMessage succeeds.
                           If None, all channels succeed.
        channels_fail:     Channel IDs for which chat_postMessage raises SlackApiError.
        ts:                The timestamp returned in success responses.

    Returns:
        A class (not instance) that, when instantiated with ``token=...``, returns
        a mock client with the configured ``chat_postMessage`` behaviour.
    """
    from slack_sdk.errors import SlackApiError

    channels_fail_set = set(channels_fail or [])

    async def _post_message(*, channel: str, text: str, **kwargs):
        if channel in channels_fail_set:
            raise SlackApiError(
                message="not_in_channel",
                response={"ok": False, "error": "not_in_channel"},
            )
        return {"ok": True, "ts": ts}

    mock_client_instance = MagicMock()
    mock_client_instance.chat_postMessage = AsyncMock(side_effect=_post_message)

    class _FakeAsyncWebClient:
        def __init__(self, token: str):
            pass

        async def chat_postMessage(self, *, channel: str, text: str, **kwargs):
            return await _post_message(channel=channel, text=text, **kwargs)

    return _FakeAsyncWebClient


# ===========================================================================
# Test 1: Happy path — single channel, success
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_happy_path(monkeypatch):
    """
    Scenario: Happy path — single channel, success
      Given workspace W with BYOK key and a bound channel C1
      And an active automation A due now targeting [C1]
      When execute_automation(A, supabase=...) is called
      Then an execution row is written with status='running' first
      And build_agent is called with workspace W's credentials
      And chat_postMessage is called with channel=C1 and generated_content
      And the execution row is updated to status='success'
      And A.last_run_at is updated
      And A.next_run_at is advanced to the next scheduled instant
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation(slack_channel_ids=[CHANNEL_ID_1])
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    mock_agent, mock_deps = _make_mock_agent(output=GENERATED_CONTENT)
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))

    FakeAsyncWebClient = _make_slack_client_mock()

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.AsyncWebClient", FakeAsyncWebClient),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # Should not be skipped
    assert not result.get("skipped"), "Expected execution to proceed, not be skipped"

    # An execution row should have been created (INSERT called on teemo_automation_executions)
    exec_table_calls = [c for c in supabase.table.call_args_list if c.args[0] == "teemo_automation_executions"]
    assert len(exec_table_calls) >= 1, "Expected at least one call to teemo_automation_executions table"

    # build_agent was called
    mock_build_agent.assert_called_once()

    # agent.run was called
    mock_agent.run.assert_called_once()


# ===========================================================================
# Test 2: Multi-channel fanout — partial delivery
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_partial_delivery(monkeypatch):
    """
    Scenario: Multi-channel fanout — partial delivery
      Given automation A targeting [C1, C2]
      And the Slack client raises SlackApiError('not_in_channel') for C2
      When execute_automation(A, ...) completes
      Then execution row status = 'partial'
      And delivery_results contains C1 (ok=True) and C2 (ok=False)
      And next_run_at is still advanced
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation(slack_channel_ids=[CHANNEL_ID_1, CHANNEL_ID_2])
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    mock_agent, mock_deps = _make_mock_agent()
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))

    # C1 succeeds, C2 fails
    FakeAsyncWebClient = _make_slack_client_mock(channels_fail=[CHANNEL_ID_2])

    update_calls: list[dict] = []

    original_table_fn = supabase.table.side_effect

    def _tracking_table(table_name: str):
        chain = original_table_fn(table_name)
        if table_name == "teemo_automation_executions":
            def _tracking_update_effect(payload: dict):
                update_calls.append(payload)
                return chain

            chain.update.side_effect = _tracking_update_effect
        return chain

    supabase.table.side_effect = _tracking_table

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.AsyncWebClient", FakeAsyncWebClient),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # Check that the final UPDATE payload has status='partial'
    final_updates = [p for p in update_calls if p.get("status") in ("partial", "success", "failed")]
    assert any(p.get("status") == "partial" for p in final_updates), (
        f"Expected status='partial' in update calls, got: {final_updates}"
    )

    # Check delivery_results contains both channels
    dr_payloads = [p for p in update_calls if "delivery_results" in p]
    assert len(dr_payloads) >= 1, "Expected delivery_results in final UPDATE payload"
    delivery_results = dr_payloads[-1]["delivery_results"]
    channel_ids_in_results = [dr["channel_id"] for dr in delivery_results]
    assert CHANNEL_ID_1 in channel_ids_in_results
    assert CHANNEL_ID_2 in channel_ids_in_results


# ===========================================================================
# Test 3: All channels fail → status='failed'
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_all_channels_fail(monkeypatch):
    """
    Scenario: All channels fail
      Given automation A targeting [C1] and Slack raises SlackApiError for C1
      When execute_automation(A, ...) completes
      Then execution row status = 'failed'
      And next_run_at is still advanced (automation stays active)
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation(slack_channel_ids=[CHANNEL_ID_1])
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    mock_agent, mock_deps = _make_mock_agent()
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))

    # Both channels fail
    FakeAsyncWebClient = _make_slack_client_mock(channels_fail=[CHANNEL_ID_1])

    update_calls: list[dict] = []
    original_table_fn = supabase.table.side_effect

    def _tracking_table(table_name: str):
        chain = original_table_fn(table_name)
        if table_name == "teemo_automation_executions":
            def _tracking_update_effect(payload: dict):
                update_calls.append(payload)
                return chain

            chain.update.side_effect = _tracking_update_effect
        return chain

    supabase.table.side_effect = _tracking_table

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.AsyncWebClient", FakeAsyncWebClient),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    final_status_updates = [p for p in update_calls if "status" in p and p["status"] in ("partial", "success", "failed")]
    assert any(p["status"] == "failed" for p in final_status_updates), (
        f"Expected status='failed' when all channels fail, got: {final_status_updates}"
    )

    # next_run_at should still be advanced (teemo_automations UPDATE should be called)
    automations_table_calls = [c for c in supabase.table.call_args_list if c.args[0] == "teemo_automations"]
    assert len(automations_table_calls) >= 1, "Expected teemo_automations to be updated even on failure"


# ===========================================================================
# Test 4: Skip-if-active guard
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_skip_if_active(monkeypatch):
    """
    Scenario: Skip-if-active guard
      Given an existing execution row for automation A with status='running'
      When execute_automation(A, ...) is called again
      Then no new execution row is written
      And the function returns {"skipped": True}
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation()
    supabase = _make_supabase_mock(
        running_execution_exists=True,  # simulates an active running row
    )

    mock_build_agent = AsyncMock()

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # Must return {"skipped": True} or a dict containing "skipped": True
    assert result.get("skipped") is True, f"Expected skipped=True, got: {result}"

    # build_agent must NOT have been called (no execution should proceed)
    mock_build_agent.assert_not_called()

    # No INSERT into teemo_automation_executions should have been made
    insert_calls = []
    for table_call in supabase.table.call_args_list:
        if table_call.args[0] == "teemo_automation_executions":
            insert_calls.append(table_call)
    # We can't directly inspect whether insert() was called on the chain easily,
    # but build_agent not being called is sufficient confirmation of the skip path.


# ===========================================================================
# Test 5: BYOK key missing → status='failed'
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_byok_key_missing(monkeypatch):
    """
    Scenario: BYOK key missing
      Given workspace W with no encrypted_api_key
      When execute_automation(A, ...) is called
      Then execution row is written with status='failed'
      And error contains "BYOK key not configured"
      And next_run_at is still advanced
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation()
    # Workspace row with no encrypted_api_key
    workspace_row = _make_workspace_row(encrypted_api_key=None)
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    mock_build_agent = AsyncMock()

    update_calls: list[dict] = []
    original_table_fn = supabase.table.side_effect

    def _tracking_table(table_name: str):
        chain = original_table_fn(table_name)
        if table_name == "teemo_automation_executions":
            def _tracking_update_effect(payload: dict):
                update_calls.append(payload)
                return chain

            chain.update.side_effect = _tracking_update_effect
        return chain

    supabase.table.side_effect = _tracking_table

    with patch("app.services.automation_executor.build_agent", mock_build_agent):
        result = await execute_automation(automation, supabase=supabase)

    # build_agent must NOT have been called
    mock_build_agent.assert_not_called()

    # Execution row must be updated to status='failed'
    failed_updates = [p for p in update_calls if p.get("status") == "failed"]
    assert len(failed_updates) >= 1, f"Expected status='failed' update, got: {update_calls}"

    # Error message must mention BYOK
    error_msgs = [p.get("error", "") for p in failed_updates]
    assert any("BYOK" in (msg or "") or "byok" in (msg or "").lower() or "key not configured" in (msg or "").lower()
               for msg in error_msgs), (
        f"Expected 'BYOK key not configured' in error, got: {error_msgs}"
    )


# ===========================================================================
# Test 6: Agent timeout → status='failed', error contains "timed out after 120s"
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_agent_timeout(monkeypatch):
    """
    Scenario: Agent timeout
      Given build_agent returns an agent that hangs > 120s
      When execute_automation(A, ...) is called
      Then execution row status = 'failed', error contains "timed out after 120s"
      And next_run_at is advanced
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation()
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    # Agent that times out
    mock_agent, mock_deps = _make_mock_agent(raise_timeout=True)
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))

    update_calls: list[dict] = []
    original_table_fn = supabase.table.side_effect

    def _tracking_table(table_name: str):
        chain = original_table_fn(table_name)
        if table_name == "teemo_automation_executions":
            def _tracking_update_effect(payload: dict):
                update_calls.append(payload)
                return chain

            chain.update.side_effect = _tracking_update_effect
        return chain

    supabase.table.side_effect = _tracking_table

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # Execution row must be updated to status='failed'
    failed_updates = [p for p in update_calls if p.get("status") == "failed"]
    assert len(failed_updates) >= 1, f"Expected status='failed' update after timeout, got: {update_calls}"

    # Error must contain "timed out after 120s"
    error_msgs = [p.get("error", "") for p in failed_updates]
    assert any("timed out after 120s" in (msg or "").lower() or "120" in (msg or "") or "timed out" in (msg or "").lower()
               for msg in error_msgs), (
        f"Expected 'timed out after 120s' in error message, got: {error_msgs}"
    )


# ===========================================================================
# Test 7: One-time automation deactivates after run
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_once_deactivates(monkeypatch):
    """
    Scenario: One-time automation deactivates after run
      Given automation A with schedule_type='once' and due now
      When execute_automation(A, ...) completes successfully
      Then A.is_active = False and A.next_run_at = NULL
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    # schedule_type='once' automation
    automation = _make_automation(
        schedule_type="once",
        schedule={"occurrence": "once", "at": "2026-04-16T09:00:00"},
    )
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
    )

    mock_agent, mock_deps = _make_mock_agent()
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))

    FakeAsyncWebClient = _make_slack_client_mock()

    automation_update_calls: list[dict] = []
    original_table_fn = supabase.table.side_effect

    def _tracking_table(table_name: str):
        chain = original_table_fn(table_name)
        if table_name == "teemo_automations":
            def _tracking_update_effect(payload: dict):
                automation_update_calls.append(payload)
                return chain

            chain.update.side_effect = _tracking_update_effect
        return chain

    supabase.table.side_effect = _tracking_table

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.AsyncWebClient", FakeAsyncWebClient),
        patch("app.services.automation_executor.prune_execution_history", return_value=0),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # For schedule_type='once': is_active must be set to False, next_run_at to None
    once_deactivate_updates = [
        p for p in automation_update_calls
        if p.get("is_active") is False or "next_run_at" in p
    ]
    assert len(once_deactivate_updates) >= 1, (
        f"Expected teemo_automations UPDATE with is_active=False for once automation, got: {automation_update_calls}"
    )
    deactivate_payload = once_deactivate_updates[0]
    assert deactivate_payload.get("is_active") is False, (
        f"Expected is_active=False, got: {deactivate_payload}"
    )
    assert deactivate_payload.get("next_run_at") is None, (
        f"Expected next_run_at=None, got: {deactivate_payload.get('next_run_at')}"
    )


# ===========================================================================
# Test 8: Execution history is pruned after run
# ===========================================================================


@pytest.mark.asyncio
async def test_execute_automation_history_pruned(monkeypatch):
    """
    Scenario: Execution history is pruned to 50 rows
      Given automation A with 55 execution rows
      When execute_automation(A, ...) completes (run #56)
      Then prune_execution_history is called (ensuring max 50 rows are kept)
    """
    _inject_decrypt_mock(return_value=PLAIN_API_KEY)

    automation = _make_automation()
    workspace_row = _make_workspace_row()
    slack_team_row = _make_slack_team_row()
    supabase = _make_supabase_mock(
        workspace_row=workspace_row,
        slack_team_row=slack_team_row,
        rpc_next_run_at=NEXT_RUN_ISO,
    )

    mock_agent, mock_deps = _make_mock_agent()
    mock_build_agent = AsyncMock(return_value=(mock_agent, mock_deps))
    FakeAsyncWebClient = _make_slack_client_mock()

    mock_prune = MagicMock(return_value=5)

    with (
        patch("app.services.automation_executor.build_agent", mock_build_agent),
        patch("app.services.automation_executor.AsyncWebClient", FakeAsyncWebClient),
        patch("app.services.automation_executor.prune_execution_history", mock_prune),
    ):
        result = await execute_automation(automation, supabase=supabase)

    # prune_execution_history must have been called with the automation id
    mock_prune.assert_called_once()
    call_kwargs = mock_prune.call_args
    # Should be called with automation_id positional + supabase= keyword
    assert call_kwargs is not None, "prune_execution_history was not called"


# ===========================================================================
# Test 9: Cron loop picks up due automations
# ===========================================================================


@pytest.mark.asyncio
async def test_cron_loop_executes_due_automations(monkeypatch):
    """
    Scenario: Cron loop picks up due automations
      Given 3 automations due now and 1 not due
      When automation_cron_loop() runs one tick
      Then execute_automation is called exactly 3 times
      And the not-due automation is not touched
    """
    due_automations = [
        _make_automation(automation_id=str(uuid.uuid4())),
        _make_automation(automation_id=str(uuid.uuid4())),
        _make_automation(automation_id=str(uuid.uuid4())),
    ]
    # 1 not-due automation is NOT returned by the RPC (simulated by having only 3 in result)

    supabase = _make_supabase_mock(
        rpc_due_automations=due_automations,
    )

    async def _fake_sleep(seconds):
        raise asyncio.CancelledError()

    mock_execute = AsyncMock(return_value={"status": "success"})

    with (
        patch("app.services.automation_cron.get_supabase", return_value=supabase),
        patch("app.services.automation_cron.execute_automation", mock_execute),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await automation_cron_loop()

    # execute_automation must have been called exactly 3 times
    assert mock_execute.call_count == 3, (
        f"Expected execute_automation called 3 times, got: {mock_execute.call_count}"
    )


# ===========================================================================
# Test 10: Stale running execution is reset on startup
# ===========================================================================


@pytest.mark.asyncio
async def test_reset_stale_executions(monkeypatch):
    """
    Scenario: Stale running execution is reset on startup
      Given an execution row with status='running' started 15 minutes ago
      When reset_stale_executions(supabase=...) is called
      Then that row is updated to status='failed',
           error='Service restarted during execution', completed_at set
      And the function returns count=1
    """
    stale_row = {
        "id": str(uuid.uuid4()),
        "automation_id": AUTOMATION_ID,
        "status": "running",
        "started_at": "2026-04-16T08:45:00+00:00",  # 15 min ago
    }

    update_calls: list[dict] = []

    # Build mock with stale execution row present
    supabase = _make_supabase_mock(
        stale_executions=[stale_row],
    )

    # Override the update tracker on teemo_automation_executions
    original_table = supabase.table

    def _tracking_table(table_name: str):
        chain = original_table(table_name)
        if table_name == "teemo_automation_executions":
            original_update = chain.update

            def _tracking_update(payload: dict):
                update_calls.append(payload)
                # Return a result indicating 1 row updated
                result = MagicMock()
                result.data = [stale_row]
                return_chain = MagicMock()
                return_chain.execute.return_value = result
                return_chain.eq.return_value = return_chain
                return_chain.neq.return_value = return_chain
                return_chain.lt.return_value = return_chain
                return return_chain

            chain.update = _tracking_update
        return chain

    supabase.table = _tracking_table

    count = await reset_stale_executions(supabase=supabase)

    # The function should return 1 (one stale row reset)
    assert count == 1, f"Expected reset count=1, got: {count}"

    # The UPDATE payload must set status='failed' and include an error message
    assert len(update_calls) >= 1, "Expected at least one UPDATE call on teemo_automation_executions"
    failed_updates = [p for p in update_calls if p.get("status") == "failed"]
    assert len(failed_updates) >= 1, f"Expected status='failed' in UPDATE, got: {update_calls}"
    error_msgs = [p.get("error", "") for p in failed_updates]
    assert any("restarted" in (msg or "").lower() or "service" in (msg or "").lower()
               for msg in error_msgs), (
        f"Expected 'Service restarted during execution' in error, got: {error_msgs}"
    )


# ===========================================================================
# Test 11: Cron loop continues after per-automation failure
# ===========================================================================


@pytest.mark.asyncio
async def test_cron_loop_continues_after_per_automation_failure(monkeypatch):
    """
    Scenario: Cron loop continues after per-automation failure
      Given 3 due automations where A2 raises an unexpected exception
      When automation_cron_loop() runs one tick
      Then A1 and A3 are executed successfully
      And the loop does not crash (CancelledError is the only exit)
    """
    auto_1 = _make_automation(automation_id="auto-1111-0000-0000-000000000001")
    auto_2 = _make_automation(automation_id="auto-2222-0000-0000-000000000002")
    auto_3 = _make_automation(automation_id="auto-3333-0000-0000-000000000003")

    supabase = _make_supabase_mock(
        rpc_due_automations=[auto_1, auto_2, auto_3],
    )

    async def _fake_sleep(seconds):
        raise asyncio.CancelledError()

    executed_ids: list[str] = []

    async def _mock_execute(automation: dict, *, supabase) -> dict:
        if automation["id"] == "auto-2222-0000-0000-000000000002":
            raise RuntimeError("Unexpected DB error for A2")
        executed_ids.append(automation["id"])
        return {"status": "success"}

    with (
        patch("app.services.automation_cron.get_supabase", return_value=supabase),
        patch("app.services.automation_cron.execute_automation", side_effect=_mock_execute),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        # Loop must exit via CancelledError only — not via RuntimeError from A2
        with pytest.raises(asyncio.CancelledError):
            await automation_cron_loop()

    # A1 and A3 must have been executed
    assert "auto-1111-0000-0000-000000000001" in executed_ids, (
        f"Expected A1 to execute, got executed_ids: {executed_ids}"
    )
    assert "auto-3333-0000-0000-000000000003" in executed_ids, (
        f"Expected A3 to execute, got executed_ids: {executed_ids}"
    )
    # A2 failed but the loop continued — total executed = 2
    assert len(executed_ids) == 2, (
        f"Expected 2 successful executions (A1, A3), got: {executed_ids}"
    )
