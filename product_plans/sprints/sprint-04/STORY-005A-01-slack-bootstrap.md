---
story_id: "STORY-005A-01-slack-bootstrap"
parent_epic_ref: "EPIC-005-phase-a"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1, §4.4 / Codebase / User Input"
actor: "Developer Agent"
complexity_label: "L2"
---

# STORY-005A-01: Slack Bootstrap — Encryption + Config + Slack Client Scaffold

**Complexity: L2** — Standard, 4 files, known pattern (copy-then-strip encryption, pydantic-settings extension, Bolt `AsyncApp` singleton).

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement
This story bootstraps the shared Slack-and-encryption infrastructure that every downstream Phase A story depends on. Without it, nothing else can land: the events signing story needs `SLACK_SIGNING_SECRET` in `Settings`, the install URL story needs the Slack `AsyncApp` + `SLACK_CLIENT_ID`, and the callback story needs `encrypt()` for the bot token.

### 1.2 Detailed Requirements

- **Req 1 — Config vars:** Declare the following fields on `Settings` in `backend/app/core/config.py`, all read from `.env`:
  - `slack_client_id: str`
  - `slack_client_secret: str`
  - `slack_signing_secret: str`
  - `slack_redirect_url: str` (should equal `https://teemo.soula.ge/api/slack/oauth/callback` in production)
  - `teemo_encryption_key: str` (32-byte urlsafe base64; decoded to raw bytes at use-site)
- **Req 2 — Startup validator:** On `Settings` instantiation, validate that `base64.urlsafe_b64decode(teemo_encryption_key)` produces exactly 32 bytes. Raise `ValueError("TEEMO_ENCRYPTION_KEY must decode to 32 bytes (got N)")` on failure. Use a pydantic `field_validator` or `@model_validator(mode="after")`.
- **Req 3 — Encryption module:** Create `backend/app/core/encryption.py` exposing two functions:
  - `encrypt(plaintext: str) -> str` — returns `base64.urlsafe_b64encode(nonce || ciphertext)` where `nonce` is 12 random bytes from `os.urandom(12)` and `ciphertext` is produced by `cryptography.hazmat.primitives.ciphers.aead.AESGCM.encrypt(nonce, plaintext.encode(), associated_data=None)`.
  - `decrypt(ciphertext_b64: str) -> str` — reverses the above. Raises `cryptography.exceptions.InvalidTag` on tamper (let it propagate; do not catch).
  - Both functions load the key lazily via `get_settings().teemo_encryption_key` → decode → pass to `AESGCM(key)`. Do NOT cache an `AESGCM` instance at module load time — settings are loaded lazily per FLASHCARDS.md singleton pattern.
- **Req 4 — Slack client scaffold:** Create `backend/app/core/slack.py` exposing `get_slack_app() -> slack_bolt.async_app.AsyncApp`, constructed once via `@lru_cache(maxsize=1)` pattern (mirrors `backend/app/core/db.py::get_supabase`). Constructor args: `token=None` (no default token — tokens are per-team), `signing_secret=settings.slack_signing_secret`, `token_verification_enabled=False` (we're not acting as a bot yet, just using the app for OAuth URL building + signing). This module is the **single import point** for the Slack SDK — downstream stories must import from here, never directly from `slack_bolt` / `slack_sdk`.
- **Req 5 — No logging of secrets:** The startup log line may print the key **fingerprint** (first 8 chars of `hashlib.sha256(decoded_key).hexdigest()`) but MUST NOT print the key itself, `slack_client_secret`, or `slack_signing_secret`.

### 1.3 Out of Scope
- The `/api/slack/install` and `/api/slack/oauth/callback` routes — STORY-005A-03 + STORY-005A-04.
- Signing-secret verification of `/api/slack/events` — STORY-005A-02.
- Any Slack Web API call — STORY-005A-04.
- BYOK key encryption — EPIC-004 (Release 2), even though it will reuse `encryption.py` unchanged.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: Slack Bootstrap Infrastructure

  Scenario: encryption roundtrip
    Given TEEMO_ENCRYPTION_KEY is a valid 32-byte base64 string
    When encrypt("hello world") is called
    And the returned ciphertext is passed to decrypt()
    Then decrypt() returns "hello world"
    And the ciphertext is NOT equal to the plaintext
    And the ciphertext changes on every encrypt() call (nonce is fresh)

  Scenario: tamper detection
    Given a ciphertext produced by encrypt("secret")
    When a single byte of the ciphertext is flipped
    Then decrypt() raises cryptography.exceptions.InvalidTag

  Scenario: invalid encryption key at startup
    Given TEEMO_ENCRYPTION_KEY is "too-short"
    When Settings is instantiated
    Then it raises ValueError matching "32 bytes"

  Scenario: Slack client scaffold loads
    Given all Slack env vars are set
    When get_slack_app() is called twice
    Then the same AsyncApp instance is returned (singleton)
    And its signing_secret matches settings.slack_signing_secret

  Scenario: Secrets never printed at startup
    Given the app starts successfully
    When the startup log is captured
    Then it contains a key fingerprint line like "enc key fp: <8-hex-chars>"
    And it does NOT contain the raw key or slack_client_secret
```

### 2.2 Verification Steps (Manual)
- [ ] `cd backend && uv run pytest tests/test_encryption.py tests/test_slack_config.py -v` — all green.
- [ ] `cd backend && uv run uvicorn app.main:app --reload` — starts without errors; startup log shows `enc key fp:` line.
- [ ] `grep -rE "(slack_client_secret|teemo_encryption_key)" backend/app/ backend/tests/` — confirm secrets never appear in log strings.

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `.env` must already contain `SLACK_CLIENT_ID`, `SLACK_CLIENT_SECRET`, `SLACK_SIGNING_SECRET`, `SLACK_REDIRECT_URL` (all 4 already present per Explorer finding 2026-04-12). Need to **ADD `TEEMO_ENCRYPTION_KEY`** — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` and paste into `.env` AND Coolify. | [ ] |
| **Services Running** | None (unit-test only). | [ ] |
| **Dependencies** | `cryptography==46.0.7` (already installed), `slack-bolt==1.28.0` (already in `pyproject.toml`). | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_encryption.py` with: roundtrip, tamper detection (flip byte, assert `InvalidTag`), wrong-key-mocked-via-monkeypatch decrypt fails.
- Create `backend/tests/test_slack_config.py` with: valid 32-byte key loads, short key raises `ValueError`, non-base64 key raises, startup fingerprint line format.
- Follow existing pattern in `backend/tests/test_auth_routes.py` for fixtures (use `monkeypatch.setenv` to swap env vars per test).

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `backend/app/core/encryption.py` (NEW), `backend/app/core/slack.py` (NEW), `backend/app/core/config.py` (MODIFY) |
| **Related Files** | `backend/app/core/db.py` (read only — singleton pattern reference), `backend/app/core/security.py` (read only — PyJWT pattern reference), `.env` (MODIFY — add `TEEMO_ENCRYPTION_KEY`) |
| **New Test Files** | `backend/tests/test_encryption.py`, `backend/tests/test_slack_config.py` |
| **ADR References** | ADR-002 (AES-256-GCM via cryptography.AESGCM), ADR-010 (Slack bot token encrypted at rest) |
| **First-Use Pattern** | **Yes** — `cryptography.hazmat.primitives.ciphers.aead.AESGCM` and `slack_bolt.async_app.AsyncApp` are new to this codebase. Check FLASHCARDS.md before implementing. After merge, add a flashcard if any gotcha surfaces. |

### 3.3 Technical Logic

**`encryption.py` skeleton:**
```python
import base64, hashlib, os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import get_settings

def _key() -> bytes:
    return base64.urlsafe_b64decode(get_settings().teemo_encryption_key)

def encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.urlsafe_b64encode(nonce + ct).decode()

def decrypt(ciphertext_b64: str) -> str:
    blob = base64.urlsafe_b64decode(ciphertext_b64)
    nonce, ct = blob[:12], blob[12:]
    return AESGCM(_key()).decrypt(nonce, ct, None).decode()

def key_fingerprint() -> str:
    return hashlib.sha256(_key()).hexdigest()[:8]
```

**`config.py` changes (pydantic-settings v2 style — match existing file):**
- Add the 5 fields as `str` with no default (fail loud if missing).
- Add `@model_validator(mode="after")` that calls `base64.urlsafe_b64decode(self.teemo_encryption_key)` and checks `len(...) == 32`.
- Import `get_settings` is already `@lru_cache(maxsize=1)` cached — no changes needed there.

**`slack.py` skeleton:**
```python
from functools import lru_cache
from slack_bolt.async_app import AsyncApp
from app.core.config import get_settings

@lru_cache(maxsize=1)
def get_slack_app() -> AsyncApp:
    s = get_settings()
    return AsyncApp(
        token=None,
        signing_secret=s.slack_signing_secret,
        token_verification_enabled=False,
    )
```

**Startup fingerprint log:** Add in `backend/app/main.py` lifespan startup handler (or app factory module-level if that's the current pattern):
```python
from app.core.encryption import key_fingerprint
logger.info("enc key fp: %s", key_fingerprint())
```

### 3.4 API Contract
N/A — this story introduces no HTTP routes.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 5 | roundtrip, tamper, short key, non-base64 key, slack singleton |
| Component tests | 0 — N/A (no UI in scope) | |
| E2E / acceptance | 0 — N/A (bootstrap story, no user flow) | |
| Integration tests | 0 — N/A (no DB or HTTP in scope) | |

### 4.2 Definition of Done
- [ ] TDD Red phase — all 5 tests written failing, then implementation makes them green.
- [ ] §4.1 counts met.
- [ ] FLASHCARDS.md consulted (first-use pattern: `AESGCM`, `slack_bolt.AsyncApp`).
- [ ] No ADR violations.
- [ ] `.env` has `TEEMO_ENCRYPTION_KEY`; DevOps adds it to Coolify before release merge.
- [ ] Backend starts locally without errors; startup log shows `enc key fp:` line.
- [ ] No secret strings in logs (grep check).

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
