"""
Unit tests for backend/app/core/security.py — STORY-002-01 Red Phase.

These tests cover all 9 Gherkin scenarios from STORY-002-01-security_primitives §2.1.
They are written BEFORE the implementation exists (TDD Red phase). All 9 tests will
fail with ImportError/ModuleNotFoundError until security.py is created in Green phase.

No DB, no network, no get_supabase() import — pure function tests only.
No freezegun dependency — uses ±60s tolerance windows for time assertions instead.

ADR compliance: ADR-001 (JWT 15min access + 7d refresh), ADR-017 (bcrypt 72-byte guard).
FLASHCARDS.md: bcrypt 5.0 raises ValueError on > 72 bytes — validate_password_length is
the single line of defense before bcrypt is called.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_length,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    """
    Scenario: hash_password and verify_password round-trip.

    Verifies that:
    - hash_password produces a bcrypt hash starting with "$2b$"
    - the hash is exactly 60 characters long
    - verify_password returns True for the correct plaintext
    - verify_password returns False for an incorrect plaintext
    """
    h = hash_password("correcthorse")
    assert h.startswith("$2b$")
    assert len(h) == 60
    assert verify_password("correcthorse", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_is_salted():
    """
    Scenario: hash_password produces different hashes for same password (salting).

    Verifies that:
    - two calls to hash_password with the same input produce different hashes (unique salt)
    - verify_password validates correctly against each distinct hash independently
    """
    h1 = hash_password("correcthorse")
    h2 = hash_password("correcthorse")
    assert h1 != h2
    assert verify_password("correcthorse", h1)
    assert verify_password("correcthorse", h2)


def test_access_token_has_15_minute_expiry():
    """
    Scenario: create_access_token emits a valid 15-minute JWT.

    Verifies that the decoded payload contains:
    - sub equal to the provided user UUID string
    - role equal to "authenticated"
    - no "type" claim (access tokens do NOT carry a type claim)
    - exp within ±60 seconds of (now + 15 minutes)
    """
    uid = UUID("11111111-1111-1111-1111-111111111111")
    token = create_access_token(uid)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "authenticated"
    assert "type" not in payload
    expected_exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    assert abs(payload["exp"] - int(expected_exp.timestamp())) < 60


def test_refresh_token_has_7_day_expiry_and_type_claim():
    """
    Scenario: create_refresh_token emits a valid 7-day JWT with type claim.

    Verifies that the decoded payload contains:
    - sub equal to the provided user UUID string
    - type equal to "refresh"
    - exp within ±60 seconds of (now + 7 days)
    """
    uid = UUID("22222222-2222-2222-2222-222222222222")
    token = create_refresh_token(uid)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["type"] == "refresh"
    expected_exp = datetime.now(timezone.utc) + timedelta(days=7)
    assert abs(payload["exp"] - int(expected_exp.timestamp())) < 60


def test_decode_token_rejects_expired_token():
    """
    Scenario: decode_token raises ExpiredSignatureError on expired token.

    Builds a JWT manually with exp set 1 second in the past, signs it with the
    same secret and algorithm that decode_token uses, then asserts that
    decode_token raises jwt.ExpiredSignatureError.

    Uses settings.supabase_jwt_secret and settings.jwt_algorithm (the new
    jwt_algorithm field added to config.py in R1 — not yet present, causing
    Red phase failure).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": int((now - timedelta(minutes=30)).timestamp()),
        "exp": int((now - timedelta(seconds=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_decode_token_rejects_tampered_signature():
    """
    Scenario: decode_token raises InvalidTokenError on tampered signature.

    Takes a valid access token, flips the last character of the signature
    segment to produce a token with an invalid signature, then asserts that
    decode_token raises jwt.InvalidTokenError.

    jwt.InvalidTokenError is the base class for jwt.DecodeError — both are
    acceptable because signature corruption results in a DecodeError which IS
    an InvalidTokenError.
    """
    token = create_access_token(uuid4())
    head, body, sig = token.split(".")
    tampered = f"{head}.{body}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)


def test_validate_password_length_rejects_73_bytes():
    """
    Scenario: validate_password_length rejects 73-byte password.

    A string of 73 ASCII characters is exactly 73 bytes in UTF-8.
    Asserts that ValueError is raised with message "password_too_long".

    This protects against bcrypt 5.0's ValueError on passwords > 72 bytes
    (FLASHCARDS.md bcrypt 5.0 entry, ADR-017).
    """
    with pytest.raises(ValueError, match="password_too_long"):
        validate_password_length("a" * 73)


def test_validate_password_length_accepts_72_bytes():
    """
    Scenario: validate_password_length accepts 72-byte password.

    A string of 72 ASCII characters is exactly 72 bytes in UTF-8 — the
    maximum bcrypt accepts. Asserts no exception is raised.
    """
    validate_password_length("a" * 72)  # must not raise


def test_validate_password_length_counts_utf8_bytes():
    """
    Scenario: validate_password_length counts bytes, not characters.

    Validates that the guard uses UTF-8 byte length, not Python character
    length:
    - "a" * 36 + "é" * 18  →  36 + (18 × 2) = 72 bytes  →  OK (no raise)
    - "a" * 36 + "é" * 19  →  36 + (19 × 2) = 74 bytes  →  raises ValueError

    "é" (U+00E9) encodes to 2 bytes in UTF-8 but is 1 character, making it
    the canonical test for byte-vs-character counting.
    """
    # 36 ASCII bytes + 36 bytes of "é" (18 × 2) = 72 bytes — OK
    validate_password_length("a" * 36 + "é" * 18)
    # 36 ASCII bytes + 38 bytes of "é" (19 × 2) = 74 bytes — reject
    with pytest.raises(ValueError, match="password_too_long"):
        validate_password_length("a" * 36 + "é" * 19)


def test_decode_token_resists_global_options_poison():
    """
    Regression lock for BUG-20260411: PyJWT module-level options leak.

    Some test paths call jwt.decode(options={"verify_signature": False}) which
    mutates module-level PyJWT state. If decode_token uses the module-level
    jwt.decode, the mutation leaks in and tampered tokens slip through.

    decode_token must use a dedicated jwt.PyJWT() instance so it is isolated
    from the global mutation. This test verifies the isolation.
    """
    import jwt as jwt_module

    # Step 1: build a tampered token
    token = create_access_token(uuid4())
    head, body, sig = token.split(".")
    flipped = "A" if sig[-1] != "A" else "B"
    tampered = f"{head}.{body}.{sig[:-1]}{flipped}"

    # Step 2: poison module-level PyJWT state by calling the module-level
    # jwt.decode with verify_signature=False. This mirrors the exact mutation
    # pattern observed during S-02 post-merge validation.
    try:
        jwt_module.decode(
            token,
            options={"verify_signature": False},
            algorithms=[settings.jwt_algorithm],
        )
    except Exception:
        pass  # We don't care whether this raises; we only care about the side effect.

    # Step 3: decode_token MUST still reject the tampered token despite the
    # poisoned global state. This is the isolation guarantee.
    with pytest.raises(jwt_module.InvalidTokenError):
        decode_token(tampered)
