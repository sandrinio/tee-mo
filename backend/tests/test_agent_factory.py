"""
Tests for the agent factory — STORY-007-02 (Red Phase).

Covers all Gherkin scenarios from §2.1:
  1. Build agent with valid workspace (openai)
  2. Build agent with no workspace → ValueError("no_workspace")
  3. Build agent with no key → ValueError("no_key_configured")
  4. System prompt includes skill catalog when skills exist
  5. System prompt omits skills section when no skills exist
  6. Model instantiation for each provider (google, anthropic, openai)
  7. Unsupported provider raises ValueError

Mock strategy:
  - Supabase client is a MagicMock; workspace query returns configured data or empty.
  - `app.core.encryption.decrypt` is patched to return a deterministic plaintext key.
  - Pydantic AI model class module-level globals (GoogleModel, AnthropicModel,
    OpenAIChatModel, GoogleProvider, AnthropicProvider, OpenAIProvider, Agent)
    are replaced with MagicMock via monkeypatch. The factory uses lazy imports via
    `_ensure_model_imports()` so globals start as None and get replaced at first call.
  - `app.services.skill_service.list_skills` is patched to return canned catalogs.
  - Tests are async (build_agent is async) — uses pytest-asyncio.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# The module under test (does not exist yet — tests are RED).
# Importing here so that the test file can be discovered; the import will fail
# until the Green phase implementation is written, which is intentional.
import importlib


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

WORKSPACE_ID = "ws-test-0001"
USER_ID = "user-test-0001"
DECRYPTED_KEY = "plaintext-test-api-key-001"


def _make_supabase_mock(workspace_row: dict | None) -> MagicMock:
    """Build a Supabase client mock that returns `workspace_row` for the
    teemo_workspaces maybe_single() call. If None is passed the query returns
    empty (workspace not found)."""
    mock_result = MagicMock()
    mock_result.data = workspace_row

    chain = MagicMock()
    chain.maybe_single.return_value = chain
    chain.execute.return_value = mock_result
    chain.eq.return_value = chain
    chain.select.return_value = chain

    supabase = MagicMock()
    supabase.table.return_value = chain
    return supabase


def _workspace_row(
    provider: str = "openai",
    model: str = "gpt-4o",
    encrypted_key: str | None = "enc-key-blob",
) -> dict:
    """Return a minimal workspace row dict as returned by Supabase."""
    return {
        "id": WORKSPACE_ID,
        "ai_provider": provider,
        "ai_model": model,
        "encrypted_api_key": encrypted_key,
    }


# ---------------------------------------------------------------------------
# Scenario 1: Build agent with valid workspace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_returns_tuple_with_agent_and_deps(monkeypatch: Any) -> None:
    """build_agent() with a fully configured workspace returns (Agent, AgentDeps).

    Verifies:
      - Return type is a 2-tuple.
      - AgentDeps.workspace_id == WORKSPACE_ID.
      - The Agent object is the value produced by the (mocked) Agent constructor.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    # Patch module-level globals that _ensure_model_imports would populate.
    mock_agent_cls = MagicMock(name="Agent")
    mock_agent_instance = MagicMock(name="agent_instance")
    mock_agent_cls.return_value = mock_agent_instance

    mock_openai_model = MagicMock(name="OpenAIChatModel")
    mock_openai_provider = MagicMock(name="OpenAIProvider")

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)

    # Patch decrypt to return deterministic key.
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)

    # Patch list_skills to return empty (skills section tested separately).
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    supabase = _make_supabase_mock(_workspace_row())

    result = await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert isinstance(result, tuple), "build_agent must return a tuple"
    assert len(result) == 2, "build_agent must return a 2-tuple (Agent, AgentDeps)"

    agent, deps = result
    assert agent is mock_agent_instance, "First element must be the constructed Agent"
    assert deps.workspace_id == WORKSPACE_ID, "AgentDeps.workspace_id must match workspace_id arg"


@pytest.mark.asyncio
async def test_build_agent_registers_four_skill_tools(monkeypatch: Any) -> None:
    """Agent constructed by build_agent() is called with tools= list of exactly 4 items.

    The four tools are: load_skill, create_skill, update_skill, delete_skill.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_agent_cls = MagicMock(name="Agent")
    mock_openai_model = MagicMock(name="OpenAIChatModel")
    mock_openai_provider = MagicMock(name="OpenAIProvider")

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    supabase = _make_supabase_mock(_workspace_row())

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Agent constructor must have been called once.
    assert mock_agent_cls.call_count == 1

    call_kwargs = mock_agent_cls.call_args[1]  # keyword args
    tools_arg = call_kwargs.get("tools")
    assert tools_arg is not None, "Agent() must be called with tools= keyword argument"
    assert len(tools_arg) == 4, (
        f"Expected 4 skill tools, got {len(tools_arg)}. "
        "Required: load_skill, create_skill, update_skill, delete_skill"
    )


@pytest.mark.asyncio
async def test_build_agent_deps_workspace_id_matches(monkeypatch: Any) -> None:
    """AgentDeps.workspace_id must equal the workspace_id argument passed to build_agent."""
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_agent_cls = MagicMock(name="Agent")
    mock_openai_model = MagicMock(name="OpenAIChatModel")
    mock_openai_provider = MagicMock(name="OpenAIProvider")

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    supabase = _make_supabase_mock(_workspace_row())

    _, deps = await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert deps.workspace_id == WORKSPACE_ID
    assert deps.user_id == USER_ID


# ---------------------------------------------------------------------------
# Scenario 2: Build agent with no workspace → ValueError("no_workspace")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_no_workspace_raises_value_error(monkeypatch: Any) -> None:
    """build_agent() raises ValueError('no_workspace') when workspace is not found.

    Supabase mock returns data=None (maybe_single found nothing).
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    supabase = _make_supabase_mock(None)  # workspace not found

    with pytest.raises(ValueError, match="no_workspace"):
        await agent_module.build_agent("ws-nonexistent", USER_ID, supabase)


# ---------------------------------------------------------------------------
# Scenario 3: Build agent with no key → ValueError("no_key_configured")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_agent_no_key_raises_value_error(monkeypatch: Any) -> None:
    """build_agent() raises ValueError('no_key_configured') when encrypted_api_key is null.

    Workspace row exists but encrypted_api_key is None.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    # workspace row has encrypted_api_key=None
    supabase = _make_supabase_mock(_workspace_row(encrypted_key=None))

    with pytest.raises(ValueError, match="no_key_configured"):
        await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)


# ---------------------------------------------------------------------------
# Scenario 4: System prompt includes skill catalog when skills exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_contains_available_skills_section(monkeypatch: Any) -> None:
    """When workspace has active skills, system_prompt contains '## Available Skills'
    and lists both skill name and summary.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_agent_cls = MagicMock(name="Agent")
    mock_agent_instance = MagicMock(name="agent_instance")
    mock_agent_cls.return_value = mock_agent_instance
    mock_openai_model = MagicMock(name="OpenAIChatModel")
    mock_openai_provider = MagicMock(name="OpenAIProvider")

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)

    # Two active skills
    skills = [
        {"name": "daily-standup", "summary": "Use for daily standups"},
        {"name": "budget-report", "summary": "Use for budget analysis"},
    ]
    monkeypatch.setattr(
        "app.services.skill_service.list_skills",
        lambda workspace_id, supabase: skills,
    )

    supabase = _make_supabase_mock(_workspace_row())

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Agent() must have been called with system_prompt=
    assert mock_agent_cls.call_count == 1
    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None, "Agent() must be called with system_prompt= keyword"
    assert "## Available Skills" in system_prompt, (
        "system_prompt must contain '## Available Skills' when skills exist"
    )
    assert "daily-standup" in system_prompt, "system_prompt must list skill name 'daily-standup'"
    assert "Use for daily standups" in system_prompt, (
        "system_prompt must include skill summary 'Use for daily standups'"
    )
    assert "budget-report" in system_prompt, "system_prompt must list skill name 'budget-report'"
    assert "Use for budget analysis" in system_prompt, (
        "system_prompt must include skill summary 'Use for budget analysis'"
    )


# ---------------------------------------------------------------------------
# Scenario 5: System prompt omits skills section when no skills exist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_omits_available_skills_when_no_skills(monkeypatch: Any) -> None:
    """When workspace has 0 active skills, system_prompt does NOT contain '## Available Skills'."""
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_agent_cls = MagicMock(name="Agent")
    mock_openai_model = MagicMock(name="OpenAIChatModel")
    mock_openai_provider = MagicMock(name="OpenAIProvider")

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)
    monkeypatch.setattr("app.core.encryption.decrypt", lambda enc: DECRYPTED_KEY)
    monkeypatch.setattr(
        "app.services.skill_service.list_skills",
        lambda workspace_id, supabase: [],  # empty catalog
    )

    supabase = _make_supabase_mock(_workspace_row())

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None
    assert "## Available Skills" not in system_prompt, (
        "system_prompt must NOT contain '## Available Skills' when no skills exist"
    )


# ---------------------------------------------------------------------------
# Scenario 6: Model instantiation for each provider
# ---------------------------------------------------------------------------


def test_build_pydantic_ai_model_google(monkeypatch: Any) -> None:
    """_build_pydantic_ai_model() with provider='google' returns a GoogleModel instance."""
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_google_model_cls = MagicMock(name="GoogleModel")
    mock_google_model_instance = MagicMock(name="google_model_instance")
    mock_google_model_cls.return_value = mock_google_model_instance

    mock_google_provider_cls = MagicMock(name="GoogleProvider")
    mock_google_provider_instance = MagicMock(name="google_provider_instance")
    mock_google_provider_cls.return_value = mock_google_provider_instance

    monkeypatch.setattr(agent_module, "GoogleModel", mock_google_model_cls)
    monkeypatch.setattr(agent_module, "GoogleProvider", mock_google_provider_cls)

    result = agent_module._build_pydantic_ai_model(
        model_id="gemini-2.5-flash",
        provider="google",
        api_key="test-key",
    )

    mock_google_provider_cls.assert_called_once_with(api_key="test-key")
    mock_google_model_cls.assert_called_once_with(
        "gemini-2.5-flash", provider=mock_google_provider_instance
    )
    assert result is mock_google_model_instance


def test_build_pydantic_ai_model_anthropic(monkeypatch: Any) -> None:
    """_build_pydantic_ai_model() with provider='anthropic' returns an AnthropicModel instance."""
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_model_cls = MagicMock(name="AnthropicModel")
    mock_model_instance = MagicMock(name="anthropic_model_instance")
    mock_model_cls.return_value = mock_model_instance

    mock_provider_cls = MagicMock(name="AnthropicProvider")
    mock_provider_instance = MagicMock(name="anthropic_provider_instance")
    mock_provider_cls.return_value = mock_provider_instance

    monkeypatch.setattr(agent_module, "AnthropicModel", mock_model_cls)
    monkeypatch.setattr(agent_module, "AnthropicProvider", mock_provider_cls)

    result = agent_module._build_pydantic_ai_model(
        model_id="claude-3-5-sonnet-20241022",
        provider="anthropic",
        api_key="test-key",
    )

    mock_provider_cls.assert_called_once_with(api_key="test-key")
    mock_model_cls.assert_called_once_with(
        "claude-3-5-sonnet-20241022", provider=mock_provider_instance
    )
    assert result is mock_model_instance


def test_build_pydantic_ai_model_openai(monkeypatch: Any) -> None:
    """_build_pydantic_ai_model() with provider='openai' returns an OpenAIChatModel instance."""
    import app.agents.agent as agent_module  # type: ignore[import]

    mock_model_cls = MagicMock(name="OpenAIChatModel")
    mock_model_instance = MagicMock(name="openai_model_instance")
    mock_model_cls.return_value = mock_model_instance

    mock_provider_cls = MagicMock(name="OpenAIProvider")
    mock_provider_instance = MagicMock(name="openai_provider_instance")
    mock_provider_cls.return_value = mock_provider_instance

    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_model_cls)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_provider_cls)

    result = agent_module._build_pydantic_ai_model(
        model_id="gpt-4o",
        provider="openai",
        api_key="test-key",
    )

    mock_provider_cls.assert_called_once_with(api_key="test-key")
    mock_model_cls.assert_called_once_with("gpt-4o", provider=mock_provider_instance)
    assert result is mock_model_instance


# ---------------------------------------------------------------------------
# Scenario 7: Unsupported provider raises ValueError
# ---------------------------------------------------------------------------


def test_build_pydantic_ai_model_unsupported_provider_raises(monkeypatch: Any) -> None:
    """_build_pydantic_ai_model() with provider='azure' raises ValueError.

    The factory must not silently accept unknown providers — it must raise
    ValueError so callers can surface a clear configuration error.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    with pytest.raises(ValueError, match="azure"):
        agent_module._build_pydantic_ai_model(
            model_id="gpt-4",
            provider="azure",
            api_key="test-key",
        )


# ---------------------------------------------------------------------------
# Additional: _ensure_model_imports populates module globals
# ---------------------------------------------------------------------------


def test_ensure_model_imports_openai_sets_globals(monkeypatch: Any) -> None:
    """_ensure_model_imports('openai') sets OpenAIChatModel and OpenAIProvider module globals.

    After calling _ensure_model_imports, the module-level names must be non-None.
    This test verifies the lazy-import side effect works correctly by mocking the
    underlying imports so no real pydantic-ai extra is required.
    """
    import app.agents.agent as agent_module  # type: ignore[import]

    # Force globals back to None so _ensure_model_imports runs the import branches.
    monkeypatch.setattr(agent_module, "Agent", None)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", None)
    monkeypatch.setattr(agent_module, "OpenAIProvider", None)

    fake_agent_cls = MagicMock(name="FakeAgent")
    fake_model_cls = MagicMock(name="FakeOpenAIChatModel")
    fake_provider_cls = MagicMock(name="FakeOpenAIProvider")

    # Patch the actual imports inside _ensure_model_imports.
    with (
        patch("pydantic_ai.Agent", fake_agent_cls, create=True),
        patch("pydantic_ai.models.openai.OpenAIChatModel", fake_model_cls, create=True),
        patch("pydantic_ai.providers.openai.OpenAIProvider", fake_provider_cls, create=True),
    ):
        agent_module._ensure_model_imports("openai")

    # After the call the module globals should be non-None.
    assert agent_module.OpenAIChatModel is not None, (
        "OpenAIChatModel global must be set after _ensure_model_imports('openai')"
    )
    assert agent_module.OpenAIProvider is not None, (
        "OpenAIProvider global must be set after _ensure_model_imports('openai')"
    )
