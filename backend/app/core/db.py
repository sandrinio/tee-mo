"""
Supabase client factory for Tee-Mo backend.

Provides a single cached service-role Supabase client used by all backend
code that needs to interact with the self-hosted Supabase instance.

ADR compliance:
- ADR-015: supabase==2.28.3 (pinned in pyproject.toml)
- ADR-020: self-hosted Supabase at settings.supabase_url
- Sprint context: one singleton — do NOT create a new client per-request

Usage::

    from app.core.db import get_supabase

    client = get_supabase()
    result = client.table("teemo_users").select("id").limit(1).execute()
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings
from starlette.concurrency import run_in_threadpool
from typing import Any


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Return the cached service-role Supabase client.

    Uses ``functools.lru_cache`` to guarantee a single client instance for
    the lifetime of the process, avoiding connection-pool exhaustion on the
    self-hosted instance (sprint context rule).

    The client is created using the **service-role key** (not the anon key)
    so backend code has full table access without hitting RLS policies that
    don't yet exist.  The service-role key must NEVER be sent to the browser.

    Returns
    -------
    Client
        An initialised ``supabase.Client`` bound to ``settings.supabase_url``
        and authenticated with ``settings.supabase_service_role_key``.
    """
    return create_client(settings.supabase_url, settings.supabase_service_role_key)

async def execute_async(query_builder: Any) -> Any:
    """
    Executes a Supabase query builder inside Starlette's non-blocking ThreadPool.
    Prevents synchronous HTTP calls (supabase-py v2.x) from blocking the FastAPI asyncio loop.
    """
    return await run_in_threadpool(query_builder.execute)
