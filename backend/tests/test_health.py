"""
Smoke test for the /api/health endpoint.

Verifies that the FastAPI app starts and returns the expected JSON payload.
This is the single acceptance test for STORY-001-01 (§2 acceptance criteria).
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    """
    Health endpoint returns HTTP 200 with the exact expected JSON body.

    Acceptance criterion: §2.1 — "the response body is
    {status: ok, service: tee-mo, version: 0.1.0}".
    """
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "tee-mo", "version": "0.1.0"}
