"""
Wiki Ingest Cron — EPIC-013, STORY-013-03.

Background asyncio task that runs every 60 seconds and processes all
``teemo_documents`` rows where ``sync_status='pending'``. For each pending
document it resolves the workspace BYOK key and calls the wiki ingest pipeline.

Documents with ``sync_status='error'`` are NOT retried automatically — they
require a manual re-trigger (user re-indexes or content is updated, which resets
the status back to ``'pending'``).

Logic per cycle:
  1. Query ``teemo_documents`` for rows where ``sync_status='pending'``.
  2. For each pending document:
     a. Resolve the workspace BYOK key (query teemo_workspaces, decrypt).
     b. Check if wiki pages already exist for this document.
        - If YES  → call ``wiki_service.reingest_document()`` (destructive re-ingest).
        - If NO   → call ``wiki_service.ingest_document()`` (first ingest).
     c. On success: ``sync_status`` is already set to ``'synced'`` by wiki_service.
     d. On failure: set ``sync_status='error'``, log, and continue to the next doc.
  3. Sleep 60 seconds, then repeat.

Error handling:
  - Per-document errors are caught, logged, and skipped.
  - ``asyncio.CancelledError`` is NOT caught in the inner loop — it propagates so
    the task can be cleanly shut down by FastAPI's lifespan context manager.

Structured log events emitted (R4):
  ``cron.wiki_ingest.start``              — beginning of a full cycle
  ``cron.wiki_ingest.document_processed`` — a document was successfully ingested
  ``cron.wiki_ingest.error``              — a document failed to ingest
  ``cron.wiki_ingest.complete``           — end of a full cycle (with counts)

Usage::

    from app.services.wiki_ingest_cron import wiki_ingest_loop
    task = asyncio.create_task(wiki_ingest_loop())
"""

from __future__ import annotations

import asyncio
import logging

from app.core.db import get_supabase
from app.services import wiki_service

logger = logging.getLogger(__name__)


async def _resolve_workspace_key(supabase, workspace_id: str) -> tuple[str, str] | None:
    """Resolve the BYOK provider and decrypted API key for a workspace.

    Queries ``teemo_workspaces`` for the given workspace ID, retrieves
    ``ai_provider`` and ``encrypted_api_key``, and decrypts the key.

    ``decrypt`` is imported lazily inside this function (not at module level)
    because ``app.core.encryption`` loads ``app.core.config`` which requires
    environment variables. Tests inject a fake ``app.core.encryption`` module
    via ``sys.modules`` / monkeypatching before calling this function so the
    inline import resolves to the mock without triggering a Settings validation
    error. (Same pattern as ``document_service._resolve_ai_description``.)

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID string of the workspace whose BYOK key to resolve.

    Returns:
        Tuple of ``(provider, plaintext_api_key)`` on success, or None if the
        workspace row is missing, has no API key, or decryption fails.
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
        return (provider, api_key)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cron.wiki_ingest.key_resolve_failed",
            extra={
                "event": "cron.wiki_ingest.key_resolve_failed",
                "workspace_id": workspace_id,
                "error": str(exc),
            },
        )
        return None


def _has_existing_wiki_pages(supabase, workspace_id: str, document_id: str) -> bool:
    """Check whether wiki pages already exist for a given document.

    Queries ``teemo_wiki_pages`` for any row where ``source_document_ids``
    contains the document UUID. Used to decide between ``ingest_document``
    (first-time) vs ``reingest_document`` (update).

    Uses the Supabase ``.cs()`` (array-contains) filter — same pattern used in
    ``wiki_service.reingest_document``.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace (for workspace isolation).
        document_id:  UUID of the document whose pages to check.

    Returns:
        True if at least one wiki page exists for this document, False otherwise.
    """
    result = (
        supabase.table("teemo_wiki_pages")
        .select("*")
        .eq("workspace_id", workspace_id)
        .cs("source_document_ids", [document_id])
        .limit(1)
        .execute()
    )
    return bool(result.data)


async def _process_document(supabase, doc_row: dict) -> None:
    """Process a single pending document through the wiki ingest pipeline.

    Resolves the workspace BYOK key, checks for existing wiki pages, and
    calls the appropriate wiki_service function (ingest or reingest).

    On success, ``sync_status`` is set to ``'synced'`` by wiki_service.
    On failure (BYOK key unavailable, or wiki_service raises), sets
    ``sync_status='error'`` and re-raises so the caller can log and continue.

    Args:
        supabase: Authenticated Supabase client.
        doc_row:  Row dict from ``teemo_documents`` with at least ``id``
                  and ``workspace_id`` fields.

    Raises:
        Exception: Any error from BYOK resolution or wiki_service call.
    """
    document_id: str = doc_row["id"]
    workspace_id: str = doc_row["workspace_id"]

    key_result = await _resolve_workspace_key(supabase, workspace_id)
    if key_result is None:
        raise RuntimeError(
            f"Could not resolve BYOK key for workspace {workspace_id} "
            f"(document {document_id})"
        )

    provider, api_key = key_result
    has_pages = _has_existing_wiki_pages(supabase, workspace_id, document_id)

    if has_pages:
        await wiki_service.reingest_document(
            supabase, workspace_id, document_id, provider, api_key
        )
    else:
        await wiki_service.ingest_document(
            supabase, workspace_id, document_id, provider, api_key
        )


async def wiki_ingest_loop() -> None:
    """Infinite loop that processes pending wiki ingest documents every 60 seconds.

    Registered as an asyncio background task during FastAPI lifespan startup.
    Catches ``asyncio.CancelledError`` only to log shutdown — then re-raises so
    the event loop can cleanly terminate the task on application shutdown.

    Per-document errors are caught and logged; one failing document never
    prevents other documents from being processed.

    Loop behaviour:
      1. Emit ``cron.wiki_ingest.start`` log.
      2. Query ``teemo_documents`` for ``sync_status='pending'`` rows (all workspaces).
      3. Process each document via :func:`_process_document`.
         - On success: log ``cron.wiki_ingest.document_processed``.
         - On failure: set ``sync_status='error'``, log ``cron.wiki_ingest.error``,
           continue to next document.
      4. Emit ``cron.wiki_ingest.complete`` log with counts.
      5. Sleep 60 seconds, then repeat.

    Note: unlike the Drive sync cron, the sleep occurs AFTER the processing cycle
    rather than before, so the first run executes immediately on startup. This is
    appropriate because documents may already be pending when the service starts.
    """
    logger.info(
        "cron.wiki_ingest.init",
        extra={"event": "cron.wiki_ingest.init", "detail": "Wiki ingest cron task started"},
    )

    while True:
        try:
            logger.info(
                "cron.wiki_ingest.start",
                extra={"event": "cron.wiki_ingest.start"},
            )

            supabase = get_supabase()

            # Query all documents with sync_status='pending' across all workspaces.
            pending_result = (
                supabase.table("teemo_documents")
                .select("*")
                .eq("sync_status", "pending")
                .execute()
            )
            pending_docs: list[dict] = pending_result.data or []

            processed = 0
            errors = 0

            for doc_row in pending_docs:
                document_id: str = doc_row.get("id", "unknown")
                workspace_id: str = doc_row.get("workspace_id", "unknown")
                try:
                    await _process_document(supabase, doc_row)
                    processed += 1
                    logger.info(
                        "cron.wiki_ingest.document_processed",
                        extra={
                            "event": "cron.wiki_ingest.document_processed",
                            "document_id": document_id,
                            "workspace_id": workspace_id,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    logger.error(
                        "cron.wiki_ingest.error",
                        extra={
                            "event": "cron.wiki_ingest.error",
                            "document_id": document_id,
                            "workspace_id": workspace_id,
                            "error": str(exc),
                        },
                    )
                    # Best-effort: mark the document as errored so it doesn't
                    # get picked up in the next cycle (R5 — skip error docs).
                    try:
                        supabase.table("teemo_documents").update(
                            {"sync_status": "error"}
                        ).eq("id", document_id).eq("workspace_id", workspace_id).execute()
                    except Exception:  # noqa: BLE001
                        pass  # DB error on status update must not crash the cron

            logger.info(
                "cron.wiki_ingest.complete",
                extra={
                    "event": "cron.wiki_ingest.complete",
                    "documents_processed": processed,
                    "documents_errored": errors,
                    "documents_total": len(pending_docs),
                },
            )

            # Sleep between cycles — 60 seconds is more responsive than Drive
            # sync (documents are already local, no external API quota concerns).
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info(
                "cron.wiki_ingest.shutdown",
                extra={
                    "event": "cron.wiki_ingest.shutdown",
                    "message": "Wiki ingest cron task cancelled",
                },
            )
            raise
        except Exception as exc:  # noqa: BLE001
            # Catch-all for unexpected top-level errors — log and continue the loop.
            logger.exception(
                "cron.wiki_ingest.loop_error",
                extra={
                    "event": "cron.wiki_ingest.loop_error",
                    "error": str(exc),
                },
            )
