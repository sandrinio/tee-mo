"""
Tee-Mo Slack events receiver — hardened with signing-secret verification.

This module ships POST /api/slack/events with:
  - Slack v0 HMAC-SHA256 signature verification (STORY-005A-02, ADR-021).
  - url_verification challenge round-trip for Slack app setup.
  - 202 Accepted passthrough for all other event types (EPIC-005 Phase B
    will dispatch real handlers on top of this skeleton).

Security note:
    All requests MUST carry valid X-Slack-Signature and
    X-Slack-Request-Timestamp headers.  Unsigned, expired, or tampered
    requests are rejected with 401 and a log line that records ONLY the
    rejection classification (expired / malformed / mismatch) — never the
    raw body, full signature, or signing secret.

Why hand-rolled (not slack_bolt middleware):
    Spec §1.3 explicitly excludes slack_bolt middleware for this endpoint.
    The helper `verify_slack_signature` in `app.core.slack` implements the
    same v0 HMAC-SHA256 algorithm independently so tests can exercise it
    without the full Bolt framework.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.config import get_settings
from app.core.slack import verify_slack_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slack", tags=["slack"])


def _reject_reason(timestamp: str, signature: str) -> str:
    """Classify the rejection reason for a failed signature check.

    Returns a short label suitable for structured logging without leaking
    the raw body, full signature bytes, or signing secret.

    Classification order:
    1. ``malformed`` — timestamp is not a decimal integer, OR signature
       does not start with ``"v0="``.
    2. ``expired`` — timestamp is valid but outside the 300-second window.
    3. ``mismatch`` — timestamp and prefix are fine but HMAC differs
       (catches both wrong secrets and tampered bodies).

    Parameters
    ----------
    timestamp:
        Value of ``X-Slack-Request-Timestamp`` as received (may be empty).
    signature:
        Value of ``X-Slack-Signature`` as received (may be empty).

    Returns
    -------
    str
        One of ``"malformed"``, ``"expired"``, or ``"mismatch"``.
    """
    import time as _time

    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return "malformed"

    if abs(int(_time.time()) - ts_int) > 300:
        return "expired"

    if not signature.startswith("v0="):
        return "malformed"

    return "mismatch"


@router.post("/events")
async def slack_events(request: Request) -> Response:
    """Slack Events API endpoint with signature verification.

    Verifies the Slack v0 HMAC-SHA256 request signature before processing
    any payload.  Handles the ``url_verification`` challenge required by
    api.slack.com to activate Event Subscriptions; all other event types
    receive 202 Accepted (EPIC-005 Phase B will add real handlers).

    Returns
    -------
    200 text/plain
        Challenge string echoed for ``url_verification`` payloads.
    202 empty
        Acknowledgement for all other event types.
    400
        Body is not valid JSON (after signature passes).
    401
        Missing, expired, or cryptographically invalid signature.
    """
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    body = await request.body()

    settings = get_settings()
    if not verify_slack_signature(settings.slack_signing_secret, body, timestamp, signature):
        reason = _reject_reason(timestamp, signature)
        logger.warning("slack signature rejected: reason=%s", reason)
        raise HTTPException(status_code=401, detail="invalid slack signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400)

    if payload.get("type") == "url_verification":
        return PlainTextResponse(payload.get("challenge", ""))

    return Response(status_code=202)
