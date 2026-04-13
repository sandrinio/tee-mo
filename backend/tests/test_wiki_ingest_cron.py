"""
Tests for wiki_ingest_cron.py — EPIC-013, STORY-013-03.

Covers all four Gherkin scenarios:
  1. Cron processes pending documents (both are ingested, sync_status → 'synced').
  2. Cron skips errored documents (only 'pending' rows are queried).
  3. Document deletion cascades to wiki pages.
  4. Cron handles ingest failure gracefully (sync_status → 'error', continues).

Mock strategy:
  - ``app.core.db.get_supabase`` is patched so tests never touch a real DB.
  - ``app.services.wiki_service.ingest_document`` and ``reingest_document``
    are patched via the ``wiki_service`` module reference.
  - ``app.core.encryption.decrypt`` is patched via sys.modules injection so
    that lazy imports in ``_resolve_workspace_key`` resolve to the mock.
  - ``asyncio.sleep`` is patched to return immediately (or raise CancelledError
    after N iterations) so the infinite loop can be driven in tests.

All tests are async (pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.wiki_ingest_cron import (
    _has_existing_wiki_pages,
    _process_document,
    _resolve_workspace_key,
    wiki_ingest_loop,
)
from app.services import document_service


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE_ID = "cccccccc-1111-0000-0000-000000000001"
DOC_ID_1 = "dddddddd-1111-0000-0000-000000000001"
DOC_ID_2 = "dddddddd-1111-0000-0000-000000000002"
PROVIDER = "anthropic"
ENCRYPTED_KEY = "enc-key-value"
PLAIN_KEY = "plain-api-key"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_supabase_mock(
    pending_docs: list[dict] | None = None,
    workspace_row: dict | None = None,
    wiki_pages: list[dict] | None = None,
) -> MagicMock:
    """Build a lightweight Supabase client mock with chainable query methods.

    Returns data from appropriate lists based on the table being queried.

    Args:
        pending_docs:   Documents to return for teemo_documents queries.
        workspace_row:  Dict to return for teemo_workspaces maybe_single().
        wiki_pages:     Wiki pages to return for teemo_wiki_pages queries.
    """
    mock = MagicMock()

    def _table_side_effect(table_name: str):
        chain = MagicMock()
        result = MagicMock()
        single_result = MagicMock()

        if table_name == "teemo_documents":
            result.data = pending_docs if pending_docs is not None else []
        elif table_name == "teemo_workspaces":
            result.data = workspace_row
            single_result.data = workspace_row
        elif table_name == "teemo_wiki_pages":
            result.data = wiki_pages if wiki_pages is not None else []
        else:
            result.data = []

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.cs.return_value = chain
        chain.limit.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.execute.return_value = result
        chain.maybe_single.return_value = chain
        # For maybe_single chain: execute returns single_result for workspace queries
        # We override execute on the chain so maybe_single().execute() returns workspace data
        def _execute():
            if table_name == "teemo_workspaces":
                return single_result
            return result
        chain.execute.side_effect = _execute
        return chain

    mock.table.side_effect = _table_side_effect
    return mock


def _make_pending_doc(doc_id: str = DOC_ID_1, workspace_id: str = WORKSPACE_ID) -> dict:
    """Return a minimal teemo_documents row dict for a pending document."""
    return {
        "id": doc_id,
        "workspace_id": workspace_id,
        "sync_status": "pending",
        "title": f"Test Document {doc_id}",
        "content": "Some document content for testing",
    }


def _make_workspace_row(
    workspace_id: str = WORKSPACE_ID,
    provider: str = PROVIDER,
    encrypted_key: str = ENCRYPTED_KEY,
) -> dict:
    """Return a minimal teemo_workspaces row dict."""
    return {
        "id": workspace_id,
        "ai_provider": provider,
        "encrypted_api_key": encrypted_key,
    }


def _inject_decrypt_mock(plain_key: str = PLAIN_KEY):
    """Inject a mock encryption module into sys.modules so lazy imports resolve.

    Returns the mock module so callers can assert on decrypt() calls.
    """
    mock_encryption = ModuleType("app.core.encryption")
    mock_decrypt = MagicMock(return_value=plain_key)
    mock_encryption.decrypt = mock_decrypt
    sys.modules["app.core.encryption"] = mock_encryption
    return mock_encryption


# ---------------------------------------------------------------------------
# Scenario 1: Cron processes pending documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_processes_two_pending_documents():
    """
    Scenario: Cron processes pending documents
      Given 2 documents with sync_status "pending"
      When the wiki ingest cron runs one cycle
      Then both documents are ingested into wiki pages
      And sync_status is set to "synced" for both (by wiki_service)
    """
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    doc1 = _make_pending_doc(doc_id=DOC_ID_1)
    doc2 = _make_pending_doc(doc_id=DOC_ID_2)
    workspace_row = _make_workspace_row()

    supabase = _make_supabase_mock(
        pending_docs=[doc1, doc2],
        workspace_row=workspace_row,
        wiki_pages=[],  # No existing pages → use ingest_document
    )

    iteration_count = [0]

    async def _fake_sleep(seconds):
        iteration_count[0] += 1
        raise asyncio.CancelledError()

    with (
        patch("app.services.wiki_ingest_cron.get_supabase", return_value=supabase),
        patch(
            "app.services.wiki_ingest_cron.wiki_service.ingest_document",
            new_callable=AsyncMock,
            return_value={"pages_created": 3, "page_types": {"source-summary": 1, "concept": 2}},
        ) as mock_ingest,
        patch(
            "app.services.wiki_ingest_cron.wiki_service.reingest_document",
            new_callable=AsyncMock,
        ) as mock_reingest,
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await wiki_ingest_loop()

    # Both documents were processed via ingest_document (no existing pages)
    assert mock_ingest.call_count == 2
    mock_reingest.assert_not_called()

    # Verify both document IDs were passed
    called_doc_ids = {c.args[2] for c in mock_ingest.call_args_list}
    assert DOC_ID_1 in called_doc_ids
    assert DOC_ID_2 in called_doc_ids


@pytest.mark.asyncio
async def test_cron_calls_reingest_when_pages_exist():
    """
    Scenario: Cron calls reingest_document when wiki pages already exist
      Given a document with sync_status "pending"
      And wiki pages already exist for that document
      When the wiki ingest cron runs
      Then reingest_document is called (not ingest_document)
    """
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    doc = _make_pending_doc(doc_id=DOC_ID_1)
    workspace_row = _make_workspace_row()
    existing_page = {
        "id": "page-1",
        "workspace_id": WORKSPACE_ID,
        "slug": "test-page",
        "source_document_ids": [DOC_ID_1],
    }

    supabase = _make_supabase_mock(
        pending_docs=[doc],
        workspace_row=workspace_row,
        wiki_pages=[existing_page],  # Existing pages → use reingest_document
    )

    async def _fake_sleep(seconds):
        raise asyncio.CancelledError()

    with (
        patch("app.services.wiki_ingest_cron.get_supabase", return_value=supabase),
        patch(
            "app.services.wiki_ingest_cron.wiki_service.ingest_document",
            new_callable=AsyncMock,
        ) as mock_ingest,
        patch(
            "app.services.wiki_ingest_cron.wiki_service.reingest_document",
            new_callable=AsyncMock,
            return_value={"pages_created": 3, "page_types": {}},
        ) as mock_reingest,
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await wiki_ingest_loop()

    mock_reingest.assert_called_once_with(
        supabase, WORKSPACE_ID, DOC_ID_1, PROVIDER, PLAIN_KEY
    )
    mock_ingest.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 2: Cron skips errored documents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_skips_error_documents():
    """
    Scenario: Cron skips errored documents
      Given a document with sync_status "error"
      When the wiki ingest cron runs
      Then the document is NOT processed
      (The query filters on sync_status='pending' — error docs never appear)
    """
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    # The cron only queries pending docs — the mock returns empty list
    # simulating that the error doc is not returned by the DB query.
    supabase = _make_supabase_mock(
        pending_docs=[],  # No pending docs (error doc filtered by query)
        workspace_row=_make_workspace_row(),
        wiki_pages=[],
    )

    async def _fake_sleep(seconds):
        raise asyncio.CancelledError()

    with (
        patch("app.services.wiki_ingest_cron.get_supabase", return_value=supabase),
        patch(
            "app.services.wiki_ingest_cron.wiki_service.ingest_document",
            new_callable=AsyncMock,
        ) as mock_ingest,
        patch(
            "app.services.wiki_ingest_cron.wiki_service.reingest_document",
            new_callable=AsyncMock,
        ) as mock_reingest,
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await wiki_ingest_loop()

    mock_ingest.assert_not_called()
    mock_reingest.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 3: Document deletion cascades to wiki pages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_document_cascades_to_wiki_pages():
    """
    Scenario: Document deletion cascades to wiki pages
      Given a document with 8 associated wiki pages
      When the document is deleted
      Then all 8 wiki pages are deleted via .cs() array-contains filter
    """
    # Track calls to the Supabase mock
    delete_calls: list[str] = []

    supabase = MagicMock()

    doc_chain = MagicMock()
    doc_result = MagicMock()
    doc_result.data = [{"id": DOC_ID_1}]  # Row was deleted
    doc_chain.delete.return_value = doc_chain
    doc_chain.eq.return_value = doc_chain
    doc_chain.execute.return_value = doc_result

    wiki_chain = MagicMock()
    wiki_result = MagicMock()
    wiki_result.data = []  # wiki delete result (success, no returned rows needed)
    wiki_chain.delete.return_value = wiki_chain
    wiki_chain.eq.return_value = wiki_chain
    wiki_chain.cs.return_value = wiki_chain
    wiki_chain.execute.return_value = wiki_result

    def _table_side_effect(table_name: str):
        delete_calls.append(table_name)
        if table_name == "teemo_documents":
            return doc_chain
        elif table_name == "teemo_wiki_pages":
            return wiki_chain
        return MagicMock()

    supabase.table.side_effect = _table_side_effect

    result = await document_service.delete_document(supabase, WORKSPACE_ID, DOC_ID_1)

    assert result is True
    # Both tables should have been targeted
    assert "teemo_documents" in delete_calls
    assert "teemo_wiki_pages" in delete_calls

    # Verify wiki_pages used .cs() filter with the document UUID
    wiki_chain.cs.assert_called_once_with("source_document_ids", [DOC_ID_1])
    # Verify workspace isolation on wiki pages
    wiki_chain.eq.assert_any_call("workspace_id", WORKSPACE_ID)


@pytest.mark.asyncio
async def test_delete_document_wiki_cascade_failure_does_not_propagate():
    """
    Scenario: Wiki cascade failure is best-effort — delete still returns True
      Given a document that exists
      And the wiki pages delete call raises an exception
      When delete_document is called
      Then the document is successfully deleted (returns True)
      And no exception is raised to the caller
    """
    supabase = MagicMock()

    doc_chain = MagicMock()
    doc_result = MagicMock()
    doc_result.data = [{"id": DOC_ID_1}]
    doc_chain.delete.return_value = doc_chain
    doc_chain.eq.return_value = doc_chain
    doc_chain.execute.return_value = doc_result

    wiki_chain = MagicMock()
    wiki_chain.delete.return_value = wiki_chain
    wiki_chain.eq.return_value = wiki_chain
    wiki_chain.cs.return_value = wiki_chain
    wiki_chain.execute.side_effect = Exception("DB connection error during wiki cleanup")

    def _table_side_effect(table_name: str):
        if table_name == "teemo_documents":
            return doc_chain
        elif table_name == "teemo_wiki_pages":
            return wiki_chain
        return MagicMock()

    supabase.table.side_effect = _table_side_effect

    # Should not raise even though wiki pages cleanup failed
    result = await document_service.delete_document(supabase, WORKSPACE_ID, DOC_ID_1)
    assert result is True


@pytest.mark.asyncio
async def test_delete_document_no_row_skips_wiki_cascade():
    """
    Scenario: No document row found — wiki cascade is NOT triggered
      Given no document with the given ID exists
      When delete_document is called
      Then it returns False
      And teemo_wiki_pages is never touched
    """
    supabase = MagicMock()

    doc_chain = MagicMock()
    doc_result = MagicMock()
    doc_result.data = []  # No row deleted
    doc_chain.delete.return_value = doc_chain
    doc_chain.eq.return_value = doc_chain
    doc_chain.execute.return_value = doc_result

    wiki_chain = MagicMock()

    tables_accessed: list[str] = []

    def _table_side_effect(table_name: str):
        tables_accessed.append(table_name)
        if table_name == "teemo_documents":
            return doc_chain
        return wiki_chain

    supabase.table.side_effect = _table_side_effect

    result = await document_service.delete_document(supabase, WORKSPACE_ID, DOC_ID_1)

    assert result is False
    assert "teemo_wiki_pages" not in tables_accessed


# ---------------------------------------------------------------------------
# Scenario 4: Cron handles ingest failure gracefully
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cron_handles_ingest_failure_gracefully():
    """
    Scenario: Cron handles ingest failure gracefully
      Given a document whose ingest fails
      When the cron processes it
      Then sync_status is set to "error"
      And the cron continues to the next document (processes both docs)
    """
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    doc1 = _make_pending_doc(doc_id=DOC_ID_1)
    doc2 = _make_pending_doc(doc_id=DOC_ID_2)
    workspace_row = _make_workspace_row()

    # Track update calls to verify sync_status='error' is set
    update_calls: list[dict] = []

    supabase = MagicMock()

    def _table_side_effect(table_name: str):
        chain = MagicMock()
        result = MagicMock()
        single_result = MagicMock()

        if table_name == "teemo_documents":
            result.data = [doc1, doc2]
            single_result.data = None

            def _execute():
                return result

            chain.execute.side_effect = _execute
        elif table_name == "teemo_workspaces":
            single_result.data = workspace_row
            result.data = workspace_row

            def _execute():
                return single_result

            chain.execute.side_effect = _execute
        elif table_name == "teemo_wiki_pages":
            result.data = []  # No existing pages

            def _execute():
                return result

            chain.execute.side_effect = _execute

            def _cs_execute():
                return result

        else:
            result.data = []

            def _execute():
                return result

            chain.execute.side_effect = _execute

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.cs.return_value = chain
        chain.limit.return_value = chain
        chain.maybe_single.return_value = chain

        # Capture update() calls to track sync_status='error' writes
        def _update(payload):
            update_calls.append({"table": table_name, "payload": payload})
            return chain

        chain.update.side_effect = _update
        chain.delete.return_value = chain
        return chain

    supabase.table.side_effect = _table_side_effect

    async def _fake_sleep(seconds):
        raise asyncio.CancelledError()

    call_count = [0]

    async def _failing_first_ingest(sb, ws_id, doc_id, provider, api_key):
        call_count[0] += 1
        if doc_id == DOC_ID_1:
            raise RuntimeError("LLM API timeout")
        return {"pages_created": 2, "page_types": {"source-summary": 1, "concept": 1}}

    with (
        patch("app.services.wiki_ingest_cron.get_supabase", return_value=supabase),
        patch(
            "app.services.wiki_ingest_cron.wiki_service.ingest_document",
            side_effect=_failing_first_ingest,
        ),
        patch(
            "app.services.wiki_ingest_cron.wiki_service.reingest_document",
            new_callable=AsyncMock,
        ) as mock_reingest,
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await wiki_ingest_loop()

    # Both documents were attempted
    assert call_count[0] == 2

    # sync_status='error' was set for the failing document
    error_updates = [
        c for c in update_calls
        if c["table"] == "teemo_documents" and c["payload"].get("sync_status") == "error"
    ]
    assert len(error_updates) >= 1


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_workspace_key_success():
    """_resolve_workspace_key returns (provider, plaintext_key) on success."""
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    workspace_row = _make_workspace_row()
    supabase = _make_supabase_mock(workspace_row=workspace_row)

    result = await _resolve_workspace_key(supabase, WORKSPACE_ID)

    assert result is not None
    provider, key = result
    assert provider == PROVIDER
    assert key == PLAIN_KEY
    mock_encryption.decrypt.assert_called_once_with(ENCRYPTED_KEY)


@pytest.mark.asyncio
async def test_resolve_workspace_key_missing_workspace():
    """_resolve_workspace_key returns None when workspace row is not found."""
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    # workspace_row=None means maybe_single returns no data
    supabase = _make_supabase_mock(workspace_row=None)

    result = await _resolve_workspace_key(supabase, WORKSPACE_ID)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_workspace_key_no_api_key():
    """_resolve_workspace_key returns None when encrypted_api_key is absent."""
    mock_encryption = _inject_decrypt_mock(PLAIN_KEY)

    workspace_row_no_key = {"id": WORKSPACE_ID, "ai_provider": PROVIDER, "encrypted_api_key": None}
    supabase = _make_supabase_mock(workspace_row=workspace_row_no_key)

    result = await _resolve_workspace_key(supabase, WORKSPACE_ID)
    assert result is None


def test_has_existing_wiki_pages_true():
    """_has_existing_wiki_pages returns True when pages exist."""
    supabase = MagicMock()
    chain = MagicMock()
    result = MagicMock()
    result.data = [{"id": "page-1"}]
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.cs.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = result
    supabase.table.return_value = chain

    assert _has_existing_wiki_pages(supabase, WORKSPACE_ID, DOC_ID_1) is True
    chain.cs.assert_called_once_with("source_document_ids", [DOC_ID_1])


def test_has_existing_wiki_pages_false():
    """_has_existing_wiki_pages returns False when no pages exist."""
    supabase = MagicMock()
    chain = MagicMock()
    result = MagicMock()
    result.data = []
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.cs.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = result
    supabase.table.return_value = chain

    assert _has_existing_wiki_pages(supabase, WORKSPACE_ID, DOC_ID_1) is False
