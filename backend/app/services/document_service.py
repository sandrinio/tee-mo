"""
Document CRUD service for Tee-Mo — EPIC-015, STORY-015-01.

Single entry point for all document create/read/update/delete operations.
Both API routes (STORY-015-02) and agent tools (STORY-015-03) call this
service — no direct Supabase queries for document CRUD anywhere else.

Design decisions:
  - SHA-256 (hashlib) for content hashing (sprint-context SHA-256 rule; upgrades
    drive_service.py's legacy MD5).
  - AI description generation uses the workspace's BYOK key via the same
    pattern as build_agent(): query teemo_workspaces for ai_provider +
    encrypted_api_key, decrypt, pass to scan_service.generate_ai_description.
    If no key is configured or resolution fails, ai_description is set to None
    and the operation continues — description is enriching metadata, not blocking.
  - Workspace isolation: every query filters on workspace_id so one workspace
    can never touch another workspace's documents.
  - sync_status starts at 'pending' on create and resets to 'pending' on
    content update — this is the handoff signal for the EPIC-013 wiki pipeline.
  - updated_at is managed by the DB trigger (migration 010) — never pass it
    in an insert/update payload (FLASHCARDS: omit DEFAULT NOW() columns).
  - created_at is also managed by the DB — omit from insert payloads.
"""

from __future__ import annotations

import hashlib
import logging

from app.services import scan_service as _scan_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_content_hash(content: str) -> str:
    """Compute the SHA-256 hex digest of a content string.

    Used to detect content changes for re-indexing (cron / wiki pipeline).
    Replaces the legacy MD5 hash in drive_service.compute_content_hash.

    Args:
        content: Document text content to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string (64 characters).
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def _resolve_ai_description(supabase, workspace_id: str, content: str) -> str | None:
    """Attempt to generate an AI description for the given content.

    Queries the workspace row for ai_provider + encrypted_api_key, decrypts
    the key, then calls scan_service.generate_ai_description. Returns None
    (without raising) if:
      - The workspace row is missing.
      - No API key is configured (encrypted_api_key is NULL).
      - Decryption or generation raises any exception.

    AI description is enriching metadata, not critical — callers must not
    fail the outer operation when this returns None.

    ``decrypt`` is imported lazily inside this function (not at module level)
    because ``app.core.encryption`` loads ``app.core.config`` which requires
    environment variables. Tests inject a fake ``app.core.encryption`` module
    via ``sys.modules`` before calling this function so the inline import
    resolves to the mock without triggering a Settings validation error.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID string of the workspace whose BYOK key to use.
        content:      Full document text to summarise.

    Returns:
        2-3 sentence AI summary string, or None on any failure.
    """
    try:
        from app.core.encryption import decrypt  # lazy: avoids .env load at module import time

        result = (
            supabase.table("teemo_workspaces")
            .select("ai_provider, encrypted_api_key")
            .eq("id", workspace_id)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return None

        row = result.data
        provider: str | None = row.get("ai_provider")
        encrypted_api_key: str | None = row.get("encrypted_api_key")

        if not provider or not encrypted_api_key:
            return None

        api_key = decrypt(encrypted_api_key)
        return await _scan_service.generate_ai_description(content, provider, api_key)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "document_service: AI description generation failed for workspace %s: %s",
            workspace_id,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_document(
    supabase,
    workspace_id: str,
    title: str,
    content: str | None,
    doc_type: str,
    source: str,
    external_id: str | None = None,
    external_link: str | None = None,
    original_filename: str | None = None,
    file_size: int | None = None,
    metadata: dict | None = None,
) -> dict:
    """Insert a new document row into teemo_documents and return the created row.

    Computes a SHA-256 content hash, attempts AI description generation via the
    workspace BYOK key (sets None on failure), then inserts with sync_status='pending'.

    The 15-document cap is enforced by the DB BEFORE INSERT trigger — if the workspace
    already has 15 documents the Supabase client will raise an exception.

    Args:
        supabase:          Authenticated Supabase client.
        workspace_id:      UUID of the owning workspace.
        title:             Document title (max 512 chars).
        content:           Full text content (may be None for stub rows).
        doc_type:          One of: pdf, docx, xlsx, text, markdown,
                           google_doc, google_sheet, google_slides.
        source:            One of: google_drive, upload, agent.
        external_id:       Google Drive file ID (None for upload/agent).
        external_link:     Drive webViewLink (None for upload/agent).
        original_filename: Original filename for uploads (None for Drive/agent).
        file_size:         Original file size in bytes (None for agent).
        metadata:          Arbitrary JSONB metadata dict (defaults to {}).

    Returns:
        The created row as a plain dict (as returned by Supabase).

    Raises:
        Exception: Any Supabase error, including the DB trigger exception when
                   the 15-document cap is reached.
    """
    content_hash: str | None = compute_content_hash(content) if content else None
    ai_description: str | None = (
        await _resolve_ai_description(supabase, workspace_id, content)
        if content
        else None
    )

    payload: dict = {
        "workspace_id": workspace_id,
        "title": title,
        "content": content,
        "ai_description": ai_description,
        "doc_type": doc_type,
        "source": source,
        "sync_status": "pending",
        "content_hash": content_hash,
        "metadata": metadata if metadata is not None else {},
    }

    if external_id is not None:
        payload["external_id"] = external_id
    if external_link is not None:
        payload["external_link"] = external_link
    if original_filename is not None:
        payload["original_filename"] = original_filename
    if file_size is not None:
        payload["file_size"] = file_size

    # created_at and updated_at are managed by DB defaults — omit them.
    result = supabase.table("teemo_documents").insert(payload).execute()
    return result.data[0]


async def read_document_content(
    supabase,
    workspace_id: str,
    document_id: str,
) -> str | None:
    """Return the raw text content of a document, enforcing workspace isolation.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the requesting workspace (isolation guard).
        document_id:  UUID of the target document.

    Returns:
        The ``content`` column value, or None if the document does not exist
        or does not belong to the given workspace.
    """
    result = (
        supabase.table("teemo_documents")
        .select("content")
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        return None
    return result.data.get("content")


async def update_document(
    supabase,
    workspace_id: str,
    document_id: str,
    content: str | None = None,
    title: str | None = None,
) -> dict:
    """Update a document row, recomputing hash and AI description if content changed.

    Resets sync_status to 'pending' so the EPIC-013 wiki pipeline re-ingests
    the document after any update.

    Workspace isolation: the update is scoped to ``workspace_id`` — documents
    from other workspaces are never touched.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace.
        document_id:  UUID of the document to update.
        content:      New text content, or None to leave unchanged.
        title:        New title, or None to leave unchanged.

    Returns:
        The updated row as a plain dict.

    Raises:
        Exception: Any Supabase error. Caller is responsible for 404 handling
                   when the returned list is empty.
    """
    payload: dict = {
        "sync_status": "pending",
    }

    if title is not None:
        payload["title"] = title

    if content is not None:
        payload["content"] = content
        payload["content_hash"] = compute_content_hash(content)
        payload["ai_description"] = await _resolve_ai_description(
            supabase, workspace_id, content
        )

    # updated_at is managed by the DB trigger — omit from payload.
    result = (
        supabase.table("teemo_documents")
        .update(payload)
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    return result.data[0]


async def delete_document(
    supabase,
    workspace_id: str,
    document_id: str,
) -> bool:
    """Delete a document row, cascade-delete associated wiki pages, and return True if deleted.

    After deleting the ``teemo_documents`` row, performs a best-effort cascade
    delete of all wiki pages in ``teemo_wiki_pages`` where ``source_document_ids``
    contains the document UUID (using Supabase ``.cs()`` array-contains filter).
    The wiki page cleanup is non-blocking — if it fails, the document delete
    still returns True.

    Workspace isolation: the delete is scoped to ``workspace_id``.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace.
        document_id:  UUID of the document to delete.

    Returns:
        True if a document row was deleted, False if no matching row was found.
    """
    result = (
        supabase.table("teemo_documents")
        .delete()
        .eq("id", document_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )
    deleted = bool(result.data)

    if deleted:
        # Best-effort cascade: delete wiki pages associated with this document.
        # Uses .cs() (array-contains) because source_document_ids is a UUID array.
        # Failure must NOT propagate — the document row is already gone and the
        # caller should not receive an error for the cleanup side effect.
        try:
            (
                supabase.table("teemo_wiki_pages")
                .delete()
                .eq("workspace_id", workspace_id)
                .cs("source_document_ids", [document_id])
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "document_service: wiki page cascade delete failed for document %s: %s",
                document_id,
                exc,
            )

    return deleted


async def list_documents(
    supabase,
    workspace_id: str,
) -> list[dict]:
    """Return all documents for a workspace ordered by created_at DESC.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the workspace.

    Returns:
        List of document row dicts, newest first. Empty list if none exist.
    """
    result = (
        supabase.table("teemo_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []
