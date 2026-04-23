---
status: "red_phase_complete"
correction_tax: 0
input_tokens: 347
output_tokens: 950
total_tokens: 1297
tokens_used: 1297
tests_written: 26
files_modified:
  - "backend/tests/test_knowledge_routes.py"
flashcards_flagged: 0
---

# Developer Implementation Report: STORY-006-03-knowledge-crud (RED Phase)

## Files Modified
- `backend/tests/test_knowledge_routes.py` — New file. 26 tests covering all 12 Gherkin scenarios plus 3 model unit tests and an extra MIME type test.

## Logic Summary

The test file covers all four knowledge CRUD endpoints across 9 test classes. Tests follow the exact same patterns established in `test_drive_oauth.py`: `TestClient` with `app.dependency_overrides` for auth, `monkeypatch.setattr("app.core.db.get_supabase", ...)` for DB, and module-level monkeypatching for `drive_service` and `scan_service` functions.

The `_TableRouter` class handles multi-table Supabase mock dispatch — it routes `.table("teemo_workspaces")` and `.table("teemo_knowledge_index")` calls to separate mock chains, avoiding a single flat MagicMock that's hard to maintain. Each table mock is built with the right chain shape for the queries used: `select().eq().eq().limit().execute()` for ownership checks, `select().eq().order().execute()` for list queries, `insert().execute()` for indexing, and `delete().eq().execute()` for removal.

Service patches use `monkeypatch.setattr` on the service module object (not `from ... import`), following the FLASHCARDS.md module-import rule. `fetch_file_content` is patched with `AsyncMock` since it's an async function. The `FakeKnowledgeAsyncClient` mirrors `FakeDriveAsyncClient` for the picker-token endpoint's httpx token exchange call.

## Test Results (RED Phase)

```
25 failed, 1 passed in 1.31s
```

All 26 tests were collected and discovered. 25 fail because `app.api.routes.knowledge` and `app.models.knowledge` do not exist yet (404 responses or ImportError). The 1 passing test (`test_picker_token_access_token_is_not_stored`) passes vacuously — no route exists, so no DB writes happen, satisfying the negative assertion. This is correct RED-phase behavior: once the implementation exists and writes an access_token to DB, this test would fail to catch the ADR-009 violation.

## Scenario Coverage

| Scenario | Test(s) | Class |
|----------|---------|-------|
| 1: Index Google Docs file (happy path) | 3 tests | `TestIndexFileHappyPath` |
| 2: 15-file cap enforced | 1 test | `TestFileCapEnforced` |
| 3: BYOK key required | 1 test | `TestByokKeyRequired` |
| 4: Drive not connected | 1 test | `TestDriveNotConnected` |
| 5: Unsupported MIME type | 2 tests | `TestUnsupportedMimeType` |
| 6: Duplicate file rejected | 1 test | `TestDuplicateFileRejected` |
| 7: List indexed files | 3 tests | `TestListIndexedFiles` |
| 8: Remove indexed file | 2 tests | `TestRemoveIndexedFile` |
| 9: Picker token minted | 2 tests | `TestPickerTokenMinted` |
| 10: Large file truncation warning | 1 test | `TestLargeFileTruncationWarning` |
| 11: Concurrent indexing serialized | 2 tests | `TestConcurrentIndexingSerialized` |
| 12: Auth required on all routes | 4 tests | `TestAuthRequired` |
| Unit: Pydantic model | 3 tests | `TestKnowledgeRequestModel` |

## Correction Tax
- Self-assessed: 0%
- Human interventions needed: none

## Flashcards Flagged
- None new. All patterns followed from existing flashcards (module-level httpx import, monkeypatch on module object, worktree-relative paths).

## Product Docs Affected
- None. RED phase — no implementation written.

## Status
- [x] Code compiles without errors (test file imports cleanly, 26 tests discovered)
- [x] Automated tests were written FIRST (Red) and now FAIL (as expected for RED phase)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-005, ADR-006, ADR-007, ADR-016 all referenced in tests)
- [x] Code is self-documenting (all classes and helpers have docstrings)
- [x] No new patterns or libraries introduced (mirrors test_drive_oauth.py pattern exactly)
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback
- The `_TableRouter` pattern was needed because the Supabase mock must handle two tables with very different query chains. The existing test examples only handle one table. A shared helper in a `conftest.py` that wraps multi-table routing would reduce boilerplate across future EPIC-006 tests.
- Scenario 11 (concurrent serialization) is the hardest to test at the unit level with a sync TestClient. The lock-existence assertion covers the structural requirement (R8); true concurrency testing would require an async test with `asyncio.gather`. This matches what the story task described as "harder to test".
