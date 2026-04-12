"""Knowledge index Pydantic models (STORY-006-03).

Defines the request/response shapes for the Knowledge CRUD routes.
These models are used by POST /api/workspaces/{id}/knowledge and
GET /api/workspaces/{id}/knowledge endpoints.

ADR compliance:
  - ADR-007: 15-file hard cap — enforced at the route level, not the model.
  - ADR-016: MIME type validation lives in the route (ALLOWED_MIME_TYPES set).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class IndexFileRequest(BaseModel):
    """Request body for POST /api/workspaces/{id}/knowledge.

    Fields correspond to metadata provided by the Google Drive Picker widget.
    The content itself is fetched server-side using the stored refresh token.

    Attributes:
        drive_file_id: Google Drive file ID (e.g. "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms").
        title: Human-readable file title from the Drive Picker.
        link: Full Google Drive link to the file (for UI display).
        mime_type: MIME type of the file — must be in ALLOWED_MIME_TYPES (ADR-016).
    """

    drive_file_id: str
    title: str
    link: str
    mime_type: str


class KnowledgeIndexRequest(BaseModel):
    """Alias request body for POST /api/workspaces/{id}/knowledge.

    Kept for backwards compatibility with any callers using the original name.
    Prefer IndexFileRequest for new code.

    Attributes:
        drive_file_id: Google Drive file ID.
        title: Human-readable file title.
        link: Full Google Drive link.
        mime_type: MIME type string (must be in ALLOWED_MIME_TYPES).
    """

    drive_file_id: str
    title: str
    link: str
    mime_type: str


class KnowledgeIndexResponse(BaseModel):
    """Response shape for a single knowledge index row.

    Returned by POST /api/workspaces/{id}/knowledge and items in the
    GET /api/workspaces/{id}/knowledge list response.

    Attributes:
        id: Primary key UUID.
        workspace_id: Owning workspace UUID.
        drive_file_id: Google Drive file ID.
        title: File title.
        link: File URL.
        mime_type: MIME type string.
        ai_description: AI-generated summary (generated at index time per ADR-006).
        content_hash: MD5 hash of file content (used for change detection per ADR-006).
        created_at: ISO 8601 timestamp of when the file was first indexed.
        last_scanned_at: ISO 8601 timestamp of the most recent scan.
        warning: Optional warning message (e.g. content truncation notice).
    """

    id: str
    workspace_id: str
    drive_file_id: str
    title: str
    link: str
    mime_type: str
    ai_description: str
    content_hash: str
    created_at: Optional[str] = None
    last_scanned_at: Optional[str] = None
    warning: Optional[str] = None
