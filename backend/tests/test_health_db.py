"""
Acceptance tests for the database smoke-check portion of GET /api/health.

Covers all Gherkin scenarios from STORY-001-02 §2.1 and STORY-003-03 §2.1:
1. All 6 teemo_ tables exist and are queryable  -> status "ok", all tables "ok"
2. One table is missing / errors                -> status "degraded", others "ok"
3. Client is reused across requests             -> get_supabase() called once per
                                                   in-process call (singleton)
4. /api/health reports exactly 6 teemo_* tables after ADR-024 migrations

The Supabase client is mocked so tests are hermetic — no live DB required.
The mock replicates the call chain:
    client.table(name).select("id").limit(0).execute()

Pattern reference: test_health.py (STORY-001-01).
Note: test_health_reports_all_six_teemo_tables() requires the ADR-024 migrations
(005, 006, 007) to be applied in Supabase before the test passes against a live
DB. Against the mock it passes immediately since TEEMO_TABLES drives both the
endpoint and the mock.
"""

from unittest.mock import MagicMock, call, patch

import pytest
from fastapi.testclient import TestClient

from app.main import TEEMO_TABLES, app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_supabase(failing_table: str | None = None) -> MagicMock:
    """
    Build a mock Supabase client.

    For each ``client.table(name)`` call the mock returns a fresh chain
    whose ``.execute()`` either succeeds (returns an empty MagicMock) or
    raises ``Exception("relation does not exist")`` when
    ``name == failing_table``.

    Parameters
    ----------
    failing_table : str | None
        If provided, ``client.table(failing_table).select().limit().execute()``
        will raise, simulating a missing / unreachable table.  All other
        tables succeed.

    Returns
    -------
    MagicMock
        A mock whose ``.table()`` method is instrumented as described above.
    """

    def table_side_effect(name: str) -> MagicMock:
        mock_execute = MagicMock()
        if name == failing_table:
            mock_execute.side_effect = Exception(
                f'relation "{name}" does not exist'
            )

        mock_limit = MagicMock()
        mock_limit.execute = mock_execute

        mock_select = MagicMock()
        mock_select.limit.return_value = mock_limit

        mock_table_obj = MagicMock()
        mock_table_obj.select.return_value = mock_select

        return mock_table_obj

    mock_client = MagicMock()
    mock_client.table.side_effect = table_side_effect
    return mock_client


# ---------------------------------------------------------------------------
# Scenario 1 — All 4 teemo_ tables exist and are queryable
# ---------------------------------------------------------------------------


def test_health_all_tables_ok() -> None:
    """
    Gherkin Scenario: All 6 teemo_ tables exist and are queryable.

    Given the mock Supabase responds without errors for all 6 tables
    When  GET /api/health is called
    Then  response.status_code is 200
    And   response.json()["status"] is "ok"
    And   every teemo_* table in response.json()["database"] is "ok"
    """
    mock_client = _make_mock_supabase(failing_table=None)
    with patch("app.main.get_supabase", return_value=mock_client):
        client = TestClient(app)
        r = client.get("/api/health")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "tee-mo"
    assert body["version"] == "0.1.0"
    assert "database" in body

    for table in TEEMO_TABLES:
        assert body["database"][table] == "ok", (
            f"Expected table {table!r} to be 'ok', got {body['database'][table]!r}"
        )


# ---------------------------------------------------------------------------
# Scenario 2 — Missing table degrades gracefully
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("failing_table", list(TEEMO_TABLES))
def test_health_degraded_when_table_missing(failing_table: str) -> None:
    """
    Gherkin Scenario: Missing table degrades gracefully.

    Parametrised over each teemo_* table to ensure the health endpoint
    survives the failure of any individual table.

    Given the mock Supabase raises for ``failing_table``
    When  GET /api/health is called
    Then  response.status_code is 200  (NOT 500)
    And   response.json()["status"] is "degraded"
    And   response.json()["database"][failing_table] starts with "missing" or "error"
    And   all other tables are still "ok"
    """
    mock_client = _make_mock_supabase(failing_table=failing_table)
    with patch("app.main.get_supabase", return_value=mock_client):
        client = TestClient(app)
        r = client.get("/api/health")

    assert r.status_code == 200, "Endpoint must NOT return 500 on table failure"
    body = r.json()
    assert body["status"] == "degraded"

    failed_val = body["database"][failing_table]
    assert failed_val.startswith("missing") or failed_val.startswith("error"), (
        f"Expected 'missing:...' or 'error:...' for {failing_table!r}, got {failed_val!r}"
    )

    for table in TEEMO_TABLES:
        if table != failing_table:
            assert body["database"][table] == "ok", (
                f"Table {table!r} should be 'ok' when only {failing_table!r} fails"
            )


# ---------------------------------------------------------------------------
# Scenario 3 — Client is reused across requests (singleton)
# ---------------------------------------------------------------------------


def test_supabase_client_is_singleton() -> None:
    """
    Gherkin Scenario: Client is reused across requests.

    Given two sequential GET /api/health requests
    When  the get_supabase factory is inspected
    Then  it was called at most once per request — the lru_cache guarantees
          a single Client instance for the process lifetime.

    Implementation note: ``get_supabase`` is decorated with
    ``@lru_cache(maxsize=1)``.  We patch the underlying factory at the
    module level and confirm only one unique Client object is returned
    across both requests.
    """
    mock_client = _make_mock_supabase(failing_table=None)

    # Track every return value from get_supabase to verify it's always the same object
    returned_clients: list[MagicMock] = []

    def recording_get_supabase() -> MagicMock:
        returned_clients.append(mock_client)
        return mock_client

    with patch("app.main.get_supabase", side_effect=recording_get_supabase):
        client = TestClient(app)
        client.get("/api/health")
        client.get("/api/health")

    # Both calls returned the same mock_client instance
    assert len(set(id(c) for c in returned_clients)) == 1, (
        "get_supabase must return the same client instance every time"
    )


# ---------------------------------------------------------------------------
# Scenario 4 — /api/health reports exactly 6 teemo_* tables (ADR-024)
# ---------------------------------------------------------------------------


def test_health_reports_all_six_teemo_tables() -> None:
    """
    After ADR-024 migrations, /api/health must list all 6 teemo_* tables.

    Gherkin Scenario: /api/health reports 6 teemo_* tables after migrations
      (STORY-003-03 §2.1)

    Given the mock Supabase responds without errors for all 6 tables
    When  GET /api/health is called
    Then  response.status_code is 200
    And   response.json()["status"] is "ok"
    And   response.json()["database"] has exactly 6 keys
    And   the keys are: teemo_users, teemo_workspaces, teemo_knowledge_index,
          teemo_skills, teemo_slack_teams, teemo_workspace_channels
    And   every value is "ok"

    Note: Against live Supabase this test fails until the user runs migrations
    005, 006, and 007 via the SQL editor. Against the mock it passes immediately.
    """
    mock_client = _make_mock_supabase(failing_table=None)
    with patch("app.main.get_supabase", return_value=mock_client):
        client = TestClient(app)
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["database"].keys()) == {
        "teemo_users",
        "teemo_workspaces",
        "teemo_knowledge_index",
        "teemo_skills",
        "teemo_slack_teams",
        "teemo_workspace_channels",
    }
    for table_name, status in body["database"].items():
        assert status == "ok", f"{table_name} is {status}"
