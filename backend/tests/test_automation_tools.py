"""Tests for STORY-018-04 — Automation Agent Tools + System Prompt Integration.

Covers all 9 Gherkin scenarios from STORY-018-04 §2.1:

  1. create_automation tool — success: service called with correct payload, returns
     string containing automation name and next_run_at.
  2. create_automation tool — unbound channel: service raises ValueError, tool returns
     error string (does NOT re-raise).
  3. list_automations tool — non-empty workspace: returns Markdown string listing both
     automations with schedule summaries.
  4. list_automations tool — empty workspace: returns canonical empty-state string.
  5. update_automation tool — toggle is_active: service called with patch={"is_active": False},
     returns confirmation string.
  6. delete_automation tool — found: service returns True, tool returns string containing "deleted".
  7. delete_automation tool — not found: service returns False, tool returns "Automation not found."
  8. _build_system_prompt — automations exist: system prompt contains "## Scheduled Automations"
     and "create_automation".
  9. _build_system_prompt — no automations: system prompt does NOT contain "## Scheduled Automations".

Invocation strategy:
  The 4 tool functions (create_automation, list_automations, update_automation, delete_automation)
  will live as module-level async functions inside ``backend/app/agents/agent.py`` after Green Phase
  implementation (STORY-018-04 §3.3). Until then, accessing them will raise AttributeError — that
  is the correct RED Phase failure mode.

  ``_build_system_prompt`` already exists in agent.py. The new ``automations`` parameter will be
  added in Green Phase. Calling it with ``automations=[...]`` before the parameter is added will
  raise TypeError — that is the correct RED Phase failure mode for tests 8 and 9.

  Following the existing test pattern in ``test_wiki_read_tool.py`` and ``test_agent_factory.py``:
  the agent module is imported INSIDE test functions (not at module level) so test collection
  succeeds even when ``pydantic_ai`` is not installed in the test environment.

  automation_service functions are patched at the service module path
  (``app.services.automation_service.<fn>``) so the patch is in effect when the lazy import
  inside the tool body resolves: ``from app.services import automation_service as _auto_service``.

Mock design:
  - ``AgentDeps`` is imported from ``app.agents.agent`` inside each test function.
  - ``RunContext`` is simulated with a plain MagicMock whose ``.deps`` is a real ``AgentDeps``.
  - ``automation_service`` functions are patched via ``unittest.mock.patch`` targeting
    ``app.services.automation_service.<function_name>``.

FLASHCARDS.md consulted:
  - S-04 Flashcard: module-level imports for monkeypatching — lazy service imports inside tool
    bodies are patched at the service path (not at the tool's local alias).
  - S-11 Flashcard: agent.py red-zone surface — tests must not modify agent.py directly.
  - Worktree-relative paths only in Edit/Write calls.
  - ``from __future__ import annotations`` breaks FastAPI runtime type resolution —
    not applicable here (test file only), but noted.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_WORKSPACE_ID = "ws-auto-test-001"
FAKE_USER_ID = "user-auto-test-001"
FAKE_AUTOMATION_ID = "auto-uuid-001"
FAKE_AUTOMATION_NAME = "Daily Standup"
FAKE_NEXT_RUN_AT = "2026-04-16 09:00 UTC"
FAKE_CHANNEL_ID = "C123"
FAKE_SCHEDULE_DAILY = {"occurrence": "daily", "when": "09:00"}


# ---------------------------------------------------------------------------
# Helper — fake RunContext factory
# ---------------------------------------------------------------------------


def _make_ctx(
    workspace_id: str = FAKE_WORKSPACE_ID,
    user_id: str = FAKE_USER_ID,
    supabase: Any = None,
) -> MagicMock:
    """Create a minimal mock RunContext[AgentDeps] for testing tool functions directly.

    Constructs a real ``AgentDeps`` and attaches it to a MagicMock ctx so the tools
    can access ``ctx.deps.workspace_id``, ``ctx.deps.user_id``, ``ctx.deps.supabase``
    exactly as they would in production.

    Note: ``AgentDeps`` is imported inside this function to avoid module-level
    import of agent.py, which requires pydantic_ai to be installed. Following the
    pattern established in test_wiki_read_tool.py and test_agent_factory.py.

    Args:
        workspace_id: Workspace UUID string.
        user_id:      User UUID string.
        supabase:     Optional Supabase mock — defaults to a new MagicMock().

    Returns:
        MagicMock with ``.deps`` set to an ``AgentDeps`` instance.
    """
    from app.agents.agent import AgentDeps  # type: ignore[import]

    deps = AgentDeps(
        workspace_id=workspace_id,
        user_id=user_id,
        supabase=supabase or MagicMock(),
    )
    ctx = MagicMock()
    ctx.deps = deps
    return ctx


# ---------------------------------------------------------------------------
# Test 1: create_automation — success
# ---------------------------------------------------------------------------


class TestCreateAutomationSuccess:
    """Scenario: Create automation via agent tool — success.

    Given workspace W with a bound channel C1 (slack_channel_id="C123"),
    When the agent calls create_automation(name="Daily Standup", ...),
    Then automation_service.create_automation is called with correct payload
    And the tool returns a string containing "Daily Standup" and the next_run_at time.
    """

    @pytest.mark.asyncio
    async def test_create_automation_tool_success(self) -> None:
        """create_automation tool must call service with correct args and return a confirmation string.

        The returned string must contain the automation name and next_run_at.
        Accessing agent_module.create_automation before Green Phase implementation
        will raise AttributeError — that is the correct RED Phase failure.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        # Accessing this attribute will raise AttributeError in RED Phase — correct failure.
        create_automation_fn = getattr(agent_module, "create_automation")

        fake_row = {
            "id": FAKE_AUTOMATION_ID,
            "name": FAKE_AUTOMATION_NAME,
            "next_run_at": FAKE_NEXT_RUN_AT,
            "slack_channel_ids": [FAKE_CHANNEL_ID],
            "timezone": "UTC",
        }

        with patch(
            "app.services.automation_service.create_automation",
            return_value=fake_row,
        ) as mock_create:
            ctx = _make_ctx()
            result = await create_automation_fn(
                ctx,
                name=FAKE_AUTOMATION_NAME,
                prompt="Post standup update",
                schedule=FAKE_SCHEDULE_DAILY,
                slack_channel_ids=[FAKE_CHANNEL_ID],
            )

        # Service must have been called
        assert mock_create.called, (
            "automation_service.create_automation was not called by the tool. "
            "STORY-018-04 R1: tool must delegate to automation_service.create_automation."
        )

        # Return value must be a string
        assert isinstance(result, str), (
            f"Tool must return a str, got {type(result).__name__!r}. "
            "STORY-018-04 R1: all tools return str."
        )

        # Must contain automation name
        assert FAKE_AUTOMATION_NAME in result, (
            f"Expected automation name {FAKE_AUTOMATION_NAME!r} in result. Got: {result!r}. "
            "STORY-018-04 R1: confirmation string must include the automation name."
        )

        # Must contain next_run_at
        assert FAKE_NEXT_RUN_AT in result or "09:00" in result, (
            f"Expected next_run_at time in result. Got: {result!r}. "
            "STORY-018-04 R1: confirmation string must include next_run_at."
        )


# ---------------------------------------------------------------------------
# Test 2: create_automation — unbound channel raises ValueError
# ---------------------------------------------------------------------------


class TestCreateAutomationUnboundChannel:
    """Scenario: Create automation — unbound channel rejected.

    Given channel "C999" is NOT bound to workspace W,
    When the agent calls create_automation(..., slack_channel_ids=["C999"]),
    Then automation_service.create_automation raises ValueError
    And the tool returns an error string (does NOT raise).
    """

    @pytest.mark.asyncio
    async def test_create_automation_tool_unbound_channel_returns_error_string(self) -> None:
        """create_automation tool must catch ValueError from service and return it as a string.

        The tool must NOT re-raise the ValueError — it must return the error message
        as a string so the LLM can surface it conversationally.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        create_automation_fn = getattr(agent_module, "create_automation")

        error_message = "Channel C999 is not bound to workspace ws-auto-test-001"

        with patch(
            "app.services.automation_service.create_automation",
            side_effect=ValueError(error_message),
        ):
            ctx = _make_ctx()
            result = await create_automation_fn(
                ctx,
                name="Bad Channel Auto",
                prompt="This should fail",
                schedule=FAKE_SCHEDULE_DAILY,
                slack_channel_ids=["C999"],
            )

        # Must NOT raise — must return a string
        assert isinstance(result, str), (
            f"Tool must return str when service raises ValueError, got {type(result).__name__!r}. "
            "STORY-018-04 R1: on ValueError, return error string instead of raising."
        )

        # Error message or reasonable error indicator must be in the result
        assert (
            "C999" in result
            or "not bound" in result
            or "channel" in result.lower()
            or "error" in result.lower()
            or "fail" in result.lower()
        ), (
            f"Expected error context in result string. Got: {result!r}. "
            "STORY-018-04 R1: error string should describe the failure."
        )


# ---------------------------------------------------------------------------
# Test 3: list_automations — non-empty workspace
# ---------------------------------------------------------------------------


class TestListAutomationsNonEmpty:
    """Scenario: List automations — non-empty workspace.

    Given workspace W has 2 automations (one active, one inactive),
    When the agent calls list_automations(),
    Then automation_service.list_automations is called
    And the tool returns a Markdown string listing both automations with schedule summaries.
    """

    @pytest.mark.asyncio
    async def test_list_automations_tool_nonempty(self) -> None:
        """list_automations tool must return a Markdown string listing all automations.

        Both automations must appear in the returned string with their names.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        list_automations_fn = getattr(agent_module, "list_automations")

        fake_automations = [
            {
                "id": "auto-001",
                "name": "Daily Standup",
                "schedule": {"occurrence": "daily", "when": "09:00"},
                "timezone": "UTC",
                "is_active": True,
                "next_run_at": "2026-04-16T09:00:00+00:00",
                "slack_channel_ids": ["C123"],
            },
            {
                "id": "auto-002",
                "name": "Weekly Report",
                "schedule": {"occurrence": "weekly", "when": "17:00", "days": [1]},
                "timezone": "Europe/Tbilisi",
                "is_active": False,
                "next_run_at": None,
                "slack_channel_ids": ["C123", "C456"],
            },
        ]

        with patch(
            "app.services.automation_service.list_automations",
            return_value=fake_automations,
        ) as mock_list:
            ctx = _make_ctx()
            result = await list_automations_fn(ctx)

        assert mock_list.called, (
            "automation_service.list_automations was not called by the tool. "
            "STORY-018-04 R1: tool must delegate to automation_service.list_automations."
        )

        assert isinstance(result, str), (
            f"Tool must return str, got {type(result).__name__!r}. "
            "STORY-018-04 R1: all tools return str."
        )

        assert "Daily Standup" in result, (
            f"Expected 'Daily Standup' in result. Got: {result!r}. "
            "STORY-018-04 R1: list_automations must include all automation names."
        )

        assert "Weekly Report" in result, (
            f"Expected 'Weekly Report' in result. Got: {result!r}. "
            "STORY-018-04 R1: list_automations must include all automation names."
        )


# ---------------------------------------------------------------------------
# Test 4: list_automations — empty workspace
# ---------------------------------------------------------------------------


class TestListAutomationsEmpty:
    """Scenario: List automations — empty workspace.

    Given workspace W has no automations,
    When the agent calls list_automations(),
    Then the tool returns "No automations configured for this workspace."
    """

    @pytest.mark.asyncio
    async def test_list_automations_tool_empty(self) -> None:
        """list_automations tool must return the canonical empty-state string when no automations exist.

        The exact string "No automations configured for this workspace." must be returned.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        list_automations_fn = getattr(agent_module, "list_automations")

        with patch(
            "app.services.automation_service.list_automations",
            return_value=[],
        ):
            ctx = _make_ctx()
            result = await list_automations_fn(ctx)

        assert isinstance(result, str), (
            f"Tool must return str, got {type(result).__name__!r}."
        )

        assert "No automations configured for this workspace." in result, (
            f"Expected 'No automations configured for this workspace.' in result. "
            f"Got: {result!r}. "
            "STORY-018-04 R1: canonical empty-state string required."
        )


# ---------------------------------------------------------------------------
# Test 5: update_automation — toggle is_active
# ---------------------------------------------------------------------------


class TestUpdateAutomationToggleActive:
    """Scenario: Update automation — toggle is_active.

    Given automation A exists in workspace W,
    When the agent calls update_automation(automation_id=A.id, is_active=False),
    Then automation_service.update_automation is called with patch={"is_active": False}
    And the tool returns a confirmation string.
    """

    @pytest.mark.asyncio
    async def test_update_automation_tool_toggle_active(self) -> None:
        """update_automation tool must call service with only the non-None fields as patch.

        When is_active=False is passed (and all other optional params are None),
        the patch dict passed to the service must be {"is_active": False}.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        update_automation_fn = getattr(agent_module, "update_automation")

        fake_updated_row = {
            "id": FAKE_AUTOMATION_ID,
            "name": FAKE_AUTOMATION_NAME,
            "is_active": False,
        }

        with patch(
            "app.services.automation_service.update_automation",
            return_value=fake_updated_row,
        ) as mock_update:
            ctx = _make_ctx()
            result = await update_automation_fn(
                ctx,
                automation_id=FAKE_AUTOMATION_ID,
                is_active=False,
            )

        assert mock_update.called, (
            "automation_service.update_automation was not called by the tool. "
            "STORY-018-04 R1: tool must delegate to automation_service.update_automation."
        )

        # Verify patch dict contains is_active and not the None optional fields
        call_kwargs = mock_update.call_args
        patch_arg = call_kwargs.kwargs.get("patch")
        if patch_arg is None and len(call_kwargs.args) >= 3:
            patch_arg = call_kwargs.args[2]

        if patch_arg is not None:
            assert "is_active" in patch_arg, (
                f"Expected 'is_active' in patch dict. Got: {patch_arg!r}. "
                "STORY-018-04 R1: update_automation must pass non-None fields in patch."
            )
            assert patch_arg.get("is_active") is False, (
                f"Expected patch['is_active'] == False. Got: {patch_arg!r}."
            )
            # None-valued optional fields must not appear in patch
            for none_field in ("name", "prompt", "schedule", "slack_channel_ids", "timezone", "description"):
                assert none_field not in patch_arg, (
                    f"Field {none_field!r} must not appear in patch when value is None. "
                    f"Got patch: {patch_arg!r}."
                )

        assert isinstance(result, str), (
            f"Tool must return str, got {type(result).__name__!r}."
        )


# ---------------------------------------------------------------------------
# Test 6: delete_automation — found (service returns True)
# ---------------------------------------------------------------------------


class TestDeleteAutomationFound:
    """Scenario: Delete automation — found.

    Given automation A exists in workspace W,
    When the agent calls delete_automation(automation_id=A.id),
    Then automation_service.delete_automation returns True
    And the tool returns a string containing "deleted".
    """

    @pytest.mark.asyncio
    async def test_delete_automation_tool_found(self) -> None:
        """delete_automation tool must return a string containing 'deleted' when service returns True.

        The service returning True signals the automation was found and deleted.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        delete_automation_fn = getattr(agent_module, "delete_automation")

        with patch(
            "app.services.automation_service.delete_automation",
            return_value=True,
        ) as mock_delete:
            ctx = _make_ctx()
            result = await delete_automation_fn(ctx, automation_id=FAKE_AUTOMATION_ID)

        assert mock_delete.called, (
            "automation_service.delete_automation was not called by the tool. "
            "STORY-018-04 R1: tool must delegate to automation_service.delete_automation."
        )

        assert isinstance(result, str), (
            f"Tool must return str, got {type(result).__name__!r}."
        )

        assert "deleted" in result.lower(), (
            f"Expected 'deleted' in result when service returns True. "
            f"Got: {result!r}. "
            "STORY-018-04 R1: delete_automation must return a string containing 'deleted'."
        )


# ---------------------------------------------------------------------------
# Test 7: delete_automation — not found (service returns False)
# ---------------------------------------------------------------------------


class TestDeleteAutomationNotFound:
    """Scenario: Delete automation — not found.

    Given no automation with that ID in workspace W,
    When the agent calls delete_automation(automation_id="nonexistent"),
    Then the tool returns "Automation not found."
    """

    @pytest.mark.asyncio
    async def test_delete_automation_tool_not_found(self) -> None:
        """delete_automation tool must return 'Automation not found.' when service returns False.

        The exact string "Automation not found." is required by the spec.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        delete_automation_fn = getattr(agent_module, "delete_automation")

        with patch(
            "app.services.automation_service.delete_automation",
            return_value=False,
        ):
            ctx = _make_ctx()
            result = await delete_automation_fn(ctx, automation_id="nonexistent-id")

        assert isinstance(result, str), (
            f"Tool must return str, got {type(result).__name__!r}."
        )

        assert result == "Automation not found.", (
            f"Expected exactly 'Automation not found.' when service returns False. "
            f"Got: {result!r}. "
            "STORY-018-04 R1: exact canonical not-found string required."
        )


# ---------------------------------------------------------------------------
# Test 8: _build_system_prompt includes automations section when automations exist
# ---------------------------------------------------------------------------


class TestSystemPromptWithAutomations:
    """Scenario: System prompt includes automations section when automations exist.

    Given workspace W has 1 active automation,
    When _build_system_prompt(skills=[], automations=[{...}]) is called,
    Then the system prompt contains "## Scheduled Automations" and "create_automation".
    """

    def test_system_prompt_includes_automations_section_when_automations_exist(self) -> None:
        """_build_system_prompt must inject the ## Scheduled Automations section when automations is non-empty.

        The automations parameter does not exist yet — calling with it will raise TypeError
        (correct RED Phase failure). After Green Phase, the section must include "create_automation".
        """
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        fake_automation = {
            "id": FAKE_AUTOMATION_ID,
            "name": FAKE_AUTOMATION_NAME,
            "schedule": FAKE_SCHEDULE_DAILY,
            "timezone": "UTC",
            "is_active": True,
            "next_run_at": "2026-04-16T09:00:00+00:00",
            "slack_channel_ids": [FAKE_CHANNEL_ID],
        }

        # Calling with automations=[...] will TypeError in RED Phase because the
        # parameter does not exist yet in _build_system_prompt — correct RED failure.
        prompt = _build_system_prompt(skills=[], automations=[fake_automation])

        assert "## Scheduled Automations" in prompt, (
            f"Expected '## Scheduled Automations' section in system prompt when automations exist. "
            f"Got prompt (first 500 chars): {prompt[:500]!r}. "
            "STORY-018-04 R2: inject automations section only when automations is non-empty."
        )

        assert "create_automation" in prompt, (
            f"Expected 'create_automation' tool listed in automations section. "
            f"Got prompt (first 500 chars): {prompt[:500]!r}. "
            "STORY-018-04 R2: _AUTOMATIONS_PROMPT_SECTION must document the create_automation tool."
        )


# ---------------------------------------------------------------------------
# Test 9: _build_system_prompt omits automations section when no automations
# ---------------------------------------------------------------------------


class TestSystemPromptWithoutAutomations:
    """Scenario: System prompt omits automations section when no automations.

    Given workspace W has 0 automations,
    When _build_system_prompt(skills=[], automations=[]) is called,
    Then the system prompt does NOT contain "## Scheduled Automations".
    """

    def test_system_prompt_omits_automations_section_when_no_automations(self) -> None:
        """_build_system_prompt must NOT inject ## Scheduled Automations when automations=[] or None.

        The section is keyword-gated: only injected when automations is a non-empty list.
        Calling with automations=[] will TypeError in RED Phase if the param doesn't exist.
        """
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        # automations=[] — should TypeError in RED (param not yet added) or pass False-gate check
        prompt = _build_system_prompt(skills=[], automations=[])

        assert "## Scheduled Automations" not in prompt, (
            f"'## Scheduled Automations' section MUST NOT appear when automations is empty. "
            f"Got prompt (first 500 chars): {prompt[:500]!r}. "
            "STORY-018-04 R2: section is only injected when automations is a non-empty list."
        )
