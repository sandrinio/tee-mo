"""Integration tests for STORY-005A-04 — Slack OAuth callback (Red phase).

10 tests covering all Gherkin scenarios from §2.1 of the story spec.

Strategy:
- REAL Supabase (no DB mocking). Users are registered via /api/auth/register and
  cleaned up via fixtures. Slack team rows with T_TEST_* IDs are purged by
  cleanup_slack_teams fixture before and after each test.
- Mock ONLY httpx.AsyncClient via hand-rolled FakeAsyncClient + monkeypatch on the
  slack_oauth module attribute. All other production code (encryption, state tokens,
  Supabase upsert, auth dep) runs for real.
- TestClient created with follow_redirects=False so 302 headers can be inspected.
- Expired tokens are crafted via create_slack_state_token(user_id, now=past_ts) — no
  time.sleep() required.

RED PHASE: All 10 tests FAIL because GET /api/slack/oauth/callback does not exist yet.
Most failures will be HTTP 404. Some may be AttributeError if slack_oauth.py doesn't
yet import httpx. The failures prove the tests are wired to the correct missing target.

ADR compliance:
- ADR-001: JWT access_token cookie for auth.
- ADR-002 / ADR-010: encrypted_slack_bot_token asserted != plaintext, decrypts back.
- ADR-024: slack_team_id PK, owner_user_id FK.

FLASHCARDS.md consulted:
- get_supabase() is the only DB entry point (service-role key, cached).
- BUG-20260411: use module-local _JWT instance — tests use create_slack_state_token /
  verify_slack_state_token helpers; no raw jwt.decode with verify_signature=False.
- Auth cookies: samesite="lax" — deliberate for OAuth redirect flows (EPIC-005).
- Pydantic EmailStr: test fixtures use @teemo.test with LaxEmailStr-accepting endpoints
  (register route already uses LaxEmailStr per STORY-002-02).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, create_slack_state_token
from app.core.encryption import encrypt, decrypt
from app.core.db import get_supabase


# ---------------------------------------------------------------------------
# Canonical mock payload — oauth.v2.access shape verified from slack-bolt
# source inspection on 2026-04-12 (slack-bolt oauth_flow.py:344)
# ---------------------------------------------------------------------------

MOCK_OAUTH_V2_ACCESS_OK = {
    "ok": True,
    "access_token": "xoxb-test-token-1",
    "token_type": "bot",
    "scope": (
        "app_mentions:read,channels:history,channels:read,"
        "chat:write,groups:history,groups:read,im:history,users:read"
    ),
    "bot_user_id": "UBOT_TEST_001",
    "app_id": "A_TEST_001",
    "team": {"id": "T_TEST_001", "name": "Test Team"},
    "enterprise": None,
    "authed_user": {
        "id": "U_INSTALLER_001",
        "scope": "",
        "access_token": "xoxp-ignored",
        "token_type": "user",
    },
}


# ---------------------------------------------------------------------------
# Hand-rolled httpx mock — first-use pattern for this codebase.
# FakeAsyncClient is a class-level singleton so monkeypatch replaces the
# constructor; each call to `async with httpx.AsyncClient(...) as client`
# gets an instance that intercepts .post(...) calls.
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal stand-in for httpx.Response — provides .json() and .text."""

    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        """Return the payload dict."""
        return self._payload

    @property
    def text(self) -> str:
        """Return the payload serialised as JSON string."""
        return json.dumps(self._payload)


class FakeAsyncClient:
    """Stand-in for httpx.AsyncClient.

    Captures the last POST call for assertion and optionally serves queued
    responses. Supports the async context-manager protocol (``async with``).

    Class-level state (last_call, _response_queue) is reset by the autouse
    fixture ``_reset_fake_client`` before and after every test.
    """

    last_call: dict[str, Any] | None = None
    _response_queue: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *a: Any) -> bool:
        return False

    async def post(self, url: str, data: Any = None, **kw: Any) -> FakeResponse:
        """Intercept POST; record call metadata and return next queued or default payload."""
        FakeAsyncClient.last_call = {"url": url, "data": data, "kwargs": kw}
        payload = (
            FakeAsyncClient._response_queue.pop(0)
            if FakeAsyncClient._response_queue
            else MOCK_OAUTH_V2_ACCESS_OK
        )
        return FakeResponse(200, payload)

    @classmethod
    def reset(cls) -> None:
        """Clear last_call and any queued responses."""
        cls.last_call = None
        cls._response_queue = []

    @classmethod
    def queue(cls, payload: dict[str, Any]) -> None:
        """Enqueue a payload to be returned by the next .post() call."""
        cls._response_queue.append(payload)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_fake_client() -> Any:
    """Reset FakeAsyncClient state before and after every test (autouse)."""
    FakeAsyncClient.reset()
    yield
    FakeAsyncClient.reset()


@pytest.fixture
def patch_httpx(monkeypatch: pytest.MonkeyPatch) -> type[FakeAsyncClient]:
    """Replace httpx.AsyncClient inside the slack_oauth module with FakeAsyncClient.

    The production route does ``import httpx`` at module level and then calls
    ``httpx.AsyncClient(...)`` inside the handler. We patch the ``AsyncClient``
    attribute on the imported ``httpx`` module reference that the slack_oauth
    module holds, so every ``async with httpx.AsyncClient(...)`` call in that
    module routes to FakeAsyncClient.

    Returns the FakeAsyncClient class so tests can inspect .last_call and
    call .queue() before hitting the endpoint.
    """
    import app.api.routes.slack_oauth as slack_oauth_module

    monkeypatch.setattr(slack_oauth_module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.fixture
def alice_user() -> Any:
    """Register a real user in teemo_users and yield (user_id: str, token: str).

    Email pattern uses @teemo.test with a random suffix to avoid parallel-test
    collisions. The register endpoint uses LaxEmailStr so @teemo.test is accepted.
    Cleaned up via teemo_users DELETE after yield; ON DELETE CASCADE removes any
    teemo_slack_teams rows referencing this user.
    """
    email = f"alice+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, f"alice register failed: {resp.text}"
    user_row = (
        get_supabase()
        .table("teemo_users")
        .select("id")
        .eq("email", email)
        .single()
        .execute()
    )
    user_id = str(user_row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    yield user_id, token
    # Cleanup — CASCADE handles slack_teams children
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def bob_user() -> Any:
    """Register a second real user for cross-user / different-owner tests."""
    email = f"bob+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, f"bob register failed: {resp.text}"
    user_row = (
        get_supabase()
        .table("teemo_users")
        .select("id")
        .eq("email", email)
        .single()
        .execute()
    )
    user_id = str(user_row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def cleanup_slack_teams() -> Any:
    """Delete all T_TEST_* rows from teemo_slack_teams before and after the test.

    This fixture must be requested explicitly by each test that touches the
    teemo_slack_teams table — it is NOT autouse to allow non-DB tests to remain
    fast. The LIKE pattern 'T_TEST_%' matches all test team IDs used in this suite.
    """

    def _clean() -> None:
        get_supabase().table("teemo_slack_teams").delete().like(
            "slack_team_id", "T_TEST_%"
        ).execute()

    _clean()
    yield
    _clean()


@pytest.fixture
def alice_client(alice_user: tuple[str, str]) -> TestClient:
    """TestClient pre-loaded with alice's access_token cookie, follow_redirects=False."""
    _, token = alice_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def bob_client(bob_user: tuple[str, str]) -> TestClient:
    """TestClient pre-loaded with bob's access_token cookie, follow_redirects=False."""
    _, token = bob_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def make_valid_state(user_id: str) -> str:
    """Create a fresh, non-expired Slack state token for the given user_id."""
    return create_slack_state_token(user_id)


# ---------------------------------------------------------------------------
# Tests — 10 scenarios from §2.1
# ---------------------------------------------------------------------------


def test_happy_path_first_install(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
) -> None:
    """Scenario: Happy path — first install.

    Given a valid state token for alice's user_id
    And mocked oauth.v2.access returns MOCK_OAUTH_V2_ACCESS_OK
    When GET /api/slack/oauth/callback?code=ok_code&state=<valid> with alice's cookie
    Then:
    - 302 redirect to /app?slack_install=ok
    - FakeAsyncClient.last_call["url"] == "https://slack.com/api/oauth.v2.access"
    - FakeAsyncClient.last_call["data"] contains code, client_id, client_secret, redirect_uri
    - A teemo_slack_teams row exists with correct owner, bot_user_id, encrypted token
    - The stored token is encrypted (not equal to plaintext) but decrypts back to plaintext

    RED: Fails with 404 — /oauth/callback route does not exist.
    """
    user_id, _ = alice_user
    state = make_valid_state(user_id)

    response = alice_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code", "state": state},
    )

    assert response.status_code == 302, f"Expected 302, got {response.status_code}: {response.text}"
    assert response.headers["location"] == "/app?slack_install=ok"

    # Slack API was called at the correct URL
    assert FakeAsyncClient.last_call is not None
    assert FakeAsyncClient.last_call["url"] == "https://slack.com/api/oauth.v2.access"

    # POST body contains the required fields
    posted_data = FakeAsyncClient.last_call["data"]
    assert posted_data["code"] == "ok_code"
    assert posted_data["client_id"] == settings.slack_client_id
    assert posted_data["client_secret"] == settings.slack_client_secret
    assert posted_data["redirect_uri"] == settings.slack_redirect_url

    # Row was written to teemo_slack_teams
    rows = (
        get_supabase()
        .table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", "T_TEST_001")
        .single()
        .execute()
    )
    row = rows.data
    assert row["owner_user_id"] == user_id
    assert row["slack_bot_user_id"] == "UBOT_TEST_001"

    # Token is stored encrypted, not in plaintext
    assert row["encrypted_slack_bot_token"] != "xoxb-test-token-1"

    # But decrypts back to the original plaintext
    assert decrypt(row["encrypted_slack_bot_token"]) == "xoxb-test-token-1"


def test_reinstall_same_owner(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
) -> None:
    """Scenario: Re-install — same owner, same team.

    Given alice already has a teemo_slack_teams row for T_TEST_001 with an old encrypted token
    And mocked oauth.v2.access returns a new token "xoxb-new"
    When alice completes the callback again for the same team
    Then:
    - 302 to /app?slack_install=ok
    - Exactly ONE row exists for T_TEST_001 (upsert, not insert duplicate)
    - The row's encrypted token decrypts to "xoxb-new"
    - owner_user_id is still alice's

    RED: Fails with 404.
    """
    user_id, _ = alice_user

    # Pre-seed an existing row with old token
    old_encrypted = encrypt("xoxb-old")
    get_supabase().table("teemo_slack_teams").insert({
        "slack_team_id": "T_TEST_001",
        "owner_user_id": user_id,
        "slack_bot_user_id": "UBOT_TEST_OLD",
        "encrypted_slack_bot_token": old_encrypted,
    }).execute()

    # Queue a response with a new token
    FakeAsyncClient.queue({
        **MOCK_OAUTH_V2_ACCESS_OK,
        "access_token": "xoxb-new",
        "bot_user_id": "UBOT_TEST_001",
        "team": {"id": "T_TEST_001", "name": "Test Team"},
    })

    state = make_valid_state(user_id)
    response = alice_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code", "state": state},
    )

    assert response.status_code == 302
    assert response.headers["location"] == "/app?slack_install=ok"

    # Exactly one row
    rows = (
        get_supabase()
        .table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", "T_TEST_001")
        .execute()
    )
    assert len(rows.data) == 1, f"Expected exactly 1 row, got {len(rows.data)}"

    row = rows.data[0]
    assert decrypt(row["encrypted_slack_bot_token"]) == "xoxb-new"
    assert row["owner_user_id"] == user_id


def test_reinstall_different_owner_returns_409(
    alice_user: tuple[str, str],
    bob_user: tuple[str, str],
    bob_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
) -> None:
    """Scenario: Re-install — different owner (R5 / Q2).

    Given alice already owns the row for T_TEST_001
    When bob completes the OAuth flow for T_TEST_001 with bob's cookie + state
    Then:
    - 409 Conflict
    - Response body contains "already installed under a different account"
    - The existing row is UNCHANGED (alice still owns it, old token intact)

    RED: Fails with 404.
    """
    alice_id, _ = alice_user
    bob_id, _ = bob_user

    # Pre-seed alice's existing row
    alice_encrypted = encrypt("xoxb-alice-original")
    get_supabase().table("teemo_slack_teams").insert({
        "slack_team_id": "T_TEST_001",
        "owner_user_id": alice_id,
        "slack_bot_user_id": "UBOT_ALICE",
        "encrypted_slack_bot_token": alice_encrypted,
    }).execute()

    # Bob attempts to install the same team
    FakeAsyncClient.queue({**MOCK_OAUTH_V2_ACCESS_OK, "team": {"id": "T_TEST_001", "name": "Test Team"}})
    state = make_valid_state(bob_id)
    response = bob_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code_bob", "state": state},
    )

    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
    assert "already installed under a different account" in response.text

    # Row is unchanged — alice still owns it
    rows = (
        get_supabase()
        .table("teemo_slack_teams")
        .select("*")
        .eq("slack_team_id", "T_TEST_001")
        .execute()
    )
    assert len(rows.data) == 1
    row = rows.data[0]
    assert row["owner_user_id"] == alice_id
    assert decrypt(row["encrypted_slack_bot_token"]) == "xoxb-alice-original"


def test_cancellation_redirects_to_cancelled(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
) -> None:
    """Scenario: User cancelled at Slack consent.

    Given the callback receives ?error=access_denied&state=<valid>
    When the callback runs with alice's cookie
    Then:
    - 302 redirect to /app?slack_install=cancelled
    - NO Slack API call was made (FakeAsyncClient.last_call is None)
    - NO teemo_slack_teams row was written

    RED: Fails with 404.
    """
    user_id, _ = alice_user
    state = make_valid_state(user_id)

    response = alice_client.get(
        "/api/slack/oauth/callback",
        params={"error": "access_denied", "state": state},
    )

    assert response.status_code == 302, f"Expected 302, got {response.status_code}: {response.text}"
    assert response.headers["location"] == "/app?slack_install=cancelled"

    # No Slack API was called
    assert FakeAsyncClient.last_call is None, (
        f"Expected no Slack API call, but got: {FakeAsyncClient.last_call}"
    )

    # No row written
    rows = (
        get_supabase()
        .table("teemo_slack_teams")
        .select("*")
        .like("slack_team_id", "T_TEST_%")
        .execute()
    )
    assert len(rows.data) == 0, f"Expected no rows written, found: {rows.data}"


def test_state_tampered_returns_400(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
) -> None:
    """Scenario: State signature tampered.

    Given a valid state token whose last signature character is flipped
    When the callback runs
    Then:
    - 400 HTTP error
    - Response body contains "invalid state"
    - NO Slack API call was made

    RED: Fails with 404.
    """
    user_id, _ = alice_user
    token = make_valid_state(user_id)

    # Flip the last character of the JWT signature segment
    head, body, sig = token.split(".")
    flipped = "A" if sig[-1] != "A" else "B"
    tampered = f"{head}.{body}.{sig[:-1]}{flipped}"

    response = alice_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code", "state": tampered},
    )

    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    assert "invalid state" in response.text

    # No Slack API was called
    assert FakeAsyncClient.last_call is None


def test_state_expired_redirects_to_expired(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
) -> None:
    """Scenario: State expired (>5 min).

    Given a state token with iat = now - 301s (1 second past the 300s window)
    When the callback runs
    Then:
    - 302 redirect to /app?slack_install=expired
    - NO Slack API call was made

    Uses create_slack_state_token(user_id, now=past) to craft an already-expired
    token without any sleep.

    RED: Fails with 404.
    """
    user_id, _ = alice_user
    past_iat = int(time.time()) - 301
    expired_state = create_slack_state_token(user_id, now=past_iat)

    response = alice_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code", "state": expired_state},
    )

    assert response.status_code == 302, f"Expected 302, got {response.status_code}: {response.text}"
    assert response.headers["location"] == "/app?slack_install=expired"

    # No Slack API was called
    assert FakeAsyncClient.last_call is None


def test_cross_user_state_returns_403(
    alice_user: tuple[str, str],
    bob_user: tuple[str, str],
    bob_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
) -> None:
    """Scenario: State user_id != auth user_id (cross-user attempt).

    Given the state token encodes alice's user_id
    And the auth cookie belongs to bob
    When the callback runs with bob's cookie
    Then:
    - 403 Forbidden
    - NO Slack API call was made

    This closes the cross-user hijacking vector (R4 in spec §1.2).

    RED: Fails with 404.
    """
    alice_id, _ = alice_user
    # bob is authenticated (bob_client cookie), but state is for alice
    alice_state = make_valid_state(alice_id)

    response = bob_client.get(
        "/api/slack/oauth/callback",
        params={"code": "ok_code", "state": alice_state},
    )

    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"

    # No Slack API was called
    assert FakeAsyncClient.last_call is None


def test_slack_ok_false_redirects_to_error(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scenario: Slack returns ok=false.

    Given mocked oauth.v2.access returns {"ok": False, "error": "invalid_code"}
    When the callback runs
    Then:
    - 302 redirect to /app?slack_install=error
    - A warning is logged containing the Slack error code ("invalid_code")

    RED: Fails with 404.
    """
    user_id, _ = alice_user
    FakeAsyncClient.queue({"ok": False, "error": "invalid_code"})
    state = make_valid_state(user_id)

    with caplog.at_level(logging.WARNING):
        response = alice_client.get(
            "/api/slack/oauth/callback",
            params={"code": "ok_code", "state": state},
        )

    assert response.status_code == 302, f"Expected 302, got {response.status_code}: {response.text}"
    assert response.headers["location"] == "/app?slack_install=error"

    # A warning log must contain the Slack error code
    assert "invalid_code" in caplog.text, (
        f"Expected 'invalid_code' in warning log. Captured log: {caplog.text!r}"
    )


def test_slack_missing_bot_user_id_redirects_to_error(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scenario: Slack response missing bot_user_id.

    Given mocked oauth.v2.access returns ok=true but WITHOUT bot_user_id
    When the callback runs
    Then:
    - 302 redirect to /app?slack_install=error
    - A warning is logged containing "bot_user_id" or "missing"

    RED: Fails with 404.
    """
    user_id, _ = alice_user

    # Build a success payload but without bot_user_id
    payload_no_bot = {k: v for k, v in MOCK_OAUTH_V2_ACCESS_OK.items() if k != "bot_user_id"}
    FakeAsyncClient.queue(payload_no_bot)

    state = make_valid_state(user_id)

    with caplog.at_level(logging.WARNING):
        response = alice_client.get(
            "/api/slack/oauth/callback",
            params={"code": "ok_code", "state": state},
        )

    assert response.status_code == 302, f"Expected 302, got {response.status_code}: {response.text}"
    assert response.headers["location"] == "/app?slack_install=error"

    # A warning log must indicate the missing bot_user_id
    assert "bot_user_id" in caplog.text or "missing" in caplog.text, (
        f"Expected 'bot_user_id' or 'missing' in warning log. Captured: {caplog.text!r}"
    )


def test_token_never_appears_in_logs(
    alice_user: tuple[str, str],
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
    cleanup_slack_teams: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scenario: Token never appears in logs.

    Given the happy path runs successfully with debug-level logging enabled
    When all log output for the request is captured
    Then:
    - The plaintext bot token "xoxb-test-token-1" does NOT appear in any log line
    - The encrypted ciphertext stored in the DB also does NOT appear in any log line

    This guards the Req 11 security constraint: the bot token (plaintext OR
    encrypted) must never leak into logs or responses.

    RED: Fails with 404 (happy path doesn't succeed yet).
    """
    user_id, _ = alice_user
    state = make_valid_state(user_id)

    with caplog.at_level(logging.DEBUG):
        response = alice_client.get(
            "/api/slack/oauth/callback",
            params={"code": "ok_code", "state": state},
        )

    assert response.status_code == 302
    assert response.headers["location"] == "/app?slack_install=ok"

    # Plaintext token must not appear in logs
    assert "xoxb-test-token-1" not in caplog.text, (
        "Plaintext bot token found in log output — security violation!"
    )

    # Fetch the encrypted ciphertext and assert it also doesn't appear in logs
    row = (
        get_supabase()
        .table("teemo_slack_teams")
        .select("encrypted_slack_bot_token")
        .eq("slack_team_id", "T_TEST_001")
        .single()
        .execute()
    )
    ciphertext = row.data["encrypted_slack_bot_token"]
    assert ciphertext not in caplog.text, (
        "Encrypted bot token ciphertext found in log output — security violation!"
    )
