"""
Supabase client factory for Tee-Mo backend.

Provides a single cached service-role Supabase client + a retry-aware
``execute_async`` wrapper.

ADR compliance:
- ADR-015: supabase==2.28.3 (pinned in pyproject.toml)
- ADR-020: self-hosted Supabase at settings.supabase_url

Concurrency note (HOTFIX 2026-04-26, third iteration):
- v1 (original): process-wide singleton via ``functools.lru_cache(maxsize=1)``.
  Failure mode: ~5% of parallel requests under EPIC-025's heavy useQuery
  fan-out hit a self-hosted PostgREST 401 ``"Duplicate API key found"`` —
  a race in postgrest-py 2.x's sync client around shared session headers.
- v2 (HOTFIX 3): switched to ``threading.local()`` so each FastAPI worker
  thread had its own client. Eliminated the header race but introduced a
  new failure mode: each thread opened its own httpx.Client → up to 40
  long-lived TCP connections to the upstream Kong/PostgREST proxy →
  intermittent ``httpx.RemoteProtocolError: <StreamReset>`` and
  ``Server disconnected`` from Kong rejecting excess connections.
- v3 (HOTFIX 9, this file): revert to the singleton client (one TCP
  connection, HTTP/2 multiplexed) AND wrap ``execute_async`` with a small
  retry loop (max 2 retries with 50/100ms backoff) for the two known
  transient error classes. This handles both root causes without
  incurring the cost of either pure approach.

Both error classes ARE transient — a retry succeeds in nearly all cases
because the underlying upstream issue is per-request, not per-client-state.

Usage::

    from app.core.db import get_supabase

    client = get_supabase()
    result = await execute_async(client.table("teemo_users").select("id").limit(1))
"""

import asyncio
import logging
from functools import lru_cache
from typing import Any

import httpx
from postgrest.exceptions import APIError
from starlette.concurrency import run_in_threadpool
from supabase import Client, create_client

from app.core.config import settings


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Return the cached service-role Supabase client.

    Singleton (process-wide) — re-using one httpx.Client preserves HTTP/2
    multiplexing and avoids overwhelming the upstream Kong/PostgREST proxy
    with parallel TCP connections.

    The client is created using the **service-role key** (not the anon key)
    so backend code has full table access without hitting RLS policies that
    don't yet exist. The service-role key must NEVER be sent to the browser.
    """
    return create_client(
        settings.supabase_url, settings.supabase_service_role_key
    )


# Transient errors that warrant a retry. Both classes have been observed
# under the EPIC-025 workspace shell's parallel useQuery fan-out:
#   - APIError code=401 detail="Duplicate API key found" — postgrest-py
#     header race (intermittent, vanishes on retry).
#   - httpx.RemoteProtocolError (StreamReset / Server disconnected) — Kong
#     dropping HTTP/2 streams under burst load (also intermittent).
_RETRY_BACKOFF_SECS = (0.05, 0.10)  # 50ms, 100ms — two retries total


def _is_transient(exc: BaseException) -> bool:
    """True if the exception is a known intermittent error worth retrying."""
    if isinstance(exc, httpx.RemoteProtocolError):
        return True
    if isinstance(exc, APIError):
        # supabase-py wraps the upstream JSON in str(exc); match on the
        # known signature without depending on the dict shape.
        return "Duplicate API key" in str(exc)
    return False


async def execute_async(query_builder: Any) -> Any:
    """
    Execute a Supabase query builder inside Starlette's threadpool with a
    retry on transient upstream errors.

    Why threadpool: supabase-py v2.x is synchronous; calling .execute()
    directly from an async handler would block the FastAPI event loop.
    Why retry: see module docstring — two known transient failure modes
    (header race + Kong stream resets) under heavy parallel load.
    """
    last_exc: BaseException | None = None
    for attempt, backoff in enumerate((*_RETRY_BACKOFF_SECS, None)):
        try:
            return await run_in_threadpool(query_builder.execute)
        except (APIError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if not _is_transient(exc) or backoff is None:
                raise
            logger.warning(
                "supabase.execute transient failure (attempt %d): %s — retrying in %.0fms",
                attempt + 1,
                type(exc).__name__,
                backoff * 1000,
            )
            await asyncio.sleep(backoff)
    # Unreachable: the for-loop either returns or raises.
    assert last_exc is not None
    raise last_exc
