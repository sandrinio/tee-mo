---
story_id: "STORY-006-01-drive-service"
parent_epic_ref: "EPIC-006"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §4.1, §4.5 / Charter §3.4, §5.1 step 9, §5.2 / Roadmap ADR-004, ADR-009, ADR-016"
actor: "System"
complexity_label: "L2"
---

# STORY-006-01: Drive Service + Config + Scan-Tier Model Helper

**Complexity: L2** — 2-3 files, known pattern, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story creates the foundational Drive API wrapper and scan-tier model helper that all subsequent EPIC-006 stories depend on. It adds Google env vars to `Settings` and implements the core functions: refresh-to-access token exchange, file content fetch by MIME type, content hashing, and scan-tier AI description generation.

### 1.2 Detailed Requirements
- **R1**: Add `google_api_client_id`, `google_api_secret`, `google_picker_api_key` (optional, default empty), `google_oauth_redirect_uri` to `Settings` in `config.py`.
- **R2**: `drive_service.py` — `get_drive_client(encrypted_refresh_token)`: decrypts refresh token, exchanges for access token via `google.oauth2.credentials.Credentials`, returns an authorized `googleapiclient.discovery.build("drive", "v3")` client.
- **R3**: `drive_service.py` — `fetch_file_content(drive_client, drive_file_id, mime_type) -> str`: branches by MIME type per ADR-016. Google Docs/Slides → `files.export(mimeType="text/plain")`, Sheets → `files.export(mimeType="text/csv")`, PDF → `files.get_media()` + `pypdf`, Word → `files.get_media()` + `python-docx`, Excel → `files.get_media()` + `openpyxl`. Truncate at 50K chars with trim notice.
- **R4**: `drive_service.py` — `compute_content_hash(content: str) -> str`: MD5 hex digest of content string.
- **R5**: `scan_service.py` — `generate_ai_description(content, provider, api_key) -> str`: builds scan-tier model (per ADR-004 mapping: google→`gemini-2.5-flash`, anthropic→`claude-haiku-4-5`, openai→`gpt-4o-mini`), sends prompt "Summarize this document in 2-3 sentences, focusing on what questions it answers.", returns the summary.
- **R6**: Scan-tier model builder reuses `_ensure_model_imports` and `_build_pydantic_ai_model` from `agent.py` — do NOT duplicate the lazy import pattern.

### 1.3 Out of Scope
- OAuth flow (STORY-006-02)
- REST routes for knowledge CRUD (STORY-006-03)
- Agent tool integration (STORY-006-04)
- Frontend (STORY-006-05)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Drive Service + Scan-Tier

  Scenario: Config loads Google env vars
    Given GOOGLE_API_CLIENT_ID and GOOGLE_API_SECRET are set in .env
    When Settings() is instantiated
    Then google_api_client_id and google_api_secret are populated
    And google_picker_api_key defaults to empty string if not set

  Scenario: Fetch Google Docs content
    Given a drive client and a file with mime_type "application/vnd.google-apps.document"
    When fetch_file_content is called
    Then it calls files.export with mimeType="text/plain"
    And returns the plain text content

  Scenario: Fetch PDF content
    Given a drive client and a file with mime_type "application/pdf"
    When fetch_file_content is called
    Then it downloads the binary via files.get_media
    And extracts text via pypdf
    And returns the extracted text

  Scenario: Content truncation
    Given file content exceeding 50000 characters
    When fetch_file_content is called
    Then the returned content is truncated to 50000 chars
    And a trim notice is appended

  Scenario: Content hash computation
    Given a content string
    When compute_content_hash is called
    Then it returns the MD5 hex digest of the string

  Scenario: Scan-tier generates AI description
    Given file content and a workspace with provider "anthropic" and api_key
    When generate_ai_description is called
    Then it uses claude-haiku-4-5 (scan tier for anthropic)
    And returns a 2-3 sentence summary
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_drive_service.py` passes
- [ ] `pytest backend/tests/test_scan_service.py` passes
- [ ] Settings loads without error with Google env vars present
- [ ] Settings loads without error with Google env vars absent (picker key optional)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `GOOGLE_API_CLIENT_ID`, `GOOGLE_API_SECRET` in `.env` | [ ] |
| **Dependencies** | `google-api-python-client`, `google-auth`, `pypdf`, `python-docx`, `openpyxl` in pyproject.toml | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_drive_service.py` — mock Google API calls, test each MIME branch, test truncation, test hash
- Create `backend/tests/test_scan_service.py` — mock Pydantic AI agent run, test scan-tier model selection per provider

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/drive_service.py` (new) |
| **Related Files** | `backend/app/services/scan_service.py` (new), `backend/app/core/config.py` (modify), `backend/app/agents/agent.py` (read — reuse model builder) |
| **New Files Needed** | Yes — `drive_service.py`, `scan_service.py` |
| **ADR References** | ADR-004 (two-tier models), ADR-009 (offline refresh token), ADR-016 (MIME types) |
| **First-Use Pattern** | Yes — Google Drive API client, `google.oauth2.credentials.Credentials` refresh flow, pypdf/python-docx/openpyxl text extraction |

### 3.3 Technical Logic

**drive_service.py:**
```python
from app.core.encryption import decrypt

def get_drive_client(encrypted_refresh_token: str):
    """Decrypt refresh token, exchange for access token, return Drive client."""
    refresh_token = decrypt(encrypted_refresh_token)
    creds = google.oauth2.credentials.Credentials(
        token=None,
        refresh_token=refresh_token,
        client_id=settings.google_api_client_id,
        client_secret=settings.google_api_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(google.auth.transport.requests.Request())
    return googleapiclient.discovery.build("drive", "v3", credentials=creds)

def fetch_file_content(drive_client, drive_file_id: str, mime_type: str) -> str:
    """Fetch file content, branch by MIME type. Truncate at 50K chars."""
    # Branch by mime_type...
    # Truncate if > 50_000 chars
    # Return content string

def compute_content_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()
```

**scan_service.py:**
```python
SCAN_TIER_MODELS = {
    "google": "gemini-2.5-flash",
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
}

async def generate_ai_description(content: str, provider: str, api_key: str) -> str:
    """Use scan-tier model to generate 2-3 sentence summary."""
    model_id = SCAN_TIER_MODELS[provider]
    # Reuse _ensure_model_imports + _build_pydantic_ai_model from agent.py
    # Run agent with summarization prompt
    # Return result text
```

**FLASHCARDS rules to obey:**
- Import `httpx` at module level (if used)
- Use `from app.core.encryption import decrypt` — never call AESGCM directly

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 8 | 6 MIME branches + truncation + hash |
| Integration tests | 2 | scan-tier model selection per provider (mocked LLM) |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted.
- [ ] No ADR violations.
- [ ] All 6 MIME types handled per ADR-016.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
