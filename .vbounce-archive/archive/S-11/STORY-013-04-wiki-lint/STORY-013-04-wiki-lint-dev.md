---
status: "implemented"
correction_tax: 5
input_tokens: 36
output_tokens: 1447
total_tokens: 1483
tokens_used: 1636
tests_written: 20
files_modified:
  - "backend/app/services/wiki_service.py"
  - "backend/app/agents/agent.py"
  - "backend/tests/test_wiki_lint.py"
  - "backend/tests/test_agent_factory.py"
flashcards_flagged: 2
---

# Developer Implementation Report: STORY-013-04-wiki-lint

## Files Modified

- `backend/app/services/wiki_service.py` — Added `lint_wiki(supabase, workspace_id) -> str` public async function and `_log_lint_operation` internal helper. `lint_wiki` performs four DB-only structural quality checks and returns a markdown health report.
- `backend/app/agents/agent.py` — Added `from app.services import wiki_service as _wiki_service` module-level import. Added `lint_wiki(ctx)` tool closure inside `build_agent()`. Registered `lint_wiki` as the 13th tool in the tools list.
- `backend/tests/test_wiki_lint.py` — New test file, 20 tests covering all four lint checks, report format, log side-effect, and agent tool delegation.
- `backend/tests/test_agent_factory.py` — Updated tool count assertion from 12 to 13 to match the new tools list.

## Logic Summary

The `lint_wiki` service function makes three targeted DB queries against the workspace:
1. Fetches all wiki pages (slug, title, related_slugs, source_document_ids, page_type, confidence).
2. Fetches all documents with `sync_status='pending'` to identify stale pages.
3. Fetches all documents to find those missing a `source-summary` wiki page.

Orphan detection is done entirely in Python: build a set of all slugs referenced across all pages' `related_slugs` arrays, then flag any page whose own slug is absent from that set. This requires no extra DB query beyond the initial pages fetch.

The `teemo_wiki_log` insert uses the actual migration schema (`operation`, `details` JSONB) — not the column names used by the existing `_log_wiki_operation` helper (which has a different schema assumption). I created a separate `_log_lint_operation` helper rather than reusing the incompatible one.

The agent tool is a thin closure that delegates entirely to `wiki_service.lint_wiki` and wraps exceptions into user-readable error strings consistent with other tools in the file.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed:
  - None. The only re-work was discovering the `teemo_wiki_log` migration schema differs from what `_log_wiki_operation` assumed (different columns). Caught by reading the migration file before coding. Fixed immediately without a bounce.
  - Agent tool tests needed two passes: first pass used `patch("app.core.encryption.decrypt", ...)` which triggers `encryption.py` import at module level (which calls `get_settings()` without `.env`). Fixed by following the pattern from `test_wiki_read_tool.py` (ExitStack + `patch.object(agent_mod, "_ensure_model_imports", ...)`) and by copying `.env` to the worktree root (FLASHCARDS rule).
  - The mock for `wiki_service.lint_wiki` in tool tests needed to be active during BOTH `build_agent` AND the tool call — wrapped in a single outer `with patch.object(...)` block.

## Flashcards Flagged

- **`teemo_wiki_log` schema mismatch**: The existing `_log_wiki_operation` function inserts columns (`document_id`, `pages_created`, `status`, `detail`) that do NOT exist in the `011_teemo_wiki_pages.sql` migration. The actual table has `operation`, `details` (JSONB), `workspace_id`, `created_at`. Any future story touching this log table should read the migration first, not copy from the existing helper. Flag for recording.

- **Worktree `.env` copy required for agent tool tests**: `patch("app.core.encryption.decrypt")` triggers the first import of `app.core.encryption`, which imports `app.core.config` at module level, which calls `get_settings()` — failing without `.env`. Without `.env` at the worktree root, all agent-tool tests that use string-path `patch("app.core.encryption.decrypt", ...)` fail. FLASHCARDS already notes this but it's worth re-emphasizing: any story with agent-layer tests in a worktree needs `.env` copied first.

## Product Docs Affected

- None. This is an additive tool. No existing product doc describes `lint_wiki` behavior.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written (20 tests, all pass)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (pure DB queries, no new libraries, module-import pattern for wiki_service consistent with existing patterns)
- [x] Code is self-documenting (JSDoc/docstrings added to all exports and helpers)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The `teemo_wiki_log` schema discrepancy between the existing helper function and the actual migration is a latent bug that could cause silent failures if any future story copies `_log_wiki_operation` for non-ingest log entries. The Scribe should document the actual schema columns in `_manifest.json`.
- The FLASHCARDS worktree `.env` rule (S-05) is correct but the Team Lead's worktree setup steps don't always copy it before handing off to the Developer. Pre-bounce worktree setup should include `.env` copy as a mandatory step.
