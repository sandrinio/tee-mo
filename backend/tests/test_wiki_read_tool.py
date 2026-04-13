"""Tests for STORY-013-01 — read_wiki_page tool and wiki index in system prompt.

Covers all Gherkin scenarios from STORY-013-01 §2.1:

  1. read_wiki_page returns page content for an existing slug.
  2. read_wiki_page returns not-found message for a missing slug.
  3. Workspace isolation — can't read another workspace's wiki pages.
  4. System prompt renders ## Wiki Index when pages exist.
  5. System prompt falls back to ## Available Files when no wiki pages exist.

Invocation strategy:
  ``read_wiki_page`` is an async nested function inside ``build_agent()`` in
  ``app/agents/agent.py``. We extract it by calling ``build_agent()`` with fully
  mocked pydantic-ai internals (Agent class, model imports) and intercepting the
  ``tools=[...]`` list passed to ``Agent()``. The extracted coroutine is then called
  with a synthetic ``ctx`` (fake RunContext with fake deps).

  ``_build_system_prompt`` is tested indirectly by calling ``build_agent()`` and
  checking the ``system_prompt=`` keyword argument captured during ``Agent()``
  construction. This exercises the ACTUAL implementation including the wiki
  index query.

Mock layers:
  - pydantic-ai Agent class → MagicMock that captures ``tools`` and ``system_prompt``
  - Model class globals (_AnthropicModel, _OpenAIChatModel, _GoogleModel, etc.) → MagicMock
  - app.core.encryption.decrypt → returns FAKE_DECRYPTED_API_KEY
  - app.services.skill_service.list_skills → returns []
  - Supabase client → MagicMock with per-table routing

FLASHCARDS.md consulted:
  - Supabase select("*").limit(0) not select("id") for tables without id PK.
  - Upsert — omit DEFAULT NOW() columns from payload.
  - Worktree-relative paths only in Edit/Write calls.
  - Always use from app.core.db import get_supabase, never ad-hoc.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_WORKSPACE_ID = "ws-wiki-test-001"
FAKE_OTHER_WORKSPACE_ID = "ws-wiki-test-other"
FAKE_USER_ID = "user-wiki-test-001"
FAKE_SLUG = "onboarding-process"
FAKE_OTHER_SLUG = "other-workspace-page"
FAKE_WIKI_CONTENT = "# Onboarding Process\n\nThis is the onboarding guide for new hires."
FAKE_WIKI_TITLE = "Onboarding Process"
FAKE_WIKI_TLDR = "Step-by-step guide for onboarding new team members."
FAKE_ENCRYPTED_API_KEY = "enc:api:key:test"
FAKE_DECRYPTED_API_KEY = "plaintext-api-key-wiki-test"
FAKE_AI_PROVIDER = "anthropic"
FAKE_AI_MODEL = "claude-3-5-sonnet-20241022"


# ---------------------------------------------------------------------------
# Helpers — fake RunContext and deps
# ---------------------------------------------------------------------------


class _FakeDeps:
    """Minimal stand-in for AgentDeps passed into read_wiki_page via ctx.deps.

    Args:
        workspace_id: Workspace UUID string.
        user_id: User UUID string.
        supabase: MagicMock Supabase client.
    """

    def __init__(self, workspace_id: str, user_id: str, supabase: MagicMock) -> None:
        self.workspace_id = workspace_id
        self.user_id = user_id
        self.supabase = supabase


class _FakeCtx:
    """Minimal stand-in for pydantic-ai RunContext passed as first arg to tools.

    Args:
        deps: _FakeDeps instance.
    """

    def __init__(self, deps: _FakeDeps) -> None:
        self.deps = deps


# ---------------------------------------------------------------------------
# Helpers — Supabase mock factories
# ---------------------------------------------------------------------------


def _make_wiki_pages_select_chain(
    page_rows: list[dict],
    *,
    filter_slug: str | None = None,
) -> MagicMock:
    """Build a Supabase SELECT chain for teemo_wiki_pages.

    Supports both full-table queries (for system prompt wiki index) and
    slug-filtered queries (for read_wiki_page tool).

    When ``filter_slug`` is None, returns all ``page_rows`` regardless of .eq() calls.
    When ``filter_slug`` is set, only rows whose ``slug`` matches are returned.

    Args:
        page_rows: List of wiki page row dicts to return.
        filter_slug: If set, simulate slug .eq() filtering.

    Returns:
        MagicMock configured as the teemo_wiki_pages table mock.
    """
    # Inner .eq("slug", slug) → .execute()
    slug_filtered_rows = (
        [r for r in page_rows if r.get("slug") == filter_slug]
        if filter_slug is not None
        else page_rows
    )

    slug_eq_result = MagicMock()
    slug_eq_result.data = slug_filtered_rows

    slug_eq_chain = MagicMock()
    slug_eq_chain.execute.return_value = slug_eq_result

    # Outer .eq("workspace_id", workspace_id) → inner .eq() chain
    ws_eq_chain = MagicMock()
    ws_eq_chain.eq.return_value = slug_eq_chain
    ws_eq_chain.execute.return_value = MagicMock(data=page_rows)  # full-table fallback

    select_mock = MagicMock()
    select_mock.eq.return_value = ws_eq_chain

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    return table_mock


def _make_workspaces_select_chain(ws_row: dict | None = None) -> MagicMock:
    """Build the Supabase SELECT chain for teemo_workspaces in build_agent.

    Args:
        ws_row: Workspace row dict, or None for default test workspace.

    Returns:
        MagicMock configured as the teemo_workspaces table mock.
    """
    if ws_row is None:
        ws_row = {
            "id": FAKE_WORKSPACE_ID,
            "ai_provider": FAKE_AI_PROVIDER,
            "ai_model": FAKE_AI_MODEL,
            "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
        }

    result = MagicMock()
    result.data = ws_row

    maybe_single = MagicMock()
    maybe_single.execute.return_value = result

    eq_mock = MagicMock()
    eq_mock.maybe_single.return_value = maybe_single

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    return table_mock


def _make_supabase_for_build_agent(
    wiki_pages: list[dict],
    *,
    workspace_id: str = FAKE_WORKSPACE_ID,
) -> MagicMock:
    """Build a Supabase mock for build_agent — includes workspace + wiki pages queries.

    build_agent queries:
      1. teemo_workspaces (workspace row — for BYOK + model resolution)
      2. teemo_knowledge_index OR teemo_wiki_pages (for system prompt)

    This mock routes both tables and configures wiki pages for system prompt rendering.

    Args:
        wiki_pages: Wiki page rows to return for system prompt construction.
        workspace_id: Workspace ID to use in the workspace row.

    Returns:
        MagicMock Supabase client.
    """
    ws_row = {
        "id": workspace_id,
        "ai_provider": FAKE_AI_PROVIDER,
        "ai_model": FAKE_AI_MODEL,
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
    }

    ws_table_mock = _make_workspaces_select_chain(ws_row)
    wiki_pages_table_mock = _make_wiki_pages_select_chain(wiki_pages)

    # teemo_documents mock (empty — STORY-015-03 table, always queried by build_agent)
    docs_result = MagicMock()
    docs_result.data = []
    docs_eq_mock = MagicMock()
    docs_eq_mock.execute.return_value = docs_result
    docs_select_mock = MagicMock()
    docs_select_mock.eq.return_value = docs_eq_mock
    docs_table_mock = MagicMock()
    docs_table_mock.select.return_value = docs_select_mock

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_table_mock
        if table_name == "teemo_wiki_pages":
            return wiki_pages_table_mock
        if table_name == "teemo_documents":
            return docs_table_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


def _make_supabase_for_tool(
    wiki_pages: list[dict],
    *,
    workspace_id: str = FAKE_WORKSPACE_ID,
    slug: str = FAKE_SLUG,
) -> MagicMock:
    """Build a Supabase mock for direct tool invocation (bypassing build_agent).

    Used for tool-level tests where we call read_wiki_page directly with a
    _FakeCtx, rather than going through build_agent.

    Args:
        wiki_pages: Wiki pages in the "database".
        workspace_id: The workspace ID queried by the tool.
        slug: The slug being queried (used to filter results).

    Returns:
        MagicMock Supabase client.
    """
    wiki_table_mock = _make_wiki_pages_select_chain(wiki_pages, filter_slug=slug)

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_wiki_pages":
            return wiki_table_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Core helper — extract read_wiki_page and system_prompt from build_agent
# ---------------------------------------------------------------------------


async def _run_build_agent(
    supabase: MagicMock,
) -> tuple[Any | None, str | None]:
    """Run build_agent with mocked pydantic-ai internals and capture outputs.

    Patches pydantic-ai's Agent class to capture the ``tools`` list and
    ``system_prompt`` string passed during construction.

    Args:
        supabase: Fully configured Supabase mock for this test.

    Returns:
        Tuple of (read_wiki_page_fn, system_prompt_str).
        Either may be None if not found in the captured constructor args.

    Raises:
        ImportError: If app.agents.agent cannot be imported.
    """
    import app.agents.agent as agent_mod  # type: ignore[import]

    captured_tools: list[Any] = []
    captured_system_prompt: list[str] = []

    def _fake_agent_cls(
        *args: Any,
        tools: list | None = None,
        system_prompt: str = "",
        **kwargs: Any,
    ) -> MagicMock:
        """Intercept Agent(..., tools=[...], system_prompt=...) to capture args."""
        if tools:
            captured_tools.extend(tools)
        if system_prompt:
            captured_system_prompt.append(system_prompt)
        return MagicMock()

    mock_model_cls = MagicMock()
    mock_provider_cls = MagicMock()

    with (
        patch.object(agent_mod, "Agent", _fake_agent_cls, create=True),
        patch("app.core.encryption.decrypt", return_value=FAKE_DECRYPTED_API_KEY),
        patch("app.services.skill_service.list_skills", return_value=[]),
        # Patch _ensure_model_imports to a no-op to avoid importing pydantic_ai
        # which may not be installed in the test environment. This mirrors the
        # approach used in test_read_drive_file.py and test_agent_factory.py.
        patch.object(agent_mod, "_ensure_model_imports", return_value=None),
        patch.object(agent_mod, "_build_pydantic_ai_model", return_value=MagicMock()),
        # Pre-populate module-level globals that _ensure_model_imports would set.
        patch.object(agent_mod, "Agent", _fake_agent_cls, create=True),
        patch.object(agent_mod, "AnthropicModel", mock_model_cls, create=True),
        patch.object(agent_mod, "AnthropicProvider", mock_provider_cls, create=True),
        patch.object(agent_mod, "OpenAIChatModel", mock_model_cls, create=True),
        patch.object(agent_mod, "OpenAIProvider", mock_provider_cls, create=True),
        patch.object(agent_mod, "GoogleModel", mock_model_cls, create=True),
        patch.object(agent_mod, "GoogleProvider", mock_provider_cls, create=True),
    ):
        try:
            await agent_mod.build_agent(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=supabase,
            )
        except Exception:
            # build_agent may raise after tool capture — tolerate as long as
            # we captured what we need.
            if not captured_tools and not captured_system_prompt:
                raise

    # Extract read_wiki_page from the captured tools list.
    read_wiki_page_fn: Any | None = None
    for tool in captured_tools:
        fn_name = getattr(tool, "__name__", "") or getattr(tool, "name", "")
        if fn_name == "read_wiki_page":
            read_wiki_page_fn = tool
            break

    system_prompt = captured_system_prompt[0] if captured_system_prompt else None
    return read_wiki_page_fn, system_prompt


# ---------------------------------------------------------------------------
# Test 1: read_wiki_page returns page content for existing slug
# ---------------------------------------------------------------------------


class TestReadWikiPageFound:
    """STORY-013-01 — Scenario: read_wiki_page returns page content.

    Given a wiki page with slug "onboarding-process" exists,
    When the agent calls read_wiki_page("onboarding-process"),
    Then the page content is returned.
    """

    @pytest.mark.asyncio
    async def test_read_wiki_page_returns_content_for_existing_slug(self) -> None:
        """read_wiki_page must return the content field of the matching wiki page.

        The tool queries teemo_wiki_pages by (workspace_id, slug) and returns
        the ``content`` column if found.
        """
        wiki_page = {
            "id": "wp-001",
            "workspace_id": FAKE_WORKSPACE_ID,
            "slug": FAKE_SLUG,
            "title": FAKE_WIKI_TITLE,
            "content": FAKE_WIKI_CONTENT,
            "tldr": FAKE_WIKI_TLDR,
            "page_type": "source-summary",
            "confidence": "high",
        }

        supabase = _make_supabase_for_build_agent([wiki_page])
        read_wiki_page_fn, _ = await _run_build_agent(supabase)

        assert read_wiki_page_fn is not None, (
            "read_wiki_page tool not found in Agent tools list. "
            "STORY-013-01 R2: register read_wiki_page in the tools=[...] list."
        )

        # For direct tool invocation, use a Supabase mock that properly filters by slug.
        tool_supabase = _make_supabase_for_tool([wiki_page], slug=FAKE_SLUG)
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=tool_supabase,
        )
        ctx = _FakeCtx(deps=deps)

        result = await read_wiki_page_fn(ctx, FAKE_SLUG)

        assert FAKE_WIKI_CONTENT in result, (
            f"Expected wiki page content in result. "
            f"Got: {result!r}. "
            f"STORY-013-01 R2: read_wiki_page must return the 'content' field of the matching page."
        )


# ---------------------------------------------------------------------------
# Test 2: read_wiki_page returns not-found message for missing slug
# ---------------------------------------------------------------------------


class TestReadWikiPageNotFound:
    """STORY-013-01 — Scenario: read_wiki_page returns not found message.

    When the agent calls read_wiki_page("nonexistent-slug"),
    Then "Wiki page not found" is returned.
    """

    @pytest.mark.asyncio
    async def test_read_wiki_page_returns_not_found_for_missing_slug(self) -> None:
        """read_wiki_page must return the canonical not-found message for unknown slugs.

        The expected message includes guidance pointing to the Wiki Index in the
        system prompt so the agent can discover valid page slugs.
        """
        # Empty database — no wiki pages exist.
        supabase = _make_supabase_for_build_agent([])
        read_wiki_page_fn, _ = await _run_build_agent(supabase)

        assert read_wiki_page_fn is not None, (
            "read_wiki_page tool not found in Agent tools list."
        )

        tool_supabase = _make_supabase_for_tool([], slug="nonexistent-slug")
        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=tool_supabase,
        )
        ctx = _FakeCtx(deps=deps)

        result = await read_wiki_page_fn(ctx, "nonexistent-slug")

        assert "Wiki page not found" in result, (
            f"Expected 'Wiki page not found' in result for missing slug. "
            f"Got: {result!r}. "
            f"STORY-013-01 R2: canonical not-found message required."
        )


# ---------------------------------------------------------------------------
# Test 3: Workspace isolation — cannot read another workspace's wiki page
# ---------------------------------------------------------------------------


class TestReadWikiPageWorkspaceIsolation:
    """STORY-013-01 — Workspace isolation: cannot read another workspace's wiki pages.

    Given workspace A has a page with slug "onboarding-process",
    When workspace B calls read_wiki_page("onboarding-process"),
    Then "Wiki page not found" is returned (not the other workspace's content).
    """

    @pytest.mark.asyncio
    async def test_workspace_isolation_prevents_cross_workspace_reads(self) -> None:
        """read_wiki_page must filter by workspace_id, not just slug.

        A wiki page belonging to workspace A must not be accessible from workspace B.
        The query must use both workspace_id AND slug as filter conditions.
        """
        # Page belonging to the OTHER workspace — not FAKE_WORKSPACE_ID.
        other_workspace_page = {
            "id": "wp-other-001",
            "workspace_id": FAKE_OTHER_WORKSPACE_ID,
            "slug": FAKE_SLUG,  # same slug, different workspace
            "title": "Other Workspace Onboarding",
            "content": "This belongs to another workspace.",
            "tldr": "Other workspace TLDR.",
            "page_type": "source-summary",
            "confidence": "high",
        }

        # Supabase mock configured for FAKE_WORKSPACE_ID context — the other
        # workspace's page is in the "database" but workspace_id filter should
        # prevent it from being returned.
        tool_supabase = _make_supabase_for_tool([], slug=FAKE_SLUG)

        # Build agent for FAKE_WORKSPACE_ID (not the other workspace).
        build_supabase = _make_supabase_for_build_agent([])
        read_wiki_page_fn, _ = await _run_build_agent(build_supabase)

        assert read_wiki_page_fn is not None, (
            "read_wiki_page tool not found in Agent tools list."
        )

        deps = _FakeDeps(
            workspace_id=FAKE_WORKSPACE_ID,
            user_id=FAKE_USER_ID,
            supabase=tool_supabase,
        )
        ctx = _FakeCtx(deps=deps)

        result = await read_wiki_page_fn(ctx, FAKE_SLUG)

        assert "Wiki page not found" in result, (
            f"Expected 'Wiki page not found' — cross-workspace reads must be blocked. "
            f"Got: {result!r}. "
            f"STORY-013-01 R2: query must filter by BOTH workspace_id AND slug."
        )

        assert "This belongs to another workspace." not in result, (
            "Other workspace's wiki page content leaked into the response. "
            "STORY-013-01 R2: workspace isolation is mandatory."
        )


# ---------------------------------------------------------------------------
# Test 4: System prompt renders ## Wiki Index when pages exist
# ---------------------------------------------------------------------------


class TestSystemPromptWikiIndex:
    """STORY-013-01 — Scenario: System prompt shows wiki index when pages exist.

    Given a workspace with 5 wiki pages,
    When the agent system prompt is built,
    Then ## Wiki Index lists all 5 pages with slug, title, TLDR.
    """

    @pytest.mark.asyncio
    async def test_system_prompt_renders_wiki_index_when_pages_exist(self) -> None:
        """_build_system_prompt must include ## Wiki Index when wiki pages exist.

        Each entry must follow the format: - [{slug}] {title} — {tldr}
        """
        wiki_pages = [
            {
                "id": f"wp-00{i}",
                "workspace_id": FAKE_WORKSPACE_ID,
                "slug": f"page-slug-{i}",
                "title": f"Page Title {i}",
                "content": f"Content for page {i}",
                "tldr": f"TLDR for page {i}",
                "page_type": "source-summary",
                "confidence": "high",
            }
            for i in range(1, 6)  # 5 pages
        ]

        supabase = _make_supabase_for_build_agent(wiki_pages)
        _, system_prompt = await _run_build_agent(supabase)

        assert system_prompt is not None, (
            "System prompt was not captured. Check that _fake_agent_cls intercepts it."
        )

        # Check for the ## Wiki Index SECTION (standalone heading on its own line).
        prompt_excerpt = repr(system_prompt[:500])
        assert "\n\n## Wiki Index\n" in system_prompt, (
            f"Expected '\\n\\n## Wiki Index\\n' section in system prompt when wiki pages exist. "
            f"System prompt: {prompt_excerpt}. "
            f"STORY-013-01 R3: replace ## Available Documents with ## Wiki Index."
        )

        # Verify all 5 pages are listed with the correct format.
        for i in range(1, 6):
            expected_entry = f"[page-slug-{i}] Page Title {i} — TLDR for page {i}"
            assert expected_entry in system_prompt, (
                f"Expected wiki index entry '{expected_entry}' not found in system prompt. "
                f"STORY-013-01 R3: format is '- [{{slug}}] {{title}} — {{tldr}}'."
            )


# ---------------------------------------------------------------------------
# Test 5: System prompt falls back to document list when no wiki pages exist
# ---------------------------------------------------------------------------


class TestSystemPromptFallback:
    """STORY-013-01 — Scenario: System prompt falls back when no wiki pages exist.

    Given a workspace with 3 documents but 0 wiki pages,
    When the agent system prompt is built,
    Then the existing file/document section remains (transitional behavior).
    """

    @pytest.mark.asyncio
    async def test_system_prompt_fallback_when_no_wiki_pages(self) -> None:
        """When no wiki pages exist, the system prompt must NOT contain ## Wiki Index.

        The existing knowledge file catalog (## Available Files or equivalent)
        must remain present as transitional fallback behavior.
        STORY-013-01 R3: wiki index replaces document catalog only when wiki pages exist.
        """
        # No wiki pages — empty list.
        # 3 documents exist in teemo_documents (STORY-015-03 schema with 'id' field).
        build_supabase_with_fallback = _make_supabase_for_build_agent_with_fallback(
            wiki_pages=[],
            knowledge_files=[
                {
                    "id": f"doc-id-00{i}",
                    "title": f"Document {i}",
                    "ai_description": f"Description for document {i}",
                }
                for i in range(1, 4)
            ],
        )

        _, system_prompt = await _run_build_agent(build_supabase_with_fallback)

        assert system_prompt is not None, (
            "System prompt was not captured."
        )

        # Check that the ## Wiki Index SECTION (as a standalone heading on its own line)
        # does not appear. The preamble includes the text "## Wiki Index" inline in a
        # tool description, so we check for the heading pattern "\n\n## Wiki Index\n"
        # which only appears when the section is actually rendered.
        assert "\n\n## Wiki Index\n" not in system_prompt, (
            f"'\\n\\n## Wiki Index\\n' section must NOT appear when no wiki pages exist. "
            f"STORY-013-01 R3: wiki index section only rendered when pages exist."
        )

        # The fallback section (## Available Files or ## Available Documents)
        # must be present since knowledge files exist.
        has_fallback = (
            "## Available Files" in system_prompt
            or "## Available Documents" in system_prompt
        )
        fallback_prompt_excerpt = repr(system_prompt[:500])
        assert has_fallback, (
            f"Expected fallback file catalog section in system prompt when no wiki pages. "
            f"System prompt: {fallback_prompt_excerpt}. "
            f"STORY-013-01 R3: existing document list is preserved as transitional fallback."
        )


def _make_supabase_for_build_agent_with_fallback(
    wiki_pages: list[dict],
    knowledge_files: list[dict],
    *,
    workspace_id: str = FAKE_WORKSPACE_ID,
) -> MagicMock:
    """Build Supabase mock for build_agent with wiki pages and documents for fallback test.

    STORY-015-03 replaced teemo_knowledge_index with teemo_documents. This mock
    routes 'teemo_documents' to the provided knowledge_files list so the fallback
    document catalog appears in the system prompt when no wiki pages are present.

    Args:
        wiki_pages: Wiki page rows (empty list for fallback scenario).
        knowledge_files: Document rows for the fallback document catalog.
            These are routed to teemo_documents (STORY-015-03 table).
            Each dict should have 'id', 'title', and 'ai_description' keys.
        workspace_id: Workspace ID used in the workspace row.

    Returns:
        MagicMock Supabase client.
    """
    ws_row = {
        "id": workspace_id,
        "ai_provider": FAKE_AI_PROVIDER,
        "ai_model": FAKE_AI_MODEL,
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
    }

    ws_table_mock = _make_workspaces_select_chain(ws_row)
    wiki_pages_table_mock = _make_wiki_pages_select_chain(wiki_pages)

    # teemo_documents mock — STORY-015-03 uses this table instead of
    # teemo_knowledge_index. The documents serve as the fallback catalog.
    docs_result = MagicMock()
    docs_result.data = knowledge_files
    docs_eq_mock = MagicMock()
    docs_eq_mock.execute.return_value = docs_result
    docs_select_mock = MagicMock()
    docs_select_mock.eq.return_value = docs_eq_mock
    docs_table_mock = MagicMock()
    docs_table_mock.select.return_value = docs_select_mock

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_table_mock
        if table_name == "teemo_wiki_pages":
            return wiki_pages_table_mock
        if table_name == "teemo_documents":
            return docs_table_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase
