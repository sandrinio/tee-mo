---
story_id: "STORY-013-03"
parent_epic_ref: "EPIC-013"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-14T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-013-03-wiki-ingest-cron.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-013-03: Wiki Ingest Cron + Document Deletion Cascade

**Complexity: L2** — 1 new cron service + deletion hook, ~2hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Create a background cron that scans `teemo_documents` for `sync_status='pending'` and runs wiki ingest for each. Also wire up document deletion to cascade-delete associated wiki pages.

### 1.2 Detailed Requirements

- **R1 — Wiki ingest cron**: Create `backend/app/services/wiki_ingest_cron.py`:
  - Runs on a loop (configurable interval, default 60 seconds — more responsive than Drive sync since documents are already local).
  - Queries `teemo_documents` where `sync_status='pending'` across all workspaces.
  - For each pending document: resolve workspace BYOK key, call `wiki_service.ingest_document()` (or `reingest_document()` if wiki pages already exist for that document).
  - On success: `sync_status='synced'`. On failure: `sync_status='error'`, log error, continue.
- **R2 — Lifespan registration**: Register in `backend/app/main.py` lifespan startup alongside Drive sync cron.
- **R3 — Document deletion cascade**: When a document is deleted from `teemo_documents`, delete all wiki pages where `source_document_ids` includes that document's ID. Rebuild wiki index. This can be a post-delete hook in `document_service.delete_document()`.
- **R4 — Logging**: Structured logging for: `cron.wiki_ingest.start`, `cron.wiki_ingest.document_processed`, `cron.wiki_ingest.error`, `cron.wiki_ingest.complete`.
- **R5 — Skip errored docs**: Documents with `sync_status='error'` are NOT retried automatically. They require manual re-trigger (e.g., user re-indexes, or content is updated which resets status to pending).

### 1.3 Out of Scope
- Lint cron (STORY-013-04)
- Drive content sync cron (STORY-015-05 — separate concern)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Wiki Ingest Cron

  Scenario: Cron processes pending documents
    Given 2 documents with sync_status "pending"
    When the wiki ingest cron runs
    Then both documents are ingested into wiki pages
    And sync_status is set to "synced" for both

  Scenario: Cron skips errored documents
    Given a document with sync_status "error"
    When the wiki ingest cron runs
    Then the document is NOT processed

  Scenario: Document deletion cascades to wiki pages
    Given a document with 8 associated wiki pages
    When the document is deleted
    Then all 8 wiki pages are deleted
    And the wiki index is rebuilt

  Scenario: Cron handles ingest failure gracefully
    Given a document whose ingest fails
    When the cron processes it
    Then sync_status is set to "error"
    And the cron continues to the next document
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **New files** | `backend/app/services/wiki_ingest_cron.py` |
| **Modified files** | `backend/app/main.py` (lifespan), `backend/app/services/document_service.py` (deletion cascade) |

### 3.2 Technical Logic
1. Cron loop: `while True` → query pending docs → process each → `asyncio.sleep(60)`.
2. For each doc: check if wiki pages already exist (re-ingest vs first ingest).
3. Add cascade logic to `document_service.delete_document()`: delete from `teemo_wiki_pages` where document ID in `source_document_ids`, then call `rebuild_wiki_index`.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |
