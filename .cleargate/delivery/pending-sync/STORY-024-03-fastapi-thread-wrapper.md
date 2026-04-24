---
story_id: "STORY-024-03"
parent_epic_ref: "EPIC-024"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L3"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-024_concurrency_hardening/STORY-024-03-fastapi-thread-wrapper.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-024-03-fastapi-thread-wrapper: FastAPI ThreadPool Wrapper

**Complexity: L3** — Widespread modification across FastAPI routes to ensure synchronicity in `supabase-py` does not block the async event loop constraint.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> This story resolves the critical bottleneck where asynchronous FastAPI routes block identically to synchronous ones because the Supabase DB client (`supabase-py`) inherently stops the thread under the hood until the DB query completes. 

### 1.2 Detailed Requirements
- **Requirement 1**: Create a utility driver function inside `backend/app/core/db.py` (e.g. `execute_async`).
- **Requirement 2**: This function must accept a Supabase query builder and execute it inside `starlette.concurrency.run_in_threadpool`.
- **Requirement 3**: Comb through `backend/app/api/routes/*.py` and replace `.execute()` with `await execute_async(...)`.
- **Requirement 4**: Ensure this migration perfectly replaces the synchronous call and does not break existing exceptions or object return structures. 

### 1.3 Out of Scope
- Replacing `supabase-py` with `asyncpg` or any other raw native async client. 
- Modifying non-route blocks (like the startup cron loops) since they run sequentially by design in backgrounds.

### TDD Red Phase: No
> Default: No for widespread syntactic migrations like wrapping APIs. Ensure integration tests pass cleanly instead.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: FastAPI Event Loop Decoupling

  Scenario: Route Thread Offloading
    Given 50 users ping `GET /api/workspaces/...` simultaneously
    When FastAPI receives the HTTP request
    Then It delegates the Supabase DB I/O out of the main asyncio loop
    And Latency and Request Timeouts do not stack linearly
```

### 2.2 Verification Steps (Manual)
- [ ] Execute `pytest` across all backend API test cases ensuring 0 regressions in route expectations since wrapping `.execute()` shouldn't impact returned structures.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Services Running** | API + Postgres locally | [ ] |

### 3.1 Test Implementation
- No explicit new endpoints are added, so this is verified via existing comprehensive tests covering `app/api/routes/`. 
- Ensure `tests/backend/core/test_db.py` covers the new `execute_async` wrapper correctly verifying it uses `run_in_threadpool`.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/core/db.py` |
| **Related Files** | `backend/app/api/routes/workspaces.py`, `backend/app/api/routes/auth.py`, `backend/app/api/routes/*.py` |
| **First-Use Pattern** | Yes — Thread pool offloading |

### 3.3 Technical Logic
- In `core/db.py`, import `from starlette.concurrency import run_in_threadpool`.
- Define wrapper:
```python
from starlette.concurrency import run_in_threadpool
from typing import Any

async def execute_async(query_builder: Any) -> Any:
    return await run_in_threadpool(query_builder.execute)
```
- In routes, change `sb.table("...").select("*").execute()` to `await execute_async(sb.table("...").select("*"))`.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Integration tests | 0 - N/A | Rely on existing test coverages for APIs |
| Unit tests | 1 | Test the `execute_async` independently |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] Global regression `pytest` pass.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
