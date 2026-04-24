"""
Automation Executor — STORY-018-03.

Executes a single automation row: decrypts the BYOK key, runs the AI agent,
delivers the generated content to Slack channels, and finalises the execution
row in the database.

Entry points:
  execute_automation:      Execute one automation. Called by the cron loop or
                           a manual trigger. Returns a dict describing the outcome.
  reset_stale_executions:  Called once at startup to mark any 'running' rows that
                           were interrupted by a previous restart as 'failed'.

Module-level imports for patchability
--------------------------------------
The following symbols are imported at module level so that tests can patch them
via their dotted path inside this module (e.g. ``app.services.automation_executor.build_agent``).

  build_agent               — from app.agents.agent
  AsyncWebClient            — from slack_sdk.web.async_client
  prune_execution_history   — from app.services.automation_service

``decrypt`` is intentionally imported LAZILY inside ``execute_automation``
(not at module level) because ``app.core.encryption`` loads ``app.core.config``
which requires environment variables. Tests inject a fake ``app.core.encryption``
module into ``sys.modules`` before calling the function, so the lazy import
resolves to the mock without triggering a pydantic-settings env-var validation.
This is the same pattern used by ``wiki_ingest_cron._resolve_workspace_key``.

ADR compliance:
  ADR-015: All DB access via injected Supabase service-role client.
  ADR-020: Self-hosted Supabase; RLS disabled; app-layer workspace isolation.
  ADR-024: Workspace model; every query filters by workspace_id.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

try:
    from app.agents.agent import build_agent  # patched as: app.services.automation_executor.build_agent
except ImportError:  # pragma: no cover — pydantic_ai not installed in test environment
    build_agent = None  # type: ignore[assignment]  # always replaced by test patches

from slack_sdk.web.async_client import AsyncWebClient  # patched as: app.services.automation_executor.AsyncWebClient
from app.services.automation_service import prune_execution_history  # patched as: app.services.automation_executor.prune_execution_history

logger = logging.getLogger(__name__)


async def execute_automation(automation: dict, *, supabase) -> dict:
    """Execute a single scheduled automation end-to-end.

    Pipeline:
      1. Skip-if-active guard — return early if a 'running' execution already exists.
      2. INSERT an execution row with status='running'.
      3. Resolve the workspace BYOK key (decrypt lazily to avoid env-var load at import).
      4. Build the AI agent and run it with a 120-second timeout.
      5. Deliver the generated content to all configured Slack channels.
      6. UPDATE the execution row with final status, delivery results, and token usage.
      7. Advance next_run_at (or deactivate for schedule_type='once').
      8. Prune execution history to the most recent 50 rows.

    Args:
        automation: Row dict from ``teemo_automations`` containing at least:
                    id, workspace_id, owner_user_id, prompt, slack_channel_ids,
                    schedule, schedule_type.
        supabase:   Supabase service-role client (injected; never calls get_supabase here).

    Returns:
        dict — ``{"skipped": True, "automation_id": ...}`` if already running,
               otherwise ``{"status": "success"|"partial"|"failed", ...}``.
    """
    auto = automation
    t0 = time.monotonic()

    # ------------------------------------------------------------------
    # Step 1 — Skip-if-active guard
    # ------------------------------------------------------------------
    running = (
        supabase.table("teemo_automation_executions")
        .select("id")
        .eq("automation_id", auto["id"])
        .eq("status", "running")
        .execute()
    )
    if running.data:
        logger.info("executor.automation_skipped", extra={"automation_id": auto["id"]})
        return {"skipped": True, "automation_id": auto["id"]}

    # ------------------------------------------------------------------
    # Step 2 — INSERT execution row with status='running'
    # ------------------------------------------------------------------
    insert_result = (
        supabase.table("teemo_automation_executions")
        .insert({
            "automation_id": auto["id"],
            "status": "running",
            "was_dry_run": False,
        })
        .execute()
    )
    exec_id = insert_result.data[0]["id"]

    # ------------------------------------------------------------------
    # Step 3 — Resolve BYOK key (lazy import to avoid env-var load)
    # ------------------------------------------------------------------
    from app.core.encryption import decrypt  # noqa: PLC0415 — lazy: avoids .env load at module import time

    ws = (
        supabase.table("teemo_workspaces")
        .select("encrypted_api_key, slack_team_id")
        .eq("id", auto["workspace_id"])
        .maybe_single()
        .execute()
    )
    if not ws.data or not ws.data.get("encrypted_api_key"):
        supabase.table("teemo_automation_executions").update({
            "status": "failed",
            "error": "BYOK key not configured for this workspace",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", exec_id).execute()
        _advance_schedule(auto, supabase)
        return {"status": "failed", "automation_id": auto["id"], "error": "BYOK key not configured"}

    # ------------------------------------------------------------------
    # Step 4 — Build and run the AI agent (120-second timeout)
    # ------------------------------------------------------------------
    generated_content: str = ""
    tokens_used: int | None = None

    try:
        agent, deps = await build_agent(
            workspace_id=auto["workspace_id"],
            user_id=auto["owner_user_id"],
            supabase=supabase,
        )
        result = await asyncio.wait_for(agent.run(auto["prompt"], deps=deps), timeout=120.0)
        generated_content = result.output
        try:
            tokens_used = result.usage().total_tokens
        except Exception:  # noqa: BLE001
            tokens_used = None

    except asyncio.TimeoutError:
        supabase.table("teemo_automation_executions").update({
            "status": "failed",
            "error": "Agent timed out after 120s",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "execution_time_ms": int((time.monotonic() - t0) * 1000),
        }).eq("id", exec_id).execute()
        _advance_schedule(auto, supabase)
        return {"status": "failed", "automation_id": auto["id"], "error": "Agent timed out after 120s"}

    # ------------------------------------------------------------------
    # Step 5 — Deliver to Slack channels
    # ------------------------------------------------------------------
    slack_row = (
        supabase.table("teemo_slack_teams")
        .select("encrypted_slack_bot_token")
        .eq("slack_team_id", ws.data["slack_team_id"])
        .maybe_single()
        .execute()
    )
    if not slack_row.data or not slack_row.data.get("encrypted_slack_bot_token"):
        supabase.table("teemo_automation_executions").update({
            "status": "failed",
            "error": "Slack bot token not found for this workspace",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", exec_id).execute()
        _advance_schedule(auto, supabase)
        return {"status": "failed", "automation_id": auto["id"], "error": "Slack bot token not found for this workspace"}

    bot_token: str = decrypt(slack_row.data["encrypted_slack_bot_token"])

    delivery_results: list[dict] = []
    for channel_id in auto["slack_channel_ids"]:
        try:
            resp = await AsyncWebClient(token=bot_token).chat_postMessage(
                channel=channel_id,
                text=generated_content,
            )
            delivery_results.append({"channel_id": channel_id, "ok": True, "ts": resp["ts"]})
        except Exception as exc:  # noqa: BLE001
            delivery_results.append({"channel_id": channel_id, "ok": False, "error": str(exc)})

    # Compute final status based on delivery outcomes
    all_ok = all(r["ok"] for r in delivery_results)
    any_ok = any(r["ok"] for r in delivery_results)
    if all_ok:
        final_status = "success"
    elif any_ok:
        final_status = "partial"
    else:
        final_status = "failed"

    # ------------------------------------------------------------------
    # Step 6 — UPDATE execution row with final outcome
    # ------------------------------------------------------------------
    supabase.table("teemo_automation_executions").update({
        "status": final_status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "generated_content": generated_content,
        "delivery_results": delivery_results,
        "tokens_used": tokens_used,
        "execution_time_ms": int((time.monotonic() - t0) * 1000),
    }).eq("id", exec_id).execute()

    # ------------------------------------------------------------------
    # Step 7 — Advance schedule (or deactivate for 'once')
    # ------------------------------------------------------------------
    _advance_schedule(auto, supabase)

    # ------------------------------------------------------------------
    # Step 8 — Prune execution history (keep only the newest 50 rows)
    # ------------------------------------------------------------------
    prune_execution_history(auto["id"], supabase=supabase)

    return {
        "status": final_status,
        "automation_id": auto["id"],
        "execution_id": exec_id,
        "delivery_results": delivery_results,
        "tokens_used": tokens_used,
    }


def _advance_schedule(auto: dict, supabase) -> None:
    """Update teemo_automations with next_run_at (or deactivate for 'once' automations).

    For ``schedule_type='once'``: sets ``is_active=False``, ``next_run_at=None``,
    ``last_run_at=now``.

    For recurring schedules: calls the ``calculate_next_run_time`` Supabase RPC
    to compute the next execution instant, then updates ``last_run_at`` and
    ``next_run_at``.

    Args:
        auto:     Automation row dict (must contain ``id``, ``schedule_type``,
                  ``schedule``).
        supabase: Supabase service-role client.
    """
    now = datetime.now(timezone.utc)

    if auto["schedule_type"] == "once":
        supabase.table("teemo_automations").update({
            "is_active": False,
            "next_run_at": None,
            "last_run_at": now.isoformat(),
        }).eq("id", auto["id"]).execute()
    else:
        rpc_result = supabase.rpc(
            "calculate_next_run_time",
            {"schedule": auto["schedule"], "from_time": now.isoformat()},
        ).execute()
        next_run_at = rpc_result.data
        supabase.table("teemo_automations").update({
            "last_run_at": now.isoformat(),
            "next_run_at": next_run_at,
        }).eq("id", auto["id"]).execute()


async def reset_stale_executions(*, supabase) -> int:
    """Reset 'running' execution rows that were interrupted by a service restart.

    Called once at FastAPI startup (before the cron task is started).
    Any execution row with ``status='running'`` and ``started_at`` older than
    10 minutes is assumed to have been abandoned by a previous process and is
    marked ``status='failed'`` with an explanatory error message.

    Args:
        supabase: Supabase service-role client.

    Returns:
        Number of stale rows that were reset (0 if none found).
    """
    stale_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    result = (
        supabase.table("teemo_automation_executions")
        .update({
            "status": "failed",
            "error": "Service restarted during execution",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("status", "running")
        .lt("started_at", stale_cutoff)
        .execute()
    )
    count = len(result.data) if result.data else 0
    logger.info("executor.stale_reset", extra={"count": count})
    return count
