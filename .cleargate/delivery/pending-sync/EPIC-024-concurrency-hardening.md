---
epic_id: "EPIC-024"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "DevOps & Backend Lead"
target_date: "TBD"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-024_concurrency_hardening/EPIC-024_concurrency_hardening.md`. Carried forward during ClearGate migration 2026-04-24.

# EPIC-024: Concurrency Hardening (50-80 User Scale)

## 1. Problem & Value

### 1.1 The Problem
The current backend architecture contains critical concurrency bottlenecks preventing it from safely scaling to the target 50-80 concurrent users.
1. Database queries inside FastAPI routes strictly block the event loop due to the synchronous `supabase-py` client.
2. Background tasks (Cron workers) pull entire payloads into memory un-paginated and inherently race each other when deployed horizontally across multiple Uvicorn instances.

### 1.2 The Solution
We will eliminate the event loop blocking by wrapping HTTP-based synchronous Supabase operations into ThreadPool workers natively supported by Starlette. For the background crons, we will introduce a zero-infrastructure distributed lock using a Postgres RPC with `UPDATE ... RETURNING ... SKIP LOCKED` batching, preventing duplicate LLM billing and race conditions.

### 1.3 Success Metrics (North Star)
- Zero duplicated API calls/processing runs during background sync tasks under horizontal scale.
- Route latency under load (< 250ms p95 response time with 80 concurrent users).
- Complete elimination of memory exhaustion via cron batch pagination.

---

## 2. Scope Boundaries

### ✅ IN-SCOPE (Build This)
- [ ] Refactor all `execute()` calls in FastAPI routes to process inside `run_in_threadpool`.
- [ ] Create a Supabase DB migration for the `claim_pending_documents` RPC function.
- [ ] Update `wiki_ingest_cron.py` and `drive_sync_cron.py` to use `.rpc()` for fetching batched, exclusively locked documents.
- [ ] Implement `try/catch` handlers inside the crons to reset failed documents back to `pending` or `error` from the new `processing` state.

### ❌ OUT-OF-SCOPE (Do NOT Build This)
- Transitioning to a completely different async driver (e.g. `asyncpg`) or SQLAlchemy (keep it simple, stick to Supabase REST client).
- Implementing new infrastructure (e.g., Redis, Celery, or ARQ) for cron extraction.

---

## 3. Context

### 3.1 Constraints
| Type | Constraint |
|------|------------|
| **Performance** | Must be able to process 50 Uvicorn requests simultaneously without threading deadlocks. |
| **Complexity** | Zero new infrastructure dependencies. Must run on the existing Supabase server. |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| DB | `backend/supabase/migrations/...` | New RPC migration |
| Routes | `backend/app/api/routes/*.py` | Modify wrapper implementation |
| Crons | `backend/app/services/*_cron.py` | Refactor to `.rpc()` |
| DB Core | `backend/app/core/db.py` | Add threadpool helper |

### 4.4 Data Changes
| Entity | Change | Fields |
|--------|--------|--------|
| `sync_status` | NEW ENUM VALUE | `processing` added to pending/synced/error |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Concurrency Scaling to 80 Users

  Scenario: Multiple background workers do not overlap
    Given there are 20 documents marked "pending"
    When 4 background worker processes run simultaneously
    Then each document is processed exactly once
    And only 1 LLM request per document is recorded

  Scenario: FastAPI Event loop remains unblocked
    Given a Uvicorn server is running with 1 worker
    When 50 synchronous database queries hit multiple endpoints
    Then the async server loop accepts new HTTP requests without > 10ms hesitation
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Zombie Tasks | A: Timeout check in RPC. B: Clean-up cron | Blocks Story 02 | DevOps | Decided (Option A) |

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [ ] STORY-024-01-database-queue-rpc -> Backlog
- [ ] STORY-024-02-background-worker-locks -> Backlog
- [ ] STORY-024-03-fastapi-thread-wrapper -> Backlog
- [ ] STORY-024-04-fix-legacy-tests -> Backlog

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-24 | Ported to ClearGate v0.2.1. | ClearGate migration |
