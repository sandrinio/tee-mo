"""Knowledge document CRUD routes (STORY-015-02 refactor of STORY-006-03).

Provides endpoints for managing the knowledge store for a workspace.
All document CRUD now goes through ``document_service`` which writes to
``teemo_documents``. The legacy ``teemo_knowledge_index`` table is gone.

Endpoints:
  POST   /api/workspaces/{workspace_id}/knowledge              — index a Drive file
  GET    /api/workspaces/{workspace_id}/knowledge              — list all documents
  DELETE /api/workspaces/{workspace_id}/knowledge/{kid}        — remove a document
  GET    /api/workspaces/{workspace_id}/drive/picker-token     — mint a Picker access token
  POST   /api/workspaces/{workspace_id}/knowledge/reindex      — re-index Drive documents
  POST   /api/workspaces/{workspace_id}/documents              — create an agent/upload document

ADR compliance:
  - ADR-005: Drive content read at index time (real-time, not cached).
  - ADR-006: AI description generated at index time, stored in DB, re-generated on hash change.
  - ADR-007: 15-document hard cap enforced at the route level (count check) and DB trigger.
  - ADR-016: Supported MIME types list — only 6 types accepted.
  - ADR-002/009: Refresh token encrypted, never logged; access tokens are transient.

Import notes (FLASHCARDS.md):
  - ``import httpx`` at module level so tests can monkeypatch httpx.AsyncClient.
  - ``import app.core.db as _db`` (module import, not ``from ... import``) so
    ``monkeypatch.setattr("app.core.db.get_supabase", ...)`` takes effect correctly.
  - ``import app.services.drive_service as _drive_service`` and
    ``import app.services.scan_service as _scan_service`` similarly so tests can patch
    individual functions on the module object.
  - ``import app.services.document_service as _document_service`` for the same reason.
  - SHA-256 is used for content hashing (sprint-context rule; document_service.compute_content_hash).
"""

import asyncio
import inspect
import logging

import httpx  # MUST be at module level — tests monkeypatch httpx.AsyncClient (FLASHCARDS.md)

from fastapi import APIRouter, Depends, HTTPException

import app.core.db as _db  # module import so monkeypatch works (FLASHCARDS.md)
import app.services.drive_service as _drive_service  # module import for monkeypatching
import app.services.document_service as _document_service  # module import for monkeypatching
import app.services.scan_service as _scan_service  # module import for monkeypatching
from app.api.deps import get_current_user_id
from app.core.config import get_settings
import app.core.encryption as _enc  # module import so monkeypatch works
from app.models.knowledge import CreateDocumentRequest, IndexFileRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["knowledge"])

# ---------------------------------------------------------------------------
# ADR-016: Supported MIME types for knowledge indexing
# ---------------------------------------------------------------------------

ALLOWED_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# ---------------------------------------------------------------------------
# R2: MIME type → doc_type mapping (ADR-016)
# Maps Google/Office MIME types to the doc_type enum values in teemo_documents.
# ---------------------------------------------------------------------------

MIME_TO_DOC_TYPE: dict[str, str] = {
    "application/vnd.google-apps.document": "google_doc",
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.google-apps.spreadsheet": "google_sheet",
    "application/vnd.google-apps.presentation": "google_slides",
}

# ---------------------------------------------------------------------------
# R8: Per-workspace asyncio.Lock store for sequential indexing
# Prevents race conditions where two concurrent requests for the same workspace
# could both pass the 15-file cap check before either insert completes.
# ---------------------------------------------------------------------------

_workspace_locks: dict[str, asyncio.Lock] = {}


def _get_workspace_lock(workspace_id: str) -> asyncio.Lock:
    """Return the asyncio.Lock for the given workspace_id, creating it if needed.

    Thread-local dict access is safe in the asyncio single-thread model.
    One lock per workspace ensures sequential indexing within a workspace (R8).

    Args:
        workspace_id: The workspace UUID to get a lock for.

    Returns:
        asyncio.Lock for this workspace.
    """
    if workspace_id not in _workspace_locks:
        _workspace_locks[workspace_id] = asyncio.Lock()
    return _workspace_locks[workspace_id]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _assert_workspace_owner(workspace_id: str, user_id: str) -> dict:
    """Verify the authenticated user owns the given workspace.

    Queries ``teemo_workspaces`` for a row matching both ``id`` and
    ``user_id``. Returns 404 (not 403) on mismatch to avoid leaking
    whether a workspace exists for another user (IDOR protection).

    The workspace row is returned because it contains the encrypted refresh
    token and encrypted API key needed by downstream route logic.

    Args:
        workspace_id: The workspace UUID to verify.
        user_id: The authenticated user's UUID (from JWT/cookie).

    Returns:
        The workspace row dict from Supabase.

    Raises:
        HTTPException(404): If the workspace is not found or belongs to another user.
    """
    result = (
        _db.get_supabase()
        .table("teemo_workspaces")
        .select("id, user_id, encrypted_google_refresh_token, encrypted_api_key, ai_provider")
        .eq("id", workspace_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return result.data[0]


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/knowledge — index a Drive file
# ---------------------------------------------------------------------------


@router.post("/api/workspaces/{workspace_id}/knowledge")
async def index_file(
    workspace_id: str,
    payload: IndexFileRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Index a Google Drive file into the workspace knowledge store (teemo_documents).

    Workflow:
      1. Assert workspace ownership (404 if not owner).
      2. Check Drive connection (encrypted refresh token) — 400 if missing.
      3. Check BYOK API key — 400 if missing.
      4. Validate MIME type against ADR-016 allowed set — 400 if unsupported.
      5. Acquire per-workspace asyncio.Lock (R8: sequential indexing queue).
      6. Count existing documents — 400 if >= 15 (ADR-007 hard cap).
      7. Check for duplicate external_id (drive_file_id) — 409 if already indexed.
      8. Fetch file content from Drive (get_drive_client + fetch_file_content).
      9. Call document_service.create_document with source='google_drive' and mapped doc_type.
         (document_service handles SHA-256 hash + AI description internally.)
      10. Add truncation warning to response if content was truncated.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        payload: Request body containing drive_file_id, title, link, mime_type.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        The newly created document row as a dict, with an optional
        ``warning`` field if the file content was truncated.

    Raises:
        HTTPException(400): Drive not connected, BYOK key missing, unsupported MIME,
            or file cap exceeded.
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
        HTTPException(409): File with same drive_file_id already indexed.
    """
    logger.info("index_file payload: %s", payload.model_dump())
    workspace = await _assert_workspace_owner(workspace_id, user_id)

    # Step 2: Drive connection check
    encrypted_refresh_token = workspace.get("encrypted_google_refresh_token")
    if not encrypted_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    # Step 3: BYOK key check
    encrypted_api_key = workspace.get("encrypted_api_key")
    if not encrypted_api_key:
        raise HTTPException(status_code=400, detail="BYOK key required to index files")

    # Step 4: MIME type validation (ADR-016)
    if payload.mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {payload.mime_type!r}. "
                   f"Supported MIME types: {sorted(ALLOWED_MIME_TYPES)}",
        )

    # Step 5: Acquire workspace lock (R8: sequential indexing queue)
    lock = _get_workspace_lock(workspace_id)
    async with lock:
        supabase = _db.get_supabase()

        # Step 6: 15-document cap check (ADR-007) — inside lock to prevent TOCTOU
        count_result = (
            supabase
            .table("teemo_documents")
            .select("*", count="exact")
            .eq("workspace_id", workspace_id)
            .execute()
        )
        current_count = count_result.count or 0
        if current_count >= 15:
            raise HTTPException(
                status_code=400,
                detail="Maximum 15 files per workspace. Remove a file before adding another.",
            )

        # Step 7: Duplicate check — look for an existing document with the same external_id
        dup_result = (
            supabase
            .table("teemo_documents")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("external_id", payload.drive_file_id)
            .limit(1)
            .execute()
        )
        if dup_result.data:
            raise HTTPException(status_code=409, detail="File already indexed in this workspace")

        # Step 8: Fetch file content from Drive
        # If the frontend passed an access_token (from the Picker session), use it
        # directly — drive.file scope ties file access to the Picker token, not the
        # refresh token. Otherwise fall back to the stored refresh token.
        logger.info("index_file: access_token present=%s", bool(payload.access_token))
        if payload.access_token:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build as _build_drive
            creds = Credentials(token=payload.access_token)
            drive_client = _build_drive("drive", "v3", credentials=creds)
        else:
            drive_client = _drive_service.get_drive_client(encrypted_refresh_token)
        _fetch = _drive_service.fetch_file_content
        if asyncio.iscoroutinefunction(_fetch):
            content = await _fetch(drive_client, payload.drive_file_id, payload.mime_type)
        else:
            content = await asyncio.to_thread(
                _fetch, drive_client, payload.drive_file_id, payload.mime_type
            )

        # step 9: Map MIME type to doc_type and create document via document_service.
        # document_service handles SHA-256 hash + AI description generation internally.
        doc_type = MIME_TO_DOC_TYPE.get(payload.mime_type, "pdf")
        response_row = await _document_service.create_document(
            supabase=supabase,
            workspace_id=workspace_id,
            title=payload.title,
            content=content,
            doc_type=doc_type,
            source="google_drive",
            external_id=payload.drive_file_id,
            external_link=payload.link,
            metadata={"mime_type": payload.mime_type},
        )

    # Step 10: Add truncation warning if content was truncated by drive_service
    # drive_service._TRUNCATION_NOTICE is appended when content > 50,000 chars (ADR-016).
    if "[Content truncated" in content:
        response_row = dict(response_row)
        response_row["warning"] = (
            "File content was truncated at 50,000 characters. "
            "The AI description and search are based on the first 50,000 characters only."
        )

    return response_row


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/knowledge — list documents
# ---------------------------------------------------------------------------


@router.get("/api/workspaces/{workspace_id}/knowledge")
async def list_knowledge(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list:
    """Return all documents for a workspace, ordered by created_at descending.

    Delegates to document_service.list_documents which queries teemo_documents.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        List of document row dicts, newest first. Empty list if none exist.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
    """
    await _assert_workspace_owner(workspace_id, user_id)
    return await _document_service.list_documents(_db.get_supabase(), workspace_id)


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/knowledge/{knowledge_id}
# ---------------------------------------------------------------------------


@router.delete("/api/workspaces/{workspace_id}/knowledge/{knowledge_id}")
async def delete_knowledge(
    workspace_id: str,
    knowledge_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Remove a document from the workspace knowledge store.

    The knowledge_id path parameter is the document UUID (``teemo_documents.id``).
    Delegates to document_service.delete_document for workspace-scoped deletion.

    Args:
        workspace_id: Path parameter — owning workspace UUID.
        knowledge_id: Path parameter — document UUID to delete.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        JSON object ``{"status": "deleted"}``.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
    """
    await _assert_workspace_owner(workspace_id, user_id)
    await _document_service.delete_document(_db.get_supabase(), workspace_id, knowledge_id)
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/drive/picker-token
# ---------------------------------------------------------------------------


@router.get("/api/workspaces/{workspace_id}/drive/picker-token")
async def get_picker_token(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Mint a short-lived Google Picker access token for the workspace.

    The Google Drive Picker widget requires an OAuth access token scoped to
    the user's account. This endpoint exchanges the stored refresh token for
    a transient access token via Google's token endpoint.

    ADR-009: The access token is NOT stored — it is only returned to the
    caller for immediate use in the Picker widget. Only the offline refresh
    token is persisted in the database.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        JSON object with:
          - ``access_token``: Short-lived Google OAuth access token for the Picker.
          - ``picker_api_key``: Google Picker API key from settings.

    Raises:
        HTTPException(400): Google Drive not connected (no refresh token stored).
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
        HTTPException(502): Token exchange with Google failed.
    """
    workspace = await _assert_workspace_owner(workspace_id, user_id)

    encrypted_refresh_token = workspace.get("encrypted_google_refresh_token")
    if not encrypted_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    # Decrypt the stored refresh token (ADR-002/009 — never log the plaintext)
    refresh_token = _enc.decrypt(encrypted_refresh_token)

    # Exchange the refresh token for a transient access token.
    # The access token is NOT stored — ADR-009: only the offline refresh token is persisted.
    s = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": s.google_api_client_id,
                "client_secret": s.google_api_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    token_data = resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        logger.warning(
            "get_picker_token: Google token exchange returned no access_token "
            "(workspace_id=%s)",
            workspace_id,
        )
        raise HTTPException(status_code=502, detail="Failed to obtain access token from Google")

    return {
        "access_token": access_token,
        "picker_api_key": s.google_picker_api_key,
    }


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/knowledge/reindex — re-extract Drive docs
# ---------------------------------------------------------------------------


@router.post("/api/workspaces/{workspace_id}/knowledge/reindex")
async def reindex_knowledge(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Re-extract content and regenerate AI descriptions for Google Drive documents.

    Only processes documents with ``source='google_drive'``. Documents with
    ``source='upload'`` or ``source='agent'`` are untouched — they have no
    corresponding Drive file to re-fetch.

    Iterates all google_drive documents for the workspace, re-fetches each file
    from Google Drive, recomputes the SHA-256 content hash, regenerates the AI
    description, and updates the row via document_service.update_document.

    Per-file errors are caught and collected in the ``errors`` list so a single
    failing file does not abort the entire re-index run.

    Gate conditions (returns HTTP 400):
      - No BYOK key stored for the workspace.
      - No Google Drive OAuth token stored for the workspace.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        JSON object with:
          - ``reindexed``: Number of files successfully re-indexed.
          - ``skipped``: Number of files that were skipped (unchanged on Drive).
          - ``failed``: Number of files that failed during re-indexing.
          - ``errors``: List of ``{"file_id": str, "error": str}`` dicts for failures.

    Raises:
        HTTPException(400): No BYOK key or no Drive connected.
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
    """
    workspace = await _assert_workspace_owner(workspace_id, user_id)

    # Gate: BYOK key required
    encrypted_api_key = workspace.get("encrypted_api_key")
    if not encrypted_api_key:
        raise HTTPException(status_code=400, detail="BYOK key required to re-index files")

    # Gate: Drive must be connected
    encrypted_refresh_token = workspace.get("encrypted_google_refresh_token")
    if not encrypted_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    # Decrypt BYOK key once for all files
    provider = workspace.get("ai_provider", "anthropic")
    api_key_plaintext = _enc.decrypt(encrypted_api_key)

    # Build the Drive client once for all files
    drive_client = _drive_service.get_drive_client(encrypted_refresh_token)

    supabase = _db.get_supabase()

    # Fetch only Google Drive documents — skip upload/agent sources (R1/reindex spec)
    list_result = (
        supabase
        .table("teemo_documents")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("source", "google_drive")
        .execute()
    )
    file_rows = list_result.data or []

    reindexed = 0
    skipped = 0
    failed = 0
    errors: list[dict] = []

    for file_row in file_rows:
        file_id = file_row.get("external_id", "")
        doc_id = file_row.get("id", "")
        mime_type = file_row.get("metadata", {}).get("mime_type") or ""
        try:
            from datetime import datetime

            file_meta = drive_client.files().get(fileId=file_id, fields="modifiedTime").execute()
            drive_modified_time_str = file_meta.get("modifiedTime")
            stored_updated_at_str = file_row.get("updated_at")

            if drive_modified_time_str and stored_updated_at_str:
                # Drive returns RFC 3339 with 'Z' for UTC. Supabase returns ISO format.
                drive_dt = datetime.fromisoformat(drive_modified_time_str.replace("Z", "+00:00"))
                stored_dt = datetime.fromisoformat(stored_updated_at_str.replace("Z", "+00:00"))
                if drive_dt <= stored_dt:
                    skipped += 1
                    continue

            # Re-fetch content from Drive
            # fetch_file_content returns _AwaitableStr — use inspect.isawaitable to handle both
            # sync and async return values (FLASHCARDS.md / STORY-006-08 pattern).
            _result = _drive_service.fetch_file_content(
                drive_client,
                file_id,
                mime_type,
                provider=provider,
                api_key=api_key_plaintext,
            )
            content = (await _result) if inspect.isawaitable(_result) else _result

            # Update the document via document_service — recomputes SHA-256 hash and
            # regenerates AI description; resets sync_status to 'pending'.
            await _document_service.update_document(
                supabase=supabase,
                workspace_id=workspace_id,
                document_id=doc_id,
                content=content,
            )

            reindexed += 1

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "reindex_knowledge: failed to re-index file %s in workspace %s: %s",
                file_id,
                workspace_id,
                exc,
            )
            failed += 1
            errors.append({"file_id": file_id, "error": str(exc)})

    return {
        "reindexed": reindexed,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/documents — create an agent/upload document
# ---------------------------------------------------------------------------


@router.post("/api/workspaces/{workspace_id}/documents")
async def create_document(
    workspace_id: str,
    payload: CreateDocumentRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Create a document with source='agent' and doc_type='markdown'.

    Accepts a title and content body, creates a row in teemo_documents via
    document_service.create_document. Used by agent tools (STORY-015-03) and
    is also available as a public API endpoint for programmatic document creation.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        payload: Request body containing title and content.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        The created document row as a dict.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
        HTTPException(400): Document cap exceeded (DB trigger fires).
    """
    await _assert_workspace_owner(workspace_id, user_id)
    try:
        doc = await _document_service.create_document(
            supabase=_db.get_supabase(),
            workspace_id=workspace_id,
            title=payload.title,
            content=payload.content,
            doc_type="markdown",
            source="agent",
        )
    except Exception as exc:  # noqa: BLE001
        # DB trigger fires when cap is exceeded — surface as 400
        logger.warning(
            "create_document: failed for workspace %s: %s",
            workspace_id,
            exc,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return doc
