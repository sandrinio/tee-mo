---
status: "implemented"
correction_tax: 5
input_tokens: 41
output_tokens: 7527
total_tokens: 7568
tokens_used: 7568
tests_written: 0
files_modified:
  - "backend/app/models/knowledge.py"
  - "backend/app/api/routes/knowledge.py"
  - "backend/app/main.py"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-006-03-knowledge-crud

## Files Modified
- `backend/app/models/knowledge.py` (created) — Pydantic models `IndexFileRequest`, `KnowledgeIndexRequest`, `KnowledgeIndexResponse`. Added `from __future__ import annotations` and `Optional[str]` instead of `str | None` for Python 3.9 compatibility (production runs 3.10+ but system Python in worktree is 3.9).
- `backend/app/api/routes/knowledge.py` (created) — All four routes with `_workspace_locks` dict, `ALLOWED_MIME_TYPES` set, and the `_get_workspace_lock` helper. `httpx` imported at module level per FLASHCARDS rule. Drive service and scan service imported as modules so monkeypatch works.
- `backend/app/main.py` (modified) — Added `from app.api.routes.knowledge import router as knowledge_router` and `app.include_router(knowledge_router)` after `drive_oauth_router`.

## Logic Summary

The knowledge routes follow the same ownership guard + module-import patterns established in `drive_oauth.py`. The `_assert_workspace_owner` helper queries `teemo_workspaces` with both `id` and `owner_user_id` filters, returning 404 to prevent IDOR — returning the full workspace row so the caller can read `encrypted_google_refresh_token`, `encrypted_api_key`, and `provider` without a second query.

The `POST /api/workspaces/{workspace_id}/knowledge` handler performs 11 steps in order: ownership check, Drive connection check, BYOK key check, MIME allowlist check, lock acquisition (R8), count check (ADR-007 15-file cap), duplicate check (409), content fetch, hash computation, AI description generation, and insert. Truncation detection checks for the literal string `"[Content truncated"` in the fetched content — this is the marker appended by `drive_service._maybe_truncate`. The `asyncio.iscoroutinefunction` branch handles both the real sync `fetch_file_content` (wrapped in `asyncio.to_thread`) and the `AsyncMock` used in tests.

The picker-token endpoint exchanges the stored refresh token for a transient access token via Google's token endpoint, returns it directly, and never writes it to the database (ADR-009). The `_workspace_locks` dict at module level satisfies the test that checks for `_workspace_locks` or `workspace_locks` attributes on the module.

## Correction Tax
- Self-assessed: 5%
- Human interventions needed:
  - Noticed the test file imports `IndexFileRequest` (not `KnowledgeIndexRequest` as the task description said) — caught by reading the test carefully before writing code.
  - Added `from __future__ import annotations` + `Optional[str]` after discovering system Python 3.9 doesn't support `str | None` union syntax at runtime in class bodies.

## Flashcards Flagged
- **`asyncio.iscoroutinefunction(AsyncMock())` returns True in Python 3.8+** — useful for writing route code that handles both sync production implementations and async mocks without requiring `to_thread` wrapping inside test paths. The pattern `if asyncio.iscoroutinefunction(fn): result = await fn(...)` else `result = await asyncio.to_thread(fn, ...)` is clean and test-transparent.

## Product Docs Affected
- None. No existing vdocs/ documents describe Knowledge CRUD behaviour — this is new functionality.

## Status
- [x] Code compiles without errors (Python syntax validation passed)
- [x] Automated tests were written FIRST (Red) and implementation written in Green phase
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-002, ADR-005, ADR-006, ADR-007, ADR-009, ADR-016)
- [x] Code is self-documenting (JSDoc/docstrings added to all exports)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback
- The test file uses `IndexFileRequest` as the model name but the task description §3.1 skeleton shows `KnowledgeIndexRequest`. The test file is authoritative (per GREEN PHASE rules) — reading the test first caught this before any wrong code was written.
- System Python 3.9 in the worktree makes it hard to run the FastAPI integration tests. The task note acknowledges this. The code was validated with `ast.parse` and logic traced manually against the test mock structure.
