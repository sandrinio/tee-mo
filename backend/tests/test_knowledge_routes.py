"""Tests for STORY-006-03 / STORY-015-02 — Knowledge Document CRUD + AI Description + Picker Token.

STORY-015-02 refactors the knowledge routes to use teemo_documents + document_service.
These tests cover both the original STORY-006-03 scenarios (Drive indexing, list, delete,
picker token, reindex) and the new STORY-015-02 scenarios (source/doc_type fields,
POST /documents endpoint).

Strategy:
- Use FastAPI TestClient (sync) so assertions are straightforward.
- Auth dependency (get_current_user_id) is overridden via app.dependency_overrides
  so no real JWT is needed.
- Supabase is mocked via monkeypatch.setattr("app.core.db.get_supabase", ...) so
  no real DB writes occur.
- Drive service functions are mocked via monkeypatch.setattr on the module reference
  (following FLASHCARDS.md module-import rule).
- Scan service generate_ai_description is mocked similarly.
- document_service functions are mocked via monkeypatch.setattr on the module reference.
- httpx.AsyncClient is replaced with FakeKnowledgeAsyncClient for picker-token endpoint
  (same pattern as FakeDriveAsyncClient in test_drive_oauth.py).
- Table routing is handled in _TableRouter (one mock handles teemo_workspaces and
  teemo_documents via side_effect dispatch).

ADR compliance:
  - ADR-005: Drive content read at index time (real-time, not cached)
  - ADR-006: AI description generated at index time, stored in DB
  - ADR-007: 15-file hard cap enforced at the route level
  - ADR-016: Supported MIME types list
  - ADR-002/009: Refresh token encrypted, never logged

FLASHCARDS.md consulted:
  - import httpx at module level in knowledge.py (monkeypatch pattern)
  - Supabase module import pattern: import app.core.db as _db (not from ... import)
  - teemo_ table prefix (all tables use teemo_ prefix)
  - Worktree-relative paths only in Edit/Write calls
  - SHA-256 for content hashing (sprint-context rule)
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_USER_ID = "user-uuid-knowledge-001"
FAKE_WORKSPACE_ID = "ws-uuid-knowledge-001"
FAKE_KNOWLEDGE_ID = "kid-uuid-001"
FAKE_DRIVE_FILE_ID = "drive-file-abc-001"

VALID_PAYLOAD = {
    "drive_file_id": FAKE_DRIVE_FILE_ID,
    "title": "Company Policy",
    "link": "https://docs.google.com/document/d/abc/edit",
    "mime_type": "application/vnd.google-apps.document",
}

ALLOWED_MIME_TYPES = {
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

FAKE_ENCRYPTED_REFRESH_TOKEN = "encrypted:fake-refresh-token:aes"
FAKE_ENCRYPTED_API_KEY = "encrypted:fake-api-key:aes"

FAKE_FILE_CONTENT = "This is the file content for testing purposes."
FAKE_CONTENT_HASH = "d41d8cd98f00b204e9800998ecf8427e"
FAKE_AI_DESCRIPTION = "This document outlines company policies for employees."
FAKE_ACCESS_TOKEN = "ya29.test-picker-access-token"
FAKE_PICKER_API_KEY = "AIza-fake-picker-key"

# ---------------------------------------------------------------------------
# Fake httpx client — mirrors FakeDriveAsyncClient from test_drive_oauth.py
# Used by the picker-token endpoint for token exchange.
# ---------------------------------------------------------------------------


class FakeKnowledgeResponse:
    """Minimal stand-in for httpx.Response — provides .json() method."""

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


MOCK_GOOGLE_TOKEN_RESPONSE = {
    "access_token": FAKE_ACCESS_TOKEN,
    "token_type": "Bearer",
    "expires_in": 3599,
}


class FakeKnowledgeAsyncClient:
    """Stand-in for httpx.AsyncClient used by knowledge routes.

    Supports POST calls for token exchange (picker-token endpoint).
    Supports the async context-manager protocol (async with).

    Class-level state is reset by the autouse fixture before each test.
    """

    last_post_call: dict[str, Any] | None = None
    _response_queue: list[dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._kwargs = kwargs

    async def __aenter__(self) -> "FakeKnowledgeAsyncClient":
        return self

    async def __aexit__(self, *a: Any) -> bool:
        return False

    async def post(self, url: str, data: Any = None, **kw: Any) -> FakeKnowledgeResponse:
        """Intercept POST (token exchange); record call and return queued or default."""
        FakeKnowledgeAsyncClient.last_post_call = {"url": url, "data": data, "kwargs": kw}
        payload = (
            FakeKnowledgeAsyncClient._response_queue.pop(0)
            if FakeKnowledgeAsyncClient._response_queue
            else MOCK_GOOGLE_TOKEN_RESPONSE
        )
        return FakeKnowledgeResponse(200, payload)

    @classmethod
    def reset(cls) -> None:
        """Clear last_post_call and any queued responses."""
        cls.last_post_call = None
        cls._response_queue = []

    @classmethod
    def queue(cls, payload: dict[str, Any]) -> None:
        """Enqueue a payload to be returned by the next .post() call."""
        cls._response_queue.append(payload)


# ---------------------------------------------------------------------------
# Autouse fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_fake_knowledge_client() -> Any:
    """Reset FakeKnowledgeAsyncClient state before and after every test."""
    FakeKnowledgeAsyncClient.reset()
    yield
    FakeKnowledgeAsyncClient.reset()


@pytest.fixture(autouse=True)
def _clear_dependency_overrides() -> Any:
    """Clear FastAPI dependency overrides after each test to avoid bleed-through."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixtures
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
    """TestClient instance for making requests against the app."""
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def patch_httpx_knowledge(monkeypatch: pytest.MonkeyPatch) -> type[FakeKnowledgeAsyncClient]:
    """Replace httpx.AsyncClient inside the knowledge module with FakeKnowledgeAsyncClient.

    Knowledge module must import httpx at module level (FLASHCARDS.md rule) so
    this monkeypatch works. Returns the class so tests can queue responses.
    """
    try:
        import app.api.routes.knowledge as knowledge_module  # type: ignore[import]
        monkeypatch.setattr(knowledge_module.httpx, "AsyncClient", FakeKnowledgeAsyncClient)
    except (ImportError, AttributeError):
        # RED phase — module doesn't exist yet, tests will fail with 404
        pass
    return FakeKnowledgeAsyncClient


# ---------------------------------------------------------------------------
# Supabase multi-table mock builder
# ---------------------------------------------------------------------------


def _make_workspace_row(
    *,
    workspace_id: str = FAKE_WORKSPACE_ID,
    user_id: str = FAKE_USER_ID,
    has_refresh_token: bool = True,
    has_api_key: bool = True,
    provider: str = "anthropic",
) -> dict[str, Any]:
    """Build a workspace row dict simulating teemo_workspaces data.

    Args:
        workspace_id: Workspace UUID.
        user_id: Owner user UUID.
        has_refresh_token: Whether encrypted_google_refresh_token is set (Drive connected).
        has_api_key: Whether encrypted_api_key is set (BYOK configured).
        provider: BYOK provider slug ("anthropic", "openai", "google").

    Returns:
        Dict with all columns relevant to knowledge CRUD routes.
    """
    return {
        "id": workspace_id,
        "owner_user_id": user_id,
        "name": "Test Workspace",
        "encrypted_google_refresh_token": FAKE_ENCRYPTED_REFRESH_TOKEN if has_refresh_token else None,
        "encrypted_api_key": FAKE_ENCRYPTED_API_KEY if has_api_key else None,
        "provider": provider,
    }


def _make_knowledge_row(
    *,
    knowledge_id: str = FAKE_KNOWLEDGE_ID,
    workspace_id: str = FAKE_WORKSPACE_ID,
    drive_file_id: str = FAKE_DRIVE_FILE_ID,
    title: str = "Company Policy",
    link: str = "https://docs.google.com/document/d/abc/edit",
    mime_type: str = "application/vnd.google-apps.document",
    ai_description: str = FAKE_AI_DESCRIPTION,
    content_hash: str = FAKE_CONTENT_HASH,
    source: str = "google_drive",
    doc_type: str = "google_doc",
) -> dict[str, Any]:
    """Build a document row dict simulating teemo_documents data.

    STORY-015-02: teemo_documents replaces teemo_knowledge_index.
    Added source and doc_type fields. external_id replaces drive_file_id.

    Args:
        knowledge_id: Primary key UUID.
        workspace_id: Owning workspace UUID.
        drive_file_id: Google Drive file ID (stored as external_id in teemo_documents).
        title: File title.
        link: File URL (stored as external_link in teemo_documents).
        mime_type: MIME type string (stored in metadata).
        ai_description: AI-generated summary.
        content_hash: SHA-256 hash of file content.
        source: Document source: google_drive, upload, or agent.
        doc_type: Document type: google_doc, pdf, docx, etc.

    Returns:
        Dict with all columns of teemo_documents.
    """
    return {
        "id": knowledge_id,
        "workspace_id": workspace_id,
        "external_id": drive_file_id,
        "drive_file_id": drive_file_id,  # backward-compat alias
        "title": title,
        "external_link": link,
        "link": link,  # backward-compat alias
        "metadata": {"mime_type": mime_type},
        "ai_description": ai_description,
        "content_hash": content_hash,
        "source": source,
        "doc_type": doc_type,
        "sync_status": "pending",
        "last_scanned_at": "2026-04-12T10:00:00Z",
        "created_at": "2026-04-12T10:00:00Z",
    }


class _TableRouter:
    """Routes Supabase .table() calls to per-table mock configurations.

    STORY-015-02: Routes teemo_workspaces and teemo_documents (replacing the
    former teemo_knowledge_index routing).

    Dispatches each .table(name) call to the appropriate mock chain.
    """

    def __init__(
        self,
        workspace_row: dict[str, Any],
        knowledge_rows: list[dict[str, Any]],
        file_count: int | None = None,
        duplicate_exists: bool = False,
        insert_result_row: dict[str, Any] | None = None,
    ) -> None:
        """Initialise the table router.

        Args:
            workspace_row: The workspace row returned from teemo_workspaces.
            knowledge_rows: List of document rows returned from teemo_documents.
            file_count: If provided, override the count returned for COUNT queries.
            duplicate_exists: If True, simulate a duplicate check returning a row.
            insert_result_row: Row returned by .insert().execute(). Defaults to first knowledge row.
        """
        self._workspace_row = workspace_row
        self._knowledge_rows = knowledge_rows
        self._file_count = file_count if file_count is not None else len(knowledge_rows)
        self._duplicate_exists = duplicate_exists
        self._insert_result_row = insert_result_row or (knowledge_rows[0] if knowledge_rows else _make_knowledge_row())
        self._delete_called = False

    def __call__(self, table_name: str) -> MagicMock:
        """Dispatch .table(name) to the correct mock chain.

        Args:
            table_name: Supabase table name string.

        Returns:
            MagicMock configured for the requested table.
        """
        if table_name == "teemo_workspaces":
            return self._workspace_table_mock()
        if table_name in ("teemo_documents", "teemo_knowledge_index"):
            # teemo_knowledge_index kept for backward-compat during migration
            return self._documents_table_mock()
        # Fallback: return a generic MagicMock for unexpected tables
        return MagicMock()

    def _workspace_table_mock(self) -> MagicMock:
        """Build the mock chain for teemo_workspaces table."""
        # Ownership check: .select().eq().eq().limit().execute()
        ownership_result = MagicMock()
        ownership_result.data = [self._workspace_row]

        limit_mock = MagicMock()
        limit_mock.execute.return_value = ownership_result

        inner_eq_mock = MagicMock()
        inner_eq_mock.limit.return_value = limit_mock
        inner_eq_mock.execute.return_value = ownership_result

        outer_eq_mock = MagicMock()
        outer_eq_mock.eq.return_value = inner_eq_mock
        outer_eq_mock.limit.return_value = limit_mock
        outer_eq_mock.execute.return_value = ownership_result

        select_mock = MagicMock()
        select_mock.eq.return_value = outer_eq_mock

        table_mock = MagicMock()
        table_mock.select.return_value = select_mock
        return table_mock

    def _documents_table_mock(self) -> MagicMock:
        """Build the mock chain for teemo_documents table.

        STORY-015-02: renamed from _knowledge_table_mock (was teemo_knowledge_index).
        Handles all query shapes the knowledge routes perform on teemo_documents:
          - COUNT select for the 15-cap check
          - Duplicate check (select by external_id)
          - List select (select("*").eq().order().execute())
          - INSERT for create_document
          - DELETE for delete_document
          - UPDATE for reindex (update_document)
        """
        table_mock = MagicMock()

        # ---- SELECT for count check (file count < 15 guard) ----
        # .select("*", count="exact").eq().execute()
        count_result = MagicMock()
        count_result.count = self._file_count
        count_result.data = self._knowledge_rows[: self._file_count]

        # ---- SELECT for duplicate check ----
        # .select("id").eq().eq().limit().execute()
        dup_result = MagicMock()
        dup_result.data = [{"id": "existing-kid"}] if self._duplicate_exists else []

        # ---- SELECT for list endpoint ----
        # .select("*").eq().order().execute()
        list_result = MagicMock()
        list_result.data = self._knowledge_rows

        # Build flexible eq/limit chain that works for all query shapes
        limit_mock = MagicMock()
        limit_mock.execute.return_value = dup_result

        order_mock = MagicMock()
        order_mock.execute.return_value = list_result

        inner_eq_mock = MagicMock()
        inner_eq_mock.limit.return_value = limit_mock
        inner_eq_mock.execute.return_value = count_result
        inner_eq_mock.eq.return_value = inner_eq_mock  # chaining .eq().eq()
        inner_eq_mock.order.return_value = order_mock

        select_mock = MagicMock()
        select_mock.eq.return_value = inner_eq_mock
        select_mock.execute.return_value = list_result

        table_mock.select.return_value = select_mock

        # ---- INSERT for create_document (document_service) ----
        insert_result = MagicMock()
        insert_result.data = [self._insert_result_row]

        insert_mock = MagicMock()
        insert_mock.execute.return_value = insert_result
        table_mock.insert.return_value = insert_mock

        # ---- DELETE for delete_document (document_service) ----
        delete_eq_mock = MagicMock()
        delete_eq_mock.execute.return_value = MagicMock(data=[])
        delete_eq_mock.eq.return_value = delete_eq_mock

        delete_mock = MagicMock()
        delete_mock.eq.return_value = delete_eq_mock
        table_mock.delete.return_value = delete_mock

        # ---- UPDATE for update_document (reindex) ----
        update_eq_mock = MagicMock()
        update_eq_mock.execute.return_value = MagicMock(data=[self._insert_result_row])
        update_eq_mock.eq.return_value = update_eq_mock

        update_mock = MagicMock()
        update_mock.eq.return_value = update_eq_mock
        table_mock.update.return_value = update_mock

        return table_mock

    # Keep old name as alias for tests that subclass and override it
    def _knowledge_table_mock(self) -> MagicMock:
        """Alias for _documents_table_mock — kept for backward-compat subclasses."""
        return self._documents_table_mock()


def _make_supabase_mock(
    workspace_row: dict[str, Any] | None = None,
    knowledge_rows: list[dict[str, Any]] | None = None,
    file_count: int | None = None,
    duplicate_exists: bool = False,
    insert_result_row: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a minimal Supabase client mock for knowledge route tests.

    Routes all .table() calls through _TableRouter so both teemo_workspaces
    and teemo_documents are handled correctly without a single massive flat MagicMock.

    STORY-015-02: Updated to route teemo_documents instead of teemo_knowledge_index.

    Args:
        workspace_row: Workspace row to return from teemo_workspaces. Defaults to
            a valid workspace with Drive connected and BYOK key set.
        knowledge_rows: List of document rows. Defaults to empty list.
        file_count: Override for the COUNT query result. Defaults to len(knowledge_rows).
        duplicate_exists: If True, duplicate check returns an existing row.
        insert_result_row: Row returned after INSERT. Defaults to knowledge_rows[0] or
            a fresh _make_knowledge_row().

    Returns:
        MagicMock Supabase client with .table() wired to _TableRouter.
    """
    if workspace_row is None:
        workspace_row = _make_workspace_row()
    if knowledge_rows is None:
        knowledge_rows = []

    router = _TableRouter(
        workspace_row=workspace_row,
        knowledge_rows=knowledge_rows,
        file_count=file_count,
        duplicate_exists=duplicate_exists,
        insert_result_row=insert_result_row,
    )

    mock_sb = MagicMock()
    mock_sb.table.side_effect = router
    return mock_sb


# ---------------------------------------------------------------------------
# Helpers — service monkeypatching
# ---------------------------------------------------------------------------


def _patch_document_service(
    monkeypatch: pytest.MonkeyPatch,
    created_row: dict[str, Any] | None = None,
    listed_rows: list[dict[str, Any]] | None = None,
) -> None:
    """Patch document_service functions used by refactored knowledge routes (STORY-015-02).

    Patches create_document, list_documents, and delete_document so tests can
    bypass the real document_service without needing a fully wired Supabase mock.

    Args:
        monkeypatch: pytest MonkeyPatch fixture.
        created_row: Row to return from create_document. Defaults to _make_knowledge_row().
        listed_rows: Rows to return from list_documents. Defaults to empty list.
    """
    if created_row is None:
        created_row = _make_knowledge_row()
    if listed_rows is None:
        listed_rows = []
    try:
        import app.services.document_service as ds  # type: ignore[import]
        monkeypatch.setattr(ds, "create_document", AsyncMock(return_value=created_row))
        monkeypatch.setattr(ds, "list_documents", AsyncMock(return_value=listed_rows))
        monkeypatch.setattr(ds, "delete_document", AsyncMock(return_value=True))
        monkeypatch.setattr(ds, "update_document", AsyncMock(return_value=created_row))
    except (ImportError, AttributeError):
        pass


def _patch_drive_services(
    monkeypatch: pytest.MonkeyPatch,
    content: str = FAKE_FILE_CONTENT,
    content_hash: str = FAKE_CONTENT_HASH,
) -> None:
    """Patch drive_service functions used by the POST /knowledge route.

    Patches:
        - app.services.drive_service.get_drive_client → returns MagicMock drive client
        - app.services.drive_service.fetch_file_content → returns content string
        - app.services.drive_service.compute_content_hash → returns content_hash string

    Args:
        monkeypatch: pytest MonkeyPatch fixture.
        content: String content to return from fetch_file_content.
        content_hash: Hash string to return from compute_content_hash.
    """
    try:
        import app.services.drive_service as ds  # type: ignore[import]
        monkeypatch.setattr(ds, "get_drive_client", lambda enc_token: MagicMock())
        monkeypatch.setattr(ds, "fetch_file_content", AsyncMock(return_value=content))
        monkeypatch.setattr(ds, "compute_content_hash", lambda c: content_hash)
    except (ImportError, AttributeError):
        pass


def _patch_scan_service(
    monkeypatch: pytest.MonkeyPatch,
    description: str = FAKE_AI_DESCRIPTION,
) -> None:
    """Patch scan_service.generate_ai_description used by the POST /knowledge route.

    Args:
        monkeypatch: pytest MonkeyPatch fixture.
        description: AI description string to return from generate_ai_description.
    """
    try:
        import app.services.scan_service as ss  # type: ignore[import]
        monkeypatch.setattr(ss, "generate_ai_description", AsyncMock(return_value=description))
    except (ImportError, AttributeError):
        pass


def _patch_encryption(monkeypatch: pytest.MonkeyPatch, decrypted_value: str = "plaintext-key") -> None:
    """Patch app.core.encryption.decrypt to return a fixed decrypted value.

    Used for picker-token and BYOK key decryption.

    Args:
        monkeypatch: pytest MonkeyPatch fixture.
        decrypted_value: Value that decrypt() should return.
    """
    try:
        import app.core.encryption as enc  # type: ignore[import]
        monkeypatch.setattr(enc, "decrypt", lambda ciphertext: decrypted_value)
    except (ImportError, AttributeError):
        pass


def _patch_settings_picker_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch settings to provide a google_picker_api_key value.

    Args:
        monkeypatch: pytest MonkeyPatch fixture.
    """
    try:
        import app.core.config as cfg  # type: ignore[import]
        fake_settings = MagicMock()
        fake_settings.google_picker_api_key = FAKE_PICKER_API_KEY
        fake_settings.google_api_client_id = "fake-client-id"
        fake_settings.google_api_secret = "fake-client-secret"
        monkeypatch.setattr(cfg, "get_settings", lambda: fake_settings)
    except (ImportError, AttributeError):
        pass


# ---------------------------------------------------------------------------
# Unit tests: Pydantic models (app/models/knowledge.py)
# ---------------------------------------------------------------------------


class TestKnowledgeRequestModel:
    """Unit tests for IndexFileRequest Pydantic model.

    RED: Fails with ImportError — app/models/knowledge.py does not exist yet.
    """

    def test_valid_payload_accepted(self) -> None:
        """IndexFileRequest must accept a complete valid payload."""
        try:
            from app.models.knowledge import IndexFileRequest  # type: ignore[import]
        except ImportError:
            pytest.fail("IndexFileRequest not found in app.models.knowledge — RED phase: model must be implemented")

        req = IndexFileRequest(**VALID_PAYLOAD)
        assert req.drive_file_id == FAKE_DRIVE_FILE_ID
        assert req.title == "Company Policy"
        assert req.mime_type == "application/vnd.google-apps.document"

    def test_missing_drive_file_id_raises(self) -> None:
        """IndexFileRequest must reject payloads missing drive_file_id."""
        try:
            from app.models.knowledge import IndexFileRequest  # type: ignore[import]
        except ImportError:
            pytest.fail("IndexFileRequest not found in app.models.knowledge — RED phase")

        import pydantic
        with pytest.raises(pydantic.ValidationError):
            IndexFileRequest(title="No ID", link="https://example.com", mime_type="application/pdf")

    def test_all_allowed_mime_types_accepted(self) -> None:
        """IndexFileRequest must accept every MIME type in ADR-016 allowed list."""
        try:
            from app.models.knowledge import IndexFileRequest  # type: ignore[import]
        except ImportError:
            pytest.fail("IndexFileRequest not found in app.models.knowledge — RED phase")

        for mime in ALLOWED_MIME_TYPES:
            req = IndexFileRequest(
                drive_file_id="file-001",
                title="Test",
                link="https://example.com",
                mime_type=mime,
            )
            assert req.mime_type == mime


# ---------------------------------------------------------------------------
# Scenario 12: Auth required on all routes (no user → 401)
# ---------------------------------------------------------------------------


class TestAuthRequired:
    """Scenario 12: All knowledge endpoints must return 401 when unauthenticated.

    RED: Will pass if routes exist with auth, fail with 404 if routes don't exist yet.
    Tests are written to assert 401 — they'll still show meaningful failure status.
    """

    def test_post_knowledge_requires_auth(self, test_client: TestClient) -> None:
        """POST /api/workspaces/{id}/knowledge must return 401 without auth cookie."""
        # No override_current_user fixture — no auth
        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        )

    def test_get_knowledge_requires_auth(self, test_client: TestClient) -> None:
        """GET /api/workspaces/{id}/knowledge must return 401 without auth cookie."""
        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        )

    def test_delete_knowledge_requires_auth(self, test_client: TestClient) -> None:
        """DELETE /api/workspaces/{id}/knowledge/{kid} must return 401 without auth."""
        response = test_client.delete(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/{FAKE_KNOWLEDGE_ID}"
        )
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        )

    def test_picker_token_requires_auth(self, test_client: TestClient) -> None:
        """GET /api/workspaces/{id}/drive/picker-token must return 401 without auth."""
        response = test_client.get(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/picker-token"
        )
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 1: Index a Google Docs file (happy path)
# ---------------------------------------------------------------------------


class TestIndexFileHappyPath:
    """Scenario 1: POST /knowledge with a valid Google Docs file should succeed.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_index_docs_file_returns_201_with_ai_description(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/knowledge with valid payload returns 200/201.

        Workspace has Drive connected and BYOK key. Response must contain
        ai_description populated from scan_service.generate_ai_description.

        RED: Fails with 404 — route does not exist yet.
        """
        inserted_row = _make_knowledge_row(ai_description=FAKE_AI_DESCRIPTION)
        mock_sb = _make_supabase_mock(
            knowledge_rows=[],
            file_count=0,
            insert_result_row=inserted_row,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch, description=FAKE_AI_DESCRIPTION)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code in (200, 201), (
            f"Expected 200 or 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "ai_description" in data, f"Response missing ai_description: {data}"
        assert data["ai_description"] == FAKE_AI_DESCRIPTION

    def test_index_file_calls_drive_fetch_and_hash(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge must call fetch_file_content and compute_content_hash.

        Verifies that the route integrates with drive_service correctly.

        RED: Fails with 404 — route does not exist yet.
        """
        fetch_mock = AsyncMock(return_value=FAKE_FILE_CONTENT)
        hash_calls: list[str] = []

        try:
            import app.services.drive_service as ds  # type: ignore[import]
            monkeypatch.setattr(ds, "get_drive_client", lambda enc_token: MagicMock())
            monkeypatch.setattr(ds, "fetch_file_content", fetch_mock)
            monkeypatch.setattr(ds, "compute_content_hash", lambda c: (hash_calls.append(c) or FAKE_CONTENT_HASH))
        except (ImportError, AttributeError):
            pass

        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        inserted_row = _make_knowledge_row()
        mock_sb = _make_supabase_mock(
            knowledge_rows=[],
            file_count=0,
            insert_result_row=inserted_row,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code in (200, 201), (
            f"Expected 200/201, got {response.status_code}: {response.text}"
        )
        fetch_mock.assert_called_once()

    def test_index_file_inserts_content_hash(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge response must include content_hash field.

        RED: Fails with 404 — route does not exist yet.
        """
        inserted_row = _make_knowledge_row(content_hash=FAKE_CONTENT_HASH)
        mock_sb = _make_supabase_mock(
            knowledge_rows=[],
            file_count=0,
            insert_result_row=inserted_row,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code in (200, 201), (
            f"Expected 200/201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "content_hash" in data or "id" in data, (
            f"Response missing expected fields: {data}"
        )


# ---------------------------------------------------------------------------
# Scenario 2: 15-file cap enforced
# ---------------------------------------------------------------------------


class TestFileCapEnforced:
    """Scenario 2: POST /knowledge must return 400 when workspace already has 15 files.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_cap_at_fifteen_files_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge when workspace has 15 files must return 400.

        RED: Fails with 404 — route does not exist yet.
        """
        # Simulate 15 existing files by setting file_count=15
        mock_sb = _make_supabase_mock(
            knowledge_rows=[_make_knowledge_row(knowledge_id=f"kid-{i}") for i in range(15)],
            file_count=15,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code == 400, (
            f"Expected 400 (cap enforced), got {response.status_code}: {response.text}"
        )
        assert "15" in response.text or "maximum" in response.text.lower() or "Maximum" in response.text, (
            f"Expected '15' or 'maximum' in error body: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 3: BYOK key required
# ---------------------------------------------------------------------------


class TestByokKeyRequired:
    """Scenario 3: POST /knowledge must return 400 if workspace has no BYOK key.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_no_byok_key_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge without BYOK key must return 400 with descriptive message.

        RED: Fails with 404 — route does not exist yet.
        """
        workspace_row = _make_workspace_row(has_api_key=False)
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code == 400, (
            f"Expected 400 (BYOK required), got {response.status_code}: {response.text}"
        )
        assert "BYOK" in response.text or "byok" in response.text.lower() or "key" in response.text.lower(), (
            f"Expected 'BYOK' in error body: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Drive not connected
# ---------------------------------------------------------------------------


class TestDriveNotConnected:
    """Scenario 4: POST /knowledge must return 400 if Google Drive is not connected.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_drive_not_connected_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge without Drive connected must return 400.

        RED: Fails with 404 — route does not exist yet.
        """
        workspace_row = _make_workspace_row(has_refresh_token=False)
        mock_sb = _make_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code == 400, (
            f"Expected 400 (Drive not connected), got {response.status_code}: {response.text}"
        )
        assert "drive" in response.text.lower() or "connected" in response.text.lower(), (
            f"Expected 'drive' or 'connected' in error body: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 5: Unsupported MIME type rejected
# ---------------------------------------------------------------------------


class TestUnsupportedMimeType:
    """Scenario 5: POST /knowledge with unsupported MIME type must return 400.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_image_mime_type_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge with mime_type='image/png' must return 400.

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        payload = dict(VALID_PAYLOAD)
        payload["mime_type"] = "image/png"

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=payload,
        )

        assert response.status_code == 400, (
            f"Expected 400 (unsupported MIME), got {response.status_code}: {response.text}"
        )
        assert "mime" in response.text.lower() or "type" in response.text.lower() or "unsupported" in response.text.lower(), (
            f"Expected MIME type error in body: {response.text}"
        )

    def test_video_mime_type_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge with mime_type='video/mp4' must return 400.

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        payload = dict(VALID_PAYLOAD)
        payload["mime_type"] = "video/mp4"

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=payload,
        )

        assert response.status_code == 400, (
            f"Expected 400 (unsupported MIME), got {response.status_code}: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 6: Duplicate file rejected
# ---------------------------------------------------------------------------


class TestDuplicateFileRejected:
    """Scenario 6: POST /knowledge with an already-indexed drive_file_id must return 409.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_duplicate_drive_file_id_returns_409(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge with duplicate drive_file_id must return 409 Conflict.

        RED: Fails with 404 — route does not exist yet.
        """
        # Set duplicate_exists=True to simulate the file already being in the index
        mock_sb = _make_supabase_mock(
            knowledge_rows=[_make_knowledge_row(drive_file_id=FAKE_DRIVE_FILE_ID)],
            file_count=1,
            duplicate_exists=True,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,  # same drive_file_id as the existing row
        )

        assert response.status_code == 409, (
            f"Expected 409 Conflict, got {response.status_code}: {response.text}"
        )
        assert "already" in response.text.lower() or "duplicate" in response.text.lower() or "indexed" in response.text.lower(), (
            f"Expected duplicate error in body: {response.text}"
        )


# ---------------------------------------------------------------------------
# Scenario 7: List indexed files
# ---------------------------------------------------------------------------


class TestListIndexedFiles:
    """Scenario 7: GET /knowledge must return all indexed files for the workspace.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_list_files_returns_array_of_three(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/workspaces/{id}/knowledge with 3 files must return array of 3.

        RED: Fails with 404 — route does not exist yet.
        """
        files = [
            _make_knowledge_row(knowledge_id=f"kid-{i}", drive_file_id=f"drive-{i}", title=f"File {i}")
            for i in range(3)
        ]
        mock_sb = _make_supabase_mock(knowledge_rows=files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        assert len(data) == 3, f"Expected 3 files, got {len(data)}: {data}"

    def test_list_files_includes_ai_description(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /knowledge response objects must include ai_description field.

        RED: Fails with 404 — route does not exist yet.
        """
        files = [_make_knowledge_row(ai_description=FAKE_AI_DESCRIPTION)]
        mock_sb = _make_supabase_mock(knowledge_rows=files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert len(data) >= 1
        assert "ai_description" in data[0], f"Response object missing ai_description: {data[0]}"

    def test_list_files_empty_workspace_returns_empty_array(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /knowledge with no files must return empty array (not null or 404).

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock(knowledge_rows=[])
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data == [], f"Expected empty array, got: {data}"


# ---------------------------------------------------------------------------
# Scenario 8: Remove indexed file
# ---------------------------------------------------------------------------


class TestRemoveIndexedFile:
    """Scenario 8: DELETE /knowledge/{kid} must remove the file and return 200.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_delete_knowledge_file_returns_200(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DELETE /api/workspaces/{id}/knowledge/{kid} must return 200.

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock(
            knowledge_rows=[_make_knowledge_row()],
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.delete(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/{FAKE_KNOWLEDGE_ID}"
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )

    def test_delete_returns_status_deleted(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DELETE /knowledge/{kid} response must indicate deletion success.

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock(
            knowledge_rows=[_make_knowledge_row()],
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.delete(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/{FAKE_KNOWLEDGE_ID}"
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "status" in data or "deleted" in str(data).lower(), (
            f"Expected deletion status in body: {data}"
        )


# ---------------------------------------------------------------------------
# Scenario 9: Picker token minted
# ---------------------------------------------------------------------------


class TestPickerTokenMinted:
    """Scenario 9: GET /drive/picker-token must return access_token + picker_api_key.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_picker_token_returns_access_token_and_key(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
        patch_httpx_knowledge: type[FakeKnowledgeAsyncClient],
    ) -> None:
        """GET /api/workspaces/{id}/drive/picker-token must return access_token and picker_api_key.

        RED: Fails with 404 — route does not exist yet.
        """
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_encryption(monkeypatch, decrypted_value="plaintext-refresh-token")
        _patch_settings_picker_key(monkeypatch)

        # Queue the token exchange response
        FakeKnowledgeAsyncClient.queue(MOCK_GOOGLE_TOKEN_RESPONSE)

        response = test_client.get(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/picker-token"
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "access_token" in data, f"Response missing access_token: {data}"
        assert "picker_api_key" in data, f"Response missing picker_api_key: {data}"

    def test_picker_token_access_token_is_not_stored(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
        patch_httpx_knowledge: type[FakeKnowledgeAsyncClient],
    ) -> None:
        """Picker token endpoint must NOT write access_token to DB (ADR-009: ephemeral).

        The mock Supabase is set up to detect any UPDATE/UPSERT calls. Verifies
        that no DB write occurs for the access token.

        RED: Fails with 404 — route does not exist yet.
        """
        update_called = []

        # Custom workspace mock that records update calls
        mock_sb = _make_supabase_mock()
        original_table = mock_sb.table.side_effect

        def _recording_table(name: str) -> MagicMock:
            t = original_table(name)
            if name == "teemo_workspaces":
                original_update = t.update
                def recording_update(*a: Any, **kw: Any) -> MagicMock:
                    update_called.append((name, a, kw))
                    return original_update(*a, **kw)
                t.update = recording_update
            return t

        mock_sb.table.side_effect = _recording_table
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_encryption(monkeypatch, decrypted_value="plaintext-refresh-token")
        _patch_settings_picker_key(monkeypatch)
        FakeKnowledgeAsyncClient.queue(MOCK_GOOGLE_TOKEN_RESPONSE)

        response = test_client.get(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/drive/picker-token"
        )

        # The route should not write access_token to DB at all
        access_token_writes = [
            call for call in update_called
            if "access_token" in str(call)
        ]
        assert not access_token_writes, (
            f"access_token was written to DB — violates ADR-009: {access_token_writes}"
        )


# ---------------------------------------------------------------------------
# Scenario 10: Large file truncation warning
# ---------------------------------------------------------------------------


class TestLargeFileTruncationWarning:
    """Scenario 10: POST /knowledge with a large file must include a warning in response.

    RED: Fails with 404 — route does not exist yet.
    """

    def test_large_file_includes_truncation_warning(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge with file content exceeding 50K chars must include 'warning' field.

        The drive_service.fetch_file_content is mocked to return content that already
        has a truncation notice appended (simulating the truncation logic in drive_service).

        RED: Fails with 404 — route does not exist yet.
        """
        # Content that signals truncation: a notice appended by drive_service
        truncated_content = "A" * 50_000 + "\n\n[Content truncated at 50000 characters]"

        inserted_row = _make_knowledge_row(ai_description=FAKE_AI_DESCRIPTION)
        mock_sb = _make_supabase_mock(
            knowledge_rows=[],
            file_count=0,
            insert_result_row=inserted_row,
        )
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch, content=truncated_content)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code in (200, 201), (
            f"Expected 200/201 (truncated but indexed), got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "warning" in data, (
            f"Expected 'warning' key in response for large file, got: {data}"
        )
        warning_text = data["warning"]
        assert "truncat" in warning_text.lower() or "50,000" in warning_text or "50000" in warning_text, (
            f"Warning text doesn't mention truncation: {warning_text!r}"
        )


# ---------------------------------------------------------------------------
# Scenario 11: Concurrent indexing serialized (lock-existence test)
# ---------------------------------------------------------------------------


class TestConcurrentIndexingSerialized:
    """Scenario 11: Sequential POST /knowledge requests for the same workspace succeed correctly.

    Full concurrency testing requires async infrastructure beyond the sync TestClient.
    This test verifies that two sequential POST calls to the same workspace both succeed,
    and the final file count is accurate (no double-counting from race conditions).

    RED: Fails with 404 — route does not exist yet.
    """

    def test_two_sequential_posts_both_succeed(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Two sequential POST /knowledge calls for the same workspace must both succeed.

        The second call sees file_count=1 (after the first insert). Both succeed without
        error — verifying that the route handles sequential indexing correctly.

        RED: Fails with 404 — route does not exist yet.
        """
        call_count = [0]

        def _counting_table_factory(count_start: int) -> Any:
            """Build a table router where count increments with each call."""
            def _factory(table_name: str) -> MagicMock:
                current_count = count_start + call_count[0]
                router = _TableRouter(
                    workspace_row=_make_workspace_row(),
                    knowledge_rows=[_make_knowledge_row(knowledge_id=f"kid-{i}") for i in range(current_count)],
                    file_count=current_count,
                    insert_result_row=_make_knowledge_row(knowledge_id=f"kid-new-{current_count}"),
                )
                return router(table_name)
            return _factory

        # Start with 0 files; after first insert count becomes 1
        mock_sb_1 = MagicMock()
        mock_sb_1.table.side_effect = _counting_table_factory(0)

        mock_sb_2 = MagicMock()
        mock_sb_2.table.side_effect = _counting_table_factory(1)

        call_sequence = iter([mock_sb_1, mock_sb_2])

        monkeypatch.setattr("app.core.db.get_supabase", lambda: next(call_sequence))
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        payload_1 = {**VALID_PAYLOAD, "drive_file_id": "drive-file-001", "title": "File 1"}
        payload_2 = {**VALID_PAYLOAD, "drive_file_id": "drive-file-002", "title": "File 2"}

        response_1 = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=payload_1,
        )
        call_count[0] += 1

        response_2 = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=payload_2,
        )

        assert response_1.status_code in (200, 201), (
            f"First POST failed: {response_1.status_code}: {response_1.text}"
        )
        assert response_2.status_code in (200, 201), (
            f"Second POST failed: {response_2.status_code}: {response_2.text}"
        )

    def test_knowledge_route_module_has_workspace_locks(self) -> None:
        """The knowledge route module must define a workspace_locks dict or similar.

        Checks that the module-level lock store exists for serializing concurrent
        requests (R8: asyncio.Lock per workspace_id).

        RED: Fails with ImportError — module does not exist yet.
        """
        try:
            import app.api.routes.knowledge as knowledge_module  # type: ignore[import]
        except ImportError:
            pytest.fail(
                "app.api.routes.knowledge not found — RED phase: module must be implemented. "
                "The module must define a per-workspace asyncio.Lock store for concurrent indexing (R8)."
            )

        # Check for a lock store (dict of locks, asyncio.Lock, or similar pattern)
        has_lock_store = (
            hasattr(knowledge_module, "workspace_locks")
            or hasattr(knowledge_module, "_workspace_locks")
            or hasattr(knowledge_module, "WORKSPACE_LOCKS")
        )
        assert has_lock_store, (
            f"knowledge module missing workspace lock store. "
            f"Expected 'workspace_locks', '_workspace_locks', or 'WORKSPACE_LOCKS' "
            f"to implement R8 (sequential indexing queue). Found attrs: "
            f"{[a for a in dir(knowledge_module) if 'lock' in a.lower()]}"
        )


# ---------------------------------------------------------------------------
# STORY-015-02: content column in teemo_documents (replaces cached_content)
# ---------------------------------------------------------------------------


class TestIndexFileStoresCachedContent:
    """STORY-015-02 (was STORY-006-10): index_file endpoint must store content in teemo_documents.

    STORY-015-02 refactor: the column is ``content`` in teemo_documents (not ``cached_content``
    which was a teemo_knowledge_index column). The INSERT is now performed via
    document_service.create_document which writes to teemo_documents.

    When a file is successfully indexed the INSERT payload sent to Supabase via
    document_service.create_document must include ``content`` equal to the raw text
    fetched from Drive at index time.
    """

    def test_index_file_insert_payload_includes_cached_content(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/knowledge must include content in the teemo_documents INSERT.

        STORY-015-02: The column is now ``content`` (not ``cached_content``).
        document_service.create_document is the path that writes to teemo_documents.

        Strategy:
          - Intercept the Supabase .insert() call on teemo_documents.
          - Capture the payload passed to .insert().
          - Assert that the payload dict contains ``content`` equal to FAKE_FILE_CONTENT.
        """
        inserted_payloads: list[dict] = []

        # Build a customised _TableRouter that records insert payloads on teemo_documents.
        class _CapturingTableRouter(_TableRouter):
            """Extends _TableRouter to record what is passed to .insert() on teemo_documents."""

            def _documents_table_mock(self) -> MagicMock:
                base_mock = super()._documents_table_mock()

                # Wrap the insert side to capture the payload.
                original_insert = base_mock.insert

                def _capture_insert(payload: dict) -> MagicMock:
                    inserted_payloads.append(payload)
                    return original_insert(payload)

                base_mock.insert = _capture_insert
                return base_mock

        inserted_row = _make_knowledge_row(content_hash=FAKE_CONTENT_HASH)
        # Build workspace row with Drive and BYOK configured.
        workspace_row = _make_workspace_row()
        router = _CapturingTableRouter(
            workspace_row=workspace_row,
            knowledge_rows=[],
            file_count=0,
            insert_result_row=inserted_row,
        )
        mock_sb = MagicMock()
        mock_sb.table.side_effect = router
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        _patch_drive_services(monkeypatch, content=FAKE_FILE_CONTENT, content_hash=FAKE_CONTENT_HASH)
        _patch_scan_service(monkeypatch, description=FAKE_AI_DESCRIPTION)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge",
            json=VALID_PAYLOAD,
        )

        assert response.status_code in (200, 201), (
            f"Expected 200 or 201, got {response.status_code}: {response.text}"
        )

        assert inserted_payloads, (
            "No INSERT payload was captured — the Supabase .insert() was not called. "
            "Check that the knowledge route calls document_service.create_document which "
            "calls _db.get_supabase().table('teemo_documents').insert(...)."
        )

        payload = inserted_payloads[0]
        # STORY-015-02: column is 'content' in teemo_documents (was 'cached_content')
        assert "content" in payload, (
            f"INSERT payload is missing 'content'. "
            f"STORY-015-02 requires document_service.create_document to store content "
            f"at index time via the teemo_documents 'content' column. "
            f"Payload keys found: {list(payload.keys())}"
        )
        assert payload["content"] == FAKE_FILE_CONTENT, (
            f"INSERT payload 'content' must equal the fetched file content. "
            f"Expected: {FAKE_FILE_CONTENT!r}. Got: {payload['content']!r}"
        )


# ---------------------------------------------------------------------------
# STORY-006-11: Re-index endpoint tests
# ---------------------------------------------------------------------------


def _make_reindex_supabase_mock(
    workspace_row: dict[str, Any] | None = None,
    knowledge_rows: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a Supabase mock suitable for reindex endpoint tests.

    STORY-015-02: Updated to route teemo_documents instead of teemo_knowledge_index.

    The reindex endpoint performs:
      1. teemo_workspaces ownership check (.select().eq().eq().limit().execute())
      2. teemo_documents list Drive docs (.select('*').eq(workspace_id).eq(source).execute())
      3. For each file: calls document_service.update_document
         which calls teemo_documents .update().eq().execute()

    Args:
        workspace_row: Workspace row to return. Defaults to a connected, keyed workspace.
        knowledge_rows: Drive documents to return from the list query. Defaults to empty list.

    Returns:
        MagicMock Supabase client.
    """
    if workspace_row is None:
        workspace_row = _make_workspace_row()
    if knowledge_rows is None:
        knowledge_rows = []

    # --- workspace table mock ---
    ownership_result = MagicMock()
    ownership_result.data = [workspace_row]

    # Also used by document_service._resolve_ai_description (maybe_single query)
    ws_maybe_single_result = MagicMock()
    ws_maybe_single_result.data = workspace_row  # maybe_single returns .data as dict

    limit_mock = MagicMock()
    limit_mock.execute.return_value = ownership_result

    inner_eq_mock = MagicMock()
    inner_eq_mock.limit.return_value = limit_mock
    inner_eq_mock.execute.return_value = ownership_result
    inner_eq_mock.eq.return_value = inner_eq_mock
    inner_eq_mock.maybe_single.return_value = MagicMock(execute=MagicMock(return_value=ws_maybe_single_result))

    outer_eq_mock = MagicMock()
    outer_eq_mock.eq.return_value = inner_eq_mock
    outer_eq_mock.limit.return_value = limit_mock
    outer_eq_mock.execute.return_value = ownership_result

    ws_select_mock = MagicMock()
    ws_select_mock.eq.return_value = outer_eq_mock

    ws_table_mock = MagicMock()
    ws_table_mock.select.return_value = ws_select_mock

    # --- teemo_documents table mock ---
    # List query: .select('*').eq(workspace_id).eq(source='google_drive').execute()
    list_result = MagicMock()
    list_result.data = knowledge_rows

    ki_inner_eq = MagicMock()
    ki_inner_eq.execute.return_value = list_result
    ki_inner_eq.eq.return_value = ki_inner_eq  # chaining .eq().eq()

    ki_select_mock = MagicMock()
    ki_select_mock.eq.return_value = ki_inner_eq

    # Update chain for document_service.update_document:
    # .update({...}).eq(id).eq(workspace_id).execute()
    knowledge_rows_by_id = {row.get("id", ""): row for row in knowledge_rows}
    update_row = knowledge_rows[0] if knowledge_rows else _make_knowledge_row()

    update_execute_mock = MagicMock()
    update_execute_mock.execute.return_value = MagicMock(data=[update_row])

    update_eq_mock = MagicMock()
    update_eq_mock.eq.return_value = update_execute_mock
    update_eq_mock.execute.return_value = MagicMock(data=[update_row])

    update_mock = MagicMock()
    update_mock.eq.return_value = update_eq_mock

    ki_table_mock = MagicMock()
    ki_table_mock.select.return_value = ki_select_mock
    ki_table_mock.update.return_value = update_mock

    def _dispatch(table_name: str) -> MagicMock:
        if table_name == "teemo_workspaces":
            return ws_table_mock
        if table_name in ("teemo_documents", "teemo_knowledge_index"):
            return ki_table_mock
        return MagicMock()

    mock_sb = MagicMock()
    mock_sb.table.side_effect = _dispatch
    return mock_sb


class TestReindexKnowledge:
    """STORY-006-11: POST /api/workspaces/{id}/knowledge/reindex tests.

    Five tests covering the five Gherkin scenarios:
      1. Happy path — returns 200 with correct reindexed/failed/errors counts
      2. No BYOK key — returns 400
      3. No Drive connected — returns 400
      4. Non-owner — returns 404
      5. Empty workspace — returns reindexed=0, failed=0, errors=[]
    """

    def test_reindex_returns_200_with_correct_counts(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex with 2 files must return 200, reindexed=2, failed=0.

        Verifies that the endpoint iterates all indexed files, re-fetches content,
        regenerates AI descriptions, and updates rows. The response must include
        ``reindexed``, ``failed``, and ``errors`` fields.
        """
        files = [
            _make_knowledge_row(knowledge_id="kid-r-1", drive_file_id="drive-r-1"),
            _make_knowledge_row(knowledge_id="kid-r-2", drive_file_id="drive-r-2"),
        ]
        mock_sb = _make_reindex_supabase_mock(knowledge_rows=files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "reindexed" in data, f"Response missing 'reindexed': {data}"
        assert "failed" in data, f"Response missing 'failed': {data}"
        assert "errors" in data, f"Response missing 'errors': {data}"
        assert data["reindexed"] == 2, f"Expected reindexed=2, got: {data}"
        assert data["failed"] == 0, f"Expected failed=0, got: {data}"
        assert data["errors"] == [], f"Expected empty errors, got: {data}"

    def test_reindex_no_byok_key_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex without BYOK key must return 400.

        Gate condition: no encrypted_api_key in workspace row triggers early 400.
        """
        workspace_row = _make_workspace_row(has_api_key=False)
        mock_sb = _make_reindex_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 400, (
            f"Expected 400 (BYOK required), got {response.status_code}: {response.text}"
        )
        assert (
            "byok" in response.text.lower()
            or "key" in response.text.lower()
        ), f"Expected BYOK-related error in body: {response.text}"

    def test_reindex_no_drive_returns_400(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex without Drive connected must return 400.

        Gate condition: no encrypted_google_refresh_token in workspace row triggers 400.
        """
        workspace_row = _make_workspace_row(has_refresh_token=False)
        mock_sb = _make_reindex_supabase_mock(workspace_row=workspace_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 400, (
            f"Expected 400 (Drive not connected), got {response.status_code}: {response.text}"
        )
        assert (
            "drive" in response.text.lower()
            or "connected" in response.text.lower()
        ), f"Expected Drive-related error in body: {response.text}"

    def test_reindex_non_owner_returns_404(
        self,
        test_client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex by non-owner must return 404 (IDOR protection).

        The _assert_workspace_owner helper returns 404 (not 403) to avoid
        revealing whether a workspace exists for another user.
        The test authenticates as a different user from the workspace owner.
        """
        from app.api.deps import get_current_user_id
        from fastapi import Request

        async def _other_user(request: Request) -> str:
            return "other-user-uuid-not-owner"

        app.dependency_overrides[get_current_user_id] = _other_user

        # Workspace row belongs to FAKE_USER_ID, but caller is "other-user-uuid-not-owner"
        ownership_result = MagicMock()
        ownership_result.data = []  # no row found — ownership check fails → 404

        limit_mock = MagicMock()
        limit_mock.execute.return_value = ownership_result

        inner_eq = MagicMock()
        inner_eq.limit.return_value = limit_mock
        inner_eq.execute.return_value = ownership_result

        outer_eq = MagicMock()
        outer_eq.eq.return_value = inner_eq
        outer_eq.limit.return_value = limit_mock

        select_mock = MagicMock()
        select_mock.eq.return_value = outer_eq

        ws_table_mock = MagicMock()
        ws_table_mock.select.return_value = select_mock

        mock_sb = MagicMock()
        mock_sb.table.return_value = ws_table_mock
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 404, (
            f"Expected 404 (non-owner), got {response.status_code}: {response.text}"
        )

    def test_reindex_empty_workspace_returns_zeros(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex with no indexed files returns reindexed=0, failed=0, errors=[].

        An empty workspace should complete successfully with zero counts and no errors.
        """
        mock_sb = _make_reindex_supabase_mock(knowledge_rows=[])
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 200, (
            f"Expected 200 (empty workspace), got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data == {"reindexed": 0, "failed": 0, "errors": []}, (
            f"Expected zero counts for empty workspace, got: {data}"
        )


# ---------------------------------------------------------------------------
# STORY-015-02: New endpoint POST /api/workspaces/{id}/documents
# ---------------------------------------------------------------------------


class TestCreateDocumentEndpoint:
    """STORY-015-02 R4: POST /api/workspaces/{id}/documents creates an agent document.

    Covers the new endpoint that accepts {title, content} and calls
    document_service.create_document with source='agent', doc_type='markdown'.
    """

    def test_create_document_returns_200_with_source_agent(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/documents must return 200 and source='agent'.

        Verifies the new endpoint creates a document with the correct source.
        """
        created_row = _make_knowledge_row(
            source="agent",
            doc_type="markdown",
            title="Agent Report",
        )
        mock_sb = _make_supabase_mock(insert_result_row=created_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_document_service(monkeypatch, created_row=created_row)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents",
            json={"title": "Agent Report", "content": "# Agent Report\n\nContent here."},
        )

        assert response.status_code in (200, 201), (
            f"Expected 200 or 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data.get("source") == "agent", (
            f"Expected source='agent', got: {data.get('source')!r}. Full response: {data}"
        )

    def test_create_document_returns_doc_type_markdown(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/documents must return doc_type='markdown'.

        Verifies the created document has the correct doc_type.
        """
        created_row = _make_knowledge_row(
            source="agent",
            doc_type="markdown",
            title="Agent Report",
        )
        mock_sb = _make_supabase_mock(insert_result_row=created_row)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_document_service(monkeypatch, created_row=created_row)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents",
            json={"title": "Agent Report", "content": "# Agent Report\n\nContent here."},
        )

        assert response.status_code in (200, 201), (
            f"Expected 200 or 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data.get("doc_type") == "markdown", (
            f"Expected doc_type='markdown', got: {data.get('doc_type')!r}. Full response: {data}"
        )

    def test_create_document_requires_auth(self, test_client: TestClient) -> None:
        """POST /api/workspaces/{id}/documents must return 401 without auth."""
        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents",
            json={"title": "Test", "content": "test"},
        )
        assert response.status_code == 401, (
            f"Expected 401 Unauthorized, got {response.status_code}: {response.text}"
        )

    def test_create_document_missing_title_returns_422(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /api/workspaces/{id}/documents with missing title must return 422."""
        mock_sb = _make_supabase_mock()
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/documents",
            json={"content": "No title here"},  # missing title
        )
        assert response.status_code == 422, (
            f"Expected 422 (validation error), got {response.status_code}: {response.text}"
        )


# ---------------------------------------------------------------------------
# STORY-015-02: List endpoint returns source + doc_type
# ---------------------------------------------------------------------------


class TestListDocumentsIncludesSource:
    """STORY-015-02 Scenario: List documents includes source and doc_type fields.

    GET /knowledge should return documents with correct source values including
    mixed sources (google_drive + agent).
    """

    def test_list_knowledge_includes_source_field(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/workspaces/{id}/knowledge must include source in each returned document."""
        files = [
            _make_knowledge_row(knowledge_id="kid-d-1", source="google_drive", doc_type="google_doc"),
            _make_knowledge_row(knowledge_id="kid-d-2", source="google_drive", doc_type="pdf"),
            _make_knowledge_row(knowledge_id="kid-a-1", source="agent", doc_type="markdown"),
        ]
        mock_sb = _make_supabase_mock(knowledge_rows=files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_document_service(monkeypatch, listed_rows=files)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}: {data}"
        assert len(data) == 3, f"Expected 3 documents, got {len(data)}: {data}"

        sources = {doc.get("source") for doc in data}
        assert "google_drive" in sources, f"Expected google_drive source, got sources: {sources}"
        assert "agent" in sources, f"Expected agent source, got sources: {sources}"

    def test_list_knowledge_includes_doc_type_field(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GET /api/workspaces/{id}/knowledge must include doc_type in each returned document."""
        files = [
            _make_knowledge_row(knowledge_id="kid-pdf-1", source="google_drive", doc_type="pdf"),
        ]
        mock_sb = _make_supabase_mock(knowledge_rows=files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)
        _patch_document_service(monkeypatch, listed_rows=files)

        response = test_client.get(f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert len(data) >= 1
        assert "doc_type" in data[0], f"Response object missing doc_type: {data[0]}"
        assert data[0]["doc_type"] == "pdf", f"Expected doc_type='pdf', got: {data[0]['doc_type']!r}"


# ---------------------------------------------------------------------------
# STORY-015-02: Reindex skips non-Drive documents
# ---------------------------------------------------------------------------


class TestReindexSkipsNonDriveDocs:
    """STORY-015-02 Scenario: Reindex only re-fetches Google Drive documents.

    Documents with source='upload' or source='agent' must be skipped.
    """

    def test_reindex_only_processes_google_drive_documents(
        self,
        test_client: TestClient,
        override_current_user: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """POST /knowledge/reindex must only re-index source='google_drive' documents.

        Set up: 2 Drive files + 1 agent doc in workspace.
        The mock returns only the 2 Drive files (matching the .eq(source=google_drive) filter).
        Reindexed count should be 2, not 3.
        """
        drive_files = [
            _make_knowledge_row(knowledge_id="kid-r-1", drive_file_id="drive-r-1", source="google_drive"),
            _make_knowledge_row(knowledge_id="kid-r-2", drive_file_id="drive-r-2", source="google_drive"),
        ]
        # The mock returns only drive docs (simulating .eq("source", "google_drive") filter)
        mock_sb = _make_reindex_supabase_mock(knowledge_rows=drive_files)
        monkeypatch.setattr("app.core.db.get_supabase", lambda: mock_sb)

        # Mock document_service.update_document to avoid actual AI calls
        try:
            import app.services.document_service as ds
            monkeypatch.setattr(
                ds, "update_document",
                AsyncMock(return_value=drive_files[0])
            )
        except (ImportError, AttributeError):
            pass

        _patch_drive_services(monkeypatch)
        _patch_scan_service(monkeypatch)
        _patch_encryption(monkeypatch)

        response = test_client.post(
            f"/api/workspaces/{FAKE_WORKSPACE_ID}/knowledge/reindex"
        )

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["reindexed"] == 2, (
            f"Expected reindexed=2 (only Drive docs), got: {data}. "
            "Reindex must skip agent/upload documents (source filter on google_drive)."
        )
        assert data["failed"] == 0, f"Expected failed=0, got: {data}"


# ---------------------------------------------------------------------------
# STORY-015-02: MIME → doc_type mapping
# ---------------------------------------------------------------------------


class TestMimeToDocTypeMapping:
    """STORY-015-02 R2: MIME type is mapped to doc_type on index.

    Verifies that the MIME_TO_DOC_TYPE mapping in knowledge.py is correct
    and that the mapped doc_type is passed to document_service.create_document.
    """

    def test_mime_mapping_module_attribute_exists(self) -> None:
        """knowledge module must define MIME_TO_DOC_TYPE mapping dict."""
        try:
            import app.api.routes.knowledge as km
        except ImportError:
            pytest.fail("app.api.routes.knowledge not importable")

        assert hasattr(km, "MIME_TO_DOC_TYPE"), (
            "knowledge module missing MIME_TO_DOC_TYPE dict (R2 of STORY-015-02)"
        )
        mapping = km.MIME_TO_DOC_TYPE
        assert mapping.get("application/vnd.google-apps.document") == "google_doc"
        assert mapping.get("application/pdf") == "pdf"
        assert mapping.get("application/vnd.openxmlformats-officedocument.wordprocessingml.document") == "docx"
        assert mapping.get("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "xlsx"
        assert mapping.get("application/vnd.google-apps.spreadsheet") == "google_sheet"
        assert mapping.get("application/vnd.google-apps.presentation") == "google_slides"
