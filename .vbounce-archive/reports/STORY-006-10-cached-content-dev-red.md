---
status: "red_complete"
correction_tax: 10
input_tokens: 60
output_tokens: 4184
total_tokens: 4244
tokens_used: 4244
tests_written: 5
files_modified:
  - "backend/tests/test_knowledge_routes.py"
  - "backend/tests/test_read_drive_file.py"
flashcards_flagged: 1
phase: "RED"
---

# Developer Implementation Report: STORY-006-10-cached-content (RED PHASE)

## Files Modified

- `backend/tests/test_knowledge_routes.py` — Added `TestIndexFileStoresCachedContent` class at the end of the file. Contains 1 test that intercepts the Supabase `.insert()` call on `teemo_knowledge_index` and asserts the payload includes `cached_content` equal to the fetched file content.

- `backend/tests/test_read_drive_file.py` — New file. Contains 4 async tests covering all cache-path scenarios in `read_drive_file` (agent.py): cache hit returns cached_content directly without Drive call; cache miss fetches Drive and upserts `cached_content`; hash-change branch includes `cached_content` in upsert; no-hash-change branch upserts `cached_content` without re-generating description.

## Logic Summary

### Test 1 — Index file stores cached_content (knowledge_routes)
Extends `test_knowledge_routes.py` with a custom `_CapturingTableRouter` subclass that intercepts `.insert()` calls on `teemo_knowledge_index` and appends the payload to a list. After calling `POST /api/workspaces/{id}/knowledge`, asserts that the captured payload contains `cached_content = FAKE_FILE_CONTENT`. Fails RED because the current `knowledge.py` route inserts a row dict without `cached_content` (line ~258).

### Tests 2-5 — read_drive_file cache behavior (agent.py)
All 4 tests use `_extract_read_drive_file_tool()` — an async helper that calls `build_agent()` with fully mocked pydantic-ai internals (`Agent` class replaced with a capture function, `_build_pydantic_ai_model` patched, `list_skills` returns `[]`, `decrypt` returns a fixed key). The `tools=[...]` list passed to `Agent()` is intercepted and the `read_drive_file` tool is extracted by name. Each test then builds a synthetic `_FakeCtx` / `_FakeDeps` with a tailored Supabase mock and invokes the actual function.

- **Test 2 (cache hit)**: file_row has `cached_content = FAKE_CACHED_CONTENT`. Expects result equals `FAKE_CACHED_CONTENT` and `get_drive_client` not called. Fails: agent.py ignores `cached_content`, calls Drive, returns `FAKE_FRESH_CONTENT`.
- **Test 3 (cache miss, hash unchanged)**: file_row has `cached_content = None`, compute_hash returns same hash as stored. Expects upsert captured with `cached_content`. Fails: agent.py skips upsert entirely when hash is unchanged.
- **Test 4 (hash change)**: file_row has `cached_content = None`, compute_hash returns a different hash. Expects upsert payload includes `ai_description`, `cached_content`, `content_hash`. Fails: current upsert omits `cached_content`.
- **Test 5 (no hash change)**: same as Test 3 but additionally asserts `ai_description` is absent from upsert. Fails: no upsert at all.

## Correction Tax
- Self-assessed: 10%
- Human interventions needed: None
- Iterations needed:
  - Initial `_extract_read_drive_file_tool` approach used `AsyncMock` for `list_skills` (which is sync) → fixed to plain `MagicMock`.
  - Initial Test 2 didn't patch `compute_content_hash` or `generate_ai_description`, causing a real Anthropic API call → added those mocks.
  - Initial `test_read_drive_file.py` used a reference implementation fallback instead of the actual agent.py code → rewrote to call real nested function via build_agent interception.

## Flashcards Flagged

- **agent.py `fetch_file_content` call is synchronous (no await)**: agent.py calls `fetch_file_content(drive_client, ...)` without `await` even though `drive_service.fetch_file_content` may be async in route tests. Tests using `AsyncMock` for this function in agent.py tests will fail — use plain `MagicMock`. The route test (`test_knowledge_routes.py`) correctly uses `AsyncMock` because the route code uses `asyncio.iscoroutinefunction` to decide whether to await.

## Product Docs Affected
- None — tests only, no implementation code written.

## Status
- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red phase — all 5 tests FAIL correctly)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (no implementation code modified)
- [x] Code is self-documenting (all helpers/fixtures have docstrings)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Test Results Summary (RED PHASE)

| Test | File | Failure Reason |
|------|------|---------------|
| Test 1: index_file stores cached_content | test_knowledge_routes.py | INSERT payload missing `cached_content` key |
| Test 2: cache hit, no Drive call | test_read_drive_file.py | Returns `FAKE_FRESH_CONTENT` instead of `FAKE_CACHED_CONTENT` |
| Test 3: cache miss + backfill | test_read_drive_file.py | No upsert called when hash unchanged |
| Test 4: hash change + description | test_read_drive_file.py | Upsert missing `cached_content` key |
| Test 5: no hash change, no description | test_read_drive_file.py | No upsert called when hash unchanged |

All 5 tests collected and failing: `5 failed` confirmed via pytest run.

## Process Feedback

- The `read_drive_file` nested-function extraction pattern required significant ceremony: mocking `Agent`, patching `_build_pydantic_ai_model`, patching model class globals. The story spec's "Recommended approach" suggested mocking Supabase chains directly without mentioning this extraction complexity — a `## Invocation Note` in the Implementation Guide would have saved 2 iterations.
- `list_skills` being sync (not async) was a non-obvious gotcha — an AsyncMock caused a `'coroutine' object is not iterable` error. The FLASHCARDS.md entry on hermetic mocks is relevant here but doesn't cover sync vs async function checking specifically.
