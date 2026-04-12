---
status: "implemented"
correction_tax: 0
input_tokens: 1498
output_tokens: 835
total_tokens: 2333
tokens_used: 2333
tests_written: 5
files_modified:
  - "backend/app/core/keys.py"
  - "backend/app/services/provider_resolver.py"
  - "backend/tests/test_key_resolvers.py"
flashcards_flagged: 0
---

# Developer Implementation Report: STORY-004-02-provider-resolvers

## Files Modified
- `backend/app/core/keys.py` — NEW. Non-inference BYOK key resolver. Queries `teemo_workspaces.encrypted_api_key` via the `.table().select().eq().maybe_single().execute()` Supabase chain, decrypts with `app.core.encryption.decrypt()`, returns `str | None`.
- `backend/app/services/provider_resolver.py` — NEW. Inference-path wrapper. Delegates to `get_workspace_key()`, raises `ValueError` with a human-readable message if no key is found. Intended for EPIC-007 agent factory.
- `backend/tests/test_key_resolvers.py` — NEW. 5 unit tests covering all Gherkin scenarios. Tests 1-3 use a hand-rolled `_make_supabase()` mock for the full query chain. Tests 4-5 patch `get_workspace_key` directly via `unittest.mock.patch`.

## Logic Summary

`get_workspace_key` implements the non-inference resolver pattern from new_app — it queries a single column from `teemo_workspaces`, guarding against both a missing row (`result.data is None`) and a present row with a `NULL` key column (`encrypted is None`). Both cases return `None` without calling `decrypt()`, which prevents spurious `InvalidTag` exceptions.

`resolve_provider_key` wraps `get_workspace_key` for the inference path: the only difference is it converts `None` to a `ValueError` with an actionable user message. This separation keeps the core resolver reusable for non-inference callers (EPIC-006 file indexing) while giving the agent factory (EPIC-007) a clean hard-failure signal.

The Supabase mock helper `_make_supabase()` in the test file chains MagicMock objects to simulate the full fluent query API without any real I/O. Test 1 uses the real `encrypt()` function to produce a realistic ciphertext, so `get_workspace_key`'s decrypt call exercises the full round-trip with the actual `TEEMO_ENCRYPTION_KEY` from the worktree's `.env`.

## Correction Tax
- Self-assessed: 0%
- Human interventions needed: none

## Flashcards Flagged
- None. No non-obvious behaviors encountered. The implementation is a straight copy-and-strip from new_app with the table name changed to `teemo_workspaces`.

## Product Docs Affected
- None. No existing vdocs describe these new internal resolver functions.

## Status
- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed (ADR-002: decrypt only inside get_workspace_key; ADR-005: resolver does not pre-load file content)
- [x] Code is self-documenting (JSDoc/docstrings added to all exports)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback
- None. Story spec was precise and the copy-and-strip instructions in §1.2 were unambiguous. No friction encountered.
