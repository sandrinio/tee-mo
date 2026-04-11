"""
Tests for STORY-005A-02: `/api/slack/events` Signing-Secret Verification.

RED PHASE — all 8 tests are written BEFORE the implementation exists.
- Unit tests 1-2: import `verify_slack_signature` from `app.core.slack`
  directly. These will fail with ImportError until Green Phase adds the
  helper.
- Integration tests 3-8: POST to `/api/slack/events` via TestClient.
  These will fail because the stub endpoint never returns 401 — it has
  no signature verification until Green Phase hardens the route.

TDD strategy:
  - `compute_v0_sig` mirrors the 2026-04-12 live simulation helper, baked
    in as a private test utility.
  - `monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")` + explicit
    `get_settings.cache_clear()` and `get_slack_app.cache_clear()` ensure
    each test's env overrides take effect even though `get_settings` uses
    `@lru_cache`.
  - `caplog` is used for the "body not logged" assertion (test 8) as
    required by the task spec.

ADR compliance:
  - ADR-021: event scope unchanged — `url_verification` + 202 fallthrough.
  - No new dependencies introduced.

FLASHCARDS.md consulted:
  - bcrypt 5.0, `LaxEmailStr`, `samesite="lax"`, `get_supabase()` —
    none directly relevant; no auth or DB touches in this file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings

# --- Deferred import: verify_slack_signature does not exist in Red Phase. ---
# We capture the ImportError here so that the integration tests (which do NOT
# call verify_slack_signature directly) can still be collected and run — they
# must fail with assertion errors (200 != 401) rather than collection errors.
# The two unit tests explicitly re-raise the ImportError so they show as errors
# (not false passes) until Green Phase adds the implementation.
try:
    from app.core.slack import verify_slack_signature  # type: ignore[attr-defined]
    _IMPORT_ERROR: ImportError | None = None
except ImportError as exc:
    verify_slack_signature = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Private test helper
# ---------------------------------------------------------------------------

_TEST_SECRET = "test_secret"


def compute_v0_sig(secret: str, body: bytes, timestamp: str) -> str:
    """Compute a Slack v0 HMAC-SHA256 signature for the given body + timestamp.

    Mirrors the helper used in the 2026-04-12 live simulation against
    https://teemo.soula.ge/api/slack/events.  Embedded in the test file so
    it never relies on the production `verify_slack_signature` implementation
    — these are the *known-good* test vectors.

    Parameters
    ----------
    secret:
        The Slack signing secret (plain string, NOT base64).
    body:
        Raw request body bytes — must match exactly what Slack sends (no
        re-encoding after the fact).
    timestamp:
        Unix epoch seconds as a string (``str(int(time.time()))``).

    Returns
    -------
    str
        Signature in ``v0=<hex>`` format, ready to place in the
        ``X-Slack-Signature`` header.
    """
    base = f"v0:{timestamp}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_slack_signing_secret(monkeypatch):
    """Override SLACK_SIGNING_SECRET for every test in this module.

    Uses `monkeypatch.setenv` so the real `.env` value is never exercised.
    Clears `get_settings` and `get_slack_app` lru_cache instances so the
    patched env var propagates to the Settings singleton.
    """
    monkeypatch.setenv("SLACK_SIGNING_SECRET", _TEST_SECRET)
    get_settings.cache_clear()

    # Also clear the Slack AsyncApp cache — it captures slack_signing_secret
    # at construction time, so a stale cached instance would use the wrong
    # secret.  Import lazily to avoid pulling in slack_bolt at module scope.
    try:
        from app.core.slack import get_slack_app
        get_slack_app.cache_clear()
    except Exception:  # pragma: no cover — defensive only
        pass

    yield

    # Restore: clear caches so the next test/module starts fresh.
    get_settings.cache_clear()
    try:
        from app.core.slack import get_slack_app
        get_slack_app.cache_clear()
    except Exception:  # pragma: no cover
        pass


@pytest.fixture()
def client():
    """Return a FastAPI TestClient bound to the main app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# UNIT TESTS — direct calls to verify_slack_signature
# ---------------------------------------------------------------------------


def test_unit_verify_slack_signature_happy_path():
    """Unit test 1 — valid secret + body + timestamp + correct sig → True.

    Gherkin backing: §4.1 unit happy-path test requirement.
    Failure mode in Red: the module-level import failed with ImportError
    (stored in `_IMPORT_ERROR`). We re-raise it here so this test shows
    as ERROR (not false-pass) until Green Phase adds `verify_slack_signature`.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    body = b'{"type":"url_verification","challenge":"abc"}'
    ts = str(int(time.time()))
    sig = compute_v0_sig(_TEST_SECRET, body, ts)

    result = verify_slack_signature(
        signing_secret=_TEST_SECRET,
        body=body,
        timestamp=ts,
        signature=sig,
    )

    assert result is True


def test_unit_verify_slack_signature_tampered_body_returns_false():
    """Unit test 2 — correct sig for original body, modified body → False.

    Verifies that HMAC mismatch on body mutation returns False, not raises.
    Gherkin backing: §4.1 unit tampered-body requirement.
    Failure mode in Red: re-raises ImportError (same as unit test 1).
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    original_body = b'{"type":"url_verification","challenge":"abc"}'
    ts = str(int(time.time()))
    sig = compute_v0_sig(_TEST_SECRET, original_body, ts)

    tampered_body = b'{"type":"url_verification","challenge":"HACKED"}'

    result = verify_slack_signature(
        signing_secret=_TEST_SECRET,
        body=tampered_body,
        timestamp=ts,
        signature=sig,
    )

    assert result is False


# ---------------------------------------------------------------------------
# INTEGRATION TESTS — TestClient → POST /api/slack/events
# ---------------------------------------------------------------------------


def test_valid_signed_url_verification_returns_200_challenge(client):
    """Integration test 3 — valid signed url_verification → 200 + challenge.

    Gherkin scenario: 'valid signed url_verification challenge → 200 + challenge echo'

    Failure mode in Red: `verify_slack_signature` doesn't exist yet, so we
    re-raise the ImportError. This prevents the test from "accidentally passing"
    against the unarmed stub, and makes the dependency on Green Phase explicit.

    In Green Phase: `_IMPORT_ERROR` is None, the route verifies the signature,
    and the challenge is echoed as plain text → 200.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    body_bytes = b'{"type":"url_verification","challenge":"abc"}'
    ts = str(int(time.time()))
    sig = compute_v0_sig(_TEST_SECRET, body_bytes, ts)

    response = client.post(
        "/api/slack/events",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )

    assert response.status_code == 200
    assert response.text == "abc"


def test_missing_signature_header_returns_401(client):
    """Integration test 4 — missing X-Slack-Signature → 401.

    Gherkin scenario: 'missing X-Slack-Signature header → 401'

    Failure mode in Red: the stub returns 200 (no signature check), so this
    test will FAIL with AssertionError(200 != 401) — expected Red behavior.
    """
    body_bytes = b'{"type":"url_verification","challenge":"xyz"}'
    ts = str(int(time.time()))

    response = client.post(
        "/api/slack/events",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            # NO X-Slack-Signature header
        },
    )

    assert response.status_code == 401
    assert "invalid slack signature" in response.text.lower()


def test_tampered_body_returns_401(client):
    """Integration test 5 — tampered body → 401.

    Gherkin scenario: 'tampered body → 401'

    Signs the original body, then sends a different body with that signature.
    The HMAC mismatch must cause a 401.

    Failure mode in Red: stub returns 200 (no sig check), so test FAILS
    with AssertionError(200 != 401) — expected Red behavior.
    """
    original_body = b'{"type":"url_verification","challenge":"legitimate"}'
    ts = str(int(time.time()))
    sig = compute_v0_sig(_TEST_SECRET, original_body, ts)

    tampered_body = b'{"type":"url_verification","challenge":"INJECTED"}'

    response = client.post(
        "/api/slack/events",
        content=tampered_body,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,  # valid sig for a DIFFERENT body
        },
    )

    assert response.status_code == 401


def test_expired_timestamp_returns_401(client):
    """Integration test 6 — timestamp 301 seconds old → 401.

    Gherkin scenario: 'expired timestamp → 401'

    The signature is cryptographically valid for the old timestamp + body
    combination.  The 5-minute (300 s) replay window causes rejection even
    though the HMAC is correct — reason=expired.

    Failure mode in Red: stub returns 200 (no replay-window check), so test
    FAILS with AssertionError(200 != 401) — expected Red behavior.
    """
    body_bytes = b'{"type":"url_verification","challenge":"stale"}'
    old_ts = str(int(time.time()) - 301)  # 301 seconds in the past
    sig = compute_v0_sig(_TEST_SECRET, body_bytes, old_ts)

    response = client.post(
        "/api/slack/events",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": old_ts,
            "X-Slack-Signature": sig,
        },
    )

    assert response.status_code == 401


def test_valid_signed_app_mention_event_callback_returns_202(client):
    """Integration test 7 — valid signed event_callback → 202 empty body.

    Gherkin scenario: 'valid signed app_mention event → 202 empty body'

    A signed event that is NOT url_verification must still receive 202.
    Tests that hardening doesn't break the passthrough behavior.

    Failure mode in Red: `verify_slack_signature` doesn't exist yet, so we
    re-raise the ImportError — same guard as tests 1, 2, and 3. This prevents
    the test from accidentally passing against the unarmed stub.

    In Green Phase: the signed request passes verification, falls through to
    the 202 Accepted passthrough → 202 with empty body.
    """
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR

    payload = {
        "type": "event_callback",
        "event": {"type": "app_mention", "text": "hey bot"},
    }
    body_bytes = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = compute_v0_sig(_TEST_SECRET, body_bytes, ts)

    response = client.post(
        "/api/slack/events",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )

    assert response.status_code == 202
    assert response.content == b""


def test_raw_body_not_logged_on_401_but_rejection_reason_is_logged(client, caplog):
    """Integration test 8 — on 401, raw body NOT logged; rejection IS logged.

    Gherkin scenario: 'request body is NOT logged on 401'

    Uses pytest's `caplog` fixture at WARNING level to capture log records
    emitted during the request.  Asserts:
      1. None of the captured log messages contain the raw request body.
      2. At least one log message contains "slack signature rejected".

    Failure mode in Red: the stub never logs "slack signature rejected" (it
    returns 200 silently for bad requests), so assertion 2 FAILS — expected.
    """
    body_bytes = b'{"type":"url_verification","challenge":"should-not-appear-in-logs"}'
    ts = str(int(time.time()))
    # Deliberately send no signature to trigger the 401 path in Green Phase.
    # In Red the route returns 200, so assertion 1 trivially passes but
    # assertion 2 fails (no "slack signature rejected" log).

    with caplog.at_level(logging.WARNING, logger="app.api.routes.slack_events"):
        response = client.post(
            "/api/slack/events",
            content=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": ts,
                # No signature — should trigger 401 + rejection log in Green
            },
        )

    # In Green Phase this will be 401; in Red Phase the stub returns 200
    # and neither assertion below holds (test 4 will catch the 401 part;
    # this test focuses on the logging contract).
    assert response.status_code == 401  # will fail in Red (stub returns 200)

    all_log_text = " ".join(r.message for r in caplog.records)

    # The raw body must NEVER appear in logs.
    assert "should-not-appear-in-logs" not in all_log_text

    # The rejection log line MUST appear.
    assert "slack signature rejected" in all_log_text
