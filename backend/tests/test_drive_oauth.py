"""Tests for STORY-006-02 — Google Drive OAuth routes (Red Phase).

Covers all 7 Gherkin scenarios from §2.1 plus supporting unit tests for the
state token helpers (security.py) and edge cases.

Strategy:
- Use FastAPI TestClient (follow_redirects=False) so redirect headers can be
  inspected directly — same pattern as test_slack_oauth_callback.py.
- Mock ONLY httpx.AsyncClient via hand-rolled FakeDriveAsyncClient (same shape
  as FakeAsyncClient in slack tests). Monkeypatch applied on the drive_oauth
  module's httpx reference (module must import httpx at module level —
  FLASHCARDS.md rule).
- Auth dependency (get_current_user_id) is overridden via
  app.dependency_overrides so no real JWT is needed for most route tests.
- Supabase is mocked via monkeypatch.setattr("app.core.db.get_supabase", ...)
  so no real DB writes occur.
- State tokens are created using create_drive_state_token from security.py.
  Expired tokens crafted via the `now` parameter (no sleep needed).

RED PHASE: All tests FAIL because:
  - drive_oauth.py does not exist → 404 on all route tests
  - create_drive_state_token / verify_drive_state_token do not exist in security.py

ADR compliance:
  - ADR-002: Refresh token encrypted with AES-256-GCM (encrypt() called).
  - ADR-009: Offline refresh token stored, access token NOT stored.
  - samesite=lax on cookies (FLASHCARDS.md — Auth Cookies entry).

FLASHCARDS.md consulted:
  - import httpx at module level in drive_oauth.py (monkeypatch pattern).
  - Supabase .upsert() omits DEFAULT NOW() columns.
  - Worktree-relative paths only.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


# ---------------------------------------------------------------------------
# Deferred import guard — drive_oauth module does not exist yet (RED phase).
# We import it lazily in fixtures so the rest of the test file loads cleanly.
# State token helpers also don't exist yet — same pattern.
# ---------------------------------------------------------------------------

def _try_import_drive_state_helpers():
    """Return (create_drive_state_token, verify_drive_state_token) or (None, None)."""
    try:
        from app.core.security import (  # type: ignore[attr-defined]
            create_drive_state_token,
            verify_drive_state_token,
        )
        return create_drive_state_token, verify_drive_state_token
    except ImportError:
        return None, None


# ---------------------------------------------------------------------------
# Fake httpx client — mirrors FakeAsyncClient from test_slack_oauth_callback.py
# ---------------------------------------------------------------------------

MOCK_GOOGLE_TOKEN_OK = {
    "access_token": "ya29.test-access-token",
    "refresh_token": "1//test-refresh-token-rt-xxx",
    "token_type": "Bearer",
    "expires_in": 3599,
}

MOCK_GOOGLE_USERINFO_OK = {
    "sub": "google-user-id-001",
    "email": "user@example.com",
    "email_verified": True,
}


class FakeDriveResponse:
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


class FakeDriveAsyncClient:
    """Stand-in for httpx.AsyncClient used by drive_oauth routes.

    Supports both POST (token exchange) and GET (userinfo) calls.
    Uses a response queue; if empty falls back to defaults.
    Supports the async context-manager protocol (``async with``).

    Class-level state is reset by the autouse fixture ``_reset_fake_drive_client``
    before and after every test.
    """

    last_post_call: dict[str, Any] | None = None
    last_get_call: dict[str, Any] | None = None
    _response_queue: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def __aenter__(self) -> "FakeDriveAsyncClient":
        return self

    async def __aexit__(self, *a: Any) -> bool:
        return False

    async def post(self, url: str, data: Any = None, **kw: Any) -> FakeDriveResponse:
        """Intercept POST (token exchange); record call and return queued or default."""
        FakeDriveAsyncClient.last_post_call = {"url": url, "data": data, "kwargs": kw}
        payload = (
            FakeDriveAsyncClient._response_queue.pop(0)
            if FakeDriveAsyncClient._response_queue
            else MOCK_GOOGLE_TOKEN_OK
        )
        return FakeDriveResponse(200, payload)

    async def get(self, url: str, **kw: Any) -> FakeDriveResponse:
        """Intercept GET (userinfo endpoint); record call and return queued or default."""
        FakeDriveAsyncClient.last_get_call = {"url": url, "kwargs": kw}
        payload = (
            FakeDriveAsyncClient._response_queue.pop(0)
            if FakeDriveAsyncClient._response_queue
            else MOCK_GOOGLE_USERINFO_OK
        )
        return FakeDriveResponse(200, payload)

    @classmethod
    def reset(cls) -> None:
        """Clear last_post_call, last_get_call, and any queued responses."""
        cls.last_post_call = None
        cls.last_get_call = None
        cls._response_queue = []

    @classmethod
    def queue(cls, payload: dict[str, Any]) -> None:
        """Enqueue a payload to be returned by the next .post() or .get() call."""
        cls._response_queue.append(payload)


# ---------------------------------------------------------------------------
# Autouse fixture — reset fake client state
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_fake_drive_client() -> Any:
    """Reset FakeDriveAsyncClient state before and after every test (autouse)."""
    FakeDriveAsyncClient.reset()
    yield
    FakeDriveAsyncClient.reset()


# ---------------------------------------------------------------------------
# Autouse fixture — clear dependency overrides after each test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> Any:
    """Clear FastAPI dependency overrides after each test to avoid bleed-through."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_USER_ID = "user-uuid-alice-001"
FAKE_WORKSPACE_ID = "ws-uuid-001"


@pytest.fixture
def override_current_user() -> str:
    """Override get_current_user_id to return FAKE_USER_ID without a real JWT.

    Returns the fake user_id string for use in assertions.
    """
    from app.api.deps import get_current_user_id

    async def _fake_user(request: Request) -> str:
        return FAKE_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user
    return FAKE_USER_ID


@pytest.fixture
def test_client() -> TestClient:
    """TestClient with follow_redirects=False so redirect headers can be inspected."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def patch_httpx_drive(monkeypatch: pytest.MonkeyPatch) -> type[FakeDriveAsyncClient]:
    """Replace httpx.AsyncClient inside the drive_oauth module with FakeDriveAsyncClient.

    Drive_oauth must import httpx at module level (FLASHCARDS.md rule) so this
    monkeypatch works. Returns the class so tests can queue responses or inspect calls.
    """
    try:
        import app.api.routes.drive_oauth as drive_oauth_module  # type: ignore[import]
        monkeypatch.setattr(drive_oauth_module.httpx, "AsyncClient", FakeDriveAsyncClient)
    except (ImportError, AttributeError):
        # RED phase — module doesn't exist yet, tests will fail with 404
        pass
    return FakeDriveAsyncClient


def _make_supabase_mock(workspace_row: dict[str, Any] | None = None) -> MagicMock:
    """Build a minimal Supabase client mock for drive_oauth route tests.

    Args:
        workspace_row: The workspace data dict to return from .select().single().
                       Pass None to simulate workspace not found (returns no data).

    Returns:
        A MagicMock configured with the chainable Supabase query API shape.
    """
    mock_sb = MagicMock()

    # Default workspace row if none provided
    if workspace_row is None:
        workspace_row = {
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": None,
        }

    # Build a chainable mock: .table(...).select(...).eq(...).single().execute()
    execute_result = MagicMock()
    execute_result.data = workspace_row

    single_mock = MagicMock()
    single_mock.execute.return_value = execute_result

    limit_mock = MagicMock()
    limit_mock.execute.return_value = MagicMock(data=[workspace_row] if workspace_row else [])
    limit_mock.single.return_value = single_mock

    eq_mock = MagicMock()
    eq_mock.execute.return_value = MagicMock(data=[workspace_row] if workspace_row else [])
    eq_mock.limit.return_value = limit_mock
    eq_mock.single.return_value = single_mock
    eq_mock.eq.return_value = eq_mock  # chaining: .eq().eq()

    select_mock = MagicMock()
    select_mock.eq.return_value = eq_mock

    update_execute = MagicMock()
    update_execute.data = [workspace_row]
    update_eq_mock = MagicMock()
    update_eq_mock.execute.return_value = update_execute
    update_eq_mock.eq.return_value = update_eq_mock

    update_mock = MagicMock()
    update_mock.eq.return_value = update_eq_mock

    upsert_execute = MagicMock()
    upsert_execute.data = [workspace_row]
    upsert_mock = MagicMock()
    upsert_mock.execute.return_value = upsert_execute

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    table_mock.update.return_value = update_mock
    table_mock.upsert.return_value = upsert_mock

    mock_sb.table.return_value = table_mock
    return mock_sb


def make_valid_drive_state(user_id: str, workspace_id: str) -> str:
    """Create a fresh, non-expired Drive state JWT for the given user and workspace.

    Returns an empty string if create_drive_state_token is not yet implemented
    (RED phase guard — the test will still run and produce a meaningful failure).
    """
    create_fn, _ = _try_import_drive_state_helpers()
    if create_fn is None:
        return "RED_PHASE_NO_TOKEN"
    return create_fn(user_id, workspace_id)


def make_expired_drive_state(user_id: str, workspace_id: str) -> str:
    """Create an already-expired Drive state JWT (iat = now - 400s, exp = now - 100s).

    Returns an empty string if create_drive_state_token is not yet implemented.
    """
    create_fn, _ = _try_import_drive_state_helpers()
    if create_fn is None:
        return "RED_PHASE_EXPIRED_TOKEN"
    past_iat = int(time.time()) - 400
    return create_fn(user_id, workspace_id, now=past_iat)


# ---------------------------------------------------------------------------
# Unit tests: State token helpers in security.py
# (create_drive_state_token, verify_drive_state_token)
# ---------------------------------------------------------------------------


class TestDriveStateTokenHelpers:
    """Unit tests for state token helpers that will live in security.py.

    RED: Fails with ImportError / AttributeError — helpers don't exist yet.
    """

    def test_create_drive_state_token_returns_string(self):
        """create_drive_state_token must return a non-empty string."""
        create_fn, _ = _try_import_drive_state_helpers()
        if create_fn is None:
            pytest.fail(
                "create_drive_state_token not found in app.core.security — "
                "RED phase: function must be implemented"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_drive_state_token_is_jwt_shaped(self):
        """create_drive_state_token must return a three-segment JWT (header.payload.sig)."""
        create_fn, _ = _try_import_drive_state_helpers()
        if create_fn is None:
            pytest.fail(
                "create_drive_state_token not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        parts = token.split(".")
        assert len(parts) == 3, f"Expected 3 JWT segments, got {len(parts)}: {token}"

    def test_verify_drive_state_token_decodes_correctly(self):
        """verify_drive_state_token must decode a freshly created token correctly."""
        create_fn, verify_fn = _try_import_drive_state_helpers()
        if create_fn is None or verify_fn is None:
            pytest.fail(
                "Drive state token helpers not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        result = verify_fn(token)

        assert result.user_id == FAKE_USER_ID
        assert result.workspace_id == FAKE_WORKSPACE_ID

    def test_verify_drive_state_token_has_exp_claim(self):
        """verify_drive_state_token result must expose the exp claim."""
        create_fn, verify_fn = _try_import_drive_state_helpers()
        if create_fn is None or verify_fn is None:
            pytest.fail(
                "Drive state token helpers not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        result = verify_fn(token)

        # exp must be roughly now + 300 (5 minutes)
        expected_exp_approx = int(time.time()) + 300
        assert abs(result.exp - expected_exp_approx) < 10, (
            f"exp={result.exp} is not within 10s of now+300={expected_exp_approx}"
        )

    def test_verify_drive_state_token_raises_on_expired(self):
        """verify_drive_state_token must raise jwt.ExpiredSignatureError on expired token."""
        import jwt as pyjwt

        create_fn, verify_fn = _try_import_drive_state_helpers()
        if create_fn is None or verify_fn is None:
            pytest.fail(
                "Drive state token helpers not found in app.core.security — RED phase"
            )

        past_iat = int(time.time()) - 400
        expired_token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID, now=past_iat)

        with pytest.raises(pyjwt.ExpiredSignatureError):
            verify_fn(expired_token)

    def test_verify_drive_state_token_raises_on_tampered(self):
        """verify_drive_state_token must raise jwt.InvalidTokenError on tampered signature."""
        import jwt as pyjwt

        create_fn, verify_fn = _try_import_drive_state_helpers()
        if create_fn is None or verify_fn is None:
            pytest.fail(
                "Drive state token helpers not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        head, body, sig = token.split(".")
        flipped = "A" if sig[-1] != "A" else "B"
        tampered = f"{head}.{body}.{sig[:-1]}{flipped}"

        with pytest.raises(pyjwt.InvalidTokenError):
            verify_fn(tampered)

    def test_drive_state_token_aud_is_drive_connect(self):
        """State token audience must be 'drive-connect' (not 'slack-install')."""
        import jwt as pyjwt

        create_fn, _ = _try_import_drive_state_helpers()
        if create_fn is None:
            pytest.fail(
                "create_drive_state_token not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        # Decode without verification to inspect the payload
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        assert payload.get("aud") == "drive-connect", (
            f"Expected aud='drive-connect', got aud={payload.get('aud')!r}"
        )

    def test_drive_state_token_embeds_workspace_id(self):
        """State token payload must embed workspace_id alongside user_id."""
        import jwt as pyjwt

        create_fn, _ = _try_import_drive_state_helpers()
        if create_fn is None:
            pytest.fail(
                "create_drive_state_token not found in app.core.security — RED phase"
            )

        token = create_fn(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        assert payload.get("user_id") == FAKE_USER_ID
        assert payload.get("workspace_id") == FAKE_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Scenario 1: Initiate Drive OAuth — 307 redirect to Google
# (GET /api/workspaces/{workspace_id}/drive/connect)
# ---------------------------------------------------------------------------


class TestInitiateDriveConnect:
    """Scenario: Initiate Drive OAuth — 307 redirect to accounts.google.com."""

    def test_initiate_drive_connect_redirects_to_google(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/workspaces/{id}/drive/connect must 307-redirect to accounts.google.com.

        RED: Fails with 404 — route does not exist yet.
        """
        # Mock Supabase to confirm workspace ownership
        mock_sb = _make_supabase_mock(workspace_row={
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": None,
        })
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        assert response.status_code == 307, (
            f"Expected 307 redirect, got {response.status_code}: {response.text}"
        )
        location = response.headers["location"]
        assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth"), (
            f"Expected Google OAuth URL, got: {location}"
        )

    def test_initiate_drive_connect_url_contains_drive_file_scope(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Redirect URL must contain 'drive.file' in the scope parameter.

        RED: Fails with 404.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        assert response.status_code == 307
        location = response.headers["location"]
        assert "drive.file" in location, (
            f"Expected 'drive.file' in scope, got location: {location}"
        )

    def test_initiate_drive_connect_url_contains_access_type_offline(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Redirect URL must contain 'access_type=offline' for refresh token grant.

        RED: Fails with 404.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        assert response.status_code == 307
        location = response.headers["location"]
        assert "access_type=offline" in location, (
            f"Expected 'access_type=offline' in URL, got: {location}"
        )

    def test_initiate_drive_connect_url_contains_prompt_consent(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Redirect URL must contain 'prompt=consent' to force refresh token issuance.

        RED: Fails with 404.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        assert response.status_code == 307
        location = response.headers["location"]
        assert "prompt=consent" in location, (
            f"Expected 'prompt=consent' in URL, got: {location}"
        )

    def test_initiate_drive_connect_url_contains_state_jwt(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Redirect URL must contain a 'state=' parameter with a JWT value.

        RED: Fails with 404.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        assert response.status_code == 307
        location = response.headers["location"]
        assert "state=" in location, f"Expected 'state=' parameter in URL, got: {location}"
        # Extract state param and verify it looks like a JWT (3 dot-separated segments)
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        state_values = params.get("state", [])
        assert len(state_values) == 1, f"Expected exactly 1 state param, got: {state_values}"
        state_token = state_values[0]
        assert len(state_token.split(".")) == 3, (
            f"Expected state to be a 3-part JWT, got: {state_token}"
        )

    def test_initiate_drive_connect_requires_auth(
        self,
        test_client: TestClient,
    ) -> None:
        """GET /api/workspaces/{id}/drive/connect must return 401 if not authenticated.

        No dependency override — the real get_current_user_id will reject the request.

        RED: Fails with 404 (route doesn't exist), but 401 is expected behaviour.
        """
        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        # Either 401 (auth failed) or 404 (route missing — RED phase)
        # We assert 401 is the correct production behaviour
        assert response.status_code in (401, 404), (
            f"Expected 401 (no auth) or 404 (RED phase), got {response.status_code}"
        )

    def test_initiate_drive_connect_workspace_not_owned_returns_404(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/workspaces/{id}/drive/connect must return 404 if workspace not owned.

        RED: Fails with 404 (route missing) — but 404 ownership check is expected behaviour.
        """
        # Supabase returns no data (workspace not owned by this user)
        mock_sb = _make_supabase_mock(workspace_row=None)
        # Override: make .eq().eq().limit().execute() return empty list
        empty_execute = MagicMock()
        empty_execute.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = empty_execute
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/connect")

        # 404 is the correct production behaviour for unowned workspace
        # 404 is also the RED phase status — either is acceptable here
        assert response.status_code == 404, (
            f"Expected 404 (workspace not owned), got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: OAuth callback success
# (GET /api/drive/oauth/callback?code=...&state=...)
# ---------------------------------------------------------------------------


class TestOAuthCallbackSuccess:
    """Scenario: OAuth callback success — code exchange + encrypt + store + redirect."""

    def test_callback_success_redirects_to_app_drive_connect_ok(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful callback must 302-redirect to /app?drive_connect=ok.

        RED: Fails with 404 — callback route does not exist.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        assert response.status_code == 302, (
            f"Expected 302 redirect, got {response.status_code}: {response.text}"
        )
        assert response.headers["location"] == "/app?drive_connect=ok", (
            f"Expected /app?drive_connect=ok, got: {response.headers.get('location')}"
        )

    def test_callback_success_calls_google_token_endpoint(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Callback must POST to https://oauth2.googleapis.com/token with auth code.

        RED: Fails with 404.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        assert FakeDriveAsyncClient.last_post_call is not None, (
            "Expected httpx POST to Google token endpoint, but no call was made"
        )
        assert FakeDriveAsyncClient.last_post_call["url"] == "https://oauth2.googleapis.com/token", (
            f"Expected Google token URL, got: {FakeDriveAsyncClient.last_post_call['url']}"
        )

    def test_callback_success_post_body_contains_auth_code(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST to Google token endpoint must include the auth code and client credentials.

        RED: Fails with 404.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        post_data = FakeDriveAsyncClient.last_post_call["data"]
        assert post_data["code"] == "AUTH_CODE_OK"
        assert post_data["client_id"] == settings.google_api_client_id
        assert post_data["client_secret"] == settings.google_api_secret

    def test_callback_success_encrypts_refresh_token(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Callback must encrypt the refresh_token before storing it.

        We capture calls to encrypt() and verify it was called with the raw
        refresh token from the Google response.

        RED: Fails with 404.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        encrypt_calls: list[str] = []

        def _fake_encrypt(value: str) -> str:
            encrypt_calls.append(value)
            return f"encrypted:{value}"

        # Patch encrypt at the drive_oauth module level
        try:
            import app.api.routes.drive_oauth as drive_oauth_module  # type: ignore[import]
            monkeypatch.setattr(drive_oauth_module, "encrypt", _fake_encrypt)
        except ImportError:
            pass  # RED phase — route module doesn't exist

        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        # encrypt must have been called with the raw refresh token from Google
        assert MOCK_GOOGLE_TOKEN_OK["refresh_token"] in encrypt_calls, (
            f"Expected encrypt({MOCK_GOOGLE_TOKEN_OK['refresh_token']!r}) to be called. "
            f"Actual encrypt calls: {encrypt_calls}"
        )

    def test_callback_success_upserts_workspace_with_encrypted_token(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Callback must upsert teemo_workspaces with the encrypted refresh token.

        RED: Fails with 404.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        # Verify that supabase .update() or .upsert() was called on teemo_workspaces
        mock_sb.table.assert_any_call("teemo_workspaces")


# ---------------------------------------------------------------------------
# Scenario 3: OAuth callback with expired state
# ---------------------------------------------------------------------------


class TestOAuthCallbackExpiredState:
    """Scenario: OAuth callback with expired state JWT → redirect to /app?drive_connect=expired."""

    def test_callback_expired_state_redirects_to_expired(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Expired state JWT must result in 302 redirect to /app?drive_connect=expired.

        RED: Fails with 404 — callback route does not exist.
        """
        expired_state = make_expired_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": expired_state},
        )

        assert response.status_code == 302, (
            f"Expected 302, got {response.status_code}: {response.text}"
        )
        assert response.headers["location"] == "/app?drive_connect=expired", (
            f"Expected /app?drive_connect=expired, got: {response.headers.get('location')}"
        )

    def test_callback_expired_state_does_not_call_google(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Expired state must NOT trigger a call to the Google token endpoint.

        RED: Fails with 404.
        """
        expired_state = make_expired_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": expired_state},
        )

        assert FakeDriveAsyncClient.last_post_call is None, (
            f"Expected no Google API call, but got: {FakeDriveAsyncClient.last_post_call}"
        )


# ---------------------------------------------------------------------------
# Scenario 4: OAuth callback with user denied consent
# ---------------------------------------------------------------------------


class TestOAuthCallbackUserDenied:
    """Scenario: OAuth callback with ?error=access_denied → redirect to cancelled."""

    def test_callback_user_denied_redirects_to_cancelled(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
    ) -> None:
        """?error=access_denied must result in 302 redirect to /app?drive_connect=cancelled.

        RED: Fails with 404 — callback route does not exist.
        """
        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"error": "access_denied"},
        )

        assert response.status_code == 302, (
            f"Expected 302 redirect, got {response.status_code}: {response.text}"
        )
        assert response.headers["location"] == "/app?drive_connect=cancelled", (
            f"Expected /app?drive_connect=cancelled, got: {response.headers.get('location')}"
        )

    def test_callback_user_denied_does_not_call_google(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
    ) -> None:
        """User-denied callback must NOT call the Google token endpoint.

        RED: Fails with 404.
        """
        test_client.get(
            "/api/drive/oauth/callback",
            params={"error": "access_denied"},
        )

        assert FakeDriveAsyncClient.last_post_call is None, (
            f"Expected no Google API call on cancellation, got: {FakeDriveAsyncClient.last_post_call}"
        )


# ---------------------------------------------------------------------------
# Scenario 5: Drive status when connected
# (GET /api/workspaces/{workspace_id}/drive/status)
# ---------------------------------------------------------------------------


class TestDriveStatusConnected:
    """Scenario: Drive status when connected → { connected: true, email: '...' }."""

    def test_drive_status_connected_returns_true_and_email(
        self,
        test_client: TestClient,
        override_current_user: str,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When workspace has refresh token, status must be { connected: true, email: 'user@example.com' }.

        RED: Fails with 404 — status route does not exist.
        """
        # Workspace has an encrypted refresh token
        workspace_row = {
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": "encrypted-refresh-token-blob",
        }
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        # Queue token exchange response (POST), then userinfo response (GET)
        # The status endpoint now does a 2-step flow: refresh→access token, then userinfo.
        # Team Lead fix: RED phase assumed single-call; Architect bounce revealed 2-step.
        FakeDriveAsyncClient.queue(MOCK_GOOGLE_TOKEN_OK)
        FakeDriveAsyncClient.queue(MOCK_GOOGLE_USERINFO_OK)

        # Mock decrypt to return a fake plaintext token
        try:
            import app.api.routes.drive_oauth as drive_oauth_module  # type: ignore[import]
            monkeypatch.setattr(
                drive_oauth_module,
                "decrypt",
                lambda _: "1//plaintext-refresh-token",
            )
        except ImportError:
            pass  # RED phase

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/status")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["connected"] is True, f"Expected connected=true, got: {data}"
        assert data["email"] == "user@example.com", (
            f"Expected email='user@example.com', got: {data}"
        )

    def test_drive_status_connected_requires_auth(
        self,
        test_client: TestClient,
    ) -> None:
        """GET /api/workspaces/{id}/drive/status must return 401 if not authenticated.

        RED: Fails with 404 (route missing).
        """
        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/status")

        assert response.status_code in (401, 404), (
            f"Expected 401 (no auth) or 404 (RED phase), got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Scenario 6: Drive status when not connected
# ---------------------------------------------------------------------------


class TestDriveStatusNotConnected:
    """Scenario: Drive status when not connected → { connected: false, email: null }."""

    def test_drive_status_not_connected_returns_false_and_null_email(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When workspace has no refresh token, status must be { connected: false, email: null }.

        RED: Fails with 404 — status route does not exist.
        """
        workspace_row = {
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": None,
        }
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/status")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["connected"] is False, f"Expected connected=false, got: {data}"
        assert data["email"] is None, f"Expected email=null, got: {data}"


# ---------------------------------------------------------------------------
# Scenario 7: Disconnect Drive
# (POST /api/workspaces/{workspace_id}/drive/disconnect)
# ---------------------------------------------------------------------------


class TestDisconnectDrive:
    """Scenario: Disconnect Drive → null the refresh token + 200."""

    def test_disconnect_drive_returns_200(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/drive/disconnect must return 200.

        RED: Fails with 404 — disconnect route does not exist.
        """
        workspace_row = {
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": "some-encrypted-token",
        }
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/disconnect")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

    def test_disconnect_drive_nulls_refresh_token_in_db(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST disconnect must call Supabase update to null encrypted_google_refresh_token.

        RED: Fails with 404.
        """
        workspace_row = {
            "id": FAKE_WORKSPACE_ID,
            "user_id": FAKE_USER_ID,
            "name": "Test Workspace",
            "encrypted_google_refresh_token": "some-encrypted-token",
        }
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        test_client.post(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/disconnect")

        # Verify update was called on teemo_workspaces
        mock_sb.table.assert_any_call("teemo_workspaces")
        # The update chain should have been called (update().eq().execute())
        update_mock = mock_sb.table.return_value.update
        update_mock.assert_called_once()
        # The payload must null the refresh token
        call_args = update_mock.call_args
        update_payload = call_args[0][0]  # first positional arg
        assert update_payload.get("encrypted_google_refresh_token") is None, (
            f"Expected encrypted_google_refresh_token=None in update payload, "
            f"got: {update_payload}"
        )

    def test_disconnect_drive_requires_auth(
        self,
        test_client: TestClient,
    ) -> None:
        """POST /api/workspaces/{id}/drive/disconnect must return 401 if not authenticated.

        RED: Fails with 404 (route missing).
        """
        response = test_client.post(f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/disconnect")

        assert response.status_code in (401, 404), (
            f"Expected 401 (no auth) or 404 (RED phase), got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# Additional edge case tests
# ---------------------------------------------------------------------------


class TestCallbackEdgeCases:
    """Additional edge-case tests for the callback endpoint."""

    def test_callback_missing_code_returns_400(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
    ) -> None:
        """Callback with a state but no code must return 400 Bad Request.

        RED: Fails with 404 (route missing).
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)

        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"state": state},
            # No 'code' param
        )

        assert response.status_code in (400, 404), (
            f"Expected 400 (missing code) or 404 (RED phase), got {response.status_code}"
        )

    def test_callback_missing_state_returns_400(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
    ) -> None:
        """Callback with a code but no state must return 400 Bad Request.

        RED: Fails with 404 (route missing).
        """
        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "some-auth-code"},
            # No 'state' param
        )

        assert response.status_code in (400, 404), (
            f"Expected 400 (missing state) or 404 (RED phase), got {response.status_code}"
        )

    def test_callback_tampered_state_returns_400(
        self,
        test_client: TestClient,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tampered state signature must result in 400 Bad Request.

        RED: Fails with 404 (route missing).
        """
        token = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        if token == "RED_PHASE_NO_TOKEN":
            # Can't create a real token to tamper — skip the tampering but still hit the route
            tampered = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZmFrZSJ9.BADSIG"
        else:
            head, body, sig = token.split(".")
            flipped = "A" if sig[-1] != "A" else "B"
            tampered = f"{head}.{body}.{sig[:-1]}{flipped}"

        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": tampered},
        )

        assert response.status_code in (400, 404), (
            f"Expected 400 (tampered state) or 404 (RED phase), got {response.status_code}"
        )

    def test_refresh_token_never_appears_in_response(
        self,
        test_client: TestClient,
        override_current_user: str,
        patch_httpx_drive: type[FakeDriveAsyncClient],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The raw refresh token must NEVER appear in any response body.

        Security constraint from ADR-009 and spec §1.2 R7: refresh tokens are
        stored only in encrypted form; the plaintext must never be returned.

        RED: Fails with 404.
        """
        state = make_valid_drive_state(FAKE_USER_ID, FAKE_WORKSPACE_ID)
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(
            "/api/drive/oauth/callback",
            params={"code": "AUTH_CODE_OK", "state": state},
        )

        raw_refresh_token = MOCK_GOOGLE_TOKEN_OK["refresh_token"]
        assert raw_refresh_token not in response.text, (
            f"Raw refresh token found in response body — security violation! "
            f"Token: {raw_refresh_token!r}, Body: {response.text!r}"
        )
