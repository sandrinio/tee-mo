---
status: "implemented"
correction_tax: 5
input_tokens: 25
output_tokens: 1847
total_tokens: 1872
tokens_used: 2015
tests_written: 12
files_modified:
  - "backend/app/services/wiki_ingest_cron.py"
  - "backend/app/services/document_service.py"
  - "backend/app/main.py"
  - "backend/tests/test_wiki_ingest_cron.py"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-013-03-wiki-ingest-cron

## Files Modified

- `backend/app/services/wiki_ingest_cron.py` — New file. Implements `wiki_ingest_loop()` infinite cron loop, `_process_document()` dispatcher, `_resolve_workspace_key()` BYOK resolver, `_has_existing_wiki_pages()` check helper.
- `backend/app/services/document_service.py` — Extended `delete_document()` to cascade-delete associated wiki pages from `teemo_wiki_pages` using `.cs()` array-contains filter. Best-effort: cascade failure is logged but not re-raised.
- `backend/app/main.py` — Added `wiki_ingest_loop` import and registration in the lifespan context manager alongside `drive_sync_loop`. Shutdown sequence cancels both tasks and awaits each separately.
- `backend/tests/test_wiki_ingest_cron.py` — 12 tests covering all 4 Gherkin scenarios plus unit tests for helper functions.

## Logic Summary

The wiki ingest cron runs immediately on startup (sleep at the end of the loop, not the beginning) and every 60 seconds thereafter. Each cycle queries `teemo_documents` for `sync_status='pending'` rows across all workspaces. For each document it resolves the workspace BYOK key via `_resolve_workspace_key()`, which uses a lazy `decrypt` import (same pattern as `document_service._resolve_ai_description`) to avoid `.env` loading at module import time. It then checks whether wiki pages already exist for the document via `.cs()` array-contains on `source_document_ids` — if yes, it calls `reingest_document()` (destructive re-ingest); if no, it calls `ingest_document()` (first ingest). Per-document failures set `sync_status='error'` and continue.

The document deletion cascade in `document_service.delete_document()` uses Supabase's `.cs()` filter against the `source_document_ids` UUID array column, scoped to the workspace. This matches the pattern already used in `wiki_service.reingest_document()`. The cascade is explicitly best-effort — if the wiki cleanup fails, the document row is already deleted and the caller gets `True` back; the failure is only logged.

The main.py lifespan was updated to create and cancel both cron tasks. Each task is awaited separately in the shutdown sequence so a `CancelledError` from one does not prevent the other from being awaited cleanly.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed: The `.env` file needed to be copied to the worktree root (documented in sprint context lesson, but only discovered when tests failed to collect due to Settings validation errors). No logic corrections required.

## Flashcards Flagged

- **Worktree `.env` copy is a hard prerequisite for test collection**: The test runner loads `app.core.db` at collection time (not just execution time), which triggers `app.core.config.settings = get_settings()`. Without `.env` in the worktree root, ALL tests in the worktree fail with a Pydantic ValidationError before running a single test. This should be checked as step 0 before running any backend tests in a worktree.

## Product Docs Affected

- None. This story adds new background infrastructure; no existing user-facing behaviors changed.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (JSDoc/docstrings added to all exports to prevent RAG poisoning)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The sprint context lesson about `.env` placement is documented but easy to miss — it would help if the Developer agent task template included a pre-flight step: "Copy `.env` to worktree root before running tests."
- The `_make_supabase_mock` helper required a slightly more complex setup than the drive_sync_cron equivalent because `_resolve_workspace_key` uses `.maybe_single()` while the documents query uses standard `.execute()`. The `execute.side_effect` pattern (switching on table name inside the closure) worked cleanly.
