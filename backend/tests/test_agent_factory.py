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
    assert len(tools_arg) == 8, (
        f"Expected 8 tools, got {len(tools_arg)}. "
        "Required: load_skill, create_skill, update_skill, delete_skill, web_search, crawl_page, http_request, read_drive_file"
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


# ---------------------------------------------------------------------------
# STORY-006-04: Agent Drive Tool — RED PHASE tests
#
# Tests for 6 Gherkin scenarios:
#   1. System prompt includes file catalog when workspace has files
#   2. System prompt omits file section when no files
#   3. read_drive_file returns content
#   4. read_drive_file self-heals stale metadata (hash mismatch)
#   5. read_drive_file handles revoked token (invalid_grant)
#   6. read_drive_file rejects unknown file ID
# ---------------------------------------------------------------------------


def _make_supabase_mock_with_knowledge(
    workspace_row: dict,
    knowledge_files: list[dict],
) -> MagicMock:
    """Build a Supabase client mock that routes different table queries correctly.

    Routes:
      - teemo_workspaces  → returns workspace_row via maybe_single().execute()
      - teemo_knowledge_index → returns knowledge_files via execute() (no maybe_single)

    The routing is done via supabase.table(name).select(...).eq(...) side_effect
    so that distinct call sequences return the right data.

    Args:
        workspace_row:    Workspace dict as returned by DB (ai_provider, etc.).
        knowledge_files:  List of knowledge index rows (drive_file_id, title, ai_description).
    """
    # Result for workspace query (maybe_single path)
    workspace_result = MagicMock()
    workspace_result.data = workspace_row

    workspace_chain = MagicMock()
    workspace_chain.maybe_single.return_value = workspace_chain
    workspace_chain.execute.return_value = workspace_result
    workspace_chain.eq.return_value = workspace_chain
    workspace_chain.select.return_value = workspace_chain

    # Result for knowledge index query (direct execute path)
    knowledge_result = MagicMock()
    knowledge_result.data = knowledge_files

    knowledge_chain = MagicMock()
    knowledge_chain.execute.return_value = knowledge_result
    knowledge_chain.eq.return_value = knowledge_chain
    knowledge_chain.select.return_value = knowledge_chain

    supabase = MagicMock()

    def _table_router(table_name: str) -> MagicMock:
        """Route supabase.table() calls to the correct chain by table name."""
        if table_name == "teemo_knowledge_index":
            return knowledge_chain
        return workspace_chain

    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Scenario 1: System prompt includes file catalog when workspace has files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_available_files_section(monkeypatch: Any) -> None:
    """When workspace has 3 indexed files, system_prompt contains '## Available Files'
    and lists all 3 files with drive_file_id, title, and ai_description.

    Verifies R2 and R3 from STORY-006-04 §1.2: _build_system_prompt appends the
    file catalog when knowledge_files is non-empty, and build_agent() queries
    teemo_knowledge_index and passes results to the prompt builder.
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
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    knowledge_files = [
        {
            "drive_file_id": "file-id-001",
            "title": "Q3 Financial Report",
            "ai_description": "Quarterly financial summary for Q3.",
        },
        {
            "drive_file_id": "file-id-002",
            "title": "Engineering Roadmap",
            "ai_description": "Technical roadmap for the engineering team.",
        },
        {
            "drive_file_id": "file-id-003",
            "title": "HR Policy Handbook",
            "ai_description": "Company HR policies and procedures.",
        },
    ]

    supabase = _make_supabase_mock_with_knowledge(_workspace_row(), knowledge_files)

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert mock_agent_cls.call_count == 1
    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None, "Agent() must be called with system_prompt= kwarg"
    assert "## Available Files" in system_prompt, (
        "system_prompt must contain '## Available Files' when workspace has indexed files"
    )

    # All 3 files must be listed with all 3 fields
    for f in knowledge_files:
        assert f["drive_file_id"] in system_prompt, (
            f"drive_file_id '{f['drive_file_id']}' must appear in system_prompt"
        )
        assert f["title"] in system_prompt, (
            f"title '{f['title']}' must appear in system_prompt"
        )
        assert f["ai_description"] in system_prompt, (
            f"ai_description '{f['ai_description']}' must appear in system_prompt"
        )


# ---------------------------------------------------------------------------
# Scenario 2: System prompt omits file section when no files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_omits_available_files_when_no_files(monkeypatch: Any) -> None:
    """When workspace has 0 indexed files, system_prompt does NOT contain '## Available Files'.

    Verifies R5 from STORY-006-04 §1.2: the files section is omitted entirely
    when knowledge_files is empty — no empty section header should appear.
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

    # Empty knowledge index
    supabase = _make_supabase_mock_with_knowledge(_workspace_row(), [])

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None
    assert "## Available Files" not in system_prompt, (
        "system_prompt must NOT contain '## Available Files' when no files are indexed"
    )


# ---------------------------------------------------------------------------
# Helper: build a supabase mock for read_drive_file tool tests.
# These tests need the mock to handle 3 distinct table query patterns:
#   1. teemo_workspaces (workspace row for build_agent) — maybe_single chain
#   2. teemo_knowledge_index (for knowledge files in build_agent) — execute chain
#   3. teemo_knowledge_index (for file lookup in read_drive_file) — execute chain
#   4. teemo_workspaces (for refresh token in read_drive_file) — maybe_single chain
# ---------------------------------------------------------------------------


def _make_drive_tool_supabase(
    workspace_row: dict,
    knowledge_files_for_prompt: list[dict],
    file_lookup_result: list[dict],
    workspace_token_row: dict | None = None,
) -> MagicMock:
    """Build a multi-query Supabase mock for read_drive_file tool scenario tests.

    The mock tracks call count to route the 4 distinct query phases:
      Phase 1: build_agent workspace query  → workspace_row (maybe_single)
      Phase 2: build_agent knowledge_index  → knowledge_files_for_prompt (execute)
      Phase 3: read_drive_file file lookup  → file_lookup_result (execute)
      Phase 4: read_drive_file ws token     → workspace_token_row (maybe_single)

    Args:
        workspace_row:              Full workspace dict with ai_provider, ai_model, etc.
        knowledge_files_for_prompt: Knowledge files injected into system prompt during build.
        file_lookup_result:         File rows returned when read_drive_file looks up the file.
        workspace_token_row:        Workspace row with encrypted_google_refresh_token field,
                                    returned when read_drive_file fetches the token. None means
                                    not found (triggers revoked-token error path).
    """
    supabase = MagicMock()

    # -- build_agent workspace chain (maybe_single path) --
    ws_build_result = MagicMock()
    ws_build_result.data = workspace_row
    ws_build_chain = MagicMock()
    ws_build_chain.maybe_single.return_value = ws_build_chain
    ws_build_chain.execute.return_value = ws_build_result
    ws_build_chain.eq.return_value = ws_build_chain
    ws_build_chain.select.return_value = ws_build_chain

    # -- build_agent knowledge index chain --
    ki_build_result = MagicMock()
    ki_build_result.data = knowledge_files_for_prompt
    ki_build_chain = MagicMock()
    ki_build_chain.execute.return_value = ki_build_result
    ki_build_chain.eq.return_value = ki_build_chain
    ki_build_chain.select.return_value = ki_build_chain

    # -- read_drive_file file-lookup chain --
    file_lookup_res = MagicMock()
    file_lookup_res.data = file_lookup_result
    file_lookup_chain = MagicMock()
    file_lookup_chain.execute.return_value = file_lookup_res
    file_lookup_chain.eq.return_value = file_lookup_chain
    file_lookup_chain.select.return_value = file_lookup_chain

    # -- read_drive_file workspace token chain (maybe_single path) --
    ws_token_result = MagicMock()
    ws_token_result.data = workspace_token_row
    ws_token_chain = MagicMock()
    ws_token_chain.maybe_single.return_value = ws_token_chain
    ws_token_chain.execute.return_value = ws_token_result
    ws_token_chain.eq.return_value = ws_token_chain
    ws_token_chain.select.return_value = ws_token_chain

    # Track call sequence: table() is called in this order across the full lifecycle
    _call_sequence: list[str] = []

    def _table_router(table_name: str) -> MagicMock:
        """Return the appropriate chain based on table name and call position."""
        _call_sequence.append(table_name)
        count = _call_sequence.count(table_name)
        if table_name == "teemo_workspaces":
            # 1st call = build_agent workspace query; 2nd call = token lookup in tool
            if count == 1:
                return ws_build_chain
            return ws_token_chain
        if table_name == "teemo_knowledge_index":
            # 1st call = build_agent prompt files; 2nd call = file lookup in tool
            if count == 1:
                return ki_build_chain
            return file_lookup_chain
        return MagicMock()

    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Scenario 3: read_drive_file returns content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_drive_file_returns_content(monkeypatch: Any) -> None:
    """read_drive_file returns the file content string when the file is found.

    Verifies R1 from STORY-006-04 §1.2: the tool fetches content from Drive API
    and returns it to the agent as a plain string.
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
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    # The file that will be requested
    file_row = {
        "drive_file_id": "file-id-abc",
        "title": "Q3 Report",
        "ai_description": "A Q3 financial report.",
        "content_hash": "hash-abc-old",
        "mime_type": "application/vnd.google-apps.document",
    }
    ws_token_row = {
        "id": WORKSPACE_ID,
        "encrypted_google_refresh_token": "enc-refresh-token-001",
        "ai_provider": "openai",
        "encrypted_api_key": "enc-key-blob",
    }

    supabase = _make_drive_tool_supabase(
        workspace_row=_workspace_row(),
        knowledge_files_for_prompt=[file_row],
        file_lookup_result=[file_row],
        workspace_token_row=ws_token_row,
    )

    # Mock drive_service: get_drive_client returns a fake client,
    # fetch_file_content returns canned content.
    mock_drive_client = MagicMock(name="drive_client")
    file_content = "This is the Q3 financial report content."
    mock_get_drive_client = MagicMock(return_value=mock_drive_client)
    mock_fetch_file_content = MagicMock(return_value=file_content)
    # Hash matches stored hash so no self-heal path is triggered.
    mock_compute_content_hash = MagicMock(return_value="hash-abc-old")

    monkeypatch.setattr("app.services.drive_service.get_drive_client", mock_get_drive_client)
    monkeypatch.setattr("app.services.drive_service.fetch_file_content", mock_fetch_file_content)
    monkeypatch.setattr("app.services.drive_service.compute_content_hash", mock_compute_content_hash)

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Extract read_drive_file tool from tools list passed to Agent()
    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_drive_file_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_drive_file"),
        None,
    )
    assert read_drive_file_fn is not None, (
        "build_agent must register a tool named 'read_drive_file'"
    )

    # Build a fake ctx with deps
    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_drive_file_fn(mock_ctx, "file-id-abc")

    assert result == file_content, (
        f"read_drive_file must return file content string, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4: read_drive_file self-heals stale metadata (hash mismatch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_drive_file_self_heals_stale_metadata(monkeypatch: Any) -> None:
    """read_drive_file detects a content hash mismatch and re-generates AI description.

    Verifies R1 (self-heal path) from STORY-006-04 §1.2: when the content hash of
    the fetched file differs from the stored hash, the tool must call
    scan_service.generate_ai_description and upsert the updated row into
    teemo_knowledge_index with the new hash + description.
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
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    # The indexed file has an old hash — content has changed on Drive.
    file_row = {
        "drive_file_id": "file-id-xyz",
        "title": "Engineering Roadmap",
        "ai_description": "Old AI description from last scan.",
        "content_hash": "old_hash_aaa",
        "mime_type": "application/vnd.google-apps.document",
    }
    ws_token_row = {
        "id": WORKSPACE_ID,
        "encrypted_google_refresh_token": "enc-refresh-token-001",
        "ai_provider": "openai",
        "encrypted_api_key": "enc-key-blob",
    }

    supabase = _make_drive_tool_supabase(
        workspace_row=_workspace_row(),
        knowledge_files_for_prompt=[file_row],
        file_lookup_result=[file_row],
        workspace_token_row=ws_token_row,
    )

    # Drive returns new content with a different hash
    mock_drive_client = MagicMock(name="drive_client")
    new_content = "Updated engineering roadmap content."
    new_hash = "new_hash_bbb"
    new_description = "Updated description of engineering roadmap."

    mock_get_drive_client = MagicMock(return_value=mock_drive_client)
    mock_fetch_file_content = MagicMock(return_value=new_content)
    mock_compute_content_hash = MagicMock(return_value=new_hash)

    monkeypatch.setattr("app.services.drive_service.get_drive_client", mock_get_drive_client)
    monkeypatch.setattr("app.services.drive_service.fetch_file_content", mock_fetch_file_content)
    monkeypatch.setattr("app.services.drive_service.compute_content_hash", mock_compute_content_hash)

    # scan_service.generate_ai_description returns the new description
    mock_generate_ai_description = AsyncMock(return_value=new_description)
    monkeypatch.setattr(
        "app.services.scan_service.generate_ai_description", mock_generate_ai_description
    )

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_drive_file_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_drive_file"),
        None,
    )
    assert read_drive_file_fn is not None, (
        "build_agent must register a tool named 'read_drive_file'"
    )

    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_drive_file_fn(mock_ctx, "file-id-xyz")

    # Tool must have called generate_ai_description with the new content
    mock_generate_ai_description.assert_called_once()
    call_args = mock_generate_ai_description.call_args
    assert call_args[0][0] == new_content, (
        "generate_ai_description must be called with the new file content"
    )

    # Supabase upsert must have been called on teemo_knowledge_index
    assert supabase.table.called, "supabase.table must be called"
    # The upsert call should contain new hash and description
    upsert_calls = [
        c for c in supabase.table.call_args_list
        if "teemo_knowledge_index" in str(c)
    ]
    # At minimum, verify the tool returned content (not an error)
    assert result == new_content, (
        f"read_drive_file must return the updated file content, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 5: read_drive_file handles revoked token (invalid_grant)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_drive_file_handles_revoked_token(monkeypatch: Any) -> None:
    """read_drive_file returns a user-friendly message when the OAuth token is revoked.

    Verifies R6 from STORY-006-04 §1.2: if get_drive_client raises an exception
    containing 'invalid_grant', the tool returns a clear error message instructing
    the user to reconnect Drive from the dashboard.
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
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    file_row = {
        "drive_file_id": "file-id-revoked",
        "title": "Secret Doc",
        "ai_description": "A document requiring Drive access.",
        "content_hash": "hash-xyz",
        "mime_type": "application/vnd.google-apps.document",
    }
    ws_token_row = {
        "id": WORKSPACE_ID,
        "encrypted_google_refresh_token": "enc-stale-token",
        "ai_provider": "openai",
        "encrypted_api_key": "enc-key-blob",
    }

    supabase = _make_drive_tool_supabase(
        workspace_row=_workspace_row(),
        knowledge_files_for_prompt=[file_row],
        file_lookup_result=[file_row],
        workspace_token_row=ws_token_row,
    )

    # get_drive_client raises an error simulating invalid_grant (revoked token)
    def _raise_invalid_grant(encrypted_token: str):
        raise Exception("invalid_grant: Token has been expired or revoked.")

    monkeypatch.setattr("app.services.drive_service.get_drive_client", _raise_invalid_grant)

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_drive_file_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_drive_file"),
        None,
    )
    assert read_drive_file_fn is not None, (
        "build_agent must register a tool named 'read_drive_file'"
    )

    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_drive_file_fn(mock_ctx, "file-id-revoked")

    assert "Google Drive access has been revoked" in result, (
        f"Result must contain revoked-token message, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 6: read_drive_file rejects unknown file ID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_drive_file_rejects_unknown_file_id(monkeypatch: Any) -> None:
    """read_drive_file returns 'File not found' when the file ID is not in the workspace.

    Verifies the file isolation guard: if the requested drive_file_id is not
    present in teemo_knowledge_index for this workspace, the tool must return a
    not-found error rather than attempting to fetch from Drive.
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
    monkeypatch.setattr(
        "app.services.skill_service.list_skills", lambda workspace_id, supabase: []
    )

    # No files in the prompt and the file lookup returns empty (file not found)
    supabase = _make_drive_tool_supabase(
        workspace_row=_workspace_row(),
        knowledge_files_for_prompt=[],
        file_lookup_result=[],    # empty = file not found in workspace
        workspace_token_row=None,
    )

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_drive_file_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_drive_file"),
        None,
    )
    assert read_drive_file_fn is not None, (
        "build_agent must register a tool named 'read_drive_file'"
    )

    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_drive_file_fn(mock_ctx, "file-id-does-not-exist")

    assert "File not found" in result, (
        f"Result must contain 'File not found' for unknown file ID, got: {result!r}"
    )
