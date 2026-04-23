---
task_id: "STORY-005A-02-dev-green"
story_id: "STORY-005A-02"
phase: "green"
agent: "developer"
worktree: ".worktrees/STORY-005A-02/"
sprint: "S-04"
---

# Developer Task — STORY-005A-02 Green Phase

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-02/`

A sibling worktree `.worktrees/STORY-005A-03/` is running in parallel — do NOT touch it.

## Phase
**GREEN PHASE — Implement code to make the 8 Red Phase tests pass.** DO NOT modify the test files.

## Red Phase Summary
Tests at `backend/tests/test_slack_events_signed.py` (8 tests: 2 unit + 6 integration). All 8 currently FAILING:
- Tests 1/2/3/7: `ImportError: cannot import name 'verify_slack_signature' from 'app.core.slack'` (re-raised via `_IMPORT_ERROR` sentinel — leave this alone, do NOT remove the sentinel)
- Tests 4/5/6/8: `AssertionError: 200 != 401` (stub route accepts any POST)

Red Phase report: `.vbounce/reports/STORY-005A-02-dev-red.md`.

## Mandatory Reading
1. `FLASHCARDS.md`
2. `.vbounce/sprint-context-S-04.md`
3. `product_plans/sprints/sprint-04/STORY-005A-02-events-signing-verification.md` — full spec
4. `backend/tests/test_slack_events_signed.py` — READ ONLY, do NOT modify
5. `backend/app/core/slack.py` — current state (only `get_slack_app()` from 005A-01)
6. `backend/app/api/routes/slack_events.py` — current stub with `TODO(S-04)` at ~line 24

## Files to Modify

### 1. MODIFY `backend/app/core/slack.py` — add `verify_slack_signature`

```python
import hashlib
import hmac
import time
from functools import lru_cache

# ... existing imports + get_slack_app ...


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
    - `timestamp` is a base-10 integer within 300 seconds of `now` (or wall clock)
    - `signature` starts with "v0=" and matches hmac_sha256(signing_secret, f"v0:{timestamp}:{body}")

    All comparisons use `hmac.compare_digest` for constant-time safety.

    Reference: https://api.slack.com/authentication/verifying-requests-from-slack
    """
    # Timestamp must be an integer within 5 minutes of now
    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return False
    current = now if now is not None else int(time.time())
    if abs(current - ts_int) > 300:
        return False

    # Build the signing basestring from raw body bytes
    sig_basestring = f"v0:{timestamp}:{body.decode()}".encode()
    expected = "v0=" + hmac.new(
        signing_secret.encode(), sig_basestring, hashlib.sha256
    ).hexdigest()

    # Constant-time comparison only
    return hmac.compare_digest(expected, signature)
```

Also add a small private classifier used by the route for the log line (keep it in `slack_events.py` actually — see below — not in `slack.py`).

### 2. MODIFY `backend/app/api/routes/slack_events.py`

Replace the `TODO(S-04)` and the existing handler body with a guarded version. Read the full current file first. Expected shape after changes:

```python
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from app.core.config import get_settings
from app.core.slack import verify_slack_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slack", tags=["slack"])


def _reject_reason(timestamp: str, signature: str) -> str:
    """Classify the rejection reason without leaking the body or signature."""
    try:
        ts_int = int(timestamp)
    except (ValueError, TypeError):
        return "malformed"
    import time as _time
    if abs(int(_time.time()) - ts_int) > 300:
        return "expired"
    if not signature.startswith("v0="):
        return "malformed"
    return "mismatch"


@router.post("/events")
async def slack_events(request: Request):
    """Slack Events API endpoint. Verifies request signature, handles url_verification, 202s everything else.

    Returns:
        - 200 + plain text challenge for url_verification
        - 202 empty for all other event types
        - 401 for missing/invalid signature (ADR-021)
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
```

**Important:** Preserve any existing behaviors from the current `slack_events.py` stub that the other test file `test_slack_events_stub.py` relies on. Read that test file first:
```bash
cat backend/tests/test_slack_events_stub.py
```
If `test_slack_events_stub.py` sends unsigned requests that previously returned 200/202/400, those tests will now break because they lack signatures. **That is EXPECTED and desired** — the whole point of this story is to close that auth hole. You may need to UPDATE `test_slack_events_stub.py` to add valid signatures to its requests — that is a legitimate test update driven by a spec change, NOT a Red Phase test modification.

If you update `test_slack_events_stub.py`: document the changes in your Green Phase report. The scope is narrow: add signature headers so those existing 3 tests (challenge, other event types, malformed JSON) still exercise the same code paths post-hardening.

### 3. Do NOT modify
- `backend/app/core/config.py` (005A-01 already added the Slack fields)
- `backend/app/core/encryption.py`
- `backend/app/api/routes/slack_oauth.py` (will be created by 005A-03 in its own worktree)
- Any frontend file

## Test Runner
Use the full path to the main-repo venv (worktrees don't have their own `.venv`):
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest tests/test_slack_events_signed.py -v 2>&1 | tail -40
```
Then full suite:
```bash
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest -v 2>&1 | tail -50
```
(`cd backend` first.)

## Success Criteria
- `tests/test_slack_events_signed.py` — **8 passed**
- Full backend suite — all tests passing (44 from before 005A-01 + 8 new from this story = 52+). If `test_slack_events_stub.py` tests break, update them to add valid signatures (documented above).
- `TODO(S-04)` removed from `slack_events.py`

## Report
Write `.vbounce/reports/STORY-005A-02-dev-green.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-02"
agent: "developer"
phase: "green"
status: "implementation-complete"
files_modified:
  - { path: "backend/app/core/slack.py", change: "add verify_slack_signature helper" }
  - { path: "backend/app/api/routes/slack_events.py", change: "signature guard + remove TODO(S-04)" }
  - { path: "backend/tests/test_slack_events_stub.py", change: "add valid signatures to existing tests (if needed)" }
test_result: "8 passed (new), N passed (full suite)"
correction_tax_pct: <>
flashcards_flagged: []
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```

## Critical Rules
- **No test modifications** to `test_slack_events_signed.py`. You MAY update `test_slack_events_stub.py` since it's pre-existing and the behavior genuinely changed.
- **Constant-time HMAC comparison only** (`hmac.compare_digest`). No `==` on signature bytes.
- **Never log** the raw body, full signature, or `slack_signing_secret`. Only log the classification (`expired` / `malformed` / `mismatch`).
- **No gold-plating** — no rate limiting, no audit trail, no metrics.
- **No slack_bolt middleware** — spec §1.3 explicitly excludes it. Use the hand-rolled helper.
