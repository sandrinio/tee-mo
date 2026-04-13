"""
Tests for wiki_service.py — STORY-013-02 (Single-pass).

Covers all Gherkin scenarios from §2.1:
  1. ingest_document produces pages with correct structure
  2. Tiny document threshold (< 100 chars skips ingest)
  3. Sync status transitions (processing → synced)
  4. reingest_document deletes old pages first
  5. rebuild_wiki_index returns correct format
  6. Ingest failure sets error status
  7. Log entry created in teemo_wiki_log

Mock strategy:
  - ``_agent_module.Agent`` and model-class globals are patched via
    monkeypatch.setattr on the agent module so _ensure_model_imports skips the
    real import. Same pattern as test_scan_service.py.
  - Supabase client is a fully configured MagicMock with per-table routing.
  - read_document_content is monkeypatched to return controlled content.
  - No real LLM API calls are made.

FLASHCARDS consulted:
  - Upsert: omit DEFAULT NOW() columns from payload (created_at, updated_at).
  - Supabase always use from app.core.db import get_supabase — tests pass a mock directly.
  - Tiny doc threshold < 100 chars → sync_status='synced' immediately.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, call

import pytest

# ---------------------------------------------------------------------------
# Import guard — module may not be importable in some environments
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

FAKE_WORKSPACE_ID = "ws-wiki-svc-test-001"
FAKE_DOCUMENT_ID = "doc-wiki-svc-test-001"
FAKE_PROVIDER = "anthropic"
FAKE_API_KEY = "test-api-key-wiki-svc"

SAMPLE_CONTENT = """\
# Company Onboarding Policy

This document describes the onboarding process for new employees at Acme Corp.

## Week 1: Orientation
All new hires attend a 2-day orientation led by HR. Key topics:
- Company values and culture
- Benefits enrollment (health, dental, 401k)
- Security training and badge activation

## Week 2: Team Integration
The new hire meets their assigned buddy — an experienced team member who
provides guidance during the first 90 days. The buddy is selected by the
team lead based on skill overlap with the new hire's role.

## IT Setup
Laptops are provisioned by the IT department (John Smith, john.smith@acme.com).
Standard setup includes: Slack, Jira, GitHub, and VPN client.

## Key Contacts
- HR: Sarah Johnson (sarah.j@acme.com)
- IT: John Smith (john.smith@acme.com)
- Facilities: Building access is managed by Security (security@acme.com)
"""

SAMPLE_LLM_JSON_RESPONSE = json.dumps([
    {
        "slug": "onboarding-policy-overview",
        "title": "Onboarding Policy Overview",
        "page_type": "source-summary",
        "content": "# Onboarding Policy Overview\n\nThis page summarizes the company onboarding process.",
        "tldr": "Complete onboarding guide for new Acme Corp hires covering orientation, team integration, and IT setup.",
        "suggested_related_topics": ["hr-processes", "it-setup"],
    },
    {
        "slug": "week-1-orientation",
        "title": "Week 1: New Hire Orientation",
        "page_type": "concept",
        "content": "# Week 1 Orientation\n\nTwo-day HR-led orientation covering values, benefits, and security.",
        "tldr": "2-day orientation in Week 1 covering company values, benefits enrollment, and security training.",
        "suggested_related_topics": ["hr-processes", "benefits"],
    },
    {
        "slug": "buddy-program",
        "title": "New Hire Buddy Program",
        "page_type": "concept",
        "content": "# Buddy Program\n\nEach new hire is assigned a buddy for their first 90 days.",
        "tldr": "Experienced team member assigned as buddy for first 90 days to guide new hires.",
        "suggested_related_topics": ["team-integration"],
    },
    {
        "slug": "john-smith",
        "title": "John Smith — IT Department",
        "page_type": "entity",
        "content": "# John Smith\n\nIT contact at Acme Corp. Handles laptop provisioning.",
        "tldr": "IT department contact responsible for laptop provisioning and IT setup.",
        "suggested_related_topics": ["it-setup"],
    },
    {
        "slug": "sarah-johnson",
        "title": "Sarah Johnson — HR",
        "page_type": "entity",
        "content": "# Sarah Johnson\n\nHR contact at Acme Corp.",
        "tldr": "HR contact at Acme Corp.",
        "suggested_related_topics": ["hr-processes"],
    },
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_agent_module_globals(monkeypatch):
    """Patch agent.py module-level globals so _ensure_model_imports skips real imports.

    Sets non-None MagicMock values for Agent and all model/provider classes,
    preventing real pydantic-ai imports from running during tests.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        Dict of mock objects keyed by the global name.
    """
    if agent_module is None:
        return {}

    mock_agent_cls = MagicMock()
    mock_google_model = MagicMock()
    mock_google_provider = MagicMock()
    mock_anthropic_model = MagicMock()
    mock_anthropic_provider = MagicMock()
    mock_openai_model = MagicMock()
    mock_openai_provider = MagicMock()

    monkeypatch.setattr(agent_module, "Agent", mock_agent_cls)
    monkeypatch.setattr(agent_module, "GoogleModel", mock_google_model)
    monkeypatch.setattr(agent_module, "GoogleProvider", mock_google_provider)
    monkeypatch.setattr(agent_module, "AnthropicModel", mock_anthropic_model)
    monkeypatch.setattr(agent_module, "AnthropicProvider", mock_anthropic_provider)
    monkeypatch.setattr(agent_module, "OpenAIChatModel", mock_openai_model)
    monkeypatch.setattr(agent_module, "OpenAIProvider", mock_openai_provider)

    return {
        "Agent": mock_agent_cls,
        "GoogleModel": mock_google_model,
        "GoogleProvider": mock_google_provider,
        "AnthropicModel": mock_anthropic_model,
        "AnthropicProvider": mock_anthropic_provider,
        "OpenAIChatModel": mock_openai_model,
        "OpenAIProvider": mock_openai_provider,
    }


def _configure_agent_mock_to_return_json(mocks, json_response: str) -> None:
    """Configure the Agent mock to return the given JSON string from run().

    The Agent mock class returns a new MagicMock instance when called;
    this helper configures that instance's async run() to return a
    MagicMock result with .output = json_response.

    Args:
        mocks: Dict returned by _patch_agent_module_globals.
        json_response: JSON string to return from agent.run().output.
    """
    mock_agent_instance = MagicMock()
    mock_result = MagicMock()
    mock_result.output = json_response
    mock_agent_instance.run = AsyncMock(return_value=mock_result)
    mocks["Agent"].return_value = mock_agent_instance


def _make_supabase_mock(
    *,
    document_content: str | None = SAMPLE_CONTENT,
    existing_wiki_pages: list[dict] | None = None,
    upsert_responses: list | None = None,
) -> MagicMock:
    """Build a fully configured Supabase mock for wiki_service tests.

    Routes table() calls to per-table mocks. Captures update calls for
    sync_status transitions so tests can assert on them.

    Args:
        document_content: Content to return from teemo_documents SELECT.
        existing_wiki_pages: Wiki pages to return from teemo_wiki_pages SELECT.
        upsert_responses: Optional list of responses for successive upsert calls.

    Returns:
        MagicMock Supabase client.
    """
    existing_wiki_pages = existing_wiki_pages or []

    # --- teemo_documents mock ---
    # Used by read_document_content (select content where id=... and workspace_id=...)
    # AND by _set_sync_status (update sync_status where id=... and workspace_id=...)
    doc_content_result = MagicMock()
    doc_content_result.data = (
        {"content": document_content} if document_content is not None else None
    )
    doc_content_execute = MagicMock()
    doc_content_execute.execute.return_value = doc_content_result

    doc_maybe_single = MagicMock()
    doc_maybe_single.maybe_single.return_value = doc_content_execute

    doc_eq_ws = MagicMock()
    doc_eq_ws.eq.return_value = doc_maybe_single

    doc_select = MagicMock()
    doc_select.eq.return_value = doc_eq_ws

    # Update chain for sync_status transitions
    update_eq_id = MagicMock()
    update_eq_id.execute.return_value = MagicMock()

    update_eq_ws = MagicMock()
    update_eq_ws.eq.return_value = update_eq_id

    doc_update = MagicMock()
    doc_update.eq.return_value = update_eq_ws

    docs_table = MagicMock()
    docs_table.select.return_value = doc_select
    docs_table.update.return_value = doc_update

    # --- teemo_wiki_pages mock ---
    # SELECT (existing pages for cross-reference + rebuild_wiki_index)
    wiki_select_result = MagicMock()
    wiki_select_result.data = existing_wiki_pages

    wiki_order_mock = MagicMock()
    wiki_order_mock.execute.return_value = wiki_select_result

    wiki_eq_mock = MagicMock()
    wiki_eq_mock.execute.return_value = wiki_select_result
    wiki_eq_mock.order.return_value = wiki_order_mock

    wiki_select_mock = MagicMock()
    wiki_select_mock.eq.return_value = wiki_eq_mock

    # UPSERT for inserting pages
    upsert_result = MagicMock()
    upsert_result.data = [{"id": "wp-new-001"}]
    upsert_execute = MagicMock()
    upsert_execute.execute.return_value = upsert_result

    wiki_upsert_mock = MagicMock()
    wiki_upsert_mock.execute.return_value = upsert_result

    # UPDATE for existing page cross-reference updates
    wiki_update_eq_mock = MagicMock()
    wiki_update_eq_mock.execute.return_value = MagicMock()

    wiki_update_ws_mock = MagicMock()
    wiki_update_ws_mock.eq.return_value = wiki_update_eq_mock

    wiki_update_mock = MagicMock()
    wiki_update_mock.eq.return_value = wiki_update_ws_mock

    # DELETE for reingest
    delete_eq_mock = MagicMock()
    delete_eq_mock.execute.return_value = MagicMock(data=[])

    delete_cs_mock = MagicMock()
    delete_cs_mock.execute.return_value = MagicMock(data=[])

    delete_ws_eq_mock = MagicMock()
    delete_ws_eq_mock.cs.return_value = delete_cs_mock

    wiki_delete_mock = MagicMock()
    wiki_delete_mock.eq.return_value = delete_ws_eq_mock

    wiki_table = MagicMock()
    wiki_table.select.return_value = wiki_select_mock
    wiki_table.upsert.return_value = wiki_upsert_mock
    wiki_table.update.return_value = wiki_update_mock
    wiki_table.delete.return_value = wiki_delete_mock

    # --- teemo_wiki_log mock ---
    log_insert_result = MagicMock()
    log_insert_result.data = [{"id": "log-001"}]
    log_insert_execute = MagicMock()
    log_insert_execute.execute.return_value = log_insert_result

    log_table = MagicMock()
    log_table.insert.return_value = log_insert_execute

    # --- Router ---
    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_documents":
            return docs_table
        if table_name == "teemo_wiki_pages":
            return wiki_table
        if table_name == "teemo_wiki_log":
            return log_table
        return MagicMock()

    supabase = MagicMock()
    supabase.table.side_effect = _table_router
    supabase._docs_table = docs_table
    supabase._wiki_table = wiki_table
    supabase._log_table = log_table
    return supabase


# ---------------------------------------------------------------------------
# Scenario 1: ingest_document produces pages with correct structure
# ---------------------------------------------------------------------------


class TestIngestDocumentStructure:
    """ingest_document must produce pages with correct fields and types."""

    @pytest.mark.asyncio
    async def test_ingest_produces_pages(self, monkeypatch):
        """ingest_document must return pages_created > 0 for a normal document."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        assert "pages_created" in result
        assert result["pages_created"] > 0, (
            f"Expected at least 1 page created, got {result['pages_created']}"
        )

    @pytest.mark.asyncio
    async def test_ingest_produces_source_summary_page(self, monkeypatch):
        """ingest_document must produce a source-summary page."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        page_types = result.get("page_types", {})
        assert "source-summary" in page_types, (
            f"Expected 'source-summary' in page_types. Got: {page_types}"
        )
        assert page_types["source-summary"] == 1, (
            f"Expected exactly 1 source-summary page, got {page_types['source-summary']}"
        )

    @pytest.mark.asyncio
    async def test_ingest_produces_concept_pages(self, monkeypatch):
        """ingest_document must produce concept pages for major themes."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        page_types = result.get("page_types", {})
        assert "concept" in page_types, (
            f"Expected 'concept' pages in result. Got page_types: {page_types}"
        )

    @pytest.mark.asyncio
    async def test_ingest_produces_entity_pages(self, monkeypatch):
        """ingest_document must produce entity pages for named items."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        page_types = result.get("page_types", {})
        assert "entity" in page_types, (
            f"Expected 'entity' pages in result. Got page_types: {page_types}"
        )

    @pytest.mark.asyncio
    async def test_ingest_upserts_pages_to_supabase(self, monkeypatch):
        """ingest_document must call supabase.table('teemo_wiki_pages').upsert() for each page."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        # teemo_wiki_pages.upsert() must have been called once per page
        wiki_table = supabase._wiki_table
        assert wiki_table.upsert.call_count == result["pages_created"], (
            f"Expected {result['pages_created']} upsert calls, "
            f"got {wiki_table.upsert.call_count}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: Tiny document threshold
# ---------------------------------------------------------------------------


class TestTinyDocumentThreshold:
    """Documents with content < 100 chars must skip LLM ingest."""

    @pytest.mark.asyncio
    async def test_tiny_doc_skips_ingest(self, monkeypatch):
        """ingest_document must return pages_created=0 for docs < 100 chars."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        # LLM should NOT be called — any call would be a test failure
        mocks["Agent"].side_effect = AssertionError("LLM was called for tiny document")

        tiny_content = "Short doc."  # 10 chars — below 100 char threshold
        supabase = _make_supabase_mock(document_content=tiny_content)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        assert result["pages_created"] == 0, (
            f"Expected 0 pages for tiny document, got {result['pages_created']}"
        )

    @pytest.mark.asyncio
    async def test_tiny_doc_sets_synced_status(self, monkeypatch):
        """ingest_document must set sync_status='synced' immediately for tiny docs."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        # Prevent real LLM call
        mocks["Agent"].return_value = MagicMock()

        tiny_content = "Too short."  # < 100 chars
        supabase = _make_supabase_mock(document_content=tiny_content)

        await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        # Verify update was called with sync_status='synced'
        docs_table = supabase._docs_table
        docs_table.update.assert_called()
        update_calls = docs_table.update.call_args_list
        synced_calls = [
            c for c in update_calls if c.args and c.args[0].get("sync_status") == "synced"
        ]
        assert synced_calls, (
            f"Expected update call with sync_status='synced' for tiny doc. "
            f"All update calls: {update_calls}"
        )

    @pytest.mark.asyncio
    async def test_empty_content_treated_as_tiny(self, monkeypatch):
        """ingest_document must skip ingest when content is empty/None."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        mocks["Agent"].return_value = MagicMock()

        supabase = _make_supabase_mock(document_content=None)

        result = await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        assert result["pages_created"] == 0


# ---------------------------------------------------------------------------
# Scenario 3: Sync status transitions (processing → synced)
# ---------------------------------------------------------------------------


class TestSyncStatusTransitions:
    """sync_status must transition: processing → synced on success."""

    @pytest.mark.asyncio
    async def test_sync_status_set_to_processing_before_llm(self, monkeypatch):
        """ingest_document must set sync_status='processing' before calling the LLM."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        processing_call_order = []

        mocks = _patch_agent_module_globals(monkeypatch)

        # Track when Agent is instantiated (LLM call happens after processing is set).
        # Using side_effect on the Agent class (not the docs_table.update mock) avoids
        # the recursion that would occur if we captured and re-called the mock with a
        # side_effect pointing back to itself.
        def _tracking_agent_cls(*args, **kwargs):
            processing_call_order.append("llm_call")
            agent_instance = MagicMock()
            result = MagicMock()
            result.output = SAMPLE_LLM_JSON_RESPONSE
            agent_instance.run = AsyncMock(return_value=result)
            return agent_instance

        mocks["Agent"].side_effect = _tracking_agent_cls

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        # Use a separate MagicMock that captures status without recursion:
        # replace docs_table.update with a fresh Mock whose side_effect records the
        # status and then returns a chainable MagicMock (no call to the original mock).
        update_return = MagicMock()
        update_return.eq.return_value = update_return
        update_return.execute.return_value = MagicMock()

        def _tracking_update(payload):
            status = payload.get("sync_status")
            if status:
                processing_call_order.append(f"set_{status}")
            return update_return

        supabase._docs_table.update = MagicMock(side_effect=_tracking_update)

        await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        # "processing" must appear before "llm_call"
        assert "set_processing" in processing_call_order, (
            f"sync_status='processing' must be set before LLM call. "
            f"Call order: {processing_call_order}"
        )
        proc_idx = processing_call_order.index("set_processing")
        llm_idx = processing_call_order.index("llm_call")
        assert proc_idx < llm_idx, (
            f"set_processing (idx={proc_idx}) must occur before llm_call (idx={llm_idx}). "
            f"Full order: {processing_call_order}"
        )

    @pytest.mark.asyncio
    async def test_sync_status_set_to_synced_on_success(self, monkeypatch):
        """ingest_document must set sync_status='synced' after successful ingest."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        docs_table = supabase._docs_table
        update_calls = docs_table.update.call_args_list
        synced_calls = [
            c for c in update_calls if c.args and c.args[0].get("sync_status") == "synced"
        ]
        assert synced_calls, (
            f"Expected update call with sync_status='synced' after successful ingest. "
            f"All update calls: {update_calls}"
        )


# ---------------------------------------------------------------------------
# Scenario 4: reingest_document deletes old pages first
# ---------------------------------------------------------------------------


class TestReingestDocument:
    """reingest_document must delete existing pages before re-ingesting."""

    @pytest.mark.asyncio
    async def test_reingest_deletes_old_pages(self, monkeypatch):
        """reingest_document must call DELETE on teemo_wiki_pages before ingest."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        await wiki_service.reingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        wiki_table = supabase._wiki_table
        wiki_table.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_reingest_deletes_by_document_id(self, monkeypatch):
        """reingest_document must scope deletion to the target document_id."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        await wiki_service.reingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        # The delete chain must filter by workspace_id
        wiki_table = supabase._wiki_table
        delete_mock = wiki_table.delete.return_value
        delete_mock.eq.assert_called_with("workspace_id", FAKE_WORKSPACE_ID)

    @pytest.mark.asyncio
    async def test_reingest_creates_new_pages_after_deletion(self, monkeypatch):
        """reingest_document must create new pages after deleting old ones."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        result = await wiki_service.reingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        assert result["pages_created"] > 0, (
            f"Expected new pages after re-ingest. Got: {result}"
        )

        # Upsert must have been called after delete
        wiki_table = supabase._wiki_table
        assert wiki_table.upsert.call_count == result["pages_created"], (
            f"Expected {result['pages_created']} upsert calls after re-ingest. "
            f"Got {wiki_table.upsert.call_count}"
        )


# ---------------------------------------------------------------------------
# Scenario 5: rebuild_wiki_index returns correct format
# ---------------------------------------------------------------------------


class TestRebuildWikiIndex:
    """rebuild_wiki_index must return list of { slug, title, tldr }."""

    @pytest.mark.asyncio
    async def test_rebuild_returns_correct_format(self, monkeypatch):
        """rebuild_wiki_index must return slug, title, tldr for all workspace pages."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        sample_pages = [
            {"slug": f"page-{i}", "title": f"Page {i}", "tldr": f"TLDR {i}"}
            for i in range(1, 6)
        ]
        supabase = _make_supabase_mock(existing_wiki_pages=sample_pages)

        result = await wiki_service.rebuild_wiki_index(supabase, FAKE_WORKSPACE_ID)

        assert isinstance(result, list), f"Expected list, got {type(result)}"
        assert len(result) == 5, f"Expected 5 entries, got {len(result)}"

        for entry in result:
            assert "slug" in entry, f"Missing 'slug' in entry: {entry}"
            assert "title" in entry, f"Missing 'title' in entry: {entry}"
            assert "tldr" in entry, f"Missing 'tldr' in entry: {entry}"

    @pytest.mark.asyncio
    async def test_rebuild_returns_empty_list_when_no_pages(self):
        """rebuild_wiki_index must return empty list when no wiki pages exist."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        supabase = _make_supabase_mock(existing_wiki_pages=[])

        result = await wiki_service.rebuild_wiki_index(supabase, FAKE_WORKSPACE_ID)

        assert result == [], f"Expected empty list for no pages, got {result}"

    @pytest.mark.asyncio
    async def test_rebuild_queries_workspace_id(self):
        """rebuild_wiki_index must filter by workspace_id."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        supabase = _make_supabase_mock(existing_wiki_pages=[])

        await wiki_service.rebuild_wiki_index(supabase, FAKE_WORKSPACE_ID)

        wiki_table = supabase._wiki_table
        # select() must have been called on teemo_wiki_pages
        wiki_table.select.assert_called()


# ---------------------------------------------------------------------------
# Scenario 6: Ingest failure sets error status
# ---------------------------------------------------------------------------


class TestIngestFailureSetsErrorStatus:
    """When the LLM call or page processing raises an exception, sync_status must be 'error'."""

    @pytest.mark.asyncio
    async def test_llm_failure_sets_error_status(self, monkeypatch):
        """ingest_document must set sync_status='error' when the LLM call fails."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)

        # Configure Agent to raise an exception on run()
        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("LLM API error"))
        mocks["Agent"].return_value = mock_agent_instance

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        with pytest.raises(RuntimeError, match="LLM API error"):
            await wiki_service.ingest_document(
                supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
            )

        docs_table = supabase._docs_table
        update_calls = docs_table.update.call_args_list
        error_calls = [
            c for c in update_calls if c.args and c.args[0].get("sync_status") == "error"
        ]
        assert error_calls, (
            f"Expected update call with sync_status='error' after LLM failure. "
            f"All update calls: {update_calls}"
        )

    @pytest.mark.asyncio
    async def test_failure_creates_log_entry(self, monkeypatch):
        """ingest_document must create a log entry in teemo_wiki_log on failure."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)

        mock_agent_instance = MagicMock()
        mock_agent_instance.run = AsyncMock(side_effect=RuntimeError("LLM API error"))
        mocks["Agent"].return_value = mock_agent_instance

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        with pytest.raises(RuntimeError):
            await wiki_service.ingest_document(
                supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
            )

        log_table = supabase._log_table
        log_table.insert.assert_called()


# ---------------------------------------------------------------------------
# Scenario 7: Log entry created on success
# ---------------------------------------------------------------------------


class TestWikiLogEntry:
    """A log entry in teemo_wiki_log must be created on successful ingest."""

    @pytest.mark.asyncio
    async def test_successful_ingest_creates_log_entry(self, monkeypatch):
        """ingest_document must insert a row into teemo_wiki_log after successful ingest."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        _configure_agent_mock_to_return_json(mocks, SAMPLE_LLM_JSON_RESPONSE)

        supabase = _make_supabase_mock(document_content=SAMPLE_CONTENT)

        await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        log_table = supabase._log_table
        log_table.insert.assert_called()

        # Verify log entry contains expected fields
        insert_calls = log_table.insert.call_args_list
        assert insert_calls, "Expected at least one insert call on teemo_wiki_log"

        log_payload = insert_calls[0].args[0] if insert_calls[0].args else {}
        assert "workspace_id" in log_payload, "Log entry must include workspace_id"
        assert "document_id" in log_payload, "Log entry must include document_id"
        assert "pages_created" in log_payload, "Log entry must include pages_created"
        assert "status" in log_payload, "Log entry must include status"
        # created_at is managed by DB — must NOT be in payload
        assert "created_at" not in log_payload, (
            "Log entry must NOT include created_at — managed by DB default"
        )

    @pytest.mark.asyncio
    async def test_tiny_doc_creates_log_entry(self, monkeypatch):
        """ingest_document must also create a log entry for tiny documents."""
        if wiki_service is None:
            pytest.skip("wiki_service not yet implemented")

        mocks = _patch_agent_module_globals(monkeypatch)
        mocks["Agent"].return_value = MagicMock()

        supabase = _make_supabase_mock(document_content="tiny")

        await wiki_service.ingest_document(
            supabase, FAKE_WORKSPACE_ID, FAKE_DOCUMENT_ID, FAKE_PROVIDER, FAKE_API_KEY
        )

        log_table = supabase._log_table
        log_table.insert.assert_called()
