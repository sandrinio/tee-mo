---
story_id: "STORY-006-03-knowledge-crud"
parent_epic_ref: "EPIC-006"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.4 / Charter §5.2 / Roadmap ADR-005, ADR-006, ADR-007, ADR-016"
actor: "Workspace Admin"
complexity_label: "L3"
---

# STORY-006-03: Knowledge Index CRUD + AI Description + Picker Token

**Complexity: L3** — Cross-cutting, touches Drive service + scan service + new routes + DB

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin**,
> I want to **add, list, and remove Google Drive files from my workspace's knowledge base**,
> So that **the bot can reference those files when answering questions**.

### 1.2 Detailed Requirements
- **R1**: `POST /api/workspaces/{id}/knowledge` — accepts `{ drive_file_id, title, link, mime_type }`. Validates: workspace ownership, Drive connected (refresh token exists), BYOK key configured, file count < 15, MIME type in ADR-016 list, file not already indexed. Reads file content via `drive_service.fetch_file_content`, computes hash via `compute_content_hash`, generates AI description via `scan_service.generate_ai_description`, inserts into `teemo_knowledge_index`. Returns the created row. **If file content was truncated (>50K chars), include `"warning": "File content truncated to 50,000 characters. The bot may not see the full document."` in the response.**
- **R2**: `GET /api/workspaces/{id}/knowledge` — lists all indexed files for workspace. Returns `[{ id, drive_file_id, title, link, mime_type, ai_description, last_scanned_at, created_at }]`. Ordered by `created_at` desc.
- **R3**: `DELETE /api/workspaces/{id}/knowledge/{knowledge_id}` — removes file from index. Verifies workspace ownership. Returns 200.
- **R4**: `GET /api/workspaces/{id}/drive/picker-token` — decrypts refresh token, mints short-lived access token, returns `{ access_token, picker_api_key }` for frontend Picker widget. Token is NOT stored — ephemeral, one-time use.
- **R5**: 15-file cap: backend count check BEFORE insert (defense in depth — DB trigger is hard gate).
- **R6**: BYOK gate: if `encrypted_api_key` is null on workspace, return 400 "BYOK key required to index files".
- **R7**: Pydantic request/response models in `backend/app/models/knowledge.py`.
- **R8**: **Sequential indexing queue**: concurrent `POST /knowledge` requests for the same workspace must be serialized (asyncio.Lock per workspace_id). Prevents race conditions on file count check and avoids BYOK rate limit spikes from parallel scan-tier calls.

### 1.3 Out of Scope
- Frontend UI (STORY-006-05)
- Agent tool (STORY-006-04)
- File content caching (read on-demand)
- Rescan/refresh button (EPIC-009)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Knowledge Index CRUD

  Scenario: Index a Google Docs file
    Given workspace "ws-1" with Drive connected and BYOK key
    And workspace has 0 indexed files
    When POST /api/workspaces/ws-1/knowledge with { drive_file_id: "abc", title: "Policy", link: "https://...", mime_type: "application/vnd.google-apps.document" }
    Then the backend reads file content from Drive API
    And generates an AI description via scan-tier model
    And computes an MD5 content hash
    And inserts a row into teemo_knowledge_index
    And returns the row with ai_description populated

  Scenario: 15-file cap enforced
    Given workspace "ws-1" with 15 indexed files
    When POST /api/workspaces/ws-1/knowledge with a new file
    Then response is 400 "Maximum 15 files per workspace"

  Scenario: BYOK key required
    Given workspace "ws-1" with Drive connected but NO BYOK key
    When POST /api/workspaces/ws-1/knowledge
    Then response is 400 "BYOK key required to index files"

  Scenario: Drive not connected
    Given workspace "ws-1" with NO encrypted_google_refresh_token
    When POST /api/workspaces/ws-1/knowledge
    Then response is 400 "Google Drive not connected"

  Scenario: Unsupported MIME type rejected
    Given workspace "ws-1" with Drive connected and BYOK key
    When POST with mime_type "image/png"
    Then response is 400 "Unsupported file type"

  Scenario: Duplicate file rejected
    Given workspace "ws-1" already has drive_file_id "abc" indexed
    When POST with drive_file_id "abc" again
    Then response is 409 "File already indexed"

  Scenario: List indexed files
    Given workspace "ws-1" with 3 indexed files
    When GET /api/workspaces/ws-1/knowledge
    Then response is an array of 3 file objects with ai_description

  Scenario: Remove indexed file
    Given workspace "ws-1" with file knowledge_id "k-1"
    When DELETE /api/workspaces/ws-1/knowledge/k-1
    Then the row is deleted from teemo_knowledge_index
    And response is 200

  Scenario: Picker token minted
    Given workspace "ws-1" with Drive connected
    When GET /api/workspaces/ws-1/drive/picker-token
    Then response contains a short-lived access_token and picker_api_key

  Scenario: Large file returns truncation warning
    Given workspace "ws-1" with Drive connected and BYOK key
    When POST /api/workspaces/ws-1/knowledge with a file exceeding 50K chars
    Then the file is indexed successfully
    And the response includes "warning": "File content truncated to 50,000 characters..."

  Scenario: Concurrent indexing is serialized
    Given workspace "ws-1" with Drive connected and BYOK key
    When two POST /api/workspaces/ws-1/knowledge requests arrive simultaneously
    Then they are processed sequentially (not in parallel)
    And both files are indexed correctly
    And the file count is accurate
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_knowledge_routes.py` passes
- [ ] Full backend suite passes
- [ ] 15-file DB trigger tested (if existing migration has it)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | STORY-006-01 (drive_service, scan_service) and STORY-006-02 (drive_oauth routes) merged | [ ] |
| **Migrations** | `003_teemo_knowledge_index.sql` already applied (existing) | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_knowledge_routes.py` — test all endpoints, mock Drive + scan services
- Create `backend/app/models/knowledge.py` — request/response Pydantic models

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/knowledge.py` (new) |
| **Related Files** | `backend/app/models/knowledge.py` (new), `backend/app/services/drive_service.py` (from 006-01), `backend/app/services/scan_service.py` (from 006-01), `backend/app/main.py` (mount router) |
| **New Files Needed** | Yes — `knowledge.py` (routes), `knowledge.py` (models) |
| **ADR References** | ADR-005 (real-time Drive read), ADR-006 (AI description), ADR-007 (15-cap) |
| **First-Use Pattern** | No — follows keys.py workspace-scoped route pattern |

### 3.3 Technical Logic

**POST /api/workspaces/{id}/knowledge flow:**
1. Verify ownership (`_assert_workspace_owner`)
2. Check Drive connected (refresh token not null)
3. Check BYOK key exists (encrypted_api_key not null)
4. Check file count < 15
5. Check MIME type in allowed list
6. Check no duplicate `(workspace_id, drive_file_id)`
7. `get_drive_client(encrypted_refresh_token)` → fetch content → hash → AI description
8. Insert into `teemo_knowledge_index`
9. Return created row

**GET picker-token flow:**
1. Verify ownership
2. Decrypt refresh token → exchange for access token (do NOT store)
3. Return `{ access_token, picker_api_key: settings.google_picker_api_key }`

### 3.4 API Contract
| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/workspaces/{id}/knowledge` | POST | JWT | `{ drive_file_id, title, link, mime_type }` | `{ id, drive_file_id, title, link, mime_type, ai_description, content_hash, created_at }` |
| `/api/workspaces/{id}/knowledge` | GET | JWT | — | `[{ id, drive_file_id, title, link, mime_type, ai_description, last_scanned_at, created_at }]` |
| `/api/workspaces/{id}/knowledge/{kid}` | DELETE | JWT | — | `{ status: "deleted" }` |
| `/api/workspaces/{id}/drive/picker-token` | GET | JWT | — | `{ access_token, picker_api_key }` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Integration tests | 9 | 1 per Gherkin scenario |
| Unit tests | 2 | Model validation, MIME check helper |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
- [ ] 15-file cap tested.
- [ ] Router mounted in `main.py`.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| QA | 15 | 689 | 704 |
