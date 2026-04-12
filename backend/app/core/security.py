"""
JWT and password security utilities for the Tee-Mo API.

This module is the single source of truth for all token operations. It signs
tokens with `settings.supabase_jwt_secret` so that Supabase can verify them
independently (ADR-001).

Usage:
    from app.core.security import create_access_token, verify_password, decode_token

Notes on library choice:
  - PyJWT (import as `jwt`) is used instead of python-jose — lighter, actively
    maintained, and produces standard RFC-7519 tokens without extra wrappers.
  - bcrypt is used directly rather than passlib to avoid the passlib dependency
    chain and to stay closer to the raw primitive (LESSONS: copy-then-optimize).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from jwt.api_jwt import PyJWT

from app.core.config import settings

# Module-local PyJWT instance — isolates our decode path from any global
# mutation of jwt.api_jwt._jwt_global_obj (BUG-20260411). A permissive
# jwt.decode(..., options={"verify_signature": False}) elsewhere in the
# process mutates module-level state and can leak into jwt.decode here;
# using a dedicated instance avoids that shared-options footgun.
_JWT = PyJWT()


# ---------------------------------------------------------------------------
# Password utilities
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.

    Uses bcrypt.gensalt() for automatic salt generation. The resulting string
    is a self-contained bcrypt hash that embeds the salt and cost factor —
    suitable for direct storage in the `password_hash` column of teemo_users.

    Args:
        password: The plaintext password to hash.

    Returns:
        A bcrypt hash string (60 characters, starts with '$2b$').
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored bcrypt hash.

    Args:
        password: The plaintext password supplied by the user.
        hashed:   The stored bcrypt hash from the database.

    Returns:
        True if the password matches, False otherwise.
    """
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------


def create_access_token(user_id: UUID, role: str = "authenticated") -> str:
    """
    Create a short-lived JWT access token.

    Expiry is controlled by `settings.access_token_expire_minutes` (must be 15
    for R5 compliance). The token is signed with `supabase_jwt_secret` so that
    Supabase can validate it without a round-trip to the API server.

    Claims:
        sub  — string user_id (UUID as string, Supabase expects this)
        role — 'authenticated' (Supabase role claim)
        iat  — issued-at timestamp (UTC)
        exp  — expiry timestamp (UTC)

    Args:
        user_id: The user's UUID from teemo_users.id.
        role:    JWT role claim. Defaults to 'authenticated'.

    Returns:
        A signed JWT string.
    """
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: UUID) -> str:
    """
    Create a long-lived JWT refresh token (7 days).

    The 'type': 'refresh' claim distinguishes this from access tokens so that
    the refresh endpoint can reject access tokens presented in the refresh
    cookie slot.

    Args:
        user_id: The user's UUID from teemo_users.id.

    Returns:
        A signed JWT string.
    """
    now = datetime.now(timezone.utc)
    payload: dict = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_expire_days)).timestamp()),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT token.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError:     If the token is malformed or the signature
                                   is invalid.

    Args:
        token: A JWT string (access or refresh).

    Returns:
        The decoded payload as a dict.
    """
    return _JWT.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )


# ---------------------------------------------------------------------------
# Slack OAuth state token helpers (STORY-005A-03)
# ---------------------------------------------------------------------------


def create_slack_state_token(user_id: str, *, now: int | None = None) -> str:
    """Create a short-lived (5 min) signed JWT for the Slack OAuth install flow state param.

    The token is audience-namespaced with ``aud="slack-install"`` so it cannot
    be confused with — or replayed as — an access token (ADR-001). Both tokens
    are signed with the same ``supabase_jwt_secret`` key but different audiences,
    which PyJWT enforces during decode.

    Uses the module-local ``_JWT`` instance (not the global ``jwt`` module) to
    avoid BUG-20260411: a ``jwt.decode(..., options={"verify_signature": False})``
    call anywhere in the process would mutate global ``jwt`` state and could
    cause tampered tokens to pass verification.

    Args:
        user_id: The authenticated user's ID string (from ``sub`` claim of access token).
        now:     Override for ``iat`` (Unix timestamp int). Defaults to ``time.time()``.
                 Pass a past timestamp in tests to generate already-expired tokens.

    Returns:
        A signed JWT string suitable for use as the Slack OAuth ``state`` query parameter.
    """
    iat = now if now is not None else int(time.time())
    payload = {
        "user_id": user_id,
        "iat": iat,
        "exp": iat + 300,
        "aud": "slack-install",
    }
    return _JWT.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def verify_slack_state_token(token: str) -> "SlackInstallState":
    """Verify and decode a Slack install state token.

    Validates the signature, expiry, and audience (``slack-install``) using the
    module-local ``_JWT`` instance (BUG-20260411 safety). The audience check
    ensures an access token cannot be used as a state token and vice versa.

    Args:
        token: A JWT string previously generated by ``create_slack_state_token``.

    Returns:
        A ``SlackInstallState`` with ``user_id`` and ``exp`` fields populated.

    Raises:
        jwt.ExpiredSignatureError:   If the token's ``exp`` is in the past.
        jwt.InvalidAudienceError:    If ``aud`` is not ``"slack-install"``.
        jwt.InvalidSignatureError:   If the signature does not match.
        jwt.DecodeError:             If the token is malformed.
    """
    from app.models.slack import SlackInstallState  # late import — avoids circular dep

    payload = _JWT.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="slack-install",
    )
    return SlackInstallState(user_id=payload["user_id"], exp=payload["exp"])


# ---------------------------------------------------------------------------
# Drive OAuth state token helpers (STORY-006-02)
# ---------------------------------------------------------------------------


def create_drive_state_token(user_id: str, workspace_id: str, *, now: int | None = None) -> str:
    """Create a short-lived (5 min) signed JWT for the Drive OAuth state param.

    The token is audience-namespaced with ``aud="drive-connect"`` so it cannot
    be confused with — or replayed as — an access token or Slack state token.
    All three token types share the same ``supabase_jwt_secret`` key but have
    distinct audiences, which PyJWT enforces during decode.

    Uses the module-local ``_JWT`` instance (not the global ``jwt`` module) to
    avoid BUG-20260411: a ``jwt.decode(..., options={"verify_signature": False})``
    call anywhere in the process would mutate global ``jwt`` state and could
    cause tampered tokens to pass verification.

    Args:
        user_id:      The authenticated user's ID string (from ``sub`` claim of access token).
        workspace_id: The target workspace ID. Embedded in the state so the callback
                      handler can associate the Google auth code with the right workspace.
        now:          Override for ``iat`` (Unix timestamp int). Defaults to ``time.time()``.
                      Pass a past timestamp in tests to generate already-expired tokens.

    Returns:
        A signed JWT string suitable for use as the Google OAuth ``state`` query parameter.
    """
    iat = now if now is not None else int(time.time())
    payload = {
        "user_id": user_id,
        "workspace_id": workspace_id,
        "iat": iat,
        "exp": iat + 300,
        "aud": "drive-connect",
    }
    return _JWT.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


def verify_drive_state_token(token: str) -> "DriveConnectState":
    """Verify and decode a Drive OAuth state token.

    Validates the signature, expiry, and audience (``drive-connect``) using the
    module-local ``_JWT`` instance (BUG-20260411 safety). The audience check
    ensures an access token or Slack state token cannot be used as a Drive state
    token.

    Args:
        token: A JWT string previously generated by ``create_drive_state_token``.

    Returns:
        A ``DriveConnectState`` with ``user_id``, ``workspace_id``, and ``exp``
        fields populated.

    Raises:
        jwt.ExpiredSignatureError:   If the token's ``exp`` is in the past.
        jwt.InvalidAudienceError:    If ``aud`` is not ``"drive-connect"``.
        jwt.InvalidSignatureError:   If the signature does not match.
        jwt.DecodeError:             If the token is malformed.
    """
    from app.models.drive import DriveConnectState  # late import — avoids circular dep

    payload = _JWT.decode(
        token,
        settings.supabase_jwt_secret,
        algorithms=["HS256"],
        audience="drive-connect",
    )
    return DriveConnectState(
        user_id=payload["user_id"],
        workspace_id=payload["workspace_id"],
        exp=payload["exp"],
    )


# ---------------------------------------------------------------------------
# Password length guard (Roadmap ADR-017, FLASHCARDS.md bcrypt 5.0 entry)
# ---------------------------------------------------------------------------


def validate_password_length(password: str) -> None:
    """
    Reject passwords longer than 72 bytes before they reach bcrypt.

    bcrypt 5.0 (pinned in backend/pyproject.toml) raises ValueError on
    passwords longer than 72 bytes — unlike bcrypt 4.x which silently
    truncated. This guard converts that failure into a controlled exception
    that the auth route (STORY-002-02) can catch and return as HTTP 422
    with detail ``password_too_long``.

    This function intentionally validates bytes, not characters, because
    bcrypt's limit is a byte limit (UTF-8 multi-byte characters like "é"
    each consume 2 bytes).

    Args:
        password: The plaintext password supplied by the user.

    Raises:
        ValueError: With message ``"password_too_long"`` when the UTF-8
            byte length of the password exceeds 72.
    """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("password_too_long")
