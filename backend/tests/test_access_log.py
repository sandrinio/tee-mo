"""
Integration tests for access log middleware and request ID header — STORY-016-01.

Tests:
  - X-Request-Id header is present in HTTP responses
  - Access log middleware emits a structured log entry for non-health requests
  - /api/health is excluded from access log emission to avoid probe noise
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App fixture — patch out DB and encryption to allow import without real env
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Return a TestClient for the Tee-Mo app with Supabase calls mocked out."""
    mock_supabase = MagicMock()
    mock_execute = MagicMock()
    mock_execute.return_value.data = []
    mock_chain = MagicMock()
    mock_chain.select.return_value = mock_chain
    mock_chain.limit.return_value = mock_chain
    mock_chain.execute.return_value = MagicMock(data=[])
    mock_supabase.table.return_value = mock_chain

    with patch("app.core.db.get_supabase", return_value=mock_supabase):
        from app.main import app
        yield TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Test: X-Request-Id header
# ---------------------------------------------------------------------------


def test_x_request_id_header_present(client: TestClient) -> None:
    """Every HTTP response includes an X-Request-Id header."""
    with patch("app.core.db.get_supabase") as mock_get_sb:
        mock_sb = MagicMock()
        mock_chain = MagicMock()
        mock_chain.select.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_chain
        mock_get_sb.return_value = mock_sb

        response = client.get("/api/health")

    assert "x-request-id" in response.headers, (
        f"Expected X-Request-Id header in response headers: {dict(response.headers)}"
    )


def test_x_request_id_is_uuid4_format(client: TestClient) -> None:
    """X-Request-Id header value is a valid UUID4 string."""
    import uuid

    with patch("app.core.db.get_supabase") as mock_get_sb:
        mock_sb = MagicMock()
        mock_chain = MagicMock()
        mock_chain.select.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_chain
        mock_get_sb.return_value = mock_sb

        response = client.get("/api/health")

    request_id = response.headers.get("x-request-id", "")
    try:
        parsed = uuid.UUID(request_id)
    except ValueError:
        pytest.fail(f"X-Request-Id is not a valid UUID: {request_id!r}")

    assert parsed.version == 4, f"Expected UUID4, got version {parsed.version}"


def test_x_request_id_unique_per_request(client: TestClient) -> None:
    """Each request receives a different X-Request-Id."""
    with patch("app.core.db.get_supabase") as mock_get_sb:
        mock_sb = MagicMock()
        mock_chain = MagicMock()
        mock_chain.select.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_chain
        mock_get_sb.return_value = mock_sb

        r1 = client.get("/api/health")
        r2 = client.get("/api/health")

    id1 = r1.headers.get("x-request-id")
    id2 = r2.headers.get("x-request-id")

    assert id1 is not None
    assert id2 is not None
    assert id1 != id2, f"Expected unique IDs per request, got {id1!r} twice"


# ---------------------------------------------------------------------------
# Test: Access log middleware
# ---------------------------------------------------------------------------


def test_access_log_emitted_for_non_health_request() -> None:
    """AccessLogMiddleware emits an INFO log for non-health endpoints.

    Uses a log capture handler attached to the 'teemo.access' logger to verify
    the structured log entry is emitted with the correct fields.
    """
    import logging
    from app.main import app

    # Capture access log records
    access_records: list[logging.LogRecord] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            access_records.append(record)

    handler = _CaptureHandler()
    handler.setLevel(logging.DEBUG)
    access_logger = logging.getLogger("teemo.access")
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.DEBUG)

    try:
        with patch("app.core.db.get_supabase") as mock_get_sb:
            mock_sb = MagicMock()
            mock_chain = MagicMock()
            mock_chain.select.return_value = mock_chain
            mock_chain.limit.return_value = mock_chain
            mock_chain.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value = mock_chain
            mock_get_sb.return_value = mock_sb

            test_client = TestClient(app, raise_server_exceptions=False)
            test_client.get("/api/health")  # Skipped — should NOT emit
            test_client.get("/api/health")  # Also skipped

            pre_count = len(access_records)

            # Make a non-health request to trigger access log
            # /api/nonexistent will return 404 but the access log should still fire
            test_client.get("/api/nonexistent-endpoint-for-test")

    finally:
        access_logger.removeHandler(handler)

    # After the non-health request, a new record should have been added
    assert len(access_records) > pre_count, (
        "Expected at least one access log record for /api/nonexistent-endpoint-for-test"
    )

    last_record = access_records[-1]
    # The record's extra fields should contain 'event', 'method', 'path', 'status'
    assert hasattr(last_record, "event"), f"Missing 'event' extra field on record: {vars(last_record)}"
    assert last_record.event == "http.request", f"Expected event=http.request, got {last_record.event!r}"
    assert hasattr(last_record, "method"), "Missing 'method' extra field"
    assert last_record.method == "GET"
    assert hasattr(last_record, "path"), "Missing 'path' extra field"
    assert hasattr(last_record, "status"), "Missing 'status' extra field"
    assert hasattr(last_record, "duration_ms"), "Missing 'duration_ms' extra field"


def test_health_endpoint_excluded_from_access_log() -> None:
    """/api/health requests do NOT emit an access log entry."""
    import logging
    from app.main import app

    access_records: list[logging.LogRecord] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            access_records.append(record)

    handler = _CaptureHandler()
    handler.setLevel(logging.DEBUG)
    access_logger = logging.getLogger("teemo.access")
    access_logger.addHandler(handler)
    access_logger.setLevel(logging.DEBUG)

    try:
        with patch("app.core.db.get_supabase") as mock_get_sb:
            mock_sb = MagicMock()
            mock_chain = MagicMock()
            mock_chain.select.return_value = mock_chain
            mock_chain.limit.return_value = mock_chain
            mock_chain.execute.return_value = MagicMock(data=[])
            mock_sb.table.return_value = mock_chain
            mock_get_sb.return_value = mock_sb

            test_client = TestClient(app, raise_server_exceptions=False)
            count_before = len(access_records)
            test_client.get("/api/health")
            test_client.get("/api/health")
            count_after = len(access_records)
    finally:
        access_logger.removeHandler(handler)

    assert count_after == count_before, (
        f"Expected no new access log records for /api/health, "
        f"got {count_after - count_before} new records"
    )
