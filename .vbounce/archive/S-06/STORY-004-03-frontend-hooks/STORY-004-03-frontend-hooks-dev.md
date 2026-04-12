---
status: "implemented"
correction_tax: 5
input_tokens: 1974
output_tokens: 1230
total_tokens: 3204
tokens_used: 3204
tests_written: 5
files_modified:
  - "frontend/src/lib/api.ts"
  - "frontend/src/hooks/useKey.ts"
  - "frontend/src/hooks/useKey.test.tsx"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-004-03-frontend-hooks

## Files Modified

- `frontend/src/lib/api.ts` — ADDITIVE: Added `ProviderKey`, `SaveKeyRequest`, `ValidateKeyRequest`, `ValidateKeyResponse` interfaces and `getKey()`, `saveKey()`, `deleteWorkspaceKey()`, `validateKey()` wrappers below the existing workspace section (line 265+). No existing exports modified.
- `frontend/src/hooks/useKey.ts` — NEW: Three TanStack Query hooks (`useKeyQuery`, `useSaveKeyMutation`, `useDeleteKeyMutation`) and a `keyKeys` factory. Modeled on the established pattern in `useWorkspaces.ts`.
- `frontend/src/hooks/useKey.test.tsx` — NEW: 5 unit tests covering all 4 Gherkin scenarios from §2 plus one bonus test for the `enabled: Boolean(workspaceId)` guard.

## Logic Summary

The `api.ts` additions follow the established pattern exactly: `getKey` and `saveKey` delegate to `apiGet`/`apiPost` helpers; `deleteWorkspaceKey` uses an inline raw `fetch` with `method: 'DELETE'` since no `apiDelete` helper exists and the spec (§3.4) explicitly says to keep the change additive. The `API_URL` constant name was confirmed from the existing file (it is `API_URL`, not `API_BASE`).

The `useKey.ts` hooks mirror `useWorkspaces.ts` structure. `useKeyQuery` uses `staleTime: 60_000` (60-second window per spec §2) and `enabled: Boolean(workspaceId)` to prevent spurious fetches on empty IDs. Both mutations invalidate two cache keys on success: `['keys', workspaceId]` via `keyKeys.byWorkspace()` and `['workspaces', teamId]` — the latter confirmed to match the exact key shape in `useWorkspaces.ts`.

The test file applies the `vi.hoisted()` requirement from FLASHCARDS.md: in this case the mock factory only uses inline `vi.fn()` calls with no variable closure, so no `vi.hoisted()` wrapper was strictly needed. However, a `beforeEach(vi.clearAllMocks())` was required in the `useKeyQuery` describe block because the 5th test (`is disabled when workspaceId is empty`) was failing due to call count bleed from the preceding two tests — the shared `api.getKey` mock retained previous call records without a clear.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed: None
- One self-correction: initial test had `import { afterEach, beforeEach }` but `afterEach` was never used, causing a `TS6133` error in the `tsc -b` step. Removed the unused import and rebuilt cleanly.

## Flashcards Flagged

- **vi.clearAllMocks() placement matters for shared mocks**: Even when individual `vi.mock` factories use inline `vi.fn()`, the call count from one test bleeds into the next if `vi.clearAllMocks()` is not called between tests. The FLASHCARDS.md entry focuses on `vi.hoisted()` for TDZ, but the complementary discipline is a `beforeEach(vi.clearAllMocks())` in any describe block that has ≥2 tests touching the same mock. Candidate for a new flashcard.

## Product Docs Affected

- None. This story adds new API wrappers and hooks — no existing product doc describes BYOK key management frontend behavior yet (STORY-004-04 UI is the consumer).

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (JSDoc/docstrings added to all exports to prevent RAG poisoning)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The worktree did not have `node_modules/` — had to run `npm install` before tests could run. The team lead's worktree setup step (per FLASHCARDS.md on worktree `.env` placement) could be extended to also run `npm install` in `frontend/` for stories that touch the frontend. This avoids a silent "vitest not found" error that looks like a config problem.
