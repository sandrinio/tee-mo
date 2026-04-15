---
story_id: "STORY-006-07"
parent_epic_ref: "EPIC-006"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Epic §2 Scope / Codebase drive_service.py / User Input (Option C decision)"
actor: "Slack User"
complexity_label: "L2"
---

# STORY-006-07: Markdown-Aware Content Extractors

**Complexity: L2** — 1 primary file + tests, known patterns, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack User**,
> I want the bot to correctly read tables from PDFs, spreadsheets, and Word docs,
> So that the agent gives accurate answers instead of garbled text from poorly extracted content.

### 1.2 Detailed Requirements

- **R1: PDF extraction upgrade** — Replace `pypdf` with `pymupdf4llm` in `drive_service.py`. Output must be markdown preserving tables, headings, lists, and layout structure.
- **R2: Word (.docx) table extraction** — Extend `_extract_docx` to extract tables alongside paragraphs, formatting tables as markdown.
- **R3: Excel (.xlsx) markdown tables** — Rewrite `_extract_xlsx` to output markdown tables with a header row per sheet, each sheet prefixed with `## Sheet: {name}`.
- **R4: Google Sheets multi-sheet** — Change the Google Sheets export MIME from `text/csv` to `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` (XLSX), then process with the same `_extract_xlsx` function. This captures all sheets (CSV only exports the first).
- **R5: Google Slides boundaries** — Post-process Slides `text/plain` export to insert slide boundary markers (`--- Slide N ---`) using form-feed or double-newline heuristics.
- **R6: All extraction outputs remain subject to the existing 50K char truncation** (`_maybe_truncate`).
- **R7: `fetch_file_content` signature unchanged** — no new parameters in this story. Multimodal fallback is STORY-006-08.

### 1.3 Out of Scope
- Multimodal LLM fallback for scanned PDFs → STORY-006-08
- Changes to `read_drive_file` tool in `agent.py` → STORY-006-08
- Changes to `scan_service.py` → STORY-006-08
- Per-page multimodal fallback for mixed PDFs — accepted gap for V1
- Wiki pipeline (EPIC-013)
- New MIME type support beyond ADR-016's 6 types

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Markdown-Aware Content Extractors

  Scenario: PDF with tables extracted as markdown
    Given a PDF file containing a table with 3 columns and 5 rows
    When fetch_file_content is called with mime_type "application/pdf"
    Then the returned text contains a markdown table with pipe separators
    And column headers are in the first row
    And all 15 cell values are present

  Scenario: PDF with headings preserved
    Given a PDF with an H1 heading and body text
    When fetch_file_content is called
    Then the output contains markdown heading syntax ("# ...")

  Scenario: Word document with tables
    Given a DOCX file with 2 paragraphs and a 4-column table
    When fetch_file_content is called with the docx mime_type
    Then both paragraphs appear as plain text
    And the table is rendered as a markdown table with a header row
    And table cell values are preserved

  Scenario: Word document without tables (regression)
    Given a DOCX file with only paragraphs (no tables)
    When fetch_file_content is called
    Then all paragraphs are returned as plain text
    And no markdown table syntax appears

  Scenario: Excel file with multiple sheets as markdown tables
    Given an XLSX file with sheets "Q1" (3 cols, 4 rows) and "Q2" (2 cols, 3 rows)
    When fetch_file_content is called with the xlsx mime_type
    Then the output contains "## Sheet: Q1" followed by a markdown table
    And the output contains "## Sheet: Q2" followed by a markdown table
    And each table has a pipe-separated header row with separator line

  Scenario: Excel with empty sheet skipped
    Given an XLSX file with sheets "Data" (has rows) and "Empty" (no rows)
    When fetch_file_content is called
    Then the output contains "## Sheet: Data" with a table
    And "Empty" does not appear in the output

  Scenario: Google Sheets exports all sheets via XLSX
    Given a Google Sheets file with 2 sheets
    When fetch_file_content is called with mime_type "application/vnd.google-apps.spreadsheet"
    Then the Drive API export uses XLSX mime type (not CSV)
    And the result is routed through _extract_xlsx
    And the output contains markdown tables for both sheets

  Scenario: Google Slides with slide boundaries
    Given a Google Slides presentation with 3 slides
    When fetch_file_content is called with the slides mime_type
    Then the output contains "--- Slide 1 ---", "--- Slide 2 ---", "--- Slide 3 ---" markers

  Scenario: Truncation still applies to markdown output
    Given any file whose extracted markdown content exceeds 50,000 characters
    When fetch_file_content is called
    Then the content is truncated at 50,000 characters
    And "[Content truncated at 50000 characters]" is appended

  Scenario: None cells in Excel rendered as empty
    Given an XLSX file where some cells are None/empty
    When fetch_file_content is called
    Then empty cells render as empty between pipe separators ("| |")
    And no "None" string appears in the output
```

### 2.2 Verification Steps (Manual)
- [ ] Index a real PDF with tables in the dev workspace → agent correctly references table data in Slack
- [ ] Index a real XLSX with 2+ sheets → agent can answer about data from sheet 2
- [ ] Index a Google Sheets file with multiple tabs → all tab data visible to agent
- [ ] Index a DOCX with inline tables → agent reads table content accurately

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | Add `pymupdf4llm` to `pyproject.toml` | [ ] |
| **Remove** | Remove `pypdf` from `pyproject.toml` (replaced by pymupdf4llm) | [ ] |
| **Services Running** | Backend dev server | [ ] |
| **Env Vars** | No new env vars needed | [x] |

### 3.1 Test Implementation
- Modify `backend/tests/test_drive_service.py`:
  - Update PDF test: mock `pymupdf4llm.to_markdown()` instead of `PdfReader`. Verify markdown output.
  - Update DOCX test: add a table fixture alongside paragraphs. Verify markdown table in output.
  - Update XLSX test: verify `## Sheet:` headers, pipe-separated markdown table format, no "None" strings.
  - Add Google Sheets test: verify export uses XLSX mime type, output routed through `_extract_xlsx`.
  - Add Slides test: verify slide boundary markers in output.
  - Add regression test: DOCX with no tables still works (paragraphs only).
  - Add edge case test: XLSX with empty sheet — sheet is skipped.
  - Add edge case test: XLSX with None cells — render as empty.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/services/drive_service.py` |
| **Related Files** | `backend/tests/test_drive_service.py`, `pyproject.toml` |
| **New Files Needed** | No |
| **ADR References** | ADR-005 (Drive read), ADR-016 (MIME types) |
| **First-Use Pattern** | Yes — `pymupdf4llm` library (no prior codebase usage) |

### 3.3 Technical Logic

#### 3.3.1 Replace imports

Remove `from pypdf import PdfReader`. Add `import pymupdf4llm` at module level (tests monkeypatch this name).

#### 3.3.2 Markdown table helpers

Add two private helpers at the top of the module:

```python
def _rows_to_markdown_table(rows: list[tuple]) -> str:
    """Convert a list of row tuples into a pipe-separated markdown table.
    
    First row becomes the header. None values become empty strings.
    """
    if not rows:
        return ""
    
    def cell(v):
        return str(v) if v is not None else ""
    
    header = rows[0]
    col_count = len(header)
    lines = [
        "| " + " | ".join(cell(v) for v in header) + " |",
        "| " + " | ".join("---" for _ in range(col_count)) + " |",
    ]
    for row in rows[1:]:
        # Pad short rows, truncate long rows to match header width
        cells = [cell(row[i]) if i < len(row) else "" for i in range(col_count)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _docx_table_to_markdown(table) -> str:
    """Convert a python-docx Table object to a markdown table."""
    rows = []
    for row in table.rows:
        rows.append(tuple(cell.text.strip() for cell in row.cells))
    return _rows_to_markdown_table(rows)
```

#### 3.3.3 `_extract_pdf(raw_bytes)` rewrite

```python
def _extract_pdf(raw_bytes: bytes) -> str:
    """Extract text from a PDF as markdown using pymupdf4llm."""
    import pymupdf
    doc = pymupdf.open(stream=raw_bytes, filetype="pdf")
    md = pymupdf4llm.to_markdown(doc)
    doc.close()
    return md
```

#### 3.3.4 `_extract_docx(raw_bytes)` rewrite

Iterate the document body XML elements in order to interleave paragraphs and tables:

```python
def _extract_docx(raw_bytes: bytes) -> str:
    """Extract text + tables from a DOCX file, preserving document order."""
    doc = DocxDocument(io.BytesIO(raw_bytes))
    parts = []
    for element in doc.element.body:
        tag = element.tag.split("}")[-1]
        if tag == "p":
            for para in doc.paragraphs:
                if para._element is element:
                    if para.text.strip():
                        parts.append(para.text)
                    break
        elif tag == "tbl":
            for table in doc.tables:
                if table._element is element:
                    parts.append(_docx_table_to_markdown(table))
                    break
    return "\n\n".join(parts)
```

#### 3.3.5 `_extract_xlsx(raw_bytes)` rewrite

```python
def _extract_xlsx(raw_bytes: bytes) -> str:
    """Extract all sheets from an XLSX as named markdown tables."""
    wb = load_workbook(io.BytesIO(raw_bytes))
    sheet_texts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        md = f"## Sheet: {sheet_name}\n\n{_rows_to_markdown_table(rows)}"
        sheet_texts.append(md)
    return "\n\n".join(sheet_texts)
```

#### 3.3.6 Google Sheets export change

In `_GOOGLE_EXPORT_MIMES`, change the spreadsheet entry:
```python
"application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
```

In `fetch_file_content`, the Google export branch currently does `.decode("utf-8")`. Add routing for binary XLSX and Slides:
```python
if mime_type in _GOOGLE_EXPORT_MIMES:
    export_mime = _GOOGLE_EXPORT_MIMES[mime_type]
    raw = drive_client.files().export(fileId=drive_file_id, mimeType=export_mime).execute()
    if export_mime.endswith("spreadsheetml.sheet"):
        content = _extract_xlsx(raw if isinstance(raw, bytes) else raw.encode())
    elif mime_type == "application/vnd.google-apps.presentation":
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        content = _add_slide_markers(text)
    else:
        content = raw.decode("utf-8") if isinstance(raw, bytes) else raw
```

#### 3.3.7 Google Slides boundary markers

```python
def _add_slide_markers(text: str) -> str:
    """Insert slide boundary markers into Slides plain text export."""
    # Google Slides text/plain export separates slides with form-feed (\x0c)
    parts = text.split("\x0c")
    if len(parts) <= 1:
        # Fallback: split on double newlines if no form-feeds
        parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(parts) <= 1:
        return text
    return "\n\n".join(
        f"--- Slide {i + 1} ---\n{part.strip()}" for i, part in enumerate(parts)
    )
```

#### 3.3.8 `pyproject.toml`

- Add `pymupdf4llm` to `[project.dependencies]`
- Remove `pypdf` from `[project.dependencies]`

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 8 | PDF markdown, DOCX with tables, DOCX without tables (regression), XLSX multi-sheet, XLSX empty sheet, XLSX None cells, Google Sheets XLSX routing, Slides markers |
| Integration tests | 0 | N/A — no API endpoints changed |
| E2E / acceptance tests | 0 | Manual verification against real Drive files (§2.2) |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations (§4.1) met — 8+ unit tests.
- [ ] FLASHCARDS.md consulted before implementation (especially: monkeypatch import patterns).
- [ ] No violations of ADR-005 (Drive read), ADR-016 (MIME types).
- [ ] `pypdf` removed from `pyproject.toml`, `pymupdf4llm` added.
- [ ] All existing `test_drive_service.py` tests updated to pass with new extractors.
- [ ] `fetch_file_content` signature unchanged — no new parameters added in this story.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
