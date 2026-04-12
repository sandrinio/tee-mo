"""
Google Drive content extraction service — EPIC-006, STORY-006-01.

Provides three public functions:
  - get_drive_client: decrypt refresh token and build an authenticated Drive API client.
  - fetch_file_content: extract text from a Drive file by MIME type.
  - compute_content_hash: MD5 digest of content string for change detection.

MIME type support (ADR-016):
  - application/vnd.google-apps.document      → export as text/plain
  - application/vnd.google-apps.spreadsheet   → export as text/csv
  - application/vnd.google-apps.presentation  → export as text/plain
  - application/pdf                            → get_media + pypdf
  - application/vnd.openxmlformats-officedocument.wordprocessingml.document → get_media + python-docx
  - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet       → get_media + openpyxl

All imports that tests monkeypatch are at module level so monkeypatch.setattr works.
"""

from __future__ import annotations

import hashlib
import io

# Module-level imports required so tests can monkeypatch these names.
# (See FLASHCARDS.md httpx module-level import rule — same pattern applies here.)
from app.core.encryption import decrypt
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader
from docx import Document as DocxDocument
from openpyxl import load_workbook

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Content truncation threshold (ADR-016)
# ---------------------------------------------------------------------------

_TRUNCATION_LIMIT = 50_000
_TRUNCATION_NOTICE = "\n\n[Content truncated at 50000 characters]"

# ---------------------------------------------------------------------------
# MIME type routing
# ---------------------------------------------------------------------------

# Google Workspace export targets (ADR-016)
_GOOGLE_EXPORT_MIMES: dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

# Binary file MIME types handled via get_media + parser
_BINARY_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def get_drive_client(encrypted_refresh_token: str):
    """Decrypt an encrypted OAuth refresh token and build an authenticated Drive v3 client.

    Steps:
      1. Decrypt the refresh token using AES-256-GCM (app.core.encryption.decrypt).
      2. Construct a google.oauth2.credentials.Credentials instance with the
         decrypted refresh token and OAuth app credentials from Settings.
      3. Call creds.refresh(Request()) to exchange the refresh token for a
         short-lived access token.
      4. Build and return a googleapiclient Drive v3 service object.

    Args:
        encrypted_refresh_token: AES-256-GCM encrypted refresh token ciphertext,
            as stored in the database. NEVER log the plaintext.

    Returns:
        A googleapiclient Resource object for the Drive v3 API.
    """
    settings = get_settings()
    plaintext_token = decrypt(encrypted_refresh_token)

    creds = Credentials(
        token=None,
        refresh_token=plaintext_token,
        client_id=settings.google_api_client_id,
        client_secret=settings.google_api_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())

    return build("drive", "v3", credentials=creds)


def _download_media(drive_client, drive_file_id: str) -> bytes:
    """Download binary file content from Drive using MediaIoBaseDownload.

    Args:
        drive_client: Authenticated Drive v3 API client.
        drive_file_id: Google Drive file ID.

    Returns:
        Raw bytes of the downloaded file.
    """
    request = drive_client.files().get_media(fileId=drive_file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    buffer.seek(0)
    return buffer.read()


def _extract_pdf(raw_bytes: bytes) -> str:
    """Extract text from a PDF file using pypdf.

    Args:
        raw_bytes: Raw PDF file bytes.

    Returns:
        Concatenated text from all pages, joined with newlines.
    """
    reader = PdfReader(io.BytesIO(raw_bytes))
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n".join(texts)


def _extract_docx(raw_bytes: bytes) -> str:
    """Extract text from a Word DOCX file using python-docx.

    Args:
        raw_bytes: Raw DOCX file bytes.

    Returns:
        Concatenated paragraph text, joined with newlines.
    """
    doc = DocxDocument(io.BytesIO(raw_bytes))
    return "\n".join(para.text for para in doc.paragraphs)


def _extract_xlsx(raw_bytes: bytes) -> str:
    """Extract text from an Excel XLSX file using openpyxl.

    Iterates all sheets, all rows, all cells. Non-None cell values are
    converted to strings and joined with tab separators within a row;
    rows are joined with newlines; sheets are separated by double newlines.

    Args:
        raw_bytes: Raw XLSX file bytes.

    Returns:
        All cell values as a single text string.
    """
    wb = load_workbook(io.BytesIO(raw_bytes))
    sheet_texts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        row_texts = []
        for row in ws.iter_rows():
            cell_values = [str(cell.value) for cell in row if cell.value is not None]
            if cell_values:
                row_texts.append("\t".join(cell_values))
        if row_texts:
            sheet_texts.append("\n".join(row_texts))
    return "\n\n".join(sheet_texts)


def _maybe_truncate(content: str) -> str:
    """Truncate content at 50,000 characters and append a trim notice if needed.

    Args:
        content: Extracted text string (may be any length).

    Returns:
        Original string if <= 50,000 chars, or first 50,000 chars + trim notice.
    """
    if len(content) > _TRUNCATION_LIMIT:
        return content[:_TRUNCATION_LIMIT] + _TRUNCATION_NOTICE
    return content


def fetch_file_content(drive_client, drive_file_id: str, mime_type: str) -> str:
    """Extract text content from a Google Drive file by MIME type.

    Dispatches to the appropriate extraction strategy based on mime_type:
      - Google Workspace native types (Docs/Sheets/Slides): uses the Drive
        export API to convert to text/plain or text/csv.
      - PDF: downloads binary via get_media, then extracts text with pypdf.
      - DOCX: downloads binary via get_media, extracts with python-docx.
      - XLSX: downloads binary via get_media, extracts with openpyxl.
      - Unsupported types: raises ValueError.

    Content is truncated at 50,000 characters with a trim notice appended
    (ADR-016 content cap to prevent LLM context overflow).

    Args:
        drive_client: Authenticated Drive v3 API client (from get_drive_client).
        drive_file_id: Google Drive file ID (e.g. "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms").
        mime_type: MIME type of the file (as returned by the Drive files.list API).

    Returns:
        Extracted text content, truncated at 50,000 characters if necessary.

    Raises:
        ValueError: If mime_type is not one of the 6 supported types (ADR-016).
    """
    if mime_type in _GOOGLE_EXPORT_MIMES:
        export_mime = _GOOGLE_EXPORT_MIMES[mime_type]
        raw = drive_client.files().export(fileId=drive_file_id, mimeType=export_mime).execute()
        content = raw.decode("utf-8") if isinstance(raw, bytes) else raw

    elif mime_type == "application/pdf":
        raw_bytes = _download_media(drive_client, drive_file_id)
        content = _extract_pdf(raw_bytes)

    elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        raw_bytes = _download_media(drive_client, drive_file_id)
        content = _extract_docx(raw_bytes)

    elif mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        raw_bytes = _download_media(drive_client, drive_file_id)
        content = _extract_xlsx(raw_bytes)

    else:
        raise ValueError(
            f"Unsupported MIME type: {mime_type!r}. "
            f"Supported types: {sorted(_GOOGLE_EXPORT_MIMES.keys() | _BINARY_MIMES)}"
        )

    return _maybe_truncate(content)


def compute_content_hash(content: str) -> str:
    """Compute an MD5 hex digest of the content string for change detection.

    Used by the self-healing description mechanism (ADR-006): if the hash of
    the current Drive file content differs from the stored hash, the
    ai_description is re-generated.

    Args:
        content: Text content string to hash.

    Returns:
        32-character lowercase hexadecimal MD5 digest.
    """
    return hashlib.md5(content.encode()).hexdigest()
