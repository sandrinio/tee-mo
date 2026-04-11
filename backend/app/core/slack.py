"""Slack Bolt AsyncApp singleton and signature verification utilities.

Downstream stories must import from here, never directly from slack_bolt.
This enforces ADR-010's single-import-point rule: if the Slack Bolt version
or construction parameters ever change, only this file needs updating.

Exports:
    - get_slack_app() -> AsyncApp
    - verify_slack_signature(signing_secret, body, timestamp, signature, *, now) -> bool

Usage::

    from app.core.slack import get_slack_app, verify_slack_signature

    app = get_slack_app()
"""
import hashlib
import hmac
import time
from functools import lru_cache

from slack_bolt.async_app import AsyncApp

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_slack_app() -> AsyncApp:
    """Return the shared AsyncApp instance (constructed once per process).

    Mirrors the ``get_supabase()`` singleton pattern in ``app.core.db``:
    ``@lru_cache(maxsize=1)`` guarantees that the same ``AsyncApp`` object is
    returned on every call within a process lifetime, avoiding repeated
    re-initialisation of the Slack client.

    The app is constructed with ``token=None`` and
    ``token_verification_enabled=False`` because Tee-Mo is a multi-workspace
    OAuth app — there is no single default bot token. Each workspace's token
    is loaded from the encrypted ``teemo_slack_teams`` table at event-handling
    time (ADR-010).

    Tests flush this cache with ``get_slack_app.cache_clear()`` to get a fresh
    instance with monkeypatched env vars (same pattern as ``get_settings``).

    Returns
    -------
    AsyncApp
        The cached Slack Bolt async application instance.
    """
    s = get_settings()
    return AsyncApp(
        token=None,
        signing_secret=s.slack_signing_secret,
        request_verification_enabled=True,
    )


def verify_slack_signature(
    signing_secret: str,
    body: bytes,
    timestamp: str,
    signature: str,
    *,
    now: int | None = None,
) -> bool:
    """Verify a Slack request signature per Slack's v0 HMAC-SHA256 spec.

    Returns True iff:
    - ``timestamp`` is a base-10 integer within 300 seconds of ``now``
      (or the wall clock if ``now`` is not provided).
    - ``signature`` starts with ``"v0="`` and matches
      ``hmac_sha256(signing_secret, f"v0:{timestamp}:{body}")``.

    All comparisons use ``hmac.compare_digest`` for constant-time safety —
    never ``==`` on signature bytes (timing-attack prevention).

    The ``now`` kwarg is injected only by tests so they can freeze time
    without monkeypatching the system clock.  Production callers omit it.

    Reference: https://api.slack.com/authentication/verifying-requests-from-slack

    Parameters
    ----------
    signing_secret:
        The Slack app's signing secret (plain string, not base64).
    body:
        Raw request body bytes — must be the exact bytes Slack signed.
    timestamp:
        Value of the ``X-Slack-Request-Timestamp`` header (epoch seconds as
        a decimal string).
    signature:
        Value of the ``X-Slack-Signature`` header (e.g. ``"v0=<hex>"``).
    now:
        Optional override for the current Unix epoch seconds.  Omit in
        production; supply in tests to avoid flaky time-window failures.

    Returns
    -------
    bool
        ``True`` if the request is authentic and within the replay window;
        ``False`` for any failure (expired, malformed timestamp, HMAC mismatch).
    """
    # Timestamp must be a decimal integer within the 5-minute replay window.
    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return False

    current = now if now is not None else int(time.time())
    if abs(current - ts_int) > 300:
        return False

    # Build the signing basestring from raw body bytes (no re-encoding).
    sig_basestring = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(
        signing_secret.encode(), sig_basestring, hashlib.sha256
    ).hexdigest()

    # Constant-time comparison — MUST NOT use == on signature strings.
    return hmac.compare_digest(expected, signature)
