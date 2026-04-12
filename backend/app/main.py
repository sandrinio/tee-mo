"""
Tee-Mo FastAPI application entry point.

Creates the FastAPI ``app`` instance, registers CORS middleware using origins
from ``settings.cors_origins_list()``, and exposes the health-check route.

The health endpoint checks all six ``teemo_*`` tables (STORY-001-02,
STORY-003-03) and returns a structured response indicating per-table
reachability.

In production (Docker/Coolify), the Vite-built frontend is served from
``/app/static/`` via FastAPI's StaticFiles with SPA fallback (STORY-003-01).
The static mount is skipped in local dev when ``static/`` does not exist.

Usage (from ``backend/`` directory)::

    uvicorn app.main:app --reload
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes import keys as keys_module
from app.api.routes.slack_events import router as slack_events_router
from app.api.routes.slack_oauth import router as slack_oauth_router
from app.api.routes.workspaces import router as workspace_router
from app.core.config import settings
from app.core.db import get_supabase
from app.core.encryption import key_fingerprint

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tee-Mo API",
    version="0.1.0",
    description="Tee-Mo: AI assistant for Slack workspaces",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(slack_events_router)
app.include_router(slack_oauth_router)
app.include_router(workspace_router)
app.include_router(keys_module.router)

# Log the encryption key fingerprint at module import time (startup).
# Only the 8-char hex fingerprint is logged — never the raw key or any secret.
# ADR-002 / STORY-005A-01 Req 5: key_fingerprint() is the only permitted
# representation of TEEMO_ENCRYPTION_KEY in log output.
logger.info("enc key fp: %s", key_fingerprint())

# Canonical list of Tee-Mo tables — all must be reachable for status "ok".
# The teemo_ prefix is non-negotiable: this is a shared Supabase instance.
# Extended in STORY-003-03 per ADR-024: added teemo_slack_teams (migration 005)
# and teemo_workspace_channels (migration 006).
TEEMO_TABLES = (
    "teemo_users",
    "teemo_workspaces",
    "teemo_knowledge_index",
    "teemo_skills",
    "teemo_slack_teams",
    "teemo_workspace_channels",
)


def _check_table(table: str) -> str:
    """
    Probe a single Supabase table for existence and basic query access.

    Uses ``LIMIT 0`` so no rows are returned — the round-trip only confirms
    the table exists and the service-role key can access it.

    Parameters
    ----------
    table : str
        The fully-prefixed table name (e.g. ``"teemo_users"``).

    Returns
    -------
    str
        ``"ok"`` if the table responds without error.
        ``"missing: <detail>"`` if the error message indicates the table does
        not exist (substring match on common Supabase/PostgreSQL error text).
        ``"error: <detail>"`` for any other failure, truncated to 120 chars to
        keep the health response payload compact.
    """
    try:
        # LIMIT 0 confirms table + permissions without fetching any rows.
        # Use select("*") not select("id") — not every teemo_* table has an
        # `id` column. teemo_slack_teams uses slack_team_id as PK (ADR-024)
        # and teemo_workspace_channels uses slack_channel_id as PK (ADR-024/025).
        # "*" is column-agnostic; with LIMIT 0 no row data is transferred.
        get_supabase().table(table).select("*").limit(0).execute()
        return "ok"
    except Exception as exc:  # noqa: BLE001 — graceful degradation by design
        msg = str(exc)
        if "not find" in msg.lower() or "does not exist" in msg.lower():
            return f"missing: {msg[:120]}"
        return f"error: {msg[:120]}"


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health() -> dict:
    """
    Health-check endpoint with Supabase schema smoke check.

    Sequentially probes each ``teemo_*`` table using a zero-cost
    ``SELECT id LIMIT 0`` query.  One table failing does not raise an
    exception — errors are captured per-table and reflected in the
    ``database`` object.

    Returns
    -------
    dict
        ``status`` — ``"ok"`` when all 4 tables are reachable;
        ``"degraded"`` when any table check is not ``"ok"``.

        ``service`` — always ``"tee-mo"``.

        ``version`` — semver string from the FastAPI app config.

        ``database`` — one key per ``teemo_*`` table; value is ``"ok"``,
        ``"missing: <detail>"``, or ``"error: <detail>"``.

    Notes
    -----
    No auth required. Used by load balancers and manual smoke checks.
    See STORY-001-02 §1.2 R3 for the full response shape contract.
    """
    db_status = {t: _check_table(t) for t in TEEMO_TABLES}
    overall = "ok" if all(v == "ok" for v in db_status.values()) else "degraded"
    return {
        "status": overall,
        "service": "tee-mo",
        "version": "0.1.0",
        "database": db_status,
    }


# Serve frontend static files for same-origin deploy (STORY-003-01).
# MUST be added AFTER all API route registrations so FastAPI's routing table
# matches /api/* paths before the static handler or SPA fallback.
# In production (Docker), /app/static/ contains the Vite build output.
# Path: backend/app/main.py -> parent = app/ -> parent.parent = backend/
#       -> parent.parent.parent = /app (container) -> /app/static.
# The is_dir() guard ensures local dev (no static/ on host) still works without error.
#
# Two-part pattern for SPA support:
#   1. Mount /assets/* and other real static files via StaticFiles.
#   2. Catch-all GET route returns index.html so TanStack Router can handle
#      client-side routes like /login, /register, /app.
#
# Note: Starlette's StaticFiles(html=True) only serves index.html for directory
# paths, NOT as a generic SPA fallback for arbitrary paths like /login.
# The explicit catch-all route below is required for correct SPA behaviour.
_static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if _static_dir.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_static_dir / "assets")),
        name="frontend-assets",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        """Serve the frontend favicon from the static directory."""
        return FileResponse(str(_static_dir / "favicon.svg"))

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        """
        SPA catch-all route — serves index.html for any unmatched GET path.

        TanStack Router handles client-side routing (/login, /register, /app, etc.)
        entirely in the browser. The server only needs to return index.html for
        every non-API, non-asset path so the browser can boot the React app.

        Must be registered AFTER all API routes. FastAPI matches routes in
        registration order, so /api/* routes defined earlier always win.
        """
        return FileResponse(str(_static_dir / "index.html"))
