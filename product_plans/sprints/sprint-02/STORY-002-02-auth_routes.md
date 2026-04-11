---
story_id: "STORY-002-02-auth_routes"
parent_epic_ref: "EPIC-002"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Charter §10 Epic Seed Map (Authentication) + Roadmap ADR-001 + new_app auth.py"
actor: "Backend Dev (Solo)"
complexity_label: "L2"
---

# STORY-002-02: Auth Routes + httpOnly Cookies + `get_current_user_id` Dep

**Complexity: L2** — Copy + strip the 5 auth endpoints from `new_app/backend/app/api/routes/auth.py`, create a minimal `models/user.py`, port `get_current_user_id` from `new_app/backend/app/api/deps.py`, mount the router in `main.py`. ~1.5 hours.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Tee-Mo user**, I want to **register with email + password, log in, stay logged in across browser refreshes, and log out**, So that **I can reach the dashboard that EPIC-003 will build and the BYOK setup that EPIC-004 depends on**. This story is the backend half — STORY-002-03 and STORY-002-04 wire the frontend.

### 1.2 Detailed Requirements

- **R1 — Pydantic models** (`backend/app/models/user.py`, new):
  - `UserRegister(BaseModel)` with `email: EmailStr` and `password: str` (min_length=8, max_length=128). **No `full_name` field** — the `teemo_users` table does not have that column.
  - `UserLogin(BaseModel)` with `email: EmailStr` and `password: str`.
  - `UserResponse(BaseModel)` with `id: UUID`, `email: EmailStr`, `created_at: datetime`. **That is all.** No `auth_provider`, no `is_instance_admin`, no `avatar_url`, no `full_name` — none of those columns exist in `teemo_users`.
- **R2 — Dependency** (`backend/app/api/deps.py`, new):
  - Copy `get_current_user_id` from `new_app/backend/app/api/deps.py` verbatim (it reads `access_token` cookie first, then falls back to `Authorization: Bearer`, decodes via `decode_token`, returns the `sub` claim as a string).
  - **Do NOT** port `get_current_user` or `get_current_admin_user` — Tee-Mo has no admin role and every caller in EPIC-002+ can fetch the full user row inline from `get_current_user_id`.
- **R3 — Auth router** (`backend/app/api/routes/auth.py`, new) with prefix `/api/auth`:
  - `POST /register` → creates row in `teemo_users`, sets both cookies, returns `{"user": UserResponse}`. **Auto-login confirmed by product decision.** The access token is set via httpOnly cookie; it is NOT returned in the response body (Tee-Mo has no Supabase Realtime, so the body copy from new_app is pure overhead).
  - `POST /login` → looks up user by email, verifies bcrypt hash, sets both cookies, returns `{"user": UserResponse}`.
  - `POST /refresh` → reads `refresh_token` cookie, rejects if type claim ≠ `"refresh"`, issues a new `access_token` cookie, returns `{"message": "Token refreshed"}`.
  - `POST /logout` → clears both cookies, returns `{"message": "Logged out"}`.
  - `GET /me` → uses `Depends(get_current_user_id)`, fetches the user row from `teemo_users`, returns `UserResponse`.
- **R4 — Cookie shape** (from new_app `_set_auth_cookies` / `_clear_auth_cookies`):
  - `access_token`: httpOnly, `samesite="lax"` (**NOT `strict`** — see R4a below), `secure=not settings.debug`, `max_age = settings.access_token_expire_minutes * 60`, path `/`.
  - `refresh_token`: same flags, `max_age = settings.refresh_token_expire_days * 86400`, **path `/api/auth`** (so browsers only send it to auth endpoints).
  - **R4a — SameSite=Lax not Strict**: new_app uses `strict` but we need `lax` because during OAuth redirects in EPIC-005/006 the browser will drop Strict cookies. Lax is still safe against CSRF for these endpoints (they all accept JSON bodies, not form posts). Document this decision in the `_set_auth_cookies` docstring.
- **R5 — Register handler specifics** (the strip list from Charter §10):
  - **Strip** `check_user_cap` entirely.
  - **Strip** `_signup_allowed_for_email` entirely (no invite-only mode in Tee-Mo).
  - **Strip** the `link_pending_invites` RPC call entirely.
  - Call `validate_password_length(body.password)` from STORY-002-01. On `ValueError("password_too_long")`, raise `HTTPException(status_code=422, detail="password_too_long")`.
  - Check for existing user by email → 409 `Email already registered`.
  - Insert the new row with `{"id": str(uuid.uuid4()), "email": body.email, "password_hash": hash_password(body.password)}` — do NOT insert `full_name`, `auth_provider`, or any other columns. The `created_at` / `updated_at` defaults fire at the DB level.
  - Issue tokens, set cookies, return `{"user": user}`.
- **R6 — Login handler specifics**:
  - **Strip** `_maybe_promote_admin` entirely (no admin role).
  - **Strip** the `if not user_row.get("password_hash")` Google-only guard — every Tee-Mo user has a password hash since there is no Google auth.
  - Generic `401 Invalid credentials` for both "no such email" and "wrong password" (anti-enumeration).
- **R7 — Table name**: All Supabase queries MUST use `teemo_users`, not `chy_users`. Search-and-replace carefully across the copied routes file.
- **R8 — Router registration**: In `backend/app/main.py`, import the auth router and mount it via `app.include_router(auth_router)`. The router must declare its own prefix internally (`APIRouter(prefix="/api/auth", tags=["auth"])`).
- **R9 — Docstrings**: Every exported function, every route handler, and the module MUST have a clear docstring per CLAUDE.md §6.

### 1.3 Out of Scope

- Email verification — intentionally none per Charter §1.
- Password-reset flow — not in EPIC-002, deferred to post-hackathon.
- Rate limiting on `/login` — not in EPIC-002.
- Refresh token rotation / denylist — not in EPIC-002.
- Google OAuth, any `/google/*` endpoints — removed by ADR-001.
- `get_current_user` and `get_current_admin_user` helpers — Tee-Mo does not need them (no admin role, no routes yet that want the full user row on every call).
- Frontend work of any kind — STORY-002-03 and STORY-002-04.
- Updating `/api/health` to include any auth info.
- Returning `access_token` in response bodies for Supabase Realtime — Tee-Mo has no Realtime consumer.

### TDD Red Phase: Yes
Rationale: Auth endpoints are security-critical and every Gherkin scenario maps cleanly to a FastAPI TestClient test. Red tests enforce that stripped behaviors (invite gate, admin promotion) cannot accidentally resurface from a sloppy copy.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Auth routes

  Background:
    Given the backend is running
    And the teemo_users table is empty

  Scenario: Register happy path with auto-login
    When I POST /api/auth/register with {"email":"alice@example.com","password":"correcthorse"}
    Then the response status is 201
    And the response JSON is {"user": {"id": "<uuid>", "email": "alice@example.com", "created_at": "<iso>"}}
    And the response sets an httpOnly "access_token" cookie
    And the response sets an httpOnly "refresh_token" cookie with path=/api/auth
    And a row exists in teemo_users with email="alice@example.com"
    And the row's password_hash starts with "$2b$"

  Scenario: Register with 73-byte password
    When I POST /api/auth/register with a password whose UTF-8 byte length is 73
    Then the response status is 422
    And the response JSON detail equals "password_too_long"
    And no new row is inserted into teemo_users

  Scenario: Register with duplicate email
    Given a user with email "alice@example.com" already exists
    When I POST /api/auth/register with the same email
    Then the response status is 409
    And the response JSON detail equals "Email already registered"

  Scenario: Register with malformed email
    When I POST /api/auth/register with {"email":"not-an-email","password":"correcthorse"}
    Then the response status is 422
    And the detail mentions the "email" field

  Scenario: Login happy path
    Given a user with email "alice@example.com" and password "correcthorse" exists
    When I POST /api/auth/login with the correct credentials
    Then the response status is 200
    And the response JSON is {"user": {"id": "<uuid>", "email": "alice@example.com", "created_at": "<iso>"}}
    And both auth cookies are set

  Scenario: Login with wrong password
    Given a user with email "alice@example.com" exists
    When I POST /api/auth/login with the wrong password
    Then the response status is 401
    And the response JSON detail equals "Invalid credentials"

  Scenario: Login with unknown email
    Given no user with email "ghost@example.com" exists
    When I POST /api/auth/login with email "ghost@example.com"
    Then the response status is 401
    And the response JSON detail equals "Invalid credentials"

  Scenario: GET /me with valid access cookie
    Given I am logged in as "alice@example.com"
    When I GET /api/auth/me with the access_token cookie
    Then the response status is 200
    And the response JSON is {"id": "<uuid>", "email": "alice@example.com", "created_at": "<iso>"}

  Scenario: GET /me without cookie
    When I GET /api/auth/me with no cookies
    Then the response status is 401

  Scenario: GET /me with expired access cookie
    Given I am logged in as "alice@example.com"
    When I tamper with the access_token cookie to force ExpiredSignatureError
    And I GET /api/auth/me
    Then the response status is 401

  Scenario: Refresh happy path
    Given I am logged in as "alice@example.com"
    When I POST /api/auth/refresh with the refresh_token cookie
    Then the response status is 200
    And the response JSON is {"message": "Token refreshed"}
    And the response sets a new "access_token" cookie

  Scenario: Refresh with an access token in the refresh slot
    Given I have an access_token value
    When I POST /api/auth/refresh with refresh_token set to the access token
    Then the response status is 401
    And the response JSON detail equals "Invalid token type"

  Scenario: Logout clears cookies
    Given I am logged in as "alice@example.com"
    When I POST /api/auth/logout
    Then the response status is 200
    And the response clears the access_token cookie
    And the response clears the refresh_token cookie
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_auth_routes.py -v` — all scenarios pass.
- [ ] `curl -i -X POST http://localhost:8000/api/auth/register -H 'Content-Type: application/json' -d '{"email":"a@b.co","password":"correcthorse"}'` returns 201 + `Set-Cookie` headers.
- [ ] `curl -b cookies.txt http://localhost:8000/api/auth/me` returns the user JSON after saving cookies from the register call.
- [ ] Supabase dashboard: new row visible in `teemo_users` with only `id`, `email`, `password_hash`, `created_at`, `updated_at` populated.
- [ ] No plaintext password appears in server logs or response bodies (grep the Uvicorn log after a register/login pair).
- [ ] `GET /api/health` still returns `status: ok` with all 4 tables — this story does NOT touch the health endpoint.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-002-01** | `backend/app/core/security.py` exists with all 5 functions + `validate_password_length`. `backend/app/core/config.py` has `access_token_expire_minutes`, `refresh_token_expire_days`, `jwt_algorithm`. | [ ] |
| **Backend deps** | Same as STORY-002-01 (PyJWT, bcrypt, fastapi, supabase client already installed) | [x] |
| **Env Vars** | `.env` has valid Supabase URL + service_role_key; `DEBUG=true` for cookie-`secure=False` behavior in dev | [ ] |
| **Services Running** | Self-hosted Supabase at `sulabase.soula.ge` reachable (verified in S-01) | [x] |
| **Migrations** | `teemo_users` table exists with columns `id, email, password_hash, created_at, updated_at` (verified in S-01) | [x] |
| **Test DB state** | Tests should delete rows from `teemo_users` they create — use a unique `test+{uuid4}@example.com` email pattern to avoid collisions with real data | [ ] |

### 3.1 Test Implementation

Create `backend/tests/test_auth_routes.py`. Use FastAPI's `TestClient` (from `fastapi.testclient`) and the running self-hosted Supabase — **no mocking**. After each test, clean up by deleting the user rows created. Prefer a `pytest` fixture that yields a unique email and deletes the row on teardown:

```python
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_supabase


@pytest.fixture
def unique_email():
    email = f"test+{uuid.uuid4()}@teemo.test"
    yield email
    # Teardown: delete any row the test may have created
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def client():
    return TestClient(app)
```

For the expired-cookie scenario, use `create_access_token` on a UUID and then manually craft an expired token via `jwt.encode` (the same pattern as STORY-002-01's `test_decode_token_rejects_expired_token`), set it on `client.cookies`, and hit `/api/auth/me`.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/auth.py` (new) |
| **Related Files** | `backend/app/models/user.py` (new), `backend/app/api/deps.py` (new), `backend/app/api/__init__.py` (new, empty), `backend/app/api/routes/__init__.py` (new, empty), `backend/app/models/__init__.py` (new, empty), `backend/app/main.py` (edit — include router), `backend/tests/test_auth_routes.py` (new) |
| **New Files Needed** | Yes — all except `main.py` |
| **ADR References** | ADR-001 (JWT pair, httpOnly cookies), ADR-017 (bcrypt 72-byte guard, applied here at the route boundary) |
| **First-Use Pattern** | No — `FastAPI` + `APIRouter` + `Depends` + cookie auth is all prior art in `new_app`. Source files: `/Users/ssuladze/Documents/Dev/new_app/backend/app/api/routes/auth.py` and `/Users/ssuladze/Documents/Dev/new_app/backend/app/api/deps.py` |

### 3.3 Technical Logic

**Step 1 — `backend/app/models/user.py`:**

```python
"""
User-related Pydantic models for Tee-Mo auth.

These models define the request and response contracts for POST /api/auth/register,
POST /api/auth/login, and GET /api/auth/me. They intentionally carry only the
columns that exist in the ``teemo_users`` table (id, email, password_hash,
created_at, updated_at) — no full_name, no avatar_url, no auth_provider,
no admin flag.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """Request body for POST /api/auth/register."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Request body for POST /api/auth/login."""
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Public user profile — safe to return to the frontend."""
    id: UUID
    email: EmailStr
    created_at: datetime
```

**Step 2 — `backend/app/api/deps.py`:**

Copy the `get_current_user_id` function **only** from `new_app/backend/app/api/deps.py`. Replace the `from app.models.user import User` line with no import at all (we don't need `User` in this file). Delete `get_current_user` and `get_current_admin_user` entirely. Result should be ~50 lines.

**Step 3 — `backend/app/api/routes/auth.py`:**

Start with the structure below, filling in bodies by copying from new_app with the strip list applied:

```python
"""
Tee-Mo authentication routes.

Implements email + password registration, login, refresh, logout, and /me.
All tokens are delivered via httpOnly cookies — the response body never
contains an access_token (Tee-Mo does not use Supabase Realtime and has no
consumer for a body-level token).

Strip history (copied from new_app with charter §10 Epic Seed Map strip list):
  - Removed: Google OAuth endpoints and helpers
  - Removed: _signup_allowed_for_email invite gate
  - Removed: check_user_cap license enforcement
  - Removed: link_pending_invites RPC
  - Removed: _maybe_promote_admin
  - Removed: access_token echo in response bodies
  - Table renamed: chy_users → teemo_users
"""

from __future__ import annotations

import uuid
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.core.db import get_supabase
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_length,
    verify_password,
)
from app.models.user import UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """
    Attach the access_token and refresh_token httpOnly cookies to a response.

    SameSite=Lax (not Strict) — Lax is required so that OAuth redirect flows
    in EPIC-005 (Slack) and EPIC-006 (Google Drive) do not lose the session
    cookie on the return hop. Lax is still CSRF-safe for these endpoints
    because they accept JSON bodies, not form posts.

    The refresh_token cookie is scoped to path="/api/auth" so that browsers
    only send it to auth endpoints — limiting its attack surface.
    """
    is_secure = not settings.debug
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies (used by POST /logout)."""
    response.delete_cookie(key="access_token", httponly=True, samesite="lax", path="/")
    response.delete_cookie(key="refresh_token", httponly=True, samesite="lax", path="/api/auth")


def _row_to_user_response(row: dict[str, Any]) -> UserResponse:
    """Convert a teemo_users row dict into a UserResponse."""
    return UserResponse(id=row["id"], email=row["email"], created_at=row["created_at"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", status_code=201)
async def register(body: UserRegister, response: Response) -> dict:
    """
    Register a new user with email + password, then auto-login by setting cookies.

    See STORY-002-02 §1.2 R5 for the full strip list applied to this handler.
    """
    # Guard against bcrypt 5.0 ValueError before touching the DB (ADR-017, FLASHCARDS.md bcrypt entry).
    try:
        validate_password_length(body.password)
    except ValueError:
        raise HTTPException(status_code=422, detail="password_too_long")

    supabase = get_supabase()

    existing = (
        supabase.table("teemo_users")
        .select("id")
        .eq("email", body.email)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_id = uuid.uuid4()
    insert_result = (
        supabase.table("teemo_users")
        .insert(
            {
                "id": str(new_id),
                "email": body.email,
                "password_hash": hash_password(body.password),
            }
        )
        .execute()
    )

    if not insert_result.data:
        raise HTTPException(status_code=500, detail="Failed to create user")

    user = _row_to_user_response(insert_result.data[0])

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _set_auth_cookies(response, access, refresh)

    return {"user": user}


@router.post("/login", status_code=200)
async def login(body: UserLogin, response: Response) -> dict:
    """
    Authenticate a user with email + password and set auth cookies.

    Error messages are intentionally generic ("Invalid credentials") to prevent
    user enumeration via the login endpoint.
    """
    supabase = get_supabase()

    result = (
        supabase.table("teemo_users")
        .select("*")
        .eq("email", body.email)
        .limit(1)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_row = result.data[0]

    if not verify_password(body.password, user_row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = _row_to_user_response(user_row)
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    _set_auth_cookies(response, access, refresh)

    return {"user": user}


@router.post("/refresh", status_code=200)
async def refresh_token_route(request: Request, response: Response) -> dict:
    """
    Exchange a valid refresh token for a new access token cookie.

    Rejects access tokens presented in the refresh slot via the ``type`` claim
    check (access tokens have no ``type`` claim; refresh tokens have ``type``
    set to ``"refresh"``).
    """
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = uuid.UUID(payload["sub"])
    new_access = create_access_token(user_id)

    is_secure = not settings.debug
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )

    return {"message": "Token refreshed"}


@router.post("/logout", status_code=200)
async def logout(response: Response) -> dict:
    """Clear both auth cookies. No server-side revocation in EPIC-002."""
    _clear_auth_cookies(response)
    return {"message": "Logged out"}


@router.get("/me", status_code=200)
async def me(user_id: str = Depends(get_current_user_id)) -> UserResponse:
    """Return the authenticated user's profile (id, email, created_at)."""
    supabase = get_supabase()
    result = (
        supabase.table("teemo_users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_user_response(result.data[0])
```

**Step 4 — `backend/app/main.py`**: add the router import and mount it. Do NOT touch the existing `/api/health` setup.

```python
# Add to imports
from app.api.routes.auth import router as auth_router

# Add after app.add_middleware(...)
app.include_router(auth_router)
```

### 3.4 API Contract

| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/auth/register` | POST | None | `{email: str, password: str}` | `201 {user: {id, email, created_at}}` + Set-Cookie × 2 |
| `/api/auth/login` | POST | None | `{email: str, password: str}` | `200 {user: {id, email, created_at}}` + Set-Cookie × 2 |
| `/api/auth/refresh` | POST | refresh_token cookie | — | `200 {message: "Token refreshed"}` + Set-Cookie (access_token only) |
| `/api/auth/logout` | POST | None | — | `200 {message: "Logged out"}` + clears both cookies |
| `/api/auth/me` | GET | access_token cookie or Bearer | — | `200 {id, email, created_at}` |

All error responses follow FastAPI's default `{"detail": "<message>"}` shape. Documented error codes per endpoint: `register` → 409, 422, 500; `login` → 401, 422; `refresh` → 401; `me` → 401, 404.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (primitives already unit-tested in STORY-002-01) | |
| Component tests | 0 — N/A (backend story) | |
| E2E / acceptance tests | 13 | One per Gherkin scenario in §2.1 |
| Integration tests | 13 (same set — each test hits real Supabase) | Counted once in the E2E row |

### 4.2 Definition of Done
- [ ] TDD Red phase: all 13 tests written and verified failing before implementation.
- [ ] Green phase: all 13 tests pass against the live self-hosted Supabase.
- [ ] Manual curl verification steps from §2.2 executed and passing.
- [ ] `backend/app/models/user.py`, `backend/app/api/deps.py`, `backend/app/api/routes/auth.py` all exist with full docstrings.
- [ ] `backend/app/main.py` mounts the auth router via `include_router`.
- [ ] Strip list audit: grep the new files for `chy_`, `_signup_allowed_for_email`, `check_user_cap`, `_maybe_promote_admin`, `link_pending_invites`, `google`, `admin`, `full_name`, `avatar_url`, `is_instance_admin`, `access_token.*return`, `setRealtimeAuth` — all must return zero hits.
- [ ] FLASHCARDS.md bcrypt entry consulted — `validate_password_length` is called before `hash_password` in the register handler.
- [ ] No ADR violations. ADR-001 cookie shape + expiry match. ADR-017 applied at the route boundary.
- [ ] No plaintext password leaks in logs or responses (verified in §2.2).

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
