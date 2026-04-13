---
story_id: "STORY-015-03"
parent_epic_ref: "EPIC-015"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-015 §2, §4.5 / new_app backend/app/agents/orchestrator.py / backend/app/agents/agent.py"
actor: "Agent (Tee-Mo)"
complexity_label: "L2"
depends_on: ["STORY-015-01"]
---

# STORY-015-03: Agent Refactor + Document CRUD Tools

**Complexity: L2** — 1 file (agent.py), ~4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Refactor the agent to use `teemo_documents` and add document CRUD tools. Rename `read_drive_file` to `read_document` (reads from `teemo_documents.content` by UUID, works for all sources). Add `create_document`, `update_document`, `delete_document` write tools for agent-created docs. Update system prompt to list documents from the new table.

### 1.2 Detailed Requirements

- **R1 — Rename `read_drive_file` → `read_document`**:
  - Reads `content` from `teemo_documents` by document `id` (UUID), not `drive_file_id`.
  - Works for ALL sources (Drive, upload, agent). Returns `content` column.
  - Workspace isolation enforced via `workspace_id` filter.
  - Self-healing logic removed — Drive sync cron (STORY-015-05) handles content freshness.
  - Much simpler than the old tool: just query by ID, return content. No Drive API calls.
- **R2 — Update system prompt builder**: `_build_system_prompt()` queries `teemo_documents` instead of `teemo_knowledge_index`. Section renamed to `## Available Documents`. Lists: `[{id}] "{title}" — {ai_description}` using UUID as identifier.
- **R3 — System prompt guidance**: Add: "Prefer wiki pages (`read_wiki_page`) for answering questions when available. Use `read_document` when you need exact quotes, specific data points, or the wiki doesn't cover the topic yet. Only create documents when the user explicitly asks you to."
- **R4 — `create_document(title, content)` tool**:
  - Calls `document_service.create_document` with `source='agent'`, `doc_type='markdown'`.
  - Returns: "Document '{title}' created (ID: {id}). It will appear in the wiki shortly."
  - Respects 15-doc cap. Requires BYOK key.
- **R5 — `update_document(document_id, content)` tool**:
  - Only `source='agent'` docs. Error for Drive/upload: "Only agent-created documents can be updated."
  - Resets `sync_status='pending'`.
- **R6 — `delete_document(document_id)` tool**:
  - Only `source='agent'` docs. Error for Drive/upload: "Only agent-created documents can be deleted via this tool."
- **R7 — Tool registration**: Replace `read_drive_file` with `read_document` + `create_document` + `update_document` + `delete_document` in `tools=[...]`.

### 1.3 Out of Scope
- Wiki layer / `read_wiki_page` (EPIC-013 STORY-013-01)
- Route changes (STORY-015-02)
- Drive sync cron (STORY-015-05)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Agent Refactor + Document Tools

  Scenario: read_drive_file tool removed, read_document exists
    Given the agent is built for a workspace
    Then the tool list does NOT include read_drive_file
    And the tool list includes read_document, create_document, update_document, delete_document

  Scenario: read_document returns content by UUID
    Given a workspace with a Drive document
    When the agent calls read_document with the document's UUID
    Then the document content is returned

  Scenario: read_document works for agent-created docs
    Given a workspace with an agent-created document
    When the agent calls read_document with the document's UUID
    Then the markdown content is returned

  Scenario: System prompt lists documents from teemo_documents
    Given a workspace with 3 documents (2 Drive, 1 agent-created)
    When the agent system prompt is built
    Then ## Available Documents lists all 3 with UUID, title, ai_description

  Scenario: Agent creates a document
    Given a workspace with BYOK key and <15 documents
    When the agent calls create_document("Meeting Notes", "# Notes\n...")
    Then a row exists in teemo_documents with source "agent", doc_type "markdown"
    And sync_status is "pending"
    And the tool returns a confirmation with the document ID

  Scenario: Agent creates document — cap reached
    Given a workspace with 15 documents
    When the agent calls create_document
    Then the tool returns "Maximum 15 documents per workspace"

  Scenario: Agent updates its own document
    Given a workspace with an agent-created document
    When the agent calls update_document with new content
    Then content and content_hash are updated
    And sync_status is reset to "pending"

  Scenario: Agent cannot update Drive document
    Given a workspace with a Drive document
    When the agent calls update_document with that ID
    Then the tool returns "Only agent-created documents can be updated"

  Scenario: Agent deletes its own document
    Given a workspace with an agent-created document
    When the agent calls delete_document with that ID
    Then the document is removed from teemo_documents

  Scenario: Agent cannot delete uploaded document
    Given a workspace with an uploaded document
    When the agent calls delete_document with that ID
    Then the tool returns "Only agent-created documents can be deleted via this tool"
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **Modified files** | `backend/app/agents/agent.py` |
| **Reference** | new_app `backend/app/agents/orchestrator.py` (create_document, update_document, delete_document tools), `backend/app/services/document_service.py` (STORY-015-01) |

### 3.2 Technical Logic

**read_document (replaces read_drive_file):**
1. Delete the old `read_drive_file` function (~110 lines with Drive client, self-healing, etc.)
2. New `read_document` is ~15 lines: query `teemo_documents` by `id` + `workspace_id`, return `content`. No Drive API calls.

**Write tools (create, update, delete):**
1. Each tool imports and calls `document_service` functions.
2. Uses `ctx.deps.workspace_id` and `ctx.deps.supabase`.
3. Source check for update/delete: query the document row first, verify `source='agent'`.

**System prompt:**
1. Update step 7.5 query: `teemo_knowledge_index` → `teemo_documents`, select `id, title, ai_description`.
2. Section header: `## Available Documents`.
3. Add guidance text about preferring wiki pages and only creating when asked.

**Tool list:**
```python
tools=[load_skill, create_skill, update_skill, delete_skill, web_search, crawl_page, http_request, read_document, create_document, update_document, delete_document]
```

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft. Merged from STORY-015-03 (agent refactor) + STORY-015-04 (agent write tools) to reduce agent.py contention. |
