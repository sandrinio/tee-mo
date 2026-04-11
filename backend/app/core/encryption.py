"""AES-256-GCM encryption helper for Slack bot tokens (ADR-002, ADR-010).

Exports:
    - encrypt(plaintext: str) -> str
    - decrypt(ciphertext_b64: str) -> str
    - key_fingerprint() -> str

The key is loaded lazily via get_settings() per call — no module-level
AESGCM instance (see FLASHCARDS.md singleton pattern).

Wire format: base64url(nonce[12] || ciphertext || gcm_tag[16])
The nonce is 12 random bytes (NIST-recommended for GCM), chosen fresh for
every encrypt() call to guarantee ciphertext uniqueness even when the same
plaintext is encrypted twice.
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _key() -> bytes:
    """Decode the configured TEEMO_ENCRYPTION_KEY to raw bytes.

    Adds standard base64 padding before decoding to support keys stored
    without trailing ``=`` characters (common in .env files). The Settings
    validator guarantees the decoded result is exactly 32 bytes.

    Returns
    -------
    bytes
        The 32-byte AES-256 key decoded from the base64url Settings field.
    """
    raw = get_settings().teemo_encryption_key
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded)


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string with AES-256-GCM and return base64url(nonce||ct).

    A fresh 12-byte nonce is generated for every call so that the same
    plaintext always produces a different ciphertext (IND-CPA property).

    Parameters
    ----------
    plaintext : str
        The plaintext to encrypt (must be valid UTF-8).

    Returns
    -------
    str
        base64url-encoded blob of nonce (12 bytes) concatenated with the
        AESGCM ciphertext+tag output.
    """
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64url(nonce||ct) blob. Raises InvalidTag on tamper.

    Parameters
    ----------
    ciphertext_b64 : str
        base64url-encoded blob previously returned by ``encrypt()``.
        Must be at least 28 bytes decoded (12-byte nonce + 16-byte GCM tag).

    Returns
    -------
    str
        The original plaintext string.

    Raises
    ------
    cryptography.exceptions.InvalidTag
        If the ciphertext has been tampered with, the key is wrong, or the
        authentication tag does not match. The caller must handle this.
    """
    blob = base64.urlsafe_b64decode(ciphertext_b64)
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(_key()).decrypt(nonce, ct, None).decode()


def key_fingerprint() -> str:
    """Return the first 8 hex chars of sha256(decoded_key). Safe to log.

    This is the ONLY permitted representation of the encryption key in log
    output (ADR-002 / STORY-005A-01 Req 5). The raw key, slack_client_secret,
    and slack_signing_secret must NEVER appear in logs.

    Returns
    -------
    str
        8 lowercase hexadecimal characters — a short fingerprint that lets
        operators confirm the correct key is loaded without revealing any
        key material.
    """
    return hashlib.sha256(_key()).hexdigest()[:8]
