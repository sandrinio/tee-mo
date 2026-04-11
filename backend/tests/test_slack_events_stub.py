"""Unit tests for the S-03 Slack events verification stub."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_url_verification_returns_challenge_as_plain_text():
    """Scenario: Slack url_verification challenge round-trips."""
    response = client.post(
        "/api/slack/events",
        json={
            "type": "url_verification",
            "challenge": "abc123",
            "token": "legacy-ignored",
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "abc123"


def test_other_event_types_return_202_accepted():
    """Scenario: Other event types return 202."""
    response = client.post(
        "/api/slack/events",
        json={
            "type": "event_callback",
            "event": {"type": "app_mention", "text": "hi"},
        },
    )
    assert response.status_code == 202
    assert response.content == b""


def test_malformed_json_returns_400():
    """Scenario: Malformed JSON returns 400 with detail."""
    response = client.post(
        "/api/slack/events",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_json"}
