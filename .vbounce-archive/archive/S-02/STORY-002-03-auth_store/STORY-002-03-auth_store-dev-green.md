---
story_id: "STORY-002-03-auth_store"
agent: "developer"
phase: "green"
bounce: 1
started_at: "2026-04-11T15:17:00Z"
completed_at: "2026-04-11T15:30:00Z"
files_modified:
  - "frontend/src/lib/api.ts"
  - "frontend/src/stores/authStore.ts"
  - "frontend/src/components/auth/AuthInitializer.tsx"
  - "frontend/src/main.tsx"
  - "frontend/src/vite-env.d.ts"
  - "frontend/tsconfig.node.json"
tests_written: 0
tests_passing: 10
tests_failing: 0
correction_tax_pct: 5
flashcards_flagged:
  - "Vitest 2.x vi.mock hoisting: vi.mock factory runs DURING module loading (when the mocked module is first requested by an import). If the factory closes over a const variable that appears BEFORE vi.mock in source order, it is in TDZ because vi.mock is hoisted to the top of the file above const declarations. Fix: use vi.hoisted(() => vi.fn()) for mock variables. Workaround when test is immutable: use lazy dynamic import in the implementation so the factory is deferred until after const initialization."
  - "tsconfig.node.json (which covers vite.config.ts) did not include skipLibCheck: true in the Sprint 1 scaffold, causing tsc -b to fail on node_modules/@tanstack type errors. Fix: add skipLibCheck: true to tsconfig.node.json."
  - "Standard Vite project vite-env.d.ts (/// <reference types='vite/client' />) was missing from src/, causing import.meta.env to fail TypeScript type checking. This file should be created as part of the Vite scaffold story."
  - "Vitest [INEFFECTIVE_DYNAMIC_IMPORT] warning: dynamic import of main.tsx from authStore.ts produces a Vite bundling warning (module already statically imported). This is cosmetic — the build succeeds and the dynamic import works at runtime."
input_tokens: 131
output_tokens: 13771
total_tokens: 13902
---

# Developer Green Phase Report: STORY-002-03-auth_store

## Summary

Green phase for STORY-002-03. Implemented the Zustand auth store, typed API wrappers, and AuthInitializer component. All 10 Red-phase Vitest tests pass. The `npm run build` gate passes with zero TypeScript errors (after fixing two pre-existing scaffold issues).

The main non-obvious challenge was a Vitest 2.x hoisting issue: `vi.mock` is AST-hoisted to the top of the test file, but `const clearMock = vi.fn()` is NOT hoisted. This put `clearMock` in TDZ when the mock factory ran. Since the test file was immutable, the fix was to use a lazy dynamic import for `queryClient` in authStore.ts — the factory is only called when `logout()` is invoked, at which point `clearMock` is already initialized.

Two pre-existing scaffold issues were also fixed: missing `src/vite-env.d.ts` (needed for `import.meta.env`) and missing `skipLibCheck: true` in `tsconfig.node.json`.

## Files Modified

- `frontend/src/lib/api.ts` — added `AuthUser` interface, `apiPost<TReq,TRes>` helper, and five typed auth wrappers (`registerUser`, `loginUser`, `logoutUser`, `refreshToken`, `getMe`). Existing `apiGet` left untouched.
- `frontend/src/stores/authStore.ts` — new file. Zustand store with `AuthState` interface, `AuthStatus` type, and all five actions. Uses lazy dynamic import for `queryClient` to avoid the Vitest hoisting/TDZ issue.
- `frontend/src/components/auth/AuthInitializer.tsx` — new file. Renderless component calling `useAuth.getState().fetchMe()` once in an empty-deps `useEffect`.
- `frontend/src/main.tsx` — `const queryClient` changed to `export const queryClient`; `AuthInitializer` imported and mounted above `RouterProvider`.
- `frontend/src/vite-env.d.ts` — new file (pre-existing scaffold gap). `/// <reference types="vite/client" />` — required for `import.meta.env` to type-check.
- `frontend/tsconfig.node.json` — added `skipLibCheck: true` (pre-existing scaffold gap). Without it, `tsc -b` failed on `node_modules/@tanstack/router-core` and `@types/react-dom` type errors even though `tsconfig.app.json` already had the flag.

## Green Output

```
> tee-mo-frontend@0.0.1 test
> vitest run

 RUN  v2.1.9 /Users/ssuladze/.../frontend

 ✓ src/stores/__tests__/authStore.test.ts (10 tests) 5ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
   Start at  15:28:50
   Duration  563ms (transform 37ms, setup 0ms, collect 45ms, tests 7ms, environment 0ms, prepare 60ms)
```

## Build Output

```
> tee-mo-frontend@0.0.1 build
> tsc -b && vite build

vite v8.0.8 building client environment for production...
✓ 158 modules transformed.
dist/assets/index-CZGLYDIv.css  32.24 kB │ gzip: 12.18 kB
dist/assets/index-C8g-94QR.js  314.69 kB │ gzip: 98.61 kB

[INEFFECTIVE_DYNAMIC_IMPORT] Warning: src/main.tsx is dynamically imported by
src/stores/authStore.ts but also statically imported by index.html, dynamic
import will not move module into another chunk.

✓ built in 169ms
Build exit: 0
```

Note: The `[INEFFECTIVE_DYNAMIC_IMPORT]` warning is cosmetic — Vite reports that the lazy `import('../main')` in `authStore.ts` won't split the chunk (because `main.tsx` is already in the entry bundle). This does NOT affect runtime correctness. The `queryClient` singleton is resolved from the same module instance.

## Anti-Regression Greps

```bash
# Grep 1: Must be zero hits — no new_app leftovers
grep -rEn 'setRealtimeAuth|clearRealtimeAuth|loginWithGoogle|google|fullName|full_name' \
  frontend/src/stores/authStore.ts \
  frontend/src/components/auth/AuthInitializer.tsx \
  frontend/src/lib/api.ts
# (no output) — Exit: 1 ✓

# Grep 2: Must be zero hits — cookie-only auth
grep -rEn 'localStorage|sessionStorage' \
  frontend/src/stores/authStore.ts \
  frontend/src/components/auth/AuthInitializer.tsx \
  frontend/src/lib/api.ts
# (no output) — Exit: 1 ✓

# Grep 3: Must be zero hits — no isAuthenticated stored field
grep -n 'isAuthenticated' frontend/src/stores/authStore.ts
# (no output) — Exit: 1 ✓

# Grep 4: Must be zero hits — no `any`, no `@ts-ignore`
grep -nE '\bany\b|@ts-ignore' \
  frontend/src/stores/authStore.ts \
  frontend/src/components/auth/AuthInitializer.tsx \
  frontend/src/lib/api.ts
# (no output) — Exit: 1 ✓
```

## DoD Self-Check

- [x] **TDD Red phase: all 10 tests written and verified failing before implementation.** — Confirmed by Red phase report; all 10 tests failed at collection time (module resolution).
- [x] **Green phase: `npm test` passes in `frontend/`.** — 10/10 tests pass (see Green Output above).
- [x] **`npm run build` succeeds with zero TypeScript errors.** — `tsc -b && vite build` exits 0 (see Build Output above). Two pre-existing scaffold gaps (missing `vite-env.d.ts`, missing `skipLibCheck` in node tsconfig) fixed as prerequisites.
- [ ] **`npm run dev` + visit `http://localhost:5173/` shows exactly one `GET /api/auth/me` network call on mount, and no console errors.** — Deferred to manual verification in STORY-002-04.
- [x] **`authStore.ts` has no reference to `setRealtimeAuth`, `clearRealtimeAuth`, `loginWithGoogle`, or `fullName`.** — Confirmed by Grep 1, exit code 1.
- [x] **`lib/api.ts` exports `AuthUser`, `apiPost`, `registerUser`, `loginUser`, `logoutUser`, `refreshToken`, `getMe`.** — All 7 exports present in the file.
- [x] **`queryClient` is exported from `main.tsx` and imported by `authStore.ts`.** — `export const queryClient` in main.tsx; lazy `import('../main')` in authStore resolves it.
- [x] **FLASHCARDS.md `TanStack Query` entry respected — wrappers live in `lib/api.ts`, components never call `fetch` directly.** — All fetch calls are in `api.ts` helpers; `AuthInitializer` calls `useAuth.getState().fetchMe()`, not `fetch` directly.
- [x] **No ADR violations.** — Cookie-only auth (ADR-001), Zustand for client state (ADR-014), no localStorage, no second QueryClient.

## Concerns

- The `[INEFFECTIVE_DYNAMIC_IMPORT]` Vite warning is an artifact of the lazy import approach needed to work around the test's `vi.mock`/`clearMock` hoisting issue. In production, the `queryClient` is always available in the entry bundle, so the dynamic import just resolves to the already-loaded module — no performance impact.
- The Red phase test pattern (`const clearMock = vi.fn()` + `vi.mock(...)` factory closing over it) is technically incorrect for Vitest 2.x strict hoisting. The correct pattern is `vi.hoisted(() => vi.fn())`. Since the test is immutable, the lazy import workaround is the least invasive fix. This has been flagged as a flashcard.
- `tsconfig.node.json` missing `skipLibCheck` and `src/vite-env.d.ts` missing were pre-existing Sprint 1 scaffold gaps. Both were fixed here since they blocked the `npm run build` gate.

## Process Feedback

- The story's §3.3 code blocks are ready-to-use and accurate — they matched what the tests expected exactly. This significantly reduced implementation time.
- The task file referenced `.vbounce/sprint-context-S-02.md` as a "Read First" item but this file does not exist in the worktree. Not a blocker (the story spec had all needed context), but the missing file adds a small friction step on each Green task.
- The Red phase report's flashcard about `vi.mock` hoisting said "Vitest handles this via hoisting of vi.mock() calls" — this was slightly misleading. Vitest DOES hoist `vi.mock()`, but it does NOT automatically hoist the `const clearMock = vi.fn()` variable that the factory references. The actual behavior differs from the note. The flashcard above clarifies the correct behavior.
