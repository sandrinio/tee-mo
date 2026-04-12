"""Google Drive OAuth flow routes (STORY-006-02).

Provides four endpoints for the Drive OAuth connect / disconnect / status flow.
Follows the same structural pattern as ``slack_oauth.py`` — state JWT, httpx
at module level (FLASHCARDS.md rule), workspace ownership guard, and encrypted
token storage (ADR-002/009).

Routes:
  GET  /api/workspaces/{workspace_id}/drive/connect     — initiate OAuth, 307 to Google
  GET  /api/drive/oauth/callback                        — handle Google redirect
  GET  /api/workspaces/{workspace_id}/drive/status      — connected status + email
  POST /api/workspaces/{workspace_id}/drive/disconnect  — null the refresh token

ADR compliance:
  - ADR-002: Refresh token encrypted with AES-256-GCM (encrypt() called, decrypt() for status).
  - ADR-009: Only the offline refresh token is stored; access tokens are transient.
  - Drive scope ``drive.file`` only (non-sensitive) — not ``drive.readonly`` or broader.
  - Refresh token NEVER logged — ``logger.warning()`` calls omit token values.

Import note on get_supabase:
  ``app.core.db`` is imported as a module (not via ``from ... import get_supabase``) so that
  ``monkeypatch.setattr("app.core.db.get_supabase", ...)`` in unit tests correctly replaces the
  function that this module calls. A direct ``from app.core.db import get_supabase`` binds a
  local reference at import time that is not affected by module-level monkeypatching.
"""

import logging
import httpx  # MUST be at module level so tests can monkeypatch httpx.AsyncClient
import jwt    # needed for jwt.ExpiredSignatureError, jwt.InvalidTokenError in callback
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user_id
from app.core.config import get_settings
import app.core.db as _db  # module import — not `from ... import` — so monkeypatch works
from app.core.encryption import encrypt, decrypt
from app.core.security import create_drive_state_token, verify_drive_state_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["drive"])

# Google OAuth 2.0 scopes (ADR — drive.file only, non-sensitive).
# openid + email are needed so we can call the userinfo endpoint for status display.
DRIVE_SCOPES = "openid email https://www.googleapis.com/auth/drive.file"


async def _assert_workspace_owner(workspace_id: str, user_id: str) -> dict:
    """Verify the authenticated user owns the given workspace.

    Queries ``teemo_workspaces`` for a row with matching ``id`` AND
    ``owner_user_id``. If no row is found (workspace doesn't exist or belongs
    to another user), raises HTTPException(404) — a generic 404 avoids leaking
    whether a workspace exists for a different user (IDOR protection).

    Calls ``_db.get_supabase()`` at call time (not import time) so that
    ``monkeypatch.setattr("app.core.db.get_supabase", ...)`` in unit tests
    takes effect correctly.

    Args:
        workspace_id: The workspace UUID to look up.
        user_id:      The authenticated user's ID (from JWT/cookie).

    Returns:
        The workspace row dict from Supabase (includes ``encrypted_google_refresh_token``).

    Raises:
        HTTPException(404): If the workspace is not found or not owned by user_id.
    """
    result = (
        _db.get_supabase()
        .table("teemo_workspaces")
        .select("id, owner_user_id, encrypted_google_refresh_token")
        .eq("id", workspace_id)
        .eq("owner_user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="workspace not found")
    return result.data[0]


@router.get("/api/workspaces/{workspace_id}/drive/connect")
async def drive_connect(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> RedirectResponse:
    """Initiate the Google Drive OAuth consent flow.

    Verifies workspace ownership, builds the Google OAuth authorization URL,
    embeds a signed state JWT (audience ``"drive-connect"``) so the callback
    handler can associate the code with the correct user and workspace without
    server-side session state, and issues a 307 redirect.

    307 (Temporary Redirect) preserves the GET method — 302 is semantically
    incorrect for a GET-initiated OAuth flow.

    The ``state`` parameter is a short-lived (5 min) JWT signed with
    ``supabase_jwt_secret``. It embeds both ``user_id`` and ``workspace_id``.
    The token is NEVER logged.

    Args:
        workspace_id: Path parameter — the target workspace UUID.
        user_id:      Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns:
        307 RedirectResponse to Google's OAuth consent screen.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by the user.
    """
    await _assert_workspace_owner(workspace_id, user_id)

    s = get_settings()
    state = create_drive_state_token(user_id, workspace_id)
    qs = urlencode(
        {
            "client_id": s.google_api_client_id,
            "redirect_uri": s.google_oauth_redirect_uri,
            "scope": DRIVE_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "response_type": "code",
            "state": state,
        }
    )
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?{qs}",
        status_code=307,
    )


@router.get("/api/drive/oauth/callback")
async def drive_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle the Google OAuth redirect after user consent.

    5 redirect branches (no auth dependency — identity comes from the state JWT):
      - ``/app?drive_connect=cancelled``  — user clicked "Cancel" at Google consent
      - ``/app?drive_connect=expired``    — state JWT has expired (>5 min)
      - ``/app?drive_connect=error``      — Google API returned no refresh_token or other failure
      - ``/app?drive_connect=ok``         — success; refresh token encrypted and stored

    2 hard-fail branches (raise HTTPException, no redirect):
      - 400 — missing ``code`` or ``state``, or tampered state signature
      - 400 — invalid state token (audience wrong or signature invalid)

    Security constraints:
      - Refresh token NEVER logged in plaintext or ciphertext form (ADR-002/009).
      - Token exchange uses ``grant_type=authorization_code`` (not PKCE; server-side flow).

    Args:
        code:   Google OAuth authorization code (query param from Google).
        state:  Signed JWT state param (query param from Google).
        error:  Google error string e.g. ``"access_denied"`` (query param).

    Returns:
        302 RedirectResponse to the appropriate URL.

    Raises:
        HTTPException(400): Missing params or invalid/tampered state.
    """
    # --- 1. Cancellation branch — no API calls, no DB writes ---
    if error == "access_denied":
        return RedirectResponse("/app?drive_connect=cancelled", status_code=302)

    # --- 2. Required params ---
    if not state or not code:
        raise HTTPException(status_code=400, detail="missing code or state")

    # --- 3. State verification: expired vs tampered are distinct branches ---
    try:
        state_payload = verify_drive_state_token(state)
    except jwt.ExpiredSignatureError:
        return RedirectResponse("/app?drive_connect=expired", status_code=302)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="invalid state")

    # --- 4. Exchange auth code for tokens ---
    s = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": s.google_api_client_id,
                "client_secret": s.google_api_secret,
                "redirect_uri": s.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    token_payload = resp.json()

    # ADR-009: Only the refresh token is stored; access tokens are transient.
    # refresh_token may be absent if the user previously consented (no re-grant).
    # prompt=consent in the authorize URL forces issuance; if still absent → error.
    refresh_token = token_payload.get("refresh_token")
    if not refresh_token:
        logger.warning(
            "drive_oauth_callback: Google token response missing refresh_token "
            "(workspace_id=%s)", state_payload.workspace_id
        )
        return RedirectResponse("/app?drive_connect=error", status_code=302)

    # --- 5. Encrypt + store ---
    # NOTE: refresh_token is NEVER passed to logger — ADR-002/009 security constraint.
    # created_at is intentionally excluded from the payload so DEFAULT NOW() is
    # preserved across reconnects (FLASHCARDS.md Supabase upsert rule).
    encrypted_token = encrypt(refresh_token)
    _db.get_supabase().table("teemo_workspaces").update(
        {"encrypted_google_refresh_token": encrypted_token}
    ).eq("id", state_payload.workspace_id).execute()

    return RedirectResponse("/app?drive_connect=ok", status_code=302)


@router.get("/api/workspaces/{workspace_id}/drive/status")
async def drive_status(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Return the Google Drive connection status for a workspace.

    Checks whether ``encrypted_google_refresh_token`` is set on the workspace.
    If set, decrypts the stored refresh token and calls the Google userinfo
    endpoint to retrieve the connected email address. On any failure (revoked
    token, network error), returns ``connected: false`` without raising an
    exception — the frontend can then prompt the user to reconnect.

    Args:
        workspace_id: Path parameter — the target workspace UUID.
        user_id:      Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns:
        JSON object ``{"connected": bool, "email": str | null}``.
        ``email`` is the Google account email when connected, null otherwise.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by the user.
    """
    workspace = await _assert_workspace_owner(workspace_id, user_id)

    encrypted_token = workspace.get("encrypted_google_refresh_token")
    if not encrypted_token:
        return {"connected": False, "email": None}

    # Decrypt the stored refresh token and call userinfo to retrieve the email.
    # Any failure (revoked token, network error, missing email) → connected=false.
    # The refresh token is used as the bearer credential for the userinfo call;
    # the userinfo endpoint validates it server-side and returns the account info.
    try:
        refresh_token = decrypt(encrypted_token)

        async with httpx.AsyncClient(timeout=10.0) as client:
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {refresh_token}"},
            )
        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        if not email:
            return {"connected": False, "email": None}
        return {"connected": True, "email": email}

    except Exception:  # noqa: BLE001 — any failure → connected=false (reconnect prompt)
        logger.warning(
            "drive_status: failed to verify Drive connection for workspace_id=%s",
            workspace_id,
        )
        return {"connected": False, "email": None}


@router.post("/api/workspaces/{workspace_id}/drive/disconnect")
async def drive_disconnect(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Disconnect Google Drive for a workspace by nulling the stored refresh token.

    Verifies workspace ownership, then sets ``encrypted_google_refresh_token``
    to null in ``teemo_workspaces``. The workspace row is preserved — only the
    Drive credential is removed. The user can reconnect Drive at any time.

    Args:
        workspace_id: Path parameter — the target workspace UUID.
        user_id:      Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns:
        JSON object ``{"status": "disconnected"}``.

    Raises:
        HTTPException(401): No valid auth cookie/token.
        HTTPException(404): Workspace not found or not owned by the user.
    """
    await _assert_workspace_owner(workspace_id, user_id)

    _db.get_supabase().table("teemo_workspaces").update(
        {"encrypted_google_refresh_token": None}
    ).eq("id", workspace_id).execute()

    return {"status": "disconnected"}
