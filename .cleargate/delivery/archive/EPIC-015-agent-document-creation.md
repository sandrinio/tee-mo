---
epic_id: "EPIC-015"
status: "Shipped"
children:
  - "STORY-015-01-schema-document-service"
  - "STORY-015-02-route-refactor"
  - "STORY-015-03-agent-refactor-and-tools"
  - "STORY-015-05-drive-sync-cron"
  - "STORY-015-06-frontend-update"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "TBD"
approved: true
created_at: "2026-04-13T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-015_agent_document_creation/EPIC-015_agent_document_creation.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# EPIC-015: Documents Table Redesign + Agent Document Creation

## 1. Problem & Value
> Target Audience: Stakeholders, Business Sponsors

### 1.1 The Problem
Two problems converging:

1. **Agent can't create knowledge.** Tee-Mo can read Drive files but cannot persist its own output. Meeting notes, summaries, synthesized insights — they disappear with the Slack thread. The agent has no write path back into the knowledge base.

2. **`teemo_knowledge_index` is being bent out of shape.** The table was designed for Drive file indexing. EPIC-014 (local upload) was already planning to bolt on nullable `drive_file_id`, a `source` column, and relaxed MIME constraints. Agent-created documents would add more patches. With zero clients and zero data, this is the right time to redesign the table properly rather than accumulate tech debt before launch.

### 1.2 The Solution
Replace `teemo_knowledge_index` with a proper **`teemo_documents`** table (following the `chy_documents` pattern from new_app) and add agent document creation tools.

The new table:
- Supports all three sources natively: `google_drive`, `upload`, `agent`
- Has a `sync_status` state machine (`pending → processing → synced → error`) that drives EPIC-013 wiki pipeline processing
- Drops Drive-specific assumptions (no more `drive_file_id` as the identity column)
- Uses UUID `id` as the universal document identifier across all sources

The agent gets **write tools only**:
- `create_document(title, content)` — persists markdown into the workspace knowledge base
- `update_document(document_id, content)` — modifies agent-created documents only
- `delete_document(document_id)` — removes agent-created documents only

The agent's **primary read path** is the wiki layer (EPIC-013) via `read_wiki_page(slug)`. This epic provides a `read_document` **fallback tool** for cases where wiki pages are insufficient (exact quotes, spreadsheet row data, documents pending wiki ingest). The wiki is the preferred path; raw document read is the escape hatch.

### 1.3 Success Metrics (North Star)
- Agent can create, update, and delete markdown documents via tools in Slack
- Created documents enter the wiki pipeline (EPIC-013) identically to Drive and uploaded files — `sync_status='pending'` triggers wiki ingest
- All existing Drive functionality works against the new `teemo_documents` table with zero behavioral regression
- `document_service.py` is the single CRUD entry point for all document operations (routes + agent tools)
- `read_document` fallback tool reads raw content from `teemo_documents` for cases where wiki pages are insufficient. Primary read path is wiki (EPIC-013).

---

## 2. Scope Boundaries
> Target Audience: AI Agents (Critical for preventing hallucinations)

### IN-SCOPE (Build This)
- [ ] **`teemo_documents` table** — replaces `teemo_knowledge_index`. New schema with `source` enum, `sync_status` state machine, `content_hash` (SHA-256), nullable `external_id` (Drive file ID), `original_filename`, `content` (replaces `cached_content`), `ai_description`, `doc_type`, `metadata` JSONB. Unified 15-doc cap via DB trigger.
- [ ] **Drop `teemo_knowledge_index`** — no data to migrate. Clean replacement.
- [ ] **`document_service.py`** — service layer with: `create_document()`, `read_document_content()`, `update_document()`, `delete_document()`, `list_documents()`. Both API routes and agent tools call this service. Handles hash computation, AI description generation, sync_status transitions.
- [ ] **Refactor knowledge routes** — `backend/app/api/routes/knowledge.py` updated to use `teemo_documents` + `document_service.py`. Existing endpoints preserved. New endpoint: `POST /api/workspaces/{id}/documents` for agent/upload creation.
- [ ] **Refactor existing agent code** — all references to `teemo_knowledge_index` in `agent.py` updated to `teemo_documents`. Rename `read_drive_file` to `read_document`. System prompt guidance: "Prefer wiki pages for answering questions. Use `read_document` only when you need exact quotes, specific data points, or the wiki doesn't cover the topic yet." Replace `## Available Files` with `## Available Documents`.
- [ ] **Agent document CRUD tools:** `create_document`, `update_document`, `delete_document`, `read_document`
- [ ] **`sync_status` state machine** — `pending → processing → synced → error`.
- [ ] **Cron: Drive change detection** — 10-minute background task checks all `source='google_drive'` documents for content-hash changes via `files.get(fields=md5Checksum)`. On hash mismatch: re-fetch content, update `content`, recompute `content_hash`, set `sync_status='pending'` for wiki re-ingest.
- [ ] **Reindex** — only re-fetches `source='google_drive'` documents. Skips `upload` and `agent`.
- [ ] **Health check** — replace `teemo_knowledge_index` with `teemo_documents` in `TEEMO_TABLES`.
- [ ] **Frontend** — update workspace detail page to read from `teemo_documents`. Source badges: Drive / Upload / Agent.

### OUT-OF-SCOPE (Do NOT Build This)
- **Wiki ingest pipeline** — that's EPIC-013.
- **`read_wiki_page` tool** — that's EPIC-013.
- **Wiki index in system prompt** — that's EPIC-013.
- Frontend document editor or viewer — agent-only creation for v1
- Frontend "Create Document" button — future enhancement
- Agent creating documents in formats other than markdown
- Agent editing Drive or uploaded files — those sources are read-only to the agent
- Version history or diff tracking
- Vector embeddings or RAG (Charter §2.3 — no vector DB)

---

## 3. Context

### 3.1 User Personas
- **Slack User**: Asks the agent to "write that up" or "save this as a doc" — expects it to persist for future conversations
- **Workspace Admin**: Manages all documents (Drive, uploaded, agent-created) from the dashboard
- **Agent (Tee-Mo)**: Can persist synthesized knowledge. Knowledge compounds across conversations via the wiki pipeline.

### 3.2 User Journey (Happy Path)
```mermaid
flowchart LR
    A[User asks agent to create a doc] --> B[Agent calls create_document tool]
    B --> C[document_service.create_document]
    C --> D[Hash content + generate AI description]
    D --> E[Insert into teemo_documents, source=agent, sync_status=pending]
    E --> F[Agent confirms to user]
    F --> G["EPIC-013: wiki pipeline picks up pending doc"]
    G --> H[Wiki pages generated, sync_status=synced]
    H --> I["Future conversations: agent reads wiki pages, not raw doc"]
```

### 3.3 Constraints
| Type | Constraint |
|------|------------|
| **Document Cap** | 15 documents per workspace, all sources combined (ADR-007). No sub-cap per source — simplest approach, no data to justify complexity. |
| **Content Size** | 100KB max content per document (aligned with new_app). Existing 50K char truncation preserved for Drive exports. |
| **BYOK** | AI description generation uses workspace BYOK key (scan-tier model). |
| **Workspace Isolation** | Documents scoped to workspace. Agent can only CRUD docs in its own workspace. |
| **Table Prefix** | `teemo_documents` (shared Supabase instance). |
| **Agent writes only** | Agent can create/update/delete `source='agent'` docs. Agent **reads** via wiki layer (EPIC-013), not raw documents. |
| **Auto-create** | Agent creates documents only when explicitly asked by the user. System prompt guides this. |

---

## 4. Technical Context
> Target Audience: AI Agents - READ THIS before decomposing.

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Migration | `database/migrations/0XX_teemo_documents.sql` | New — create `teemo_documents`, drop `teemo_knowledge_index` |
| Service | `backend/app/services/document_service.py` | New — CRUD operations, hash, AI description, sync_status transitions |
| Service | `backend/app/services/drive_service.py` | Modify — update table references from `teemo_knowledge_index` → `teemo_documents` |
| Service | `backend/app/services/scan_service.py` | No change — `generate_ai_description` interface stays the same |
| Routes | `backend/app/api/routes/knowledge.py` | Modify — use `teemo_documents` + `document_service`, add `POST .../documents` |
| Models | `backend/app/models/knowledge.py` | Modify — add `CreateDocumentRequest`, `DocumentResponse` with source field |
| Agent | `backend/app/agents/agent.py` | Modify — remove `read_drive_file` tool, add write tools, add transitional `## Available Documents` section |
| Cron | `backend/app/services/drive_sync_cron.py` | New — 10-minute background task checking Drive files for content-hash changes |
| Startup | `backend/app/main.py` | Modify — replace `teemo_knowledge_index` with `teemo_documents` in `TEEMO_TABLES`, register cron on lifespan |
| Frontend | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` | Modify — update API response shape, add source badges |
| Frontend | `frontend/src/hooks/useKnowledge.ts` | Modify — update types and API calls |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-004: BYOK Key Management | Done (S-06) — scan-tier uses workspace BYOK key |
| **Requires** | EPIC-007: AI Agent + Slack Event Loop | Done (S-07) — agent tool registration |
| **Absorbs** | EPIC-014: Local Upload | Ready — upload stories retarget `teemo_documents` instead of patching `teemo_knowledge_index` |
| **Feeds** | EPIC-013: Wiki Knowledge Pipeline | Draft — wiki pipeline reads `teemo_documents` where `sync_status='pending'` |

### 4.3 Integration Points
| System | Purpose | Docs |
|--------|---------|------|
| Pydantic AI Agent | `create_document`, `update_document`, `delete_document` write tools | `backend/app/agents/agent.py` |
| Scan-tier LLM | AI description generation | `backend/app/services/scan_service.py` |
| Google Drive API | Source content for `google_drive` documents + cron hash check | `backend/app/services/drive_service.py` |
| Wiki Pipeline (EPIC-013) | Reads `teemo_documents` where `sync_status='pending'`, processes into wiki pages | Future `wiki_service.py` |
| new_app reference | `chy_documents` table pattern, `document_service.py` CRUD pattern | `/Users/ssuladze/Documents/Dev/new_app/` |

### 4.4 Data Changes

**New table: `teemo_documents`**

```sql
CREATE TABLE teemo_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    title               VARCHAR(512) NOT NULL,
    content             TEXT,
    ai_description      TEXT,
    doc_type            VARCHAR(32) NOT NULL,
    source              VARCHAR(20) NOT NULL,
    sync_status         VARCHAR(16) NOT NULL DEFAULT 'pending',
    external_id         VARCHAR(128),
    external_link       TEXT,
    original_filename   VARCHAR(512),
    content_hash        VARCHAR(64),
    file_size           INTEGER,
    metadata            JSONB DEFAULT '{}',
    last_synced_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_teemo_documents_source CHECK (source IN ('google_drive', 'upload', 'agent')),
    CONSTRAINT chk_teemo_documents_sync_status CHECK (sync_status IN ('pending', 'processing', 'synced', 'error')),
    CONSTRAINT chk_teemo_documents_doc_type CHECK (doc_type IN (
        'pdf', 'docx', 'xlsx', 'text', 'markdown',
        'google_doc', 'google_sheet', 'google_slides'
    ))
);
```

**Dropped table: `teemo_knowledge_index`** — replaced entirely by `teemo_documents`.

### 4.5 Architecture Alignment — Karpathy Wiki (EPIC-013)

| Layer | Epic | Table | Agent interaction | Responsibility |
|-------|------|-------|-------------------|----------------|
| **Source document layer** | EPIC-015 (this) | `teemo_documents` | Write only (`create_document`, `update_document`, `delete_document`) | Where documents come from. Storage, sync, extraction, AI description. |
| **Knowledge layer** | EPIC-013 | `teemo_wiki_pages` | Read only (`read_wiki_page`, wiki index in system prompt) | Where the agent reads. Wiki pages, cross-references, TLDRs, lint. |

---

## 5. Decomposition Guidance

### Affected Areas (for codebase research)
- [ ] `backend/app/api/routes/knowledge.py` — all endpoints query `teemo_knowledge_index`, need `teemo_documents`
- [ ] `backend/app/agents/agent.py` — `read_drive_file` tool, `_build_system_prompt()`, tool list, `AgentDeps`
- [ ] `backend/app/services/drive_service.py` — table references
- [ ] `backend/app/services/scan_service.py` — `generate_ai_description`
- [ ] `backend/app/models/knowledge.py` — Pydantic models
- [ ] `backend/app/main.py` — `TEEMO_TABLES` list, lifespan for cron registration
- [ ] `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — knowledge list UI
- [ ] `frontend/src/hooks/useKnowledge.ts` — API hooks
- [ ] `database/migrations/` — follow existing sequential numbering
- [ ] new_app reference: `backend/app/services/document_service.py`, `backend/app/agents/orchestrator.py`, `database/migrations/006_documents.sql`

### Suggested Sequencing Hints
1. **Schema + service layer** — `teemo_documents` migration + `document_service.py` with core CRUD. Drop `teemo_knowledge_index`.
2. **Route refactor** — Update knowledge routes to use `teemo_documents` + `document_service`. All existing Drive endpoints work.
3. **Agent refactor** — Remove `read_drive_file` tool, update system prompt to transitional `## Available Documents`, update all table references.
4. **Agent create/update/delete tools** — New write tools calling `document_service`.
5. **Drive sync cron** — 10-minute background task checking `source='google_drive'` docs for hash changes, resetting `sync_status='pending'`.
6. **Frontend update** — Update workspace detail page for new API shape + source badges.

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| **Table rename breaks existing code** — many files reference `teemo_knowledge_index` | High (expected) | This IS the work. Systematic find-and-replace across routes, services, agent, tests. No data to migrate — purely code changes. |
| **Transitional gap** — after removing `read_drive_file` and before EPIC-013 lands | Medium | Acceptable tradeoff. The transitional `## Available Documents` section gives the agent enough context for most queries. |
| **Agent floods knowledge base** | Medium | 15-doc cap applies to all sources equally. Agent gets a clear error at cap. System prompt instructs agent to create docs only when explicitly asked. |
| **Drive functionality regression** | Medium | All existing Drive tests must pass against `teemo_documents`. Column mapping is mechanical. |
| **sync_status stays pending forever** | Low | Until EPIC-013 lands, documents stay `pending` — no ill effects. The field is forward-compatible. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Documents Table Redesign + Agent Document Creation

  Scenario: Existing Drive functionality works on new table
    Given a workspace with Drive connected and BYOK key configured
    When the user adds a file via Google Picker
    Then a row is inserted into teemo_documents with source "google_drive"
    And external_id contains the Drive file ID
    And ai_description is generated
    And content contains the extracted text
    And sync_status is "pending"
    And the file appears in the knowledge list on the dashboard

  Scenario: Agent creates a markdown document
    Given a workspace with BYOK key configured and fewer than 15 documents
    When the agent calls create_document with title "Meeting Notes" and markdown content
    Then a row is inserted into teemo_documents with source "agent" and doc_type "markdown"
    And ai_description is generated via scan-tier model
    And content_hash is computed (SHA-256)
    And sync_status is "pending"
    And the agent returns confirmation with the document ID

  Scenario: Agent cannot update Drive or uploaded files
    Given a workspace with a Drive-sourced document
    When the agent calls update_document with that document's ID
    Then the tool returns "Only agent-created documents can be updated"

  Scenario: 15-document cap spans all sources
    Given a workspace with 15 total documents (any mix of Drive, upload, agent)
    When the agent calls create_document
    Then the tool returns "Maximum 15 documents per workspace"

  Scenario: Drive sync cron detects content change
    Given a workspace with a Drive file whose content has changed
    When the 10-minute cron job runs
    Then it detects the hash mismatch via files.get(fields=md5Checksum)
    And re-fetches the file content
    And updates content, content_hash, and ai_description in teemo_documents
    And sets sync_status to "pending" for wiki re-ingest

  Scenario: Dashboard shows source badges
    Given a workspace with documents from all three sources
    When the user views the knowledge list
    Then each document shows a source badge: "Drive", "Upload", or "Agent"
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| **Sub-cap for agent docs?** | **A: No sub-cap** | Simplest. No data to justify complexity. | Solo dev | **Decided** — Option A |
| **Should agent auto-create docs?** | **A: Only when user explicitly asks.** | System prompt guides this. | Solo dev | **Decided** — Option A |
| **Transitional read gap** | **Keep `read_document` as fallback.** | No gap. Agent always has a read path. | Solo dev | **Decided** — keep fallback |
| **Cron ownership** | **Drive sync cron lives in EPIC-015** (document layer). Wiki ingest cron lives in EPIC-013 (knowledge layer). | Clean separation of concerns. | Solo dev | **Decided** |

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [ ] STORY-015-01-schema-document-service (L2) → Active (Sprint S-11)
- [ ] STORY-015-02-route-refactor (L2) → Active (Sprint S-11)
- [ ] STORY-015-03-agent-refactor-and-tools (L2) → Active (Sprint S-11) — merged from 015-03 + 015-04
- [ ] STORY-015-05-drive-sync-cron (L2) → Active (Sprint S-11)
- [ ] STORY-015-06-frontend-update (L1) → Active (Sprint S-11)

**References:**
- Charter: [Tee-Mo Charter](../../strategy/tee_mo_charter.md) §2.7 (Chat-First Extensibility)
- Roadmap: [Tee-Mo Roadmap](../../strategy/tee_mo_roadmap.md) §3 ADR-005, ADR-006, ADR-007
- Reference impl: `/Users/ssuladze/Documents/Dev/new_app/` — `chy_documents` table, `document_service.py`
- Absorbs: EPIC-014 schema migration
- Feeds: EPIC-013 (Wiki Pipeline)
- Depends on: EPIC-004 (BYOK, Done), EPIC-007 (Agent, Done)

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Epic created. Agent document creation tools + API. 3 open questions. | Claude (doc-manager) |
| 2026-04-13 | Major rewrite. Scope expanded to full table redesign. | Claude (doc-manager) |
| 2026-04-13 | Architecture alignment with Karpathy Wiki (EPIC-013). Added `read_document` as fallback tool. | Claude (doc-manager) |
| 2026-04-13 | Pre-sprint refinement. Restored `read_document` as fallback tool. | Claude (doc-manager) |
