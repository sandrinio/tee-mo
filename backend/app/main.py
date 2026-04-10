"""
Tee-Mo FastAPI application entry point.

Creates the FastAPI ``app`` instance, registers CORS middleware using origins
from ``settings.cors_origins_list()``, and exposes a single health-check route.

Usage (from ``backend/`` directory)::

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

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


@app.get("/api/health")
def health() -> dict[str, str]:
    """
    Health-check endpoint.

    Returns a fixed JSON payload confirming the service is running.
    No auth required. Used by load balancers and smoke tests.

    Returns
    -------
    dict
        ``{"status": "ok", "service": "tee-mo", "version": "0.1.0"}``
    """
    return {"status": "ok", "service": "tee-mo", "version": "0.1.0"}
