"""
FastAPI dependency injection helpers for the Tee-Mo API.

These functions are used as FastAPI ``Depends(...)`` arguments in route handlers.
They extract authenticated user identity from either:
  1. The 'access_token' httpOnly cookie (browser clients, primary flow), or
  2. The 'Authorization: Bearer <token>' header (API clients, testing).

The cookie takes precedence. If both are missing, HTTP 401 is returned.

Only ``get_current_user_id`` is implemented here. Tee-Mo does not have an admin
role, so ``get_current_user`` and ``get_current_admin_user`` are intentionally
absent (see STORY-002-02 §1.2 R2 and §1.3).

Usage::

    from app.api.deps import get_current_user_id

    @router.get("/api/something")
    async def protected(user_id: str = Depends(get_current_user_id)):
        ...
"""

from __future__ import annotations

import jwt
from fastapi import HTTPException, Request

from app.core.security import decode_token


async def get_current_user_id(request: Request) -> str:
    """
    Extract and validate the user_id from the access_token cookie or Authorization header.

    Checks for the token in this priority order:
      1. 'access_token' httpOnly cookie (primary — set by the auth routes on login).
      2. 'Authorization: Bearer <token>' header (secondary — for API clients and tests).

    Decodes the JWT and returns the ``sub`` claim (user_id as string). Raises HTTP 401
    for any failure so that protected routes never leak information about why auth failed.

    Args:
        request: The incoming FastAPI request (injected automatically).

    Returns:
        The user's UUID as a string (from the ``sub`` JWT claim).

    Raises:
        HTTPException(401): If no token is present, or if the token is expired/invalid.
    """
    # Primary: cookie (browser / SPA flow)
    token: str | None = request.cookies.get("access_token")

    # Secondary: Authorization header (API clients, test clients)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[len("Bearer "):]

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user_id_optional(request: Request) -> str | None:
    """Return the authenticated user_id, or None if no valid auth cookie.

    Used by routes that want to redirect to /login instead of returning 401
    on missing auth — e.g. the Slack OAuth callback, which cannot show a
    blank 401 page after the user just completed a consent flow.

    Args:
        request: The incoming FastAPI request (injected automatically).

    Returns:
        The user's UUID as a string, or None if not authenticated.
    """
    try:
        return await get_current_user_id(request)
    except HTTPException:
        return None
