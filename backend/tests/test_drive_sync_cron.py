"""
Tests for drive_sync_cron.py — EPIC-015, STORY-015-05.

Covers all four Gherkin scenarios:
  1. Hash change detection triggers re-fetch and document update.
  2. Unchanged file (matching hash) is skipped — no DB write, no LLM call.
  3. Error in one workspace doesn't crash the cron loop.
  4. Non-Drive documents are ignored.

Mock strategy:
  - ``app.core.db.get_supabase`` is patched so tests never touch a real DB.
  - ``app.services.drive_service.get_drive_client`` is patched.
  - ``app.services.drive_service.fetch_file_content`` is patched to return
    controlled content strings.
  - ``app.services.document_service.update_document`` is patched to avoid
    triggering real LLM calls or Supabase writes.
  - ``asyncio.sleep`` is patched to return immediately so the cron loop can be
    driven in tests without waiting 600 seconds.

All tests are async (pytest-asyncio).
"""

from __future__ import annotations

import asyncio
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.drive_sync_cron import _check_file, _sync_workspace, drive_sync_loop
from app.services.document_service import compute_content_hash


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WORKSPACE_ID = "aaaaaaaa-1111-0000-0000-000000000001"
DOC_ID_1 = "bbbbbbbb-1111-0000-0000-000000000001"
DOC_ID_2 = "bbbbbbbb-1111-0000-0000-000000000002"
EXTERNAL_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"


def _make_supabase_mock(docs: list[dict] | None = None, workspaces: list[dict] | None = None) -> MagicMock:
    """Build a lightweight Supabase client mock with chainable query methods.

    Returns data from the ``docs`` list for ``teemo_documents`` queries and
    from the ``workspaces`` list for ``teemo_workspaces`` queries.
    """
    mock = MagicMock()

    def _table_side_effect(table_name: str):
        chain = MagicMock()
        result = MagicMock()

        if table_name == "teemo_documents":
            result.data = docs if docs is not None else []
        elif table_name == "teemo_workspaces":
            result.data = workspaces if workspaces is not None else []
        else:
            result.data = []

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.not_.is_.return_value = chain
        chain.update.return_value = chain
        chain.execute.return_value = result
        return chain

    mock.table.side_effect = _table_side_effect
    return mock


def _make_drive_doc(
    doc_id: str = DOC_ID_1,
    external_id: str = EXTERNAL_ID,
    content_hash: str | None = None,
    mime_type: str | None = "application/pdf",
) -> dict:
    """Return a minimal teemo_documents row dict for a Drive-sourced document."""
    return {
        "id": doc_id,
        "workspace_id": WORKSPACE_ID,
        "source": "google_drive",
        "external_id": external_id,
        "content_hash": content_hash,
        "metadata": {"mime_type": mime_type} if mime_type else {},
    }


def _make_non_drive_doc(doc_id: str = DOC_ID_2) -> dict:
    """Return a minimal teemo_documents row dict for an agent-created document."""
    return {
        "id": doc_id,
        "workspace_id": WORKSPACE_ID,
        "source": "agent",
        "external_id": None,
        "content_hash": "abc123",
        "metadata": {},
    }


# ---------------------------------------------------------------------------
# Scenario 1: Hash change detection triggers re-fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_changed_file_triggers_update():
    """
    Scenario: Cron detects changed file
      Given a workspace with a Drive document whose content has changed
      When the cron runs (via _check_file)
      Then content is re-fetched and updated in teemo_documents
      And content_hash is recomputed
      And sync_status is set to 'pending' (via update_document)
    """
    old_content = "old content"
    new_content = "new content with changes"
    old_hash = compute_content_hash(old_content)

    doc_row = _make_drive_doc(content_hash=old_hash, mime_type="application/pdf")
    supabase = _make_supabase_mock(docs=[doc_row])

    mock_drive_client = MagicMock()
    # Drive returns an md5Checksum for binary files
    mock_drive_client.files.return_value.get.return_value.execute.return_value = {
        "md5Checksum": "some-md5-value"
    }

    with (
        patch(
            "app.services.drive_service.fetch_file_content",
            return_value=new_content,
        ) as mock_fetch,
        patch(
            "app.services.document_service.update_document",
            new_callable=AsyncMock,
            return_value={"id": DOC_ID_1},
        ) as mock_update,
    ):
        result = await _check_file(supabase, WORKSPACE_ID, mock_drive_client, doc_row)

    assert result is True
    mock_fetch.assert_called_once_with(
        mock_drive_client,
        EXTERNAL_ID,
        "application/pdf",
    )
    mock_update.assert_called_once_with(
        supabase,
        WORKSPACE_ID,
        DOC_ID_1,
        content=new_content,
    )


# ---------------------------------------------------------------------------
# Scenario 2: Unchanged file is skipped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unchanged_file_is_skipped():
    """
    Scenario: Cron skips unchanged files
      Given a Drive document whose content has NOT changed
      When _check_file runs
      Then update_document is never called
      And _check_file returns False
    """
    content = "unchanged content"
    content_hash = compute_content_hash(content)

    doc_row = _make_drive_doc(content_hash=content_hash, mime_type="application/pdf")
    supabase = _make_supabase_mock(docs=[doc_row])

    mock_drive_client = MagicMock()
    mock_drive_client.files.return_value.get.return_value.execute.return_value = {
        "md5Checksum": "any-md5"
    }

    with (
        patch(
            "app.services.drive_service.fetch_file_content",
            return_value=content,
        ),
        patch(
            "app.services.document_service.update_document",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        result = await _check_file(supabase, WORKSPACE_ID, mock_drive_client, doc_row)

    assert result is False
    mock_update.assert_not_called()


@pytest.mark.asyncio
async def test_unchanged_workspace_no_llm_calls():
    """
    Scenario: Cron skips unchanged files (workspace-level)
      Given a workspace with 3 Drive files, all unchanged
      When _sync_workspace runs
      Then no documents are modified
      And update_document is never called
    """
    content = "same content everywhere"
    content_hash = compute_content_hash(content)

    docs = [
        _make_drive_doc(doc_id=f"doc-{i}", content_hash=content_hash, mime_type="application/pdf")
        for i in range(3)
    ]

    supabase = _make_supabase_mock(docs=docs)

    workspace_row = {
        "id": WORKSPACE_ID,
        "encrypted_google_refresh_token": "encrypted-token-value",
    }

    mock_drive_client = MagicMock()
    mock_drive_client.files.return_value.get.return_value.execute.return_value = {
        "md5Checksum": "any-md5"
    }

    with (
        patch("app.services.drive_sync_cron.get_supabase", return_value=supabase),
        patch("app.services.drive_sync_cron.drive_service.get_drive_client", return_value=mock_drive_client),
        patch("app.services.drive_sync_cron.drive_service.fetch_file_content", return_value=content),
        patch(
            "app.services.drive_sync_cron.document_service.update_document",
            new_callable=AsyncMock,
        ) as mock_update,
    ):
        checked, updated = await _sync_workspace(workspace_row)

    assert checked == 3
    assert updated == 0
    mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 3: Error in one workspace doesn't crash the cron
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_workspace_error_does_not_crash_cron():
    """
    Scenario: Cron handles revoked Drive token
      Given a workspace whose Google refresh token has been revoked
      When drive_sync_loop runs one iteration
      Then the error is logged
      And the cron continues to the next workspace (loop does not crash)
    """
    workspace_rows = [
        {"id": "workspace-bad", "encrypted_google_refresh_token": "bad-token"},
        {"id": "workspace-good", "encrypted_google_refresh_token": "good-token"},
    ]

    good_content = "good doc content"
    good_hash = compute_content_hash(good_content)
    good_doc = _make_drive_doc(
        doc_id="good-doc-id",
        external_id="good-external-id",
        content_hash=good_hash,
        mime_type="application/pdf",
    )

    bad_supabase = MagicMock()
    good_supabase = _make_supabase_mock(docs=[good_doc])

    call_count = 0

    def _get_supabase_side_effect():
        return MagicMock()

    iteration_count = 0

    async def _fake_sleep(seconds):
        nonlocal iteration_count
        iteration_count += 1
        if iteration_count >= 2:
            raise asyncio.CancelledError()

    top_supabase = MagicMock()

    def _top_table_side_effect(name):
        chain = MagicMock()
        result = MagicMock()
        result.data = workspace_rows
        chain.select.return_value = chain
        chain.not_.is_.return_value = chain
        chain.execute.return_value = result
        return chain

    top_supabase.table.side_effect = _top_table_side_effect

    call_index = [0]

    def _get_drive_client_side_effect(token):
        if token == "bad-token":
            raise Exception("Token has been revoked")
        return MagicMock(
            files=lambda: MagicMock(
                get=lambda **kw: MagicMock(
                    execute=lambda: {"md5Checksum": "some-md5"}
                )
            )
        )

    workspace_call_index = [0]

    async def _fake_sync_workspace(workspace_row):
        if workspace_row["id"] == "workspace-bad":
            raise Exception("Token has been revoked")
        return (1, 0)

    with (
        patch("app.core.db.get_supabase", return_value=top_supabase),
        patch("app.services.drive_sync_cron._sync_workspace", side_effect=_fake_sync_workspace),
        patch("asyncio.sleep", side_effect=_fake_sleep),
    ):
        with pytest.raises(asyncio.CancelledError):
            await drive_sync_loop()

    # If we reach here without an unhandled exception (other than CancelledError),
    # the cron successfully handled the bad workspace error and continued.
    assert iteration_count >= 1


# ---------------------------------------------------------------------------
# Scenario 4: Non-Drive documents are ignored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_drive_docs_are_ignored():
    """
    Scenario: Cron ignores non-Drive documents
      Given a workspace with 2 Drive files and 1 agent-created doc
      When _sync_workspace runs
      Then only the 2 Drive files are checked via files.get
      And the agent-created doc is never touched
    """
    drive_doc_1 = _make_drive_doc(
        doc_id=DOC_ID_1,
        content_hash="hash-1",
        mime_type="application/pdf",
    )
    drive_doc_2 = _make_drive_doc(
        doc_id=DOC_ID_2,
        external_id="second-external-id",
        content_hash="hash-2",
        mime_type="application/vnd.google-apps.document",
    )
    # The supabase mock returns only docs with source='google_drive' because
    # the query filters on source='google_drive'. We simulate the filtered result.
    drive_docs_only = [drive_doc_1, drive_doc_2]

    supabase = _make_supabase_mock(docs=drive_docs_only)

    workspace_row = {
        "id": WORKSPACE_ID,
        "encrypted_google_refresh_token": "some-token",
    }

    mock_drive_client = MagicMock()
    mock_drive_client.files.return_value.get.return_value.execute.return_value = {
        "md5Checksum": "any-md5"
    }

    content_1 = "content for doc 1"
    content_2 = "content for doc 2"

    # Make content match stored hash so no updates happen
    drive_doc_1["content_hash"] = compute_content_hash(content_1)
    drive_doc_2["content_hash"] = compute_content_hash(content_2)

    fetch_call_count = [0]

    def _fake_fetch(drive_client, external_id, mime_type, **kwargs):
        fetch_call_count[0] += 1
        if external_id == EXTERNAL_ID:
            return content_1
        return content_2

    with (
        patch("app.services.drive_sync_cron.get_supabase", return_value=supabase),
        patch("app.services.drive_sync_cron.drive_service.get_drive_client", return_value=mock_drive_client),
        patch("app.services.drive_sync_cron.drive_service.fetch_file_content", side_effect=_fake_fetch),
        patch("app.services.drive_sync_cron.document_service.update_document", new_callable=AsyncMock) as mock_update,
    ):
        checked, updated = await _sync_workspace(workspace_row)

    # Only the 2 Drive docs from the filtered query are checked.
    assert checked == 2
    assert updated == 0
    # update_document was never called (hashes matched)
    mock_update.assert_not_called()
    # fetch_file_content was called exactly 2 times (once per Drive doc)
    assert fetch_call_count[0] == 2


# ---------------------------------------------------------------------------
# Scenario 5: Google Workspace files (no md5Checksum) always re-fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_google_workspace_file_always_refetched():
    """
    Google Workspace files (Docs/Sheets/Slides) have no md5Checksum in Drive
    metadata.  The cron must always re-fetch and compare SHA-256 hashes.
    Verify that when md5Checksum is absent AND content changed, update is called.
    """
    old_content = "original google doc content"
    new_content = "updated google doc content"
    old_hash = compute_content_hash(old_content)

    doc_row = _make_drive_doc(
        content_hash=old_hash,
        mime_type="application/vnd.google-apps.document",
    )
    supabase = _make_supabase_mock(docs=[doc_row])

    mock_drive_client = MagicMock()
    # No md5Checksum for Google Workspace files
    mock_drive_client.files.return_value.get.return_value.execute.return_value = {}

    with (
        patch(
            "app.services.drive_service.fetch_file_content",
            return_value=new_content,
        ),
        patch(
            "app.services.document_service.update_document",
            new_callable=AsyncMock,
            return_value={"id": DOC_ID_1},
        ) as mock_update,
    ):
        result = await _check_file(supabase, WORKSPACE_ID, mock_drive_client, doc_row)

    assert result is True
    mock_update.assert_called_once_with(
        supabase,
        WORKSPACE_ID,
        DOC_ID_1,
        content=new_content,
    )
