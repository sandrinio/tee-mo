"""
Tests for drive_service.py — STORY-006-01 (Red Phase).

Covers all Gherkin scenarios from §2.1:
  1. get_drive_client — decrypts token, builds Credentials, refreshes, returns Drive client
  2. fetch_file_content for Google Docs (text/plain export)
  3. fetch_file_content for Google Sheets (text/csv export)
  4. fetch_file_content for Google Slides (text/plain export)
  5. fetch_file_content for PDF (get_media + pypdf extraction)
  6. fetch_file_content for Word DOCX (get_media + python-docx extraction)
  7. fetch_file_content for Excel XLSX (get_media + openpyxl extraction)
  8. Content truncation at 50K chars with trim notice appended
  9. compute_content_hash returns MD5 hex digest
  10. Unsupported MIME type raises ValueError (or returns an error string)

Mock strategy:
  - `app.core.encryption.decrypt` is patched to return a deterministic plaintext token.
  - `google.oauth2.credentials.Credentials` is patched at module level.
  - `google.auth.transport.requests.Request` is patched at module level.
  - `googleapiclient.discovery.build` is patched at module level.
  - `pypdf.PdfReader`, `docx.Document`, `openpyxl.load_workbook` are patched
    at module level in drive_service to intercept binary extraction calls.
  - No real Google API calls are made.
"""

from __future__ import annotations

import hashlib
import io
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import guard — module does not exist yet (RED phase)
# ---------------------------------------------------------------------------

drive_service = None

try:
    import app.services.drive_service as _ds  # type: ignore[import]
    drive_service = _ds
except ImportError:
    pass  # Expected during RED phase — implementation not yet written


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENCRYPTED_REFRESH_TOKEN = "encrypted-token-blob-001"
DECRYPTED_REFRESH_TOKEN = "1//plaintext-refresh-token"
DRIVE_FILE_ID = "drive-file-id-abc123"
FAKE_API_KEY = "fake-google-client-id"
FAKE_SECRET = "fake-google-client-secret"


def _make_drive_client_mock(export_content: bytes | None = None, media_content: bytes | None = None) -> MagicMock:
    """Build a minimal Drive API client mock supporting files().export() and files().get_media()."""
    media_io_result = MagicMock()
    if media_content is not None:
        media_io_result.read.return_value = media_content

    request_export = MagicMock()
    request_export.execute.return_value = export_content or b""

    request_media = MagicMock()
    # get_media returns a MediaIoBaseDownload-compatible request
    request_media.execute.return_value = None  # MediaIoBaseDownload handles it

    files_resource = MagicMock()
    files_resource.export.return_value = request_export
    files_resource.get_media.return_value = request_media

    drive_client = MagicMock()
    drive_client.files.return_value = files_resource
    return drive_client


# ---------------------------------------------------------------------------
# Scenario 1: get_drive_client — decrypt, build Credentials, refresh, build client
# ---------------------------------------------------------------------------

class TestGetDriveClient:
    """Tests for drive_service.get_drive_client()."""

    def test_decrypts_refresh_token(self, monkeypatch):
        """get_drive_client must call decrypt() with the encrypted token."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_decrypt = MagicMock(return_value=DECRYPTED_REFRESH_TOKEN)
        mock_creds_cls = MagicMock()
        mock_creds_instance = MagicMock()
        mock_creds_cls.return_value = mock_creds_instance
        mock_request_cls = MagicMock()
        mock_build = MagicMock()

        monkeypatch.setattr(drive_service, "decrypt", mock_decrypt)
        monkeypatch.setattr(drive_service, "Credentials", mock_creds_cls)
        monkeypatch.setattr(drive_service, "Request", mock_request_cls)
        monkeypatch.setattr(drive_service, "build", mock_build)

        drive_service.get_drive_client(ENCRYPTED_REFRESH_TOKEN)

        mock_decrypt.assert_called_once_with(ENCRYPTED_REFRESH_TOKEN)

    def test_creates_credentials_with_correct_params(self, monkeypatch):
        """get_drive_client must instantiate Credentials with the decrypted token."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_decrypt = MagicMock(return_value=DECRYPTED_REFRESH_TOKEN)
        mock_creds_cls = MagicMock()
        mock_creds_instance = MagicMock()
        mock_creds_cls.return_value = mock_creds_instance
        mock_request_cls = MagicMock()
        mock_build = MagicMock()

        monkeypatch.setattr(drive_service, "decrypt", mock_decrypt)
        monkeypatch.setattr(drive_service, "Credentials", mock_creds_cls)
        monkeypatch.setattr(drive_service, "Request", mock_request_cls)
        monkeypatch.setattr(drive_service, "build", mock_build)

        drive_service.get_drive_client(ENCRYPTED_REFRESH_TOKEN)

        # Credentials must be constructed with token=None and refresh_token set
        call_kwargs = mock_creds_cls.call_args.kwargs
        assert call_kwargs.get("token") is None
        assert call_kwargs.get("refresh_token") == DECRYPTED_REFRESH_TOKEN
        assert call_kwargs.get("token_uri") == "https://oauth2.googleapis.com/token"

    def test_calls_creds_refresh(self, monkeypatch):
        """get_drive_client must call creds.refresh() to exchange for an access token."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_decrypt = MagicMock(return_value=DECRYPTED_REFRESH_TOKEN)
        mock_creds_cls = MagicMock()
        mock_creds_instance = MagicMock()
        mock_creds_cls.return_value = mock_creds_instance
        mock_request_cls = MagicMock()
        mock_build = MagicMock()

        monkeypatch.setattr(drive_service, "decrypt", mock_decrypt)
        monkeypatch.setattr(drive_service, "Credentials", mock_creds_cls)
        monkeypatch.setattr(drive_service, "Request", mock_request_cls)
        monkeypatch.setattr(drive_service, "build", mock_build)

        drive_service.get_drive_client(ENCRYPTED_REFRESH_TOKEN)

        mock_creds_instance.refresh.assert_called_once()

    def test_returns_drive_v3_client(self, monkeypatch):
        """get_drive_client must return the result of build('drive', 'v3')."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_decrypt = MagicMock(return_value=DECRYPTED_REFRESH_TOKEN)
        mock_creds_cls = MagicMock()
        mock_creds_instance = MagicMock()
        mock_creds_cls.return_value = mock_creds_instance
        mock_request_cls = MagicMock()
        fake_drive_client = MagicMock()
        mock_build = MagicMock(return_value=fake_drive_client)

        monkeypatch.setattr(drive_service, "decrypt", mock_decrypt)
        monkeypatch.setattr(drive_service, "Credentials", mock_creds_cls)
        monkeypatch.setattr(drive_service, "Request", mock_request_cls)
        monkeypatch.setattr(drive_service, "build", mock_build)

        result = drive_service.get_drive_client(ENCRYPTED_REFRESH_TOKEN)

        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds_instance)
        assert result is fake_drive_client


# ---------------------------------------------------------------------------
# Scenario 2: fetch_file_content — Google Docs (application/vnd.google-apps.document)
# ---------------------------------------------------------------------------

class TestFetchFileContentGoogleDocs:
    """Google Docs → export as text/plain."""

    def test_exports_google_doc_as_text_plain(self):
        """fetch_file_content must call files.export with mimeType='text/plain' for Google Docs."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        expected_text = "Hello from Google Docs"
        drive_client = _make_drive_client_mock(export_content=expected_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.google-apps.document",
        )

        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType="text/plain",
        )
        assert expected_text in result


# ---------------------------------------------------------------------------
# Scenario 3: fetch_file_content — Google Sheets (application/vnd.google-apps.spreadsheet)
# ---------------------------------------------------------------------------

class TestFetchFileContentGoogleSheets:
    """Google Sheets → export as text/csv."""

    def test_exports_google_sheet_as_csv(self):
        """fetch_file_content must call files.export with mimeType='text/csv' for Sheets."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        expected_csv = "col1,col2\nval1,val2\n"
        drive_client = _make_drive_client_mock(export_content=expected_csv.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.google-apps.spreadsheet",
        )

        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType="text/csv",
        )
        assert expected_csv in result


# ---------------------------------------------------------------------------
# Scenario 4: fetch_file_content — Google Slides (application/vnd.google-apps.presentation)
# ---------------------------------------------------------------------------

class TestFetchFileContentGoogleSlides:
    """Google Slides → export as text/plain."""

    def test_exports_google_slides_as_text_plain(self):
        """fetch_file_content must call files.export with mimeType='text/plain' for Slides."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        expected_text = "Slide 1: Introduction\nSlide 2: Details"
        drive_client = _make_drive_client_mock(export_content=expected_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.google-apps.presentation",
        )

        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType="text/plain",
        )
        assert expected_text in result


# ---------------------------------------------------------------------------
# Scenario 5: fetch_file_content — PDF (application/pdf)
# ---------------------------------------------------------------------------

class TestFetchFileContentPDF:
    """PDF → get_media + pypdf text extraction."""

    def test_fetches_pdf_via_get_media_and_extracts_text(self, monkeypatch):
        """fetch_file_content must use files.get_media() + pypdf for PDFs."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        extracted_text = "PDF page one content"

        # Mock PdfReader to return extracted text
        mock_page = MagicMock()
        mock_page.extract_text.return_value = extracted_text
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_pdf_reader_cls = MagicMock(return_value=mock_reader_instance)

        monkeypatch.setattr(drive_service, "PdfReader", mock_pdf_reader_cls)

        # Drive client returns bytes via MediaIoBaseDownload flow
        drive_client = MagicMock()
        files_resource = MagicMock()
        request_media = MagicMock()
        files_resource.get_media.return_value = request_media
        drive_client.files.return_value = files_resource

        # Mock MediaIoBaseDownload
        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.side_effect = [
            (MagicMock(progress=lambda: 1.0), True)
        ]
        mock_downloader_cls = MagicMock(return_value=mock_downloader_instance)
        monkeypatch.setattr(drive_service, "MediaIoBaseDownload", mock_downloader_cls)

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/pdf",
        )

        files_resource.get_media.assert_called_once_with(fileId=DRIVE_FILE_ID)
        assert extracted_text in result


# ---------------------------------------------------------------------------
# Scenario 6: fetch_file_content — Word DOCX
# ---------------------------------------------------------------------------

class TestFetchFileContentDocx:
    """Word DOCX → get_media + python-docx extraction."""

    def test_fetches_docx_via_get_media_and_extracts_text(self, monkeypatch):
        """fetch_file_content must use files.get_media() + python-docx for DOCX files."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        extracted_text = "Word document paragraph one"

        mock_para = MagicMock()
        mock_para.text = extracted_text
        mock_doc_instance = MagicMock()
        mock_doc_instance.paragraphs = [mock_para]
        mock_document_cls = MagicMock(return_value=mock_doc_instance)

        monkeypatch.setattr(drive_service, "DocxDocument", mock_document_cls)

        drive_client = MagicMock()
        files_resource = MagicMock()
        request_media = MagicMock()
        files_resource.get_media.return_value = request_media
        drive_client.files.return_value = files_resource

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.side_effect = [
            (MagicMock(progress=lambda: 1.0), True)
        ]
        mock_downloader_cls = MagicMock(return_value=mock_downloader_instance)
        monkeypatch.setattr(drive_service, "MediaIoBaseDownload", mock_downloader_cls)

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        files_resource.get_media.assert_called_once_with(fileId=DRIVE_FILE_ID)
        assert extracted_text in result


# ---------------------------------------------------------------------------
# Scenario 7: fetch_file_content — Excel XLSX
# ---------------------------------------------------------------------------

class TestFetchFileContentXlsx:
    """Excel XLSX → get_media + openpyxl extraction."""

    def test_fetches_xlsx_via_get_media_and_extracts_text(self, monkeypatch):
        """fetch_file_content must use files.get_media() + openpyxl for XLSX files."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        cell_value = "spreadsheet cell value"

        mock_cell = MagicMock()
        mock_cell.value = cell_value
        mock_row = [mock_cell]
        mock_sheet = MagicMock()
        mock_sheet.iter_rows.return_value = [mock_row]
        mock_wb_instance = MagicMock()
        mock_wb_instance.sheetnames = ["Sheet1"]
        mock_wb_instance.__getitem__ = MagicMock(return_value=mock_sheet)
        mock_load_workbook_cls = MagicMock(return_value=mock_wb_instance)

        monkeypatch.setattr(drive_service, "load_workbook", mock_load_workbook_cls)

        drive_client = MagicMock()
        files_resource = MagicMock()
        request_media = MagicMock()
        files_resource.get_media.return_value = request_media
        drive_client.files.return_value = files_resource

        mock_downloader_instance = MagicMock()
        mock_downloader_instance.next_chunk.side_effect = [
            (MagicMock(progress=lambda: 1.0), True)
        ]
        mock_downloader_cls = MagicMock(return_value=mock_downloader_instance)
        monkeypatch.setattr(drive_service, "MediaIoBaseDownload", mock_downloader_cls)

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        files_resource.get_media.assert_called_once_with(fileId=DRIVE_FILE_ID)
        assert cell_value in result


# ---------------------------------------------------------------------------
# Scenario 8: Content truncation at 50K chars
# ---------------------------------------------------------------------------

class TestContentTruncation:
    """Content exceeding 50K chars must be truncated with a trim notice."""

    def test_content_truncated_at_50k_chars(self):
        """fetch_file_content must truncate returned content at 50000 chars and append trim notice."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Build content that's 60000 chars
        long_content = "A" * 60_000
        drive_client = _make_drive_client_mock(export_content=long_content.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.google-apps.document",
        )

        # Result must be capped + have a trim notice
        assert len(result) <= 50_000 + 200  # allow some slack for the notice
        assert result[:50_000] == "A" * 50_000
        assert "truncated" in result.lower() or "[" in result

    def test_content_under_50k_not_truncated(self):
        """fetch_file_content must NOT truncate content that is under 50000 chars."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        short_content = "Hello world"
        drive_client = _make_drive_client_mock(export_content=short_content.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            "application/vnd.google-apps.document",
        )

        assert short_content in result
        # No truncation notice for short content
        assert "truncated" not in result.lower()


# ---------------------------------------------------------------------------
# Scenario 9: compute_content_hash returns MD5 hex digest
# ---------------------------------------------------------------------------

class TestComputeContentHash:
    """compute_content_hash must return MD5 hex digest of the content string."""

    def test_returns_md5_hex_digest(self):
        """compute_content_hash must return the MD5 hexdigest of the given string."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        content = "The quick brown fox jumps over the lazy dog"
        expected_hash = hashlib.md5(content.encode()).hexdigest()

        result = drive_service.compute_content_hash(content)

        assert result == expected_hash

    def test_returns_32_char_hex_string(self):
        """MD5 digest must be a 32-character lowercase hex string."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        result = drive_service.compute_content_hash("test content")

        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_content_different_hash(self):
        """Different content strings must produce different hashes."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        hash_a = drive_service.compute_content_hash("content A")
        hash_b = drive_service.compute_content_hash("content B")

        assert hash_a != hash_b

    def test_same_content_same_hash(self):
        """Same content string must always produce the same hash (deterministic)."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        content = "deterministic content"
        hash_1 = drive_service.compute_content_hash(content)
        hash_2 = drive_service.compute_content_hash(content)

        assert hash_1 == hash_2


# ---------------------------------------------------------------------------
# Scenario 10: Unsupported MIME type
# ---------------------------------------------------------------------------

class TestUnsupportedMimeType:
    """Unsupported MIME types must result in an error (ValueError or error string)."""

    def test_unsupported_mime_type_raises_or_returns_error(self):
        """fetch_file_content must raise ValueError or return error string for unknown MIME type."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        drive_client = _make_drive_client_mock()

        try:
            result = drive_service.fetch_file_content(
                drive_client,
                DRIVE_FILE_ID,
                "application/x-unknown-format",
            )
            # If it doesn't raise, it must return a meaningful error indicator
            assert "unsupported" in result.lower() or "unknown" in result.lower() or "error" in result.lower()
        except (ValueError, NotImplementedError):
            pass  # Either approach is acceptable
