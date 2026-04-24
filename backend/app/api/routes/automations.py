"""Automations REST endpoints for the Tee-Mo API.

STORY-018-02: Automations REST Endpoints

Implements 7 REST endpoints for managing workspace automations:

  POST   /api/workspaces/{workspace_id}/automations          — create (201)
  GET    /api/workspaces/{workspace_id}/automations          — list (200)
  GET    /api/workspaces/{workspace_id}/automations/{automation_id} — get one (200/404)
  PATCH  /api/workspaces/{workspace_id}/automations/{automation_id} — partial update (200)
  DELETE /api/workspaces/{workspace_id}/automations/{automation_id} — delete (204)
  GET    /api/workspaces/{workspace_id}/automations/{automation_id}/history — history (200)
  POST   /api/workspaces/{workspace_id}/automations/test-run — dry-run preview (200)

Authorization pattern:
- All endpoints require authentication via ``get_current_user_id``.
- Every endpoint verifies workspace ownership via ``_assert_workspace_owner``.
- Non-owners receive HTTP 403 Forbidden.

Pydantic models are defined at module scope (R4):
- AutomationCreate, AutomationUpdate, AutomationResponse,
  AutomationExecutionResponse, AutomationTestRunRequest, AutomationTestRunResponse

Error mapping (R5):
- ValueError from service    → HTTP 422
- None from get_automation   → HTTP 404
- DuplicateAutomationName    → HTTP 409

Dry-run (R6):
- _run_preview_prompt is a top-level async function (required for monkeypatch in tests).
- Builds a tool-free Agent with the workspace's BYOK model.
- Enforces 30-second asyncio.wait_for timeout.
- Never writes to teemo_automation_executions.

IMPORTANT: Do NOT add ``from __future__ import annotations`` to this file.
FastAPI resolves type annotations at runtime for dependency injection.
Stringifying annotations (PEP 563) breaks this. See FLASHCARDS.md.

IMPORTANT: ``automation_service`` is imported at MODULE LEVEL (not inside
handlers) so that tests can monkeypatch it via
``monkeypatch.setattr(automations_module.automation_service, "create_automation", ...)``.
See FLASHCARDS.md — httpx module-level import rule; same principle applies here.

ADR references: ADR-001 (JWT auth via cookie), ADR-024 (workspace-owned channels).
"""

import asyncio
import logging
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_id
from app.core.db import get_supabase
from app.services import automation_service  # MODULE LEVEL — do not move inside functions

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/workspaces/{workspace_id}/automations",
    tags=["automations"],
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class DuplicateAutomationName(Exception):
    """Raised when an automation with the same name already exists in the workspace.

    The route handler catches this and returns HTTP 409 Conflict with
    a detail message indicating the duplicate name.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"Automation with name '{name}' already exists")
        self.name = name


# ---------------------------------------------------------------------------
# Pydantic models (R4)
# ---------------------------------------------------------------------------


class AutomationCreate(BaseModel):
    """Request body for POST /automations — create a new automation.

    Attributes
    ----------
    name : str
        Human-readable name for the automation. Must be unique within the workspace.
    prompt : str
        The AI prompt that will run on the schedule.
    schedule : dict
        Schedule configuration dict. Must pass ``validate_schedule`` in the service.
        Example: ``{"occurrence": "daily", "when": "09:00"}``.
    slack_channel_ids : list[str]
        One or more Slack channel IDs to deliver results to. Must be bound to
        the workspace via teemo_workspace_channels. min_length=1 enforced by Pydantic.
    schedule_type : Literal["recurring", "once"]
        Whether this automation repeats or runs once. Defaults to "recurring".
    timezone : str
        IANA timezone string for schedule interpretation. Defaults to "UTC".
    description : Optional[str]
        Optional human-readable description. Stored but not used by the engine.
    """

    name: str
    prompt: str
    schedule: dict
    slack_channel_ids: list[str] = Field(min_length=1)
    schedule_type: Literal["recurring", "once"] = "recurring"
    timezone: str = "UTC"
    description: Optional[str] = None


class AutomationUpdate(BaseModel):
    """Request body for PATCH /automations/{automation_id} — partial update.

    All fields are optional. Only keys present in the request body are updated.
    Re-validates schedule and slack_channel_ids if included in the patch.
    """

    name: Optional[str] = None
    prompt: Optional[str] = None
    schedule: Optional[dict] = None
    slack_channel_ids: Optional[list[str]] = None
    schedule_type: Optional[Literal["recurring", "once"]] = None
    timezone: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AutomationResponse(BaseModel):
    """Response model for a single automation row.

    Matches the teemo_automations table schema (migration 012).
    """

    id: str
    workspace_id: str
    owner_user_id: str
    name: str
    description: Optional[str] = None
    prompt: str
    slack_channel_ids: list[str]
    schedule: dict
    schedule_type: str
    timezone: str
    is_active: bool
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str
    updated_at: str


class AutomationExecutionResponse(BaseModel):
    """Response model for a single automation execution record.

    Matches the teemo_automation_executions table schema (migration 012).
    """

    id: str
    automation_id: str
    status: str
    was_dry_run: bool
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    generated_content: Optional[str] = None
    delivery_results: Optional[Any] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    execution_time_ms: Optional[int] = None


class AutomationTestRunRequest(BaseModel):
    """Request body for POST /automations/test-run — ephemeral dry-run preview.

    Attributes
    ----------
    prompt : str
        The prompt to execute. Never persisted; runs once and returns output.
    """

    prompt: str


class AutomationTestRunResponse(BaseModel):
    """Response model for the test-run endpoint.

    Always returns HTTP 200. ``success=False`` indicates a handled failure
    (missing BYOK key, timeout, runtime error) — not a server error.

    Attributes
    ----------
    success : bool
        True if the agent produced output; False on any failure condition.
    output : Optional[str]
        The agent's text output. None when success=False.
    error : Optional[str]
        Error description when success=False. One of:
        - "no_key_configured" — workspace has no BYOK API key
        - "timeout after 30s" — LLM call exceeded 30 seconds
        - Any other exception message for unexpected failures.
    tokens_used : Optional[int]
        Token count from the agent run. None when success=False.
    execution_time_ms : Optional[int]
        Wall-clock time in milliseconds. Present even on timeout/error.
    """

    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    execution_time_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Authorization helper
# ---------------------------------------------------------------------------


def _assert_workspace_owner(
    workspace_id: str, user_id: str, supabase: Any
) -> dict[str, Any]:
    """Verify that the authenticated user owns the given workspace.

    Queries ``teemo_workspaces`` for a row matching both ``id`` and ``user_id``.
    Raises HTTP 403 if no match — prevents cross-user automation access.

    Parameters
    ----------
    workspace_id : str
        The workspace UUID from the path parameter.
    user_id : str
        The authenticated caller's UUID (from JWT sub claim).
    supabase : Any
        The injected Supabase service-role client.

    Returns
    -------
    dict
        The raw Supabase workspace row.

    Raises
    ------
    HTTPException(403)
        If the user does not own the specified workspace.
    """
    result = (
        supabase.table("teemo_workspaces")
        .select("*")
        .eq("id", workspace_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=403, detail="Forbidden")
    return result.data[0]


# ---------------------------------------------------------------------------
# Dry-run preview helper (must be a top-level function for monkeypatching)
# ---------------------------------------------------------------------------


async def _run_preview_prompt(
    workspace_id: str, prompt: str, *, supabase: Any
) -> AutomationTestRunResponse:
    """Build and run a tool-free preview agent for the given workspace prompt.

    Fetches the workspace's BYOK configuration (ai_provider, ai_model,
    encrypted_api_key), builds a minimal ``pydantic_ai.Agent`` with no tools,
    and runs the prompt with a 30-second timeout.

    This function is intentionally a module-level async def (not nested inside
    the route handler) so that tests can monkeypatch it via:
        ``monkeypatch.setattr(automations_module, "_run_preview_prompt", fake_fn)``

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace to fetch BYOK config for.
    prompt : str
        The user-supplied prompt to run.
    supabase : Any
        The injected Supabase service-role client.

    Returns
    -------
    AutomationTestRunResponse
        Always returns this model — never raises. On missing key, timeout,
        or unexpected exception, ``success=False`` with an ``error`` field.
    """
    # 1. Fetch workspace BYOK configuration
    row = (
        supabase.table("teemo_workspaces")
        .select("ai_provider, ai_model, encrypted_api_key")
        .eq("id", workspace_id)
        .maybe_single()
        .execute()
    )
    if not row.data or not row.data.get("encrypted_api_key"):
        return AutomationTestRunResponse(
            success=False,
            error="no_key_configured",
            output=None,
            tokens_used=None,
            execution_time_ms=None,
        )

    provider = row.data["ai_provider"]
    model_id = row.data["ai_model"]

    # Import decrypt at call time to avoid circular import issues
    from app.core.encryption import decrypt
    api_key = decrypt(row.data["encrypted_api_key"])

    # 2. Build a minimal tool-free agent using the same provider wiring as
    #    the production Slack agent. Passing the API key via `model_settings`
    #    on .run() does NOT work for Google — GoogleProvider reads the key at
    #    construction time. Use _build_pydantic_ai_model so BYOK keys reach
    #    GoogleProvider(api_key=...) / AnthropicProvider / OpenAIProvider.
    from pydantic_ai import Agent  # lazy import — avoid startup overhead
    from app.agents.agent import (
        _build_pydantic_ai_model,
        _ensure_model_imports,
    )

    _ensure_model_imports(provider)
    model = _build_pydantic_ai_model(model_id, provider, api_key)
    preview = Agent(
        model=model,
        system_prompt=(
            "You are a preview agent. Respond to the user's prompt as you would "
            "in a scheduled run, without calling any tools."
        ),
    )

    # 3. Run with 30-second timeout
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            preview.run(prompt),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        return AutomationTestRunResponse(
            success=False,
            error="timeout after 30s",
            output=None,
            tokens_used=None,
            execution_time_ms=int((time.monotonic() - t0) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 — surface as non-fatal error
        return AutomationTestRunResponse(
            success=False,
            error=str(exc),
            output=None,
            tokens_used=None,
            execution_time_ms=int((time.monotonic() - t0) * 1000),
        )

    dt = int((time.monotonic() - t0) * 1000)
    return AutomationTestRunResponse(
        success=True,
        output=str(result.output),
        error=None,
        tokens_used=getattr(result, "usage_tokens", None),
        execution_time_ms=dt,
    )


# ---------------------------------------------------------------------------
# POST /test-run — MUST be declared BEFORE /{automation_id} routes
# to prevent FastAPI from treating "test-run" as an automation_id path param.
# ---------------------------------------------------------------------------


@router.post("/test-run", response_model=AutomationTestRunResponse)
async def test_run(
    workspace_id: str,
    body: AutomationTestRunRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> AutomationTestRunResponse:
    """Run a prompt ephemerally against the workspace's BYOK model (dry-run).

    Verifies workspace ownership then delegates to ``_run_preview_prompt``.
    Always returns HTTP 200 — failures are surfaced in the response body
    (``success=False`` with ``error`` field). Never writes to
    ``teemo_automation_executions`` (R6.7).

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    body : AutomationTestRunRequest
        The prompt to run.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    AutomationTestRunResponse
        ``{success, output, error, tokens_used, execution_time_ms}``.
        HTTP 200 even on failure.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)
    return await _run_preview_prompt(workspace_id, body.prompt, supabase=supabase)


# ---------------------------------------------------------------------------
# POST /api/workspaces/{workspace_id}/automations — create
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=AutomationResponse)
async def create_automation(
    workspace_id: str,
    body: AutomationCreate,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> dict[str, Any]:
    """Create a new workspace automation.

    Verifies ownership, then delegates to ``automation_service.create_automation``.
    The service validates the schedule and channel bindings before inserting.

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    body : AutomationCreate
        Create payload. ``slack_channel_ids`` must have at least one entry (Pydantic
        min_length=1) and all IDs must be bound to the workspace.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    dict
        The created automation row. HTTP 201 Created.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    HTTPException(409)
        An automation with the same name already exists in the workspace.
    HTTPException(422)
        Invalid schedule or unbound channel IDs (ValueError from service).
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)

    payload = body.model_dump()
    try:
        row = automation_service.create_automation(
            workspace_id, user_id, payload, supabase=supabase
        )
    except DuplicateAutomationName as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return row


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/automations — list
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AutomationResponse])
async def list_automations(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> list[dict[str, Any]]:
    """List all automations in a workspace, ordered by created_at DESC.

    Returns an empty list (not 404) when no automations exist.
    Results are workspace-scoped — R8 is enforced by the service layer.

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    list[dict]
        List of automation row dicts. HTTP 200.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)
    return automation_service.list_automations(workspace_id, supabase=supabase)


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/automations/{automation_id} — get one
# ---------------------------------------------------------------------------


@router.get("/{automation_id}", response_model=AutomationResponse)
async def get_automation(
    workspace_id: str,
    automation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> dict[str, Any]:
    """Fetch a single automation by ID within a workspace.

    Both workspace_id and automation_id must match — prevents cross-workspace
    leaks even if a caller provides a valid automation_id from another workspace.

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    automation_id : str
        UUID of the automation to fetch (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    dict
        The automation row dict. HTTP 200.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    HTTPException(404)
        No automation with the given ID exists in this workspace.
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)
    row = automation_service.get_automation(workspace_id, automation_id, supabase=supabase)
    if row is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return row


# ---------------------------------------------------------------------------
# PATCH /api/workspaces/{workspace_id}/automations/{automation_id} — update
# ---------------------------------------------------------------------------


@router.patch("/{automation_id}", response_model=AutomationResponse)
async def update_automation(
    workspace_id: str,
    automation_id: str,
    body: AutomationUpdate,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> dict[str, Any]:
    """Partially update an automation's fields.

    Only keys present in the request body are updated. Re-validates
    schedule and slack_channel_ids if included in the patch.

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    automation_id : str
        UUID of the automation to update (path parameter).
    body : AutomationUpdate
        Partial update payload. Only non-None fields are applied.
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    dict
        The updated automation row. HTTP 200.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    HTTPException(404)
        No automation with the given ID exists in this workspace.
    HTTPException(422)
        Invalid schedule or unbound channel IDs (ValueError from service).
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)

    # Only include fields that were explicitly set (exclude_none for partial update)
    patch = body.model_dump(exclude_none=True)

    try:
        row = automation_service.update_automation(
            workspace_id, automation_id, patch, supabase=supabase
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if row is None:
        raise HTTPException(status_code=404, detail="Automation not found")
    return row


# ---------------------------------------------------------------------------
# DELETE /api/workspaces/{workspace_id}/automations/{automation_id} — delete
# ---------------------------------------------------------------------------


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    workspace_id: str,
    automation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> Response:
    """Delete an automation and all associated execution history.

    Execution rows are removed by ON DELETE CASCADE on the FK (migration 012).
    Returns 204 No Content regardless of whether the automation existed.

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter).
    automation_id : str
        UUID of the automation to delete (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    Response
        HTTP 204 No Content.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)
    automation_service.delete_automation(workspace_id, automation_id, supabase=supabase)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /api/workspaces/{workspace_id}/automations/{automation_id}/history
# ---------------------------------------------------------------------------


@router.get("/{automation_id}/history", response_model=list[AutomationExecutionResponse])
async def get_automation_history(
    workspace_id: str,
    automation_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Any = Depends(get_supabase),
) -> list[dict[str, Any]]:
    """Return the last 50 execution records for an automation, sorted DESC.

    The service enforces the 50-row limit and DESC ordering. This endpoint
    is workspace-scoped via the ownership check.

    Note: ``automation_service.get_automation_history`` is called with
    only ``automation_id`` as the first positional arg (the service's
    ``workspace_id`` parameter is for API symmetry but not used in the query).

    Parameters
    ----------
    workspace_id : str
        UUID of the workspace (path parameter, used for ownership check).
    automation_id : str
        UUID of the automation whose history to fetch (path parameter).
    user_id : str
        Injected by ``get_current_user_id``; raises 401 if missing/invalid.
    supabase : Any
        Injected Supabase service-role client.

    Returns
    -------
    list[dict]
        Up to 50 execution row dicts ordered by started_at DESC. HTTP 200.

    Raises
    ------
    HTTPException(401)
        No or invalid auth token.
    HTTPException(403)
        Authenticated user does not own the workspace.
    """
    _assert_workspace_owner(workspace_id, user_id, supabase)
    return automation_service.get_automation_history(
        workspace_id, automation_id, supabase=supabase
    )
