---
task_id: "STORY-005A-01-dev-red"
story_id: "STORY-005A-01"
phase: "red"
agent: "developer"
worktree: ".worktrees/STORY-005A-01/"
sprint: "S-04"
---

# Developer Task — STORY-005A-01 Red Phase

## Working Directory
**You MUST operate inside** `/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/`

Every `Read`, `Edit`, `Write`, and `Bash` call must be rooted at that path. Do NOT touch files in `/Users/ssuladze/Documents/Dev/SlaXadeL/` (the main checkout) — it is on a different branch.

## Phase
**RED PHASE — Tests ONLY.** Do NOT write implementation code. Do NOT create `encryption.py` or `slack.py` or modify `config.py`. Exit the moment the test files exist and the test run shows them failing/erroring for the expected reason (missing modules).

## Story Spec
Read: `.worktrees/STORY-005A-01/product_plans/sprints/sprint-04/STORY-005A-01-slack-bootstrap.md`

The §1 Spec, §2.1 Gherkin, and §3 Implementation Guide are your ground truth. You MUST cover all 5 Gherkin scenarios as tests.

## Mandatory Reading (before writing any test)
1. `.worktrees/STORY-005A-01/FLASHCARDS.md` — especially the Supabase factory pattern, samesite=lax cookie decision, and any entries tagged `encryption` / `slack`.
2. `.worktrees/STORY-005A-01/.vbounce/sprint-context-S-04.md` — Sprint-wide rules. Locked dependencies, out-of-scope fences, and the canonical AESGCM/httpx/Settings patterns.
3. `.worktrees/STORY-005A-01/backend/tests/test_auth_routes.py` — existing test style reference for `monkeypatch.setenv` fixture pattern.
4. `.worktrees/STORY-005A-01/backend/app/core/db.py` — existing `@lru_cache` singleton pattern that `slack.py` will mirror.
5. `.worktrees/STORY-005A-01/backend/app/core/config.py` — read before writing the Settings test so you understand the existing pydantic-settings v2 style.

## Test Files to Create

### 1. `backend/tests/test_encryption.py`
Must cover:
- **Roundtrip** — `encrypt("hello world")` then `decrypt(...)` returns `"hello world"`. Assert ciphertext ≠ plaintext AND two consecutive `encrypt()` calls on the same plaintext produce different ciphertexts (nonce freshness).
- **Tamper detection** — `encrypt("secret")`, base64-decode, flip one byte of the ciphertext portion (NOT the nonce prefix), base64-encode, call `decrypt()` → expect `cryptography.exceptions.InvalidTag`.
- **Wrong key** — use `monkeypatch` to swap `TEEMO_ENCRYPTION_KEY` between encrypt and decrypt (clear the `get_settings()` lru_cache in between). Expect `InvalidTag`.

### 2. `backend/tests/test_slack_config.py`
Must cover:
- **Valid 32-byte key loads** — Settings instantiates, no exception. Access `settings.slack_client_id`, `slack_client_secret`, `slack_signing_secret`, `slack_redirect_url`, `teemo_encryption_key` — all present.
- **Short key raises `ValueError`** — `monkeypatch.setenv("TEEMO_ENCRYPTION_KEY", "too-short")`, force a fresh `Settings()` import (clear `get_settings` cache), expect `ValueError` with `"32 bytes"` substring in the message.
- **Non-base64 key raises** — set key to `"!!!not-base64!!!"`, expect `ValueError` (either from the validator or from the `urlsafe_b64decode` call — whichever surfaces first; match on either `"32 bytes"` or `"base64"` / `"decode"` substring).
- **Slack singleton** — `from app.core.slack import get_slack_app`, call twice, assert `is` identity. Assert `.signing_secret` (or equivalent AsyncApp attribute — check slack_bolt source if unsure) equals `settings.slack_signing_secret`. If the attribute isn't directly readable, at minimum assert the same object instance is returned.
- **Startup fingerprint log format** — simplest form: import `key_fingerprint` from `app.core.encryption`, assert it returns an 8-char hex string (`re.match(r"[0-9a-f]{8}$", fp)`) and does NOT contain any part of the raw key or `SLACK_CLIENT_SECRET`. (The actual startup log line can be verified in a separate integration test — keep this test scope narrow to the helper.)

## Critical Rules
- **You MUST NOT write `backend/app/core/encryption.py`, `backend/app/core/slack.py`, or modify `backend/app/core/config.py`.** Red phase is tests-only.
- All tests MUST fail initially (ModuleNotFoundError or AttributeError are acceptable failure modes for red phase — they prove tests import the targets that don't exist yet).
- Use `monkeypatch.setenv` + cache-clearing, NOT global state mutations.
- Follow the existing pytest style in `backend/tests/test_auth_routes.py`. Match conftest fixtures if any exist.
- **No out-of-scope additions** — do not write tests for `/api/slack/install`, callback, or events routes. Those belong to other stories.

## Environment Check
Before writing tests, verify the `.env` file at the worktree root has `TEEMO_ENCRYPTION_KEY` set. If it's missing, STOP and write a Blockers Report — do NOT generate a new key yourself (the real key is already in the root `.env` per PREREQ 3a).

```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01
grep -c "^TEEMO_ENCRYPTION_KEY=" .env || echo "MISSING"
```

## After Writing Tests
1. Run the test suite from the worktree:
   ```bash
   cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-01/backend
   uv run pytest tests/test_encryption.py tests/test_slack_config.py -v 2>&1 | tail -40
   ```
2. Confirm all tests FAIL (expected — no implementation yet). Record exact failure counts.
3. Write a Red Phase report to `.worktrees/STORY-005A-01/.vbounce/reports/STORY-005A-01-dev-red.md` with YAML frontmatter:
   ```yaml
   ---
   story_id: "STORY-005A-01"
   agent: "developer"
   phase: "red"
   status: "tests-written"
   test_files: [list of relative paths]
   test_count: N
   test_run_result: "X failed, 0 passed (expected)"
   ---
   ```
   Then a short body: which files you created, which scenario each test covers, and any open questions for the Team Lead.

## Out-of-Scope Reminder
Do NOT touch:
- `backend/app/api/routes/slack_oauth.py` (doesn't exist yet; STORY-005A-03 creates it)
- `backend/app/api/routes/slack_events.py` (exists as stub; STORY-005A-02 hardens it)
- `backend/app/models/slack.py` (doesn't exist yet; STORY-005A-03 creates it)
- `frontend/*` (STORY-005A-06 only)
- BYOK, AI Apps, AsyncAssistant, thread metadata
