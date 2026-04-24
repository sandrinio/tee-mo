---
story_id: "STORY-024-02"
parent_epic_ref: "EPIC-024"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-024_concurrency_hardening/STORY-024-02-background-worker-locks.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-024-02-background-worker-locks: Background Worker Locks Refactor

**Complexity: L2** — Updates two existing Cron files to utilize the RPC locking, resolving race conditions.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> This story refactors our `wiki_ingest` and `drive_sync` cron workers to securely claim batches of pending documents via an exclusive Postgres lock, preventing horizontal scaling from resulting in LLM duplicate charges and race conditions.

### 1.2 Detailed Requirements
- **Requirement 1**: Inside `wiki_ingest_cron.py`, locate the query retrieving pending documents. Replace it with a `.rpc("claim_pending_documents", {"batch_size": 20})` execution.
- **Requirement 2**: Inside `drive_sync_cron.py`, perform the exact same refactor for its pending document queue query.
- **Requirement 3**: Verify that the explicit `except Exception:` handlers correctly reset failed document `sync_status` to `error` (so it does not remain stuck in `processing` holding up zombies until the 30min timeout).
- **Requirement 4**: Ensure that successful document ingestion is updating from `processing` to `synced` (or whatever the success terminal state is). This is likely already handled by `wiki_service`, just review it doesn't break. 

### 1.3 Out of Scope
- Modifying the core LLM ingestion `wiki_service.py` logic.
- Adding API routes to force retry crashed workers.

### TDD Red Phase: Yes
> Team Lead enforces Red-Green multi-pass if there are unit tests for crons.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: CRON Exclusive Locking 

  Scenario: Processing pending queues exclusively
    Given multiple workers are active for the wiki ingest cron
    When the cron loop ticks
    Then the worker fetches docs exclusively using `claim_pending_documents`
    And documents transitioning to `error` upon exception are verified
```

### 2.2 Verification Steps (Manual)
- [ ] Spin up 2 concurrent processes of the backend manually and insert 20 documents. Verify total calls to `ingest_document` equal 20, not 40.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Migrations** | Ensure STORY-01 is merged and RPC exists on DB | [ ] |

### 3.1 Test Implementation
- Update unit tests inside `tests/backend/services/test_wiki_ingest_cron.py` if assertions verify `.select("*").eq(...)` previously. 
- Ensure mocked supabase client verifies `.rpc()` was called appropriately.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/wiki_ingest_cron.py` |
| **Related Files** | `backend/app/services/drive_sync_cron.py` |
| **First-Use Pattern** | Yes — Supabase PostgREST RPC consumption in Python |

### 3.3 Technical Logic
- In `backend/app/services/wiki_ingest_cron.py`, swap out the `pending_result = supabase.table("teemo_documents").select("*").eq("sync_status", "pending").execute()` query.
- New query block: `pending_result = supabase.rpc("claim_pending_documents", {"batch_size": 20}).execute()`.
- Validate that the data structure returned by `.rpc` is cleanly mapped correctly to `pending_docs` loop.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 2 | Ensure both crons' test suites have updated mocks |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] No violations of Roadmap ADRs.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
