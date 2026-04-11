"""
Acceptance tests for STORY-002-02: Auth Routes + httpOnly Cookies + get_current_user_id.

13 test functions — one per Gherkin scenario in STORY-002-02-auth_routes §2.1.

These tests are written in TDD Red Phase: the modules they import do NOT yet exist.
All 13 tests will fail with ModuleNotFoundError/ImportError until Green Phase.

Test strategy:
  - No mocking: FastAPI TestClient + live self-hosted Supabase (sulabase.soula.ge).
  - Unique email addresses per test (test+{uuid4}@teemo.test) with teardown to
    prevent row pollution between runs.
  - Expired token scenario uses jwt.encode directly to build a past-exp token,
    matching the pattern from test_security.py.
  - Refresh-slot abuse scenario uses create_access_token to get a valid access
    token, then places it in the refresh_token cookie slot.

ADR compliance:
  - ADR-001: JWT pair, httpOnly cookies, access 15min / refresh 7d.
  - ADR-017: validate_password_length called before hash_password in /register.

FLASHCARDS.md consulted:
  - bcrypt 5.0: 73-byte password must yield 422 "password_too_long".
  - get_supabase(): all DB access goes through app.core.db.get_supabase().
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_supabase
from app.core.security import create_access_token, decode_token
from app.core.config import settings

# --- These imports DO NOT EXIST yet. They drive the Red phase failure. ---
from app.api.routes.auth import router as auth_router  # noqa: F401 — must fail in Red
from app.models.user import UserRegister, UserLogin, UserResponse  # noqa: F401
from app.api.deps import get_current_user_id  # noqa: F401
# -------------------------------------------------------------------------


@pytest.fixture
def unique_email():
    """
    Yield a unique test email and delete the teemo_users row on teardown.

    Uses the pattern test+{uuid4}@teemo.test to avoid collisions with real data.
    The teardown is unconditional — if the test never inserted a row, the delete
    is a harmless no-op.
    """
    email = f"test+{uuid.uuid4()}@teemo.test"
    yield email
    # Teardown: delete any row the test may have created
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def client():
    """
    Return a FastAPI TestClient wrapping the main app.

    TestClient uses HTTPX under the hood and resets cookies between separate
    fixture instances. Tests that need a pre-authenticated state must perform
    the login/register call themselves and use the resulting cookie jar.
    """
    return TestClient(app)


# ---------------------------------------------------------------------------
# Scenario 1: Register happy path with auto-login
# ---------------------------------------------------------------------------


def test_register_happy_path(client, unique_email):
    """
    Scenario: Register happy path with auto-login.

    Covers:
    - 201 status on successful registration
    - Response body shape: {"user": {id, email, created_at}}
    - httpOnly access_token cookie is set
    - httpOnly refresh_token cookie is set with path=/api/auth
    - A row is inserted in teemo_users with the correct email
    - The stored password_hash starts with "$2b$" (bcrypt)
    """
    response = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )
    assert response.status_code == 201

    body = response.json()
    assert "user" in body
    user = body["user"]
    assert user["email"] == unique_email
    assert "id" in user
    assert "created_at" in user
    # access_token must NOT appear in the response body (R3 — no Realtime consumer)
    assert "access_token" not in body

    # Cookie assertions: TestClient stores cookies from Set-Cookie headers
    # access_token cookie must be present
    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_str = " ".join(set_cookie_headers)
    assert "access_token=" in cookie_str
    assert "refresh_token=" in cookie_str
    assert "HttpOnly" in cookie_str
    # refresh_token must be scoped to /api/auth (R4)
    assert "Path=/api/auth" in cookie_str or "path=/api/auth" in cookie_str.lower()

    # Verify row in teemo_users
    supabase = get_supabase()
    db_result = (
        supabase.table("teemo_users")
        .select("email, password_hash")
        .eq("email", unique_email)
        .limit(1)
        .execute()
    )
    assert db_result.data, "Expected a row in teemo_users after register"
    row = db_result.data[0]
    assert row["email"] == unique_email
    assert row["password_hash"].startswith("$2b$")


# ---------------------------------------------------------------------------
# Scenario 2: Register with 73-byte password
# ---------------------------------------------------------------------------


def test_register_73_byte_password(client, unique_email):
    """
    Scenario: Register with 73-byte password.

    bcrypt 5.0 raises ValueError on passwords > 72 bytes (FLASHCARDS.md, ADR-017).
    The /register handler calls validate_password_length BEFORE touching the DB.

    Covers:
    - 422 status
    - detail equals "password_too_long"
    - No row is inserted in teemo_users
    """
    # 73 ASCII characters = 73 UTF-8 bytes
    long_password = "a" * 73

    response = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": long_password},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "password_too_long"

    # Confirm no row was inserted
    supabase = get_supabase()
    db_result = (
        supabase.table("teemo_users")
        .select("id")
        .eq("email", unique_email)
        .limit(1)
        .execute()
    )
    assert not db_result.data, "No row should be inserted for a 73-byte password"


# ---------------------------------------------------------------------------
# Scenario 3: Register with duplicate email
# ---------------------------------------------------------------------------


def test_register_duplicate_email(client, unique_email):
    """
    Scenario: Register with duplicate email.

    Covers:
    - First registration succeeds (201)
    - Second registration with the same email returns 409
    - detail equals "Email already registered"
    """
    payload = {"email": unique_email, "password": "correcthorse"}

    # First registration — must succeed
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    # Second registration — must conflict
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "Email already registered"


# ---------------------------------------------------------------------------
# Scenario 4: Register with malformed email
# ---------------------------------------------------------------------------


def test_register_malformed_email(client):
    """
    Scenario: Register with malformed email.

    Pydantic's EmailStr validation rejects addresses that don't look like emails.
    FastAPI returns 422 automatically with a detail array that references the
    "email" field.

    Covers:
    - 422 status
    - Response detail mentions the "email" field
    """
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "correcthorse"},
    )
    assert response.status_code == 422
    body = response.json()
    # FastAPI validation errors return a list of error objects
    detail = body["detail"]
    assert isinstance(detail, list)
    # At least one error must reference the "email" field
    email_errors = [
        err for err in detail
        if any("email" in str(loc).lower() for loc in err.get("loc", []))
    ]
    assert email_errors, f"Expected an error referencing 'email' field, got: {detail}"


# ---------------------------------------------------------------------------
# Scenario 5: Login happy path
# ---------------------------------------------------------------------------


def test_login_happy_path(client, unique_email):
    """
    Scenario: Login happy path.

    Registers a user first (setup), then logs in with correct credentials.

    Covers:
    - 200 status
    - Response body shape: {"user": {id, email, created_at}}
    - Both auth cookies set on login response
    """
    password = "correcthorse"
    # Setup: register the user
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": password},
    )
    assert reg.status_code == 201

    # Act: login with fresh client (no existing cookies)
    fresh_client = TestClient(app)
    response = fresh_client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert response.status_code == 200

    body = response.json()
    assert "user" in body
    user = body["user"]
    assert user["email"] == unique_email
    assert "id" in user
    assert "created_at" in user

    # Both cookies must be set
    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_str = " ".join(set_cookie_headers)
    assert "access_token=" in cookie_str
    assert "refresh_token=" in cookie_str


# ---------------------------------------------------------------------------
# Scenario 6: Login with wrong password
# ---------------------------------------------------------------------------


def test_login_wrong_password(client, unique_email):
    """
    Scenario: Login with wrong password.

    Anti-enumeration: the response is 401 "Invalid credentials" regardless of
    whether the email exists or the password is wrong.

    Covers:
    - 401 status
    - detail equals "Invalid credentials"
    """
    # Setup: register the user
    client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )

    response = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# Scenario 7: Login with unknown email
# ---------------------------------------------------------------------------


def test_login_unknown_email(client):
    """
    Scenario: Login with unknown email.

    Anti-enumeration: same 401 "Invalid credentials" as wrong-password.
    No fixture teardown needed — this email is never inserted.

    Covers:
    - 401 status
    - detail equals "Invalid credentials"
    """
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "doesnotmatter"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# Scenario 8: GET /me with valid access cookie
# ---------------------------------------------------------------------------


def test_me_with_valid_access_cookie(client, unique_email):
    """
    Scenario: GET /me with valid access cookie.

    Registers a user, captures the access_token cookie, then hits /me.

    Covers:
    - 200 status
    - Response body: {id, email, created_at} (no "user" wrapper — /me returns flat)
    """
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )
    assert reg.status_code == 201

    # TestClient carries cookies from the register response automatically
    # because it's the same client instance
    response = client.get("/api/auth/me")
    assert response.status_code == 200

    body = response.json()
    assert body["email"] == unique_email
    assert "id" in body
    assert "created_at" in body


# ---------------------------------------------------------------------------
# Scenario 9: GET /me without cookie
# ---------------------------------------------------------------------------


def test_me_without_cookie(client):
    """
    Scenario: GET /me without cookie.

    Fresh client with no cookies set. The get_current_user_id dependency
    must return 401.

    Covers:
    - 401 status
    """
    response = client.get("/api/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Scenario 10: GET /me with expired access cookie
# ---------------------------------------------------------------------------


def test_me_with_expired_access_cookie(client, unique_email):
    """
    Scenario: GET /me with expired access cookie.

    Manually crafts a JWT with exp 1 second in the past (same technique as
    test_decode_token_rejects_expired_token in test_security.py), sets it as
    the access_token cookie, then asserts /me returns 401.

    Covers:
    - 401 status when access token is expired
    """
    # Register so teardown can clean up the unique_email row if needed
    # (not strictly needed for this test but keeps fixture consistent)
    client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )

    # Craft an expired token
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(uuid.uuid4()),
        "role": "authenticated",
        "iat": int((now - timedelta(minutes=30)).timestamp()),
        "exp": int((now - timedelta(seconds=1)).timestamp()),
    }
    expired_token = jwt.encode(
        expired_payload,
        settings.supabase_jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    # Overwrite the access_token cookie with the expired token
    client.cookies.set("access_token", expired_token)

    response = client.get("/api/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Scenario 11: Refresh happy path
# ---------------------------------------------------------------------------


def test_refresh_happy_path(client, unique_email):
    """
    Scenario: Refresh happy path.

    Registers/logs-in to obtain a refresh_token cookie, then calls /refresh.

    Covers:
    - 200 status
    - Response body: {"message": "Token refreshed"}
    - A new access_token cookie is set in the response
    """
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )
    assert reg.status_code == 201

    response = client.post("/api/auth/refresh")
    assert response.status_code == 200
    assert response.json() == {"message": "Token refreshed"}

    # A new access_token cookie must be issued
    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_str = " ".join(set_cookie_headers)
    assert "access_token=" in cookie_str


# ---------------------------------------------------------------------------
# Scenario 12: Refresh with an access token in the refresh slot
# ---------------------------------------------------------------------------


def test_refresh_with_access_token_in_refresh_slot(client, unique_email):
    """
    Scenario: Refresh with an access token in the refresh slot.

    Places a valid access token (no 'type' claim) into the refresh_token cookie
    slot. The /refresh handler checks payload.get("type") != "refresh" and must
    return 401 "Invalid token type".

    Covers:
    - 401 status
    - detail equals "Invalid token type"
    """
    # Register to get a valid user UUID for the token
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )
    assert reg.status_code == 201

    # Grab the access token from the register response cookies
    access_token_value = client.cookies.get("access_token")
    assert access_token_value, "Expected access_token cookie after register"

    # Place the access token in the refresh_token cookie slot
    fresh_client = TestClient(app)
    fresh_client.cookies.set("refresh_token", access_token_value)

    response = fresh_client.post("/api/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token type"


# ---------------------------------------------------------------------------
# Scenario 13: Logout clears cookies
# ---------------------------------------------------------------------------


def test_logout_clears_cookies(client, unique_email):
    """
    Scenario: Logout clears cookies.

    Registers to obtain auth cookies, then calls /logout. Verifies the
    response returns 200 and the Set-Cookie headers indicate the cookies
    are being cleared (max-age=0 or expires in the past).

    Covers:
    - 200 status
    - Response body: {"message": "Logged out"}
    - access_token cookie cleared in Set-Cookie header
    - refresh_token cookie cleared in Set-Cookie header
    """
    reg = client.post(
        "/api/auth/register",
        json={"email": unique_email, "password": "correcthorse"},
    )
    assert reg.status_code == 201

    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Logged out"}

    # Inspect Set-Cookie headers to confirm cookies are being deleted.
    # FastAPI's delete_cookie sets max-age=0 (or a past expires).
    set_cookie_headers = response.headers.get_list("set-cookie")
    cookie_str = " ".join(set_cookie_headers)
    assert "access_token=" in cookie_str, "Expected access_token to be cleared"
    assert "refresh_token=" in cookie_str, "Expected refresh_token to be cleared"
    # Cleared cookies have max-age=0
    assert "max-age=0" in cookie_str.lower() or "max-age=0" in cookie_str
