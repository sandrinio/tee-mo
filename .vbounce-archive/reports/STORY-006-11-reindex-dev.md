---
status: "implemented"
correction_tax: 5
input_tokens: 34
output_tokens: 1857
total_tokens: 1891
tokens_used: 2467
tests_written: 5
files_modified:
  - "backend/app/api/routes/knowledge.py"
  - "backend/tests/test_knowledge_routes.py"
  - "frontend/src/lib/api.ts"
  - "frontend/src/hooks/useKnowledge.ts"
  - "frontend/src/routes/app.teams.$teamId.$workspaceId.tsx"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-006-11-reindex

## Files Modified

- `backend/app/api/routes/knowledge.py` — Added `POST /api/workspaces/{workspace_id}/knowledge/reindex` endpoint. Added `import inspect` and `from datetime import datetime` at top. The endpoint asserts ownership, gates on BYOK key and Drive connection, builds the Drive client once, then iterates all indexed files sequentially — re-fetching content, recomputing hash, regenerating AI description, and updating via `.update()` (not `.upsert()`). Per-file errors are collected without aborting the run.

- `backend/tests/test_knowledge_routes.py` — Added 5 tests in `TestReindexKnowledge` class: happy path (2 files → reindexed=2, failed=0, errors=[]), no BYOK key → 400, no Drive → 400, non-owner → 404, empty workspace → reindexed=0, failed=0, errors=[]. Added `_make_reindex_supabase_mock` helper for the reindex-specific Supabase mock shape (list + update chains).

- `frontend/src/lib/api.ts` — Added `ReindexResult` interface and `reindexKnowledge(workspaceId)` function calling `apiPost` to `POST .../knowledge/reindex` with an empty body.

- `frontend/src/hooks/useKnowledge.ts` — Added `useReindexKnowledgeMutation(workspaceId)` hook with `mutationFn: () => reindexKnowledge(workspaceId)` and `onSuccess` invalidating `['knowledge', workspaceId]`.

- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — Added `ReindexFeedback` interface, imported `useReindexKnowledgeMutation`, wired the mutation into `PickerSection`, added "Re-index All Files" button (hidden when fileCount=0, disabled when pending/no Drive/no key), and inline success/error feedback messages.

## Logic Summary

The backend endpoint follows the same owner-gating pattern used by all other knowledge routes (`_assert_workspace_owner` returning 404 on mismatch). Two early 400 guards mirror the index-file endpoint: BYOK key checked first, then Drive connection. The Drive client is built once from the decrypted refresh token and reused across all files, avoiding N redundant OAuth exchanges.

Per-file content re-extraction uses the `inspect.isawaitable()` pattern from STORY-006-08 since `fetch_file_content` returns `_AwaitableStr` — a `str` subclass that may or may not be a coroutine depending on whether the multimodal fallback path is exercised. The update uses `.update()` on the existing row (not `.upsert()`) — inserting new rows would violate the existing PK and duplicate files. `last_scanned_at` is set to `datetime.utcnow().isoformat()` rather than the string `"now()"` since PostgREST does not accept SQL function strings in update payloads.

The frontend button is placed inside `PickerSection` alongside the existing "Add File" button, which is architecturally appropriate since both actions operate on the knowledge file collection. The button is hidden (not just disabled) when `fileCount === 0` to avoid confusing the user with a re-index action when there are no files. Success feedback is shown inline below the buttons rather than as a toast, keeping the UI changes minimal and scoped.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed: None. The `fetch_file_content` signature was confirmed by reading the service file (it accepts `provider` and `api_key` keyword args matching the story spec's pattern).

## Flashcards Flagged

- **`StopIteration` in async coroutines (`iter()` + `lambda`): pre-existing `TestConcurrentIndexingSerialized::test_two_sequential_posts_both_succeed` fails because `next(call_sequence)` inside a `lambda` called from an async context raises `StopIteration` which is converted to `RuntimeError` per PEP 479. This test was failing before this story and is unrelated to the reindex feature. Worth recording as a test pattern anti-pattern to avoid when writing concurrent mock sequences in async test contexts.**

## Product Docs Affected

- None. No existing product docs describe the re-index feature behavior that changed.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (JSDoc/docstrings added to all exports to prevent RAG poisoning)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The `_AwaitableStr` / `inspect.isawaitable` pattern is now used in two places (index_file and reindex). The story spec note about it was accurate and saved investigation time.
- The story spec correctly flagged that `.update()` must be used (not `.upsert()`), which is a subtle distinction that the hermetic mock pattern would have hidden — good explicit guidance.
