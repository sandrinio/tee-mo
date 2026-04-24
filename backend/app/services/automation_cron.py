"""
Automation Cron Loop — STORY-018-03.

Background asyncio task that runs every 60 seconds and picks up all automations
whose ``next_run_at`` is due (via the ``get_due_automations`` Supabase RPC) and
executes them via ``execute_automation``.

Loop behaviour per tick:
  1. Call ``get_supabase()`` to get a fresh client for the cycle.
  2. Call RPC ``get_due_automations`` — returns all teemo_automations rows whose
     ``next_run_at <= NOW()`` and ``is_active = TRUE``.
  3. For each due automation: call ``execute_automation(auto, supabase=supabase)``.
     - If the result has ``{"skipped": True}``, count it as skipped (already running).
     - Any unexpected exception is caught, logged, and skipped — does NOT crash the loop.
  4. Emit a summary log line with executed / skipped / failed counts.
  5. ``await asyncio.sleep(60)`` — NOTE: uses ``asyncio.sleep`` not a local alias so
     that tests can patch ``asyncio.sleep`` at the global level without needing a
     module-attribute patch.

Error handling:
  - Per-automation exceptions are caught and counted as ``failed`` — one failing
    automation never prevents others from running.
  - ``asyncio.CancelledError`` is NOT caught inside the per-automation loop — it
    propagates out to the outer ``except asyncio.CancelledError`` block so the
    task can be cleanly shut down via the FastAPI lifespan context manager.
  - Unexpected top-level errors (e.g. failed RPC) are caught, logged, and the
    loop continues after the next sleep.

Module-level imports for patchability
--------------------------------------
The following symbols are imported at module level so that tests can patch them
via their dotted path inside this module:

  get_supabase        — patched as: app.services.automation_cron.get_supabase
  execute_automation  — patched as: app.services.automation_cron.execute_automation
  asyncio             — ``asyncio.sleep`` is patched at the global asyncio level

IMPORTANT: Do NOT use ``from asyncio import sleep``.  Tests patch ``asyncio.sleep``
globally. The cron loop MUST call ``await asyncio.sleep(60)`` so the patch resolves.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.db import get_supabase
from app.services.automation_executor import execute_automation

logger = logging.getLogger(__name__)


async def automation_cron_loop() -> None:
    """Infinite 60-second loop — picks up due automations and executes them.

    Registered as an asyncio background task during FastAPI lifespan startup
    (via ``asyncio.create_task(automation_cron_loop())``).

    The loop exits only when cancelled (``asyncio.CancelledError`` is re-raised
    after logging the shutdown event). Any other exception at the top level is
    logged and the loop continues after the next sleep.
    """
    logger.info("cron.automation.init")
    while True:
        try:
            supabase = get_supabase()
            result = supabase.rpc("get_due_automations").execute()
            due: list[dict] = result.data or []

            executed, skipped, failed = 0, 0, 0
            for auto in due:
                try:
                    outcome = await execute_automation(auto, supabase=supabase)
                    if outcome.get("skipped"):
                        skipped += 1
                    else:
                        executed += 1
                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    logger.error(
                        "cron.automation.error",
                        extra={"automation_id": auto.get("id"), "error": str(exc)},
                    )

            logger.info(
                "cron.automation.complete",
                extra={"executed": executed, "skipped": skipped, "failed": failed},
            )
            await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("cron.automation.shutdown")
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "cron.automation.loop_error",
                extra={"error": str(exc)},
            )
