"""Tests for STORY-015-03 — document CRUD tools in app/agents/agent.py.

Covers all Gherkin scenarios from STORY-015-03 §2:

  Scenario: read_drive_file tool removed, read_document exists
    - Tool list includes read_document, create_document, update_document, delete_document
    - Tool list does NOT include read_drive_file

  Scenario: read_document returns content by UUID
    - Given a workspace document, calling read_document with its UUID returns content.

  Scenario: read_document works for agent-created docs
    - Same as above (document_service.read_document_content is source-agnostic).

  Scenario: System prompt lists documents from teemo_documents (in test_agent_factory.py)

  Scenario: Agent creates a document
    - create_document calls document_service.create_document with source='agent'.
    - Returns confirmation message with ID.

  Scenario: Agent creates document — cap reached
    - When the DB trigger raises a cap exception, create_document returns friendly message.

  Scenario: Agent updates its own document
    - update_document passes source guard when source='agent'.
    - Calls document_service.update_document.

  Scenario: Agent cannot update Drive document
    - update_document returns "Only agent-created documents can be updated." when source!='agent'.

  Scenario: Agent deletes its own document
    - delete_document passes source guard when source='agent'.
    - Calls document_service.delete_document.

  Scenario: Agent cannot delete uploaded document
    - delete_document returns "Only agent-created documents can be deleted via this tool."
      when source!='upload'.

Extraction strategy:
  Tools are nested closures inside build_agent(). We extract them by:
    1. Calling build_agent() with fully mocked pydantic-ai internals.
    2. Intercepting the ``tools=[...]`` list passed to Agent().
    3. Locating the target function by __name__.
    4. Calling the extracted coroutine with a synthetic ctx (fake RunContext).

FLASHCARDS.md consulted:
  - Supabase client: use get_supabase() pattern — but this module is isolated (no FastAPI).
  - Omit DEFAULT NOW() columns from insert/update payloads.
  - SHA-256 for content hashing (not directly tested here — delegated to document_service).
  - Worktree-relative paths only in Edit/Write calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_WORKSPACE_ID = "ws-rdt-test-001"
FAKE_USER_ID = "user-rdt-test-001"
FAKE_DOC_ID = "uuid-doc-test-aabbcc"
FAKE_CONTENT = "# Test Document\n\nThis is some test content."
FAKE_TITLE = "Test Document"
FAKE_AI_PROVIDER = "anthropic"
FAKE_AI_MODEL = "claude-3-5-sonnet-20241022"
FAKE_ENCRYPTED_API_KEY = "enc:api:key:test"
FAKE_DECRYPTED_API_KEY = "plaintext-api-key-test"


# ---------------------------------------------------------------------------
# Helpers — fake RunContext and deps
# ---------------------------------------------------------------------------


class _FakeDeps:
    """Minimal stand-in for AgentDeps passed into tools via ctx.deps.

    Args:
        workspace_id: Workspace UUID string.
        user_id:      User UUID string.
        supabase:     MagicMock Supabase client.
    """

    def __init__(self, workspace_id: str, user_id: str, supabase: Any) -> None:
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


def _make_build_agent_supabase(workspace_row: dict, docs_for_prompt: list[dict]) -> MagicMock:
    """Build a Supabase mock for build_agent's workspace + document catalog queries.

    build_agent queries:
      1. teemo_workspaces (maybe_single) → workspace_row
      2. teemo_documents (execute) → docs_for_prompt

    Args:
        workspace_row:    Full workspace dict.
        docs_for_prompt:  Documents for system prompt catalog.

    Returns:
        MagicMock Supabase client.
    """
    ws_result = MagicMock()
    ws_result.data = workspace_row

    ws_chain = MagicMock()
    ws_chain.maybe_single.return_value = ws_chain
    ws_chain.execute.return_value = ws_result
    ws_chain.eq.return_value = ws_chain
    ws_chain.select.return_value = ws_chain

    docs_result = MagicMock()
    docs_result.data = docs_for_prompt

    docs_chain = MagicMock()
    docs_chain.execute.return_value = docs_result
    docs_chain.eq.return_value = docs_chain
    docs_chain.select.return_value = docs_chain

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_documents":
            return docs_chain
        return ws_chain  # teemo_workspaces

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Core helper — extract a named tool from build_agent's tools list
# ---------------------------------------------------------------------------


async def _extract_tool(tool_name: str) -> Any:
    """Extract a named async tool coroutine from build_agent() by intercepting Agent().

    Calls build_agent() with fully mocked pydantic-ai internals, captures the
    ``tools=`` list passed to Agent(), and returns the function whose __name__
    matches tool_name.

    Args:
        tool_name: The __name__ of the tool to extract (e.g. "read_document").

    Returns:
        Async callable — the tool function defined inside agent.py.

    Raises:
        AttributeError: If the tool is not found in the captured tools list.
    """
    import app.agents.agent as agent_mod  # type: ignore[import]

    captured_tools: list[Any] = []

    def _fake_agent_cls(*args: Any, tools: list | None = None, **kwargs: Any) -> MagicMock:
        if tools:
            captured_tools.extend(tools)
        return MagicMock()

    workspace_row = {
        "ai_provider": FAKE_AI_PROVIDER,
        "ai_model": FAKE_AI_MODEL,
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
    }
    build_supabase = _make_build_agent_supabase(workspace_row, docs_for_prompt=[])

    mock_model_cls = MagicMock()
    mock_provider_cls = MagicMock()

    with (
        patch.object(agent_mod, "Agent", _fake_agent_cls, create=True),
        patch("app.core.encryption.decrypt", return_value=FAKE_DECRYPTED_API_KEY),
        patch("app.services.skill_service.list_skills", return_value=[]),
        patch.object(agent_mod, "_build_pydantic_ai_model", return_value=MagicMock()),
        patch.object(agent_mod, "AnthropicModel", mock_model_cls, create=True),
        patch.object(agent_mod, "AnthropicProvider", mock_provider_cls, create=True),
    ):
        try:
            await agent_mod.build_agent(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=build_supabase,
            )
        except Exception:
            if not captured_tools:
                raise

    fn: Any = None
    for tool in captured_tools:
        fn_name = getattr(tool, "__name__", "") or getattr(tool, "name", "")
        if fn_name == tool_name:
            fn = tool
            break

    if fn is None:
        available = [getattr(t, "__name__", repr(t)) for t in captured_tools]
        raise AttributeError(
            f"Tool '{tool_name}' not found in Agent tools. "
            f"Available: {available}"
        )

    return fn


# ---------------------------------------------------------------------------
# Scenario: Tool list correctness
# ---------------------------------------------------------------------------


class TestToolListAfterRefactor:
    """STORY-015-03: Tool list must include new doc tools and exclude read_drive_file."""

    @pytest.mark.asyncio
    async def test_tool_list_includes_document_tools(self) -> None:
        """build_agent tools list must include all 4 document tools.

        Expected: read_document, create_document, update_document, delete_document.
        """
        import app.agents.agent as agent_mod  # type: ignore[import]

        captured_tools: list[Any] = []

        def _fake_agent_cls(*args: Any, tools: list | None = None, **kwargs: Any) -> MagicMock:
            if tools:
                captured_tools.extend(tools)
            return MagicMock()

        workspace_row = {
            "ai_provider": FAKE_AI_PROVIDER,
            "ai_model": FAKE_AI_MODEL,
            "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
        }
        build_supabase = _make_build_agent_supabase(workspace_row, [])

        with (
            patch.object(agent_mod, "Agent", _fake_agent_cls, create=True),
            patch("app.core.encryption.decrypt", return_value=FAKE_DECRYPTED_API_KEY),
            patch("app.services.skill_service.list_skills", return_value=[]),
            patch.object(agent_mod, "_build_pydantic_ai_model", return_value=MagicMock()),
            patch.object(agent_mod, "AnthropicModel", MagicMock(), create=True),
            patch.object(agent_mod, "AnthropicProvider", MagicMock(), create=True),
        ):
            await agent_mod.build_agent(
                workspace_id=FAKE_WORKSPACE_ID,
                user_id=FAKE_USER_ID,
                supabase=build_supabase,
            )

        tool_names = {getattr(t, "__name__", "") for t in captured_tools}

        for expected in ("read_document", "create_document", "update_document", "delete_document"):
            assert expected in tool_names, (
                f"Tool '{expected}' must be in the tools list. Found: {tool_names}"
            )

        assert "read_drive_file" not in tool_names, (
            f"Tool 'read_drive_file' must NOT be in the tools list after STORY-015-03 refactor. "
            f"Found: {tool_names}"
        )


# ---------------------------------------------------------------------------
# Scenario: read_document returns content
# ---------------------------------------------------------------------------


class TestReadDocument:
    """STORY-015-03 R1: read_document reads from teemo_documents by UUID."""

    @pytest.mark.asyncio
    async def test_read_document_returns_content(self) -> None:
        """read_document returns content when document exists in this workspace.

        Patches document_service.read_document_content to return canned content.
        """
        import app.agents.agent as agent_mod  # type: ignore[import]

        read_document = await _extract_tool("read_document")

        mock_read = AsyncMock(return_value=FAKE_CONTENT)
        supabase = MagicMock()
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "read_document_content", mock_read):
            result = await read_document(ctx, FAKE_DOC_ID)

        assert result == FAKE_CONTENT, (
            f"read_document must return document content. Got: {result!r}"
        )
        mock_read.assert_called_once_with(supabase, FAKE_WORKSPACE_ID, FAKE_DOC_ID)

    @pytest.mark.asyncio
    async def test_read_document_returns_not_found_for_missing_doc(self) -> None:
        """read_document returns 'Document not found.' when document does not exist."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        read_document = await _extract_tool("read_document")

        mock_read = AsyncMock(return_value=None)
        supabase = MagicMock()
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "read_document_content", mock_read):
            result = await read_document(ctx, "uuid-does-not-exist")

        assert result == "Document not found.", (
            f"read_document must return 'Document not found.' for missing doc. Got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Scenario: create_document
# ---------------------------------------------------------------------------


class TestCreateDocument:
    """STORY-015-03 R4: create_document tool calls document_service.create_document."""

    @pytest.mark.asyncio
    async def test_create_document_returns_confirmation(self) -> None:
        """create_document returns confirmation with ID on success."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        create_document = await _extract_tool("create_document")

        created_row = {"id": FAKE_DOC_ID, "title": FAKE_TITLE, "source": "agent"}
        mock_create = AsyncMock(return_value=created_row)
        supabase = MagicMock()
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "create_document", mock_create):
            result = await create_document(ctx, FAKE_TITLE, FAKE_CONTENT)

        assert FAKE_TITLE in result, (
            f"Confirmation must contain the document title. Got: {result!r}"
        )
        assert FAKE_DOC_ID in result, (
            f"Confirmation must contain the document ID. Got: {result!r}"
        )

        # Verify create_document was called with correct args
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs.get("source") == "agent", (
            "create_document must be called with source='agent'"
        )
        assert call_kwargs.get("doc_type") == "markdown", (
            "create_document must be called with doc_type='markdown'"
        )

    @pytest.mark.asyncio
    async def test_create_document_handles_cap_reached(self) -> None:
        """create_document returns friendly message when 100-doc cap is reached."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        create_document = await _extract_tool("create_document")

        def _raise_cap(*args: Any, **kwargs: Any):
            raise Exception("Maximum 100 documents per workspace (doc_cap)")

        mock_create = AsyncMock(side_effect=_raise_cap)
        supabase = MagicMock()
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "create_document", mock_create):
            result = await create_document(ctx, FAKE_TITLE, FAKE_CONTENT)

        assert "Maximum 100 documents" in result, (
            f"Must return cap-reached message when DB raises exception. Got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Scenario: update_document source guard
# ---------------------------------------------------------------------------


class TestUpdateDocument:
    """STORY-015-03 R5: update_document only allows source='agent' documents."""

    def _make_source_check_supabase(self, source: str | None) -> MagicMock:
        """Build a Supabase mock that returns a document row with the given source.

        The mock handles: .table("teemo_documents").select("source").eq(...).eq(...).maybe_single().execute()

        Args:
            source: Source value to return in the document row, or None for not found.
        """
        result = MagicMock()
        result.data = {"source": source} if source is not None else None

        chain = MagicMock()
        chain.maybe_single.return_value = chain
        chain.execute.return_value = result
        chain.eq.return_value = chain
        chain.select.return_value = chain

        supabase = MagicMock()
        supabase.table.return_value = chain
        return supabase

    @pytest.mark.asyncio
    async def test_update_document_succeeds_for_agent_source(self) -> None:
        """update_document calls document_service.update_document for agent docs."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        update_document = await _extract_tool("update_document")

        supabase = self._make_source_check_supabase("agent")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        mock_update = AsyncMock(return_value={"id": FAKE_DOC_ID})

        with patch.object(agent_mod._doc_service, "update_document", mock_update):
            result = await update_document(ctx, FAKE_DOC_ID, "new content")

        assert "updated successfully" in result, (
            f"Must return success message for agent-sourced doc. Got: {result!r}"
        )
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_document_rejects_drive_source(self) -> None:
        """update_document returns error message for Google Drive documents."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        update_document = await _extract_tool("update_document")

        supabase = self._make_source_check_supabase("google_drive")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "update_document", AsyncMock()) as mock_update:
            result = await update_document(ctx, FAKE_DOC_ID, "new content")

        assert "Only agent-created documents can be updated" in result, (
            f"Must refuse to update Drive docs. Got: {result!r}"
        )
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_document_rejects_upload_source(self) -> None:
        """update_document returns error message for uploaded documents."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        update_document = await _extract_tool("update_document")

        supabase = self._make_source_check_supabase("upload")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "update_document", AsyncMock()) as mock_update:
            result = await update_document(ctx, FAKE_DOC_ID, "new content")

        assert "Only agent-created documents can be updated" in result, (
            f"Must refuse to update uploaded docs. Got: {result!r}"
        )
        mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_document_returns_not_found(self) -> None:
        """update_document returns 'Document not found.' when the doc does not exist."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        update_document = await _extract_tool("update_document")

        supabase = self._make_source_check_supabase(None)  # not found
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        result = await update_document(ctx, "uuid-does-not-exist", "new content")

        assert "not found" in result.lower(), (
            f"Must return not-found message when document missing. Got: {result!r}"
        )


# ---------------------------------------------------------------------------
# Scenario: delete_document source guard
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    """STORY-015-03 R6: delete_document only allows source='agent' documents."""

    def _make_source_check_supabase(self, source: str | None) -> MagicMock:
        """Build a Supabase mock that returns a document row with the given source.

        Args:
            source: Source value to return, or None for not found.
        """
        result = MagicMock()
        result.data = {"source": source} if source is not None else None

        chain = MagicMock()
        chain.maybe_single.return_value = chain
        chain.execute.return_value = result
        chain.eq.return_value = chain
        chain.select.return_value = chain

        supabase = MagicMock()
        supabase.table.return_value = chain
        return supabase

    @pytest.mark.asyncio
    async def test_delete_document_succeeds_for_agent_source(self) -> None:
        """delete_document calls document_service.delete_document for agent docs."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        delete_document = await _extract_tool("delete_document")

        supabase = self._make_source_check_supabase("agent")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        mock_delete = AsyncMock(return_value=True)

        with patch.object(agent_mod._doc_service, "delete_document", mock_delete):
            result = await delete_document(ctx, FAKE_DOC_ID)

        assert "deleted successfully" in result, (
            f"Must return success message for agent-sourced doc. Got: {result!r}"
        )
        mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document_rejects_drive_source(self) -> None:
        """delete_document returns error message for Google Drive documents."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        delete_document = await _extract_tool("delete_document")

        supabase = self._make_source_check_supabase("google_drive")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "delete_document", AsyncMock()) as mock_delete:
            result = await delete_document(ctx, FAKE_DOC_ID)

        assert "Only agent-created documents can be deleted via this tool" in result, (
            f"Must refuse to delete Drive docs. Got: {result!r}"
        )
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_document_rejects_upload_source(self) -> None:
        """delete_document returns error message for uploaded documents."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        delete_document = await _extract_tool("delete_document")

        supabase = self._make_source_check_supabase("upload")
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        with patch.object(agent_mod._doc_service, "delete_document", AsyncMock()) as mock_delete:
            result = await delete_document(ctx, FAKE_DOC_ID)

        assert "Only agent-created documents can be deleted via this tool" in result, (
            f"Must refuse to delete uploaded docs. Got: {result!r}"
        )
        mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_document_returns_not_found(self) -> None:
        """delete_document returns 'Document not found.' when the doc does not exist."""
        import app.agents.agent as agent_mod  # type: ignore[import]

        delete_document = await _extract_tool("delete_document")

        supabase = self._make_source_check_supabase(None)  # not found
        deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
        ctx = _FakeCtx(deps)

        result = await delete_document(ctx, "uuid-does-not-exist")

        assert "not found" in result.lower(), (
            f"Must return not-found message when document missing. Got: {result!r}"
        )
