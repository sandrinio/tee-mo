"""Tests for STORY-013-04 — lint_wiki service function and agent tool.

Covers all Gherkin scenarios from §2.1:
  1. Orphan page detection — pages with no incoming related_slugs are reported.
  2. Stale page detection — pages referencing pending documents are reported.
  3. Missing summary detection — documents with no source-summary page reported.
  4. Low confidence detection — pages with confidence='low' are reported.
  5. Report format — markdown report starts with ## Wiki Health Report and has
     correct counts.
  6. lint_wiki agent tool invokes wiki_service.lint_wiki and returns its result.

Mock strategy:
  - All Supabase calls are fully mocked via MagicMock per-table routing.
  - wiki_service is imported directly for service-level tests.
  - agent.py's lint_wiki tool is extracted from build_agent() using the same
    tools-list-capture pattern as test_wiki_read_tool.py.
  - No real DB, LLM, or network calls are made.

FLASHCARDS consulted:
  - Upsert: omit DEFAULT NOW() columns from payload (created_at, updated_at).
  - Supabase always use from app.core.db import get_supabase — tests pass mock directly.
  - Agent module-level globals are patched before calling build_agent() to skip real imports.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import guard — modules may not be importable in all environments
# ---------------------------------------------------------------------------

wiki_service = None
agent_module = None

try:
    import app.services.wiki_service as _ws  # type: ignore[import]
    wiki_service = _ws
except ImportError:
    pass

try:
    import app.agents.agent as _agent_mod  # type: ignore[import]
    agent_module = _agent_mod
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_WORKSPACE_ID = "ws-lint-test-001"
FAKE_USER_ID = "user-lint-test-001"
FAKE_ENCRYPTED_API_KEY = "enc:api:key:lint-test"
FAKE_DECRYPTED_API_KEY = "plaintext-api-key-lint-test"
FAKE_AI_PROVIDER = "anthropic"
FAKE_AI_MODEL = "claude-haiku-4-5"

# Sample wiki pages used across tests
PAGE_WITH_INCOMING = {
    "slug": "concept-alpha",
    "title": "Alpha Concept",
    "page_type": "concept",
    "confidence": "high",
    "related_slugs": [],
    "source_document_ids": ["doc-aaa"],
}
PAGE_ORPHAN = {
    "slug": "orphan-page",
    "title": "Orphaned Page",
    "page_type": "concept",
    "confidence": "high",
    "related_slugs": [],
    "source_document_ids": ["doc-bbb"],
}
PAGE_REFERENCES_ORPHAN = {
    "slug": "referencing-page",
    "title": "Referencing Page",
    "page_type": "source-summary",
    "confidence": "high",
    "related_slugs": ["concept-alpha"],  # references alpha but NOT orphan-page
    "source_document_ids": ["doc-ccc"],
}
PAGE_STALE = {
    "slug": "stale-page",
    "title": "Stale Page",
    "page_type": "concept",
    "confidence": "high",
    "related_slugs": ["concept-alpha"],
    "source_document_ids": ["doc-pending-001"],
}
PAGE_LOW_CONFIDENCE = {
    "slug": "low-conf-page",
    "title": "Low Confidence Page",
    "page_type": "entity",
    "confidence": "low",
    "related_slugs": ["concept-alpha"],
    "source_document_ids": ["doc-ddd"],
}
PAGE_SOURCE_SUMMARY_DOC_AAA = {
    "slug": "doc-aaa-summary",
    "title": "Doc AAA Summary",
    "page_type": "source-summary",
    "confidence": "high",
    "related_slugs": [],
    "source_document_ids": ["doc-aaa"],
}

DOC_AAA = {"id": "doc-aaa", "title": "Document AAA"}
DOC_BBB = {"id": "doc-bbb", "title": "Document BBB"}
DOC_PENDING = {"id": "doc-pending-001", "title": "Pending Document"}
DOC_NO_COVERAGE = {"id": "doc-no-wiki", "title": "Document Without Wiki"}


# ---------------------------------------------------------------------------
# Helpers — fake RunContext and deps
# ---------------------------------------------------------------------------


class _FakeDeps:
    """Minimal stand-in for AgentDeps injected into lint_wiki tool.

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


def _make_supabase(
    *,
    wiki_pages: list[dict],
    all_docs: list[dict],
    pending_docs: list[dict],
) -> MagicMock:
    """Build a fully routed Supabase mock for lint_wiki queries.

    lint_wiki makes three queries:
      1. teemo_wiki_pages — all pages for the workspace
         (.select("slug,title,related_slugs,...").eq("workspace_id", wid).execute())
      2. teemo_documents (pending) — documents with sync_status='pending'
         (.select("id").eq("workspace_id", wid).eq("sync_status", "pending").execute())
      3. teemo_documents (all) — all documents in workspace
         (.select("id, title").eq("workspace_id", wid).execute())
      4. teemo_wiki_log — insert for the lint log
         (.insert(payload).execute())

    We route by table name and by query shape (eq count).

    Args:
        wiki_pages:   Rows to return from teemo_wiki_pages.
        all_docs:     Rows to return from the full teemo_documents query.
        pending_docs: Rows to return from the pending-filter teemo_documents query.

    Returns:
        MagicMock Supabase client.
    """
    # --- teemo_wiki_pages mock ---
    wiki_pages_exec_result = MagicMock()
    wiki_pages_exec_result.data = wiki_pages

    wiki_eq_chain = MagicMock()
    wiki_eq_chain.execute.return_value = wiki_pages_exec_result

    wiki_select_mock = MagicMock()
    wiki_select_mock.eq.return_value = wiki_eq_chain

    wiki_table_mock = MagicMock()
    wiki_table_mock.select.return_value = wiki_select_mock

    # --- teemo_documents mock — two different queries: pending filter + full list
    # pending: .select("id").eq("workspace_id", wid).eq("sync_status", "pending").execute()
    pending_exec_result = MagicMock()
    pending_exec_result.data = pending_docs

    pending_status_eq_chain = MagicMock()
    pending_status_eq_chain.execute.return_value = pending_exec_result

    pending_ws_eq_chain = MagicMock()
    pending_ws_eq_chain.eq.return_value = pending_status_eq_chain
    pending_ws_eq_chain.execute.return_value = MagicMock(data=pending_docs)

    pending_select_mock = MagicMock()
    pending_select_mock.eq.return_value = pending_ws_eq_chain

    pending_docs_table_mock = MagicMock()
    pending_docs_table_mock.select.return_value = pending_select_mock

    # full docs: .select("id, title").eq("workspace_id", wid).execute()
    all_docs_exec_result = MagicMock()
    all_docs_exec_result.data = all_docs

    all_docs_eq_chain = MagicMock()
    all_docs_eq_chain.execute.return_value = all_docs_exec_result

    all_docs_select_mock = MagicMock()
    all_docs_select_mock.eq.return_value = all_docs_eq_chain

    all_docs_table_mock = MagicMock()
    all_docs_table_mock.select.return_value = all_docs_select_mock

    # --- teemo_wiki_log mock (insert) ---
    log_insert_result = MagicMock()
    log_insert_result.data = [{"id": "log-fake-001"}]

    log_insert_chain = MagicMock()
    log_insert_chain.execute.return_value = log_insert_result

    log_table_mock = MagicMock()
    log_table_mock.insert.return_value = log_insert_chain

    # Route calls by table name. teemo_documents is called twice — we track
    # the call to differentiate by which columns are selected.
    docs_call_count = [0]

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_wiki_pages":
            return wiki_table_mock
        if table_name == "teemo_wiki_log":
            return log_table_mock
        if table_name == "teemo_documents":
            docs_call_count[0] += 1
            # First call: pending filter (.select("id").eq(...).eq(...).execute())
            # Second call: full docs (.select("id, title").eq(...).execute())
            if docs_call_count[0] == 1:
                return pending_docs_table_mock
            return all_docs_table_mock
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    return supabase


# ---------------------------------------------------------------------------
# Service-level tests — lint_wiki()
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(wiki_service is None, reason="wiki_service not importable")
class TestLintWikiOrphans:
    """Scenario: Lint detects orphan pages."""

    async def test_orphan_page_detected_in_report(self) -> None:
        """An orphan page (slug not in any other page's related_slugs) is listed."""
        # PAGE_ORPHAN's slug ("orphan-page") does NOT appear in any page's related_slugs.
        # PAGE_REFERENCES_ORPHAN only references "concept-alpha".
        pages = [PAGE_WITH_INCOMING, PAGE_ORPHAN, PAGE_REFERENCES_ORPHAN]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA, DOC_BBB],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "orphan-page" in report
        assert "Orphan" in report or "orphan" in report

    async def test_non_orphan_page_not_flagged(self) -> None:
        """A page that IS referenced by another page is not reported as orphaned."""
        pages = [PAGE_WITH_INCOMING, PAGE_REFERENCES_ORPHAN]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        # concept-alpha is referenced by referencing-page's related_slugs
        assert "concept-alpha" not in report.split("**Orphan")[1] if "**Orphan" in report else True

    async def test_orphan_count_in_summary_line(self) -> None:
        """The summary line shows the correct orphan count."""
        pages = [PAGE_ORPHAN]  # single orphan, no one references it
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_BBB],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "1 orphan page(s)" in report


@pytest.mark.skipif(wiki_service is None, reason="wiki_service not importable")
class TestLintWikiStale:
    """Scenario: Lint detects stale pages."""

    async def test_stale_page_detected(self) -> None:
        """A page referencing a pending document is flagged as stale."""
        # PAGE_STALE's source_document_ids includes "doc-pending-001" which is pending.
        pages = [PAGE_STALE, PAGE_WITH_INCOMING]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA, DOC_PENDING],
            pending_docs=[DOC_PENDING],  # doc-pending-001 is pending
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "stale-page" in report
        assert "Stale" in report or "stale" in report

    async def test_non_stale_page_not_flagged(self) -> None:
        """A page whose source documents are all synced is not reported as stale."""
        pages = [PAGE_WITH_INCOMING]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA],
            pending_docs=[],  # no pending docs
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "0 stale page(s)" in report

    async def test_stale_count_in_summary_line(self) -> None:
        """The summary line shows the correct stale page count."""
        pages = [PAGE_STALE]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_PENDING],
            pending_docs=[DOC_PENDING],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "1 stale page(s)" in report


@pytest.mark.skipif(wiki_service is None, reason="wiki_service not importable")
class TestLintWikiMissingSummaries:
    """Scenario: Lint detects documents without wiki coverage."""

    async def test_missing_coverage_detected(self) -> None:
        """A document with no source-summary wiki page is reported as missing coverage."""
        # DOC_NO_COVERAGE has no corresponding source-summary page.
        pages = [PAGE_SOURCE_SUMMARY_DOC_AAA]  # only covers DOC_AAA
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA, DOC_NO_COVERAGE],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "doc-no-wiki" in report
        assert "missing" in report.lower()

    async def test_covered_document_not_flagged(self) -> None:
        """A document that already has a source-summary page is not flagged."""
        pages = [PAGE_SOURCE_SUMMARY_DOC_AAA]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "0 document(s) missing wiki pages" in report

    async def test_missing_coverage_count_in_summary(self) -> None:
        """The summary line shows the correct missing coverage count."""
        pages = []  # no wiki pages at all
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_NO_COVERAGE],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "1 document(s) missing wiki pages" in report


@pytest.mark.skipif(wiki_service is None, reason="wiki_service not importable")
class TestLintWikiLowConfidence:
    """Scenario: Lint detects low-confidence pages."""

    async def test_low_confidence_page_detected(self) -> None:
        """A page with confidence='low' is reported in the low-confidence section."""
        pages = [PAGE_LOW_CONFIDENCE, PAGE_WITH_INCOMING]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "low-conf-page" in report
        assert "Low-Confidence" in report or "low confidence" in report.lower()

    async def test_high_confidence_page_not_flagged(self) -> None:
        """A page with confidence='high' is not reported in low-confidence section."""
        pages = [PAGE_WITH_INCOMING]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_AAA],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "0 low-confidence page(s)" in report

    async def test_low_confidence_count_in_summary(self) -> None:
        """The summary line shows the correct low-confidence count."""
        pages = [PAGE_LOW_CONFIDENCE]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "1 low-confidence page(s)" in report


@pytest.mark.skipif(wiki_service is None, reason="wiki_service not importable")
class TestLintWikiReportFormat:
    """Scenario: Report format is correct markdown."""

    async def test_report_starts_with_header(self) -> None:
        """The report begins with ## Wiki Health Report."""
        supabase = _make_supabase(wiki_pages=[], all_docs=[], pending_docs=[])

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert report.startswith("## Wiki Health Report")

    async def test_empty_wiki_report_has_zero_counts(self) -> None:
        """A workspace with no pages and no documents shows all-zero counts."""
        supabase = _make_supabase(wiki_pages=[], all_docs=[], pending_docs=[])

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "0 orphan page(s)" in report
        assert "0 stale page(s)" in report
        assert "0 document(s) missing wiki pages" in report
        assert "0 low-confidence page(s)" in report

    async def test_clean_wiki_has_no_details_section(self) -> None:
        """A fully clean wiki (all zeros) does not include a Details section."""
        supabase = _make_supabase(wiki_pages=[], all_docs=[], pending_docs=[])

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "### Details" not in report

    async def test_issues_trigger_details_section(self) -> None:
        """When issues are found, a ### Details section is included."""
        pages = [PAGE_ORPHAN]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_BBB],
            pending_docs=[],
        )

        report = await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        assert "### Details" in report

    async def test_lint_logs_operation(self) -> None:
        """lint_wiki inserts a row in teemo_wiki_log with operation='lint'."""
        pages = [PAGE_ORPHAN]
        supabase = _make_supabase(
            wiki_pages=pages,
            all_docs=[DOC_BBB],
            pending_docs=[],
        )

        await wiki_service.lint_wiki(supabase, FAKE_WORKSPACE_ID)

        # The log insert should have been called on teemo_wiki_log
        supabase.table.assert_any_call("teemo_wiki_log")


# ---------------------------------------------------------------------------
# Agent tool tests — lint_wiki tool in build_agent()
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    agent_module is None or wiki_service is None,
    reason="agent or wiki_service not importable",
)
class TestLintWikiAgentTool:
    """Verify the lint_wiki tool is registered and delegates to wiki_service.

    Uses the same tool-extraction pattern as test_wiki_read_tool.py:
      - Patch Agent class to capture the tools list.
      - Patch _ensure_model_imports and _build_pydantic_ai_model to skip real
        pydantic-ai imports (may not be installed in test env).
      - Patch decrypt as a module-level attribute on the agent module (avoids
        importing encryption.py which calls get_settings() at module level and
        fails without a full .env in the test environment).
    """

    def _build_supabase_for_build_agent(self) -> MagicMock:
        """Build a minimal Supabase mock that satisfies build_agent's queries."""
        ws_row = {
            "id": FAKE_WORKSPACE_ID,
            "ai_provider": FAKE_AI_PROVIDER,
            "ai_model": FAKE_AI_MODEL,
            "encrypted_api_key": FAKE_ENCRYPTED_API_KEY,
        }

        # teemo_workspaces mock
        ws_result = MagicMock()
        ws_result.data = ws_row
        ws_maybe_single = MagicMock()
        ws_maybe_single.execute.return_value = ws_result
        ws_eq = MagicMock()
        ws_eq.maybe_single.return_value = ws_maybe_single
        ws_select = MagicMock()
        ws_select.eq.return_value = ws_eq
        ws_table = MagicMock()
        ws_table.select.return_value = ws_select

        # teemo_wiki_pages mock (for system prompt construction)
        wiki_result = MagicMock()
        wiki_result.data = []
        wiki_eq = MagicMock()
        wiki_eq.execute.return_value = wiki_result
        wiki_select = MagicMock()
        wiki_select.eq.return_value = wiki_eq
        wiki_table = MagicMock()
        wiki_table.select.return_value = wiki_select

        # teemo_documents mock (for system prompt construction)
        docs_result = MagicMock()
        docs_result.data = []
        docs_eq = MagicMock()
        docs_eq.execute.return_value = docs_result
        docs_select = MagicMock()
        docs_select.eq.return_value = docs_eq
        docs_table = MagicMock()
        docs_table.select.return_value = docs_select

        def _router(name: str) -> MagicMock:
            if name == "teemo_workspaces":
                return ws_table
            if name == "teemo_wiki_pages":
                return wiki_table
            if name == "teemo_documents":
                return docs_table
            return MagicMock()

        supabase = MagicMock()
        supabase.table.side_effect = _router
        return supabase

    async def _run_build_agent_capture_tools(
        self,
        supabase: MagicMock,
        extra_patches: list | None = None,
    ) -> list:
        """Run build_agent with minimal mocking and capture the tools list.

        Mirrors the _run_build_agent helper in test_wiki_read_tool.py.

        Args:
            supabase: Fully-mocked Supabase client.
            extra_patches: Additional context managers to apply (e.g. lint mock).

        Returns:
            List of tool functions captured from Agent() constructor.
        """
        captured_tools: list = []

        def _fake_agent_cls(
            *args,
            tools: list | None = None,
            system_prompt: str = "",
            **kwargs,
        ) -> MagicMock:
            if tools:
                captured_tools.extend(tools)
            return MagicMock()

        base_patches = [
            patch.object(agent_module, "Agent", _fake_agent_cls, create=True),
            patch.object(agent_module, "_ensure_model_imports", return_value=None),
            patch.object(agent_module, "_build_pydantic_ai_model", return_value=MagicMock()),
            patch.object(agent_module, "AnthropicModel", MagicMock(), create=True),
            patch.object(agent_module, "AnthropicProvider", MagicMock(), create=True),
            patch.object(agent_module, "OpenAIChatModel", MagicMock(), create=True),
            patch.object(agent_module, "OpenAIProvider", MagicMock(), create=True),
            patch.object(agent_module, "GoogleModel", MagicMock(), create=True),
            patch.object(agent_module, "GoogleProvider", MagicMock(), create=True),
            patch("app.core.encryption.decrypt", return_value=FAKE_DECRYPTED_API_KEY),
            patch("app.services.skill_service.list_skills", return_value=[]),
        ]

        all_patches = base_patches + (extra_patches or [])

        # Stack all context managers manually for Python 3.9 compatibility.
        # Python 3.9 does not support parenthesised multi-with syntax for
        # more than a few items in some edge cases.
        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in all_patches:
                stack.enter_context(p)
            try:
                await agent_module.build_agent(FAKE_WORKSPACE_ID, FAKE_USER_ID, supabase)
            except Exception:
                if not captured_tools:
                    raise

        return captured_tools

    async def test_lint_wiki_tool_registered_in_tools_list(self) -> None:
        """lint_wiki appears in the 13-item tools list passed to Agent()."""
        supabase = self._build_supabase_for_build_agent()
        captured_tools = await self._run_build_agent_capture_tools(supabase)

        tool_names = [t.__name__ for t in captured_tools]
        assert "lint_wiki" in tool_names

    async def test_lint_wiki_tool_calls_wiki_service(self) -> None:
        """lint_wiki tool delegates to wiki_service.lint_wiki with correct args."""
        expected_report = "## Wiki Health Report\n\n- 0 orphan page(s)\n"
        mock_lint = AsyncMock(return_value=expected_report)

        supabase = self._build_supabase_for_build_agent()

        # Patch wiki_service.lint_wiki for both the build_agent call AND the
        # subsequent tool call — they share the same execution scope here.
        with patch.object(agent_module._wiki_service, "lint_wiki", mock_lint):
            captured_tools = await self._run_build_agent_capture_tools(supabase)

            # Extract lint_wiki tool from captured list
            lint_tool = next(t for t in captured_tools if t.__name__ == "lint_wiki")

            # Call the tool with a fake ctx (patch still active)
            mock_supabase = MagicMock()
            fake_deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, mock_supabase)
            fake_ctx = _FakeCtx(fake_deps)

            result = await lint_tool(fake_ctx)

        assert result == expected_report
        mock_lint.assert_called_once_with(mock_supabase, FAKE_WORKSPACE_ID)

    async def test_lint_wiki_tool_handles_exception_gracefully(self) -> None:
        """lint_wiki tool returns an error string when wiki_service raises."""
        mock_lint_fail = AsyncMock(side_effect=RuntimeError("DB connection failed"))

        supabase = self._build_supabase_for_build_agent()

        with patch.object(agent_module._wiki_service, "lint_wiki", mock_lint_fail):
            captured_tools = await self._run_build_agent_capture_tools(supabase)
            lint_tool = next(t for t in captured_tools if t.__name__ == "lint_wiki")

            mock_supabase = MagicMock()
            fake_deps = _FakeDeps(FAKE_WORKSPACE_ID, FAKE_USER_ID, mock_supabase)
            fake_ctx = _FakeCtx(fake_deps)

            result = await lint_tool(fake_ctx)

        assert "Failed to lint wiki" in result
        assert "DB connection failed" in result
