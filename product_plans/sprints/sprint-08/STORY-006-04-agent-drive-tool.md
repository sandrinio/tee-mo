---
story_id: "STORY-006-04-agent-drive-tool"
parent_epic_ref: "EPIC-006"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1 / Charter §5.1 step 9 / Roadmap ADR-005, ADR-006"
actor: "Slack User"
complexity_label: "L2"
---

# STORY-006-04: Agent `read_drive_file` Tool + System Prompt File Catalog

**Complexity: L2** — Modifies existing agent.py, known pattern

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack User**,
> I want the **bot to read my team's Drive files when answering questions**,
> So that **I get answers grounded in our actual documents**.

### 1.2 Detailed Requirements
- **R1**: New agent tool `read_drive_file(drive_file_id: str) -> str` — fetches file content via `drive_service.fetch_file_content`, self-heals stale metadata (if content hash changed → re-generate AI description via `scan_service`, update DB row), returns file content to agent.
- **R2**: `_build_system_prompt(skills, knowledge_files)` — accepts a new `knowledge_files` parameter (list of dicts with `drive_file_id`, `title`, `ai_description`). If non-empty, appends an `## Available Files` section listing each file: `- [drive_file_id] "Title" — ai_description`. Agent uses this to decide which file to read.
- **R3**: `build_agent()` — at construction time, query `teemo_knowledge_index` for workspace's files. Pass to `_build_system_prompt`. Wire `read_drive_file` tool into agent tools list.
- **R4**: `read_drive_file` needs the workspace's `encrypted_google_refresh_token` to build the Drive client. Fetch it from workspace row at tool call time (via `ctx.deps`).
- **R5**: If workspace has no Drive files, omit `## Available Files` entirely (no empty section).
- **R6**: If `read_drive_file` encounters `invalid_grant` (revoked token), return a user-friendly message: "Google Drive access has been revoked. Please reconnect Drive from the dashboard."

### 1.3 Out of Scope
- Wiki pipeline (EPIC-013)
- Frontend (STORY-006-05)
- Context window overflow handling / pruning (EPIC-009)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Agent Drive Tool

  Scenario: System prompt includes file catalog
    Given workspace has 3 indexed files
    When build_agent is called
    Then the system prompt contains "## Available Files"
    And lists all 3 files with drive_file_id, title, and ai_description

  Scenario: System prompt omits file section when no files
    Given workspace has 0 indexed files
    When build_agent is called
    Then the system prompt does NOT contain "## Available Files"

  Scenario: read_drive_file returns content
    Given a valid drive_file_id indexed in workspace
    When the agent calls read_drive_file
    Then it fetches file content via Drive API
    And returns the content string to the agent

  Scenario: read_drive_file self-heals stale metadata
    Given an indexed file whose content has changed (hash mismatch)
    When read_drive_file is called
    Then it detects the hash change
    And re-generates the AI description via scan-tier model
    And updates content_hash, ai_description, last_scanned_at in teemo_knowledge_index
    And returns the updated content

  Scenario: read_drive_file handles revoked token
    Given the workspace's Google refresh token has been revoked
    When read_drive_file is called
    Then it returns "Google Drive access has been revoked. Please reconnect Drive from the dashboard."

  Scenario: read_drive_file rejects unknown file ID
    Given a drive_file_id NOT in workspace's knowledge_index
    When read_drive_file is called
    Then it returns "File not found in this workspace's knowledge base."
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_agent_factory.py` passes (existing + new tests)
- [ ] Full backend suite passes
- [ ] System prompt renders correctly with files

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | STORY-006-01 (drive_service, scan_service) merged | [ ] |
| **Dependencies** | STORY-006-03 (knowledge routes — files exist in DB) merged or at least migration applied | [ ] |

### 3.1 Test Implementation
- Modify `backend/tests/test_agent_factory.py` — add tests for system prompt with files, read_drive_file tool, self-healing, error cases
- Mock Drive service calls (do NOT call real Google API)

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/agents/agent.py` (modify) |
| **Related Files** | `backend/app/services/drive_service.py` (from 006-01), `backend/app/services/scan_service.py` (from 006-01) |
| **New Files Needed** | No |
| **ADR References** | ADR-005 (real-time Drive read), ADR-006 (self-healing AI description) |
| **First-Use Pattern** | No — extends existing tool pattern |

### 3.3 Technical Logic

**Modify `_build_system_prompt`:**
```python
def _build_system_prompt(skills: list[dict], knowledge_files: list[dict] | None = None) -> str:
    # ... existing preamble + skills section ...
    if knowledge_files:
        file_lines = "\n".join(
            f"- [{f['drive_file_id']}] \"{f['title']}\" — {f['ai_description']}"
            for f in knowledge_files
        )
        prompt += f"\n\n## Available Files\n{file_lines}"
    return prompt
```

**New tool in `build_agent`:**
```python
async def read_drive_file(ctx: Any, drive_file_id: str) -> str:
    """Read a Google Drive file from the workspace knowledge base."""
    # 1. Lookup file in knowledge_index by (workspace_id, drive_file_id)
    # 2. If not found → return error
    # 3. Fetch workspace row for encrypted_google_refresh_token
    # 4. get_drive_client → fetch_file_content
    # 5. Compare hash. If changed → scan_service.generate_ai_description → update DB
    # 6. Return content
```

**Modify `build_agent` step 7.5 (after skills, before constructing Agent):**
```python
# Fetch knowledge files for system prompt
knowledge_result = supabase.table("teemo_knowledge_index") \
    .select("drive_file_id, title, ai_description") \
    .eq("workspace_id", workspace_id) \
    .execute()
knowledge_files = knowledge_result.data or []
prompt = _build_system_prompt(skills, knowledge_files)
```

Add `read_drive_file` to the tools list alongside skill tools.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 6 | 1 per Gherkin scenario |
| Integration tests | 0 | N/A — agent factory tests are unit-level with mocks |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
- [ ] `read_drive_file` tool registered in agent tools list.
- [ ] System prompt correctly renders file catalog.
- [ ] Self-healing hash check works.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 16 | 341 | 357 |
