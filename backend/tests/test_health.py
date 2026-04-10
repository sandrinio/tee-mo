"""
Smoke test for the /api/health endpoint.

Verifies that the FastAPI app starts and returns the expected JSON payload.
This is the single acceptance test for STORY-001-01 (§2 acceptance criteria).

Updated by STORY-001-02: the health endpoint now returns a ``database`` key
alongside the core fields, so this test checks the subset of fields rather
than an exact payload equality.  The DB-specific assertions live in
``test_health_db.py``.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app, TEEMO_TABLES


def _make_mock_supabase(table_status: str = "ok") -> MagicMock:
    """
    Return a mock Supabase client whose ``table().select().limit().execute()``
    chain either succeeds (``table_status == "ok"``) or raises a generic
    ``Exception`` (any other value is used as the exception message).
    """
    mock_execute = MagicMock()
    if table_status != "ok":
        mock_execute.side_effect = Exception(table_status)

    mock_limit = MagicMock()
    mock_limit.execute = mock_execute

    mock_select = MagicMock()
    mock_select.limit.return_value = mock_limit

    mock_table = MagicMock()
    mock_table.select.return_value = mock_select

    mock_client = MagicMock()
    mock_client.table.return_value = mock_table
    return mock_client


def test_health_returns_ok() -> None:
    """
    Health endpoint returns HTTP 200 and includes core service fields.

    Acceptance criterion: §2.1 — response must contain status, service,
    version keys.  The database sub-object is tested in test_health_db.py.
    """
    mock_client = _make_mock_supabase("ok")
    with patch("app.main.get_supabase", return_value=mock_client):
        client = TestClient(app)
        r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "tee-mo"
    assert body["version"] == "0.1.0"
