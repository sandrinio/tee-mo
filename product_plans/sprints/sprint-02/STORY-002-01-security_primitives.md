---
story_id: "STORY-002-01-security_primitives"
parent_epic_ref: "EPIC-002"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Charter §10 Epic Seed Map (Authentication) + Roadmap ADR-001 + FLASHCARDS.md bcrypt entry"
actor: "Backend Dev (Solo)"
complexity_label: "L1"
---

# STORY-002-01: Backend Security Primitives + bcrypt Length Guard

**Complexity: L1** — Copy `security.py` from `new_app`, add 3 JWT config fields to `config.py`, add a 72-byte password guard. 3 files touched, ~30 minutes.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".

### 1.1 User Story
> This story ships the password-hashing and JWT primitives because every subsequent auth story in EPIC-002 (register, login, refresh, `/me`) depends on having `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, and `decode_token` available as pure functions with no route coupling.

### 1.2 Detailed Requirements

- **R1**: Extend `backend/app/core/config.py` with three new settings fields, all with defaults so existing `.env` files keep working:
  - `access_token_expire_minutes: int = 15` (per Roadmap ADR-001 — 15 minutes)
  - `refresh_token_expire_days: int = 7` (per Roadmap ADR-001 — 7 days)
  - `jwt_algorithm: str = "HS256"` (Tee-Mo signs with `supabase_jwt_secret` which is a shared symmetric secret, so HS256 is the only valid choice)
- **R2**: Create `backend/app/core/security.py` containing **exactly** these five functions, copied verbatim from `/Users/ssuladze/Documents/Dev/new_app/backend/app/core/security.py` with only surface-level edits (docstrings may reference Tee-Mo instead of Chyro, but the function bodies are unchanged):
  - `hash_password(password: str) -> str` — bcrypt hash
  - `verify_password(password: str, hashed: str) -> bool` — bcrypt check
  - `create_access_token(user_id: UUID, role: str = "authenticated") -> str` — 15-min JWT
  - `create_refresh_token(user_id: UUID) -> str` — 7-day JWT with `"type": "refresh"` claim
  - `decode_token(token: str) -> dict` — PyJWT decode using `settings.supabase_jwt_secret` + `settings.jwt_algorithm`
- **R3**: Add a new function `validate_password_length(password: str) -> None` to `security.py` that raises `ValueError("password_too_long")` when `len(password.encode("utf-8")) > 72`. No other validation — email format, password strength, etc. live on the Pydantic model in STORY-002-02. **This function is the ONLY line of defense against bcrypt 5.0's ValueError on overflow, per FLASHCARDS.md `bcrypt 5.0` entry and Roadmap ADR-017.**
- **R4**: All five copied functions and the new guard MUST keep their full JSDoc/docstrings — every export is self-documenting per CLAUDE.md critical rule §6.
- **R5**: `settings.access_token_expire_minutes` and `settings.refresh_token_expire_days` are the only knobs the copied functions pull from config; the values used by the copied `create_access_token` / `create_refresh_token` match new_app 1:1 after R1 is applied, so no numeric literals need rewriting inside the copied code.
- **R6**: Add unit tests in `backend/tests/test_security.py` covering every acceptance scenario in §2.1. Use pytest (`httpx` and `fastapi.testclient` are not needed for this story — all tests are pure-function).

### 1.3 Out of Scope
- Auth routes (register/login/refresh/logout/me) — STORY-002-02.
- `get_current_user_id` FastAPI dependency — STORY-002-02.
- `models/user.py` Pydantic models — STORY-002-02.
- Any frontend work — STORY-002-03 and STORY-002-04.
- Any DB writes — this story is 100% pure functions on in-memory inputs.
- Supabase Realtime — Tee-Mo does not use Realtime; do NOT port the `setRealtimeAuth` pattern from new_app anywhere.

### TDD Red Phase: Yes
Rationale: Security primitives are high-risk and every scenario maps cleanly to a unit test. Red tests are cheap here and protect the bcrypt-72-byte boundary from regression.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Backend security primitives

  Scenario: hash_password and verify_password round-trip
    Given a plaintext password "correcthorse"
    When I hash it with hash_password
    Then the result starts with "$2b$"
    And the result is 60 characters long
    And verify_password("correcthorse", result) returns True
    And verify_password("wrong", result) returns False

  Scenario: hash_password produces different hashes for same password (salting)
    Given a plaintext password "correcthorse"
    When I hash it twice
    Then the two hashes are not equal
    And verify_password matches both independently

  Scenario: create_access_token emits a valid 15-minute JWT
    Given a user UUID "11111111-1111-1111-1111-111111111111"
    When I call create_access_token(user_uuid)
    And decode the resulting token with decode_token
    Then the payload sub equals "11111111-1111-1111-1111-111111111111"
    And the payload role equals "authenticated"
    And the payload exp is within 60 seconds of (now + 15 minutes)
    And the payload has no "type" claim

  Scenario: create_refresh_token emits a valid 7-day JWT with type claim
    Given a user UUID "22222222-2222-2222-2222-222222222222"
    When I call create_refresh_token(user_uuid)
    And decode the resulting token with decode_token
    Then the payload sub equals "22222222-2222-2222-2222-222222222222"
    And the payload type equals "refresh"
    And the payload exp is within 60 seconds of (now + 7 days)

  Scenario: decode_token raises ExpiredSignatureError on expired token
    Given a JWT signed with the same secret but with exp set 1 second in the past
    When I call decode_token on it
    Then jwt.ExpiredSignatureError is raised

  Scenario: decode_token raises InvalidTokenError on tampered signature
    Given a valid access token
    When I flip one character in the signature segment
    And call decode_token on the tampered string
    Then jwt.InvalidTokenError is raised

  Scenario: validate_password_length rejects 73-byte password
    Given a password that is exactly 73 bytes when UTF-8 encoded
    When I call validate_password_length(password)
    Then ValueError is raised with message "password_too_long"

  Scenario: validate_password_length accepts 72-byte password
    Given a password that is exactly 72 bytes when UTF-8 encoded
    When I call validate_password_length(password)
    Then no exception is raised

  Scenario: validate_password_length counts bytes, not characters
    Given a password "a" * 36 + "é" * 18
    # 36 ASCII bytes + (18 × 2 UTF-8 bytes) = 72 bytes
    When I call validate_password_length(password)
    Then no exception is raised
    Given a password "a" * 36 + "é" * 19
    # 36 + 38 = 74 bytes
    When I call validate_password_length(password)
    Then ValueError is raised with message "password_too_long"
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_security.py -v` passes all scenarios above
- [ ] `python -c "from app.core.security import hash_password, verify_password; h = hash_password('x'); print(verify_password('x', h))"` prints `True`
- [ ] `python -c "from app.core.security import create_access_token; from uuid import uuid4; print(create_access_token(uuid4()))"` prints a JWT string
- [ ] Importing `security.py` at backend boot does NOT trigger any DB connection (pure module — confirm by reading the file, no `get_supabase()` calls)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Python** | 3.11 installed; backend venv active (`backend/.venv`) | [ ] |
| **Backend deps** | `pip install -e .` already run (PyJWT==2.12.1, bcrypt==5.0.0 pinned in `backend/pyproject.toml`) | [x] |
| **Env Vars** | `.env` at project root with valid `SUPABASE_JWT_SECRET` (≥32 bytes, already validated at config import time by S-01) | [x] |
| **Services Running** | None — this story is pure functions, no network/DB | [x] |
| **Migrations** | None | [x] |

### 3.1 Test Implementation

Create `backend/tests/test_security.py`. One test function per Gherkin scenario in §2.1 (9 tests total).

Use `freezegun` if you need to verify exact `exp` values — **but** `freezegun` is NOT in `pyproject.toml` and this story does NOT add it. Instead use a ±60s tolerance (as spec'd in §2.1) comparing the decoded `exp` against `datetime.now(timezone.utc) + timedelta(...)`.

For the expired-token scenario, build the token manually with `jwt.encode` using a payload whose `exp` is `int((now - timedelta(seconds=1)).timestamp())`, sign with `settings.supabase_jwt_secret`, then call `decode_token` and assert it raises `jwt.ExpiredSignatureError`.

For the tampered-signature scenario, call `create_access_token`, split on `.`, flip a character in the third segment, rejoin, and assert `decode_token` raises `jwt.InvalidTokenError`.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/core/security.py` (new) |
| **Related Files** | `backend/app/core/config.py` (edit — add 3 fields), `backend/tests/test_security.py` (new) |
| **New Files Needed** | Yes — `security.py` and `test_security.py` |
| **ADR References** | ADR-001 (JWT strategy: 15min access + 7d refresh), ADR-017 (bcrypt 72-byte hard gate at the boundary) |
| **First-Use Pattern** | No — new_app ships a battle-tested `security.py`, we are copying it verbatim. Reference source: `/Users/ssuladze/Documents/Dev/new_app/backend/app/core/security.py` |

### 3.3 Technical Logic

**Step 1 — Extend `backend/app/core/config.py`:**

Add these three fields to the `Settings` class (after `supabase_jwt_secret`, before `cors_origins_list`):

```python
# JWT settings — ADR-001 + Roadmap §3
access_token_expire_minutes: int = 15
refresh_token_expire_days: int = 7
jwt_algorithm: str = "HS256"
```

Do NOT touch the existing `>= 32 bytes` secret validator. Do NOT rename any existing fields.

**Step 2 — Create `backend/app/core/security.py`:**

Copy the entire file from `/Users/ssuladze/Documents/Dev/new_app/backend/app/core/security.py`. The five functions (`hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token`) are lawful copies — do NOT edit their bodies. You MAY:
- Edit the module docstring to say "Tee-Mo" instead of "Chyro".
- Edit function docstring references from `chy_users` to `teemo_users`.
- Remove ADR-008/ADR-018 references in comments and replace with ADR-001.

Then append the new guard function at the end of the file:

```python
# ---------------------------------------------------------------------------
# Password length guard (Roadmap ADR-017, FLASHCARDS.md bcrypt 5.0 entry)
# ---------------------------------------------------------------------------


def validate_password_length(password: str) -> None:
    """
    Reject passwords longer than 72 bytes before they reach bcrypt.

    bcrypt 5.0 (pinned in backend/pyproject.toml) raises ValueError on
    passwords longer than 72 bytes — unlike bcrypt 4.x which silently
    truncated. This guard converts that failure into a controlled exception
    that the auth route (STORY-002-02) can catch and return as HTTP 422
    with detail ``password_too_long``.

    This function intentionally validates bytes, not characters, because
    bcrypt's limit is a byte limit (UTF-8 multi-byte characters like "é"
    each consume 2 bytes).

    Args:
        password: The plaintext password supplied by the user.

    Raises:
        ValueError: With message ``"password_too_long"`` when the UTF-8
            byte length of the password exceeds 72.
    """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("password_too_long")
```

**Step 3 — Write the test file `backend/tests/test_security.py`:**

Keep tests in a single file. Import from `app.core.security`. Use `uuid.uuid4()` and `uuid.UUID("11111111-...")` for fixture UUIDs. Use `datetime.now(timezone.utc)` for time comparisons with a ±60s window.

Sample skeleton — fill in the remaining scenarios:

```python
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_length,
    verify_password,
)


def test_hash_and_verify_roundtrip():
    h = hash_password("correcthorse")
    assert h.startswith("$2b$")
    assert len(h) == 60
    assert verify_password("correcthorse", h) is True
    assert verify_password("wrong", h) is False


def test_hash_password_is_salted():
    h1 = hash_password("correcthorse")
    h2 = hash_password("correcthorse")
    assert h1 != h2
    assert verify_password("correcthorse", h1)
    assert verify_password("correcthorse", h2)


def test_access_token_has_15_minute_expiry():
    uid = UUID("11111111-1111-1111-1111-111111111111")
    token = create_access_token(uid)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "authenticated"
    assert "type" not in payload
    expected_exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    assert abs(payload["exp"] - int(expected_exp.timestamp())) < 60


def test_refresh_token_has_7_day_expiry_and_type_claim():
    uid = UUID("22222222-2222-2222-2222-222222222222")
    token = create_refresh_token(uid)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["type"] == "refresh"
    expected_exp = datetime.now(timezone.utc) + timedelta(days=7)
    assert abs(payload["exp"] - int(expected_exp.timestamp())) < 60


def test_decode_token_rejects_expired_token():
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "11111111-1111-1111-1111-111111111111",
        "iat": int((now - timedelta(minutes=30)).timestamp()),
        "exp": int((now - timedelta(seconds=1)).timestamp()),
    }
    token = jwt.encode(payload, settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


def test_decode_token_rejects_tampered_signature():
    token = create_access_token(uuid4())
    head, body, sig = token.split(".")
    tampered = f"{head}.{body}.{sig[:-1]}{'A' if sig[-1] != 'A' else 'B'}"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)


def test_validate_password_length_rejects_73_bytes():
    with pytest.raises(ValueError, match="password_too_long"):
        validate_password_length("a" * 73)


def test_validate_password_length_accepts_72_bytes():
    validate_password_length("a" * 72)  # must not raise


def test_validate_password_length_counts_utf8_bytes():
    # 36 ASCII + 36 bytes of "é" (18 × 2) = 72 bytes — OK
    validate_password_length("a" * 36 + "é" * 18)
    # 36 ASCII + 38 bytes of "é" (19 × 2) = 74 bytes — reject
    with pytest.raises(ValueError, match="password_too_long"):
        validate_password_length("a" * 36 + "é" * 19)
```

### 3.4 API Contract

N/A — this story exposes no HTTP endpoint. All consumers are internal Python imports.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 9 | One per Gherkin scenario in §2.1 |
| Component tests | 0 — N/A (backend story) | |
| E2E / acceptance tests | 0 — N/A (no HTTP surface in this story) | |
| Integration tests | 0 — N/A (no external services) | |

### 4.2 Definition of Done
- [ ] TDD Red phase: all 9 tests written and verified failing (ImportError is fine for Red) before implementation.
- [ ] Green phase: all 9 tests pass.
- [ ] `backend/app/core/security.py` exists with the 5 copied functions + `validate_password_length`.
- [ ] `backend/app/core/config.py` has the 3 new JWT fields with defaults.
- [ ] FLASHCARDS.md `bcrypt 5.0` entry consulted — `validate_password_length` enforces the 72-byte rule as described.
- [ ] No ADR violations (ADR-001 JWT expiry values match; ADR-017 byte-length guard present).
- [ ] Every exported function has a docstring.
- [ ] No new dependencies added to `pyproject.toml`.
- [ ] `backend/tests/test_security.py` runs in isolation (no DB, no network, no `get_supabase()` import).

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer (Red) | 10 | 2566 | 2576 |
