"""Unit tests for the S-03 Slack events verification stub.

Updated in STORY-005A-02 Green Phase: the endpoint now requires a valid
Slack v0 HMAC-SHA256 signature (X-Slack-Signature + X-Slack-Request-Timestamp
headers).  Tests that previously sent unsigned requests have been updated to
include correctly-computed signatures so they still exercise the same code
paths (challenge round-trip, 202 fallthrough, 400 for malformed JSON).

The signing secret is patched to ``"stub_test_secret"`` via
``SLACK_SIGNING_SECRET`` env var + ``get_settings.cache_clear()`` in the
``_patch_settings`` autouse fixture so the real .env value is never
exercised.
"""

import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

_STUB_SECRET = "stub_test_secret"


def _sign(body: bytes, secret: str = _STUB_SECRET) -> tuple[str, str]:
    """Return (timestamp_str, v0_signature) for ``body`` signed with ``secret``."""
    ts = str(int(time.time()))
    base = f"v0:{ts}:{body.decode()}".encode()
    sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return ts, sig


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch):
    """Override SLACK_SIGNING_SECRET for every test in this module."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", _STUB_SECRET)
    get_settings.cache_clear()
    try:
        from app.core.slack import get_slack_app
        get_slack_app.cache_clear()
    except Exception:  # pragma: no cover
        pass
    yield
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


def test_url_verification_returns_challenge_as_plain_text(client):
    """Scenario: Slack url_verification challenge round-trips."""
    import json as _json
    body = _json.dumps(
        {"type": "url_verification", "challenge": "abc123", "token": "legacy-ignored"}
    ).encode()
    ts, sig = _sign(body)

    response = client.post(
        "/api/slack/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "abc123"


def test_other_event_types_return_202_accepted(client):
    """Scenario: event_callback types return 200 (changed from 202 in STORY-007-05).

    STORY-007-05 changed the passthrough from 202 Accepted to 200 OK because
    event_callback payloads are now dispatched via asyncio.create_task.
    """
    import json as _json
    body = _json.dumps(
        {"type": "event_callback", "event": {"type": "app_mention", "text": "hi"}}
    ).encode()
    ts, sig = _sign(body)

    response = client.post(
        "/api/slack/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )
    assert response.status_code == 200
    assert response.content == b""


def test_malformed_json_returns_400(client):
    """Scenario: Malformed JSON returns 400 after signature passes.

    Note: the response body changes from ``{"detail": "invalid_json"}``
    (S-03 stub) to an empty 400 (hardened handler) because the new route
    returns ``Response(status_code=400)`` without a JSON body on parse
    failure.  Only the status code matters for this scenario.
    """
    body = b"not json"
    ts, sig = _sign(body)

    response = client.post(
        "/api/slack/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": sig,
        },
    )
    assert response.status_code == 400
