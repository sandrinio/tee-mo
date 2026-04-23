---
status: "red-phase-complete"
correction_tax: 0
input_tokens: 30
output_tokens: 1071
total_tokens: 1101
tokens_used: 1468
tests_written: 12
files_modified:
  - ".worktrees/STORY-006-08-multimodal-fallback/backend/tests/test_drive_service.py"
  - ".worktrees/STORY-006-08-multimodal-fallback/backend/tests/test_scan_service.py"
flashcards_flagged: 0
---

# Developer RED Phase Report: STORY-006-08-multimodal-fallback

## Files Modified

- `.worktrees/STORY-006-08-multimodal-fallback/backend/tests/test_drive_service.py` — Added `TestMultimodalFallback` class (7 tests) covering all multimodal fallback scenarios. Also updated the module docstring to list the new scenarios and added `AsyncMock` to the import line.
- `.worktrees/STORY-006-08-multimodal-fallback/backend/tests/test_scan_service.py` — Added `TestExtractContentMultimodal` class (5 tests) covering `extract_content_multimodal` function behavior.

## Logic Summary

### TestMultimodalFallback (test_drive_service.py — 7 tests)

The new class tests the async `fetch_file_content` function's multimodal fallback behavior. Two helper functions (`_make_scanned_pdf_mocks`, `_make_normal_pdf_mocks`) set up pymupdf/pymupdf4llm mocks and a custom `_fake_downloader` that writes raw bytes into the BytesIO buffer (replacing `MediaIoBaseDownload`). This allows full control over both the text extraction result and the raw PDF byte size.

The `extract_content_multimodal` import is lazy inside the implementation (inside the function body), so the tests mock it at `app.services.scan_service.extract_content_multimodal` using `unittest.mock.patch` as a context manager. This intercepts the lazy import correctly regardless of module caching.

Tests cover: google provider calls fallback, openai provider calls fallback, anthropic provider does NOT call fallback (warning emitted), oversized PDF does NOT call fallback (warning emitted), normal PDF with provider does NOT trigger fallback, no provider is backwards-compatible, and multimodal output >50K chars is truncated.

### TestExtractContentMultimodal (test_scan_service.py — 5 tests)

These tests verify the new `extract_content_multimodal(pdf_bytes, provider, api_key)` function. They reuse the existing `_patch_agent_module_globals` helper to inject mocks into the agent module globals, preventing real LLM calls. Tests verify: GoogleModel is built with `SCAN_TIER_MODELS["google"]`, OpenAIChatModel is built with `SCAN_TIER_MODELS["openai"]`, `agent.run()` is called with the PDF content, the result string is returned from `result.output`, and the API key is forwarded to the provider constructor.

## Test Discovery and RED Verification

All 12 tests are discovered by pytest. Running them produces:

- `TestMultimodalFallback` (7 tests): **SKIPPED** — `drive_service` cannot be imported in the local env because `pymupdf4llm` is not installed. This is the same behavior as the existing STORY-006-07 tests for the same class. In CI (Docker with the full dependency set), these tests will FAIL instead of skip until the implementation is provided.
- `TestExtractContentMultimodal` (5 tests): **FAILED** — `scan_service` is importable but `extract_content_multimodal` does not exist yet (`AttributeError: module 'app.services.scan_service' has no attribute 'extract_content_multimodal'`). This is correct RED behavior.

## Mock Strategy Decisions

**`_fake_downloader` instead of `MagicMock` for `MediaIoBaseDownload`**: The existing `_make_downloader_mock` helper uses `monkeypatch.setattr` on the `MediaIoBaseDownload` class but doesn't write bytes to the buffer. For multimodal tests, the raw bytes need to reach the fallback decision logic (size check), so the fake downloader writes the bytes into the BytesIO buffer directly.

**`patch("app.services.scan_service.extract_content_multimodal", ...)` as context manager**: The lazy import means `monkeypatch.setattr(drive_service, ...)` won't work (there's no module-level reference to patch). Using `unittest.mock.patch` on the full dotted path intercepts the import at the scan_service module level.

## Correction Tax

- Self-assessed: 0%
- Human interventions needed: None

## Flashcards Flagged

- None new — the lazy-import mock pattern (patch full dotted path) is already established in the codebase.

## Product Docs Affected

- None

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) — they FAIL/SKIP (no implementation exists)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (docstrings on all helpers and classes)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The `_make_downloader_mock` helper in the existing test file patches `MediaIoBaseDownload` as a class mock but does not write bytes into the BytesIO buffer — for the new fallback tests that need to check the size of the raw PDF bytes, a new `_fake_downloader` closure was required. This gap could be noted in FLASHCARDS.md if reuse is expected in future stories.
