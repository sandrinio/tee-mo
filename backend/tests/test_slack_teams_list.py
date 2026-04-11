"""Integration tests for STORY-005A-05 — GET /api/slack/teams.

5 tests covering all Gherkin scenarios from §2.1:
  1. Empty list returns 200 with empty teams array.
  2. Single team returned with correct fields, no encrypted token in body.
  3. Only the authenticated user's teams are returned (multi-user isolation).
  4. Anonymous (no cookie) request returns 401.
  5. Teams are ordered newest-first by installed_at.

Strategy:
- REAL Supabase (no DB mocking). Users registered via /api/auth/register and
  cleaned up via fixtures. Slack team rows with T_LIST_* IDs purged by
  cleanup_list_rows fixture before and after each test.
- TestClient with follow_redirects=False for auth checks.
- create_access_token used directly to create auth cookies so we do not depend
  on the /api/auth/login round-trip.

ADR compliance:
- ADR-010: encrypted_slack_bot_token NEVER appears in response body.
- ADR-024: slack_team_id PK, owner_user_id FK.
- Explicit-column select enforced by the route (.select("slack_team_id, slack_bot_user_id, installed_at")).

FLASHCARDS.md consulted:
- get_supabase() is the only DB entry point (service-role key, cached).
- Pydantic EmailStr: fixtures use @teemo.test — register route uses LaxEmailStr.
- samesite="lax" on auth cookies — deliberate for OAuth redirect flows.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import get_supabase
from app.core.encryption import encrypt
from app.core.security import create_access_token


# --- Helpers ------------------------------------------------------------------


def _register_user(email_prefix: str = "alice") -> tuple[str, str, str]:
    """Register a real user via /api/auth/register, return (user_id, access_token, email).

    Uses a UUID suffix to guarantee no email collision between parallel test runs.
    The email domain is @teemo.test — accepted because the register route uses
    LaxEmailStr (see FLASHCARDS.md — Pydantic + email-validator entry).
    """
    email = f"{email_prefix}+{uuid.uuid4().hex[:8]}@teemo.test"
    password = "Password123!@#"
    client = TestClient(app)
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    row = get_supabase().table("teemo_users").select("id").eq("email", email).single().execute()
    user_id = str(row.data["id"])
    token = create_access_token(uuid.UUID(user_id))
    return user_id, token, email


def _seed_team(
    user_id: str,
    team_id: str,
    bot_user_id: str,
    bot_token: str,
    installed_at: datetime | None = None,
) -> str:
    """Insert a real teemo_slack_teams row with an encrypted bot token.

    Returns the ciphertext so callers can assert it is NOT in responses.
    installed_at defaults to Supabase's server-side DEFAULT NOW() when None.
    """
    ciphertext = encrypt(bot_token)
    row: dict = {
        "slack_team_id": team_id,
        "owner_user_id": user_id,
        "slack_bot_user_id": bot_user_id,
        "encrypted_slack_bot_token": ciphertext,
    }
    if installed_at is not None:
        row["installed_at"] = installed_at.isoformat()
    get_supabase().table("teemo_slack_teams").insert(row).execute()
    return ciphertext


# --- Fixtures -----------------------------------------------------------------


@pytest.fixture
def alice():
    """Register alice, yield (user_id, access_token), delete her user row on teardown."""
    user_id, token, email = _register_user("alice")
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def bob():
    """Register bob, yield (user_id, access_token), delete his user row on teardown."""
    user_id, token, email = _register_user("bob")
    yield user_id, token
    get_supabase().table("teemo_users").delete().eq("email", email).execute()


@pytest.fixture
def cleanup_list_rows():
    """Remove all T_LIST_* slack_team rows before and after the test.

    Prevents cross-test contamination when tests share the same real Supabase
    instance. Runs cleanup eagerly (before test) in case a previous test crashed
    before its teardown.
    """
    def _clean() -> None:
        get_supabase().table("teemo_slack_teams").delete().like("slack_team_id", "T_LIST_%").execute()

    _clean()
    yield
    _clean()


# --- Tests --------------------------------------------------------------------


def test_empty_list_returns_200_with_empty_teams(alice):
    """Gherkin S1: alice is registered but has no teemo_slack_teams rows.

    GET /api/slack/teams must return HTTP 200 with body {"teams": []}.
    Empty list is NOT a 404 — the route always returns 200 per spec §1.
    """
    user_id, token = alice
    client = TestClient(app, cookies={"access_token": token})
    resp = client.get("/api/slack/teams")

    assert resp.status_code == 200
    assert resp.json() == {"teams": []}


def test_single_team(alice, cleanup_list_rows):
    """Gherkin S2: alice has one installed team.

    GET /api/slack/teams must return the correct slack_team_id and
    slack_bot_user_id, include installed_at, and MUST NOT include
    the encrypted_slack_bot_token in the response body at all.
    ADR-010: explicit-column select is the DB-layer defence; this test is the
    application-layer guard.
    """
    user_id, token = alice
    ciphertext = _seed_team(user_id, "T_LIST_001", "UBOT_LIST_001", "xoxb-list-one")

    client = TestClient(app, cookies={"access_token": token})
    resp = client.get("/api/slack/teams")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["teams"]) == 1

    team = body["teams"][0]
    assert team["slack_team_id"] == "T_LIST_001"
    assert team["slack_bot_user_id"] == "UBOT_LIST_001"
    assert "installed_at" in team

    # Token MUST NOT appear in the response body in any form.
    body_text = json.dumps(body)
    assert ciphertext not in body_text, "Encrypted ciphertext must not appear in response"
    assert "encrypted" not in body_text.lower(), "'encrypted' key must not appear in response"
    assert "xoxb-list-one" not in body_text, "Plaintext bot token must not appear in response"


def test_only_my_teams(alice, bob, cleanup_list_rows):
    """Gherkin S3: alice owns T_LIST_AA, bob owns T_LIST_BB.

    GET /api/slack/teams as alice must return only T_LIST_AA.
    T_LIST_BB (bob's row) must not appear anywhere in the response.
    This validates the .eq("owner_user_id", user_id) filter in the route.
    """
    alice_id, alice_token = alice
    bob_id, _bob_token = bob

    _seed_team(alice_id, "T_LIST_AA", "UBOT_AA", "xoxb-alice-aa")
    _seed_team(bob_id, "T_LIST_BB", "UBOT_BB", "xoxb-bob-bb")

    client = TestClient(app, cookies={"access_token": alice_token})
    resp = client.get("/api/slack/teams")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["teams"]) == 1
    assert body["teams"][0]["slack_team_id"] == "T_LIST_AA"
    assert "T_LIST_BB" not in json.dumps(body), "Bob's team must not appear in Alice's response"


def test_anonymous_returns_401():
    """Gherkin S4: no auth cookie present.

    GET /api/slack/teams without an access_token cookie must return 401.
    The route uses get_current_user_id (not _optional), so missing/invalid
    cookies are rejected at the FastAPI dependency layer.
    """
    client = TestClient(app)
    resp = client.get("/api/slack/teams")
    assert resp.status_code == 401


def test_ordering_newest_first(alice, cleanup_list_rows):
    """Gherkin S5: three teams inserted with explicit timestamps.

    GET /api/slack/teams must return them ordered newest installed_at first.
    The route uses .order("installed_at", desc=True) — this test validates
    that the ordering reaches the client correctly.
    """
    user_id, token = alice
    now = datetime.now(timezone.utc)

    _seed_team(user_id, "T_LIST_OLD", "UBOT_OLD", "xoxb-old", installed_at=now - timedelta(hours=2))
    _seed_team(user_id, "T_LIST_MID", "UBOT_MID", "xoxb-mid", installed_at=now - timedelta(hours=1))
    _seed_team(user_id, "T_LIST_NEW", "UBOT_NEW", "xoxb-new", installed_at=now)

    client = TestClient(app, cookies={"access_token": token})
    resp = client.get("/api/slack/teams")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["teams"]) == 3
    assert body["teams"][0]["slack_team_id"] == "T_LIST_NEW"
    assert body["teams"][2]["slack_team_id"] == "T_LIST_OLD"
