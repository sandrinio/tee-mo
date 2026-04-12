---
story_id: "STORY-007-01-skill-service"
parent_epic_ref: "EPIC-007"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §4.5 / Charter §3.3 / new_app skill_service.py"
actor: "Agent (internal consumer)"
complexity_label: "L1"
---

# STORY-007-01: Skill Service (CRUD)

**Complexity: L1** — Single file, known copy+strip pattern from new_app.

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story creates `backend/app/services/skill_service.py` — the pure data-access layer for workspace skills. The agent's skill tools (STORY-007-02) will call these functions. No REST API — skills are chat-only CRUD per ADR-023.

### 1.2 Detailed Requirements
- **R1**: `list_skills(workspace_id, supabase) -> list[dict]` — returns all active skills for a workspace (name, summary only — the L1 catalog).
- **R2**: `get_skill(workspace_id, name, supabase) -> dict | None` — returns full skill (including instructions) by name. Returns None if not found.
- **R3**: `create_skill(workspace_id, name, summary, instructions, supabase) -> dict` — inserts a new skill. Validates name format (`^[a-z0-9]+(-[a-z0-9]+)*$`, 1-60 chars), summary (1-160 chars), instructions (1-2000 chars). Raises `ValueError` on validation failure.
- **R4**: `update_skill(workspace_id, name, supabase, *, summary=None, instructions=None) -> dict` — partial update by name. Only updates fields that are not None. Raises `ValueError` if skill not found.
- **R5**: `delete_skill(workspace_id, name, supabase) -> None` — deletes by name. Raises `ValueError` if not found.
- **R6**: Name validation is enforced in the service layer (the DB has a CHECK constraint too, but service-layer validation gives better error messages for the agent).
- **R7**: All functions use `workspace_id` for isolation — never query across workspaces.

### 1.3 Out of Scope
- REST endpoints for skills (ADR-023: chat-only CRUD)
- `related_tools` field (stripped per Charter §3.3)
- `is_system` field and `seed_system_skills()` (stripped per Charter §3.3)
- `SYSTEM_SKILLS` constant (stripped — Tee-Mo starts with zero skills)
- `TOOL_CATALOG` validation (stripped — Tee-Mo has only `read_drive_file`)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Skill Service CRUD

  Scenario: Create a valid skill
    Given a workspace_id and valid skill data (name="budget-report", summary="Use when...", instructions="1. Do X...")
    When create_skill() is called
    Then a new row exists in teemo_skills with the given data
    And the returned dict contains id, name, summary, instructions, is_active=true

  Scenario: Create skill with invalid name
    Given name="INVALID Name!"
    When create_skill() is called
    Then ValueError is raised with a message about name format

  Scenario: List skills returns L1 catalog
    Given 2 active skills exist for workspace W1
    When list_skills(W1) is called
    Then a list of 2 dicts is returned, each with name and summary (no instructions)

  Scenario: Get skill by name
    Given a skill "daily-standup" exists in workspace W1
    When get_skill(W1, "daily-standup") is called
    Then the full skill dict is returned including instructions

  Scenario: Get skill not found
    Given no skill "nonexistent" in workspace W1
    When get_skill(W1, "nonexistent") is called
    Then None is returned

  Scenario: Update skill partial
    Given a skill "daily-standup" exists
    When update_skill(W1, "daily-standup", summary="New summary") is called
    Then summary is updated, instructions unchanged

  Scenario: Delete skill
    Given a skill "daily-standup" exists
    When delete_skill(W1, "daily-standup") is called
    Then the row is removed from teemo_skills
```

### 2.2 Verification Steps (Manual)
- [ ] All 7 tests pass with `pytest backend/tests/test_skill_service.py -v`
- [ ] Full backend suite still passes (99+ tests)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | Standard `.env` (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, etc.) | [ ] |
| **Migration** | `004_teemo_skills.sql` already applied | [ ] |
| **Dependencies** | No new deps | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_skill_service.py`
- 7 tests matching the 7 Gherkin scenarios above
- Mock Supabase client (same pattern as existing tests — no live DB calls)
- Test validation edge cases: empty name, name with uppercase, summary > 160 chars, instructions > 2000 chars

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/skill_service.py` (new) |
| **Related Files** | `backend/app/services/__init__.py` (exists) |
| **New Files Needed** | Yes — `skill_service.py`, `tests/test_skill_service.py` |
| **ADR References** | ADR-023 (Skills Architecture) |
| **First-Use Pattern** | No — follows existing service patterns (key_validator.py, provider_resolver.py) |
| **Copy Source** | `Documents/Dev/new_app/backend/app/services/skill_service.py` |

### 3.3 Technical Logic
1. Copy `new_app/backend/app/services/skill_service.py`.
2. Strip: `SYSTEM_SKILLS`, `seed_system_skills()`, `related_tools` param from `create_skill`/`update_skill`, `TOOL_CATALOG` validation, `is_system` checks.
3. Keep: `list_skills`, `get_skill`, `create_skill`, `update_skill`, `delete_skill`, `_validate_skill_fields`.
4. Adapt table name: `chy_agent_skills` -> `teemo_skills`.
5. `list_skills` selects `name, summary` only (L1 catalog — instructions are loaded on-demand via `get_skill`).
6. All functions take `workspace_id` + `supabase` as args (no dependency injection — pure functions).
7. Validation function `_validate_skill_fields(name, summary, instructions)` raises `ValueError` with specific message.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 7 | 1 per Gherkin scenario |
| Integration tests | 0 | N/A — mocked Supabase |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] 7+ tests passing.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 74 | 581 | 655 |
| Developer | 17 | 982 | 999 |
