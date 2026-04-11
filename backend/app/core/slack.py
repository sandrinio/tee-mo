"""Slack Bolt AsyncApp singleton — single import point for slack_bolt.

Downstream stories must import from here, never directly from slack_bolt.
This enforces ADR-010's single-import-point rule: if the Slack Bolt version
or construction parameters ever change, only this file needs updating.

Exports:
    - get_slack_app() -> AsyncApp

Usage::

    from app.core.slack import get_slack_app

    app = get_slack_app()
"""
from functools import lru_cache

from slack_bolt.async_app import AsyncApp

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_slack_app() -> AsyncApp:
    """Return the shared AsyncApp instance (constructed once per process).

    Mirrors the ``get_supabase()`` singleton pattern in ``app.core.db``:
    ``@lru_cache(maxsize=1)`` guarantees that the same ``AsyncApp`` object is
    returned on every call within a process lifetime, avoiding repeated
    re-initialisation of the Slack client.

    The app is constructed with ``token=None`` and
    ``token_verification_enabled=False`` because Tee-Mo is a multi-workspace
    OAuth app — there is no single default bot token. Each workspace's token
    is loaded from the encrypted ``teemo_slack_teams`` table at event-handling
    time (ADR-010).

    Tests flush this cache with ``get_slack_app.cache_clear()`` to get a fresh
    instance with monkeypatched env vars (same pattern as ``get_settings``).

    Returns
    -------
    AsyncApp
        The cached Slack Bolt async application instance.
    """
    s = get_settings()
    return AsyncApp(
        token=None,
        signing_secret=s.slack_signing_secret,
        request_verification_enabled=True,
    )
