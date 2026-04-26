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

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.routes.auth import router as auth_router
from app.api.routes import keys as keys_module
from app.api.routes.automations import router as automations_router
from app.api.routes.channels import router as channels_router
from app.api.routes.drive_oauth import router as drive_oauth_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.slack_events import router as slack_events_router
from app.api.routes.slack_oauth import router as slack_oauth_router
from app.api.routes.mcp_servers import router as mcp_servers_router
from app.api.routes.workspaces import router as workspace_router
from app.core.config import settings
from app.core.db import get_supabase
from app.core.encryption import key_fingerprint
from app.core.logging_config import setup_logging, request_id_ctx
from app.services.automation_cron import automation_cron_loop
from app.services.automation_executor import reset_stale_executions
from app.services.drive_sync_cron import drive_sync_loop
from app.services.wiki_ingest_cron import wiki_ingest_loop

# Configure logging as early as possible — before any route registration or
# module-level log calls below. This ensures the startup banner and the
# enc-key fingerprint line are both captured in JSON format.
setup_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager — startup and shutdown hooks.

    On startup:
      - Registers the Drive Content Sync Cron as an asyncio background task
        (STORY-015-05). The task runs every 10 minutes, checking all connected
        Google Drive workspaces for content changes.
      - Registers the Wiki Ingest Cron as an asyncio background task
        (STORY-013-03). The task runs every 60 seconds, processing all
        ``teemo_documents`` rows with ``sync_status='pending'``.
      - Resets any stale 'running' automation execution rows left over from a
        previous service restart (STORY-018-03).
      - Registers the Automation Cron as an asyncio background task
        (STORY-018-03). The task runs every 60 seconds, firing any automations
        whose ``next_run_at`` has elapsed.

    On shutdown:
      - Cancels all three cron tasks (Drive sync, Wiki ingest, Automation) so
        the event loop can terminate cleanly. Each task catches
        ``asyncio.CancelledError`` and logs a shutdown event before re-raising
        to allow clean termination.
    """
    # Start Drive content sync cron as a background task.
    cron_task = asyncio.create_task(drive_sync_loop())
    logger.info("lifespan.startup", extra={"event": "lifespan.startup", "detail": "Drive sync cron registered"})

    # Start Wiki Ingest Cron as a background task.
    wiki_cron_task = asyncio.create_task(wiki_ingest_loop())
    logger.info("lifespan.startup", extra={"event": "lifespan.startup", "detail": "Wiki ingest cron registered"})

    # Reset any stale 'running' execution rows left over from a previous restart.
    try:
        await reset_stale_executions(supabase=get_supabase())
        logger.info("lifespan.startup", extra={"event": "lifespan.startup", "detail": "Stale automation executions reset"})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "lifespan.startup.reset_stale_skip",
            extra={"event": "lifespan.startup", "detail": f"reset_stale_executions skipped: {exc}"},
        )

    # Start Automation Cron as a background task.
    automation_cron_task = asyncio.create_task(automation_cron_loop())
    logger.info("lifespan.startup", extra={"event": "lifespan.startup", "detail": "Automation cron registered"})

    yield

    # Shutdown: cancel background tasks gracefully.
    cron_task.cancel()
    wiki_cron_task.cancel()
    automation_cron_task.cancel()
    try:
        await cron_task
    except asyncio.CancelledError:
        pass
    try:
        await wiki_cron_task
    except asyncio.CancelledError:
        pass
    try:
        await automation_cron_task
    except asyncio.CancelledError:
        pass
    logger.info("lifespan.shutdown", extra={"event": "lifespan.shutdown", "detail": "Drive sync cron stopped"})
    logger.info("lifespan.shutdown", extra={"event": "lifespan.shutdown", "detail": "Wiki ingest cron stopped"})
    logger.info("lifespan.shutdown", extra={"event": "lifespan.shutdown", "detail": "Automation cron stopped"})


app = FastAPI(
    title="Tee-Mo API",
    version="0.1.0",
    description="Tee-Mo: AI assistant for Slack workspaces",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware that generates a UUID4 request ID for every incoming request.

    The ID is:
    1. Stored in ``request_id_ctx`` (ContextVar) so that all log calls made
       during the request automatically include it via ``RequestIdFilter``.
    2. Added to the HTTP response as ``X-Request-Id`` header for client-side
       correlation and debugging.

    Must be registered BEFORE ``AccessLogMiddleware`` so the context variable
    is set by the time the access log is written.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Generate request ID, set context var, delegate, and add header."""
        request_id = str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Middleware that logs one INFO line per completed HTTP request.

    Emits a structured log with: ``event``, ``method``, ``path``, ``status``,
    ``duration_ms``, ``request_id`` so that HTTP traffic is observable without
    requiring an external access log parser.

    The ``/api/health`` path is skipped to avoid flooding logs with liveness
    probe traffic from load balancers and Kubernetes probes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Time the request and emit an access log entry on completion."""
        start = time.monotonic()
        response: Response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000)

        # Skip health-check path to avoid probe noise
        if request.url.path != "/api/health":
            _access_logger.info(
                "http.request",
                extra={
                    "event": "http.request",
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id_ctx.get() or "–",
                },
            )
        return response


# Module-level logger for access log entries — distinct name so operators can
# filter/route access logs separately if needed.
_access_logger = logging.getLogger("teemo.access")

app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIdMiddleware)

app.include_router(auth_router)
app.include_router(slack_events_router)
app.include_router(slack_oauth_router)
app.include_router(drive_oauth_router)
app.include_router(knowledge_router)
app.include_router(workspace_router)
app.include_router(keys_module.router)
app.include_router(channels_router)
app.include_router(automations_router)
app.include_router(mcp_servers_router)

# Log the encryption key fingerprint at module import time (startup).
# Only the 8-char hex fingerprint is logged — never the raw key or any secret.
# ADR-002 / STORY-005A-01 Req 5: key_fingerprint() is the only permitted
# representation of TEEMO_ENCRYPTION_KEY in log output.
logger.info("enc key fp: %s", key_fingerprint())

# Canonical list of Tee-Mo tables — all must be reachable for status "ok".
# The teemo_ prefix is non-negotiable: this is a shared Supabase instance.
# Extended in STORY-003-03 per ADR-024: added teemo_slack_teams (migration 005)
# and teemo_workspace_channels (migration 006).
# Extended in STORY-013-01: added teemo_wiki_pages and teemo_wiki_log (migration 011).
TEEMO_TABLES = (
    "teemo_users",
    "teemo_workspaces",
    "teemo_documents",
    "teemo_skills",
    "teemo_slack_teams",
    "teemo_workspace_channels",
    "teemo_slack_team_members",
    "teemo_wiki_pages",
    "teemo_wiki_log",
    "teemo_automations",
    "teemo_automation_executions",
    "teemo_mcp_servers",  # STORY-012-01 (EPIC-012 MCP integration)
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
