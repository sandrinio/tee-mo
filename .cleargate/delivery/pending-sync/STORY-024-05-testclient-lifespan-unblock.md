---
story_id: "STORY-024-05-testclient-lifespan-unblock"
parent_epic_ref: "EPIC-024"
status: "Draft"
ambiguity: "🟢"
context_source: "EPIC-024-concurrency-hardening.md"
actor: "Backend developer running the pytest suite"
complexity_label: "L2"
created_at: "2026-04-24T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "cleargate-post-sprint-13"
updated_at_version: "cleargate-post-sprint-13"
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

# STORY-024-05: Unblock 4 excluded test modules — drop `TestClient(app) as client:` lifespan trigger
**Complexity:** L2 — 4 known test files, one proven pattern, ~1-2hr. Proven in SPRINT-13 via `test_workspaces_team_member_access.py`.

## 1. The Spec (The Contract)

### 1.1 User Story
As a **backend developer**, I want the full `backend/tests/` suite to run under pytest-asyncio auto mode without hanging, so that CI gives a clear red/green signal and I stop having to remember which 4 modules to skip when reasoning about coverage.

### 1.2 Detailed Requirements
- **R1.** Convert every `with TestClient(app) as client:` occurrence in the four currently-hanging modules to `client = TestClient(app, raise_server_exceptions=False)` — matching the pattern proven in `backend/tests/test_workspaces_team_member_access.py:317` and `backend/tests/test_auth_routes.py:72`.
- **R2.** Affected files (exhaustive — surfaced via grep in SPRINT-13 report §"What's unblocked"):
  - `backend/tests/test_workspace_routes.py` (2 occurrences — lines ~114 and ~895)
  - `backend/tests/test_channel_binding.py` (2 occurrences — lines ~115 and ~133)
  - `backend/tests/test_channel_enrichment.py` (1 occurrence — line ~112)
  - `backend/tests/test_automations_routes.py` (2 occurrences — lines ~250 and ~271)
- **R3.** All tests in the four modules continue to pass after the refactor — no assertion changes, no mock changes, no fixture changes. Only the `TestClient` construction style changes.
- **R4.** Record a flashcard (formalize the SPRINT-13 "candidate" note):
  > `#test-harness #fastapi #lifespan · TestClient(app) as client: deadlocks under pytest-asyncio auto mode — FastAPI lifespan spawns 3 cron loops (drive, wiki, automation) that never return. Use TestClient(app, raise_server_exceptions=False) without the context manager for mock-heavy tests.`
- **R5.** Add one sentence near the top docstring of each edited module explaining the pattern (so future copy-paste from these modules carries the lesson, not the bug).

### 1.3 Out of Scope
- Refactoring `main.py` lifespan to gate cron loops on an env var (e.g. `DISABLE_CRONS_IN_TESTS=1`). That's the "root-cause" fix and is a larger blast-radius change — filed as a follow-up idea, not this story.
- Moving any of these modules to integration-test tier or live-Supabase mode.
- Tightening CI config to enforce the pattern (pre-commit hook / ruff rule). Leave to a future conventions pass.

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: 4 excluded backend test modules run cleanly under pytest-asyncio auto mode

  Scenario: Full suite completes without hanging
    Given a fresh checkout with default pytest-asyncio config
    When I run: backend/.venv/bin/pytest backend/tests/test_workspace_routes.py backend/tests/test_channel_binding.py backend/tests/test_channel_enrichment.py backend/tests/test_automations_routes.py
    Then the run completes in under 60 seconds
    And exit code is 0
    And no test is SKIPPED due to lifespan hang

  Scenario: No behavioral regression in the four modules
    Given the pre-refactor test counts per module (captured before the change)
    When the refactor lands
    Then each module reports the same number of passing tests as before (zero regressions)
    And no previously-passing test now fails

  Scenario: Full backend suite runs cleanly
    Given the four modules are restored to the default pytest collection path
    When I run: backend/.venv/bin/pytest backend/tests/
    Then the suite completes without hanging
    And exit code reflects genuine test signal (0 or >0 but deterministic)
```

### 2.2 Verification Steps (Manual)
- [ ] On the story branch, capture pre-refactor pass count per module via `pytest <file> --collect-only -q | wc -l`.
- [ ] Run `backend/.venv/bin/pytest backend/tests/test_workspace_routes.py backend/tests/test_channel_binding.py backend/tests/test_channel_enrichment.py backend/tests/test_automations_routes.py` — confirm <60s, exit 0.
- [ ] Run the full suite `backend/.venv/bin/pytest backend/tests/` — confirm no hang.
- [ ] Verify post-refactor pass count matches pre-refactor per module.

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary Files | `backend/tests/test_workspace_routes.py`, `backend/tests/test_channel_binding.py`, `backend/tests/test_channel_enrichment.py`, `backend/tests/test_automations_routes.py` |
| Reference Pattern | `backend/tests/test_workspaces_team_member_access.py:317` (canonical), `backend/tests/test_auth_routes.py:72` |
| Flashcard Log | `.cleargate/FLASHCARD.md` |
| New Files Needed | No |

### 3.2 Technical Logic
The FastAPI lifespan hook at `backend/app/main.py:61-110` starts three long-running cron tasks via `asyncio.create_task(...)`:
- `drive_sync_loop()` (line 84)
- `wiki_ingest_loop()` (line 88)
- `automation_cron_loop()` (line 102)

`TestClient(app)` as a context manager invokes the lifespan (startup + shutdown). Under pytest-asyncio auto mode, the event loop used for the test is the same loop scheduling these tasks — they never make real DB progress (mocks/offline) and the test never releases the loop, producing a deadlock on teardown.

Bypassing the lifespan for mock-heavy tests is the right call: these are unit tests against mocked Supabase clients; they do not need the cron loops to be alive. Use:

```python
# Use TestClient WITHOUT the context manager — avoids triggering the FastAPI
# lifespan. The cron loops (drive, wiki, automation) spawned on startup hang
# the event loop under pytest-asyncio auto mode.
client = TestClient(app, raise_server_exceptions=False)
```

Any `finally: app.dependency_overrides.clear()` or similar teardown previously tucked inside the `with` block should move into a fixture teardown (or an explicit `try/finally`) — grep for this during the refactor.

### 3.3 API Contract
No runtime contract change. Test-only.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| New tests | 0 | This is a test-infra refactor. Pre-existing tests are the signal. |
| Regression | All pre-existing tests in the 4 modules must still pass | Zero tolerance for drift |

### 4.2 Definition of Done (The Gate)
- [ ] All `with TestClient(app) as client:` occurrences in the four modules converted to the non-context-manager pattern.
- [ ] Full `pytest backend/tests/` run completes in reasonable time (no lifespan hang) and exits cleanly.
- [ ] Pre vs. post pass counts match per module.
- [ ] Flashcard recorded in `.cleargate/FLASHCARD.md` per R4.
- [ ] Module docstrings updated per R5.
- [ ] Peer / Architect review passed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low Ambiguity** — exact files, exact pattern, proven in SPRINT-13. Root-cause fix deferred out-of-scope on purpose.
