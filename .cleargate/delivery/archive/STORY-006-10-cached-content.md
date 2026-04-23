---
story_id: "STORY-006-10"
parent_epic_ref: "EPIC-006"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-006_google_drive/STORY-006-10-cached-content.md`. Shipped in sprint S-08, carried forward during ClearGate migration 2026-04-24.

# STORY-006-10: Cache Extracted Content at Index Time

**Complexity: L2** — Migration + 2 backend files + agent tool change, known pattern, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack User**,
> I want the bot to answer from cached file content instead of re-fetching from Google Drive on every question,
> So that responses are faster and don't fail when Drive is temporarily unavailable.

### 1.2 Detailed Requirements

- **R1: Migration** — Add `cached_content TEXT` column to `teemo_knowledge_index`. Nullable (existing rows will have NULL until re-indexed).
- **R2: Populate at index time** — When a file is indexed via `POST /api/workspaces/{id}/knowledge`, store the extracted content in `cached_content` alongside the existing `content_hash` and `ai_description`.
- **R3: `read_drive_file` reads from cache** — The agent tool in `agent.py` should first check `cached_content`. If non-NULL, return it directly without hitting the Drive API. This eliminates the Drive API call on every query.
- **R4: Self-healing updates cache** — When `read_drive_file` detects a content hash change (existing ADR-006 mechanism), it fetches fresh content from Drive, updates `cached_content`, `content_hash`, and `ai_description` in the DB.
- **R5: Cache miss fallback** — If `cached_content` is NULL (legacy rows indexed before this story), fall back to the existing Drive API fetch. After fetching, populate `cached_content` so subsequent reads hit cache.
- **R6: No new API endpoints** — This is a transparent optimization. No frontend changes needed.
- **R7: Content in cache is post-extraction markdown** — The cached content is the output of the improved extractors (STORY-006-07), not raw Drive API bytes.

### 1.3 Out of Scope
- Frontend display of cached content
- Cache invalidation UI (manual re-scan is STORY-006-11)
- TTL-based cache expiry — self-healing hash mechanism is sufficient
- Compression of cached content

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Cached Content at Index Time

  Scenario: New file indexed — content cached
    Given a workspace with Drive connected and BYOK key
    When a user indexes a PDF file via the knowledge endpoint
    Then teemo_knowledge_index row has non-NULL cached_content
    And cached_content matches the output of fetch_file_content

  Scenario: Agent reads from cache — no Drive API call
    Given an indexed file with cached_content populated
    When the agent calls read_drive_file for that file
    Then the cached_content is returned
    And no Drive API call is made (get_drive_client not called)

  Scenario: Cache miss — legacy row without cached_content
    Given an indexed file with cached_content = NULL (pre-migration row)
    When the agent calls read_drive_file for that file
    Then the content is fetched from Drive API (fallback)
    And the fetched content is written to cached_content
    And subsequent reads return from cache

  Scenario: Self-healing updates cache on content change
    Given an indexed file with cached_content populated
    And the file content has changed in Drive (different hash)
    When the agent calls read_drive_file
    Then fresh content is fetched from Drive
    And cached_content is updated with the new content
    And content_hash is updated
    And ai_description is re-generated

  Scenario: Self-healing skipped when hash matches
    Given an indexed file with cached_content populated
    And the file has NOT changed in Drive
    When the agent calls read_drive_file
    Then cached_content is returned directly
    And no Drive API call is made
    And no DB update occurs
```

### 2.2 Verification Steps (Manual)
- [ ] Index a new file → check DB row has `cached_content` populated
- [ ] Ask agent about the file → response is fast (no Drive latency)
- [ ] Disconnect Drive (revoke token) → agent still answers from cache for existing files

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-006-07 merged (improved extractors produce the content being cached) | [ ] |
| **Migration** | New migration file to add column | [ ] |
| **Services Running** | Backend dev server + Supabase | [ ] |

### 3.1 Test Implementation
- Modify `backend/tests/test_knowledge_routes.py`:
  - Test: index_file stores `cached_content` in the inserted row
- Modify `backend/tests/test_agent_factory.py` (or agent-related tests):
  - Test: read_drive_file returns `cached_content` when present, no Drive call
  - Test: read_drive_file falls back to Drive when `cached_content` is NULL, then populates it
  - Test: read_drive_file on hash change — updates cache + hash + description

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `backend/app/agents/agent.py` (read_drive_file tool), `backend/app/api/routes/knowledge.py` (index_file route) |
| **Related Files** | `database/migrations/` (new migration), `backend/app/main.py` (no change — same table) |
| **New Files Needed** | Yes — `database/migrations/012_knowledge_cached_content.sql` |
| **ADR References** | ADR-005 (Drive read — now cache-first), ADR-006 (self-healing — unchanged, cache updated alongside) |
| **First-Use Pattern** | No |

### 3.3 Technical Logic

#### 3.3.1 Migration — `database/migrations/012_knowledge_cached_content.sql`

```sql
-- Migration: 012_knowledge_cached_content
-- Purpose:   Add cached_content column to teemo_knowledge_index for
--            cache-first reads (no Drive API call on every agent query).
-- Depends on: 003_teemo_knowledge_index

ALTER TABLE teemo_knowledge_index
    ADD COLUMN IF NOT EXISTS cached_content TEXT;

-- Existing rows will have NULL cached_content until re-indexed (STORY-006-11)
-- or until the agent reads them (cache-miss fallback populates on first read).
```

Check migration numbering — look at existing files in `database/migrations/` and use the next sequential number.

#### 3.3.2 `knowledge.py` — index_file route

After content is fetched and before the insert (around line 249), add `cached_content` to the row payload:

```python
row = {
    "id": new_id,
    "workspace_id": workspace_id,
    "drive_file_id": payload.drive_file_id,
    "title": payload.title,
    "link": payload.link,
    "mime_type": payload.mime_type,
    "ai_description": ai_description,
    "content_hash": content_hash,
    "cached_content": content,  # NEW — cache extracted content at index time
}
```

That's the only change to this file.

#### 3.3.3 `agent.py` — `read_drive_file` tool rewrite

Current flow (lines 608-692):
1. Look up file in knowledge_index
2. Get workspace Drive refresh token + BYOK key
3. Build Drive client
4. Fetch content from Drive
5. Self-healing check (hash compare → re-generate description if changed)
6. Return content

New flow:
1. Look up file in knowledge_index (already selects `*`, so `cached_content` is included)
2. **If `cached_content` is not NULL → return it immediately.** Skip steps 3-5 entirely. No Drive call.
3. (Cache miss path) Get workspace Drive refresh token + BYOK key
4. Build Drive client, fetch content from Drive
5. Self-healing: always update `cached_content` + `content_hash` + `ai_description` since this is either a cache-miss backfill or a hash change
6. Return content

```python
async def read_drive_file(ctx: Any, drive_file_id: str) -> str:
    # ... existing step 1 (file lookup) ...
    file_row = file_result.data[0]

    # Cache-first: return cached content if available
    cached = file_row.get("cached_content")
    if cached:
        return cached

    # Cache miss — fall through to Drive API fetch
    # ... existing steps 2-4 (get workspace, build client, fetch content) ...

    # Always update cache on fetch (either backfill or self-healing)
    new_hash = compute_content_hash(content)
    update_payload = {
        "workspace_id": deps.workspace_id,
        "drive_file_id": drive_file_id,
        "cached_content": content,
        "content_hash": new_hash,
    }
    # Only re-generate AI description if hash actually changed
    if new_hash != file_row.get("content_hash"):
        api_key_plain = _decrypt_key(ws_row["encrypted_api_key"])
        new_description = await generate_ai_description(
            content, ws_row["ai_provider"], api_key_plain
        )
        update_payload["ai_description"] = new_description

    deps.supabase.table("teemo_knowledge_index").upsert(update_payload).execute()

    return content
```

**Important:** The cache-first return skips Drive entirely. If the user wants to force a refresh (content changed in Drive), that's STORY-006-11 (re-index). The self-healing path only triggers on cache miss (first read after migration) — after that, cache is always hit. This is intentional: the re-index endpoint is the explicit refresh mechanism.

Wait — this changes the self-healing behavior. Currently, `read_drive_file` fetches from Drive every time and checks the hash. With cache-first, it never fetches from Drive once cached, so stale content stays stale until re-indexed.

**Decision needed from story spec:** Accept this trade-off. The re-index endpoint (006-11) is the explicit way to refresh. Self-healing on every read was expensive (Drive API call per question). The cache-first approach is the user's stated preference ("process at index time + cached_content column for fast concurrent reads").

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 5 | Cache populated at index, cache hit (no Drive call), cache miss + backfill, self-healing on miss with hash change, self-healing on miss without hash change |
| Integration tests | 0 | N/A — no new endpoints |
| E2E / acceptance tests | 0 | Manual (§2.2) |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations (§4.1) met — 5+ tests.
- [ ] Migration applied to dev database.
- [ ] FLASHCARDS.md consulted (Supabase upsert + DEFAULT NOW() rule).
- [ ] No violations of ADR-005, ADR-006.
- [ ] `read_drive_file` returns cached content without Drive API call.
- [ ] Index route stores `cached_content` on insert.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 60 | 4,184 | 4,244 |
| Developer | 16 | 868 | 884 |
