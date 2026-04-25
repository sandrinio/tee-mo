---
story_id: "STORY-014-01-extraction-service-refactor"
parent_epic_ref: "EPIC-014"
status: "Draft"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
actor: "Backend Developer"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-pre-S15"
updated_at_version: "cleargate-pre-S15"
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

# STORY-014-01: Extraction Service Refactor

**Complexity: L1** — Pure code move. Six private functions migrate from `drive_service.py` to a new `extraction_service.py`. No behavior change, no schema change, no new tests required beyond regression coverage.

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **Backend Developer**, I want the file-extraction logic (PDF / DOCX / XLSX → text/markdown) to live in a service module that does not depend on Google Drive, so that the upcoming local-upload endpoint (STORY-014-02) can reuse it without dragging in the Drive client.

### 1.2 Detailed Requirements
- **R1.** Create `backend/app/services/extraction_service.py`. Export the following public callables (rename from leading-underscore private to no-underscore public during the move):
  - `extract_pdf(raw_bytes: bytes) -> str`
  - `extract_docx(raw_bytes: bytes) -> str`
  - `extract_xlsx(raw_bytes: bytes) -> str`
  - `maybe_truncate(content: str) -> str`
  - `rows_to_markdown_table(rows: list[tuple]) -> str`
  - `docx_table_to_markdown(table) -> str`
- **R2.** Update `backend/app/services/drive_service.py` to `import` the six functions from `extraction_service` and call them at every existing call-site. Remove the now-duplicate definitions from `drive_service.py`.
- **R3.** Module-level constants the extractors depend on (e.g. truncation threshold) move with them to `extraction_service.py`. `drive_service.py` re-imports if any code outside the extractors still needs them.
- **R4.** No public API change. No route, model, agent, or frontend change. No DB migration.

### 1.3 Out of Scope
- New extractor formats (TXT/MD trivial-decode path is added in STORY-014-02, not here).
- Extractor improvements (encoding fallbacks, OCR, multimodal) — pure relocation only.
- Renaming or restructuring `_download_media`, `fetch_file_content`, or any Drive-specific function — those stay in `drive_service.py`.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)

```gherkin
Feature: Extraction Service Module Boundary

  Scenario: Drive ingestion still extracts text after the move
    Given a PDF file is fetched via Google Drive
    When fetch_file_content runs
    Then the resulting text matches the byte-for-byte output produced before the refactor

  Scenario: Extraction service is importable with no Drive client
    Given a process that has never imported drive_service
    When extraction_service is imported and extract_pdf is called on raw bytes
    Then the call succeeds and returns extracted text

  Scenario: drive_service no longer defines the extractor functions
    Given a fresh interpreter
    When extract_pdf is looked up on the drive_service module
    Then the lookup either fails OR resolves to the re-exported reference from extraction_service (not a local definition)
```

### 2.2 Verification Steps (Manual)
- [ ] `pytest backend/tests/test_drive_service.py` — passes with zero changes to test file behavior.
- [ ] `grep -n "_extract_pdf\|_extract_docx\|_extract_xlsx" backend/app/services/drive_service.py` — returns only call-sites, no `def` lines.
- [ ] `python -c "from app.services.extraction_service import extract_pdf, extract_docx, extract_xlsx, maybe_truncate, rows_to_markdown_table, docx_table_to_markdown; print('ok')"` — prints `ok`.

---

## 3. The Implementation Guide

### 3.1 Context & Files

| Item | Value |
|---|---|
| Primary File | `backend/app/services/extraction_service.py` (NEW) |
| Related Files | `backend/app/services/drive_service.py` (modify imports + delete defs) |
| New Files Needed | Yes — `extraction_service.py` |

### 3.2 Technical Logic
1. Copy the six function bodies (`_extract_pdf`, `_extract_docx`, `_extract_xlsx`, `_maybe_truncate`, `_rows_to_markdown_table`, `_docx_table_to_markdown`) from `drive_service.py` into a new module. Drop the leading underscore on the public names.
2. Move any module-level imports the extractors depend on (e.g. `pymupdf4llm`, `python-docx`, `openpyxl`) — these stay only in `extraction_service.py` if `drive_service.py` does not also use them directly.
3. In `drive_service.py`, replace each `def _extract_pdf(...):` block with `from app.services.extraction_service import extract_pdf as _extract_pdf` (or update the call-sites directly to use the public name — pick one and apply consistently).
4. Run `pytest backend/tests/test_drive_service.py backend/tests/test_drive_oauth.py` to confirm zero regression.
5. Confirm no other module imports `_extract_pdf` etc. from `drive_service`. If any do, point them at `extraction_service`.

### 3.3 API Contract (if applicable)
N/A — internal refactor.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Unit tests | 0 new | Existing Drive tests are the regression signal. |
| Regression | full | `pytest backend/tests/test_drive_service.py` passes pre and post with same counts. |

### 4.2 Definition of Done (The Gate)
- [ ] `extraction_service.py` exists with the six public functions.
- [ ] `drive_service.py` no longer defines them.
- [ ] `pytest backend/tests/` passes with the same pass/fail counts as on the sprint-tip baseline (no new failures introduced).
- [ ] `grep "_extract_" backend/app/services/drive_service.py` shows no `def` lines.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Green — Ready for Execution**

- [x] Gherkin scenarios cover R1–R4.
- [x] §3 maps to verified file paths (`drive_service.py:168–278` are the source lines per pre-flight grep).
- [x] No TBDs. No schema, no API, no UI surface — pure relocation.
