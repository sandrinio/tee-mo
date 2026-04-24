"""
Automation Service — CRUD and validation for scheduled AI automations (STORY-018-01).

Provides the core automation operations used by the REST layer (STORY-018-02),
the execution engine (STORY-018-03), and agent tools (STORY-018-04).

Automations are workspace-scoped scheduled tasks: a prompt runs on a schedule,
the result is delivered to one or more Slack channels.

Functions:
  validate_schedule:         Validate a schedule dict — raises ValueError on invalid shape.
  validate_channels:         Verify channel IDs are bound to the workspace — raises ValueError if not.
  create_automation:         Insert a new automation row; validates schedule + channels first.
  list_automations:          Return all automations for a workspace, ordered created_at DESC.
  get_automation:            Fetch one automation by workspace + id (workspace-scoped).
  update_automation:         Partial update; re-validates schedule/channels if those keys are patched.
  delete_automation:         Delete one automation; returns True if deleted, False if not found.
  get_automation_history:    Return the last 50 executions for an automation.
  prune_execution_history:   Delete executions beyond the newest cap rows; returns deleted count.

Security:
  - All queries include workspace_id filter (ADR-024 workspace isolation).
  - Channel validation queries teemo_workspace_channels for binding verification.

Tables:
  teemo_automations           — primary CRUD target (migration 012)
  teemo_automation_executions — execution history (migration 012)
  teemo_workspace_channels    — channel binding lookup (migration 006)

ADR compliance:
  ADR-015: All DB access via injected Supabase service-role client.
  ADR-020: Self-hosted Supabase; RLS disabled; app-layer workspace isolation.
  ADR-024: Workspace model; every query filters by workspace_id.

FLASHCARD compliance:
  - created_at, updated_at, next_run_at, last_run_at are NEVER in insert/update payloads.
    DB triggers and DEFAULT NOW() fill them automatically.
  - Use .in_() for multi-value channel lookups (PostgREST-safe).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Pattern for HH:MM time strings (24-hour clock, zero-padded).
_WHEN_PATTERN = re.compile(r"^\d{2}:\d{2}$")

#: Valid occurrence values for a schedule dict.
_VALID_OCCURRENCES = {"daily", "weekdays", "weekly", "monthly", "once"}


# ---------------------------------------------------------------------------
# Schedule validation helpers (dispatch table)
# ---------------------------------------------------------------------------


def _validate_daily(schedule: dict) -> None:
    """Validate a ``daily`` schedule: requires ``when`` matching HH:MM.

    Args:
        schedule: The schedule dict with ``occurrence == "daily"``.

    Raises:
        ValueError: If ``when`` is missing or does not match HH:MM format.
    """
    when = schedule.get("when")
    if not when or not _WHEN_PATTERN.match(when):
        raise ValueError(
            f"Schedule 'daily' requires 'when' in HH:MM format (got {when!r})"
        )


def _validate_weekdays(schedule: dict) -> None:
    """Validate a ``weekdays`` schedule: requires ``when`` matching HH:MM.

    Args:
        schedule: The schedule dict with ``occurrence == "weekdays"``.

    Raises:
        ValueError: If ``when`` is missing or does not match HH:MM format.
    """
    when = schedule.get("when")
    if not when or not _WHEN_PATTERN.match(when):
        raise ValueError(
            f"Schedule 'weekdays' requires 'when' in HH:MM format (got {when!r})"
        )


def _validate_weekly(schedule: dict) -> None:
    """Validate a ``weekly`` schedule: requires ``when`` + ``days`` (list of 0-6).

    Args:
        schedule: The schedule dict with ``occurrence == "weekly"``.

    Raises:
        ValueError: If ``when`` is missing/invalid, ``days`` is missing/not a list,
                    or any day value is outside 0-6.
    """
    when = schedule.get("when")
    if not when or not _WHEN_PATTERN.match(when):
        raise ValueError(
            f"Schedule 'weekly' requires 'when' in HH:MM format (got {when!r})"
        )
    days = schedule.get("days")
    if not isinstance(days, list) or not days:
        raise ValueError(
            f"Schedule 'weekly' requires 'days' as a non-empty list (got {days!r})"
        )
    for d in days:
        if not isinstance(d, int) or d < 0 or d > 6:
            raise ValueError(
                f"Schedule 'weekly' 'days' values must be integers 0-6 (got {d!r})"
            )


def _validate_monthly(schedule: dict) -> None:
    """Validate a ``monthly`` schedule: requires ``when`` + ``day_of_month`` (1-31).

    Args:
        schedule: The schedule dict with ``occurrence == "monthly"``.

    Raises:
        ValueError: If ``when`` is missing/invalid or ``day_of_month`` is not in 1-31.
    """
    when = schedule.get("when")
    if not when or not _WHEN_PATTERN.match(when):
        raise ValueError(
            f"Schedule 'monthly' requires 'when' in HH:MM format (got {when!r})"
        )
    day_of_month = schedule.get("day_of_month")
    if not isinstance(day_of_month, int) or day_of_month < 1 or day_of_month > 31:
        raise ValueError(
            f"Schedule 'monthly' requires 'day_of_month' as an integer 1-31 "
            f"(got {day_of_month!r})"
        )


def _validate_once(schedule: dict) -> None:
    """Validate a ``once`` schedule: requires ``at`` as a future ISO 8601 timestamp.

    The ``at`` value is parsed as a naive local datetime and compared to UTC now.
    If the parsed time is in the past, raises ValueError with "in the past" in the message.

    Args:
        schedule: The schedule dict with ``occurrence == "once"``.

    Raises:
        ValueError: If ``at`` is missing, unparseable, or refers to a past time.
    """
    at_str = schedule.get("at")
    if not at_str:
        raise ValueError("Schedule 'once' requires 'at' (ISO 8601 timestamp)")

    try:
        # Parse as naive or offset-aware datetime
        at_dt = datetime.fromisoformat(at_str)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Schedule 'once' 'at' must be a valid ISO 8601 timestamp (got {at_str!r})"
        ) from exc

    # Normalise to UTC-aware for comparison
    if at_dt.tzinfo is None:
        # Treat naive timestamps as UTC (consistent with DB behaviour)
        at_dt = at_dt.replace(tzinfo=timezone.utc)

    now_utc = datetime.now(timezone.utc)
    if at_dt <= now_utc:
        raise ValueError(
            f"Schedule 'once' 'at' timestamp {at_str!r} is in the past. "
            "Provide a future timestamp."
        )


#: Dispatch table: occurrence → validator function.
_OCCURRENCE_VALIDATORS: dict[str, Callable[[dict], None]] = {
    "daily": _validate_daily,
    "weekdays": _validate_weekdays,
    "weekly": _validate_weekly,
    "monthly": _validate_monthly,
    "once": _validate_once,
}


# ---------------------------------------------------------------------------
# Public validation functions
# ---------------------------------------------------------------------------


def validate_schedule(schedule: dict) -> None:
    """Validate an automation schedule dict.

    Checks that ``occurrence`` is one of the supported values and that all
    required sub-fields are present and well-formed.

    Valid occurrences and their required fields:
      - ``daily``    → ``when`` (HH:MM)
      - ``weekdays`` → ``when`` (HH:MM)
      - ``weekly``   → ``when`` (HH:MM) + ``days`` (list[0-6])
      - ``monthly``  → ``when`` (HH:MM) + ``day_of_month`` (1-31)
      - ``once``     → ``at`` (ISO 8601, future)

    Args:
        schedule: Dict representing the automation schedule.

    Raises:
        ValueError: If ``occurrence`` is unknown or any required field is invalid.
                    The message mentions "in the past" when a ``once`` schedule's
                    ``at`` timestamp is in the past.
    """
    occurrence = schedule.get("occurrence")
    if occurrence not in _OCCURRENCE_VALIDATORS:
        raise ValueError(
            f"Unknown schedule occurrence {occurrence!r}. "
            f"Must be one of: {sorted(_VALID_OCCURRENCES)}"
        )
    _OCCURRENCE_VALIDATORS[occurrence](schedule)


def validate_channels(
    workspace_id: str, slack_channel_ids: list[str], *, supabase: Any
) -> None:
    """Verify that all channel IDs are bound to the workspace.

    Queries ``teemo_workspace_channels`` to confirm each channel ID in
    ``slack_channel_ids`` is registered for the given workspace. Raises
    immediately if the list is empty (no DB call needed).

    Args:
        workspace_id:      UUID string of the workspace.
        slack_channel_ids: List of Slack channel IDs to validate.
        supabase:          Supabase service-role client.

    Raises:
        ValueError: If ``slack_channel_ids`` is empty, or if any channel ID
                    is not bound to the workspace in ``teemo_workspace_channels``.
    """
    if not slack_channel_ids:
        raise ValueError("slack_channel_ids must contain at least one channel ID")

    result = (
        supabase.table("teemo_workspace_channels")
        .select("slack_channel_id")
        .eq("workspace_id", workspace_id)
        .in_("slack_channel_id", slack_channel_ids)
        .execute()
    )

    # Verify that the returned rows actually cover all requested channel IDs.
    # The mock (and real PostgREST .in_() filter) returns only matching rows,
    # so we compare the returned slack_channel_id values against the request.
    found_ids = {row["slack_channel_id"] for row in (result.data or [])}
    missing = [ch for ch in slack_channel_ids if ch not in found_ids]
    if missing:
        raise ValueError(
            f"The following channel IDs are not bound to workspace {workspace_id}: "
            f"{missing}. Bind them first via the workspace channels API."
        )


# ---------------------------------------------------------------------------
# CRUD — Create
# ---------------------------------------------------------------------------


def create_automation(
    workspace_id: str,
    owner_user_id: str,
    payload: dict,
    *,
    supabase: Any,
) -> dict:
    """Insert a new automation row after validating schedule and channels.

    Validates the schedule and channels before performing the insert. The DB
    BEFORE INSERT trigger computes ``next_run_at`` automatically — do NOT
    include it in the payload.

    FLASHCARD: Never include ``created_at``, ``updated_at``, ``next_run_at``,
    or ``last_run_at`` in the insert payload — let DB defaults + triggers fill them.

    Args:
        workspace_id:  UUID string of the workspace.
        owner_user_id: UUID string of the user creating the automation.
        payload:       Dict with at minimum: ``name``, ``prompt``,
                       ``slack_channel_ids``, ``schedule``, ``timezone``.
                       Optional: ``description``, ``schedule_type``, ``is_active``.
        supabase:      Supabase service-role client.

    Returns:
        The inserted ``teemo_automations`` row as a dict.

    Raises:
        ValueError: If the schedule is invalid or any channel is unbound.
    """
    validate_schedule(payload["schedule"])
    validate_channels(workspace_id, payload["slack_channel_ids"], supabase=supabase)

    row = {
        "workspace_id": workspace_id,
        "owner_user_id": owner_user_id,
        "name": payload["name"],
        "prompt": payload["prompt"],
        "slack_channel_ids": payload["slack_channel_ids"],
        "schedule": payload["schedule"],
        "timezone": payload.get("timezone", "UTC"),
        "schedule_type": payload.get("schedule_type", "recurring"),
    }
    if "description" in payload:
        row["description"] = payload["description"]
    if "is_active" in payload:
        row["is_active"] = payload["is_active"]

    # next_run_at is intentionally omitted — the BEFORE INSERT trigger fills it.
    result = (
        supabase.table("teemo_automations")
        .insert(row)
        .execute()
    )

    logger.info(
        "[AUTOMATION_SERVICE] Created automation name=%r workspace=%s",
        payload.get("name"),
        workspace_id,
    )
    return result.data[0]


# ---------------------------------------------------------------------------
# CRUD — Read
# ---------------------------------------------------------------------------


def list_automations(workspace_id: str, *, supabase: Any) -> list[dict]:
    """Return all automations for a workspace, newest first.

    Results are ordered by ``created_at DESC`` so callers get the most
    recently created automation at index 0.

    Args:
        workspace_id: UUID string of the workspace.
        supabase:     Supabase service-role client.

    Returns:
        List of teemo_automations row dicts. Empty list if none exist.
    """
    result = (
        supabase.table("teemo_automations")
        .select("*")
        .eq("workspace_id", workspace_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_automation(
    workspace_id: str, automation_id: str, *, supabase: Any
) -> dict | None:
    """Fetch one automation by workspace + id (workspace-scoped).

    Both ``workspace_id`` and ``automation_id`` must match — this prevents
    cross-workspace leaks even if a caller provides a valid automation_id
    from another workspace.

    Args:
        workspace_id:  UUID string of the workspace (isolation filter).
        automation_id: UUID string of the automation to fetch.
        supabase:      Supabase service-role client.

    Returns:
        The automation row dict if found, or None if no matching row exists
        for the given workspace.
    """
    result = (
        supabase.table("teemo_automations")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("id", automation_id)
        .maybe_single()
        .execute()
    )
    # result.data is None (maybe_single no-match) or a dict (single row) or
    # an empty list (mock fallback) — normalise all falsy cases to None.
    data = result.data
    if not data:
        return None
    return data


# ---------------------------------------------------------------------------
# CRUD — Update
# ---------------------------------------------------------------------------


def update_automation(
    workspace_id: str,
    automation_id: str,
    patch: dict,
    *,
    supabase: Any,
) -> dict | None:
    """Partially update an automation's fields.

    Only keys present in ``patch`` are updated — unspecified fields are
    left unchanged. Re-validates ``schedule`` if the patch includes it.
    Re-validates ``slack_channel_ids`` if the patch includes them.

    Returns None if the automation does not exist in the workspace (no raise).

    FLASHCARD: Do not include ``created_at``, ``updated_at``, ``next_run_at``,
    or ``last_run_at`` in the patch — the DB trigger and defaults handle them.

    Args:
        workspace_id:  UUID string of the workspace (isolation filter).
        automation_id: UUID string of the automation to update.
        patch:         Dict of fields to update. Any subset of automation columns.
        supabase:      Supabase service-role client.

    Returns:
        Updated automation row dict, or None if not found.

    Raises:
        ValueError: If the patch contains an invalid schedule or unbound channels.
    """
    # Re-validate schedule if patched
    if "schedule" in patch:
        validate_schedule(patch["schedule"])

    # Re-validate channels if patched
    if "slack_channel_ids" in patch:
        validate_channels(workspace_id, patch["slack_channel_ids"], supabase=supabase)

    # Confirm the automation exists in this workspace (None or empty → not found)
    existing = get_automation(workspace_id, automation_id, supabase=supabase)
    if not existing:
        return None

    # Exclude server-managed columns from the patch payload (FLASHCARD rule)
    _server_managed = {"created_at", "updated_at", "next_run_at", "last_run_at", "id", "workspace_id"}
    clean_patch = {k: v for k, v in patch.items() if k not in _server_managed}

    result = (
        supabase.table("teemo_automations")
        .update(clean_patch)
        .eq("id", automation_id)
        .eq("workspace_id", workspace_id)
        .execute()
    )

    logger.info(
        "[AUTOMATION_SERVICE] Updated automation id=%s workspace=%s fields=%s",
        automation_id,
        workspace_id,
        list(clean_patch.keys()),
    )

    # result.data may be a list (real PostgREST) or a dict (mock single_result path).
    # Normalise: if it's a non-empty list, take first element; if it's a dict, return it;
    # otherwise fall back to the existing row we already fetched.
    data = result.data
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict) and data:
        return data
    return existing


# ---------------------------------------------------------------------------
# CRUD — Delete
# ---------------------------------------------------------------------------


def delete_automation(
    workspace_id: str, automation_id: str, *, supabase: Any
) -> bool:
    """Delete one automation by workspace + id.

    Execution history is removed via ON DELETE CASCADE on the FK.

    Args:
        workspace_id:  UUID string of the workspace (isolation filter).
        automation_id: UUID string of the automation to delete.
        supabase:      Supabase service-role client.

    Returns:
        True if a row was deleted; False if no matching row was found.
    """
    result = (
        supabase.table("teemo_automations")
        .delete()
        .eq("workspace_id", workspace_id)
        .eq("id", automation_id)
        .execute()
    )
    deleted = len(result.data) > 0

    if deleted:
        logger.info(
            "[AUTOMATION_SERVICE] Deleted automation id=%s workspace=%s",
            automation_id,
            workspace_id,
        )
    return deleted


# ---------------------------------------------------------------------------
# Execution History
# ---------------------------------------------------------------------------


def get_automation_history(
    workspace_id: str, automation_id: str, *, supabase: Any
) -> list[dict]:
    """Return the last 50 execution records for an automation.

    Results are ordered by ``started_at DESC`` (most recent first). The
    ``workspace_id`` parameter is accepted for API symmetry and future
    cross-workspace isolation checks, but the query is keyed on
    ``automation_id`` (which is globally unique as a UUID).

    Args:
        workspace_id:  UUID string of the workspace (for API symmetry).
        automation_id: UUID string of the automation.
        supabase:      Supabase service-role client.

    Returns:
        List of up to 50 teemo_automation_executions row dicts.
    """
    result = (
        supabase.table("teemo_automation_executions")
        .select("*")
        .eq("automation_id", automation_id)
        .order("started_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


def prune_execution_history(
    automation_id: str, *, supabase: Any, cap: int = 50
) -> int:
    """Delete execution rows beyond the newest ``cap`` rows for an automation.

    Selects execution IDs ordered by ``started_at DESC`` with OFFSET ``cap``
    — these are the oldest rows beyond the cap. If none are found, returns 0
    immediately (idempotent no-op).

    Args:
        automation_id: UUID string of the automation to prune.
        supabase:      Supabase service-role client.
        cap:           Maximum number of rows to retain (default 50).

    Returns:
        Number of rows deleted (0 if already within cap).
    """
    # Select IDs of excess rows (oldest, beyond the cap)
    excess_result = (
        supabase.table("teemo_automation_executions")
        .select("id")
        .eq("automation_id", automation_id)
        .order("started_at", desc=True)
        .offset(cap)
        .execute()
    )

    excess_rows = excess_result.data or []
    if not excess_rows:
        return 0

    excess_ids = [row["id"] for row in excess_rows]

    delete_result = (
        supabase.table("teemo_automation_executions")
        .delete()
        .in_("id", excess_ids)
        .execute()
    )

    deleted_count = len(excess_ids)
    logger.info(
        "[AUTOMATION_SERVICE] Pruned %d execution rows for automation id=%s",
        deleted_count,
        automation_id,
    )
    return deleted_count
