---
task_id: "STORY-005A-02-dev-red"
story_id: "STORY-005A-02"
phase: "red"
agent: "developer"
worktree: ".worktrees/STORY-005A-02/"
sprint: "S-04"
---

# Developer Task — STORY-005A-02 Red Phase

## Working Directory
**You MUST operate inside** `/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-02/`

Do NOT touch `/Users/ssuladze/Documents/Dev/SlaXadeL/` (the main checkout — it's `sprint/S-04` and must stay clean while you work).

**Parallel sibling:** STORY-005A-03 is running in parallel at `.worktrees/STORY-005A-03/`. You will NOT see its changes. Your only dependency is STORY-005A-01 (already merged into `sprint/S-04` — encryption.py, slack.py, config.py with 5 Slack fields, `get_settings()`).

## Phase
**RED PHASE — Tests ONLY.** Do NOT write implementation code. Do NOT modify `backend/app/core/slack.py` to add `verify_slack_signature`. Do NOT modify `backend/app/api/routes/slack_events.py`. Exit the moment the test file exists and the test run shows it failing for the expected reason (missing `verify_slack_signature` helper).

## Story Spec
Read: `.worktrees/STORY-005A-02/product_plans/sprints/sprint-04/STORY-005A-02-events-signing-verification.md`

§1 Spec, §2.1 Gherkin (6 scenarios), and §3 Implementation Guide are ground truth.

## Mandatory Reading (before writing any test)
1. `.worktrees/STORY-005A-02/FLASHCARDS.md` — full file.
2. `.worktrees/STORY-005A-02/.vbounce/sprint-context-S-04.md` — sprint-wide rules, out-of-scope fences.
3. `.worktrees/STORY-005A-02/backend/app/core/slack.py` — NOTE: currently only has `get_slack_app()` (from 005A-01). The `verify_slack_signature` function is what you're writing tests FOR.
4. `.worktrees/STORY-005A-02/backend/app/api/routes/slack_events.py` — current stub (with `TODO(S-04)` at line ~24). Do NOT modify; understand the existing url_verification/202 shape.
5. `.worktrees/STORY-005A-02/backend/tests/test_slack_events_stub.py` — existing stub-level tests. Match this file's style.
6. `.worktrees/STORY-005A-02/backend/tests/test_auth_routes.py` — reference for `TestClient` pattern.

## Test File to Create

**`backend/tests/test_slack_events_signed.py`**

Must cover all 6 Gherkin scenarios from §2.1, plus 2 unit-level tests for `verify_slack_signature` itself (per §4.1):

**Unit tests (direct calls to `from app.core.slack import verify_slack_signature`):**
1. **Happy path** — valid signing secret + body + timestamp + correct HMAC signature → returns `True`.
2. **Tampered body** — valid signature for original body, then call with modified body → returns `False`.

**Integration tests (TestClient → `/api/slack/events`):**
3. **Valid signed url_verification → 200 + challenge echo (plain text)**
4. **Missing X-Slack-Signature header → 401 + body mentions "invalid slack signature"**
5. **Tampered body → 401**
6. **Expired timestamp (301 seconds old) → 401**
7. **Valid signed app_mention event_callback → 202 empty body**
8. **Raw body NOT logged on 401, "slack signature rejected" IS logged** — use `caplog` fixture.

Use this helper at the top of the test file (mirroring the 2026-04-12 live simulation):
```python
import hashlib, hmac, time, json

def compute_v0_sig(secret: str, body: bytes, timestamp: str) -> str:
    base = f"v0:{timestamp}:{body.decode()}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
```

## Critical Rules
- **DO NOT modify** `backend/app/core/slack.py` (add helper = implementation work = Green Phase).
- **DO NOT modify** `backend/app/api/routes/slack_events.py` (hardening = implementation = Green Phase).
- **DO NOT touch** `slack_oauth.py`, `encryption.py`, frontend, or anything outside the 1 new test file.
- All tests MUST fail on first run (ImportError for `verify_slack_signature` is the expected failure mode for the unit tests; the integration tests will produce 200s where 401s are expected).
- Use `monkeypatch.setenv("SLACK_SIGNING_SECRET", "test_secret")` + `get_settings.cache_clear()` at the top of each integration test OR use a session-scoped fixture.
- Use FastAPI `TestClient` — pattern from `backend/tests/test_auth_routes.py`.
- For the "body not logged" test, use pytest's `caplog` fixture with `caplog.set_level(logging.WARNING)`.
- For the expired-timestamp test, pass `timestamp = str(int(time.time()) - 301)` and use the real HMAC for that old timestamp — the rejection should be `reason=expired`, not `reason=mismatch`.

## Environment Check
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-02
ls -la .env   # must show the symlink → main .env (Team Lead created it)
grep -c "^SLACK_SIGNING_SECRET=" .env || echo "MISSING"
grep -c "^TEEMO_ENCRYPTION_KEY=" .env || echo "MISSING"
```
Both must be present. If not, STOP and write a blockers report.

## After Writing Tests
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-02/backend
.venv/bin/pytest tests/test_slack_events_signed.py -v 2>&1 | tail -40
# (use .venv/bin/pytest — `uv` may not be on PATH)
```

Confirm all tests FAIL. Record the exact test count and failure mode.

## Report
Write `.worktrees/STORY-005A-02/.vbounce/reports/STORY-005A-02-dev-red.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-02"
agent: "developer"
phase: "red"
status: "tests-written"
test_files:
  - "backend/tests/test_slack_events_signed.py"
test_count: N
test_run_result: "X failed, 0 passed (expected — verify_slack_signature not implemented)"
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```
Body: scenario → test mapping, any blockers, open questions.

## Out-of-Scope Reminder
Do NOT touch:
- `slack_oauth.py` / `install` / `oauth/callback` / `teams` routes (stories 03/04/05)
- `models/slack.py` (story 03)
- Frontend (story 06)
- BYOK, AsyncAssistant, any Phase B event handling
- Adding new dependencies
