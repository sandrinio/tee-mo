---
task_id: "STORY-005A-06-dev"
story_id: "STORY-005A-06"
phase: "red+green"
agent: "developer"
worktree: ".worktrees/STORY-005A-06/"
sprint: "S-04"
execution_mode: "Fast Track"
---

# Developer Task — STORY-005A-06 Frontend Install UI (L2 Fast Track)

## Working Directory
`/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-06/` — branch `story/STORY-005A-06`, cut from `sprint/S-04` at commit `405feff` (all 5 backend stories merged).

## Execution Mode: L2 Fast Track — Red + Green in one pass
Write the test file first, confirm failures, then implement, then confirm 9/9 + full suite. One report at the end.

## Story Spec
`.worktrees/STORY-005A-06/product_plans/sprints/sprint-04/STORY-005A-06-frontend-install-ui.md`

Read §1 Spec + §2 Gherkin (9 scenarios) + §3 Implementation Guide in full.

## Mandatory Reading
1. `.worktrees/STORY-005A-06/FLASHCARDS.md` — **especially the 2026-04-11 `vi.hoisted` entry** (Vitest 2.x requires vi.hoisted for module mocks). The TanStack Query discipline entry is also relevant.
2. `.worktrees/STORY-005A-06/.vbounce/sprint-context-S-04.md` — frontend section: Install button must be `<a href>`, NOT `onClick`; banner variants live in a single `BANNER_VARIANTS` lookup.
3. `.worktrees/STORY-005A-06/frontend/src/routes/app.tsx` — current placeholder (Welcome card) that you'll replace.
4. `.worktrees/STORY-005A-06/frontend/src/lib/api.ts` — existing `apiGet`/`apiPost` pattern you'll extend with `listSlackTeams()`. Check whether it uses `VITE_API_URL` or relative paths.
5. `.worktrees/STORY-005A-06/frontend/src/stores/__tests__/authStore.test.ts` — the only existing Vitest test file; use this as a style reference.
6. `.worktrees/STORY-005A-06/frontend/src/routes/login.tsx` and `register.tsx` — reference for TanStack Router route declaration patterns with search/state.
7. `.worktrees/STORY-005A-06/frontend/package.json` — confirm `@tanstack/react-query`, `@tanstack/react-router`, `vitest`, `@testing-library/react` are all already installed. DO NOT add new deps.
8. `.worktrees/STORY-005A-06/frontend/src/components/auth/ProtectedRoute.tsx` — you'll continue wrapping the page in this.

## Explore before coding — answer these first
Before writing any code, run these discovery steps (use Grep/Read only):
1. **How are types organized?** `grep -rn "export interface\|export type" frontend/src/lib/api.ts frontend/src/types/` — is there a `frontend/src/types/` directory already? If so, add `slack.ts` there. If not, put types inline in `api.ts`.
2. **How does `apiGet` work?** Read `frontend/src/lib/api.ts` top-to-bottom. Check its return-type convention, base-URL handling, and error shape.
3. **How are existing routes declared?** Read `frontend/src/routes/login.tsx` and `register.tsx` — note the `createFileRoute` pattern and any `validateSearch` usage.
4. **Is there a `QueryClientProvider` already wired up?** `grep -rn "QueryClientProvider\|QueryClient" frontend/src/` — if not, the test needs to wrap `<AppContent>` in one.
5. **What does the existing Button / Card component look like?** Peek at `frontend/src/components/ui/Card.tsx` — reuse its shell for the team cards and empty state.

Document any non-obvious discoveries in the Dev report under "Exploration notes".

## Files to Modify

### 1. MODIFY `frontend/src/lib/api.ts` — add `listSlackTeams`
At the end of the file:
```typescript
export interface SlackTeam {
  slack_team_id: string;
  slack_bot_user_id: string;
  installed_at: string; // ISO timestamp from backend
}

export interface SlackTeamsResponse {
  teams: SlackTeam[];
}

export async function listSlackTeams(): Promise<SlackTeamsResponse> {
  return apiGet<SlackTeamsResponse>("/api/slack/teams");
}
```
Match the EXACT signature of existing `apiGet<T>` calls in the file — if `apiGet` requires a different argument shape (e.g., passing an auth token explicitly), adapt. Do NOT invent a new helper.

### 2. MODIFY `frontend/src/routes/app.tsx` — replace the welcome card
The current file renders a `Card` with "Welcome to Tee-Mo" and a SignOutButton. Replace the ENTIRE body of `AppContent` (lines ~43-60) with the new Slack Teams page. Keep the `Route` export, the `AppPage` wrapper, and the `ProtectedRoute` import unchanged.

The new `AppContent` must include:
- Header with "Slack Teams" title + `<SignOutButton />` on the right
- Flash banner (driven by `useSearch` — see below)
- Loading skeleton while `useQuery` is fetching
- Inline error with retry if the query fails
- Empty state if `teams.length === 0`
- Team list if `teams.length > 0`, plus a secondary "Install another team" button
- Install button (primary when empty state, secondary when list has items) — ALWAYS an `<a href={`${API_URL}/api/slack/install`}>`, never an `onClick`. The browser must do a full-page navigation so the auth cookie rides along to Slack.

**Route declaration — add `validateSearch`** so `useSearch` returns typed data:
```typescript
import { z } from 'zod'; // if zod is installed; check package.json. If not, use a plain validateSearch function.

const appSearchSchema = /* zod schema OR plain validator */;

export const Route = createFileRoute('/app')({
  component: AppPage,
  validateSearch: (search: Record<string, unknown>): { slack_install?: 'ok' | 'cancelled' | 'expired' | 'error' | 'session_lost' } => {
    const v = search.slack_install;
    const allowed = ['ok', 'cancelled', 'expired', 'error', 'session_lost'] as const;
    return {
      slack_install: typeof v === 'string' && (allowed as readonly string[]).includes(v)
        ? (v as (typeof allowed)[number])
        : undefined,
    };
  },
});
```
Check `frontend/src/routes/login.tsx` / `register.tsx` to see if there's an existing pattern you should match (zod, yup, or a plain function).

**BANNER_VARIANTS lookup** — place it at the top of `app.tsx` (do NOT extract to a new file — the story says to keep it co-located):
```typescript
const BANNER_VARIANTS = {
  ok:           { text: "Tee-Mo installed.",                                       role: "status" as const, className: "bg-emerald-50 text-emerald-900 border-emerald-200" },
  cancelled:    { text: "Install cancelled.",                                      role: "status" as const, className: "bg-slate-50 text-slate-700 border-slate-200"       },
  expired:      { text: "Install session expired — please try again.",             role: "alert"  as const, className: "bg-amber-50 text-amber-900 border-amber-200"       },
  error:        { text: "Install failed. Please try again or check the logs.",     role: "alert"  as const, className: "bg-rose-50 text-rose-900 border-rose-200"           },
  session_lost: { text: "Your session expired during install. Please log in and try again.", role: "alert" as const, className: "bg-amber-50 text-amber-900 border-amber-200" },
};
```

**`FlashBanner` component** — inline in `app.tsx` (small inner component). Reads the variant from props, renders the text + role + className, renders a small `✕` button that calls `onDismiss`. `onDismiss` uses `useNavigate()` to clear the query param via `navigate({ to: '/app', search: {} })`.

**`useQuery` call:**
```typescript
const { data, isLoading, error, refetch } = useQuery({
  queryKey: ['slack-teams'],
  queryFn: listSlackTeams,
  staleTime: 0,
});
```

**Empty state** — a `Card` containing:
- `<h2>No Slack teams yet</h2>`
- `<p>Install Tee-Mo into a Slack workspace to get started</p>`
- `<a className="..." href={`${API_URL}/api/slack/install`}>Install Slack</a>`

Use `const API_URL = import.meta.env.VITE_API_URL ?? ""` at the top.

**Team list** — map over `data.teams` rendering a card per team. Each card shows `slack_team_id`, `slack_bot_user_id`, and a "Installed <relative time>" string. Keep the relative-time formatting simple — `Intl.RelativeTimeFormat` or a plain "Installed at <ISO date>" is fine; don't pull in date-fns or dayjs (no new deps).

### 3. CREATE `frontend/src/routes/__tests__/app.test.tsx` — 9 tests

Set up:
```typescript
import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import userEvent from '@testing-library/user-event';
```

**CRITICAL — `vi.hoisted` for listSlackTeams mock** (FLASHCARDS.md 2026-04-11):
```typescript
const { mockListSlackTeams } = vi.hoisted(() => ({
  mockListSlackTeams: vi.fn(),
}));

vi.mock('../../lib/api', () => ({
  listSlackTeams: mockListSlackTeams,
}));
```

**Mock `useSearch`/`useNavigate`** — the tests need to control the search param per scenario. Mock `@tanstack/react-router`:
```typescript
const { mockSearch, mockNavigate } = vi.hoisted(() => ({
  mockSearch: vi.fn(() => ({})),
  mockNavigate: vi.fn(),
}));

vi.mock('@tanstack/react-router', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-router')>('@tanstack/react-router');
  return {
    ...actual,
    useSearch: () => mockSearch(),
    useNavigate: () => mockNavigate,
  };
});
```

**Mock `ProtectedRoute` and `useAuth`** if needed so the component renders without a real auth store. Simplest: mock `../../components/auth/ProtectedRoute` to just render `children`.

**Per-test setup:** reset all mocks in `beforeEach`, provide a fresh `QueryClient`, render `<AppContent />` directly (bypassing `ProtectedRoute`) inside `<QueryClientProvider>`.

### The 9 Tests

1. **`empty state when no teams`** — `mockListSlackTeams.mockResolvedValue({ teams: [] })`. Wait for `findByText('No Slack teams yet')`. Assert an anchor tag with `href` containing `/api/slack/install` is present.

2. **`team list when teams exist`** — mockResolvedValue one team `{ slack_team_id: "T1", slack_bot_user_id: "UBOT1", installed_at: "2026-04-10T12:00:00Z" }`. Wait for "T1" text. Assert "UBOT1" is visible. Assert the "Install another team" secondary button is visible.

3. **`success banner from slack_install=ok`** — `mockSearch.mockReturnValue({ slack_install: 'ok' })`, mock teams `[]`. Wait for the banner, assert it has `role="status"` and contains "Tee-Mo installed".

4. **`cancelled banner`** — `mockSearch` returns `{ slack_install: 'cancelled' }`. Assert banner contains "Install cancelled".

5. **`expired banner`** — `mockSearch` returns `{ slack_install: 'expired' }`. Assert banner contains "session expired".

6. **`error banner with role=alert`** — `mockSearch` returns `{ slack_install: 'error' }`. Assert banner has `role="alert"` and contains "Install failed".

7. **`session_lost banner`** — `mockSearch` returns `{ slack_install: 'session_lost' }`. Assert banner contains "session expired during install".

8. **`banner dismiss clears query param`** — `mockSearch` returns `{ slack_install: 'ok' }`, render, find the `✕` button (aria-label "Dismiss banner" or similar — set it in the component), click it. Assert `mockNavigate` was called with `{ to: '/app', search: {} }` (or equivalent — whatever the component uses).

9. **`loading skeleton while query is in flight`** — `mockListSlackTeams.mockImplementation(() => new Promise(() => {}))` (never resolves). Render. Assert a skeleton element is visible (use a `data-testid="skeleton-card"` on the skeleton component) AND the "No Slack teams yet" heading is NOT visible yet.

## Execution Steps

### Step 1: Exploration (5 min)
Run the 5 discovery greps/reads listed in "Explore before coding". Write notes in a scratch file OR just keep in memory for the report.

### Step 2: Red Phase — write the test file
Create `frontend/src/routes/__tests__/app.test.tsx` with the 9 tests. Run:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-06/frontend
pnpm vitest run src/routes/__tests__/app.test.tsx 2>&1 | tail -40
```
Expect failures (most likely component-not-found or import errors). Record the failure mode.

### Step 3: Green Phase — implement api.ts + app.tsx
Edit the 2 files per §1 and §2 above. Re-run:
```bash
pnpm vitest run src/routes/__tests__/app.test.tsx 2>&1 | tail -40
```
Target: **9 passed**.

Then the full frontend test suite:
```bash
pnpm vitest run 2>&1 | tail -30
```
Target: all frontend tests passing (the only pre-existing frontend test is `stores/__tests__/authStore.test.ts`, so expect 9 + whatever was there).

### Step 4: Typecheck + lint + build
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-06/frontend
pnpm tsc --noEmit 2>&1 | tail -20
pnpm lint 2>&1 | tail -20  # if lint script exists in package.json
pnpm build 2>&1 | tail -20
```
No TypeScript errors, no lint errors, build succeeds.

### Step 5: Backend full suite — must not regress
Story doesn't touch backend, but the worktree has a `.env` symlink so we can quickly verify:
```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-005A-06/backend
/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/pytest 2>&1 | tail -10
```
Target: 73 passed (unchanged from before this story).

## Success Criteria
- 9/9 new frontend tests pass
- Full frontend suite passes (including pre-existing `authStore.test.ts`)
- `pnpm tsc --noEmit` clean
- `pnpm build` succeeds
- Backend suite still 73/73 (no regression)
- Install button is an `<a href>` not an onClick
- BANNER_VARIANTS lookup exists and is the ONLY place banner copy lives
- `validateSearch` on the route declaration narrows the search type

## Report
`.vbounce/reports/STORY-005A-06-dev-green.md`:
```yaml
---
story_id: "STORY-005A-06"
agent: "developer"
phase: "red+green"
status: "implementation-complete"
files_modified:
  - { path: "frontend/src/lib/api.ts", change: "add listSlackTeams + SlackTeam/SlackTeamsResponse types" }
  - { path: "frontend/src/routes/app.tsx", change: "replace welcome card with Slack Teams page (empty state, team list, flash banners, install button, loading/error states)" }
  - { path: "frontend/src/routes/__tests__/app.test.tsx", change: "NEW — 9 component tests" }
test_result: "9 passed (new frontend), N passed (full frontend), 73 passed (backend unchanged)"
typecheck_result: "clean"
build_result: "success"
correction_tax_pct: <>
flashcards_flagged: []
input_tokens: <>
output_tokens: <>
total_tokens: <>
---
```
Body: exploration notes (what you found in the 5 discovery steps), file changes summary, any flashcards flagged, typecheck/build output summary.

## Critical Rules
- **Install button is `<a href>`, NOT `onClick`.** Tests MUST assert the anchor tag.
- **Use `vi.hoisted`** for module mocks per FLASHCARDS.md — plain top-level `vi.fn()` won't work with Vitest 2.x hoisted `vi.mock`.
- **No new dependencies.** Use only what's already in `package.json`.
- **BANNER_VARIANTS lookup is the SINGLE source of banner copy.** Do not spread strings across the component.
- **No `fetch` outside `lib/api.ts`.**
- **Do not add toast/snackbar libraries.** Banners are inline DOM.
- **Do not touch backend files.** Frontend only.
- **Use `pnpm`** — this is a pnpm workspace.

## Final Message Must Include
- 9-test output showing `9 passed`
- Full frontend suite summary
- TypeScript check result
- Build result
- Backend suite (should still be 73 passed)
- List of files modified
- Any flashcards flagged
- Self-assessed Correction Tax %
