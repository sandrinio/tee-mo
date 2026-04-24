---
story_id: "STORY-003-05-slack-events-stub"
parent_epic_ref: "EPIC-005 Phase A (preparation)"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-03/STORY-003-05-slack-events-stub.md`. Shipped in sprint S-03, carried forward during ClearGate migration 2026-04-24.

# STORY-003-05: Slack Events Verification Stub Endpoint

**Complexity: L1** — 1 new endpoint file, 1 mount line in `main.py`, 1 unit test. ~20 minutes.

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

Slack's app creation flow verifies the Event Subscriptions Request URL by POSTing a `url_verification` challenge to the URL. The app cannot be activated in api.slack.com until Slack receives a valid response. Without this endpoint live in prod, the user cannot complete Steps 5–7 of the Slack app setup guide, which blocks EPIC-005 Phase A in S-04. We need the smallest possible endpoint that satisfies Slack's verification — no real event handling, no body parsing beyond the challenge extraction, no signature verification yet (that lands in S-04).

### 1.2 Detailed Requirements

- **R1 — Create `backend/app/api/routes/slack_events.py`** with a single endpoint `POST /api/slack/events`. The function signature is `async def slack_events(request: Request) -> Response`.
- **R2 — Parse the JSON body**. If parsing fails, return `400 Bad Request` with `{"detail": "invalid_json"}`.
- **R3 — `url_verification` handling**: If `body.type == "url_verification"`, return `200 OK` with content-type `text/plain` and body = the `challenge` value from the request body. Slack accepts plain text or JSON — plain text is the simpler option and matches Slack's own documented example. (The alternative `{"challenge": "..."}` JSON response also works but is slightly more code.)
- **R4 — Any other `type`**: return `202 Accepted` with an empty body. This is the placeholder for real event handlers that come in EPIC-005 Phase B. Returning 202 tells Slack "got it, we'll process asynchronously" and stops Slack from retrying. Critical: do NOT return 500 or 404 for unrecognized types — Slack will hammer the endpoint with retries and eventually disable the subscription.
- **R5 — NO signature verification yet**. S-04's Slack Phase A story adds the `x-slack-signature` header check using `SLACK_SIGNING_SECRET`. For S-03, skipping verification is fine because (a) the only caller is Slack itself during app-setup verification, (b) the only handled payload is `url_verification`, (c) the endpoint has no side effects, and (d) it returns 202 for everything else. Document this explicitly in a TODO comment.
- **R6 — Router registration**: Add `include_router(slack_events_router)` to `backend/app/main.py`, after the auth router mount. The router declares its own prefix `/api/slack`.
- **R7 — Unit test**: Create `backend/tests/test_slack_events_stub.py` with 3 tests: (1) `url_verification` returns the challenge, (2) other event types return 202, (3) malformed JSON returns 400.
- **R8 — Logging**: Log incoming POSTs at INFO level with the body `type` field. No PII concern — Slack events are structured and don't carry user content in the verification flow.

### 1.3 Out of Scope

- **Signature verification** — S-04 Phase A.
- **Real `app_mention` / `message.im` handlers** — S-04 Phase A builds the infrastructure, EPIC-005 Phase B builds the handlers (needs EPIC-007 agent to be callable).
- **Self-message filter** — lives in the real event handler, not this stub.
- **Slack Bolt AsyncApp integration** — S-04 introduces it.
- **Retry / deduplication** based on `event_id` — future concern.
- **Metrics / observability** — Coolify's built-in container logs are enough.

### TDD Red Phase: No

Rationale: L1 story, 3 unit tests, single-pass. TDD Red would just mean writing the tests first, which is built into the workflow. No separate Red phase.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Slack events verification stub

  Scenario: Slack url_verification challenge round-trips
    Given the backend is running
    When Slack POSTs to /api/slack/events with body {"type":"url_verification","challenge":"abc123","token":"legacy-ignored"}
    Then the response status is 200
    And the response content-type is text/plain; charset=utf-8
    And the response body is exactly "abc123"

  Scenario: Other event types return 202
    Given the backend is running
    When Slack POSTs to /api/slack/events with body {"type":"event_callback","event":{"type":"app_mention","text":"hi"}}
    Then the response status is 202
    And the response body is empty

  Scenario: Malformed JSON returns 400
    Given the backend is running
    When a client POSTs to /api/slack/events with body "not json"
    Then the response status is 400
    And the response JSON detail is "invalid_json"

  Scenario: Production URL verification succeeds end-to-end
    Given STORY-003-06 has completed and teemo.soula.ge is live with this endpoint
    When curl -X POST https://teemo.soula.ge/api/slack/events -H 'Content-Type: application/json' -d '{"type":"url_verification","challenge":"prodtest"}'
    Then the response status is 200
    And the response body is "prodtest"
```

### 2.2 Verification Steps (Manual)

- [ ] `cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/test_slack_events_stub.py -v` passes 3 tests.
- [ ] Local integration:
  ```bash
  cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m uvicorn app.main:app --reload
  # In a new terminal:
  curl -s -X POST http://localhost:8000/api/slack/events \
    -H 'Content-Type: application/json' \
    -d '{"type":"url_verification","challenge":"abc123"}'
  ```
  Expected output: `abc123` (no JSON wrapper).
- [ ] Curl with other event type:
  ```bash
  curl -sI -X POST http://localhost:8000/api/slack/events \
    -H 'Content-Type: application/json' \
    -d '{"type":"event_callback","event":{"type":"app_mention","text":"hi"}}'
  ```
  Expected: `HTTP/1.1 202 Accepted`.
- [ ] Curl malformed:
  ```bash
  curl -s -X POST http://localhost:8000/api/slack/events \
    -H 'Content-Type: application/json' \
    -d 'not-json'
  ```
  Expected: `{"detail":"invalid_json"}`.
- [ ] Deferred to STORY-003-06: production verification at `https://teemo.soula.ge/api/slack/events`.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-003-04** | PyJWT fix merged so the expanded test suite runs stably | [ ] |
| **Local uvicorn** | Backend dev server runs cleanly via `uvicorn app.main:app --reload` | [x] |
| **FastAPI** | `Request`, `Response`, `status` already importable from fastapi (used by `auth.py`) | [x] |

### 3.1 `backend/app/api/routes/slack_events.py` — full content

```python
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
```

### 3.2 `backend/app/main.py` edit

Add the import and `include_router` call. Keep the existing `auth_router` + `StaticFiles` mount order — the Slack router goes between `auth_router` and `StaticFiles` (both are under `/api/*` so order doesn't matter between API routers, but static must stay LAST).

```diff
 from app.api.routes.auth import router as auth_router
+from app.api.routes.slack_events import router as slack_events_router

 # ... app = FastAPI(), middleware ...

 app.include_router(auth_router)
+app.include_router(slack_events_router)

 # ... StaticFiles mount (remains last) ...
```

### 3.3 `backend/tests/test_slack_events_stub.py` — full content

```python
"""Unit tests for the S-03 Slack events verification stub."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_url_verification_returns_challenge_as_plain_text():
    """Scenario: Slack url_verification challenge round-trips."""
    response = client.post(
        "/api/slack/events",
        json={
            "type": "url_verification",
            "challenge": "abc123",
            "token": "legacy-ignored",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "abc123"


def test_other_event_types_return_202_accepted():
    """Scenario: Other event types return 202."""
    response = client.post(
        "/api/slack/events",
        json={
            "type": "event_callback",
            "event": {"type": "app_mention", "text": "hi"},
        },
    )
    assert response.status_code == 202
    assert response.content == b""


def test_malformed_json_returns_400():
    """Scenario: Malformed JSON returns 400 with detail."""
    response = client.post(
        "/api/slack/events",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_json"}
```

### 3.4 Files to Modify

| File | Change |
|------|--------|
| `backend/app/api/routes/slack_events.py` | **NEW** |
| `backend/app/main.py` | **EDIT** — import + `include_router` |
| `backend/tests/test_slack_events_stub.py` | **NEW** |

### 3.5 Verification run

```bash
cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/test_slack_events_stub.py -v
```

Expected: 3 passed.

Then run the full suite to confirm no regression:

```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/ -v
```

Expected count: 22 (S-02) + 1 (STORY-003-03 health test update — assume same count, just different assertion) + 1 (STORY-003-04 regression-lock) + 3 (this story) = **~26 passed**. Confirm exact count with the actual run.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 3 | url_verification happy path, other-type 202, malformed 400 |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — covered by STORY-003-06 production verification | |
| Integration tests | 0 — N/A | |

### 4.2 Definition of Done

- [ ] `backend/app/api/routes/slack_events.py` exists with a single `POST /api/slack/events` handler.
- [ ] `backend/app/main.py` mounts `slack_events_router` via `include_router`.
- [ ] `backend/tests/test_slack_events_stub.py` has 3 passing unit tests.
- [ ] Local curl tests (§2.2) all pass.
- [ ] No signature verification yet (documented TODO(S-04)).
- [ ] Full backend test suite passes (no regressions from prior stories).
- [ ] Logging is at INFO level with the event type visible.
- [ ] No new dependencies added to `backend/pyproject.toml`.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
