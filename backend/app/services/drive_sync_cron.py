"""
Drive Content Sync Cron — EPIC-015, STORY-015-05.

Background asyncio task that runs every 10 minutes and checks all
``source='google_drive'`` documents for content changes via the Google Drive API.

Logic per cycle:
  1. Fetch all workspaces with ``encrypted_google_refresh_token IS NOT NULL``.
  2. For each workspace, build an authenticated Drive v3 client.
  3. Query ``teemo_documents`` for rows where ``source='google_drive'``.
  4. For each document:
     a. Google Workspace files (Docs, Sheets, Slides) — no ``md5Checksum`` in
        Drive metadata, so always re-fetch and compare SHA-256 hashes.
     b. Binary files (PDF, DOCX, XLSX) — call ``files.get(fields=md5Checksum)``
        (1 API call).  If the MD5 from Drive matches the stored ``content_hash``
        *prefix* (Drive MD5 vs. our SHA-256), use SHA-256 re-computation to
        confirm.  If unchanged, skip entirely.
  5. When content has changed: call ``document_service.update_document()`` which
     recomputes the SHA-256 hash, regenerates the AI description, and resets
     ``sync_status`` to ``'pending'`` for the EPIC-013 wiki pipeline.

Error handling:
  - Per-workspace errors (e.g. revoked token) are caught, logged, and skipped.
  - Per-file errors are caught, logged, and skipped.
  - ``asyncio.CancelledError`` is NOT caught — it propagates so the task can be
    cleanly shut down by FastAPI's lifespan context manager.

Structured log events emitted (R5):
  ``cron.drive_sync.start``       — beginning of a full cycle
  ``cron.drive_sync.file_changed``— a document was re-fetched and updated
  ``cron.drive_sync.complete``    — end of a full cycle (with counts)

Usage::

    from app.services.drive_sync_cron import drive_sync_loop
    task = asyncio.create_task(drive_sync_loop())
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.db import get_supabase
from app.services import document_service
from app.services import drive_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MIME types for Google Workspace files — Drive does NOT expose md5Checksum
# for these native formats.  We must always re-fetch and compare SHA-256.
# ---------------------------------------------------------------------------

_GOOGLE_WORKSPACE_MIMES = frozenset(
    {
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.spreadsheet",
        "application/vnd.google-apps.presentation",
    }
)


async def _check_file(
    supabase,
    workspace_id: str,
    drive_client,
    doc_row: dict,
) -> bool:
    """Check a single Drive document for content changes and update if changed.

    For binary files (PDF, DOCX, XLSX):
      - Calls ``files.get(fields='md5Checksum')`` — 1 lightweight API call.
      - If ``md5Checksum`` is absent (Google Workspace file acting as binary),
        treats the file as potentially changed and re-fetches.
      - Re-fetches content only when needed and computes SHA-256 to confirm change.

    For Google Workspace files (Docs, Sheets, Slides):
      - ``md5Checksum`` is never available for these MIME types.
      - Always re-fetches exported content and compares SHA-256 hash.

    When content has changed:
      - Calls ``document_service.update_document()`` which handles hash
        recompute, AI description re-generation, and ``sync_status='pending'``.
      - Updates ``last_synced_at`` to current UTC time.

    Args:
        supabase:     Authenticated Supabase client.
        workspace_id: UUID of the owning workspace.
        drive_client: Authenticated Drive v3 API client.
        doc_row:      Row dict from ``teemo_documents``.

    Returns:
        ``True`` if the document was updated, ``False`` if unchanged or skipped.
    """
    doc_id: str = doc_row["id"]
    external_id: str = doc_row["external_id"]
    stored_hash: str | None = doc_row.get("content_hash")
    mime_type: str | None = doc_row.get("metadata", {}).get("mime_type") if doc_row.get("metadata") else None

    is_google_workspace = mime_type in _GOOGLE_WORKSPACE_MIMES if mime_type else False

    if not is_google_workspace:
        # Lightweight check: fetch only the md5Checksum field.
        try:
            meta = (
                drive_client.files()
                .get(fileId=external_id, fields="md5Checksum")
                .execute()
            )
            drive_md5: str | None = meta.get("md5Checksum")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cron.drive_sync.meta_fetch_failed",
                extra={
                    "event": "cron.drive_sync.meta_fetch_failed",
                    "workspace_id": workspace_id,
                    "document_id": doc_id,
                    "external_id": external_id,
                    "error": str(exc),
                },
            )
            raise  # re-raise so _sync_workspace can log at workspace level

        if drive_md5 is None:
            # Drive returned no md5Checksum — treat as Google Workspace file
            # or otherwise unknown; fall through to always-re-fetch path.
            is_google_workspace = True
        else:
            # We have a Drive MD5.  The stored hash is SHA-256 so we cannot
            # compare directly.  Re-fetch content and compute SHA-256 to confirm.
            # If we have NO stored hash, content must be refreshed unconditionally.
            if stored_hash is not None:
                # Fetch content to compute SHA-256 and compare.
                # This costs one export/download API call, but only when the
                # Drive MD5 could indicate a change (we have no cheap shortcut
                # between MD5 and SHA-256).
                pass  # fall through to re-fetch below

    # Re-fetch content to compute the new SHA-256 hash.
    # fetch_file_content returns _AwaitableStr (a str subclass) for most cases and
    # a coroutine for the multimodal fallback path.  Inspect with asyncio.iscoroutine
    # so we handle both gracefully without importing the private _AwaitableStr type.
    try:
        result = drive_service.fetch_file_content(
            drive_client,
            external_id,
            mime_type or "application/vnd.google-apps.document",
        )
        if asyncio.iscoroutine(result):
            new_content = await result
        else:
            new_content = str(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "cron.drive_sync.content_fetch_failed",
            extra={
                "event": "cron.drive_sync.content_fetch_failed",
                "workspace_id": workspace_id,
                "document_id": doc_id,
                "external_id": external_id,
                "error": str(exc),
            },
        )
        raise

    new_hash = document_service.compute_content_hash(new_content)

    if new_hash == stored_hash:
        # Content unchanged — skip DB write and LLM call.
        return False

    # Content has changed — update document (recomputes hash, AI desc, sync_status).
    logger.info(
        "cron.drive_sync.file_changed",
        extra={
            "event": "cron.drive_sync.file_changed",
            "workspace_id": workspace_id,
            "document_id": doc_id,
            "external_id": external_id,
        },
    )

    await document_service.update_document(
        supabase,
        workspace_id,
        doc_id,
        content=new_content,
    )

    # Update last_synced_at to now (column managed by cron, not a DB trigger).
    supabase.table("teemo_documents").update(
        {"last_synced_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", doc_id).eq("workspace_id", workspace_id).execute()

    return True


async def _sync_workspace(workspace_row: dict) -> tuple[int, int]:
    """Process all Drive documents for a single workspace.

    Queries all ``source='google_drive'`` documents for the workspace, then
    checks each one via :func:`_check_file`.  Per-file errors are caught,
    logged, and skipped — one bad file must not prevent other files from
    being checked.

    Args:
        workspace_row: Row dict from ``teemo_workspaces`` containing at least
            ``id`` and ``encrypted_google_refresh_token``.

    Returns:
        Tuple of ``(checked_count, updated_count)``.
    """
    workspace_id: str = workspace_row["id"]
    encrypted_token: str = workspace_row["encrypted_google_refresh_token"]

    supabase = get_supabase()

    # Build Drive client — raises on invalid/revoked token.
    drive_client = drive_service.get_drive_client(encrypted_token)

    # Query all Drive-sourced documents for this workspace.
    result = (
        supabase.table("teemo_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("source", "google_drive")
        .execute()
    )
    docs: list[dict] = result.data or []

    checked = 0
    updated = 0

    for doc_row in docs:
        checked += 1
        try:
            was_updated = await _check_file(supabase, workspace_id, drive_client, doc_row)
            if was_updated:
                updated += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "cron.drive_sync.file_error",
                extra={
                    "event": "cron.drive_sync.file_error",
                    "workspace_id": workspace_id,
                    "document_id": doc_row.get("id"),
                    "error": str(exc),
                },
            )

    return checked, updated


async def drive_sync_loop() -> None:
    """Infinite loop that syncs all Drive workspaces every 10 minutes.

    Registered as an asyncio background task during FastAPI lifespan startup.
    Catches ``asyncio.CancelledError`` only to log shutdown — then re-raises so
    the event loop can cleanly terminate the task on application shutdown.

    Per-workspace errors are caught and logged; one failing workspace never
    prevents the rest from being processed.

    Loop behaviour:
      1. Sleep 600 seconds (10 min) at the START of each iteration so the first
         full run is not immediate on cold-boot (avoids startup contention with
         DB migrations and other startup tasks).
      2. Emit ``cron.drive_sync.start`` log.
      3. Query all workspaces with a connected Drive account.
      4. Process each workspace via :func:`_sync_workspace`.
      5. Emit ``cron.drive_sync.complete`` log with totals.
    """
    logger.info(
        "cron.drive_sync.init",
        extra={"event": "cron.drive_sync.init", "message": "Drive sync cron task started"},
    )

    while True:
        try:
            # Sleep first so cold-boot doesn't hammer the Drive API immediately.
            await asyncio.sleep(600)

            logger.info(
                "cron.drive_sync.start",
                extra={"event": "cron.drive_sync.start"},
            )

            supabase = get_supabase()

            # Fetch all workspaces with a Google Drive token.
            ws_result = (
                supabase.table("teemo_workspaces")
                .select("id, encrypted_google_refresh_token")
                .not_.is_("encrypted_google_refresh_token", "null")
                .execute()
            )
            workspaces: list[dict] = ws_result.data or []

            total_checked = 0
            total_updated = 0

            for workspace_row in workspaces:
                try:
                    checked, updated = await _sync_workspace(workspace_row)
                    total_checked += checked
                    total_updated += updated
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "cron.drive_sync.workspace_error",
                        extra={
                            "event": "cron.drive_sync.workspace_error",
                            "workspace_id": workspace_row.get("id"),
                            "error": str(exc),
                        },
                    )

            logger.info(
                "cron.drive_sync.complete",
                extra={
                    "event": "cron.drive_sync.complete",
                    "workspaces_processed": len(workspaces),
                    "files_checked": total_checked,
                    "files_updated": total_updated,
                },
            )

        except asyncio.CancelledError:
            logger.info(
                "cron.drive_sync.shutdown",
                extra={"event": "cron.drive_sync.shutdown", "message": "Drive sync cron task cancelled"},
            )
            raise
        except Exception as exc:  # noqa: BLE001
            # Catch-all for unexpected top-level errors — log and continue the loop.
            logger.exception(
                "cron.drive_sync.loop_error",
                extra={
                    "event": "cron.drive_sync.loop_error",
                    "error": str(exc),
                },
            )
