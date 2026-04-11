"""
Tee-Mo authentication routes.

Implements email + password registration, login, refresh, logout, and /me.
All tokens are delivered via httpOnly cookies — the response body never
contains an access_token (Tee-Mo does not use Supabase Realtime and has no
consumer for a body-level token).

Strip history (copied from new_app with charter §10 Epic Seed Map strip list):
  - Removed: Google OAuth endpoints and helpers
  - Removed: _signup_allowed_for_email invite gate
  - Removed: check_user_cap license enforcement
  - Removed: link_pending_invites RPC
  - Removed: _maybe_promote_admin
  - Removed: access_token echo in response bodies
  - Table renamed: chy_users → teemo_users
"""

from __future__ import annotations

import uuid
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.core.db import get_supabase
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_length,
    verify_password,
)
from app.models.user import UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Attach the access_token and refresh_token httpOnly cookies to a response.

    SameSite=Lax (not Strict) — Lax is required so that OAuth redirect flows
    in EPIC-005 (Slack) and EPIC-006 (Google Drive) do not lose the session
    cookie on the return hop. Lax is still CSRF-safe for these endpoints
    because they accept JSON bodies, not form posts.

    The refresh_token cookie is scoped to path="/api/auth" so that browsers
    only send it to auth endpoints — limiting its attack surface.
    """
    is_secure = not settings.debug
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies (used by POST /logout)."""
    response.delete_cookie(key="access_token", httponly=True, samesite="lax", path="/")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax", path="/api/auth")


def _row_to_user_response(row: dict[str, Any]) -> UserResponse:
    """Convert a teemo_users row dict into a UserResponse."""
    return UserResponse(id=row["id"], email=row["email"], created_at=row["created_at"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=201)
async def register(body: UserRegister, response: Response) -> dict:
    """
    Register a new user with email + password, then auto-login by setting cookies.

    See STORY-002-02 §1.2 R5 for the full strip list applied to this handler.
    """
    # Guard against bcrypt 5.0 ValueError before touching the DB (ADR-017, FLASHCARDS.md bcrypt entry).
    try:
        validate_password_length(body.password)
    except ValueError:
        raise HTTPException(status_code=422, detail="password_too_long")

    supabase = get_supabase()

    existing = (
        supabase.table("teemo_users")
        .select("id")
        .eq("email", body.email)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_id = uuid.uuid4()
    insert_result = (
        supabase.table("teemo_users")
        .insert(
            {
                "id": str(new_id),
                "email": body.email,
                "password_hash": hash_password(body.password),
            }
        )
        .execute()
    )

    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Failed to create user")

    user = _row_to_user_response(insert_result.data[0])

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _set_auth_cookies(response, access, refresh)

    return {"user": user}


@router.post("/login", status_code=200)
async def login(body: UserLogin, response: Response) -> dict:
    """
    Authenticate a user with email + password and set auth cookies.

    Error messages are intentionally generic ("Invalid credentials") to prevent
    user enumeration via the login endpoint.
    """
    supabase = get_supabase()

    result = (
        supabase.table("teemo_users")
        .select("*")
        .eq("email", body.email)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_row = result.data[0]

    if not verify_password(body.password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = _row_to_user_response(user_row)
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _set_auth_cookies(response, access, refresh)

    return {"user": user}


@router.post("/refresh", status_code=200)
async def refresh_token_route(request: Request, response: Response) -> dict:
    """
    Exchange a valid refresh token for a new access token cookie.

    Rejects access tokens presented in the refresh slot via the ``type`` claim
    check (access tokens have no ``type`` claim; refresh tokens have ``type``
    set to ``"refresh"``).
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = uuid.UUID(payload["sub"])
    new_access = create_access_token(user_id)

    is_secure = not settings.debug
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    return {"message": "Token refreshed"}


@router.post("/logout", status_code=200)
async def logout(response: Response) -> dict:
    """Clear both auth cookies. No server-side revocation in EPIC-002."""
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", status_code=200)
async def me(user_id: str = Depends(get_current_user_id)) -> UserResponse:
    """Return the authenticated user's profile (id, email, created_at)."""
    supabase = get_supabase()
    result = (
        supabase.table("teemo_users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_user_response(result.data[0])
