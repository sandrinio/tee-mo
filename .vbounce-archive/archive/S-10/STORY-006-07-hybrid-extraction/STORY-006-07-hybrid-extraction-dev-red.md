---
status: "red-phase-complete"
correction_tax: 5
input_tokens: 12
output_tokens: 308
total_tokens: 320
tokens_used: 476
tests_written: 15
files_modified:
  - "backend/tests/test_drive_service.py"
flashcards_flagged: 1
---

# Developer RED Phase Report: STORY-006-07-hybrid-extraction

## Files Modified
- `backend/tests/test_drive_service.py` — Rewrote/extended tests for new markdown-aware extractors. Kept all 15 passing tests from STORY-006-01, added 15 new tests that currently fail (RED confirmed).

## Test Results
- **30 tests total** collected
- **15 FAILING** (new tests — RED confirmed, all failing for correct implementation-gap reasons)
- **15 PASSING** (existing STORY-006-01 tests — unchanged functionality preserved)

### Failing Tests (RED — expected)
| Test | Reason Failing |
|------|---------------|
| `TestFetchFileContentGoogleSheets::test_exports_google_sheet_as_xlsx_not_csv` | Still uses `text/csv`, not XLSX mime |
| `TestFetchFileContentGoogleSheets::test_google_sheets_output_contains_markdown_table` | Returns raw CSV bytes decoded as string |
| `TestFetchFileContentGoogleSheets::test_google_sheets_output_contains_sheet_header` | No `## Sheet:` headers |
| `TestFetchFileContentGoogleSlides::test_google_slides_inserts_slide_boundary_markers` | No `_add_slide_markers()` implementation |
| `TestFetchFileContentPDF::test_fetches_pdf_via_get_media_and_extracts_markdown` | Module has no `pymupdf` attribute |
| `TestFetchFileContentPDF::test_pdf_markdown_contains_pipe_table` | Module has no `pymupdf` attribute |
| `TestFetchFileContentPDF::test_pdf_markdown_contains_heading_syntax` | Module has no `pymupdf` attribute |
| `TestFetchFileContentDocx::test_fetches_docx_with_tables_and_extracts_markdown` | No table extraction in `_extract_docx` |
| `TestFetchFileContentDocx::test_docx_table_rendered_as_markdown_table` | No table extraction in `_extract_docx` |
| `TestFetchFileContentXlsx::test_xlsx_outputs_sheet_name_headers` | Old implementation uses `cell.value`; no `## Sheet:` headers |
| `TestFetchFileContentXlsx::test_xlsx_outputs_pipe_separated_markdown_table` | No markdown table format |
| `TestFetchFileContentXlsx::test_xlsx_empty_sheet_skipped` | Old code crashes on tuple rows from `values_only=True` mock |
| `TestFetchFileContentXlsx::test_xlsx_none_cells_render_as_empty_not_none_string` | Old code crashes on tuple rows; outputs "None" strings |
| `TestFetchFileContentXlsx::test_xlsx_multi_sheet_all_sheets_appear` | Old code crashes on tuple rows |
| `TestContentTruncation::test_truncation_with_notice_matches_spec_text` | Module has no `pymupdf` attribute |

## Test Coverage by Gherkin Scenario
| Scenario | Test(s) | Status |
|----------|---------|--------|
| 1. PDF with tables as markdown | `test_pdf_markdown_contains_pipe_table` | FAIL (RED) |
| 2. PDF with headings preserved | `test_pdf_markdown_contains_heading_syntax` | FAIL (RED) |
| 3. PDF extractor uses pymupdf4llm | `test_fetches_pdf_via_get_media_and_extracts_markdown` | FAIL (RED) |
| 4. DOCX with tables → markdown table | `test_fetches_docx_with_tables_and_extracts_markdown`, `test_docx_table_rendered_as_markdown_table` | FAIL (RED) |
| 5. DOCX without tables (regression) | `test_docx_without_tables_returns_paragraphs_only` | PASS (old impl satisfies too) |
| 6. XLSX multi-sheet markdown tables | `test_xlsx_outputs_sheet_name_headers`, `test_xlsx_multi_sheet_all_sheets_appear` | FAIL (RED) |
| 7. XLSX empty sheet skipped | `test_xlsx_empty_sheet_skipped` | FAIL (RED) |
| 8. Google Sheets → XLSX export | `test_exports_google_sheet_as_xlsx_not_csv`, `test_google_sheets_output_contains_markdown_table`, `test_google_sheets_output_contains_sheet_header` | FAIL (RED) |
| 9. Google Slides boundary markers | `test_google_slides_inserts_slide_boundary_markers`, `test_google_slides_content_preserved_between_markers` | 1 FAIL (RED), 1 PASS |
| 10. Truncation applies to markdown | `test_truncation_with_notice_matches_spec_text` | FAIL (RED) |
| 11. None cells → empty in XLSX | `test_xlsx_none_cells_render_as_empty_not_none_string` | FAIL (RED) |

## Logic Summary
Tests are written to match the implementation described in §3.3 of the story spec. Key design decisions:

**XLSX mocks** use `values_only=True` tuple-style rows (e.g. `("A", "B", "C")`) matching the new `_extract_xlsx` implementation which will call `ws.iter_rows(values_only=True)`. The old implementation uses `cell.value` on objects — this causes the test to fail with an `AttributeError` on the old code, which is the correct RED behavior since the old code is incompatible with the new mock contract.

**PDF mocks** use `monkeypatch.setattr(drive_service, "pymupdf", ...)` and `monkeypatch.setattr(drive_service, "pymupdf4llm", ...)` — these fail immediately with `AttributeError` since the module-level imports don't exist yet in `drive_service.py`.

**DOCX table tests** build a mock `doc.element.body` that iterates paragraph and table XML elements (with fake namespace tags), matching the new `_extract_docx` implementation which iterates body elements in document order.

**Google Slides test** uses form-feed (`\x0c`) as slide separator in the export content, matching what the Drive API actually returns.

## Correction Tax
- Self-assessed: 5%
- The DOCX test had a minor bug (`mock_para.text.strip = ...` on a string attribute) that was caught immediately and fixed. All other tests were written correctly on first attempt.

## Flashcards Flagged
- **XLSX `iter_rows(values_only=True)` mock pattern**: When testing the new `_extract_xlsx`, pass tuples directly as `ws.iter_rows.return_value` (values_only style). The old implementation iterates cell objects with `.value`, so tests designed for the new API will fail with `AttributeError` on the old code — this is the correct RED behavior, not a test bug. The GREEN phase dev must call `iter_rows(values_only=True)` to make these tests pass.

## Product Docs Affected
- None — no vdocs/ changes required in RED phase.

## Status
- [x] Tests are discoverable by pytest (30 collected)
- [x] New tests FAIL (15 failing — RED confirmed)
- [x] Existing tests still PASS (15 passing — no regression)
- [x] All 10 Gherkin scenarios from §2.1 covered
- [x] FLASHCARDS.md was read before writing tests
- [x] Monkeypatch patterns use `drive_service.pymupdf` / `drive_service.pymupdf4llm` (module-level)
- [x] No implementation code written (test file ONLY modified)
- [x] Token tracking completed (count_tokens.mjs ran successfully)

## Process Feedback
- The DOCX body iteration mock is somewhat complex to set up (need to match XML tag format with namespace). The story spec §3.3.4 didn't spell out what the tag format looks like, requiring inference from python-docx internals. A brief note in §3.3 about the expected tag format (e.g. `{http://schemas.openxmlformats.org/...}p`) would reduce ambiguity for future tests.
