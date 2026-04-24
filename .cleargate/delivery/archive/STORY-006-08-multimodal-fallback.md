---
story_id: "STORY-006-08"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-006_google_drive/STORY-006-08-multimodal-fallback.md`. Shipped in sprint S-08, carried forward during ClearGate migration 2026-04-24.

# STORY-006-08: Multimodal LLM Fallback for Scanned PDFs

**Complexity: L2** — 3 files, known patterns, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack User**,
> I want the bot to extract readable content from scanned (image-based) PDFs,
> So that I can ask questions about scanned documents and get accurate answers.

### 1.2 Detailed Requirements

- **R1: Fallback trigger** — If `_extract_pdf` (pymupdf4llm from STORY-006-07) returns <100 characters of stripped text for a PDF, the file is likely scanned/image-based. Trigger multimodal fallback.
- **R2: Multimodal extraction** — Send raw PDF bytes to the scan-tier multimodal model for content extraction. The model extracts text, tables, and structure from the scanned images and returns markdown.
- **R3: Provider support** — Only Google (Gemini Flash) and OpenAI (GPT-4o-mini) support multimodal PDF input. Anthropic does not — return best-effort pymupdf4llm text + warning.
- **R4: Size limit** — If the scanned PDF exceeds 20MB, skip multimodal fallback and return best-effort text + warning. Multimodal APIs cap at ~20MB.
- **R5: BYOK-only** — Multimodal fallback uses the user's own BYOK key, scan-tier model. No cross-provider calls. No new env vars.
- **R6: `fetch_file_content` signature extension** — Add optional keyword params `provider` and `api_key` for the fallback path. When not provided, no fallback occurs (backwards-compatible).
- **R7: `read_drive_file` tool update** — Pass workspace provider and decrypted API key to `fetch_file_content` so the fallback can fire at query time.
- **R8: `fetch_file_content` becomes async** — The multimodal fallback calls `extract_content_multimodal` which is async (runs a Pydantic AI agent). `fetch_file_content` must become `async def`. Update the single caller in `agent.py` to `await` it. Also update the sync caller in `knowledge.py` (file indexing route) — wrap with `asyncio` or make the indexing path async.

### 1.3 Out of Scope
- Per-page multimodal fallback for mixed PDFs (text + scanned pages) — accepted gap for V1
- Multimodal fallback for non-PDF file types (only PDFs can be scanned)
- Changing the scan-tier model mapping (stays Gemini Flash / GPT-4o-mini / Haiku)
- Any frontend changes

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Multimodal LLM Fallback for Scanned PDFs

  Scenario: Scanned PDF triggers multimodal fallback (Google provider)
    Given a PDF where pymupdf4llm extraction returns only 50 characters
    And the workspace provider is "google" and api_key is provided
    And the PDF is under 20MB
    When fetch_file_content is called with provider and api_key
    Then extract_content_multimodal is called with raw PDF bytes, "google", and the api_key
    And the returned text is the multimodal model's extraction output

  Scenario: Scanned PDF triggers multimodal fallback (OpenAI provider)
    Given a PDF where pymupdf4llm extraction returns only 30 characters
    And the workspace provider is "openai" and api_key is provided
    And the PDF is under 20MB
    When fetch_file_content is called with provider and api_key
    Then extract_content_multimodal is called with raw PDF bytes, "openai", and the api_key
    And the returned text is the multimodal model's extraction output

  Scenario: Scanned PDF with Anthropic provider returns warning
    Given a PDF where pymupdf4llm extraction returns only 50 characters
    And the workspace provider is "anthropic"
    When fetch_file_content is called with provider and api_key
    Then extract_content_multimodal is NOT called
    And the returned text includes the pymupdf4llm output (50 chars)
    And the returned text includes "scanned document" warning text

  Scenario: Oversized scanned PDF (>20MB) skips fallback
    Given a scanned PDF of 25MB where pymupdf4llm returns <100 characters
    And the workspace provider is "google"
    When fetch_file_content is called with provider and api_key
    Then extract_content_multimodal is NOT called
    And the returned text includes a "too large for AI-assisted extraction" warning

  Scenario: Normal PDF (>100 chars extracted) does NOT trigger fallback
    Given a PDF where pymupdf4llm extraction returns 5,000 characters
    And provider and api_key are provided
    When fetch_file_content is called
    Then extract_content_multimodal is NOT called
    And the returned text is the pymupdf4llm output (no warning appended)

  Scenario: No provider/api_key provided — no fallback
    Given a PDF where pymupdf4llm extraction returns only 50 characters
    And provider and api_key are NOT provided (None)
    When fetch_file_content is called without keyword args
    Then extract_content_multimodal is NOT called
    And the returned text is the pymupdf4llm output as-is (backwards compatible)

  Scenario: read_drive_file passes provider and api_key
    Given a workspace with provider "google" and an encrypted API key
    When the agent calls read_drive_file for a Drive file
    Then fetch_file_content is called with provider="google" and the decrypted api_key

  Scenario: Truncation applies after multimodal fallback
    Given a scanned PDF where multimodal extraction returns 60,000 characters
    When fetch_file_content processes the result
    Then the content is truncated at 50,000 characters
    And "[Content truncated at 50000 characters]" is appended
```

### 2.2 Verification Steps (Manual)
- [ ] Test with a known scanned PDF (if available) using Google or OpenAI provider → multimodal fallback fires, readable content extracted
- [ ] Test same scanned PDF with Anthropic provider → warning appears, no crash
- [ ] Test a normal text-based PDF → no fallback triggered, output unchanged from STORY-006-07

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-006-07 merged (pymupdf4llm extractors in place) | [ ] |
| **Services Running** | Backend dev server | [ ] |
| **Env Vars** | No new env vars needed | [x] |

### 3.1 Test Implementation

- Modify `backend/tests/test_drive_service.py`:
  - Test: pymupdf4llm returns <100 chars, provider="google", size <20MB → `extract_content_multimodal` called
  - Test: pymupdf4llm returns <100 chars, provider="openai" → fallback called
  - Test: pymupdf4llm returns <100 chars, provider="anthropic" → fallback NOT called, warning appended
  - Test: pymupdf4llm returns <100 chars, size >20MB → fallback NOT called, warning appended
  - Test: pymupdf4llm returns >100 chars → fallback NOT called, no warning
  - Test: no provider/api_key → fallback NOT called (backwards compatible)
  - Test: multimodal output exceeds 50K → truncation applies
- Add test in `backend/tests/test_scan_service.py`:
  - Test: `extract_content_multimodal()` builds scan-tier agent and runs with PDF content

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/drive_service.py` |
| **Related Files** | `backend/app/services/scan_service.py`, `backend/app/agents/agent.py` (read_drive_file tool), `backend/app/api/routes/knowledge.py` (indexing caller), `backend/tests/test_drive_service.py`, `backend/tests/test_scan_service.py` |
| **New Files Needed** | No |
| **ADR References** | ADR-004 (scan tier models), ADR-005 (Drive read), ADR-016 (MIME types) |
| **First-Use Pattern** | Yes — Pydantic AI multimodal input (check 1.79 docs for binary/PDF content API) |

### 3.3 Technical Logic

#### 3.3.1 `drive_service.py` — constants

Add at module level:

```python
_SCANNED_PDF_WARNING = (
    "\n\n[Warning: This file appears to be a scanned document. "
    "Text extraction is limited for this provider. Consider using "
    "Google or OpenAI as your AI provider for better scanned document support.]"
)
_OVERSIZED_PDF_WARNING = (
    "\n\n[Warning: This scanned document is too large for "
    "AI-assisted extraction. Text shown is best-effort.]"
)
_MULTIMODAL_FALLBACK_THRESHOLD = 100
_MULTIMODAL_SIZE_LIMIT = 20_000_000  # 20MB
```

#### 3.3.2 `fetch_file_content` — signature + async + fallback

Change the function signature. The function must become `async` because the multimodal fallback is async:

```python
async def fetch_file_content(
    drive_client, drive_file_id: str, mime_type: str,
    *, provider: str | None = None, api_key: str | None = None,
) -> str:
```

After the PDF extraction branch (`content = _extract_pdf(raw_bytes)`), add fallback logic:

```python
elif mime_type == "application/pdf":
    raw_bytes = _download_media(drive_client, drive_file_id)
    content = _extract_pdf(raw_bytes)

    # Multimodal fallback for scanned/image-based PDFs
    if len(content.strip()) < _MULTIMODAL_FALLBACK_THRESHOLD and provider and api_key:
        if provider in ("google", "openai") and len(raw_bytes) <= _MULTIMODAL_SIZE_LIMIT:
            from app.services.scan_service import extract_content_multimodal
            content = await extract_content_multimodal(raw_bytes, provider, api_key)
        elif provider == "anthropic":
            content += _SCANNED_PDF_WARNING
        elif len(raw_bytes) > _MULTIMODAL_SIZE_LIMIT:
            content += _OVERSIZED_PDF_WARNING
```

**Important:** Since `fetch_file_content` becomes async, update all callers:
1. `agent.py` line 672: already inside an `async` function — add `await`
2. `knowledge.py` indexing route: check if it's already async. If yes, add `await`. If sync, wrap or make async.

#### 3.3.3 `scan_service.py` — `extract_content_multimodal()`

```python
async def extract_content_multimodal(
    pdf_bytes: bytes, provider: str, api_key: str,
) -> str:
    """Extract text from a scanned PDF using multimodal scan-tier model.

    Sends raw PDF bytes to the model for content extraction.
    Only supports Google (Gemini Flash) and OpenAI (GPT-4o-mini).

    Args:
        pdf_bytes: Raw PDF file bytes.
        provider:  "google" or "openai" (Anthropic not supported).
        api_key:   Decrypted plaintext BYOK API key.

    Returns:
        Extracted text content as markdown.
    """
    model_id = SCAN_TIER_MODELS[provider]
    _agent_module._ensure_model_imports(provider)
    model = _agent_module._build_pydantic_ai_model(model_id, provider, api_key)

    scan_agent = _agent_module.Agent(
        model,
        system_prompt=(
            "Extract all text content from this PDF document. "
            "Preserve tables as markdown tables. "
            "Preserve headings and structure."
        ),
    )

    # Developer MUST check Pydantic AI 1.79 docs for the correct way to
    # pass binary PDF content to a multimodal model. Options may include:
    #   - pydantic_ai.messages.BinaryContent
    #   - Provider-specific attachment APIs
    #   - Base64-encoded content in a UserMessage
    # The key requirement: send the PDF bytes, receive extracted text.
    import base64
    b64_pdf = base64.b64encode(pdf_bytes).decode()
    result = await scan_agent.run(
        f"Extract all text from the following base64-encoded PDF:\n{b64_pdf}"
    )
    return result.output
```

**Note:** The base64 approach above is a fallback. The Developer agent should first check if Pydantic AI 1.79 has native multimodal content support (e.g., `BinaryPart`, `ImageUrl`, or provider-specific wrappers). If native support exists, use it instead of base64 — it's more token-efficient and models handle it better.

#### 3.3.4 `agent.py` — `read_drive_file` tool update

Current code (line 672):
```python
content = fetch_file_content(drive_client, drive_file_id, file_row["mime_type"])
```

Change to:
```python
api_key_plain = _decrypt_key(ws_row["encrypted_api_key"])
content = await fetch_file_content(
    drive_client, drive_file_id, file_row["mime_type"],
    provider=ws_row["ai_provider"],
    api_key=api_key_plain,
)
```

Move the `_decrypt_key` call before `fetch_file_content` (it's currently done later at line 679 for self-healing). Reuse `api_key_plain` for both the fallback and the self-healing description generation.

#### 3.3.5 `knowledge.py` — indexing route caller

Check the file indexing route that calls `fetch_file_content` at index time. It currently doesn't need multimodal fallback (indexing extracts content for hash + AI description — if the PDF is scanned, the AI description generator can still summarize whatever text is available). Two options:

- **Option A (recommended):** Don't pass provider/api_key from the indexing route. Multimodal fallback only triggers at query time (via `read_drive_file`). The indexing path stays sync-compatible and doesn't burn extra BYOK tokens.
- **Option B:** Pass provider/api_key from indexing too, so the indexed content hash reflects the multimodal-extracted content. But this changes the async boundary.

Go with **Option A** — the indexing route calls `fetch_file_content` without the new kwargs, so it stays backwards-compatible. Only `read_drive_file` passes the kwargs. If `fetch_file_content` becomes async, the indexing route needs `await` but the fallback branch won't trigger (no provider/api_key).

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 8 | Fallback triggered (google), fallback triggered (openai), anthropic warning, oversized warning, normal PDF no fallback, no provider no fallback, truncation after fallback, extract_content_multimodal basic |
| Integration tests | 0 | N/A — no new API endpoints |
| E2E / acceptance tests | 0 | Manual verification (§2.2) |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations (§4.1) met — 8+ unit tests.
- [ ] FLASHCARDS.md consulted (monkeypatch import patterns, async test patterns).
- [ ] No violations of ADR-004 (scan tier), ADR-005 (Drive read).
- [ ] `fetch_file_content` callers updated for async.
- [ ] `read_drive_file` in `agent.py` passes provider + api_key.
- [ ] Pydantic AI 1.79 multimodal API verified (not guessed).
- [ ] Existing tests still pass after async conversion.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 33 | 1,435 | 1,468 |
