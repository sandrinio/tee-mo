"""Knowledge Index CRUD routes (STORY-006-03).

Provides four endpoints for managing the knowledge index for a workspace:
  POST   /api/workspaces/{workspace_id}/knowledge              — index a Drive file
  GET    /api/workspaces/{workspace_id}/knowledge              — list all indexed files
  DELETE /api/workspaces/{workspace_id}/knowledge/{kid}        — remove a file from the index
  GET    /api/workspaces/{workspace_id}/drive/picker-token     — mint a Google Picker access token

ADR compliance:
  - ADR-005: Drive content read at index time (real-time, not cached).
  - ADR-006: AI description generated at index time, stored in DB, re-generated on hash change.
  - ADR-007: 15-file hard cap enforced at the route level.
  - ADR-016: Supported MIME types list — only 6 types accepted.
  - ADR-002/009: Refresh token encrypted, never logged; access tokens are transient.

Import notes (FLASHCARDS.md):
  - ``import httpx`` at module level so tests can monkeypatch httpx.AsyncClient.
  - ``import app.core.db as _db`` (module import, not ``from ... import``) so
    ``monkeypatch.setattr("app.core.db.get_supabase", ...)`` takes effect correctly.
  - ``import app.services.drive_service as _drive_service`` and
    ``import app.services.scan_service as _scan_service`` similarly so tests can patch
    individual functions on the module object.
"""

import asyncio
import logging
import uuid

import httpx  # MUST be at module level — tests monkeypatch httpx.AsyncClient (FLASHCARDS.md)

from fastapi import APIRouter, Depends, HTTPException

import app.core.db as _db  # module import so monkeypatch works (FLASHCARDS.md)
import app.services.drive_service as _drive_service  # module import for monkeypatching
import app.services.scan_service as _scan_service  # module import for monkeypatching
from app.api.deps import get_current_user_id
from app.core.config import get_settings
import app.core.encryption as _enc  # module import so monkeypatch works
from app.models.knowledge import IndexFileRequest

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
    """Index a Google Drive file into the workspace knowledge store.

    Workflow:
      1. Assert workspace ownership (404 if not owner).
      2. Check Drive connection (encrypted refresh token) — 400 if missing.
      3. Check BYOK API key — 400 if missing.
      4. Validate MIME type against ADR-016 allowed set — 400 if unsupported.
      5. Acquire per-workspace asyncio.Lock (R8: sequential indexing).
      6. Count existing files — 400 if >= 15 (ADR-007 hard cap).
      7. Check for duplicate drive_file_id — 409 if already indexed.
      8. Fetch file content from Drive (get_drive_client + fetch_file_content).
      9. Compute content hash (compute_content_hash).
      10. Generate AI description (generate_ai_description with BYOK key).
      11. Insert row into teemo_knowledge_index.
      12. Add truncation warning to response if content was truncated.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        payload: Request body containing drive_file_id, title, link, mime_type.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        The newly created knowledge index row as a dict, with an optional
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
        # Step 6: 15-file cap check (ADR-007) — inside lock to prevent TOCTOU
        count_result = (
            _db.get_supabase()
            .table("teemo_knowledge_index")
            .select("id", count="exact")
            .eq("workspace_id", workspace_id)
            .execute()
        )
        current_count = count_result.count or 0
        if current_count >= 15:
            raise HTTPException(
                status_code=400,
                detail="Maximum 15 files per workspace. Remove a file before adding another.",
            )

        # Step 7: Duplicate check
        dup_result = (
            _db.get_supabase()
            .table("teemo_knowledge_index")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("drive_file_id", payload.drive_file_id)
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

        # Step 9: Compute content hash for change-detection (ADR-006)
        content_hash = _drive_service.compute_content_hash(content)

        # Step 10: Generate AI description with BYOK key (ADR-004/006)
        provider = workspace.get("ai_provider", "anthropic")
        api_key_plaintext = _enc.decrypt(encrypted_api_key)
        ai_description = await _scan_service.generate_ai_description(
            content, provider, api_key_plaintext
        )

        # Step 11: Insert into teemo_knowledge_index
        new_id = str(uuid.uuid4())
        row = {
            "id": new_id,
            "workspace_id": workspace_id,
            "drive_file_id": payload.drive_file_id,
            "title": payload.title,
            "link": payload.link,
            "mime_type": payload.mime_type,
            "ai_description": ai_description,
            "content_hash": content_hash,
        }
        insert_result = (
            _db.get_supabase()
            .table("teemo_knowledge_index")
            .insert(row)
            .execute()
        )

        response_row = insert_result.data[0] if insert_result.data else row

    # Step 12: Add truncation warning if content was truncated by drive_service
    # drive_service._TRUNCATION_NOTICE is appended when content > 50,000 chars (ADR-016).
    if "[Content truncated" in content:
        response_row = dict(response_row)
        response_row["warning"] = (
            "File content was truncated at 50,000 characters. "
            "The AI description and search are based on the first 50,000 characters only."
        )

    return response_row


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/knowledge — list indexed files
# ---------------------------------------------------------------------------


@router.get("/api/workspaces/{workspace_id}/knowledge")
async def list_knowledge(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list:
    """Return all indexed files for a workspace, ordered by created_at descending.

    Args:
        workspace_id: Path parameter — target workspace UUID.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        List of knowledge index row dicts, newest first. Empty list if none indexed.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
    """
    await _assert_workspace_owner(workspace_id, user_id)

    result = (
        _db.get_supabase()
        .table("teemo_knowledge_index")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/knowledge/{knowledge_id}
# ---------------------------------------------------------------------------


@router.delete("/api/workspaces/{workspace_id}/knowledge/{knowledge_id}")
async def delete_knowledge(
    workspace_id: str,
    knowledge_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Remove a file from the workspace knowledge index.

    Deletes the row where both id=knowledge_id AND workspace_id=workspace_id
    so a user cannot delete files from workspaces they don't own (scoped delete).

    Args:
        workspace_id: Path parameter — owning workspace UUID.
        knowledge_id: Path parameter — knowledge index row UUID to delete.
        user_id: Injected by get_current_user_id; raises 401 if missing/invalid.

    Returns:
        JSON object ``{"status": "deleted"}``.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by user.
    """
    await _assert_workspace_owner(workspace_id, user_id)

    _db.get_supabase().table("teemo_knowledge_index").delete().eq(
        "id", knowledge_id
    ).eq("workspace_id", workspace_id).execute()

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
