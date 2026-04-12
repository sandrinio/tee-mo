"""
Skill Service — CRUD operations for workspace agent skills (STORY-007-01).

Provides the core skill operations used by the orchestrator (L1 catalog injection,
skill loading) and future skill-authoring tools. Skills are instruction bundles
that carry workflow guidance fetched by the LLM on demand.

Functions:
  list_skills:             Return name + summary for all active skills in a workspace (L1 catalog).
  get_skill:               Fetch one full skill row by workspace + name (returns None if missing).
  create_skill:            Insert a new user-defined skill with field validation.
  update_skill:            Partial update of summary and/or instructions by workspace + name.
  delete_skill:            Delete a skill by workspace + name; raises ValueError if not found.
  _validate_skill_fields:  Shared field validator — raises ValueError with descriptive messages.

Security:
  - All queries include workspace_id filter — mandatory workspace isolation.
  - Validation rejects names that don't match the slug pattern.

Tables:
  teemo_skills — primary CRUD target (migration for S-07)

ADR compliance:
  - ADR-023: Skills are chat-only CRUD — no REST routes in this module.
  - All functions accept workspace_id for workspace isolation (R7).
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

#: Pattern for valid skill names: lowercase alphanumeric segments joined by single hyphens.
#: Allows: "daily-standup", "budget-report", "my-skill-v2"
#: Rejects: "UPPERCASE", "has spaces", "has_underscore", "trailing-", "-leading", "double--hyphen"
_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _validate_skill_fields(name: str, summary: str, instructions: str) -> None:
    """Validate skill fields before insert or update.

    Enforces field constraints from STORY-007-01:
      - name: matches ^[a-z0-9]+(-[a-z0-9]+)*$, length 1-60
      - summary: length 1-160
      - instructions: length 1-2000

    Args:
        name:         Skill slug identifier.
        summary:      Short "Use when..." description. Max 160 chars.
        instructions: Full workflow instructions. Max 2000 chars.

    Raises:
        ValueError: If any field fails validation, with a descriptive message.
    """
    # Empty name check first (regex won't match but empty gives a clearer message)
    if not name:
        raise ValueError(
            "Skill name cannot be empty. "
            "name must be a lowercase slug, e.g. 'daily-standup'."
        )

    # Validate name length (1-60)
    if len(name) > 60:
        raise ValueError(
            f"Skill name must be 1-60 characters (got {len(name)}). "
            "Shorten the name slug."
        )

    # Validate name pattern: lowercase alphanumeric with hyphens, no leading/trailing/double hyphens
    if not _NAME_PATTERN.match(name):
        raise ValueError(
            f"Skill name {name!r} is invalid. "
            "name must be lowercase alphanumeric with hyphens (e.g. 'daily-standup'). "
            "Pattern: ^[a-z0-9]+(-[a-z0-9]+)*$"
        )

    # Validate summary length (1-160)
    if not (1 <= len(summary) <= 160):
        raise ValueError(
            f"Summary must be 1-160 characters (got {len(summary)}). "
            "The summary should be a short 'Use when...' sentence."
        )

    # Validate instructions length (1-2000)
    if not (1 <= len(instructions) <= 2000):
        raise ValueError(
            f"Instructions must be 1-2000 characters (got {len(instructions)}). "
            "Break the instructions into concise numbered steps and rules."
        )


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------


def list_skills(workspace_id: str, supabase: Any) -> list[dict]:
    """Return the L1 skill catalog for a workspace: name and summary only.

    Only is_active=True skills are returned — inactive skills are excluded from
    the L1 catalog. Results are workspace-scoped for mandatory isolation.

    Selects only ``name, summary`` columns — instructions are NOT included in the
    catalog listing. Callers that need full instructions should use get_skill().

    Args:
        workspace_id: UUID string of the workspace to query.
        supabase:     Supabase service-role client.

    Returns:
        List of dicts with ``name`` and ``summary`` keys. Empty list if no active
        skills exist for the workspace.
    """
    result = (
        supabase.table("teemo_skills")
        .select("name, summary")
        .eq("workspace_id", workspace_id)
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def get_skill(workspace_id: str, name: str, supabase: Any) -> dict | None:
    """Fetch one skill by workspace and name, returning the full row.

    Used by the orchestrator's load_skill tool to retrieve full instructions
    for a named skill. Returns None when the skill does not exist so callers
    can produce user-friendly not-found messages.

    Args:
        workspace_id: UUID string of the workspace — isolation filter.
        name:         Exact slug name of the skill (e.g. "daily-standup").
        supabase:     Supabase service-role client.

    Returns:
        The full skill row dict if found, or None if no matching skill exists
        in the given workspace.
    """
    result = (
        supabase.table("teemo_skills")
        .select("*")
        .eq("workspace_id", workspace_id)
        .eq("name", name)
        .execute()
    )
    return result.data[0] if result.data else None


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_skill(
    workspace_id: str,
    name: str,
    summary: str,
    instructions: str,
    supabase: Any,
) -> dict:
    """Create a new user-defined skill in the workspace.

    Validates all fields via _validate_skill_fields before inserting. Catches
    unique constraint violations and converts them to ValueError with a friendly
    message the LLM can use to self-correct.

    Workspace isolation is enforced by including workspace_id in the insert payload.

    Args:
        workspace_id:  UUID string of the workspace.
        name:          Slug identifier — must match ^[a-z0-9]+(-[a-z0-9]+)*$, max 60 chars.
        summary:       Short "Use when..." description. Max 160 chars.
        instructions:  Full workflow instructions. Max 2000 chars.
        supabase:      Supabase service-role client.

    Returns:
        The inserted teemo_skills row as a dict (includes id, name, workspace_id, etc.).

    Raises:
        ValueError: If any field fails validation or the name already exists in the workspace.
    """
    _validate_skill_fields(name, summary, instructions)

    try:
        result = (
            supabase.table("teemo_skills")
            .insert(
                {
                    "workspace_id": workspace_id,
                    "name": name,
                    "summary": summary,
                    "instructions": instructions,
                    "is_active": True,
                }
            )
            .execute()
        )
    except Exception as exc:
        # Detect UNIQUE constraint violation (Supabase/PostgREST returns 409 or "duplicate key")
        exc_str = str(exc).lower()
        if "duplicate" in exc_str or "unique" in exc_str or "23505" in exc_str:
            raise ValueError(
                f"A skill named '{name}' already exists in this workspace. "
                "Choose a different name or update the existing skill."
            ) from exc
        raise

    if not result.data:
        raise ValueError(f"Failed to create skill '{name}': no data returned from insert")

    logger.info(
        "[SKILL_SERVICE] Created skill %r for workspace=%s",
        name,
        workspace_id,
    )
    return result.data[0]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_skill(
    workspace_id: str,
    name: str,
    supabase: Any,
    *,
    summary: str | None = None,
    instructions: str | None = None,
) -> dict:
    """Partially update a skill's summary and/or instructions by workspace + name.

    Fetches the current skill first to confirm it exists. Only provided fields
    (non-None) are included in the update payload — unspecified fields are left
    unchanged (partial update semantics).

    Args:
        workspace_id:  UUID string of the workspace — isolation filter.
        name:          Exact slug name of the skill to update.
        supabase:      Supabase service-role client.
        summary:       Optional new summary. Max 160 chars.
        instructions:  Optional new instructions. Max 2000 chars.

    Returns:
        The updated teemo_skills row as a dict.

    Raises:
        ValueError: If the skill does not exist in the workspace, or if the provided
                    summary/instructions fail length validation.
    """
    # Confirm skill exists before attempting update
    skill = get_skill(workspace_id, name, supabase=supabase)
    if skill is None:
        raise ValueError(f"Skill '{name}' not found in workspace {workspace_id}")

    # Build update payload from provided fields
    update_payload: dict[str, Any] = {}
    if summary is not None:
        if not (1 <= len(summary) <= 160):
            raise ValueError(f"Summary must be 1-160 characters (got {len(summary)})")
        update_payload["summary"] = summary
    if instructions is not None:
        if not (1 <= len(instructions) <= 2000):
            raise ValueError(
                f"Instructions must be 1-2000 characters (got {len(instructions)})"
            )
        update_payload["instructions"] = instructions

    if not update_payload:
        # Nothing to update — return current state unchanged
        return skill

    updated = (
        supabase.table("teemo_skills")
        .update(update_payload)
        .eq("workspace_id", workspace_id)
        .eq("name", name)
        .execute()
    )

    logger.info(
        "[SKILL_SERVICE] Updated skill %r for workspace=%s fields=%s",
        name,
        workspace_id,
        list(update_payload.keys()),
    )
    return updated.data[0] if updated.data else skill


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_skill(workspace_id: str, name: str, supabase: Any) -> None:
    """Delete a skill from the workspace by name.

    Checks for skill existence first and raises ValueError if not found, so
    callers receive a clear error rather than a silent no-op.

    Args:
        workspace_id: UUID string of the workspace — isolation filter.
        name:         Exact slug name of the skill to delete.
        supabase:     Supabase service-role client.

    Returns:
        None on success.

    Raises:
        ValueError: If no skill with the given name exists in the workspace.
    """
    skill = get_skill(workspace_id, name, supabase=supabase)
    if skill is None:
        raise ValueError(f"Skill '{name}' not found in workspace {workspace_id}")

    supabase.table("teemo_skills").delete().eq(
        "workspace_id", workspace_id
    ).eq("name", name).execute()

    logger.info(
        "[SKILL_SERVICE] Deleted skill %r for workspace=%s",
        name,
        workspace_id,
    )
