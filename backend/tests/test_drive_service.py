"""
Tests for drive_service.py — STORY-006-07 (Red Phase) extends STORY-006-01.

Covers all Gherkin scenarios from §2.1:
  1.  get_drive_client — decrypts token, builds Credentials, refreshes, returns Drive client
  2.  fetch_file_content for Google Docs (text/plain export) — unchanged
  3.  fetch_file_content for Google Sheets — NOW exports as XLSX, routes through _extract_xlsx
  4.  fetch_file_content for Google Slides — NOW inserts slide boundary markers
  5.  fetch_file_content for PDF — NOW uses pymupdf4llm.to_markdown (not PdfReader)
  6.  fetch_file_content for Word DOCX — NOW extracts tables as markdown alongside paragraphs
  7.  fetch_file_content for Word DOCX without tables (regression) — paragraphs only, no markdown table syntax
  8.  fetch_file_content for Excel XLSX — NOW outputs ## Sheet: headers + pipe-separated markdown tables
  9.  Excel XLSX with empty sheet skipped — empty sheet does not appear in output
  10. Excel XLSX with None cells — None renders as empty between pipes, no "None" string
  11. Content truncation at 50K chars with trim notice appended — unchanged
  12. compute_content_hash returns MD5 hex digest — unchanged
  13. Unsupported MIME type raises ValueError — unchanged
  14. PDF with headings preserved — markdown heading syntax (#) present in output

Mock strategy:
  - `app.core.encryption.decrypt` is patched to return a deterministic plaintext token.
  - `google.oauth2.credentials.Credentials` is patched at module level.
  - `google.auth.transport.requests.Request` is patched at module level.
  - `googleapiclient.discovery.build` is patched at module level.
  - `drive_service.pymupdf4llm` and `drive_service.pymupdf` are monkeypatched (module-level imports).
  - `drive_service.DocxDocument`, `drive_service.load_workbook` are monkeypatched.
  - `drive_service.MediaIoBaseDownload` is monkeypatched for binary download paths.
  - No real Google API calls are made.
"""

from __future__ import annotations

import hashlib
import io
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Import guard — module may not exist yet (RED phase)
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

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
SLIDES_MIME = "application/vnd.google-apps.presentation"
DOCS_MIME = "application/vnd.google-apps.document"


def _make_drive_client_mock(
    export_content: bytes | None = None,
    media_content: bytes | None = None,
) -> MagicMock:
    """Build a minimal Drive API client mock supporting files().export() and files().get_media()."""
    media_io_result = MagicMock()
    if media_content is not None:
        media_io_result.read.return_value = media_content

    request_export = MagicMock()
    request_export.execute.return_value = export_content or b""

    request_media = MagicMock()
    request_media.execute.return_value = None  # MediaIoBaseDownload handles it

    files_resource = MagicMock()
    files_resource.export.return_value = request_export
    files_resource.get_media.return_value = request_media

    drive_client = MagicMock()
    drive_client.files.return_value = files_resource
    return drive_client


def _make_downloader_mock(monkeypatch) -> MagicMock:
    """Attach a mock MediaIoBaseDownload to drive_service and return the instance mock."""
    mock_downloader_instance = MagicMock()
    mock_downloader_instance.next_chunk.side_effect = [
        (MagicMock(progress=lambda: 1.0), True)
    ]
    mock_downloader_cls = MagicMock(return_value=mock_downloader_instance)
    monkeypatch.setattr(drive_service, "MediaIoBaseDownload", mock_downloader_cls)
    return mock_downloader_instance


def _make_binary_drive_client() -> MagicMock:
    """Drive client mock for get_media flows (binary extraction tests)."""
    drive_client = MagicMock()
    files_resource = MagicMock()
    request_media = MagicMock()
    files_resource.get_media.return_value = request_media
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
    """Google Docs → export as text/plain (unchanged from STORY-006-01)."""

    def test_exports_google_doc_as_text_plain(self):
        """fetch_file_content must call files.export with mimeType='text/plain' for Google Docs."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        expected_text = "Hello from Google Docs"
        drive_client = _make_drive_client_mock(export_content=expected_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            DOCS_MIME,
        )

        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType="text/plain",
        )
        assert expected_text in result


# ---------------------------------------------------------------------------
# Scenario 3 (updated): Google Sheets → export as XLSX (not CSV), via _extract_xlsx
# ---------------------------------------------------------------------------

class TestFetchFileContentGoogleSheets:
    """Google Sheets → export as XLSX MIME type, routed through _extract_xlsx."""

    def test_exports_google_sheet_as_xlsx_not_csv(self, monkeypatch):
        """fetch_file_content must call files.export with XLSX mimeType (not CSV) for Sheets."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Build a mock workbook with one sheet and one data row.
        # _extract_xlsx calls load_workbook and ws.iter_rows(values_only=True).
        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            ("header1", "header2"),
            ("val1", "val2"),
        ]
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        mock_load_workbook = MagicMock(return_value=mock_wb)
        monkeypatch.setattr(drive_service, "load_workbook", mock_load_workbook)

        fake_xlsx_bytes = b"PK\x03\x04fake-xlsx-content"
        drive_client = _make_drive_client_mock(export_content=fake_xlsx_bytes)

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SHEETS_MIME,
        )

        # Must export with XLSX mime, NOT text/csv
        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType=XLSX_MIME,
        )
        # load_workbook must have been called, indicating _extract_xlsx was used
        mock_load_workbook.assert_called_once()

    def test_google_sheets_output_contains_markdown_table(self, monkeypatch):
        """Google Sheets result must contain pipe-separated markdown table from _extract_xlsx."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_ws = MagicMock()
        mock_ws.iter_rows.return_value = [
            ("Name", "Revenue"),
            ("Alice", "1000"),
            ("Bob", "2000"),
        ]
        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sales"]
        mock_wb.__getitem__ = MagicMock(return_value=mock_ws)
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))

        drive_client = _make_drive_client_mock(export_content=b"fake-xlsx")

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SHEETS_MIME,
        )

        # Output must contain pipe-separated markdown table
        assert "|" in result
        assert "Name" in result
        assert "Revenue" in result

    def test_google_sheets_output_contains_sheet_header(self, monkeypatch):
        """Google Sheets result must contain ## Sheet: header for each sheet."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_ws1 = MagicMock()
        mock_ws1.iter_rows.return_value = [("A", "B"), ("1", "2")]
        mock_ws2 = MagicMock()
        mock_ws2.iter_rows.return_value = [("X", "Y"), ("3", "4")]

        def _getitem(name):
            return {"Q1": mock_ws1, "Q2": mock_ws2}[name]

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Q1", "Q2"]
        mock_wb.__getitem__ = _getitem
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))

        drive_client = _make_drive_client_mock(export_content=b"fake-xlsx")

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SHEETS_MIME,
        )

        assert "## Sheet: Q1" in result
        assert "## Sheet: Q2" in result


# ---------------------------------------------------------------------------
# Scenario 4 (updated): Google Slides → slide boundary markers
# ---------------------------------------------------------------------------

class TestFetchFileContentGoogleSlides:
    """Google Slides → export as text/plain, then insert slide boundary markers."""

    def test_exports_google_slides_as_text_plain(self):
        """fetch_file_content must call files.export with mimeType='text/plain' for Slides."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Form-feed (\x0c) separates slides in the Drive text/plain export
        slide_text = "Intro slide\x0cSecond slide\x0cThird slide"
        drive_client = _make_drive_client_mock(export_content=slide_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SLIDES_MIME,
        )

        drive_client.files().export.assert_called_once_with(
            fileId=DRIVE_FILE_ID,
            mimeType="text/plain",
        )
        assert result is not None

    def test_google_slides_inserts_slide_boundary_markers(self):
        """fetch_file_content must insert '--- Slide N ---' markers between slides."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Drive text/plain export uses form-feed (\x0c) between slides
        slide_text = "Title: Welcome\x0cContent: Agenda\x0cContent: Summary"
        drive_client = _make_drive_client_mock(export_content=slide_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SLIDES_MIME,
        )

        assert "--- Slide 1 ---" in result
        assert "--- Slide 2 ---" in result
        assert "--- Slide 3 ---" in result

    def test_google_slides_content_preserved_between_markers(self):
        """Slide content (text) must be preserved alongside the boundary markers."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        slide_text = "Introduction\x0cDetails here\x0cConclusion"
        drive_client = _make_drive_client_mock(export_content=slide_text.encode())

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            SLIDES_MIME,
        )

        assert "Introduction" in result
        assert "Details here" in result
        assert "Conclusion" in result


# ---------------------------------------------------------------------------
# Scenario 5 (updated): PDF — pymupdf4llm.to_markdown (not PdfReader)
# ---------------------------------------------------------------------------

class TestFetchFileContentPDF:
    """PDF → get_media + pymupdf4llm markdown extraction."""

    def test_fetches_pdf_via_get_media_and_extracts_markdown(self, monkeypatch):
        """fetch_file_content must use pymupdf + pymupdf4llm for PDFs, not PdfReader."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        markdown_output = "# Heading\n\nSome PDF paragraph text."

        # Mock pymupdf module — drive_service will call pymupdf.open(stream=..., filetype="pdf")
        mock_pymupdf_doc = MagicMock()
        mock_pymupdf_module = MagicMock()
        mock_pymupdf_module.open.return_value = mock_pymupdf_doc

        # Mock pymupdf4llm module — drive_service will call pymupdf4llm.to_markdown(doc)
        mock_pymupdf4llm_module = MagicMock()
        mock_pymupdf4llm_module.to_markdown.return_value = markdown_output

        monkeypatch.setattr(drive_service, "pymupdf", mock_pymupdf_module)
        monkeypatch.setattr(drive_service, "pymupdf4llm", mock_pymupdf4llm_module)

        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            PDF_MIME,
        )

        # Must use get_media, not export
        drive_client.files().get_media.assert_called_once_with(fileId=DRIVE_FILE_ID)
        # Must call pymupdf4llm.to_markdown
        mock_pymupdf4llm_module.to_markdown.assert_called_once_with(mock_pymupdf_doc)
        assert markdown_output in result

    def test_pdf_markdown_contains_pipe_table(self, monkeypatch):
        """PDF with tables: output contains pipe-separated markdown table rows."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Simulate pymupdf4llm returning a markdown table
        table_markdown = (
            "| Col1 | Col2 | Col3 |\n"
            "| --- | --- | --- |\n"
            "| A | B | C |\n"
            "| D | E | F |\n"
        )

        mock_pymupdf_doc = MagicMock()
        mock_pymupdf_module = MagicMock()
        mock_pymupdf_module.open.return_value = mock_pymupdf_doc

        mock_pymupdf4llm_module = MagicMock()
        mock_pymupdf4llm_module.to_markdown.return_value = table_markdown

        monkeypatch.setattr(drive_service, "pymupdf", mock_pymupdf_module)
        monkeypatch.setattr(drive_service, "pymupdf4llm", mock_pymupdf4llm_module)

        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            PDF_MIME,
        )

        assert "|" in result
        assert "Col1" in result
        assert "Col2" in result
        assert "Col3" in result

    def test_pdf_markdown_contains_heading_syntax(self, monkeypatch):
        """PDF with headings: output contains markdown heading syntax (# ...)."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        heading_markdown = "# Main Title\n\nBody paragraph text here."

        mock_pymupdf_doc = MagicMock()
        mock_pymupdf_module = MagicMock()
        mock_pymupdf_module.open.return_value = mock_pymupdf_doc

        mock_pymupdf4llm_module = MagicMock()
        mock_pymupdf4llm_module.to_markdown.return_value = heading_markdown

        monkeypatch.setattr(drive_service, "pymupdf", mock_pymupdf_module)
        monkeypatch.setattr(drive_service, "pymupdf4llm", mock_pymupdf4llm_module)

        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            PDF_MIME,
        )

        # Must contain markdown heading syntax
        assert "# " in result
        assert "Main Title" in result


# ---------------------------------------------------------------------------
# Scenario 6 (updated): Word DOCX — tables extracted as markdown alongside paragraphs
# ---------------------------------------------------------------------------

class TestFetchFileContentDocx:
    """Word DOCX → get_media + python-docx extraction with table support."""

    def _make_docx_element_mock(self, tag_suffix: str) -> MagicMock:
        """Create a mock XML element with a tag ending in the given suffix (e.g. 'p' or 'tbl')."""
        elem = MagicMock()
        elem.tag = f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{tag_suffix}"
        return elem

    def test_fetches_docx_with_tables_and_extracts_markdown(self, monkeypatch):
        """fetch_file_content must extract paragraphs AND tables from DOCX, tables as markdown."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        para_text = "This is a paragraph"

        # Build mock paragraph element
        para_elem = self._make_docx_element_mock("p")
        mock_para = MagicMock()
        mock_para.text = para_text
        mock_para._element = para_elem

        # Build mock table element
        tbl_elem = self._make_docx_element_mock("tbl")

        # Build mock table with rows and cells
        mock_cell_1 = MagicMock()
        mock_cell_1.text = "Header A"
        mock_cell_2 = MagicMock()
        mock_cell_2.text = "Header B"
        mock_cell_3 = MagicMock()
        mock_cell_3.text = "Val 1"
        mock_cell_4 = MagicMock()
        mock_cell_4.text = "Val 2"

        mock_row_1 = MagicMock()
        mock_row_1.cells = [mock_cell_1, mock_cell_2]
        mock_row_2 = MagicMock()
        mock_row_2.cells = [mock_cell_3, mock_cell_4]

        mock_table = MagicMock()
        mock_table.rows = [mock_row_1, mock_row_2]
        mock_table._element = tbl_elem

        # Build mock document
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = [mock_table]

        # Body iterates paragraph element then table element
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([para_elem, tbl_elem]))

        mock_document_cls = MagicMock(return_value=mock_doc)
        monkeypatch.setattr(drive_service, "DocxDocument", mock_document_cls)
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            DOCX_MIME,
        )

        drive_client.files().get_media.assert_called_once_with(fileId=DRIVE_FILE_ID)
        # Paragraph text must be present
        assert para_text in result
        # Table headers and values must be present
        assert "Header A" in result
        assert "Header B" in result
        assert "Val 1" in result
        assert "Val 2" in result

    def test_docx_table_rendered_as_markdown_table(self, monkeypatch):
        """DOCX table must appear as pipe-separated markdown with separator row."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        tbl_elem = self._make_docx_element_mock("tbl")

        mock_cell_h1 = MagicMock(); mock_cell_h1.text = "Name"
        mock_cell_h2 = MagicMock(); mock_cell_h2.text = "Score"
        mock_cell_d1 = MagicMock(); mock_cell_d1.text = "Alice"
        mock_cell_d2 = MagicMock(); mock_cell_d2.text = "95"

        mock_row_header = MagicMock()
        mock_row_header.cells = [mock_cell_h1, mock_cell_h2]
        mock_row_data = MagicMock()
        mock_row_data.cells = [mock_cell_d1, mock_cell_d2]

        mock_table = MagicMock()
        mock_table.rows = [mock_row_header, mock_row_data]
        mock_table._element = tbl_elem

        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = [mock_table]
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([tbl_elem]))

        monkeypatch.setattr(drive_service, "DocxDocument", MagicMock(return_value=mock_doc))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            DOCX_MIME,
        )

        # Must contain pipe characters for markdown table
        assert "|" in result
        assert "Name" in result
        assert "Score" in result
        assert "Alice" in result
        assert "95" in result
        # Must have separator row with dashes
        assert "---" in result

    def test_docx_without_tables_returns_paragraphs_only(self, monkeypatch):
        """Regression: DOCX with only paragraphs (no tables) must return plain text, no markdown table syntax."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        para_text_1 = "First paragraph content"
        para_text_2 = "Second paragraph content"

        para_elem_1 = self._make_docx_element_mock("p")
        para_elem_2 = self._make_docx_element_mock("p")

        mock_para_1 = MagicMock()
        mock_para_1.text = para_text_1
        mock_para_1._element = para_elem_1

        mock_para_2 = MagicMock()
        mock_para_2.text = para_text_2
        mock_para_2._element = para_elem_2

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para_1, mock_para_2]
        mock_doc.tables = []
        mock_doc.element.body.__iter__ = MagicMock(return_value=iter([para_elem_1, para_elem_2]))

        monkeypatch.setattr(drive_service, "DocxDocument", MagicMock(return_value=mock_doc))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            DOCX_MIME,
        )

        assert para_text_1 in result
        assert para_text_2 in result
        # No markdown table syntax should appear when there are no tables
        assert "|" not in result


# ---------------------------------------------------------------------------
# Scenario 7 (updated): Excel XLSX — markdown tables with ## Sheet: headers
# ---------------------------------------------------------------------------

class TestFetchFileContentXlsx:
    """Excel XLSX → markdown tables with ## Sheet: headers per sheet."""

    def _make_workbook_mock(self, sheets: dict) -> MagicMock:
        """Build a mock openpyxl workbook.

        Args:
            sheets: dict mapping sheet_name -> list of row tuples (values_only=True style).
        """
        sheet_mocks = {}
        for name, rows in sheets.items():
            ws = MagicMock()
            ws.iter_rows.return_value = rows
            sheet_mocks[name] = ws

        mock_wb = MagicMock()
        mock_wb.sheetnames = list(sheets.keys())
        mock_wb.__getitem__ = MagicMock(side_effect=lambda n: sheet_mocks[n])
        return mock_wb

    def test_xlsx_outputs_sheet_name_headers(self, monkeypatch):
        """_extract_xlsx output must include '## Sheet: {name}' for each non-empty sheet."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_wb = self._make_workbook_mock({
            "Q1": [("Revenue", "Profit"), ("100", "20"), ("200", "50")],
            "Q2": [("Revenue", "Profit"), ("300", "70")],
        })
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            XLSX_MIME,
        )

        assert "## Sheet: Q1" in result
        assert "## Sheet: Q2" in result

    def test_xlsx_outputs_pipe_separated_markdown_table(self, monkeypatch):
        """_extract_xlsx must produce pipe-separated markdown tables with a separator row."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_wb = self._make_workbook_mock({
            "Data": [
                ("Name", "Value"),
                ("Alpha", "1"),
                ("Beta", "2"),
            ],
        })
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            XLSX_MIME,
        )

        assert "|" in result
        assert "Name" in result
        assert "Value" in result
        assert "Alpha" in result
        # Separator row must be present (--- tokens)
        assert "---" in result

    def test_xlsx_empty_sheet_skipped(self, monkeypatch):
        """Empty sheets (no rows) must not appear in the output."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_wb = self._make_workbook_mock({
            "Data": [("Col1", "Col2"), ("row1a", "row1b")],
            "Empty": [],  # no rows
        })
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            XLSX_MIME,
        )

        assert "## Sheet: Data" in result
        # Empty sheet header must NOT appear
        assert "## Sheet: Empty" not in result
        assert "Empty" not in result

    def test_xlsx_none_cells_render_as_empty_not_none_string(self, monkeypatch):
        """None cells must appear as empty between pipe separators, not as the string 'None'."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_wb = self._make_workbook_mock({
            "Sheet1": [
                ("A", "B", "C"),
                ("val1", None, "val3"),
                (None, "val2", None),
            ],
        })
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            XLSX_MIME,
        )

        # "None" string must not appear anywhere
        assert "None" not in result
        # Must still contain the actual values
        assert "val1" in result
        assert "val2" in result
        assert "val3" in result

    def test_xlsx_multi_sheet_all_sheets_appear(self, monkeypatch):
        """All non-empty sheets must appear in the output with their data."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        mock_wb = self._make_workbook_mock({
            "January": [("Item", "Sales"), ("Widget", "500")],
            "February": [("Item", "Sales"), ("Gadget", "300")],
            "March": [("Item", "Sales"), ("Doohickey", "700")],
        })
        monkeypatch.setattr(drive_service, "load_workbook", MagicMock(return_value=mock_wb))
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            XLSX_MIME,
        )

        assert "## Sheet: January" in result
        assert "## Sheet: February" in result
        assert "## Sheet: March" in result
        assert "Widget" in result
        assert "Gadget" in result
        assert "Doohickey" in result


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
            DOCS_MIME,
        )

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
            DOCS_MIME,
        )

        assert short_content in result
        assert "truncated" not in result.lower()

    def test_truncation_with_notice_matches_spec_text(self, monkeypatch):
        """Truncation notice must contain the spec text '[Content truncated at 50000 characters]'."""
        if drive_service is None:
            pytest.skip("drive_service not yet implemented (RED phase)")

        # Use a binary path to ensure markdown content can also be truncated.
        # Mock pymupdf4llm to return > 50K chars of markdown
        long_markdown = "# Heading\n\n" + "A" * 60_000

        mock_pymupdf_doc = MagicMock()
        mock_pymupdf_module = MagicMock()
        mock_pymupdf_module.open.return_value = mock_pymupdf_doc

        mock_pymupdf4llm_module = MagicMock()
        mock_pymupdf4llm_module.to_markdown.return_value = long_markdown

        monkeypatch.setattr(drive_service, "pymupdf", mock_pymupdf_module)
        monkeypatch.setattr(drive_service, "pymupdf4llm", mock_pymupdf4llm_module)
        _make_downloader_mock(monkeypatch)
        drive_client = _make_binary_drive_client()

        result = drive_service.fetch_file_content(
            drive_client,
            DRIVE_FILE_ID,
            PDF_MIME,
        )

        assert "[Content truncated at 50000 characters]" in result


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
            assert "unsupported" in result.lower() or "unknown" in result.lower() or "error" in result.lower()
        except (ValueError, NotImplementedError):
            pass  # Either approach is acceptable
