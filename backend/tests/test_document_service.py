"""
Tests for document_service.py — EPIC-015, STORY-015-01.

Covers:
  - compute_content_hash: SHA-256 digest, known-value verification
  - create_document: returns row with content_hash, sync_status='pending'
  - read_document_content: returns content; None for missing/wrong workspace
  - update_document: recomputes hash and ai_description, resets sync_status
  - delete_document: returns True on success, False on missing
  - list_documents: returns ordered list (newest first)

Mock strategy:
  - Supabase client is mocked with a chain-builder that records the table name
    and returns preset data via .execute().
  - scan_service.generate_ai_description is patched on the _scan_service module
    reference inside document_service so tests never call a real LLM.
  - app.core.encryption.decrypt is patched so key resolution can proceed without
    real AES-GCM secrets.
  - All tests are async (pytest-asyncio) because all service functions are async.
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# ---------------------------------------------------------------------------
# Module import — must succeed (GREEN phase)
# ---------------------------------------------------------------------------

from app.services.document_service import (
    compute_content_hash,
    create_document,
    delete_document,
    list_documents,
    read_document_content,
    update_document,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-0000-0000-0000-000000000001"
DOCUMENT_ID = "bbbbbbbb-0000-0000-0000-000000000002"
SAMPLE_CONTENT = "Hello world. This is a test document."
SAMPLE_HASH = hashlib.sha256(SAMPLE_CONTENT.encode("utf-8")).hexdigest()


def _make_supabase(return_data: list | None = None, single_data: dict | None = None):
    """Build a mock Supabase client whose .execute() returns preset data.

    The mock supports the chained query builder pattern:
        supabase.table(...).select(...).eq(...).execute()
        supabase.table(...).insert(...).execute()
        supabase.table(...).update(...).eq(...).eq(...).execute()
        supabase.table(...).delete().eq(...).eq(...).execute()
        supabase.table(...).order(...).execute()

    Parameters
    ----------
    return_data : list | None
        Value for result.data when the query returns a list (insert, update,
        delete, select-all, select-order).
    single_data : dict | None
        Value for result.data when the query uses .maybe_single() (workspace
        key lookup, read_document_content).
    """
    execute_result_list = MagicMock()
    execute_result_list.data = return_data if return_data is not None else []

    execute_result_single = MagicMock()
    execute_result_single.data = single_data

    chain = MagicMock()
    # All chaining methods return self so the chain is arbitrarily deep.
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.maybe_single.return_value = chain

    def _execute():
        # If maybe_single was called anywhere in the chain, use single_data path.
        if chain.maybe_single.called:
            return execute_result_single
        return execute_result_list

    chain.execute.side_effect = _execute

    supabase = MagicMock()
    supabase.table.return_value = chain
    return supabase


# ---------------------------------------------------------------------------
# compute_content_hash
# ---------------------------------------------------------------------------


class TestComputeContentHash:
    def test_known_value(self):
        """SHA-256 of 'Hello world. This is a test document.' must equal SAMPLE_HASH."""
        assert compute_content_hash(SAMPLE_CONTENT) == SAMPLE_HASH

    def test_empty_string(self):
        """SHA-256 of empty string must equal the known digest."""
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_content_hash("") == expected

    def test_returns_64_char_hex(self):
        """Result must be exactly 64 lowercase hex characters."""
        result = compute_content_hash("some content")
        assert len(result) == 64
        assert result == result.lower()
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_content_different_hash(self):
        """Different content must produce a different hash."""
        h1 = compute_content_hash("content A")
        h2 = compute_content_hash("content B")
        assert h1 != h2

    def test_deterministic(self):
        """Same content must produce the same hash across calls."""
        h1 = compute_content_hash(SAMPLE_CONTENT)
        h2 = compute_content_hash(SAMPLE_CONTENT)
        assert h1 == h2


# ---------------------------------------------------------------------------
# create_document
# ---------------------------------------------------------------------------


class TestCreateDocument:
    @pytest.mark.asyncio
    async def test_returns_row_with_sha256_hash(self):
        """create_document must return a row whose content_hash is SHA-256."""
        created_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "Test Doc",
            "content": SAMPLE_CONTENT,
            "content_hash": SAMPLE_HASH,
            "sync_status": "pending",
            "source": "agent",
            "doc_type": "markdown",
        }
        supabase = _make_supabase(return_data=[created_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value="An AI summary."),
        ):
            result = await create_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                title="Test Doc",
                content=SAMPLE_CONTENT,
                doc_type="markdown",
                source="agent",
            )

        assert result["content_hash"] == SAMPLE_HASH

    @pytest.mark.asyncio
    async def test_sync_status_is_pending(self):
        """create_document must insert with sync_status='pending'."""
        created_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "Test Doc",
            "content": SAMPLE_CONTENT,
            "content_hash": SAMPLE_HASH,
            "sync_status": "pending",
            "source": "agent",
            "doc_type": "markdown",
        }
        supabase = _make_supabase(return_data=[created_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value=None),
        ):
            result = await create_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                title="Test Doc",
                content=SAMPLE_CONTENT,
                doc_type="markdown",
                source="agent",
            )

        assert result["sync_status"] == "pending"

    @pytest.mark.asyncio
    async def test_calls_insert_with_correct_payload(self):
        """create_document must call supabase.table('teemo_documents').insert(...)."""
        created_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "My Doc",
            "content": SAMPLE_CONTENT,
            "content_hash": SAMPLE_HASH,
            "sync_status": "pending",
            "source": "google_drive",
            "doc_type": "pdf",
        }
        supabase = _make_supabase(return_data=[created_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value="Summary here."),
        ):
            await create_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                title="My Doc",
                content=SAMPLE_CONTENT,
                doc_type="pdf",
                source="google_drive",
                external_id="drive-file-001",
            )

        supabase.table.assert_called_with("teemo_documents")
        call_args = supabase.table.return_value.insert.call_args
        payload = call_args[0][0]
        assert payload["workspace_id"] == WORKSPACE_ID
        assert payload["content_hash"] == SAMPLE_HASH
        assert payload["sync_status"] == "pending"
        assert payload["external_id"] == "drive-file-001"

    @pytest.mark.asyncio
    async def test_none_content_skips_hash_and_description(self):
        """create_document with None content must set content_hash=None, ai_description=None."""
        created_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "Empty Doc",
            "content": None,
            "content_hash": None,
            "ai_description": None,
            "sync_status": "pending",
            "source": "agent",
            "doc_type": "markdown",
        }
        supabase = _make_supabase(return_data=[created_row])

        result = await create_document(
            supabase,
            workspace_id=WORKSPACE_ID,
            title="Empty Doc",
            content=None,
            doc_type="markdown",
            source="agent",
        )

        assert result["content_hash"] is None
        assert result["ai_description"] is None

    @pytest.mark.asyncio
    async def test_ai_description_failure_does_not_raise(self):
        """create_document must succeed even when AI description generation fails."""
        created_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "Robust Doc",
            "content": SAMPLE_CONTENT,
            "content_hash": SAMPLE_HASH,
            "ai_description": None,
            "sync_status": "pending",
            "source": "agent",
            "doc_type": "markdown",
        }
        supabase = _make_supabase(return_data=[created_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value=None),
        ):
            result = await create_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                title="Robust Doc",
                content=SAMPLE_CONTENT,
                doc_type="markdown",
                source="agent",
            )

        # Must return the row without raising
        assert result["id"] == DOCUMENT_ID


# ---------------------------------------------------------------------------
# read_document_content
# ---------------------------------------------------------------------------


class TestReadDocumentContent:
    @pytest.mark.asyncio
    async def test_returns_content_for_existing_doc(self):
        """read_document_content must return the content string for a matching row."""
        supabase = _make_supabase(single_data={"content": SAMPLE_CONTENT})

        result = await read_document_content(supabase, WORKSPACE_ID, DOCUMENT_ID)

        assert result == SAMPLE_CONTENT

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_doc(self):
        """read_document_content must return None when no matching row exists."""
        supabase = _make_supabase(single_data=None)

        result = await read_document_content(supabase, WORKSPACE_ID, DOCUMENT_ID)

        assert result is None

    @pytest.mark.asyncio
    async def test_workspace_isolation_enforced(self):
        """read_document_content must filter by workspace_id (not just document_id)."""
        supabase = _make_supabase(single_data=None)

        result = await read_document_content(
            supabase,
            workspace_id="different-workspace-id",
            document_id=DOCUMENT_ID,
        )

        # No row returned because the workspace doesn't match
        assert result is None
        # Verify .eq was called with workspace_id filter
        chain = supabase.table.return_value
        eq_calls = [str(call) for call in chain.eq.call_args_list]
        assert any("workspace_id" in c for c in eq_calls)


# ---------------------------------------------------------------------------
# update_document
# ---------------------------------------------------------------------------


class TestUpdateDocument:
    @pytest.mark.asyncio
    async def test_recomputes_hash_when_content_changed(self):
        """update_document must recompute content_hash when content is provided."""
        new_content = "Updated content here."
        new_hash = compute_content_hash(new_content)
        updated_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "content": new_content,
            "content_hash": new_hash,
            "sync_status": "pending",
        }
        supabase = _make_supabase(return_data=[updated_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value="Updated summary."),
        ):
            result = await update_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                document_id=DOCUMENT_ID,
                content=new_content,
            )

        assert result["content_hash"] == new_hash

    @pytest.mark.asyncio
    async def test_resets_sync_status_to_pending(self):
        """update_document must always reset sync_status to 'pending'."""
        updated_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "sync_status": "pending",
        }
        supabase = _make_supabase(return_data=[updated_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value=None),
        ):
            result = await update_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                document_id=DOCUMENT_ID,
                content="New content",
            )

        assert result["sync_status"] == "pending"

    @pytest.mark.asyncio
    async def test_title_only_update_no_hash_recompute(self):
        """update_document with only title must not set content_hash in payload."""
        updated_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "title": "New Title",
            "sync_status": "pending",
        }
        supabase = _make_supabase(return_data=[updated_row])

        await update_document(
            supabase,
            workspace_id=WORKSPACE_ID,
            document_id=DOCUMENT_ID,
            title="New Title",
        )

        chain = supabase.table.return_value
        update_payload = chain.update.call_args[0][0]
        assert "content_hash" not in update_payload
        assert update_payload["title"] == "New Title"
        assert update_payload["sync_status"] == "pending"

    @pytest.mark.asyncio
    async def test_regenerates_ai_description_on_content_change(self):
        """update_document must call _resolve_ai_description when content changes."""
        updated_row = {
            "id": DOCUMENT_ID,
            "workspace_id": WORKSPACE_ID,
            "sync_status": "pending",
            "ai_description": "New description.",
        }
        supabase = _make_supabase(return_data=[updated_row])

        with patch(
            "app.services.document_service._resolve_ai_description",
            new=AsyncMock(return_value="New description."),
        ) as mock_ai:
            await update_document(
                supabase,
                workspace_id=WORKSPACE_ID,
                document_id=DOCUMENT_ID,
                content="Updated text.",
            )

        mock_ai.assert_awaited_once_with(supabase, WORKSPACE_ID, "Updated text.")


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_returns_true_when_row_deleted(self):
        """delete_document must return True when the Supabase response has data."""
        deleted_row = {"id": DOCUMENT_ID, "workspace_id": WORKSPACE_ID}
        supabase = _make_supabase(return_data=[deleted_row])

        result = await delete_document(supabase, WORKSPACE_ID, DOCUMENT_ID)

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_no_row_found(self):
        """delete_document must return False when Supabase returns empty data."""
        supabase = _make_supabase(return_data=[])

        result = await delete_document(supabase, WORKSPACE_ID, DOCUMENT_ID)

        assert result is False

    @pytest.mark.asyncio
    async def test_workspace_isolation_enforced(self):
        """delete_document must include workspace_id filter in the delete query."""
        supabase = _make_supabase(return_data=[])

        await delete_document(supabase, WORKSPACE_ID, DOCUMENT_ID)

        chain = supabase.table.return_value
        eq_calls = [str(call) for call in chain.eq.call_args_list]
        assert any("workspace_id" in c for c in eq_calls)


# ---------------------------------------------------------------------------
# list_documents
# ---------------------------------------------------------------------------


class TestListDocuments:
    @pytest.mark.asyncio
    async def test_returns_ordered_list(self):
        """list_documents must return the data list from the Supabase response."""
        rows = [
            {"id": "doc-3", "created_at": "2026-04-13T12:00:00Z"},
            {"id": "doc-1", "created_at": "2026-04-11T12:00:00Z"},
        ]
        supabase = _make_supabase(return_data=rows)

        result = await list_documents(supabase, WORKSPACE_ID)

        assert result == rows

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_documents(self):
        """list_documents must return an empty list when the workspace has no docs."""
        supabase = _make_supabase(return_data=[])

        result = await list_documents(supabase, WORKSPACE_ID)

        assert result == []

    @pytest.mark.asyncio
    async def test_calls_order_desc(self):
        """list_documents must call .order('created_at', desc=True)."""
        supabase = _make_supabase(return_data=[])

        await list_documents(supabase, WORKSPACE_ID)

        chain = supabase.table.return_value
        chain.order.assert_called_with("created_at", desc=True)

    @pytest.mark.asyncio
    async def test_filters_by_workspace_id(self):
        """list_documents must filter on workspace_id."""
        supabase = _make_supabase(return_data=[])

        await list_documents(supabase, WORKSPACE_ID)

        chain = supabase.table.return_value
        eq_calls = [str(call) for call in chain.eq.call_args_list]
        assert any("workspace_id" in c for c in eq_calls)


# ---------------------------------------------------------------------------
# _resolve_ai_description (via create_document integration)
# ---------------------------------------------------------------------------


class TestResolveAiDescription:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_byok_key(self):
        """_resolve_ai_description must return None when encrypted_api_key is absent."""
        from app.services.document_service import _resolve_ai_description

        supabase = _make_supabase(single_data={"ai_provider": "google", "encrypted_api_key": None})

        result = await _resolve_ai_description(supabase, WORKSPACE_ID, SAMPLE_CONTENT)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_workspace_missing(self):
        """_resolve_ai_description must return None when workspace row not found."""
        from app.services.document_service import _resolve_ai_description

        supabase = _make_supabase(single_data=None)

        result = await _resolve_ai_description(supabase, WORKSPACE_ID, SAMPLE_CONTENT)

        assert result is None

    @pytest.mark.asyncio
    async def test_calls_generate_ai_description_with_decrypted_key(self):
        """_resolve_ai_description must decrypt the key and pass it to scan_service.

        ``app.core.encryption`` is injected via sys.modules so that the inline
        ``from app.core.encryption import decrypt`` inside _resolve_ai_description
        resolves to our mock without triggering the real Pydantic Settings load
        (which requires a .env file not present in the worktree test environment).
        """
        import sys
        import types
        from app.services.document_service import _resolve_ai_description

        supabase = _make_supabase(
            single_data={
                "ai_provider": "anthropic",
                "encrypted_api_key": "encrypted-blob",
            }
        )

        mock_decrypt = MagicMock(return_value="plain-api-key")
        mock_encryption_module = types.ModuleType("app.core.encryption")
        mock_encryption_module.decrypt = mock_decrypt

        # Also ensure app.core is in sys.modules (as a package) so the relative
        # import `from app.core.encryption import decrypt` resolves from
        # sys.modules["app.core.encryption"] without triggering a real package load.
        import app.core as _app_core  # noqa: F401 — ensures app.core is registered

        original = sys.modules.get("app.core.encryption")
        sys.modules["app.core.encryption"] = mock_encryption_module
        try:
            with patch(
                "app.services.document_service._scan_service.generate_ai_description",
                new=AsyncMock(return_value="Summary from AI."),
            ) as mock_gen:
                result = await _resolve_ai_description(supabase, WORKSPACE_ID, SAMPLE_CONTENT)
        finally:
            if original is None:
                sys.modules.pop("app.core.encryption", None)
            else:
                sys.modules["app.core.encryption"] = original

        assert result == "Summary from AI."
        mock_gen.assert_awaited_once_with(SAMPLE_CONTENT, "anthropic", "plain-api-key")

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        """_resolve_ai_description must swallow exceptions and return None.

        ``app.core.encryption`` is injected via sys.modules (same pattern as above).
        """
        import sys
        import types
        from app.services.document_service import _resolve_ai_description

        supabase = _make_supabase(
            single_data={
                "ai_provider": "openai",
                "encrypted_api_key": "encrypted-blob",
            }
        )

        mock_encryption_module = types.ModuleType("app.core.encryption")
        mock_encryption_module.decrypt = MagicMock(return_value="plain-api-key")

        original = sys.modules.get("app.core.encryption")
        sys.modules["app.core.encryption"] = mock_encryption_module
        try:
            with patch(
                "app.services.document_service._scan_service.generate_ai_description",
                new=AsyncMock(side_effect=RuntimeError("LLM unavailable")),
            ):
                result = await _resolve_ai_description(supabase, WORKSPACE_ID, SAMPLE_CONTENT)
        finally:
            if original is None:
                sys.modules.pop("app.core.encryption", None)
            else:
                sys.modules["app.core.encryption"] = original

        assert result is None
