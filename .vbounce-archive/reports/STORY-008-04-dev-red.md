---
status: "red-phase-complete"
correction_tax: 0
input_tokens: 34
output_tokens: 5343
total_tokens: 5377
tokens_used: 5377
tests_written: 24
files_modified:
  - "frontend/src/components/layout/__tests__/AppNav.test.tsx"
  - "frontend/src/routes/__tests__/app.index.toast.test.tsx"
  - "frontend/src/components/dashboard/__tests__/CreateWorkspaceModal.toast.test.tsx"
  - "frontend/src/components/dashboard/__tests__/RenameWorkspaceModal.toast.test.tsx"
flashcards_flagged: 0
---

# Developer Implementation Report (RED PHASE): STORY-008-04-top-nav-chrome

## Files Modified

- `frontend/src/components/layout/__tests__/AppNav.test.tsx` — NEW. 9 tests covering AppNav render (logo, Workspaces link, user email, Log out button) and logout behavior (calls `logoutUser()`, navigates to `/login`, navigates even if logout rejects).
- `frontend/src/routes/__tests__/app.index.toast.test.tsx` — NEW. 11 tests covering all 5 Slack OAuth toast variants (`ok`, `cancelled`, `expired`, `error`, `session_lost`), `drive_connect=ok` toast, URL param stripping after toast, FlashBanner absence, and single-fire idempotency.
- `frontend/src/components/dashboard/__tests__/CreateWorkspaceModal.toast.test.tsx` — NEW. 2 tests covering `toast.error` call on mutation failure and absence of inline `<p role="alert">` after failure.
- `frontend/src/components/dashboard/__tests__/RenameWorkspaceModal.toast.test.tsx` — NEW. 2 tests covering `toast.error` call on rename mutation failure and absence of inline `<p role="alert">` after failure.

## Test Counts by File

| File | Tests | Status |
|------|-------|--------|
| `AppNav.test.tsx` | 9 | FAIL — `AppNav.tsx` does not exist yet (import resolution error) |
| `app.index.toast.test.tsx` | 11 | FAIL — `sonner` toast not called; FlashBanner still present |
| `CreateWorkspaceModal.toast.test.tsx` | 2 | FAIL — `toast.error` not called; inline error `<p>` still present |
| `RenameWorkspaceModal.toast.test.tsx` | 2 | FAIL — `toast.error` not called; inline error `<p>` still present |

Total: **24 new tests**, all failing as expected.

## Test Strategy

### AppNav Tests (`AppNav.test.tsx`)
The `AppNav` component does not exist yet. The test imports `../AppNav` which causes a module resolution error — a clean RED failure. Tests use `vi.hoisted` for `mockLogoutUser` and `mockNavigate` per the Vitest 2.x TDZ rule from FLASHCARDS.md. The `Link` component from `@tanstack/react-router` is mocked to a plain `<a>` so the test can query it with `getByRole('link', ...)` without needing a full router context.

### Toast Migration Tests (`app.index.toast.test.tsx`)
These test against the existing `AppContent` component which currently uses `FlashBanner` instead of `sonner` toasts. The tests mock `sonner`'s `toast` using `vi.hoisted` and assert that:
1. `toast.success` / `toast.error` / `toast` (plain info) are called with exact message strings
2. The `FlashBanner` element (aria-label "Flash banner") is absent from the DOM
3. `navigate` is called to strip params after the toast fires

The `drive_connect` param is added as a new search parameter — the existing `validateSearch` in `app.index.tsx` only handles `slack_install`, so the Green phase implementation must extend it.

### Modal Toast Tests
Both `CreateWorkspaceModal.toast.test.tsx` and `RenameWorkspaceModal.toast.test.tsx` mock `sonner` and `useWorkspaces` hooks via `vi.hoisted`. They verify that when `mutateAsync` rejects, `toast.error(err.message)` is called and no `<p role="alert">` exists in the DOM.

## Key Decisions

1. **Separate test files for toast behavior** — The existing `app.test.tsx` tests the old `FlashBanner` behavior. Rather than modifying that immutable (RED-phase) file or creating conflicts, new toast behavior tests live in a separate file `app.index.toast.test.tsx`. During GREEN phase the developer can either update `app.test.tsx` (it's not a Red-phase test file for this story) or leave it to fail and address it as part of the migration.

2. **`AppNav` import causes collection-level error** — Since `AppNav.tsx` doesn't exist, Vitest fails at the module resolution phase before any tests run. This is stronger than a test assertion failure — it proves the implementation is completely absent.

3. **`vi.hoisted` throughout** — All mock variables used inside `vi.mock` factory functions are wrapped in `vi.hoisted(...)` per the FLASHCARDS.md TDZ rule for Vitest 2.x.

4. **Sonner mock structure** — `toast` is mocked as a function with `.success` and `.error` sub-methods via `Object.assign`. This mirrors how sonner exports `toast` in practice.

## Correction Tax
- Self-assessed: 0%
- Human interventions needed: None

## Flashcards Flagged
- None new. Existing rules (`vi.hoisted` TDZ, `globals: true`, div-based modals, separate vitest config) were all applied correctly from FLASHCARDS.md.

## Product Docs Affected
- None

## Status
- [ ] Code compiles without errors (RED phase — implementation intentionally missing)
- [x] Tests were written FIRST (RED phase) and currently FAIL as expected
- [x] FLASHCARDS.md was read before writing tests
- [x] ADRs from Roadmap §3 were followed (no new patterns — vi.hoisted, RTL, existing mock structure)
- [x] Test files are self-documenting (JSDoc on each describe block and key test)
- [x] No new patterns or libraries introduced in test files (sonner mock uses same vi.hoisted pattern)
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback
- The story spec says "Update existing `app.test.tsx` or create tests for toast behavior" — since the existing file tests the OLD FlashBanner behavior (which the implementation will remove), creating a separate file is safer for RED phase and avoids breaking the existing test suite while the FlashBanner still exists.
- The `drive_connect` param is handled by a new `validateSearch` entry; the spec mentions it but the current `validateSearch` only handles `slack_install`. This is a spec gap the Green developer must resolve by extending `validateSearch`.
