"""Tests for STORY-014-02 — Multipart Upload Endpoint.

Seven tests, one per Gherkin scenario in STORY-014-02 §2.1:
  1. Happy path — upload a 2MB PDF
  2. 100-document cap shared with Drive
  3. File too large
  4. BYOK key required
  5. Unsupported file type
  6. Duplicate upload filename
  7. Workspace not owned by user

Strategy:
- TestClient(app, raise_server_exceptions=False) WITHOUT context manager —
  avoids lifespan deadlock under pytest-asyncio auto mode
  (FLASHCARD: 2026-04-25 #test-harness #fastapi #lifespan).
- Auth dependency overridden via app.dependency_overrides.
- Supabase mocked via monkeypatch.setattr("app.core.db.get_supabase", ...).
- extraction_service.* and document_service.create_document mocked via
  monkeypatch.setattr on module objects (module-import pattern).
- Never from __future__ import annotations in this file (FLASHCARD: 2026-04-13 #fastapi).
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_USER_ID = "user-uuid-upload-001"
FAKE_WORKSPACE_ID = "ws-uuid-upload-001"

FAKE_ENCRYPTED_API_KEY = "encrypted:fake-api-key:aes"

# A minimal 2MB-ish PDF payload for happy path tests
FAKE_PDF_BYTES = b"%PDF-1.4 " + b"x" * (2 * 1024 * 1024)  # just over 2MB
FAKE_DOCX_BYTES = b"PK" + b"\x00" * 100  # minimal zip-like header

FAKE_EXTRACTED_TEXT = "Extracted document content for testing."

FAKE_UPLOAD_ROW: dict[str, Any] = {
    "id": "doc-uuid-upload-001",
    "workspace_id": FAKE_WORKSPACE_ID,
    "title": "report.pdf",
    "source": "upload",
    "doc_type": "pdf",
    "original_filename": "report.pdf",
    "content": FAKE_EXTRACTED_TEXT,
    "ai_description": "A test PDF document.",
    "sync_status": "pending",
    "created_at": "2026-04-25T10:00:00Z",
}


# ---------------------------------------------------------------------------
# Autouse fixture — clear dependency overrides after every test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> Any:
    """Clear FastAPI dependency overrides after each test to avoid bleed-through."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def override_current_user() -> str:
    """Override get_current_user_id to return FAKE_USER_ID without a real JWT."""
    from app.api.deps import get_current_user_id

    async def _fake_user(request: Request) -> str:
        return FAKE_USER_ID

    app.dependency_overrides[get_current_user_id] = _fake_user
    return FAKE_USER_ID


@pytest.fixture
def test_client() -> TestClient:
    """TestClient without context manager — avoids lifespan deadlock.

    raise_server_exceptions=False so 4xx/5xx are returned as responses,
    not raised as Python exceptions in the test.
    """
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Supabase mock helpers
# ---------------------------------------------------------------------------


def _make_workspace_row(
    *,
    workspace_id: str = FAKE_WORKSPACE_ID,
    user_id: str = FAKE_USER_ID,
    has_api_key: bool = True,
) -> dict[str, Any]:
    """Build a minimal workspace row."""
    return {
        "id": workspace_id,
        "user_id": user_id,
        "name": "Upload Test Workspace",
        "encrypted_google_refresh_token": "encrypted:refresh:aes",
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY if has_api_key else None,
        "ai_provider": "anthropic",
    }


def _make_upload_supabase_mock(
    workspace_row: dict[str, Any] | None = None,
    doc_count: int = 0,
    duplicate_exists: bool = False,
    insert_result_row: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a minimal Supabase mock for upload route tests.

    Handles:
      - teemo_workspaces — ownership check
      - teemo_documents  — count query, duplicate query, insert

    Queries run in strict order inside the upload route:
      1. workspaces ownership (.select().eq().eq().limit().execute())
      2. documents count (.select("*", count="exact").eq().execute())
      3. documents dup check (.select("id").eq().eq().eq().limit().execute())
      4. documents insert (delegated to document_service mock)
    """
    if workspace_row is None:
        workspace_row = _make_workspace_row()
    if insert_result_row is None:
        insert_result_row = FAKE_UPLOAD_ROW

    # ---- workspaces mock ----
    ownership_result = MagicMock()
    ownership_result.data = [workspace_row]

    ws_limit_mock = MagicMock()
    ws_limit_mock.execute.return_value = ownership_result

    ws_inner_eq = MagicMock()
    ws_inner_eq.limit.return_value = ws_limit_mock
    ws_inner_eq.execute.return_value = ownership_result

    ws_outer_eq = MagicMock()
    ws_outer_eq.eq.return_value = ws_inner_eq
    ws_outer_eq.limit.return_value = ws_limit_mock
    ws_outer_eq.execute.return_value = ownership_result

    ws_select = MagicMock()
    ws_select.eq.return_value = ws_outer_eq

    ws_table = MagicMock()
    ws_table.select.return_value = ws_select

    # ---- documents mock ----
    # Count query result
    count_result = MagicMock()
    count_result.count = doc_count
    count_result.data = []

    # Duplicate query result
    dup_result = MagicMock()
    dup_result.data = [{"id": "dup-existing-id"}] if duplicate_exists else []

    # Insert result (used by document_service.create_document — but we mock that at service level)
    insert_result = MagicMock()
    insert_result.data = [insert_result_row]
    insert_mock = MagicMock()
    insert_mock.execute.return_value = insert_result

    # The documents table needs to support:
    #   .select("*", count="exact").eq(workspace_id).execute()  → count
    #   .select("id").eq().eq().eq().limit().execute()           → dup check
    #
    # We build a single flexible eq chain that returns the right result
    # depending on what execute() is called on.

    dup_limit_mock = MagicMock()
    dup_limit_mock.execute.return_value = dup_result

    # Inner-most eq (for 3-eq dup chain)
    docs_eq3 = MagicMock()
    docs_eq3.limit.return_value = dup_limit_mock
    docs_eq3.execute.return_value = dup_result
    docs_eq3.eq.return_value = docs_eq3

    # Second eq (chains to eq3)
    docs_eq2 = MagicMock()
    docs_eq2.eq.return_value = docs_eq3
    docs_eq2.limit.return_value = dup_limit_mock
    docs_eq2.execute.return_value = count_result

    # First eq on .select("*", count=...) or .select("id")
    docs_eq1 = MagicMock()
    docs_eq1.eq.return_value = docs_eq2
    docs_eq1.execute.return_value = count_result

    docs_select = MagicMock()
    docs_select.eq.return_value = docs_eq1
    docs_select.execute.return_value = count_result

    docs_table = MagicMock()
    docs_table.select.return_value = docs_select
    docs_table.insert.return_value = insert_mock

    def _table_router(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_table
        return docs_table

    mock_sb = MagicMock()
    mock_sb.table.side_effect = _table_router
    return mock_sb


def _patch_extraction_service(monkeypatch: pytest.MonkeyPatch, extracted: str = FAKE_EXTRACTED_TEXT) -> None:
    """Patch all extraction_service functions used by the upload route."""
    import app.services.extraction_service as es
    monkeypatch.setattr(es, "extract_pdf", lambda b: extracted)
    monkeypatch.setattr(es, "extract_docx", lambda b: extracted)
    monkeypatch.setattr(es, "extract_xlsx", lambda b: extracted)
    monkeypatch.setattr(es, "maybe_truncate", lambda s: s)


def _patch_document_service_create(
    monkeypatch: pytest.MonkeyPatch,
    row: dict[str, Any] | None = None,
) -> AsyncMock:
    """Patch document_service.create_document to return a canned row."""
    import app.services.document_service as ds
    created = row or FAKE_UPLOAD_ROW
    mock_fn = AsyncMock(return_value=created)
    monkeypatch.setattr(ds, "create_document", mock_fn)
    return mock_fn


# ---------------------------------------------------------------------------
# Scenario 1: Happy path — upload a 2MB PDF
# ---------------------------------------------------------------------------


class TestUploadHappyPath:
    """Scenario: Happy path — upload a 2MB PDF.

    Given a workspace owned by the current user
    And the workspace has a BYOK key configured
    And the workspace has fewer than 100 indexed documents
    When the user POSTs /api/workspaces/{id}/documents/upload with a 2MB PDF named "report.pdf"
    Then the response status is 201
    And the response body has source="upload" and original_filename="report.pdf"
    """

    def test_upload_pdf_happy_path_returns_201(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload with a valid 2MB PDF returns 201 with upload metadata."""
        mock_sb = _make_upload_supabase_mock(doc_count=0)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        expected_row = {**FAKE_UPLOAD_ROW, "source": "upload", "original_filename": "report.pdf"}
        _patch_document_service_create(monkeypatch, row=expected_row)

        files = {"file": ("report.pdf", FAKE_PDF_BYTES, "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("source") == "upload", f"Expected source='upload', got: {data}"
        assert data.get("original_filename") == "report.pdf", (
            f"Expected original_filename='report.pdf', got: {data}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: 100-document cap shared with Drive
# ---------------------------------------------------------------------------


class TestUploadCapEnforced:
    """Scenario: 100-document cap shared with Drive.

    Given a workspace with 100 indexed documents (mix of Drive and upload)
    When the user POSTs a new file
    Then the response status is 400 with detail
    "Maximum 100 files per workspace. Remove a file before adding another."
    """

    def test_upload_returns_400_when_cap_reached(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload when workspace has 100 docs must return 400."""
        mock_sb = _make_upload_supabase_mock(doc_count=100)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        files = {"file": ("newfile.pdf", b"%PDF-1.4 small", "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "100" in resp.text, f"Expected '100' in error body: {resp.text}"
        assert "Maximum" in resp.text, f"Expected 'Maximum' in error body: {resp.text}"
        assert "Remove a file before adding another" in resp.text, (
            f"Expected cap detail string in body: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 3: File too large
# ---------------------------------------------------------------------------


class TestUploadFileTooLarge:
    """Scenario: File too large.

    When the user POSTs a 12MB file
    Then the response status is 400 with detail matching "10MB"
    """

    def test_upload_returns_400_when_file_exceeds_10mb(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload with a 12MB file must return 400."""
        mock_sb = _make_upload_supabase_mock(doc_count=0)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        large_bytes = b"x" * (12 * 1024 * 1024)  # 12MB
        files = {"file": ("big.pdf", large_bytes, "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "10MB" in resp.text, f"Expected '10MB' in error body: {resp.text}"


# ---------------------------------------------------------------------------
# Scenario 4: BYOK key required
# ---------------------------------------------------------------------------


class TestUploadByokRequired:
    """Scenario: BYOK key required.

    Given a workspace with no ai_provider configured
    When the user POSTs a valid PDF
    Then the response status is 400 with detail matching "BYOK key required"
    """

    def test_upload_returns_400_when_no_byok_key(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload without BYOK key must return 400."""
        workspace_row = _make_workspace_row(has_api_key=False)
        mock_sb = _make_upload_supabase_mock(workspace_row=workspace_row, doc_count=0)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        files = {"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "BYOK" in resp.text or "key" in resp.text.lower(), (
            f"Expected 'BYOK key required' in error body: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 5: Unsupported file type
# ---------------------------------------------------------------------------


class TestUploadUnsupportedMimeType:
    """Scenario: Unsupported file type.

    When the user POSTs a .png file with content_type "image/png"
    Then the response status is 400 with detail "Unsupported file type"
    """

    def test_upload_returns_400_for_unsupported_mime(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload with image/png must return 400."""
        mock_sb = _make_upload_supabase_mock(doc_count=0)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        files = {"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
        assert "Unsupported file type" in resp.text, (
            f"Expected 'Unsupported file type' in error body: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 6: Duplicate upload filename
# ---------------------------------------------------------------------------


class TestUploadDuplicateFilename:
    """Scenario: Duplicate upload filename.

    Given a workspace already has an upload row with original_filename "report.pdf"
    When the user POSTs another file named "report.pdf"
    Then the response status is 409 with detail matching "already uploaded"
    """

    def test_upload_returns_409_for_duplicate_filename(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload with duplicate filename returns 409."""
        mock_sb = _make_upload_supabase_mock(doc_count=5, duplicate_exists=True)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        files = {"file": ("report.pdf", b"%PDF-1.4 content", "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
        assert "already uploaded" in resp.text, (
            f"Expected 'already uploaded' in error body: {resp.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 7: Workspace not owned by user
# ---------------------------------------------------------------------------


class TestUploadWorkspaceNotOwned:
    """Scenario: Workspace not owned by user.

    Given a workspace owned by a different user
    When the current user POSTs a valid file
    Then the response status is 404
    """

    def test_upload_returns_404_for_unowned_workspace(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /documents/upload for a workspace not owned by user returns 404."""
        # Workspace row with a DIFFERENT user_id — ownership check fails
        other_user_workspace = _make_workspace_row(user_id="other-user-uuid-999")
        # Simulate ownership check returning empty data (no matching workspace for this user)
        ownership_result = MagicMock()
        ownership_result.data = []  # not found / not owned

        ws_limit = MagicMock()
        ws_limit.execute.return_value = ownership_result

        ws_inner_eq = MagicMock()
        ws_inner_eq.limit.return_value = ws_limit
        ws_inner_eq.execute.return_value = ownership_result

        ws_outer_eq = MagicMock()
        ws_outer_eq.eq.return_value = ws_inner_eq
        ws_outer_eq.limit.return_value = ws_limit
        ws_outer_eq.execute.return_value = ownership_result

        ws_select = MagicMock()
        ws_select.eq.return_value = ws_outer_eq

        ws_table = MagicMock()
        ws_table.select.return_value = ws_select

        mock_sb = MagicMock()
        mock_sb.table.return_value = ws_table
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_extraction_service(monkeypatch)
        _patch_document_service_create(monkeypatch)

        files = {"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")}
        resp = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents/upload",
            files=files,
        )

        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
