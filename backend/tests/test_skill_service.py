"""RED PHASE tests for STORY-007-01 — Skill Service (CRUD).

Covers all 7 Gherkin scenarios from STORY-007-01 §2.1:
  1. Create a valid skill
  2. Create skill with invalid name
  3. List skills returns L1 catalog
  4. Get skill by name
  5. Get skill not found
  6. Update skill partial
  7. Delete skill

Strategy:
- The module under test is ``app.services.skill_service`` (does NOT exist yet —
  all tests are expected to FAIL in Red Phase).
- Supabase client is fully mocked using MagicMock chains that replicate the
  supabase-py call pattern:
    client.table(name).select(...).eq(...).execute()
    client.table(name).insert(...).execute()
    client.table(name).update(...).eq(...).execute()
    client.table(name).delete().eq(...).execute()
- Table name expected by the service is ``teemo_skills``.
- No live DB calls are made.

ADR compliance:
- ADR-023: Skills are chat-only CRUD — no REST routes tested here.
- All functions accept workspace_id for workspace isolation (R7).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE_ID = str(uuid.uuid4())

SKILL_NAME = "daily-standup"
SKILL_SUMMARY = "Use when the user asks for a standup update"
SKILL_INSTRUCTIONS = "1. Greet the team\n2. Ask for updates\n3. Summarize blockers"

SKILL_ROW: dict[str, Any] = {
    "id": str(uuid.uuid4()),
    "workspace_id": WORKSPACE_ID,
    "name": SKILL_NAME,
    "summary": SKILL_SUMMARY,
    "instructions": SKILL_INSTRUCTIONS,
    "is_active": True,
}


# ---------------------------------------------------------------------------
# Helpers: build Supabase mock chains
# ---------------------------------------------------------------------------


def _make_execute_result(data: list[dict]) -> MagicMock:
    """Return a MagicMock whose .data attribute holds the given list.

    This mirrors the pattern in test_workspace_routes.py and other
    existing hermetic test files in this codebase.
    """
    result = MagicMock()
    result.data = data
    return result


def _make_supabase_mock(
    *,
    select_result: list[dict] | None = None,
    insert_result: list[dict] | None = None,
    update_result: list[dict] | None = None,
    delete_result: list[dict] | None = None,
) -> MagicMock:
    """Build a supabase-py mock whose .table('teemo_skills') chains succeed.

    Each chain returns results as configured by keyword arguments.
    Defaults to empty lists for all operations.

    The mock supports:
    - select chain: .select().eq().eq().execute()
    - insert chain: .insert(payload).execute()
    - update chain: .update(payload).eq().eq().execute()
    - delete chain: .delete().eq().eq().execute()
    """
    select_data = select_result if select_result is not None else []
    insert_data = insert_result if insert_result is not None else []
    update_data = update_result if update_result is not None else []
    delete_data = delete_result if delete_result is not None else []

    mock = MagicMock()

    def _table(name: str) -> MagicMock:
        tbl = MagicMock()

        # SELECT chain
        sel = MagicMock()
        sel.eq.return_value = sel
        sel.execute.return_value = _make_execute_result(select_data)
        tbl.select.return_value = sel

        # INSERT chain
        ins = MagicMock()
        ins.execute.return_value = _make_execute_result(insert_data)
        tbl.insert.return_value = ins

        # UPDATE chain
        upd = MagicMock()
        upd.eq.return_value = upd
        upd.execute.return_value = _make_execute_result(update_data)
        tbl.update.return_value = upd

        # DELETE chain
        dlt = MagicMock()
        dlt.eq.return_value = dlt
        dlt.execute.return_value = _make_execute_result(delete_data)
        tbl.delete.return_value = dlt

        return tbl

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Scenario 1: Create a valid skill
# ---------------------------------------------------------------------------


def test_create_valid_skill_returns_dict_with_id_and_is_active() -> None:
    """Gherkin: Create a valid skill.

    Given a workspace_id and valid skill data
      (name="budget-report", summary="Use when analyzing budgets",
       instructions="1. Load the budget file...")
    When create_skill() is called
    Then a new row exists in teemo_skills with the given data
    And the returned dict contains id, name, summary, instructions, is_active=True
    """
    from app.services.skill_service import create_skill  # type: ignore[import]

    created_row: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "workspace_id": WORKSPACE_ID,
        "name": "budget-report",
        "summary": "Use when analyzing budgets",
        "instructions": "1. Load the budget file...",
        "is_active": True,
    }
    supabase = _make_supabase_mock(insert_result=[created_row])

    result = create_skill(
        workspace_id=WORKSPACE_ID,
        name="budget-report",
        summary="Use when analyzing budgets",
        instructions="1. Load the budget file...",
        supabase=supabase,
    )

    assert isinstance(result, dict)
    assert result["id"] is not None
    assert result["name"] == "budget-report"
    assert result["summary"] == "Use when analyzing budgets"
    assert result["instructions"] == "1. Load the budget file..."
    assert result["is_active"] is True


# ---------------------------------------------------------------------------
# Scenario 2: Create skill with invalid name
# ---------------------------------------------------------------------------


def test_create_skill_with_invalid_name_raises_value_error() -> None:
    """Gherkin: Create skill with invalid name.

    Given name="INVALID Name!" (contains uppercase and special chars)
    When create_skill() is called
    Then ValueError is raised with a message about name format
    """
    from app.services.skill_service import create_skill  # type: ignore[import]

    supabase = _make_supabase_mock()

    with pytest.raises(ValueError, match="name"):
        create_skill(
            workspace_id=WORKSPACE_ID,
            name="INVALID Name!",
            summary="Some summary",
            instructions="Some instructions",
            supabase=supabase,
        )


@pytest.mark.parametrize(
    "bad_name",
    [
        "UPPERCASE",         # uppercase letters not allowed
        "has spaces",        # spaces not allowed
        "has_underscore",    # underscores not allowed — only hyphens
        "trailing-",         # trailing hyphen
        "-leading",          # leading hyphen
        "double--hyphen",    # consecutive hyphens
        "",                  # empty string
        "a" * 61,            # exceeds 60 chars
    ],
)
def test_create_skill_invalid_name_formats(bad_name: str) -> None:
    """All name patterns that must fail regex ``^[a-z0-9]+(-[a-z0-9]+)*$`` (1-60 chars)."""
    from app.services.skill_service import create_skill  # type: ignore[import]

    supabase = _make_supabase_mock()
    with pytest.raises(ValueError):
        create_skill(
            workspace_id=WORKSPACE_ID,
            name=bad_name,
            summary="Valid summary",
            instructions="Valid instructions",
            supabase=supabase,
        )


# ---------------------------------------------------------------------------
# Scenario 3: List skills returns L1 catalog
# ---------------------------------------------------------------------------


def test_list_skills_returns_l1_catalog_with_two_items() -> None:
    """Gherkin: List skills returns L1 catalog.

    Given 2 active skills exist for workspace W1
    When list_skills(W1) is called
    Then a list of 2 dicts is returned, each with name and summary (no instructions)
    """
    from app.services.skill_service import list_skills  # type: ignore[import]

    catalog_rows = [
        {"name": "daily-standup", "summary": "Use for standup meetings"},
        {"name": "budget-report", "summary": "Use when analyzing budgets"},
    ]
    supabase = _make_supabase_mock(select_result=catalog_rows)

    results = list_skills(workspace_id=WORKSPACE_ID, supabase=supabase)

    assert isinstance(results, list)
    assert len(results) == 2
    # Each dict must have name and summary
    for item in results:
        assert "name" in item
        assert "summary" in item
    # Instructions should NOT be present in L1 catalog
    for item in results:
        assert "instructions" not in item


# ---------------------------------------------------------------------------
# Scenario 4: Get skill by name
# ---------------------------------------------------------------------------


def test_get_skill_by_name_returns_full_dict_with_instructions() -> None:
    """Gherkin: Get skill by name.

    Given a skill "daily-standup" exists in workspace W1
    When get_skill(W1, "daily-standup") is called
    Then the full skill dict is returned including instructions
    """
    from app.services.skill_service import get_skill  # type: ignore[import]

    supabase = _make_supabase_mock(select_result=[SKILL_ROW])

    result = get_skill(
        workspace_id=WORKSPACE_ID,
        name=SKILL_NAME,
        supabase=supabase,
    )

    assert result is not None
    assert isinstance(result, dict)
    assert result["name"] == SKILL_NAME
    assert result["instructions"] == SKILL_INSTRUCTIONS
    assert result["summary"] == SKILL_SUMMARY


# ---------------------------------------------------------------------------
# Scenario 5: Get skill not found
# ---------------------------------------------------------------------------


def test_get_skill_not_found_returns_none() -> None:
    """Gherkin: Get skill not found.

    Given no skill "nonexistent" in workspace W1
    When get_skill(W1, "nonexistent") is called
    Then None is returned
    """
    from app.services.skill_service import get_skill  # type: ignore[import]

    supabase = _make_supabase_mock(select_result=[])  # empty — not found

    result = get_skill(
        workspace_id=WORKSPACE_ID,
        name="nonexistent",
        supabase=supabase,
    )

    assert result is None


# ---------------------------------------------------------------------------
# Scenario 6: Update skill partial
# ---------------------------------------------------------------------------


def test_update_skill_partial_changes_summary_keeps_instructions() -> None:
    """Gherkin: Update skill partial.

    Given a skill "daily-standup" exists
    When update_skill(W1, "daily-standup", summary="New summary") is called
    Then summary is updated, instructions unchanged
    """
    from app.services.skill_service import update_skill  # type: ignore[import]

    updated_row: dict[str, Any] = {
        **SKILL_ROW,
        "summary": "New summary",
        # instructions remain unchanged
        "instructions": SKILL_INSTRUCTIONS,
    }
    # First call (existence check or get) returns the original row;
    # second call (after update) returns the updated row.
    supabase = _make_supabase_mock(
        select_result=[SKILL_ROW],
        update_result=[updated_row],
    )

    result = update_skill(
        workspace_id=WORKSPACE_ID,
        name=SKILL_NAME,
        supabase=supabase,
        summary="New summary",
    )

    assert isinstance(result, dict)
    assert result["summary"] == "New summary"
    assert result["instructions"] == SKILL_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Scenario 7: Delete skill
# ---------------------------------------------------------------------------


def test_delete_skill_removes_row() -> None:
    """Gherkin: Delete skill.

    Given a skill "daily-standup" exists
    When delete_skill(W1, "daily-standup") is called
    Then the row is removed from teemo_skills (no error raised, returns None)
    """
    from app.services.skill_service import delete_skill  # type: ignore[import]

    # Select returns a row (skill exists), delete chain succeeds
    supabase = _make_supabase_mock(
        select_result=[SKILL_ROW],
        delete_result=[SKILL_ROW],
    )

    result = delete_skill(
        workspace_id=WORKSPACE_ID,
        name=SKILL_NAME,
        supabase=supabase,
    )

    # delete_skill returns None on success
    assert result is None
    # Verify the delete was attempted on the supabase mock
    # (the mock's .table was called at least once)
    supabase.table.assert_called()
