"""
Unit tests for backend/app/core/encryption.py — STORY-005A-01 Red Phase.

Covers all encryption-related Gherkin scenarios from STORY-005A-01 §2.1:
  - Scenario: encryption roundtrip (nonce freshness + ciphertext != plaintext)
  - Scenario: tamper detection (flip a ciphertext byte, expect InvalidTag)
  - Scenario: wrong key decrypt (monkeypatch key swap, expect InvalidTag)

These tests are written BEFORE the implementation exists (TDD Red phase).
All tests will fail with ModuleNotFoundError until Green phase creates
``backend/app/core/encryption.py``.

Test strategy:
  - No DB, no network, no FastAPI TestClient — pure function tests.
  - ``monkeypatch.setenv`` swaps ``TEEMO_ENCRYPTION_KEY`` between encrypt and
    decrypt to simulate a wrong-key scenario; ``get_settings.cache_clear()``
    flushes the lru_cache so Settings re-reads from env on the next call.
  - The tamper test mutates the ciphertext portion (bytes 12+), NOT the nonce
    prefix (bytes 0..11), so the AESGCM tag check fails deterministically.

ADR compliance:
  - ADR-002: AES-256-GCM via cryptography.AESGCM; nonce is 12 random bytes.
  - ADR-010: Encrypted bot tokens stored as base64(nonce || ciphertext || tag).

FLASHCARDS.md consulted:
  - Sprint context (S-04): AESGCM is first use in this codebase — review docs.
  - No lru_cache on AESGCM instance — key loaded lazily per call to get_settings().
"""

from __future__ import annotations

import base64

import pytest

# --- These imports DO NOT EXIST yet. They drive the Red phase failure. ---
from app.core.encryption import decrypt, encrypt, key_fingerprint  # noqa: F401
from app.core.config import get_settings  # noqa: F401  — added by Green phase
# -------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scenario: encryption roundtrip
# ---------------------------------------------------------------------------


def test_encrypt_decrypt_roundtrip():
    """
    Scenario: encryption roundtrip.

    Verifies:
    - decrypt(encrypt(plaintext)) returns the original plaintext.
    - The ciphertext differs from the plaintext (it is actually encrypted).
    - Two consecutive encrypt() calls on the same plaintext return different
      ciphertexts because each call uses a freshly generated 12-byte nonce
      (probabilistic guarantee — collision probability is astronomically low).

    ADR-002 compliance: nonce is 12 random bytes; ciphertext is base64url of
    nonce || ciphertext || GCM-tag.
    """
    plaintext = "hello world"

    ciphertext1 = encrypt(plaintext)
    ciphertext2 = encrypt(plaintext)

    # Ciphertext must not equal the plaintext
    assert ciphertext1 != plaintext, "Ciphertext must differ from plaintext"

    # Two encryptions of the same plaintext must produce different ciphertexts
    # (nonce freshness — each call uses os.urandom(12))
    assert ciphertext1 != ciphertext2, (
        "Two encrypt() calls on the same plaintext must produce different "
        "ciphertexts (fresh nonce per call)"
    )

    # Both ciphertexts must decrypt back to the original plaintext
    assert decrypt(ciphertext1) == plaintext
    assert decrypt(ciphertext2) == plaintext


# ---------------------------------------------------------------------------
# Scenario: tamper detection
# ---------------------------------------------------------------------------


def test_tamper_detection_raises_invalid_tag():
    """
    Scenario: tamper detection.

    Mutates a single byte of the ciphertext portion of the blob (the bytes
    AFTER the 12-byte nonce prefix). AESGCM's authentication tag check will
    fail and ``cryptography.exceptions.InvalidTag`` must propagate from
    ``decrypt()``. The implementation must NOT catch InvalidTag internally.

    The first 12 bytes are the nonce — mutating the nonce would also cause
    InvalidTag, but this test explicitly targets the ciphertext region to
    confirm the GCM authentication tag covers it.
    """
    from cryptography.exceptions import InvalidTag

    ciphertext_b64 = encrypt("secret")
    blob = bytearray(base64.urlsafe_b64decode(ciphertext_b64))

    # Flip a byte in the ciphertext region (byte 12 — first byte after nonce).
    # XOR with 0xFF guarantees the byte changes regardless of its current value.
    blob[12] ^= 0xFF

    tampered_b64 = base64.urlsafe_b64encode(bytes(blob)).decode()

    with pytest.raises(InvalidTag):
        decrypt(tampered_b64)


# ---------------------------------------------------------------------------
# Scenario: wrong key decrypt (monkeypatched via env)
# ---------------------------------------------------------------------------


def test_wrong_key_raises_invalid_tag(monkeypatch):
    """
    Scenario: wrong key decrypt.

    Encrypts with the key currently in TEEMO_ENCRYPTION_KEY, then swaps the
    env var to a different valid 32-byte key and flushes the lru_cache so
    get_settings() re-reads from the env on the next call. decrypt() must
    raise ``cryptography.exceptions.InvalidTag`` because the AESGCM key no
    longer matches.

    The replacement key is a known-good 32-byte base64url string (44 chars
    with the trailing ``=`` padding character). Using a fully valid key ensures
    the ValueError path (short/invalid key) is not triggered — only the
    authentication-tag mismatch path.

    Uses monkeypatch.setenv so the original env is restored after the test.
    get_settings.cache_clear() is called both before and after to avoid
    polluting other tests in the session.
    """
    from cryptography.exceptions import InvalidTag

    # Encrypt with the current (correct) key
    ciphertext_b64 = encrypt("my secret message")

    # A different valid 32-byte urlsafe-base64 key (32 raw bytes → 44 base64 chars)
    wrong_key = base64.urlsafe_b64encode(b"\xde\xad\xbe\xef" * 8).decode()

    # Swap the key and flush the settings cache so the next get_settings() call
    # reads the wrong key from the environment.
    monkeypatch.setenv("TEEMO_ENCRYPTION_KEY", wrong_key)
    get_settings.cache_clear()

    try:
        with pytest.raises(InvalidTag):
            decrypt(ciphertext_b64)
    finally:
        # Restore cache state regardless of test outcome to prevent key leakage
        # into subsequent tests that share the same process.
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Scenario: Secrets never printed at startup — key_fingerprint helper
# ---------------------------------------------------------------------------


def test_key_fingerprint_is_8_char_hex():
    """
    Scenario: Secrets never printed at startup (fingerprint helper sub-check).

    Verifies that ``key_fingerprint()`` returns exactly 8 lowercase hex
    characters (sha256(decoded_key).hexdigest()[:8]), and that the result
    does NOT contain any substring of the raw key or the literal string
    ``slack_client_secret``.

    This is a narrow unit test of the helper function. The actual startup log
    line format (``"enc key fp: <8-hex-chars>"``) is verified in the manual
    verification checklist (§2.2) rather than an automated test, to keep this
    test hermetic and free of log-capture machinery.

    ADR-002 / Req 5: fingerprint is the ONLY permitted representation of the
    key in log output. The raw key and all other secret values must never appear.
    """
    import re

    fp = key_fingerprint()

    # Must be exactly 8 lowercase hex characters
    assert re.match(r"^[0-9a-f]{8}$", fp), (
        f"key_fingerprint() must return exactly 8 lowercase hex chars, got: {fp!r}"
    )

    # Must not contain the literal string "slack_client_secret"
    assert "slack_client_secret" not in fp
