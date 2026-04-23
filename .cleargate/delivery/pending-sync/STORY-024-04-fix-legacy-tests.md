---
story_id: "STORY-024-04-fix-legacy-tests"
parent_epic_ref: "EPIC-024"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-024_concurrency_hardening/STORY-024-04-fix-legacy-tests.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-024-04: Fix Legacy Backend Test Tech Debt

**Complexity: L1** — Trivial fixes to 4 broken test files caused by legacy codebase drift.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> This story fixes 4 broken backend tests because legacy technical debt from previous epics left these mocks and assertions stale, blocking clear CI signal on `main`.

### 1.2 Detailed Requirements
- **Requirement 1**: Fix `backend/tests/test_config_google.py` by mocking the `google_picker_api_key` to strictly equal `""` in testing environments, overriding live `.env` interference.
- **Requirement 2**: Fix `backend/tests/test_drive_oauth.py` by asserting `drive.readonly` instead of `drive.file` in the scope verifications to match the actual router logic.
- **Requirement 3**: Fix `backend/tests/test_channel_binding.py` by patching `teemo_slack_teams` within its mock `get_supabase()` implementation to prevent it from returning a blank `MagicMock()` when called.
- **Requirement 4**: Fix `backend/tests/test_agent_factory.py` similarly due to the exact same `teemo_slack_teams` lookup boundary decrypt error.

### 1.3 Out of Scope
- Introducing new features.
- Changing `backend/app/api/routes` application code (strictly fixing test mocks).

### TDD Red Phase: No
> "Yes" = Team Lead enforces Red-Green multi-pass. "No" = single-pass Developer spawn.
> Default: Yes for stories with Gherkin scenarios in §2. No for pure config/doc/template changes.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Clean Test Suite

  Scenario: Run backend tests successfully
    Given the legacy test files are patched
    When the QA agent runs pytest on the backend suite
    Then all 4 previously failing tests pass without AssertionErrors or TypeErrors
```

### 2.2 Verification Steps (Manual)
- [ ] Execute `backend/.venv/bin/pytest backend/tests/test_config_google.py backend/tests/test_drive_oauth.py backend/tests/test_channel_binding.py backend/tests/test_agent_factory.py` and verify completely green status.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
> Verify these before starting. Do NOT waste a bounce cycle on setup failures.

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `None` | [ ] |
| **Services Running** | `None` | [ ] |
| **Dependencies** | Python `pytest` available in `.venv` | [ ] |

### 3.1 Test Implementation
- No new tests to be created. This story exclusively modifies the implementation of existing tests.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/tests/*.py` |
| **New Files Needed** | No |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- In `test_config_google.py`: Update `test_defaults_to_empty_string_when_not_set`. Currently asserts `settings.google_picker_api_key == ""`.
- In `test_drive_oauth.py`: Update `test_initiate_drive_connect_url_contains_drive_file_scope`. Change the string expected from `drive.file` to `drive.readonly` and rename the test to match.
- In `test_channel_binding.py`: Add an `elif name == "teemo_slack_teams":` block inside the `_table` mock function and provide `FAKE_SLACK_TEAM_ROW` as its return data.
- In `test_agent_factory.py`: Apply the exact same `teemo_slack_teams` patching fix to prevent `TypeError: argument should be a bytes-like object or ASCII string, not 'MagicMock'`.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | Testing the tests |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — N/A | |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] FLASHCARDS.md + Sprint Context consulted before implementation.
- [ ] No violations of Roadmap ADRs.
- [ ] Environment prerequisites (§3.0) verified before starting.

---

## Token Usage
> Auto-populated by agents. Each agent runs `node .vbounce/scripts/count_tokens.mjs --self --append <this-file> --name <Agent>` before writing their report.

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
