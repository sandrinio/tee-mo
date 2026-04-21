"""BYOK key management routes for the Tee-Mo API.

STORY-004-01: Backend Key Routes + Models + Validator

Implements 4 routes for workspace-scoped BYOK (Bring Your Own Key) management:

  POST /api/keys/validate                  — stateless probe of a provider key
  POST /api/workspaces/{workspace_id}/keys — encrypt + store key on workspace
  GET  /api/workspaces/{workspace_id}/keys — read key mask + provider metadata
  DELETE /api/workspaces/{workspace_id}/keys — NULL out stored key + provider

Security model:
- All routes require authentication via ``get_current_user_id``.
- All workspace-scoped routes verify ownership (``user_id`` filter on every query)
  before reading or writing. A non-owned workspace returns 404 — not 403 — to
  avoid confirming that the workspace ID exists for another user.
- Plaintext key is NEVER stored, logged, or returned. It lives in memory only
  for the duration of the POST handler and is immediately encrypted via
  ``encrypt()`` before any DB write.

Key mask computation:
- Long keys (>8 chars):  key[:4] + "..." + key[-4:]   e.g. "sk-ab...xyz9"
- Short keys (<=8 chars): key[:2] + "..." + key[-2:]   e.g. "ab...yz"
- The mask is stored in the ``key_mask`` column (migration 008) so GET reads
  don't need to decrypt anything.

Default models per provider (Charter §3.4):
- google    → "gemini-2.5-flash"
- openai    → "gpt-4o"
- anthropic → "claude-sonnet-4-6"

ADR references:
- ADR-002: AES-256-GCM encryption only via ``encryption.py``.
- ADR-024: workspace table schema; ownership filter required on all queries.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.core.db import get_supabase, execute_async
from app.core.encryption import encrypt
from app.models.key import KeyCreate, KeyResponse, KeyValidateRequest, KeyValidateResponse
from app.services.key_validator import validate_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["keys"])

# Default ai_model values per provider — Charter §3.4 conversation-tier defaults.
_DEFAULT_MODELS: dict[str, str] = {
    "google": "gemini-3-flash-preview",
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
}


def _make_key_mask(key: str) -> str:
    """Compute a short visual hint for a plaintext API key.

    The mask lets users confirm which key is stored without revealing the
    full key. Computation rules:
    - ``len(key) > 8``:  mask = ``key[:4] + "..." + key[-4:]``
    - ``len(key) <= 8``: mask = ``key[:2] + "..." + key[-2:]``

    The resulting string is at most 11 characters, safely within the
    ``VARCHAR(20)`` column limit defined in migration 008.

    Parameters
    ----------
    key : str
        The plaintext API key (already stripped and non-empty).

    Returns
    -------
    str
        The masked representation, e.g. ``"sk-ab...xyz9"``.
    """
    if len(key) > 8:
        return key[:4] + "..." + key[-4:]
    return key[:2] + "..." + key[-2:]


async def _assert_workspace_owner(workspace_id: str, user_id: str) -> dict:
    """Assert that user_id owns workspace_id and return the workspace row.

    Queries ``teemo_workspaces`` for a row matching both ``id`` and
    ``user_id``. Returns 404 (NOT 403) if no match — this prevents callers
    from learning whether the workspace exists for another user.

    Parameters
    ----------
    workspace_id : str
        The workspace UUID from the path parameter.
    user_id : str
        The authenticated caller's UUID (from JWT sub claim).

    Returns
    -------
    dict
        The raw Supabase row dict for the workspace.

    Raises
    ------
    HTTPException(404)
        If no workspace with that ID exists for this user.
    """
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .select("id, ai_provider, key_mask, ai_model, encrypted_api_key")
        .eq("id", workspace_id)
        .eq("user_id", user_id)
        .maybe_single()
        )
    )
    if not result or not result.data:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return result.data


# ---------------------------------------------------------------------------
# POST /api/keys/validate — stateless key probe
# ---------------------------------------------------------------------------


@router.post("/keys/validate", response_model=KeyValidateResponse)
async def validate_key_route(
    body: KeyValidateRequest,
    user_id: str = Depends(get_current_user_id),
) -> KeyValidateResponse:
    """Probe a provider API with the given key and return validity status.

    This is a stateless endpoint — no data is written to the database.
    The key is forwarded to the provider's public API and discarded immediately.

    The caller is authenticated to prevent unauthenticated brute-force probing
    of provider keys via this endpoint.

    Parameters
    ----------
    body : KeyValidateRequest
        The provider and plaintext key to validate.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    KeyValidateResponse
        ``{valid: true, message: "Valid"}`` or
        ``{valid: false, message: "<error description>"}``.
    """
    valid, message = await validate_key(body.provider, body.key)
    return KeyValidateResponse(valid=valid, message=message)


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/keys — save (encrypt + store) a key
# ---------------------------------------------------------------------------


@router.post(
    "/workspaces/{workspace_id}/keys",
    status_code=201,
    response_model=KeyResponse,
)
async def save_key(
    workspace_id: str,
    body: KeyCreate,
    user_id: str = Depends(get_current_user_id),
) -> KeyResponse:
    """Encrypt and store a provider API key on the workspace row.

    Ownership is verified before any write. The plaintext key is immediately
    encrypted via AES-256-GCM (ADR-002) and the ciphertext is stored on the
    workspace row. A short mask is computed from the plaintext and stored in
    the ``key_mask`` column so that subsequent reads can surface the mask
    without decrypting.

    The plaintext key is NEVER written to logs or the response.

    If ``ai_model`` is not supplied in the request body, the provider's
    default model is used (Charter §3.4):
    - google    → "gemini-2.5-flash"
    - openai    → "gpt-4o"
    - anthropic → "claude-sonnet-4-6"

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    body : KeyCreate
        Provider, plaintext key, and optional model override.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    KeyResponse
        The stored metadata (mask, provider, has_key=True, ai_model) — HTTP 201.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(404)
        Workspace not found or not owned by the caller.
    """
    # 1. Ownership check — raises 404 if not found
    await _assert_workspace_owner(workspace_id, user_id)

    # 2. Compute mask BEFORE encrypting (we need plaintext for mask computation).
    #    The mask is the only representation of the key that persists in clear.
    key_mask = _make_key_mask(body.key)

    # 3. Encrypt the plaintext key — ADR-002.
    encrypted = encrypt(body.key)
    # The plaintext is no longer referenced after this point.

    # 4. Resolve ai_model: use the supplied value or fall back to provider default.
    ai_model = body.ai_model or _DEFAULT_MODELS.get(body.provider, "")

    # 5. PATCH the workspace row.
    sb = get_supabase()
    result = (
        await execute_async(sb.table("teemo_workspaces")
        .update(
            {
                "encrypted_api_key": encrypted,
                "ai_provider": body.provider,
                "ai_model": ai_model,
                "key_mask": key_mask,
            }
        )
        .eq("id", workspace_id)
        .eq("user_id", user_id)
        )
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save key")

    return KeyResponse(
        provider=body.provider,
        key_mask=key_mask,
        has_key=True,
        ai_model=ai_model,
    )


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/keys — read key metadata
# ---------------------------------------------------------------------------


@router.get("/workspaces/{workspace_id}/keys", response_model=KeyResponse)
async def get_key(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> KeyResponse:
    """Return key metadata (mask + provider) for a workspace. No decryption.

    Reads ``key_mask``, ``ai_provider``, ``ai_model``, and the presence of
    ``encrypted_api_key`` from the workspace row. The plaintext key is never
    decrypted by this endpoint.

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    KeyResponse
        ``{has_key: true, provider: "...", key_mask: "sk-ab...xyz9", ai_model: "..."}``
        if a key is stored, or
        ``{has_key: false, provider: null, key_mask: null, ai_model: null}``
        if no key is stored.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(404)
        Workspace not found or not owned by the caller.
    """
    row = await _assert_workspace_owner(workspace_id, user_id)

    has_key = row.get("encrypted_api_key") is not None
    return KeyResponse(
        provider=row.get("ai_provider"),
        key_mask=row.get("key_mask"),
        has_key=has_key,
        ai_model=row.get("ai_model"),
    )


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/keys — remove stored key
# ---------------------------------------------------------------------------


@router.delete("/workspaces/{workspace_id}/keys", status_code=200)
async def delete_key(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Remove the stored API key from a workspace row.

    NULLs out ``encrypted_api_key``, ``ai_provider``, ``ai_model``, and
    ``key_mask`` on the workspace row. After this call, ``GET /keys`` will
    return ``{has_key: false}``.

    Parameters
    ----------
    workspace_id : str
        UUID of the target workspace (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.

    Returns
    -------
    dict
        ``{"message": "Key deleted"}`` — HTTP 200.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(404)
        Workspace not found or not owned by the caller.
    """
    # Verify ownership first — raises 404 if not found
    await _assert_workspace_owner(workspace_id, user_id)

    sb = get_supabase()
    await execute_async(sb.table("teemo_workspaces").update(
        {
            "encrypted_api_key": None,
            "ai_provider": None,
            "ai_model": None,
            "key_mask": None,
        }
    ).eq("id", workspace_id).eq("user_id", user_id))

    return {"message": "Key deleted"}
