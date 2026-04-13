---
story_id: "STORY-015-02"
parent_epic_ref: "EPIC-015"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-015 §4.1 / backend/app/api/routes/knowledge.py"
actor: "System"
complexity_label: "L2"
depends_on: ["STORY-015-01"]
---

# STORY-015-02: Refactor Knowledge Routes to teemo_documents

**Complexity: L2** — 2-3 files, mechanical refactor, ~3hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Update all knowledge API routes to use `teemo_documents` table and `document_service.py`. All existing Drive endpoints (index, list, delete, reindex) must work identically against the new table.

### 1.2 Detailed Requirements

- **R1 — Route refactor**: Update `backend/app/api/routes/knowledge.py`:
  - `POST /api/workspaces/{id}/knowledge` (index from Drive) → calls `document_service.create_document` with `source='google_drive'`, `external_id=drive_file_id`, `external_link=link`, `doc_type` mapped from MIME type.
  - `GET /api/workspaces/{id}/knowledge` (list) → calls `document_service.list_documents`.
  - `DELETE /api/workspaces/{id}/knowledge/{id}` (delete) → calls `document_service.delete_document`.
  - `POST /api/workspaces/{id}/knowledge/reindex` → only re-fetches `source='google_drive'` documents. Skips `upload` and `agent`.
- **R2 — MIME to doc_type mapping**: Create a mapping function: `application/vnd.google-apps.document` → `google_doc`, `application/pdf` → `pdf`, etc.
- **R3 — Models**: Update `backend/app/models/knowledge.py` — `KnowledgeIndexResponse` gains `source` and `doc_type` fields. Add `DocumentResponse` if needed.
- **R4 — New endpoint**: `POST /api/workspaces/{id}/documents` — accepts `{ title, content }`, calls `document_service.create_document` with `source='agent'`, `doc_type='markdown'`. (Used by agent tools, also available as API.)
- **R5 — Zero behavioral regression**: All existing Drive tests must pass with the new table.

### 1.3 Out of Scope
- Agent tool changes (STORY-015-03, STORY-015-04)
- Frontend (STORY-015-06)
- Drive service internals (extraction logic unchanged)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Knowledge Routes on teemo_documents

  Scenario: Index a Drive file
    Given a workspace with Drive connected and BYOK key
    When POST /api/workspaces/{id}/knowledge with a Drive file
    Then a row is created in teemo_documents with source "google_drive"
    And external_id matches the drive_file_id

  Scenario: List documents includes source
    Given a workspace with 2 Drive files and 1 agent-created doc
    When GET /api/workspaces/{id}/knowledge
    Then all 3 documents are returned with correct source values

  Scenario: Delete a document
    Given a workspace with a document
    When DELETE /api/workspaces/{id}/knowledge/{id}
    Then the document is removed from teemo_documents

  Scenario: Reindex skips non-Drive documents
    Given a workspace with 2 Drive files and 1 agent-created doc
    When POST /api/workspaces/{id}/knowledge/reindex
    Then only the 2 Drive files are re-fetched
    And the agent-created doc is untouched

  Scenario: Create document via API
    Given a workspace with BYOK key
    When POST /api/workspaces/{id}/documents with title and content
    Then a row is created with source "agent" and doc_type "markdown"
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **Modified files** | `backend/app/api/routes/knowledge.py`, `backend/app/models/knowledge.py` |
| **Reference** | `backend/app/services/document_service.py` (from STORY-015-01) |

### 3.2 Technical Logic
1. Replace all `supabase.table("teemo_knowledge_index")` calls with `document_service` functions.
2. Add MIME → doc_type mapping dict in knowledge.py or document_service.
3. Update reindex to filter `source='google_drive'` before re-fetching.
4. Add `POST .../documents` endpoint.
5. Update response models.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |
