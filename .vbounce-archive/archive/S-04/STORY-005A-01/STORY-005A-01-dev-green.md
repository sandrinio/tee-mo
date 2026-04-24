---
task_id: "STORY-005A-01-dev-green"
story_id: "STORY-005A-01"
phase: "green"
agent: "developer"
worktree: ".worktrees/STORY-005A-01/"
sprint: "S-04"
---

# Developer Task — STORY-005A-01 Green Phase

## Working Directory
**You MUST operate inside** `/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/`

All `Read`, `Edit`, `Write`, and `Bash` calls must be rooted at that path. Do NOT touch the main checkout.

## Phase
**GREEN PHASE — Implement code to make the Red Phase tests pass.** Then refactor for clarity without breaking tests. **You MUST NOT modify the test files.**

## Red Phase Summary
8 tests were written in:
- `backend/tests/test_encryption.py` (4 tests)
- `backend/tests/test_slack_config.py` (4 tests)

Red Phase result: `0 passed, 0 failed, 2 collection errors` — both files fail at import because:
1. `app.core.encryption` does not exist
2. `app.core.config.get_settings` does not exist (spec §3.3 assumed it did; it does not)

Full Red Phase report: `.worktrees/STORY-005A-01/.vbounce/reports/STORY-005A-01-dev-red.md`

## Mandatory Reading (before writing any code)
1. `.worktrees/STORY-005A-01/FLASHCARDS.md`
2. `.worktrees/STORY-005A-01/.vbounce/sprint-context-S-04.md`
3. `.worktrees/STORY-005A-01/product_plans/sprints/sprint-04/STORY-005A-01-slack-bootstrap.md` — full spec
4. `.worktrees/STORY-005A-01/.vbounce/reports/STORY-005A-01-dev-red.md` — Red Phase report with context
5. `.worktrees/STORY-005A-01/backend/tests/test_encryption.py` — READ ONLY, do NOT modify
6. `.worktrees/STORY-005A-01/backend/tests/test_slack_config.py` — READ ONLY, do NOT modify
7. `.worktrees/STORY-005A-01/backend/app/core/config.py` — the file you will extend
8. `.worktrees/STORY-005A-01/backend/app/core/db.py` — reference pattern for `@lru_cache` singleton

## Spec Correction — `get_settings()` must be ADDED
The story spec §3.3 says *"Import `get_settings` is already `@lru_cache(maxsize=1)` cached — no changes needed there."* **That is wrong.** The current `backend/app/core/config.py` only exposes a module-level `settings = Settings()` at line 68. There is NO `get_settings()` function.

**You MUST add:**
```python
from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton. Tests can flush via get_settings.cache_clear()."""
    return Settings()
```

Keep the existing `settings = Settings()` at line 68 for backward compatibility if any other module imports it directly — OR (cleaner) change line 68 to `settings = get_settings()` so it stays a drop-in alias. Check with grep before deciding:
```bash
grep -rn "from app.core.config import settings" backend/app/ backend/tests/
```
If any matches exist, keep the alias. If none, you can collapse to just `get_settings()`.

## Files to Create / Modify

### 1. MODIFY `backend/app/core/config.py`
- Add 5 new fields on `Settings`:
  - `slack_client_id: str`
  - `slack_client_secret: str`
  - `slack_signing_secret: str`
  - `slack_redirect_url: str`
  - `teemo_encryption_key: str`
  - All required (no defaults) — fail loud if missing from env.
- Add a `@model_validator(mode="after")` that decodes `teemo_encryption_key` as `base64.urlsafe_b64decode(...)` and checks `len(decoded) == 32`. On failure, raise `ValueError("TEEMO_ENCRYPTION_KEY must decode to 32 bytes (got N)")`. Pydantic will wrap this into `ValidationError` — that's fine, the tests catch both.
- Handle the non-base64 case: catch `(binascii.Error, ValueError)` around the decode, re-raise as `ValueError("TEEMO_ENCRYPTION_KEY must decode to 32 bytes (got invalid base64: <msg>)")`. The test asserts the message contains one of `32 bytes`, `base64`, `decode`, or `Invalid`.
- Add the `@lru_cache(maxsize=1)` `get_settings()` function.

### 2. CREATE `backend/app/core/encryption.py`
Follow spec §3.3 skeleton exactly:
```python
"""AES-256-GCM encryption helper for Slack bot tokens (ADR-002, ADR-010).

Exports:
    - encrypt(plaintext: str) -> str
    - decrypt(ciphertext_b64: str) -> str
    - key_fingerprint() -> str

The key is loaded lazily via get_settings() per call — no module-level
AESGCM instance (see FLASHCARDS.md singleton pattern).
"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings


def _key() -> bytes:
    """Decode the configured TEEMO_ENCRYPTION_KEY to raw bytes."""
    return base64.urlsafe_b64decode(get_settings().teemo_encryption_key)


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string with AES-256-GCM and return base64url(nonce||ct)."""
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decrypt(ciphertext_b64: str) -> str:
    """Decrypt a base64url(nonce||ct) blob. Raises InvalidTag on tamper."""
    blob = base64.urlsafe_b64decode(ciphertext_b64)
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(_key()).decrypt(nonce, ct, None).decode()


def key_fingerprint() -> str:
    """Return the first 8 hex chars of sha256(decoded_key). Safe to log."""
    return hashlib.sha256(_key()).hexdigest()[:8]
```

### 3. CREATE `backend/app/core/slack.py`
```python
"""Slack Bolt AsyncApp singleton — single import point for slack_bolt.

Downstream stories must import from here, never directly from slack_bolt.
"""
from functools import lru_cache

from slack_bolt.async_app import AsyncApp

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_slack_app() -> AsyncApp:
    """Return the shared AsyncApp instance (constructed once per process)."""
    s = get_settings()
    return AsyncApp(
        token=None,
        signing_secret=s.slack_signing_secret,
        token_verification_enabled=False,
    )
```

### 4. MODIFY `backend/app/main.py`
Add the startup fingerprint log line. Check where the lifespan / app init lives:
```bash
grep -nE "lifespan|startup|logger.info" backend/app/main.py
```
Add near existing startup logs:
```python
from app.core.encryption import key_fingerprint
# ... inside startup:
logger.info("enc key fp: %s", key_fingerprint())
```
**Do NOT** log the raw key, `slack_client_secret`, `slack_signing_secret`, or `teemo_encryption_key` anywhere.

## Environment Note — Worktree `.env`
The Red Phase Dev agent created a symlink at `<worktree-root>/.env` → main repo `.env`. This is REQUIRED for tests to collect. Verify it still exists:
```bash
ls -la /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/.env
```
If it is missing, recreate the symlink:
```bash
ln -s /Users/ssuladze/Documents/Dev/SlaXadeL/.env /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/.env
```
Do NOT commit the symlink — `.env` is in `.gitignore` and the symlink inherits that.

## Test Run — Success Criteria
After implementation, run from the worktree:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/backend
uv run pytest tests/test_encryption.py tests/test_slack_config.py -v 2>&1 | tail -40
```
**Must show: 8 passed.**

Then run the FULL existing backend test suite to ensure no regressions:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/backend
uv run pytest -v 2>&1 | tail -50
```
**Must show: no failures in previously-passing tests.** If the existing test suite touches `settings` (module-level singleton), your `get_settings()` addition must not break it.

## Manual Verification
Per spec §2.2, verify:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/backend
uv run uvicorn app.main:app --reload 2>&1 | head -30 &
# Wait 3 seconds, check the log for "enc key fp: aecf7b12" (or whatever the real fingerprint is)
# Then kill the process
```
Actually, prefer a non-server approach to avoid port conflicts:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/backend
uv run python -c "
from app.core.encryption import key_fingerprint
print('enc key fp:', key_fingerprint())
"
```
Expected: `enc key fp: aecf7b12` (the fingerprint recorded in sprint state.json for the real key).

Also verify no secrets leak to logs:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01
grep -rE "(slack_client_secret|teemo_encryption_key)" backend/app/ | grep -v "config.py" | grep -v "test_"
```
This should return NO log/print statements with those literal strings (only the Settings field definitions and test code should match).

## Critical Rules
- **No test modifications.** Only the Team Lead may fix test files between phases. If you find a broken test, STOP and write a blockers report.
- **No gold-plating.** Do not add BYOK key handling, per-provider namespaces, rotation helpers, key caching, or anything the spec doesn't list.
- **No slack_sdk imports outside `slack.py`.** Downstream stories import `from app.core.slack import get_slack_app` — respect the single-import-point rule.
- **Docstrings on every new export** (encryption.py functions, slack.py function, get_settings function). Per sprint context.
- **Do not touch** `slack_events.py`, `slack_oauth.py`, `models/slack.py`, or frontend files. Those belong to later stories.

## Report Requirements
Write an Implementation Report to `.worktrees/STORY-005A-01/.vbounce/reports/STORY-005A-01-dev-green.md` with YAML frontmatter:
```yaml
---
story_id: "STORY-005A-01"
agent: "developer"
phase: "green"
status: "implementation-complete"
files_modified:
  - { path: "backend/app/core/config.py", change: "add 5 Slack fields + validator + get_settings" }
  - { path: "backend/app/core/encryption.py", change: "NEW — AES-256-GCM helpers" }
  - { path: "backend/app/core/slack.py", change: "NEW — AsyncApp singleton" }
  - { path: "backend/app/main.py", change: "log enc key fingerprint at startup" }
test_result: "8 passed (005A-01), N passed (full suite)"
correction_tax_pct: <your self-assessed %>
flashcards_flagged:
  - <any gotchas or first-use patterns worth recording>
input_tokens: <from vbounce.tokens if available>
output_tokens: <>
total_tokens: <>
---
```
Body: implementation summary, test results, any deviations from spec, flashcards flagged, open questions.

## Out-of-Scope Reminder
Do NOT:
- Create `slack_oauth.py`, `slack_events.py`, `models/slack.py` (other stories)
- Touch `frontend/`
- Add BYOK, AI Apps, AsyncAssistant, thread metadata
- Modify test files
- Touch unrelated files (typing, formatting, etc.) — only the 4 files listed above
