"""Knowledge document Pydantic models (STORY-015-02 refactor of STORY-006-03).

Defines the request/response shapes for the Knowledge CRUD routes.
These models are used by the knowledge and documents API endpoints.

ADR compliance:
  - ADR-007: 15-document hard cap — enforced at the route level, not the model.
  - ADR-016: MIME type validation lives in the route (ALLOWED_MIME_TYPES set).

STORY-015-02 changes vs original STORY-006-03:
  - KnowledgeIndexResponse gains ``source`` and ``doc_type`` fields.
  - ``drive_file_id`` is aliased as ``external_id`` (backward-compat alias kept).
  - Added ``id`` UUID field (was implicit before).
  - Added ``CreateDocumentRequest`` for the new POST /documents endpoint.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class IndexFileRequest(BaseModel):
    """Request body for POST /api/workspaces/{id}/knowledge.

    Fields correspond to metadata provided by the Google Drive Picker widget.
    The content itself is fetched server-side using the stored refresh token.

    Attributes:
        drive_file_id: Google Drive file ID (e.g. "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms").
        title: Human-readable file title from the Drive Picker.
        link: Full Google Drive link to the file (for UI display).
        mime_type: MIME type of the file — must be in ALLOWED_MIME_TYPES (ADR-016).
        access_token: Optional short-lived Picker access token from the frontend.
    """

    drive_file_id: str
    title: str
    link: str
    mime_type: str
    access_token: Optional[str] = None


class KnowledgeIndexResponse(BaseModel):
    """Response shape for a single knowledge document row (teemo_documents).

    Returned by POST /api/workspaces/{id}/knowledge and items in the
    GET /api/workspaces/{id}/knowledge list response.

    STORY-015-02: Added ``source``, ``doc_type`` fields. ``id`` is now explicit.
    ``drive_file_id`` is an optional alias for ``external_id`` to support
    backward-compatible consumers that still read that field.

    Attributes:
        id: Primary key UUID of the document row.
        workspace_id: Owning workspace UUID.
        external_id: Google Drive file ID (formerly drive_file_id).
        drive_file_id: Alias for external_id — backward-compat for existing clients.
        title: File title.
        external_link: File URL (formerly ``link``).
        doc_type: Document type: google_doc, pdf, docx, xlsx, google_sheet, google_slides.
        source: Document source: google_drive, upload, or agent.
        ai_description: AI-generated summary (generated at index time per ADR-006).
        content_hash: SHA-256 hash of file content (used for change detection per ADR-006).
        created_at: ISO 8601 timestamp of when the file was first indexed.
        last_scanned_at: ISO 8601 timestamp of the most recent scan.
        warning: Optional warning message (e.g. content truncation notice).
    """

    id: str
    workspace_id: str
    title: str
    doc_type: Optional[str] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    external_link: Optional[str] = None
    # Backward-compat alias — external_id is the canonical column in teemo_documents
    drive_file_id: Optional[str] = Field(default=None, alias="external_id")
    ai_description: Optional[str] = None
    content_hash: Optional[str] = None
    created_at: Optional[str] = None
    last_scanned_at: Optional[str] = None
    warning: Optional[str] = None

    model_config = {"populate_by_name": True}


class CreateDocumentRequest(BaseModel):
    """Request body for POST /api/workspaces/{id}/documents.

    Used by agent tools (STORY-015-03) and as a public API to create
    markdown documents. The route always sets source='agent' and
    doc_type='markdown' — these are not caller-configurable.

    Attributes:
        title: Document title (required).
        content: Document text content in Markdown format.
    """

    title: str
    content: str
