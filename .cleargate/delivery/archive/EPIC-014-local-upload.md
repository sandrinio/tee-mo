---
epic_id: "EPIC-014"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "2026-04-15"
shipped_at: "2026-04-25"
shipping_sprint: "SPRINT-15"
shipping_commit: "3f87e9a"
children:
  - "STORY-014-01-extraction-service-refactor"
  - "STORY-014-02-upload-endpoint"
  - "STORY-014-03-frontend-upload"
created_at: "2026-04-13T00:00:00Z"
updated_at: "2026-04-25T08:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-post-S15-close"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-014_local_upload/EPIC-014_local_upload.md`. Carried forward during ClearGate migration 2026-04-24.

> **⚠ Re-scoped 2026-04-25 (pre-SPRINT-15 triage).** EPIC-015 (shipped via migration `010_teemo_documents.sql`) replaced the legacy `teemo_knowledge_index` table with `teemo_documents`, which **already includes** the `source` column (`google_drive | upload | agent`), `original_filename`, `text`/`markdown` doc_types, the shared 15-doc cap, and a source-agnostic `read_document` agent tool. ~70% of this epic's original IN-SCOPE list is already shipped as a side effect. The schema migration in §4.3 below is **dead code** — kept for historical context only. Remaining work is the multipart upload endpoint, the extraction-service refactor, and the frontend upload UI. See §5 (re-scoped) and Change Log entry 2026-04-25.

# EPIC-014: Local Document Upload

## 1. Problem & Value

### 1.1 The Problem
Users can only add knowledge files via Google Drive. If a user has a local PDF, Word doc, or spreadsheet that isn't on Drive, they cannot get it into the knowledge base without first uploading it to Drive. This is friction for quick demos and for users who don't use Google Drive.

### 1.2 The Solution
Add a file upload endpoint and frontend UI that lets users upload local documents directly. The file is processed in-memory (text extraction + AI description), stored as `cached_content` in the existing `teemo_knowledge_index` table, and the physical file is immediately discarded. No file storage on disk or blob storage — the extracted text is the only artifact.

### 1.3 Success Metrics (North Star)
- User can upload a local PDF, DOCX, or XLSX file from the workspace detail page
- Uploaded file is processed identically to Drive files (AI description, content hash, truncation)
- Uploaded files share the same 15-file cap with Drive files (ADR-007)
- Agent can read uploaded files via the existing `read_drive_file` tool (cache-first path)
- No physical file is persisted on disk or in blob storage — only extracted text in DB

---

## 2. Scope Boundaries

### IN-SCOPE (Build This)
- [ ] Database migration: make `drive_file_id` nullable, add `source` column (`google_drive` | `upload`), add `original_filename` column, relax MIME constraint to include `text/plain` and `text/markdown`, update unique constraint
- [ ] `POST /api/workspaces/{id}/knowledge/upload` — multipart form endpoint accepting a single file. Validates: workspace ownership, BYOK key, file count < 15, MIME type, file size ≤ 10MB. Extracts text, generates AI description, inserts row with `source = 'upload'`, `drive_file_id = NULL`, `cached_content = extracted_text`. Returns the created row.
- [ ] Refactor extraction functions (`_extract_pdf`, `_extract_docx`, `_extract_xlsx`) from `drive_service.py` into a shared `extraction_service.py` so both Drive and upload paths use them
- [ ] Support for `text/plain` (.txt) and `text/markdown` (.md) uploads — these are trivially read as-is (UTF-8 decode)
- [ ] Frontend: "Upload File" button alongside "Add from Drive" in the workspace detail page
- [ ] Frontend: file input with drag-and-drop or click-to-select, showing upload progress
- [ ] Frontend: uploaded files appear in the same KnowledgeList table with a distinct source badge ("Drive" vs "Upload")
- [ ] Agent system prompt: uploaded files listed in `## Available Files` same as Drive files, with a local identifier instead of drive_file_id
- [ ] Agent `read_drive_file` tool: uploaded files always return from `cached_content` (no Drive fetch path). Tool name stays the same for backwards compatibility; tool description updated.

### OUT-OF-SCOPE (Do NOT Build This)
- Drag-and-drop of folders or multiple files at once (single file per upload)
- Image uploads (PNG, JPG, etc.) — only document types
- OCR for scanned PDF uploads (multimodal fallback only available for Drive files)
- File versioning or re-upload of the same file
- Physical file storage (disk, S3, Supabase Storage) — extracted text only
- Renaming the `read_drive_file` tool to something generic (breaking change to agent tool schema; deferred)

---

## 3. Context

### 3.1 User Personas
- **Workspace Admin**: Uploads local files, manages knowledge base from dashboard
- **Slack User**: Asks questions — doesn't know or care whether a file came from Drive or upload
- **Agent (Tee-Mo)**: Reads cached_content for uploaded files; identical to cached Drive files

### 3.2 User Journey (Happy Path)
```mermaid
flowchart LR
    A[Admin opens workspace settings] --> B[Clicks 'Upload File']
    B --> C[Selects a local PDF/DOCX/XLSX/TXT]
    C --> D[Frontend sends multipart POST]
    D --> E[Backend extracts text in-memory]
    E --> F[Backend generates AI description via scan-tier]
    F --> G[Backend stores row with cached_content]
    G --> H[Physical file discarded — never saved]
    H --> I[File appears in knowledge list with 'Upload' badge]
    I --> J[Slack user @mentions bot]
    J --> K[Agent reads cached_content — same as Drive files]
```

### 3.3 Constraints
| Type | Constraint |
|------|------------|
| **File Size** | 10MB maximum per upload. Enforced at backend + frontend. |
| **File Cap** | Shared 15-file cap with Drive files (ADR-007). Same DB trigger. |
| **MIME Types** | PDF, DOCX, XLSX, TXT, MD. (Google Workspace types not applicable for uploads.) |
| **No Storage** | File bytes exist only in memory during processing. Never written to disk or blob storage. |
| **BYOK Gate** | Upload requires a valid BYOK key (scan-tier LLM call for AI description). |
| **Truncation** | Same 50K char content truncation as Drive files (ADR-016). |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Migration | `database/migrations/010_knowledge_upload_support.sql` | New — ALTER `teemo_knowledge_index` |
| Service | `backend/app/services/extraction_service.py` | New — shared extraction functions extracted from drive_service |
| Service | `backend/app/services/drive_service.py` | Modify — import extraction functions from extraction_service instead of defining locally |
| Routes | `backend/app/api/routes/knowledge.py` | Modify — add `POST /upload` endpoint |
| Models | `backend/app/models/knowledge.py` | Modify — add UploadFileResponse model |
| Agent | `backend/app/agents/agent.py` | Modify — use `id` (UUID) as file identifier for uploaded files in system prompt and tool |
| Frontend | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` | Modify — add Upload button + file input |
| Frontend | `frontend/src/hooks/useKnowledge.ts` | Modify — add useUploadKnowledgeMutation |
| Frontend | `frontend/src/lib/api.ts` | Modify — add uploadKnowledgeFile function |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-004: BYOK Key Management | Done — scan-tier uses workspace BYOK key |
| **Requires** | EPIC-006: Google Drive Integration | Done — knowledge_index table, extraction logic, agent tool |
| **Requires** | STORY-006-10: Cached Content | Done — `cached_content` column exists |

### 4.3 Data Changes

> **DEAD — already shipped via migration `010_teemo_documents.sql` (EPIC-015).** The block below targets the legacy `teemo_knowledge_index` table and is preserved only for historical context. Do not re-implement. See top-of-file re-scope note.

**Migration: `010_knowledge_upload_support.sql`** (NOT BUILT — superseded)

```sql
-- 1. Add source column (defaults to 'google_drive' for existing rows)
ALTER TABLE teemo_knowledge_index
    ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'google_drive';

-- 2. Add original_filename for uploaded files
ALTER TABLE teemo_knowledge_index
    ADD COLUMN IF NOT EXISTS original_filename VARCHAR(512);

-- 3. Make drive_file_id nullable (uploaded files have no Drive ID)
ALTER TABLE teemo_knowledge_index
    ALTER COLUMN drive_file_id DROP NOT NULL;

-- 4. Drop the old unique constraint and create a new one
ALTER TABLE teemo_knowledge_index
    DROP CONSTRAINT IF EXISTS uq_teemo_knowledge_index_workspace_file;

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_drive_file
    ON teemo_knowledge_index (workspace_id, drive_file_id)
    WHERE drive_file_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_upload_filename
    ON teemo_knowledge_index (workspace_id, original_filename)
    WHERE source = 'upload';

-- 5. Relax MIME type constraint to include text/plain and text/markdown
ALTER TABLE teemo_knowledge_index
    DROP CONSTRAINT IF EXISTS chk_teemo_knowledge_index_mime_type;

ALTER TABLE teemo_knowledge_index
    ADD CONSTRAINT chk_teemo_knowledge_index_mime_type CHECK (
        mime_type IN (
            'application/vnd.google-apps.document',
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.google-apps.presentation',
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/plain',
            'text/markdown'
        )
    );

-- 6. Add source check constraint
ALTER TABLE teemo_knowledge_index
    ADD CONSTRAINT chk_teemo_knowledge_source CHECK (
        source IN ('google_drive', 'upload')
    );
```

### 4.4 Key Design Decisions

**Why reuse `teemo_knowledge_index` instead of a new table?**
- The 15-file cap is enforced by a DB trigger on this table — one table = unified cap.
- The agent's `read_drive_file` tool already queries this table and returns `cached_content`.
- The `## Available Files` system prompt section already reads from this table.
- Adding a `source` column is a minimal schema change that preserves all existing behavior.

**Why 10MB file size limit?**
- Processing happens in-memory (extraction libraries load the whole file). 10MB is safe for server memory.
- Content is truncated at 50K chars anyway — files beyond ~5MB of text content rarely add value.
- Covers virtually all business documents (average PDF is 1-3MB, DOCX under 1MB).

**Why discard the physical file?**
- User requirement: "we just process it and delete."
- Eliminates storage cost, security surface (stored PII), and cleanup complexity.
- The `cached_content` column already stores the extracted text — that's all the agent needs.

**Agent tool naming:**
- The tool stays named `read_drive_file` for backwards compatibility with existing agent conversations.
- For uploaded files, the agent passes the knowledge index `id` (UUID) instead of a `drive_file_id`.

---

## 5. Decomposition Guidance

> **Re-scoped 2026-04-25.** Original 4-story plan reduced to 3 — schema work absorbed by EPIC-015 / migration 010, agent integration absorbed by STORY-015-03 (`read_document` tool is source-agnostic).

### Re-scoped Sequencing (SPRINT-15 candidates)

1. **STORY-014-01: Extraction service refactor** (L1)
   - Move `_extract_pdf`, `_extract_docx`, `_extract_xlsx`, `_maybe_truncate`, `_rows_to_markdown_table`, `_docx_table_to_markdown` from `drive_service.py` into a new `backend/app/services/extraction_service.py`
   - Update `drive_service.py` to import from the new module (no behavior change)
   - All existing Drive tests still pass

2. **STORY-014-02: Multipart upload endpoint** (L2)
   - `POST /api/workspaces/{id}/documents/upload` — multipart form, single file
   - Validations: workspace ownership, BYOK key present, doc count < 15, MIME allowlist (PDF/DOCX/XLSX/TXT/MD), file size ≤ 10MB
   - Extracts text via `extraction_service`, generates AI description via `scan_service`, calls `document_service.create_document(source='upload', ...)`
   - Duplicate filename returns 409
   - Physical file bytes never persisted to disk

3. **STORY-014-03: Frontend upload UI + source badge** (L2)
   - "Upload File" button alongside "Add from Drive" in workspace card
   - File input with progress indicator + 10MB client-side size check
   - Source badge ("Drive" / "Upload") rendered from existing `source` field on documents list
   - Read-only verification: agent system prompt lists upload rows correctly + `read_document` returns content for uploaded docs (no fixes expected — already shipped via EPIC-015)

### Dead — already shipped (do NOT re-implement)

- ~~Migration `010_knowledge_upload_support.sql`~~ — superseded by `010_teemo_documents.sql` (EPIC-015)
- ~~`source` column with `'upload'` value~~ — shipped in migration 010
- ~~`original_filename` column~~ — shipped in migration 010
- ~~Relax MIME for `text/plain` / `text/markdown`~~ — `doc_type` constraint includes `'text'` and `'markdown'`
- ~~Shared 15-file cap~~ — DB trigger on `teemo_documents` already covers all sources
- ~~Agent system prompt update for upload rows~~ — already source-agnostic (STORY-015-03)
- ~~Agent `read_drive_file` tool change~~ — replaced by source-agnostic `read_document` tool (STORY-015-03)

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Large file OOM** — 10MB XLSX with many sheets could expand significantly in memory | Low | 10MB limit + 50K char truncation. openpyxl streams data. |
| **Encoding issues** — non-UTF-8 text files | Medium | Attempt UTF-8 decode first, fall back to latin-1. |
| **MIME type sniffing mismatch** — user renames .txt to .pdf | Low | Trust the file extension / Content-Type header from the browser. |
| **Race condition on upload** | Low | Reuse the existing per-workspace `asyncio.Lock` from knowledge routes. |
| **Cannot re-extract uploaded files** — if extractors improve, old uploads won't benefit | Medium | Accept for v1. User can delete and re-upload. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Local Document Upload

  Scenario: Upload a PDF file
    Given a workspace with BYOK key configured
    And the workspace has fewer than 15 indexed files
    When the user uploads a 2MB PDF file
    Then the backend extracts text using pymupdf4llm
    And generates a 2-3 sentence AI description
    And stores the extracted text in cached_content
    And the physical file is NOT saved to disk
    And the file appears in the knowledge list with source "Upload"

  Scenario: 15-file cap includes uploads
    Given a workspace with 14 Drive files and 1 uploaded file (total 15)
    When the user tries to upload another file
    Then response is 400 "Maximum 15 files per workspace"

  Scenario: File too large
    When the user uploads a 15MB file
    Then response is 400 "File size exceeds 10MB limit"

  Scenario: BYOK key required
    Given a workspace with NO BYOK key
    When the user tries to upload a file
    Then response is 400 "BYOK key required to index files"

  Scenario: Unsupported file type rejected
    When the user uploads a .png file
    Then response is 400 "Unsupported file type"

  Scenario: Agent reads uploaded file
    Given a workspace with an uploaded PDF file
    When the agent calls read_drive_file with the file's ID
    Then the agent receives the cached_content text
    And no Drive API call is made

  Scenario: Duplicate filename rejected
    Given a workspace with an uploaded file named "report.pdf"
    When the user uploads another file named "report.pdf"
    Then response is 409 "File already uploaded"
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| None — all decisions made at epic planning time | — | — | — | — |

---

## 9. Artifact Links

**Stories (Status Tracking — re-scoped 2026-04-25):**
- [ ] [STORY-014-01-extraction-service-refactor](./STORY-014-01-extraction-service-refactor.md) (L1) — Draft — Move extractors out of `drive_service.py` into shared `extraction_service.py`
- [ ] [STORY-014-02-upload-endpoint](./STORY-014-02-upload-endpoint.md) (L2) — Draft — Multipart `POST /documents/upload` with validation + extraction + AI description
- [ ] [STORY-014-03-frontend-upload](./STORY-014-03-frontend-upload.md) (L2) — Draft — Upload UI + source badge + agent path verification

**References:**
- Depends on: EPIC-006 (Google Drive, Done), EPIC-004 (BYOK, Done), STORY-006-10 (Cached Content, Done)

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Epic created. 4 stories identified. Schema migration designed. All questions resolved at planning time. | Claude (doc-manager) |
| 2026-04-25 | Re-scoped pre-SPRINT-15. Discovered EPIC-015 / migration 010 already shipped the schema + agent integration the V-Bounce-era epic was designed for. Reduced from 4 stories to 3 (extraction refactor + multipart endpoint + frontend UI). Added top-of-file warning, "Dead — already shipped" subsection in §5, refreshed §9 story links. §4.3 migration SQL preserved as dead code for historical context — flagged in §5. | Claude |
| 2026-04-25 | **Shipped.** All three re-scoped stories landed on SPRINT-15: STORY-014-01 (`bfd82e4`), STORY-014-02 (`1c4ccb1`), STORY-014-03 (`e36e74c`). Squash-merged to main as `3f87e9a`. Status flipped Active → Shipped at sprint close. | Claude |
