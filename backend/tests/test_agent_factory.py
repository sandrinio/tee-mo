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

# Minimal teemo_slack_teams row — seeded so any decrypt call on the encrypted
# bot-token field gets a real string instead of a MagicMock, preventing:
#   TypeError: argument should be a bytes-like object or ASCII string, not 'MagicMock'
FAKE_SLACK_TEAM_ROW_AF: dict = {
    "slack_team_id": "T_AGENT_FACTORY_001",
    "owner_user_id": USER_ID,
    "encrypted_slack_bot_token": "encrypted-agent-factory-bot-token",
}


def _make_execute_result_af(data: list) -> MagicMock:
    """Return a MagicMock whose .data holds the given list (agent-factory local helper)."""
    r = MagicMock()
    r.data = data
    return r


def _make_supabase_mock(workspace_row: dict | None) -> MagicMock:
    """Build a Supabase client mock that dispatches table queries by name.

    - teemo_workspaces  → returns workspace_row via maybe_single().execute()
    - teemo_slack_teams → returns FAKE_SLACK_TEAM_ROW_AF via select().eq().limit().execute()
    - all other tables  → return a generic chain (data defaults to workspace_row dict)

    Seeding teemo_slack_teams prevents the TypeError that arises when
    encryption.decrypt receives a MagicMock instead of a bytes-like string.
    """
    mock_result = MagicMock()
    mock_result.data = workspace_row

    # Workspace chain (maybe_single path used by build_agent step 1)
    ws_chain = MagicMock()
    ws_chain.maybe_single.return_value = ws_chain
    ws_chain.execute.return_value = mock_result
    ws_chain.eq.return_value = ws_chain
    ws_chain.select.return_value = ws_chain

    # Slack-teams chain (seeded row — prevents MagicMock decrypt TypeError)
    st_chain = MagicMock()
    st_chain.eq.return_value = st_chain
    st_chain.limit.return_value = st_chain
    st_chain.execute.return_value = _make_execute_result_af([FAKE_SLACK_TEAM_ROW_AF])
    st_chain.select.return_value = st_chain

    supabase = MagicMock()

    def _dispatch(table_name: str) -> MagicMock:
        """Route supabase.table() calls to the appropriate mock chain."""
        if table_name == "teemo_workspaces":
            return ws_chain
        if table_name == "teemo_slack_teams":
            return st_chain
        # Generic fallback: return the workspace chain — it handles the
        # .select().eq().execute() and .execute() patterns gracefully
        # (data = workspace_row; isinstance check guards against non-list).
        return ws_chain

    supabase.table.side_effect = _dispatch
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
    assert len(tools_arg) == 14, (
        f"Expected 14 tools, got {len(tools_arg)}. "
        "Required: load_skill, create_skill, update_skill, delete_skill, web_search, crawl_page, "
        "http_request, read_document, create_document, update_document, delete_document, "
        "search_wiki, read_wiki_page, lint_wiki"
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
# Tests for Gherkin scenarios (STORY-015-03 refactor):
#   1. System prompt includes document catalog when workspace has documents
#   2. System prompt omits document section when no documents
#   3. read_document returns content by UUID
#   4. read_document returns "Document not found." for unknown UUID
# ---------------------------------------------------------------------------


def _make_supabase_mock_with_documents(
    workspace_row: dict,
    documents: list[dict],
) -> MagicMock:
    """Build a Supabase client mock that routes different table queries correctly.

    Routes:
      - teemo_workspaces  → returns workspace_row via maybe_single().execute()
      - teemo_documents   → returns documents via execute() (no maybe_single)

    STORY-015-03: replaces the legacy teemo_knowledge_index routing.

    Args:
        workspace_row: Workspace dict as returned by DB (ai_provider, etc.).
        documents:     List of document rows (id, title, ai_description).
    """
    # Result for workspace query (maybe_single path)
    workspace_result = MagicMock()
    workspace_result.data = workspace_row

    workspace_chain = MagicMock()
    workspace_chain.maybe_single.return_value = workspace_chain
    workspace_chain.execute.return_value = workspace_result
    workspace_chain.eq.return_value = workspace_chain
    workspace_chain.select.return_value = workspace_chain

    # Result for teemo_documents query (direct execute path)
    docs_result = MagicMock()
    docs_result.data = documents

    docs_chain = MagicMock()
    docs_chain.execute.return_value = docs_result
    docs_chain.eq.return_value = docs_chain
    docs_chain.select.return_value = docs_chain

    supabase = MagicMock()

    # Slack-teams chain (seeded row — prevents MagicMock decrypt TypeError)
    st_chain_doc = MagicMock()
    st_chain_doc.eq.return_value = st_chain_doc
    st_chain_doc.limit.return_value = st_chain_doc
    st_chain_doc.execute.return_value = _make_execute_result_af([FAKE_SLACK_TEAM_ROW_AF])
    st_chain_doc.select.return_value = st_chain_doc

    def _table_router(table_name: str) -> MagicMock:
        """Route supabase.table() calls to the correct chain by table name."""
        if table_name == "teemo_documents":
            return docs_chain
        if table_name == "teemo_slack_teams":
            return st_chain_doc
        return workspace_chain

    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Scenario 1: System prompt includes document catalog when workspace has documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_includes_available_documents_section(monkeypatch: Any) -> None:
    """When workspace has 3 documents, system_prompt contains '## Available Documents'
    and lists all 3 with UUID id, title, and ai_description.

    Verifies R2 from STORY-015-03: _build_system_prompt appends the document catalog
    when documents is non-empty, and build_agent() queries teemo_documents and passes
    results to the prompt builder.
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

    documents = [
        {
            "id": "uuid-doc-001",
            "title": "Q3 Financial Report",
            "ai_description": "Quarterly financial summary for Q3.",
        },
        {
            "id": "uuid-doc-002",
            "title": "Engineering Roadmap",
            "ai_description": "Technical roadmap for the engineering team.",
        },
        {
            "id": "uuid-doc-003",
            "title": "HR Policy Handbook",
            "ai_description": "Company HR policies and procedures.",
        },
    ]

    supabase = _make_supabase_mock_with_documents(_workspace_row(), documents)

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    assert mock_agent_cls.call_count == 1
    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None, "Agent() must be called with system_prompt= kwarg"
    assert "## Available Documents" in system_prompt, (
        "system_prompt must contain '## Available Documents' when workspace has indexed documents"
    )

    # All 3 documents must be listed with all 3 fields
    for d in documents:
        assert d["id"] in system_prompt, (
            f"document id '{d['id']}' must appear in system_prompt"
        )
        assert d["title"] in system_prompt, (
            f"title '{d['title']}' must appear in system_prompt"
        )
        assert d["ai_description"] in system_prompt, (
            f"ai_description '{d['ai_description']}' must appear in system_prompt"
        )


# ---------------------------------------------------------------------------
# Scenario 2: System prompt omits document section when no documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_system_prompt_omits_available_documents_when_no_documents(monkeypatch: Any) -> None:
    """When workspace has 0 documents, system_prompt does NOT contain '## Available Documents'.

    The section is omitted entirely when documents is empty — no empty header.
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

    # Empty documents
    supabase = _make_supabase_mock_with_documents(_workspace_row(), [])

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    call_kwargs = mock_agent_cls.call_args[1]
    system_prompt = call_kwargs.get("system_prompt")

    assert system_prompt is not None
    assert "## Available Documents" not in system_prompt, (
        "system_prompt must NOT contain '## Available Documents' when no documents are indexed"
    )


# ---------------------------------------------------------------------------
# Helper: build a supabase mock for read_document tool tests.
# Needs to handle 2 distinct table query patterns:
#   1. teemo_workspaces (workspace row for build_agent) — maybe_single chain
#   2. teemo_documents (for doc catalog in build_agent) — execute chain
#   3. teemo_documents (for read_document_content call) — maybe_single chain
# ---------------------------------------------------------------------------


def _make_doc_tool_supabase(
    workspace_row: dict,
    docs_for_prompt: list[dict],
    read_doc_content: str | None,
) -> MagicMock:
    """Build a multi-query Supabase mock for read_document tool scenario tests.

    The mock tracks call count to route distinct query phases:
      Phase 1: build_agent workspace query    → workspace_row (maybe_single)
      Phase 2: build_agent teemo_documents    → docs_for_prompt (execute)
      Phase 3: read_document_content lookup   → read_doc_content (maybe_single)

    Args:
        workspace_row:    Full workspace dict with ai_provider, ai_model, etc.
        docs_for_prompt:  Documents injected into system prompt during build.
        read_doc_content: Content string returned for the document read, or None
                          for "not found".
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

    # -- build_agent teemo_documents catalog chain (direct execute path) --
    docs_build_result = MagicMock()
    docs_build_result.data = docs_for_prompt
    docs_build_chain = MagicMock()
    docs_build_chain.execute.return_value = docs_build_result
    docs_build_chain.eq.return_value = docs_build_chain
    docs_build_chain.select.return_value = docs_build_chain

    # -- read_document_content lookup (maybe_single path) --
    doc_read_result = MagicMock()
    doc_read_result.data = {"content": read_doc_content} if read_doc_content is not None else None
    doc_read_chain = MagicMock()
    doc_read_chain.maybe_single.return_value = doc_read_chain
    doc_read_chain.execute.return_value = doc_read_result
    doc_read_chain.eq.return_value = doc_read_chain
    doc_read_chain.select.return_value = doc_read_chain

    # Track call sequence to route multiple teemo_documents calls correctly.
    _docs_call_count = [0]

    # Slack-teams chain (seeded row — prevents MagicMock decrypt TypeError)
    st_chain_dt = MagicMock()
    st_chain_dt.eq.return_value = st_chain_dt
    st_chain_dt.limit.return_value = st_chain_dt
    st_chain_dt.execute.return_value = _make_execute_result_af([FAKE_SLACK_TEAM_ROW_AF])
    st_chain_dt.select.return_value = st_chain_dt

    def _table_router(table_name: str) -> MagicMock:
        """Return appropriate chain based on table name and call order."""
        if table_name == "teemo_workspaces":
            return ws_build_chain
        if table_name == "teemo_documents":
            _docs_call_count[0] += 1
            if _docs_call_count[0] == 1:
                return docs_build_chain  # catalog fetch during build_agent
            return doc_read_chain  # content fetch during read_document call
        if table_name == "teemo_slack_teams":
            return st_chain_dt
        return MagicMock()

    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Scenario 3: read_document returns content by UUID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_document_returns_content(monkeypatch: Any) -> None:
    """read_document returns the document content string when the document is found.

    Verifies R1 from STORY-015-03: the tool reads from teemo_documents by UUID
    and returns the content column value.
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

    doc_id = "uuid-doc-abc-001"
    doc_content = "This is the Q3 financial report content."
    doc_row = {
        "id": doc_id,
        "title": "Q3 Report",
        "ai_description": "A Q3 financial report.",
    }
    supabase = _make_doc_tool_supabase(
        workspace_row=_workspace_row(),
        docs_for_prompt=[doc_row],
        read_doc_content=doc_content,
    )

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    # Extract read_document tool from tools list passed to Agent()
    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_document_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_document"),
        None,
    )
    assert read_document_fn is not None, (
        "build_agent must register a tool named 'read_document'"
    )

    # Build a fake ctx with deps
    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_document_fn(mock_ctx, doc_id)

    assert result == doc_content, (
        f"read_document must return document content string, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4: read_document returns "Document not found." for unknown UUID
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_document_returns_not_found_for_unknown_uuid(monkeypatch: Any) -> None:
    """read_document returns 'Document not found.' when the UUID is not in the workspace.

    Verifies the workspace isolation guard from STORY-015-03 R1: if the requested
    document UUID is not present in teemo_documents for this workspace, the tool
    returns the standard not-found message without crashing.
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

    # No documents in prompt; read_doc_content=None simulates not-found.
    supabase = _make_doc_tool_supabase(
        workspace_row=_workspace_row(),
        docs_for_prompt=[],
        read_doc_content=None,
    )

    await agent_module.build_agent(WORKSPACE_ID, USER_ID, supabase)

    tools_arg = mock_agent_cls.call_args.kwargs["tools"]
    read_document_fn = next(
        (t for t in tools_arg if getattr(t, "__name__", "") == "read_document"),
        None,
    )
    assert read_document_fn is not None, (
        "build_agent must register a tool named 'read_document'"
    )

    mock_deps = MagicMock()
    mock_deps.workspace_id = WORKSPACE_ID
    mock_deps.supabase = supabase
    mock_deps.user_id = USER_ID
    mock_ctx = MagicMock()
    mock_ctx.deps = mock_deps

    result = await read_document_fn(mock_ctx, "uuid-does-not-exist")

    assert result == "Document not found.", (
        f"Result must be 'Document not found.' for unknown document UUID, got: {result!r}"
    )
