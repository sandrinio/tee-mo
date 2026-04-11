---
story_id: "STORY-005A-02-events-signing-verification"
parent_epic_ref: "EPIC-005-phase-a"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1, §6 R2 / Codebase / 2026-04-12 live simulation"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-005A-02: `/api/slack/events` Signing-Secret Verification

**Complexity: L2** — Standard, 2 files, known pattern (Slack's HMAC-SHA256 v0 signing spec, with known-good test vectors from a 2026-04-12 live production simulation baked into the test fixtures).

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement
S-03 shipped `/api/slack/events` as a **stub** that handles `url_verification` but accepts any POST body without verifying it came from Slack. The `TODO(S-04)` comment at `backend/app/api/routes/slack_events.py:24` needs to become real signature verification, closing an auth hole before Phase B event handlers land.

### 1.2 Detailed Requirements

- **Req 1 — Signing helper:** In `backend/app/core/slack.py`, add:
  ```python
  def verify_slack_signature(
      signing_secret: str,
      body: bytes,
      timestamp: str,
      signature: str,
      now: int | None = None,
  ) -> bool
  ```
  Implementation per Slack spec:
  1. Return `False` if `timestamp` is not a base-10 integer or differs from `now or int(time.time())` by more than **300 seconds** (5-minute replay window).
  2. Compute `sig_basestring = f"v0:{timestamp}:{body.decode()}"`.
  3. Compute `expected = "v0=" + hmac.new(signing_secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()`.
  4. Return `hmac.compare_digest(expected, signature)`.
  5. Use **constant-time comparison only** (no `==`).
- **Req 2 — Events route hardening:** In `backend/app/api/routes/slack_events.py`, replace the `TODO(S-04)` with a guard at the top of the handler:
  - Read `X-Slack-Request-Timestamp` and `X-Slack-Signature` headers.
  - Read raw body bytes via `await request.body()` (must happen BEFORE any JSON parse — Slack signs the raw bytes).
  - Call `verify_slack_signature(settings.slack_signing_secret, body, timestamp, signature)`.
  - If it returns `False` → raise `HTTPException(status_code=401, detail="invalid slack signature")`.
  - Otherwise continue with existing `url_verification` challenge logic + 202 fallthrough.
- **Req 3 — Preserve existing behavior:** Valid `url_verification` POSTs must still return 200 with the `challenge` value as a plain-text body (matches current S-03 behavior observed in production on 2026-04-12). Non-`url_verification` events must still return 202 with an empty body.
- **Req 4 — Known-good test vectors:** Use the canonical HMAC test vectors from Slack's verifying-requests-from-slack documentation as positive test fixtures. Use the format `v0:{ts}:{body}` verified working on 2026-04-12 against https://teemo.soula.ge/api/slack/events.
- **Req 5 — No body logging:** On 401, do NOT log the raw request body or any signature value. Log only a one-line warning like `slack signature rejected: reason=<expired|mismatch|malformed>`.

### 1.3 Out of Scope
- Actually handling `app_mention` / `message.im` events — deferred to EPIC-005 Phase B.
- `slack_bolt.AsyncApp`'s built-in signature verifier — we're writing a small helper instead for test isolation and because we only need one function, not the full Bolt middleware.
- Any changes to `GET /api/slack/install` or `GET /api/slack/oauth/callback` (they exchange OAuth codes, not signed events — different security model).

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: Slack Events Signing Verification

  Background:
    Given SLACK_SIGNING_SECRET is set to "test_secret"

  Scenario: valid signed url_verification challenge → 200 + challenge echo
    Given a POST to /api/slack/events with body '{"type":"url_verification","challenge":"abc"}'
    And header X-Slack-Request-Timestamp = current unix seconds
    And header X-Slack-Signature = correct HMAC-SHA256 v0 of the body
    When the request is processed
    Then the response status is 200
    And the response body is "abc" (plain text)

  Scenario: missing X-Slack-Signature header → 401
    Given a POST to /api/slack/events with a valid body but no signature header
    Then the response status is 401
    And the response body mentions "invalid slack signature"

  Scenario: tampered body → 401
    Given a valid signed request
    When the body is modified after signing
    Then the response status is 401

  Scenario: expired timestamp → 401
    Given a POST to /api/slack/events signed correctly with a timestamp 301 seconds old
    Then the response status is 401

  Scenario: valid signed app_mention event → 202 empty body
    Given a POST to /api/slack/events with a valid signature and event_callback body
    When the request is processed
    Then the response status is 202
    And the body is empty

  Scenario: request body is NOT logged on 401
    Given a 401 response is returned
    When the test captures log output
    Then the captured logs do NOT contain the raw body
    And the captured logs contain "slack signature rejected"
```

### 2.2 Verification Steps (Manual)
- [ ] `cd backend && uv run pytest tests/test_slack_events_signed.py -v`
- [ ] Manual curl with a bad signature:
  ```bash
  curl -i -X POST https://teemo.soula.ge/api/slack/events \
    -H "Content-Type: application/json" \
    -H "X-Slack-Request-Timestamp: $(date +%s)" \
    -H "X-Slack-Signature: v0=deadbeef" \
    -d '{"type":"url_verification","challenge":"x"}'
  ```
  → must return 401 AFTER this story lands (was 200 before per 2026-04-12 simulation).

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `SLACK_SIGNING_SECRET` in `.env` (present since S-03) AND declared in `Settings` (done in STORY-005A-01). | [ ] |
| **Depends On** | STORY-005A-01 merged (`Settings` has `slack_signing_secret`, `backend/app/core/slack.py` exists). | [ ] |
| **Services** | None for unit tests; live backend needed only for manual curl verification. | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_slack_events_signed.py`.
- Use `TestClient` from FastAPI (pattern in `backend/tests/test_auth_routes.py`).
- Override `settings.slack_signing_secret = "test_secret"` via `monkeypatch.setenv` or a dependency override.
- Use the same `compute_v0_sig(body, timestamp, secret)` helper in the test file that we used in the live simulation script on 2026-04-12 — bake it in as a private test helper.
- One test per Gherkin scenario (6 tests minimum).

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `backend/app/api/routes/slack_events.py` (MODIFY), `backend/app/core/slack.py` (MODIFY — add `verify_slack_signature`) |
| **Related Files** | `backend/tests/test_slack_events_signed.py` (NEW) |
| **ADR References** | ADR-021 (Slack event scope) |
| **First-Use Pattern** | No — `hmac.compare_digest` is standard library, and `verify_slack_signature` is a plain function. |
| **Reference** | Slack signing spec: https://api.slack.com/authentication/verifying-requests-from-slack. Test vector format verified against live production endpoint on 2026-04-12. |

### 3.3 Technical Logic

**Current `slack_events.py` shape (from Context Pack):**
```python
# Lines ~39-73: POST /api/slack/events
# 1. Reads raw body
# 2. Parses JSON
# 3. If type == "url_verification": return PlainTextResponse(challenge)
# 4. Else: return Response(status_code=202)
```

**New shape:**
```python
@router.post("/api/slack/events")
async def slack_events(request: Request):
    timestamp = request.headers.get("x-slack-request-timestamp", "")
    signature = request.headers.get("x-slack-signature", "")
    body = await request.body()  # raw bytes — MUST happen before JSON parse

    if not verify_slack_signature(
        settings.slack_signing_secret, body, timestamp, signature
    ):
        logger.warning("slack signature rejected: reason=%s", _reject_reason(...))
        raise HTTPException(status_code=401, detail="invalid slack signature")

    # Existing logic unchanged below:
    payload = json.loads(body)
    if payload.get("type") == "url_verification":
        return PlainTextResponse(payload["challenge"])
    return Response(status_code=202)
```

**Reject-reason classification (for non-body-leaking log):**
- `expired` — timestamp delta > 300s
- `malformed` — timestamp not an int, or signature doesn't match `v0=<hex>` shape
- `mismatch` — HMAC doesn't match

### 3.4 API Contract

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/api/slack/events` | POST | Slack signing secret (X-Slack-Signature + X-Slack-Request-Timestamp headers) | Raw JSON body per Slack Events API spec | 200 + plain text challenge (url_verification), 202 empty (all other events), 401 (bad/missing signature) |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 2 | `verify_slack_signature` happy + tampered body direct calls |
| Component tests | 0 — N/A | |
| Integration tests | 6 | One per Gherkin scenario |
| E2E / acceptance | 1 | Manual curl against live endpoint post-deploy |

### 4.2 Definition of Done
- [ ] TDD Red phase enforced — all 6 scenario tests written failing first.
- [ ] §4.1 minimum counts met.
- [ ] FLASHCARDS.md consulted.
- [ ] ADR-021 respected (event scope unchanged — still `url_verification` challenge + 202 fallthrough only).
- [ ] Manual curl against production after merge confirms 401 for unsigned requests (was 200 before).
- [ ] No raw body or signature values in log output.
- [ ] `TODO(S-04)` comment removed from `slack_events.py`.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 25 | 2,199 | 2,224 |
| Developer | 15 | 1,246 | 1,261 |
| DevOps | 14 | 180 | 194 |
