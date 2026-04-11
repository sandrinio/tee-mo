"""
Tee-Mo Slack events receiver — S-03 verification stub.

This module ships a single endpoint POST /api/slack/events that satisfies
Slack's Event Subscriptions URL verification handshake during app setup.
It does NOT yet handle real events (app_mention, message.im) — EPIC-005
Phase B in a later sprint builds those handlers on top of this skeleton.

Why a stub:
    Slack's app creation flow verifies the Events Request URL by POSTing
    a `url_verification` challenge to the URL. The app cannot be activated
    in api.slack.com until Slack receives a valid response. Without this
    endpoint live in prod, the user cannot finish Steps 5-7 of the Slack
    app setup guide and EPIC-005 Phase A in S-04 is blocked.

Security note:
    Signature verification via SLACK_SIGNING_SECRET is NOT done here.
    EPIC-005 Phase A (S-04) adds the `x-slack-signature` check.
    For S-03 it's acceptable to skip because:
      - The only handled payload is `url_verification` (no side effects).
      - Other event types return 202 and are no-ops.
      - The endpoint cannot leak data regardless of caller identity.
      - The attack surface is one HTTP POST that echoes a string back.
    TODO(S-04): add `verify_slack_signature(request)` per Slack's docs.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/slack", tags=["slack"])


@router.post("/events")
async def slack_events(request: Request) -> Response:
    """
    Slack Event Subscriptions receiver — S-03 verification stub.

    Handles ONLY the `url_verification` challenge required by api.slack.com
    to activate the app's Event Subscriptions. Every other event type is
    acknowledged with 202 Accepted so Slack stops retrying but no real
    processing occurs. EPIC-005 Phase B will dispatch real events here.

    Returns:
        200 text/plain with the challenge string, for `url_verification`
        400 JSON if the body is not valid JSON
        202 (empty) for any other event type
    """
    raw_body = await request.body()

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.warning("Slack events endpoint received invalid JSON")
        return JSONResponse({"detail": "invalid_json"}, status_code=400)

    event_type = payload.get("type")
    logger.info("Slack event received: type=%s", event_type)

    if event_type == "url_verification":
        challenge = payload.get("challenge", "")
        # Slack accepts plain text or JSON — plain text is simpler and matches
        # Slack's own documented example.
        return PlainTextResponse(content=challenge, status_code=200)

    # Everything else is a placeholder ack until EPIC-005 Phase B ships the
    # real event handlers. 202 Accepted signals "received, will not retry".
    return Response(status_code=status.HTTP_202_ACCEPTED)
