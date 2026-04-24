---
story_id: "STORY-005A-06"
agent: "developer"
phase: "red+green"
status: "implementation-complete"
correction_tax: 5
input_tokens: 286
output_tokens: 7843
total_tokens: 8129
tests_written: 9
files_modified:
  - { path: "frontend/src/lib/api.ts", change: "add listSlackTeams + SlackTeam/SlackTeamsResponse types" }
  - { path: "frontend/src/routes/app.tsx", change: "replace welcome card with Slack Teams page (empty state, team list, flash banners, install anchor, loading/error states); export AppContent" }
  - { path: "frontend/src/routes/__tests__/app.test.tsx", change: "NEW — 9 component tests with vi.hoisted mocks" }
  - { path: "frontend/vitest.config.ts", change: "NEW — separate vitest config (jsdom, globals, setupFiles)" }
  - { path: "frontend/src/test-setup.ts", change: "NEW — @testing-library/jest-dom extension" }
  - { path: "frontend/vite.config.ts", change: "updated comment; test block moved to separate vitest.config.ts" }
  - { path: "frontend/tsr.config.json", change: "added routeFileIgnorePattern: __tests__ to suppress route warning" }
  - { path: "frontend/package.json", change: "added @testing-library/react, @testing-library/user-event, @testing-library/jest-dom, jsdom as devDeps (required by test spec)" }
test_result: "9 passed (new frontend), 19 passed (full frontend), 73 passed (backend unchanged)"
typecheck_result: "clean"
build_result: "success"
correction_tax_pct: 5
flashcards_flagged:
  - "vitest@2.1.9 + vite@8: separate vitest.config.ts required — avoid type conflicts"
  - "@testing-library/react auto-cleanup requires globals:true in vitest config"
  - "getByText exact match fails when text nodes have prefix text — use <span> wrapper"
---

# Developer Implementation Report: STORY-005A-06 Frontend Install UI

## Exploration Notes

**Step 1 — Type organization:** No `frontend/src/types/` directory exists. All types live inline in `api.ts`. Added `SlackTeam` and `SlackTeamsResponse` there.

**Step 2 — `apiGet` shape:** `apiGet<T>(path: string)` uses `${API_URL}${path}` with `credentials: 'include'`, throws `Error` with HTTP status on non-2xx. No auth token param — cookies are implicit. `API_URL` comes from `import.meta.env.VITE_API_URL ?? ''`.

**Step 3 — Route patterns:** `login.tsx` and `register.tsx` use `createFileRoute('/path')({ component: ... })` without `validateSearch`. No zod in project — plain function validator used.

**Step 4 — QueryClientProvider:** Already mounted in `main.tsx`. Exported as `queryClient`. Tests wrap `<AppContent />` in a fresh `QueryClient` per-test to avoid cache contamination.

**Step 5 — Card component:** Accepts `className` for composition. `CardHeader` and `CardBody` are available companions.

**Extra discovery — testing-library absent:** `@testing-library/react`, `@testing-library/user-event`, and `jsdom` were NOT in `package.json`. The test spec in the task explicitly requires them. Installed as devDeps — this is infrastructure, not a runtime dependency, and the spec demanded it.

**Extra discovery — vitest + vite version conflict:** `vitest@2.1.9` peers with `vite@5.4.21`, but the project pins `vite@8.0.8`. Putting vitest config inside `vite.config.ts` caused TypeScript to pull in vite@5 types alongside vite@8 types, creating `ProxyOptions` incompatibility errors. Solution: create a separate `vitest.config.ts` that imports `defineConfig` from `vitest/config`, and exclude it from `tsconfig.node.json` (vitest finds it automatically via its own config discovery).

## Files Modified

- `frontend/src/lib/api.ts` — Added `SlackTeam`, `SlackTeamsResponse` interfaces and `listSlackTeams()` function at the bottom. Follows existing `apiGet<T>` pattern exactly.

- `frontend/src/routes/app.tsx` — Replaced the EPIC-002 welcome-card placeholder with the full Slack Teams page. Key elements:
  - `BANNER_VARIANTS` lookup at file top — single source for all banner copy, roles, and colours
  - `validateSearch` on the Route declaration narrows `slack_install` to `SlackInstallState` union
  - `FlashBanner` inline component with `aria-label="Flash banner"` (enables `getByRole` with name option in tests) and `aria-label="Dismiss banner"` on the dismiss button
  - `AppContent` exported as a named export so tests can render it without the ProtectedRoute wrapper
  - Install button is always `<a href={`${API_URL}/api/slack/install`}>` — never onClick

- `frontend/src/routes/__tests__/app.test.tsx` — 9 component tests. Uses `vi.hoisted` for all mock variables per FLASHCARDS.md 2026-04-11. Mocks: `listSlackTeams`, `useSearch`, `useNavigate`, `ProtectedRoute`, `SignOutButton`, `useAuth`.

- `frontend/vitest.config.ts` — NEW. Separate vitest config to avoid vite@5/vite@8 type conflicts. Sets `environment: 'jsdom'`, overrides stores/** to `node`, sets `globals: true` (required for testing-library auto-cleanup), and points to `./src/test-setup.ts`.

- `frontend/src/test-setup.ts` — NEW. Imports `@testing-library/jest-dom` to extend vitest's expect with DOM matchers.

- `frontend/tsr.config.json` — Added `routeFileIgnorePattern: "__tests__"` to suppress the TanStack Router warning about test files lacking a Route export.

## Logic Summary

The `AppContent` component uses `useSearch({ from: '/app' })` to read the typed `slack_install` search param (validated on the Route declaration). If a banner variant is present and not dismissed, `FlashBanner` renders above the content area. The dismiss handler calls `navigate({ to: '/app', search: {} })` to strip the param from the URL and sets local `dismissed` state to prevent a re-render flash.

The TanStack Query call (`queryKey: ['slack-teams']`, `staleTime: 0`) drives three content states: loading skeleton (with `data-testid="skeleton-card"`), error card with retry, and the team list or empty state. The install anchor is present in both the empty state (primary styling) and team list (secondary "Install another team" link).

The `validateSearch` function uses a plain `const allowed = [...] as const` pattern since zod is not installed. Any unknown `slack_install` value becomes `undefined`, preventing unknown variants from reaching `BANNER_VARIANTS`.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed: none
- Wrong turns: (1) initially put test config in vite.config.ts → vite@5/vite@8 type conflict → moved to separate vitest.config.ts; (2) TeamCard rendered "Bot: UBOT1" as one text node → test `getByText('UBOT1')` failed → fixed by wrapping bot ID in its own `<span>`.

## Flashcards Flagged

1. **`vitest@2.1.9` + `vite@8` type conflict when using inline test config** — vitest@2.1.9 peers with vite@5.x. Placing a `test:` block in `vite.config.ts` (which imports from vite@8) causes TypeScript to see two incompatible `ProxyOptions` types from pnpm's dual-vite install. Fix: create a separate `vitest.config.ts` importing `defineConfig` from `vitest/config` and exclude it from `tsconfig.node.json`. This is the canonical separation for projects that can't upgrade vitest alongside vite.

2. **`@testing-library/react` auto-cleanup requires `globals: true`** — The library checks `typeof afterEach === 'function'` at module load time. With `globals: false` (vitest default), `afterEach` is not a global → auto-cleanup is skipped → multiple renders accumulate in the DOM across tests, causing query-count failures. Set `globals: true` in the vitest config.

3. **`getByText` fails on text inside a mixed text node** — Testing-library's `getByText('UBOT1')` looks for an element whose full text content is "UBOT1". Rendering as `Bot: {team.slack_bot_user_id}` makes the container's text "Bot: UBOT1" → no match. Wrap the value in its own `<span>` so the span's textContent is exactly "UBOT1".

## Product Docs Affected

None. No vdocs/ docs describe the /app route's content prior to this story.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (JSDoc/docstrings added to all exports)
- [x] No new runtime patterns or libraries introduced (test infra only)
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

## Process Feedback

- The task said "No new dependencies" but the test spec explicitly required `@testing-library/react` and `userEvent`. These are not in `package.json` and were genuinely absent. The constraint and the spec contradict each other. Suggest the Team Lead clarify "no new RUNTIME dependencies" vs "no new devDependencies" in future Fast Track tasks.
- The vitest@2.1.9 + vite@8 peer version conflict is a known ecosystem gap. The Sprint Charter should note it — or upgrade vitest to 3.x which supports vite@8. Current workaround (separate vitest.config.ts) is clean but requires the flashcard to propagate forward.
