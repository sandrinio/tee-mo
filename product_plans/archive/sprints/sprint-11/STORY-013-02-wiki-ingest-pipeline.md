---
story_id: "STORY-013-02"
parent_epic_ref: "EPIC-013"
status: "Draft"
ambiguity: "🟡 Medium"
context_source: "EPIC-013 §2, §7 / Karpathy LLM Wiki pattern"
actor: "System"
complexity_label: "L3"
depends_on: ["STORY-013-01", "STORY-015-01"]
---

# STORY-013-02: Wiki Ingest Pipeline + Prompt Tuning

**Complexity: L3** — new service with LLM prompt engineering + iterative tuning, ~6-8hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Build `wiki_service.py` — the core ingest pipeline that takes a document from `teemo_documents` and produces wiki pages in `teemo_wiki_pages`. This includes the LLM prompt that decomposes a document into source-summary, concept, and entity pages with cross-references, and iterative tuning of that prompt against real test data.

### 1.2 Detailed Requirements

- **R1 — Ingest function**: `async def ingest_document(supabase, workspace_id, document_id, provider, api_key) → dict`:
  - Reads `content` from `teemo_documents` for the given document.
  - Calls the scan-tier LLM with a structured prompt to produce wiki pages.
  - Expected output per document: 1 source-summary + N concept pages + N entity pages.
  - Each page has: slug, title, page_type, content (markdown), tldr (≤500 chars), related_slugs.
  - Inserts all pages into `teemo_wiki_pages`.
  - Logs the operation in `teemo_wiki_log`.
  - Returns summary: `{ pages_created: int, page_types: dict }`.

- **R2 — Destructive re-ingest**: `async def reingest_document(...)`:
  - Deletes ALL wiki pages where `source_document_ids` includes the target document ID.
  - Runs full ingest from scratch.
  - Updates cross-references: scans existing pages from other documents, updates `related_slugs` where the new pages are relevant.

- **R3 — Cross-referencing**: After generating pages for a document, scan existing wiki pages in the workspace. For each new page, identify related existing pages by title/concept overlap. Update `related_slugs` on both new and existing pages.

- **R4 — Index rebuild**: `async def rebuild_wiki_index(supabase, workspace_id) → list[dict]`:
  - Returns list of `{ slug, title, tldr }` for all wiki pages in the workspace.
  - This is what gets injected into the system prompt.

- **R5 — Prompt tuning loop**: The LLM prompt for wiki page generation MUST be tuned against real test data:
  - Prepare 2-3 sample documents (real Drive content or representative markdown).
  - Run ingest, inspect generated pages for: quality, redundancy, slug clarity, TLDR usefulness, cross-ref accuracy.
  - Iterate on the prompt until pages are reliably useful.
  - Document the final prompt in the code with comments explaining key design choices.

- **R6 — Sync status transitions**: Before ingest: set `sync_status='processing'`. After successful ingest: set `sync_status='synced'`. On failure: set `sync_status='error'`.

### 1.3 Out of Scope
- Wiki ingest cron (STORY-013-03 — wires the cron to call this service)
- Lint (STORY-013-04)
- Synthesis pages created by agent during queries (deferred)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Wiki Ingest Pipeline

  Scenario: Ingest a document into wiki pages
    Given a document in teemo_documents with content about onboarding policy
    When ingest_document is called
    Then a source-summary page is created
    And concept pages are created for key themes
    And entity pages are created for named items
    And all pages have non-empty slugs, titles, TLDRs
    And sync_status is set to "synced"
    And a log entry is created in teemo_wiki_log

  Scenario: Destructive re-ingest replaces old pages
    Given a document with 8 existing wiki pages
    When reingest_document is called with updated content
    Then the 8 old pages are deleted
    And new pages are created from the updated content
    And cross-references with other documents' pages are rebuilt

  Scenario: Cross-references link related pages
    Given two documents about related topics
    When both are ingested
    Then pages from document A have related_slugs pointing to relevant pages from document B
    And vice versa

  Scenario: Wiki index rebuild returns correct format
    Given a workspace with 20 wiki pages
    When rebuild_wiki_index is called
    Then 20 entries are returned, each with slug, title, and tldr

  Scenario: Ingest failure sets error status
    Given a document whose content causes an LLM error
    When ingest_document is called
    Then sync_status is set to "error"
    And a log entry is created with error details
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **BYOK key** | Workspace must have a valid API key | [ ] |
| **Test data** | 8 files from `/Users/ssuladze/Documents/Dev/new_app/RAG_TESTING/`: `attention-is-all-you-need.pdf`, `bitcoin-whitepaper.pdf`, `company-handbook.docx`, `employee-directory.xlsx`, `financial-sample.xlsx`, `irs-pub1-taxpayer-rights.pdf`, `product-inventory.xlsx`, `technical-architecture.docx` | [ ] |

### 3.1 Files
| Item | Value |
|------|-------|
| **New files** | `backend/app/services/wiki_service.py` |
| **Reference** | Karpathy LLM Wiki gist, EPIC-013 §1.2 for page types |

### 3.2 Technical Logic

**Tiny document threshold:** Documents with `content` < 100 chars skip wiki ingest entirely. Set `sync_status='synced'` immediately. Agent reads them via `read_document` fallback.

**Ingest prompt structure** (starting point — will be tuned):
1. System prompt: "You are a wiki editor. Given a source document, produce structured wiki pages."
2. Ask the LLM to output JSON array of pages, each with: `slug`, `title`, `page_type`, `content`, `tldr`, `suggested_related_topics`.
3. Parse the JSON response. Generate slugs from titles if LLM output is inconsistent.
4. Insert pages into `teemo_wiki_pages`.
5. Cross-reference pass: for each new page's `suggested_related_topics`, search existing pages by title similarity, populate `related_slugs`.

**Tuning loop with AI judge:**

The prompt tuning loop uses the conversation-tier model to evaluate wiki page quality. This removes subjective human judgment and makes the loop repeatable.

1. **Ingest**: Run each of the 8 RAG_TESTING files through the ingest pipeline using the scan-tier model.
2. **Evaluate**: For each ingested document, call the conversation-tier model with:
   - The original source document content
   - The generated wiki pages (source-summary, concepts, entities)
   - Evaluation prompt: "Rate the wiki pages generated from this source document on a 1-5 scale for each criterion. Return JSON."
3. **Criteria**:
   - **Accuracy** (1-5): Do the wiki pages faithfully represent the source content? No hallucinated facts?
   - **Coverage** (1-5): Are all major topics from the source captured as concept/entity pages?
   - **TLDR usefulness** (1-5): Would the TLDRs help an agent decide which pages to read for a given query?
   - **Slug clarity** (1-5): Are slugs descriptive and consistent? Would an agent guess the right slug?
   - **Cross-ref relevance** (1-5): Are `suggested_related_topics` meaningful, not spurious?
4. **Pass threshold**: All criteria ≥ 3.5 average across all 8 test files. Any file scoring <3 on any criterion triggers a prompt revision.
5. **Iterate**: Adjust the ingest prompt based on the AI judge's feedback. Re-run. Repeat until threshold is met.
6. **Document**: Final prompt committed with comments explaining key design choices and tuning history.

**Common issues to watch for during tuning:**
- Too many/few pages per document
- Vague TLDRs that don't help routing
- Duplicate or overlapping concept pages
- Hallucinated entities (names/tools not in the source)
- Poor slugs (too generic, inconsistent naming)
- Spreadsheets producing low-quality concept pages (tabular data may need different handling)

### 3.3 Estimated Page Counts
- Short document (~1K words): 3-5 pages (1 summary + 2-4 concepts/entities)
- Medium document (~5K words): 8-12 pages
- Long document (~20K words): 12-15 pages (cap at ~15 to keep index manageable)
- Spreadsheets: 2-4 pages (1 summary + 1-3 entity pages for key data categories)

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. L3 due to LLM prompt engineering + tuning loop. |
| 2026-04-13 | Claude (doc-manager) | Pre-sprint refinement: added AI judge evaluation loop (conversation-tier rates scan-tier output), RAG_TESTING test data path (8 files), tiny doc threshold (<100 chars skip ingest), spreadsheet page count estimates, pass threshold (all criteria ≥3.5 across 8 files). |

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 20 | 925 | 945 |
