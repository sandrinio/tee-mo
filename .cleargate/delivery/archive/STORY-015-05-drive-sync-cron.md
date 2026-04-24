---
story_id: "STORY-015-05"
parent_epic_ref: "EPIC-015"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-015-05-drive-sync-cron.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-015-05: Drive Content Sync Cron

**Complexity: L2** — 1 new service file + startup registration, ~3hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Create a 10-minute background cron that checks all `source='google_drive'` documents for content changes via the Google Drive API. When a file's content hash has changed, re-fetch content, recompute hash, re-generate AI description, and set `sync_status='pending'` so the wiki pipeline (EPIC-013) re-ingests.

### 1.2 Detailed Requirements

- **R1 — Cron service**: Create `backend/app/services/drive_sync_cron.py`:
  - Runs every 10 minutes as an asyncio background task registered on FastAPI lifespan.
  - Queries all workspaces that have Google Drive connected (`encrypted_google_refresh_token IS NOT NULL`).
  - For each workspace, queries `teemo_documents` where `source='google_drive'`.
  - For each Drive document: calls `files.get(fileId, fields='md5Checksum')` via the Drive API.
  - If hash differs from stored `content_hash`: re-fetch full content, update `content`, recompute SHA-256 `content_hash`, re-generate `ai_description`, set `sync_status='pending'`, update `last_synced_at`.
  - If hash matches: skip (no LLM call, no DB write).
- **R2 — Lightweight API usage**: Only `files.get(fields=md5Checksum)` for the check — 1 API call per file, no content download unless hash changed. Google Drive API allows 12,000 queries/100s.
- **R3 — Error handling**: If a file check fails (revoked token, file deleted from Drive), log the error and continue to next file. Don't crash the cron loop.
- **R4 — Lifespan registration**: Register the cron in `backend/app/main.py` lifespan startup. Use `asyncio.create_task` with a `while True` + `asyncio.sleep(600)` loop.
- **R5 — Logging**: Use structured logging (STORY-016-01) for all cron events: `cron.drive_sync.start`, `cron.drive_sync.file_changed`, `cron.drive_sync.complete`.

### 1.3 Out of Scope
- Wiki ingest cron (EPIC-013)
- Manual reindex endpoint changes (STORY-015-02)
- Drive webhook / push notifications (future optimization)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Drive Sync Cron

  Scenario: Cron detects changed file
    Given a workspace with a Drive document whose content has changed
    When the cron runs
    Then content is re-fetched and updated in teemo_documents
    And content_hash is recomputed
    And ai_description is re-generated
    And sync_status is set to "pending"

  Scenario: Cron skips unchanged files
    Given a workspace with 3 Drive files, all unchanged
    When the cron runs
    Then no documents are modified
    And no LLM calls are made

  Scenario: Cron handles revoked Drive token
    Given a workspace whose Google refresh token has been revoked
    When the cron runs
    Then the error is logged
    And the cron continues to the next workspace

  Scenario: Cron ignores non-Drive documents
    Given a workspace with 2 Drive files and 1 agent-created doc
    When the cron runs
    Then only the 2 Drive files are checked
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **New files** | `backend/app/services/drive_sync_cron.py` |
| **Modified files** | `backend/app/main.py` (lifespan registration) |
| **Reference** | new_app `backend/app/workers/cron.py`, existing `drive_service.py` for Drive client construction |

### 3.2 Technical Logic
1. Reuse `get_drive_client()` from `drive_service.py` for each workspace.
2. Use `document_service.update_document()` for content updates (handles hash + AI desc + sync_status).
3. Wrap per-workspace processing in try/except to isolate failures.
4. Register in lifespan: `asyncio.create_task(drive_sync_loop())`.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |
