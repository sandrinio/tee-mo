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
# Test 9: _build_system_prompt ALWAYS includes automations section
#
# Previously this test asserted the section was omitted on empty automations
# (STORY-018-04 R2). In live Slack testing the gate made the first automation
# impossible to create — the LLM never saw the "schedule" / "remind me" /
# "every week" heuristics and routed recurring-task requests to create_skill
# instead. The tools are registered with pydantic-ai unconditionally, so
# hiding the prompt section never prevented tool use; it only prevented
# discovery. Flipped: the section must be present whether or not automations
# already exist.
# ---------------------------------------------------------------------------


class TestSystemPromptAutomationsAlwaysPresent:
    """Scenario: System prompt always includes the automations section.

    Given workspace W has 0 automations,
    When _build_system_prompt(skills=[], automations=[]) is called,
    Then the system prompt still contains "## Scheduled Automations" and
    documents create_automation — so the LLM can create the first automation.
    """

    def test_system_prompt_includes_automations_section_when_no_automations(self) -> None:
        """_build_system_prompt must inject ## Scheduled Automations even on an empty workspace."""
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        prompt = _build_system_prompt(skills=[], automations=[])

        assert "## Scheduled Automations" in prompt, (
            f"'## Scheduled Automations' section must appear even when no automations exist "
            f"(needed so the LLM can create the first one). "
            f"Got prompt (first 500 chars): {prompt[:500]!r}."
        )
        assert "create_automation" in prompt, (
            "create_automation tool must be documented in the system prompt so the LLM "
            "routes recurring-task requests to it instead of create_skill."
        )


# ---------------------------------------------------------------------------
# STORY-018-08 Unit Tests (R2, R3, R4, R5)
# ---------------------------------------------------------------------------


class TestAgentDepsSenderTzDefault:
    """Unit A (STORY-018-08 R2): AgentDeps.sender_tz has default "UTC".

    Constructing AgentDeps without the sender_tz kwarg must work without error
    and the field value must be "UTC".
    """

    def test_agent_deps_sender_tz_default_is_utc(self) -> None:
        """AgentDeps must expose sender_tz with a default of 'UTC'.

        Verifies R2: existing test fixtures that construct AgentDeps without
        sender_tz keep compiling — the default must be present.
        """
        from app.agents.agent import AgentDeps  # type: ignore[import]

        deps = AgentDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=MagicMock(),
        )

        assert hasattr(deps, "sender_tz"), (
            "AgentDeps must have a sender_tz field (STORY-018-08 R2)."
        )
        assert deps.sender_tz == "UTC", (
            f"AgentDeps.sender_tz default must be 'UTC'. Got: {deps.sender_tz!r}. "
            "STORY-018-08 R2: default preserves backward compat."
        )


class TestBuildSystemPromptIncludesUserTzLine:
    """Unit B (STORY-018-08 R3): _build_system_prompt includes user-tz line when set.

    Calling _build_system_prompt with sender_tz="America/Los_Angeles" must
    produce a prompt containing the user's timezone string and a local-time
    line, plus the standing rule about stating the timezone in replies (R4).
    """

    def test_system_prompt_includes_user_tz_when_sender_tz_known(self) -> None:
        """_build_system_prompt must include a 'User's timezone' line when sender_tz is non-UTC."""
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        prompt = _build_system_prompt(skills=[], sender_tz="America/Los_Angeles")

        assert "User's timezone: America/Los_Angeles" in prompt, (
            f"Expected 'User's timezone: America/Los_Angeles' in prompt. "
            f"Got prompt slice (first 800 chars): {prompt[:800]!r}. "
            "STORY-018-08 R3: known tz must produce per-user tz line."
        )
        assert "Current local time for the user:" in prompt, (
            f"Expected 'Current local time for the user:' in prompt when sender_tz is set. "
            f"Got prompt slice: {prompt[:800]!r}."
        )

    def test_system_prompt_includes_standing_timezone_rule(self) -> None:
        """_build_system_prompt must include the standing 'state the timezone' rule (R4).

        The rule applies on every run regardless of sender_tz — it goes in the
        Rules block, not in the tz-conditional section.
        """
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        prompt = _build_system_prompt(skills=[])

        assert "state the timezone" in prompt.lower() or "timezone you used" in prompt.lower(), (
            f"Expected the standing timezone-citation rule in prompt. "
            f"Got prompt Rules section: {prompt[:1000]!r}. "
            "STORY-018-08 R4: 'state the timezone you used' must appear in every prompt."
        )

    def test_system_prompt_softer_variant_when_sender_tz_utc(self) -> None:
        """_build_system_prompt must emit the softer 'unknown tz' variant when sender_tz='UTC'."""
        from app.agents.agent import _build_system_prompt  # type: ignore[import]

        prompt = _build_system_prompt(skills=[], sender_tz="UTC")

        assert "timezone could not be determined" in prompt, (
            f"Expected softer 'timezone could not be determined' variant when sender_tz='UTC'. "
            f"Got prompt slice: {prompt[:800]!r}. "
            "STORY-018-08 R3: UTC fallback must use softer wording."
        )


class TestCreateAutomationUsesSenderTz:
    """Unit C (STORY-018-08 R5): create_automation uses sender_tz when caller omits timezone.

    When the agent calls create_automation without passing timezone,
    the tool must use ctx.deps.sender_tz as the effective timezone.
    """

    @pytest.mark.asyncio
    async def test_create_automation_uses_sender_tz_when_timezone_omitted(self) -> None:
        """create_automation must use ctx.deps.sender_tz when timezone kwarg is absent.

        Verifies R5: the row written to the service has the sender's profile tz,
        not the hardcoded "UTC" default.
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        create_automation_fn = getattr(agent_module, "create_automation")

        captured_payloads: list[dict] = []

        def _fake_create(workspace_id: str, owner_user_id: str, payload: dict, supabase: Any) -> dict:
            captured_payloads.append(payload)
            return {
                "id": FAKE_AUTOMATION_ID,
                "name": FAKE_AUTOMATION_NAME,
                "next_run_at": FAKE_NEXT_RUN_AT,
                "slack_channel_ids": [FAKE_CHANNEL_ID],
                "timezone": payload.get("timezone"),
            }

        with patch(
            "app.services.automation_service.create_automation",
            side_effect=_fake_create,
        ):
            # Construct context with sender_tz set to a non-UTC zone
            from app.agents.agent import AgentDeps  # type: ignore[import]
            deps = AgentDeps(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=MagicMock(),
                sender_tz="America/Los_Angeles",
            )
            ctx = MagicMock()
            ctx.deps = deps

            # Call without passing timezone — tool must fall back to deps.sender_tz
            result = await create_automation_fn(
                ctx,
                name=FAKE_AUTOMATION_NAME,
                prompt="Daily standup",
                schedule=FAKE_SCHEDULE_DAILY,
                slack_channel_ids=[FAKE_CHANNEL_ID],
            )

        assert captured_payloads, "automation_service.create_automation must have been called"
        effective_tz = captured_payloads[0].get("timezone")
        assert effective_tz == "America/Los_Angeles", (
            f"Expected timezone='America/Los_Angeles' in service payload (from deps.sender_tz). "
            f"Got: {effective_tz!r}. "
            "STORY-018-08 R5: create_automation must use sender_tz when caller omits timezone."
        )

        # The tool result string must echo the final tz so the agent can cite it.
        assert isinstance(result, str)
        assert "America/Los_Angeles" in result, (
            f"Expected tz echoed in tool result string for agent citation. Got: {result!r}."
        )


class TestCreateAutomationHonorsExplicitOverride:
    """Unit D (STORY-018-08 R5): create_automation honors an explicit timezone override.

    When the agent passes timezone="America/New_York" explicitly, that value
    must win over ctx.deps.sender_tz="America/Los_Angeles".
    """

    @pytest.mark.asyncio
    async def test_create_automation_explicit_timezone_overrides_sender_tz(self) -> None:
        """Explicit timezone parameter must override ctx.deps.sender_tz.

        Verifies R5: the model can always override the profile default by
        passing an explicit IANA string (e.g. "9am New York time").
        """
        import app.agents.agent as agent_module  # type: ignore[import]

        create_automation_fn = getattr(agent_module, "create_automation")

        captured_payloads: list[dict] = []

        def _fake_create(workspace_id: str, owner_user_id: str, payload: dict, supabase: Any) -> dict:
            captured_payloads.append(payload)
            return {
                "id": FAKE_AUTOMATION_ID,
                "name": FAKE_AUTOMATION_NAME,
                "next_run_at": FAKE_NEXT_RUN_AT,
                "slack_channel_ids": [FAKE_CHANNEL_ID],
                "timezone": payload.get("timezone"),
            }

        with patch(
            "app.services.automation_service.create_automation",
            side_effect=_fake_create,
        ):
            from app.agents.agent import AgentDeps  # type: ignore[import]
            deps = AgentDeps(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=MagicMock(),
                sender_tz="America/Los_Angeles",
            )
            ctx = MagicMock()
            ctx.deps = deps

            # Explicit override — must win over sender_tz
            result = await create_automation_fn(
                ctx,
                name=FAKE_AUTOMATION_NAME,
                prompt="5pm New York standup",
                schedule=FAKE_SCHEDULE_DAILY,
                slack_channel_ids=[FAKE_CHANNEL_ID],
                timezone="America/New_York",
            )

        assert captured_payloads, "automation_service.create_automation must have been called"
        effective_tz = captured_payloads[0].get("timezone")
        assert effective_tz == "America/New_York", (
            f"Expected explicit override timezone='America/New_York' in service payload. "
            f"Got: {effective_tz!r}. "
            "STORY-018-08 R5: explicit timezone must override ctx.deps.sender_tz."
        )

        assert isinstance(result, str)
        assert "America/New_York" in result, (
            f"Expected override tz echoed in tool result string. Got: {result!r}."
        )
