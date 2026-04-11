"""
User-related Pydantic models for Tee-Mo auth.

These models define the request and response contracts for POST /api/auth/register,
POST /api/auth/login, and GET /api/auth/me. They intentionally carry only the
columns that exist in the ``teemo_users`` table (id, email, password_hash,
created_at, updated_at) — no full_name, no avatar_url, no auth_provider,
no admin flag.

Email validation note:
    The ``LaxEmailStr`` type is used instead of Pydantic's built-in ``EmailStr``
    because ``email-validator`` 2.x (transitively installed) rejects ``.test``
    TLD domains as "special-use or reserved" even when ``check_deliverability=False``.
    Tests use ``@teemo.test`` addresses; this annotation enables ``test_environment=True``
    so that those addresses pass validation during testing while still rejecting
    genuinely malformed addresses like ``not-an-email``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import email_validator as ev
from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator


def _validate_email_lax(v: str) -> str:
    """
    Validate an email address using email-validator with test_environment=True.

    Accepts test-domain addresses like ``@teemo.test`` (used in automated tests)
    while still rejecting clearly malformed addresses such as ``not-an-email``.
    Does NOT perform DNS deliverability checks (``check_deliverability=False``).

    Args:
        v: The raw email string to validate.

    Returns:
        The normalised email address.

    Raises:
        ValueError: If the address fails basic syntax validation.
    """
    try:
        result = ev.validate_email(v, check_deliverability=False, test_environment=True)
        return result.normalized
    except ev.EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


# Annotated email type that accepts .test TLD addresses used in automated tests.
LaxEmailStr = Annotated[str, AfterValidator(_validate_email_lax)]


class UserRegister(BaseModel):
    """Request body for POST /api/auth/register."""

    email: LaxEmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Request body for POST /api/auth/login."""

    email: LaxEmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Public user profile — safe to return to the frontend."""

    id: UUID
    email: str
    created_at: datetime
