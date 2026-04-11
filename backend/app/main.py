"""
Tee-Mo FastAPI application entry point.

Creates the FastAPI ``app`` instance, registers CORS middleware using origins
from ``settings.cors_origins_list()``, and exposes the health-check route.

The health endpoint checks all four ``teemo_*`` tables (STORY-001-02) and
returns a structured response indicating per-table reachability.

Usage (from ``backend/`` directory)::

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.core.config import settings
from app.core.db import get_supabase

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

# Canonical list of Tee-Mo tables — all must be reachable for status "ok".
# The teemo_ prefix is non-negotiable: this is a shared Supabase instance.
TEEMO_TABLES = ("teemo_users", "teemo_workspaces", "teemo_knowledge_index", "teemo_skills")


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
        # LIMIT 0 confirms table + permissions without fetching any rows
        get_supabase().table(table).select("id").limit(0).execute()
        return "ok"
    except Exception as exc:  # noqa: BLE001 — graceful degradation by design
        msg = str(exc)
        if "not find" in msg.lower() or "does not exist" in msg.lower():
            return f"missing: {msg[:120]}"
        return f"error: {msg[:120]}"


@app.get("/api/health")
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
