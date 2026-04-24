---
story_id: "STORY-024-01"
parent_epic_ref: "EPIC-024"
status: "Shipped"
approved: true
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-21T00:00:00Z"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-024_concurrency_hardening/STORY-024-01-database-queue-rpc.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-024-01-database-queue-rpc: Postgres RPC Background Queue

**Complexity: L1** — Single SQL migration file to introduce RPC for claiming documents.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> This story introduces a native Postgres queue primitive because concurrent background workers are currently processing duplicate documents and racing one another, wasting LLM credits.

### 1.2 Detailed Requirements
- **Requirement 1**: Create a new database migration file in `database/migrations`.
- **Requirement 2**: Define a Supabase RPC function named `claim_pending_documents(batch_size integer)` that returns `teemo_documents` rows.
- **Requirement 3**: The function must atomically select `batch_size` pending documents using `FOR UPDATE SKIP LOCKED`.
- **Requirement 4**: The function must instantly update the claimed rows to `sync_status = 'processing'` and return them using the `RETURNING *` clause.
- **Requirement 5**: The function must consider both new (`sync_status = 'pending'`) documents AND zombies (`sync_status = 'processing'` where `last_scanned_at` or `updated_at` > 30 minutes ago) as available to claim. Note: `teemo_documents` might not have `updated_at` updated continually before completion, so ensure condition handles zombies effectively (option A selected in Epic). 

### 1.3 Out of Scope
- Actually utilizing the RPC function in the Python codebase (that's STORY-02).
- Restructuring the entire table schema.

### TDD Red Phase: No
> Default: No for pure config/doc/template changes.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Postgres Queue Native Function

  Scenario: Claim pending documents without blocking
    Given 5 documents are "pending"
    When user A queries the RPC for 2 documents
    And user B queries the RPC for 5 documents concurrently
    Then user A receives 2 documents marked as "processing"
    And user B receives the remaining 3 documents marked as "processing"
    And neither request is blocked by standard locks
```

### 2.2 Verification Steps (Manual)
- [ ] Verify the SQL migration file exists and contains valid PL/pgSQL function syntax supporting `SKIP LOCKED`.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Migrations** | Verify local Supabase instance is accessible | [ ] |

### 3.1 Test Implementation
- No unit tests required (pure SQL migration). Add to the backend schema tests if appropriate but manual verification through Supabase GUI/CLI is mostly sufficient.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `database/migrations/YYYYMMDDHHMMSS_create_claim_pending_docs_rpc.sql` (new file) |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Example Logic: 
```sql
CREATE OR REPLACE FUNCTION claim_pending_documents(batch_size int default 20) 
RETURNS SETOF teemo_documents AS $$
BEGIN
  RETURN QUERY UPDATE teemo_documents
  SET sync_status = 'processing'
  WHERE id IN (
    SELECT id FROM teemo_documents 
    WHERE sync_status = 'pending' 
       OR (sync_status = 'processing' AND updated_at < now() - interval '30 minutes')
    LIMIT batch_size 
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
END;
$$ LANGUAGE plpgsql;
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 | N/A |
| Schema  validation | 1 | Supabase db reset doesn't fail |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met.
- [ ] No violations of Roadmap ADRs.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
