"""Integration tests for STORY-004-01 — BYOK Key Routes.

7 tests covering all Gherkin scenarios from §2.1 of the story spec.

Strategy:
- REAL Supabase for DB operations (workspaces, users). No DB mocking.
- Mock ONLY httpx.AsyncClient via hand-rolled FakeAsyncClient + monkeypatch on
  the key_validator module attribute. Follows the identical pattern established
  in test_slack_oauth_callback.py (S-04 FLASHCARDS.md rule).
- Users registered via /api/auth/register; workspaces inserted directly via
  get_supabase() for setup speed.
- Workspace inserts omit slack_team_id (NULL, which PostgreSQL FK allows for
  nullable FK columns) so no teemo_slack_teams seed row is needed.
- All test workspaces are cleaned up via cascade delete on teemo_users.

Mock pattern reference:
    import app.services.key_validator as kv_module
    monkeypatch.setattr(kv_module.httpx, "AsyncClient", FakeAsyncClient)

This works because key_validator.py imports httpx at MODULE LEVEL per the
FLASHCARDS.md S-04 rule.

ADR compliance:
- ADR-002: encrypted_api_key is asserted != plaintext; decrypts back correctly.
- ADR-024: ownership filter — cross-user access returns 404.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_supabase
from app.core.security import create_access_token
from app.core.encryption import decrypt


# ---------------------------------------------------------------------------
# Hand-rolled httpx mock — same pattern as test_slack_oauth_callback.py
# ---------------------------------------------------------------------------


class FakeResponse:
    """Minimal stand-in for httpx.Response — provides .json(), .text, and .status_code."""

    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, Any]:
        """Return the payload dict."""
        return self._payload

    @property
    def text(self) -> str:
        """Return the payload serialised as JSON string."""
        return json.dumps(self._payload)


class FakeAsyncClient:
    """Stand-in for httpx.AsyncClient.

    Supports async context-manager protocol (``async with``).
    Intercepts ``.get()`` and ``.post()`` calls.
    Queued responses are consumed in FIFO order; the default response is
    HTTP 200 with an empty dict if the queue is empty.

    Class-level state is reset by the autouse ``_reset_fake_client`` fixture.
    """

    last_call: dict[str, Any] | None = None
    _response_queue: list[tuple[int, dict[str, Any]]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *a: Any) -> bool:
        return False

    def _next_response(self, url: str, method: str, **kw: Any) -> FakeResponse:
        FakeAsyncClient.last_call = {"url": url, "method": method, "kwargs": kw}
        if FakeAsyncClient._response_queue:
            status, payload = FakeAsyncClient._response_queue.pop(0)
            return FakeResponse(status, payload)
        return FakeResponse(200, {})

    async def get(self, url: str, **kw: Any) -> FakeResponse:
        """Intercept GET requests."""
        return self._next_response(url, "GET", **kw)

    async def post(self, url: str, **kw: Any) -> FakeResponse:
        """Intercept POST requests."""
        return self._next_response(url, "POST", **kw)

    @classmethod
    def reset(cls) -> None:
        """Clear last_call and queued responses."""
        cls.last_call = None
        cls._response_queue = []

    @classmethod
    def queue(cls, status: int, payload: dict[str, Any] | None = None) -> None:
        """Enqueue a (status, payload) pair to be returned by the next call."""
        cls._response_queue.append((status, payload or {}))


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
    """Replace httpx.AsyncClient inside key_validator module with FakeAsyncClient.

    key_validator.py imports httpx at module level, so we patch the
    ``AsyncClient`` attribute on the module-level ``httpx`` reference.
    This ensures every ``async with httpx.AsyncClient(...)`` in the validator
    routes through FakeAsyncClient.

    Returns the FakeAsyncClient class so tests can queue responses and
    inspect last_call.
    """
    import app.services.key_validator as kv_module

    monkeypatch.setattr(kv_module.httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient


@pytest.fixture
def alice_user() -> Any:
    """Register alice in teemo_users and yield (user_id, token, client).

    Uses @teemo.test address (accepted by LaxEmailStr in the register route).
    The registered user and any cascade-deleted workspaces are cleaned up
    after yield.
    """
    email = f"alice-keys+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    http_client = TestClient(app)
    resp = http_client.post("/api/auth/register", json={"email": email, "password": password})
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
    # Cleanup — CASCADE removes teemo_workspaces
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def bob_user() -> Any:
    """Register bob — a second user for cross-user ownership tests."""
    email = f"bob-keys+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    http_client = TestClient(app)
    resp = http_client.post("/api/auth/register", json={"email": email, "password": password})
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
def alice_client(alice_user: tuple[str, str]) -> TestClient:
    """TestClient pre-loaded with alice's access_token cookie."""
    _, token = alice_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client


@pytest.fixture
def bob_client(bob_user: tuple[str, str]) -> TestClient:
    """TestClient pre-loaded with bob's access_token cookie."""
    _, token = bob_user
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", token)
    return client


def _create_workspace(user_id: str, name: str = "Test Workspace") -> str:
    """Insert a workspace row directly via Supabase and return its id.

    slack_team_id is NULL (nullable FK — PostgreSQL allows NULL FK values),
    so no teemo_slack_teams seed row is required for key tests.

    Parameters
    ----------
    user_id : str
        The owning user's UUID string.
    name : str
        Workspace display name.

    Returns
    -------
    str
        The newly created workspace UUID string.
    """
    result = (
        get_supabase()
        .table("teemo_workspaces")
        .insert(
            {
                "user_id": user_id,
                "name": name,
                "is_default_for_team": True,
            }
        )
        .execute()
    )
    assert result.data, "Failed to create test workspace"
    return str(result.data[0]["id"])


# ---------------------------------------------------------------------------
# Tests — 7 scenarios from §4.1
# ---------------------------------------------------------------------------


def test_validate_valid_openai_key(
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
) -> None:
    """Scenario: POST /api/keys/validate — valid OpenAI key.

    Given the user is authenticated
    And mock httpx returns HTTP 200 for the OpenAI models endpoint
    When POST /api/keys/validate {provider: "openai", key: "sk-test"}
    Then response 200 {valid: true, message: "Valid"}
    And no DB row is modified.
    """
    # Queue a 200 response for the OpenAI probe
    patch_httpx.queue(200, {"data": []})

    resp = alice_client.post(
        "/api/keys/validate",
        json={"provider": "openai", "key": "sk-test-valid-key"},
    )

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["valid"] is True
    assert body["message"] == "Valid"


def test_validate_invalid_key(
    alice_client: TestClient,
    patch_httpx: type[FakeAsyncClient],
) -> None:
    """Scenario: POST /api/keys/validate — invalid key (auth error).

    Given the user is authenticated
    And mock httpx returns HTTP 401 with an error message
    When POST /api/keys/validate {provider: "openai", key: "bad-key"}
    Then response 200 {valid: false, message: contains error text}
    """
    patch_httpx.queue(401, {"error": {"message": "Incorrect API key provided"}})

    resp = alice_client.post(
        "/api/keys/validate",
        json={"provider": "openai", "key": "bad-key"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["message"] != ""  # some error description present


def test_save_key_success(
    alice_user: tuple[str, str],
    alice_client: TestClient,
) -> None:
    """Scenario: POST /api/workspaces/{id}/keys — saves key successfully.

    Given alice owns workspace W1
    When POST /api/workspaces/W1/keys {provider: "openai", key: "sk-abcdefghijklmnopxyz9"}
    Then response 201 {provider: "openai", key_mask: "sk-ab...xyz9", has_key: true, ai_model: "gpt-4o"}
    And DB row has encrypted_api_key != plaintext AND decrypts correctly.
    """
    user_id, _ = alice_user
    ws_id = _create_workspace(user_id)
    plaintext_key = "sk-abcdefghijklmnopxyz9"

    resp = alice_client.post(
        f"/api/workspaces/{ws_id}/keys",
        json={"provider": "openai", "key": plaintext_key},
    )

    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["provider"] == "openai"
    assert body["has_key"] is True
    # key[:4] = "sk-a" (s,k,-,a), key[-4:] = "xyz9"
    assert body["key_mask"] == "sk-a...xyz9"
    assert body["ai_model"] == "gpt-4o"  # default model for openai

    # Verify DB has encrypted blob — NOT the plaintext
    row = (
        get_supabase()
        .table("teemo_workspaces")
        .select("encrypted_api_key, ai_provider, ai_model, key_mask")
        .eq("id", ws_id)
        .single()
        .execute()
    )
    db_row = row.data
    assert db_row["encrypted_api_key"] is not None
    assert db_row["encrypted_api_key"] != plaintext_key  # ADR-002: never plaintext in DB
    assert decrypt(db_row["encrypted_api_key"]) == plaintext_key  # decrypts correctly
    assert db_row["ai_provider"] == "openai"
    assert db_row["ai_model"] == "gpt-4o"
    assert db_row["key_mask"] == "sk-a...xyz9"


def test_save_key_ownership_enforced(
    alice_user: tuple[str, str],
    bob_client: TestClient,
) -> None:
    """Scenario: POST /api/workspaces/{id}/keys — different user → 404.

    Given alice owns workspace W1
    And bob is authenticated (different user)
    When bob POSTs to /api/workspaces/W1/keys
    Then response 404
    """
    alice_id, _ = alice_user
    ws_id = _create_workspace(alice_id)

    resp = bob_client.post(
        f"/api/workspaces/{ws_id}/keys",
        json={"provider": "openai", "key": "sk-test-key-12345"},
    )

    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"


def test_get_key_with_key(
    alice_user: tuple[str, str],
    alice_client: TestClient,
) -> None:
    """Scenario: GET /api/workspaces/{id}/keys — key exists.

    Given workspace W1 has a stored key
    When GET /api/workspaces/W1/keys
    Then response 200 {provider: "google", key_mask: "ai-t...est9", has_key: true}
    """
    from app.core.encryption import encrypt as do_encrypt

    user_id, _ = alice_user
    ws_id = _create_workspace(user_id)
    plaintext = "ai-test-key-for-google0001test9"
    encrypted = do_encrypt(plaintext)
    mask = "ai-t...est9"

    # Directly patch the workspace with a key
    get_supabase().table("teemo_workspaces").update(
        {
            "encrypted_api_key": encrypted,
            "ai_provider": "google",
            "ai_model": "gemini-2.5-flash",
            "key_mask": mask,
        }
    ).eq("id", ws_id).execute()

    resp = alice_client.get(f"/api/workspaces/{ws_id}/keys")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["has_key"] is True
    assert body["provider"] == "google"
    assert body["key_mask"] == mask
    assert body["ai_model"] == "gemini-2.5-flash"


def test_get_key_no_key(
    alice_user: tuple[str, str],
    alice_client: TestClient,
) -> None:
    """Scenario: GET /api/workspaces/{id}/keys — no key stored.

    Given workspace W1 has encrypted_api_key = NULL
    When GET /api/workspaces/W1/keys
    Then response 200 {has_key: false, provider: null, key_mask: null}
    """
    user_id, _ = alice_user
    ws_id = _create_workspace(user_id)
    # No key is set on the freshly-created workspace

    resp = alice_client.get(f"/api/workspaces/{ws_id}/keys")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["has_key"] is False
    assert body["provider"] is None
    assert body["key_mask"] is None


def test_delete_key(
    alice_user: tuple[str, str],
    alice_client: TestClient,
) -> None:
    """Scenario: DELETE /api/workspaces/{id}/keys — NULLs out all key fields.

    Given workspace W1 has a stored key
    When DELETE /api/workspaces/W1/keys
    Then response 200 {message: "Key deleted"}
    And DB: encrypted_api_key = NULL, ai_provider = NULL, ai_model = NULL, key_mask = NULL
    """
    from app.core.encryption import encrypt as do_encrypt

    user_id, _ = alice_user
    ws_id = _create_workspace(user_id)

    # Pre-seed a key so there's something to delete
    get_supabase().table("teemo_workspaces").update(
        {
            "encrypted_api_key": do_encrypt("sk-some-key-1234567890"),
            "ai_provider": "anthropic",
            "ai_model": "claude-sonnet-4-6",
            "key_mask": "sk-s...7890",
        }
    ).eq("id", ws_id).execute()

    resp = alice_client.delete(f"/api/workspaces/{ws_id}/keys")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["message"] == "Key deleted"

    # Verify DB columns are NULLed out
    row = (
        get_supabase()
        .table("teemo_workspaces")
        .select("encrypted_api_key, ai_provider, ai_model, key_mask")
        .eq("id", ws_id)
        .single()
        .execute()
    )
    db_row = row.data
    assert db_row["encrypted_api_key"] is None
    assert db_row["ai_provider"] is None
    assert db_row["ai_model"] is None
    assert db_row["key_mask"] is None
