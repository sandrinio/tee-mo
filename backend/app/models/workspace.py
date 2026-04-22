"""
Workspace Pydantic models for Tee-Mo API.

These models define the request and response contracts for Workspace CRUD.
Crucially, WorkspaceResponse explicitly omits secret fields like
`encrypted_api_key` and `encrypted_google_refresh_token`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceBase(BaseModel):
    """Base model for workspace data."""

    name: str = Field(..., min_length=1, max_length=120)


class WorkspaceCreate(WorkspaceBase):
    """Request model for POST /api/slack-teams/{team_id}/workspaces"""

    slack_team_id: str = Field(..., min_length=1, max_length=32)


class WorkspaceUpdate(BaseModel):
    """Request model for PATCH /api/workspaces/{id}"""

    name: str = Field(..., min_length=1, max_length=120)
    bot_persona: Optional[str] = Field(None, max_length=2000)


class WorkspaceResponse(WorkspaceBase):
    """
    Public workspace model — safe to return to the frontend.
    EXPLICITLY OMITS encrypted_api_key and encrypted_google_refresh_token
    to prevent secret leakage.
    """

    id: UUID
    user_id: UUID
    slack_team_id: Optional[str] = None
    ai_provider: Optional[str] = Field(None, max_length=16)
    ai_model: Optional[str] = Field(None, max_length=64)
    is_default_for_team: bool = False
    bot_persona: Optional[str] = Field(None, max_length=2000)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
