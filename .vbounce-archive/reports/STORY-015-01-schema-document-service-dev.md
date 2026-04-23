---
story_id: "STORY-015-01"
agent: "Developer"
status: "implemented"
correction_tax: 5
input_tokens: 54
output_tokens: 3263
total_tokens: 3317
tests_written: 28
tests_passed: 28
files_modified:
  - "backend/app/main.py"
files_created:
  - "database/migrations/010_teemo_documents.sql"
  - "backend/app/services/document_service.py"
  - "backend/tests/test_document_service.py"
flashcards_flagged: 1
sprint_id: "S-11"
---

# Developer Implementation Report: STORY-015-01-schema-document-service

## Files Modified
- `backend/app/main.py` — replaced `"teemo_knowledge_index"` with `"teemo_documents"` in the `TEEMO_TABLES` tuple (line ~78) so the health check probes the new table.

## Files Created
- `database/migrations/010_teemo_documents.sql` — Full migration: creates `teemo_documents` with all EPIC-015 §4.4 columns, constraints (`chk_teemo_documents_source`, `chk_teemo_documents_sync_status`, `chk_teemo_documents_doc_type`), 5 indexes (workspace, content_hash, external_id partial, sync_status partial, and two unique partial indexes for Drive and upload uniqueness), `updated_at` auto-update trigger, 15-document BEFORE INSERT cap trigger, and `DROP TABLE IF EXISTS teemo_knowledge_index CASCADE`.

- `backend/app/services/document_service.py` — CRUD service layer with: `compute_content_hash` (SHA-256), `_resolve_ai_description` (internal helper), `create_document`, `read_document_content`, `update_document`, `delete_document`, `list_documents`. All exported functions have full JSDoc-style docstrings. AI description generation gracefully degrades to `None` on any failure (no key, LLM error, etc.).

- `backend/tests/test_document_service.py` — 28 unit tests (all passing): 5 for `compute_content_hash`, 5 for `create_document`, 3 for `read_document_content`, 4 for `update_document`, 3 for `delete_document`, 4 for `list_documents`, 4 for `_resolve_ai_description`.

## Logic Summary

The migration follows EPIC-015 §4.4 verbatim. The `sync_status` partial index excludes `'synced'` rows to keep the index lean for EPIC-013's wiki pipeline queries. Both triggers (cap and updated_at) use `CREATE OR REPLACE FUNCTION` for idempotency. The `DROP TABLE IF EXISTS teemo_knowledge_index CASCADE` is safe because zero production rows exist.

`document_service.py` follows the same workspace-isolation pattern as `drive_service.py`: every query includes an `.eq("workspace_id", workspace_id)` filter. The `_resolve_ai_description` helper uses a lazy `from app.core.encryption import decrypt` inside the function body (not at module level) to avoid loading `app.core.config` / Pydantic Settings at import time — which would fail in test environments without a `.env` file. This is a deliberate deviation from the module-level import convention used by `drive_service.py` (which requires `.env` in the test environment too). The `updated_at` and `created_at` columns are never included in insert/update payloads per the FLASHCARDS rule on `DEFAULT NOW()` columns.

The `create_document` function omits optional fields (external_id, external_link, original_filename, file_size) from the payload when they are None rather than sending `null` — this prevents PostgREST from overwriting any default values on upsert-style operations in future callers.

## Correction Tax
- Self-assessed: 5%
- Human interventions needed: None
- Mid-implementation fix: My first edit to `_resolve_ai_description` accidentally removed the `from app.core.encryption import decrypt` line while editing the docstring. Caught by running tests (27/28 passed, the `NameError` pointed directly to the missing line). Fixed in one edit.
- Two tests for `_resolve_ai_description` required `sys.modules` injection pattern rather than standard `patch("app.core.encryption.decrypt", ...)` because the worktree lacks a `.env` file and the real `app.core.encryption` module cannot be imported without it.

## Flashcards Flagged
- **Worktree `.env` absence causes sys.modules injection pattern for encrypt tests.** When testing a service function that lazily imports `app.core.encryption` (which loads `app.core.config`/Pydantic Settings), the standard `patch("app.core.encryption.decrypt")` target cannot be used because the module is not importable without env vars. The workaround: pre-register `app.core` as a package (importable without `.env`) then inject a `types.ModuleType("app.core.encryption")` fake into `sys.modules` before the call. This is a test-only pattern — do not add it to production code.

## Product Docs Affected
- None. This story creates new infrastructure. No existing product docs describe `teemo_knowledge_index` behavior that users see directly.

## Status
- [x] Code compiles without errors
- [x] Automated tests written and all 28 pass
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (SHA-256 per sprint context, teemo_ prefix, no column name in select probes)
- [x] Code is self-documenting (JSDoc/docstrings on all exported functions)
- [x] No new patterns or libraries introduced (hashlib, unittest.mock — stdlib only)
- [x] Token tracking completed (count_tokens.mjs ran successfully: 3,317 tokens)

## Process Feedback
- The sprint context note about copying `.env` to the worktree root is critical for tests that import `app.core.encryption` or other config-dependent modules. The worktree env setup step (copying `.env`) should be done by DevOps/the Team Lead before Developer work begins — otherwise any test that touches `app.core.config` will ERROR at collection time with 12 missing-field validation errors.
