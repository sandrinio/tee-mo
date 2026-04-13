---
story_id: "STORY-015-01"
parent_epic_ref: "EPIC-015"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-015 §4.4, §4.5 / new_app database/migrations/006_documents.sql + services/document_service.py"
actor: "System"
complexity_label: "L2"
depends_on: []
---

# STORY-015-01: Documents Table Migration + Document Service Layer

**Complexity: L2** — 1 migration + 1 new service file + health check update, ~3hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Replace `teemo_knowledge_index` with `teemo_documents` — a properly designed table supporting Drive, upload, and agent-created documents with a `sync_status` state machine. Create `document_service.py` as the single CRUD entry point (both API routes and agent tools will use it).

### 1.2 Detailed Requirements

- **R1 — Migration**: Create `teemo_documents` table per EPIC-015 §4.4 schema. Drop `teemo_knowledge_index`. Include all indexes, constraints, and the 15-doc cap trigger.
- **R2 — Document service**: Create `backend/app/services/document_service.py` with:
  - `create_document(supabase, workspace_id, title, content, doc_type, source, external_id=None, external_link=None, original_filename=None, file_size=None, metadata=None) → dict` — computes SHA-256 hash, generates AI description via scan-tier, inserts row with `sync_status='pending'`, returns created row.
  - `read_document_content(supabase, workspace_id, document_id) → str | None` — returns `content` column. Workspace isolation enforced.
  - `update_document(supabase, workspace_id, document_id, content=None, title=None) → dict` — updates fields, recomputes hash if content changed, re-generates AI description, resets `sync_status='pending'`. Returns updated row.
  - `delete_document(supabase, workspace_id, document_id) → bool` — deletes row. Returns True if deleted.
  - `list_documents(supabase, workspace_id) → list[dict]` — returns all documents ordered by `created_at DESC`.
- **R3 — Hash upgrade**: Use SHA-256 (hashlib) instead of MD5. Extract `compute_content_hash()` into `document_service.py`.
- **R4 — Health check**: Replace `teemo_knowledge_index` with `teemo_documents` in `TEEMO_TABLES` in `backend/app/main.py`.

### 1.3 Out of Scope
- Route refactoring (STORY-015-02)
- Agent tool changes (STORY-015-03, STORY-015-04)
- Frontend changes (STORY-015-06)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Documents Table + Service Layer

  Scenario: teemo_documents table exists
    Given the migration has been applied
    Then teemo_documents table exists with all columns per EPIC-015 §4.4
    And teemo_knowledge_index does NOT exist

  Scenario: 15-document cap enforced
    Given a workspace with 15 documents
    When a 16th document is inserted
    Then the DB trigger raises "Maximum 15 documents per workspace"

  Scenario: create_document generates hash and AI description
    Given a workspace with a BYOK key
    When document_service.create_document is called with title and content
    Then the returned row has a SHA-256 content_hash
    And ai_description is non-empty
    And sync_status is "pending"

  Scenario: update_document resets sync_status
    Given an existing agent-created document
    When document_service.update_document is called with new content
    Then content_hash is recomputed
    And sync_status is reset to "pending"

  Scenario: Health check includes teemo_documents
    Given the backend is running
    When GET /api/health is called
    Then the response includes "teemo_documents" in the database breakdown
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Migration tool** | Manual SQL execution on Supabase | [ ] |
| **Existing table** | `teemo_knowledge_index` (will be dropped) | [ ] |

### 3.1 Files
| Item | Value |
|------|-------|
| **New files** | `database/migrations/0XX_teemo_documents.sql`, `backend/app/services/document_service.py` |
| **Modified files** | `backend/app/main.py` (TEEMO_TABLES) |
| **Reference** | new_app `backend/app/services/document_service.py`, `database/migrations/006_documents.sql` |

### 3.2 Technical Logic
1. Write migration SQL per EPIC-015 §4.4 (copy schema verbatim).
2. Create `document_service.py` following new_app's pattern. Import `generate_ai_description` from `scan_service.py`. Use `hashlib.sha256` for content hashing.
3. Update `TEEMO_TABLES` in `main.py`.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |
