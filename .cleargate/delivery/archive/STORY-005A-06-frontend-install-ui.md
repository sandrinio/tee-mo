---
story_id: "STORY-005A-06-frontend-install-ui"
parent_epic_ref: "EPIC-005-phase-a"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-04/STORY-005A-06-frontend-install-ui.md`. Shipped in sprint S-04, carried forward during ClearGate migration 2026-04-24.

# STORY-005A-06: Frontend `/app` — Install Slack Button + Teams List + Flash Banners

**Complexity: L2** — Standard, 3 frontend files modified, known patterns (TanStack Query for data, TanStack Router for query params, Vitest for tests).

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **logged-in Tee-Mo user**,
> I want to **see my installed Slack teams on `/app` and a clear "Install Slack" button when I have none**,
> So that **I can install the bot into a Slack workspace and visually confirm the install succeeded**.

### 1.2 Detailed Requirements

- **Req 1 — Replace `/app` body:** The current welcome card in `frontend/src/routes/app.tsx` (the "EPIC-003 will replace the body" placeholder) is replaced with:
  - A page header "Slack Teams"
  - **If `teams.length === 0`:** an empty-state card containing the heading "No Slack teams yet", a one-sentence helper ("Install Tee-Mo into a Slack workspace to get started"), and a primary `<a>` button "Install Slack" (see Req 3).
  - **If `teams.length > 0`:** a list of team cards. Each card shows: `slack_team_id`, `slack_bot_user_id`, "Installed <relative time>". Plus a secondary "Install another team" button at the bottom (same `<a>`).
  - The existing `SignOutButton` stays in the header.
- **Req 2 — Data fetching:** Use TanStack Query (`useQuery`) with key `["slack-teams"]` to call a new `listSlackTeams()` function added to `frontend/src/lib/api.ts`. Stale time: 0 (always refetch on `/app` mount so the post-install redirect shows fresh data). FLASHCARDS.md: never call `fetch` directly from a component.
- **Req 3 — Install button = `<a href>`, NOT a fetch:** Per Q7 decision, the Install button is a plain anchor tag:
  ```tsx
  <a href={`${API_URL}/api/slack/install`} className="...">Install Slack</a>
  ```
  Where `API_URL` comes from `import.meta.env.VITE_API_URL`. Same-origin in production (no CORS). Browser navigates away from the SPA on click → Slack consent → Slack redirects to `/api/slack/oauth/callback` → backend redirects to `/app?slack_install=ok`. The SPA remounts.
- **Req 4 — Flash banners:** Read the `slack_install` query parameter via TanStack Router's `useSearch()` hook. Render an inline banner above the team list:
  - `?slack_install=ok` → green success banner: "Tee-Mo installed."
  - `?slack_install=cancelled` → neutral gray banner: "Install cancelled."
  - `?slack_install=expired` → yellow banner: "Install session expired — please try again."
  - `?slack_install=error` → red banner: "Install failed. Please try again or check the logs."
  - `?slack_install=session_lost` → yellow banner: "Your session expired during install. Please log in and try again."
  - **No `?slack_install` param** → no banner.
  - The banner has a small ✕ button that clears the query param via `navigate({ search: { } })`. Banner does NOT auto-dismiss.
- **Req 5 — Loading + error states:** While the `useQuery` is fetching, render a skeleton card. On query error, render a small inline error: "Couldn't load teams. <Retry>".
- **Req 6 — Types:** Add TypeScript types matching the backend `SlackTeamResponse` from STORY-005A-05. Either a new `frontend/src/types/slack.ts` file or inline in `lib/api.ts` — pick whichever matches the existing convention (check how user types are organized in the codebase first).
- **Req 7 — Design tokens:** Use existing Tailwind classes consistent with the design guide (`tee_mo_design_guide.md` ADR-022). Coral primary for the Install button (`bg-rose-500` or whatever the existing primary class is — verify in code).
- **Req 8 — Accessibility:** The banner has `role="status"` (or `role="alert"` for error/expired/session_lost). Buttons have visible focus rings.

### 1.3 Out of Scope
- Workspace cards under each team (knowledge silos) — S-05 / EPIC-003 Slice B.
- "Make default" toggles — S-05.
- Channel binding pickers — Phase B.
- Team display name (would require backend `team.info` call) — deferred unless trivial.
- Uninstall / disconnect button — out of scope for Phase A; out of scope for hackathon overall.
- Toast/snackbar library — banners are inline DOM, no library.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: /app Install Slack UI

  Background:
    Given alice is logged in
    And /app is mounted

  Scenario: Empty state when no teams
    Given GET /api/slack/teams returns {"teams": []}
    When the page renders
    Then the heading "No Slack teams yet" is visible
    And the "Install Slack" button is visible
    And the button is an anchor tag with href ending in "/api/slack/install"

  Scenario: Team list when teams exist
    Given GET /api/slack/teams returns one team T1 with bot_user UBOT1
    When the page renders
    Then a card with text "T1" is visible
    And a card with text "UBOT1" is visible
    And the "Install another team" secondary button is visible

  Scenario: Success banner from query param
    Given the URL is /app?slack_install=ok
    When the page renders
    Then a banner with role="status" containing "Tee-Mo installed" is visible

  Scenario: Cancelled banner
    Given the URL is /app?slack_install=cancelled
    Then a neutral banner containing "Install cancelled" is visible

  Scenario: Expired banner
    Given the URL is /app?slack_install=expired
    Then a banner containing "session expired" is visible

  Scenario: Error banner
    Given the URL is /app?slack_install=error
    Then a banner with role="alert" containing "Install failed" is visible

  Scenario: Session lost banner
    Given the URL is /app?slack_install=session_lost
    Then a banner containing "session expired during install" is visible

  Scenario: Banner dismiss clears query param
    Given the URL is /app?slack_install=ok
    When the user clicks the banner's ✕ button
    Then the URL becomes /app
    And the banner is no longer visible

  Scenario: Loading skeleton
    Given the listSlackTeams query is in flight
    Then a skeleton card is rendered
    And the "No Slack teams yet" heading is NOT yet rendered
```

### 2.2 Verification Steps (Manual)
- [ ] `cd frontend && pnpm vitest run src/routes/__tests__/app.test.tsx`
- [ ] `cd frontend && pnpm dev` → register/login → land on `/app` → see empty state → click Install Slack → (after STORY-005A-04 lands) complete OAuth → see success banner + team card.

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-005A-05 merged (`GET /api/slack/teams` exists) | [ ] |
| **Env** | `VITE_API_URL` already configured (S-02). | [ ] |
| **Frontend deps** | `@tanstack/react-query`, `@tanstack/react-router` (already installed). No new deps. | [ ] |

### 3.1 Test Implementation
- Modify or create `frontend/src/routes/__tests__/app.test.tsx`.
- Mock `listSlackTeams` via `vi.mock` + `vi.hoisted` (FLASHCARDS.md 2026-04-11 entry — vi.hoisted is required for Vitest 2.x).
- Mock TanStack Router's `useSearch()` per scenario.
- 9 tests (one per Gherkin scenario).

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `frontend/src/routes/app.tsx` (MODIFY — replace welcome card body) |
| **Related Files** | `frontend/src/lib/api.ts` (MODIFY — add `listSlackTeams`), `frontend/src/types/slack.ts` (NEW — or inline types in `api.ts`, match existing convention) |
| **New Test Files** | `frontend/src/routes/__tests__/app.test.tsx` (NEW or MODIFY) |
| **ADR References** | ADR-014 (frontend stack), ADR-022 (design system — coral primary, slate neutrals) |
| **First-Use Pattern** | **Maybe** — first time this codebase reads URL query params via TanStack Router's `useSearch()`. Verify if any existing route does it; if not, add a flashcard after merge. |

### 3.3 Technical Logic

**`api.ts` addition:**
```typescript
export interface SlackTeam {
  slack_team_id: string;
  slack_bot_user_id: string;
  installed_at: string; // ISO timestamp
}

export interface SlackTeamsResponse {
  teams: SlackTeam[];
}

export async function listSlackTeams(): Promise<SlackTeamsResponse> {
  return apiGet<SlackTeamsResponse>("/api/slack/teams");
}
```

**`app.tsx` shape (pseudocode):**
```tsx
import { useQuery } from "@tanstack/react-query";
import { useSearch, useNavigate } from "@tanstack/react-router";
import { listSlackTeams } from "../lib/api";

const API_URL = import.meta.env.VITE_API_URL ?? "";

export function AppRoute() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["slack-teams"],
    queryFn: listSlackTeams,
    staleTime: 0,
  });
  const search = useSearch({ from: "/app" });
  const navigate = useNavigate();

  return (
    <div>
      <Header />
      {search.slack_install && (
        <FlashBanner
          variant={search.slack_install}
          onDismiss={() => navigate({ search: {} })}
        />
      )}
      {isLoading && <SkeletonCard />}
      {error && <InlineError onRetry={refetch} />}
      {data && data.teams.length === 0 && <EmptyState installHref={`${API_URL}/api/slack/install`} />}
      {data && data.teams.length > 0 && <TeamList teams={data.teams} installHref={`${API_URL}/api/slack/install`} />}
    </div>
  );
}
```

**`FlashBanner` variant → text/role mapping** (lift to a small lookup object inside `app.tsx` or a new `FlashBanner` component file — either is fine, prefer keeping it co-located unless it grows >40 lines):
```typescript
const BANNER_VARIANTS = {
  ok:           { text: "Tee-Mo installed.", role: "status",  className: "bg-emerald-50 text-emerald-900 border-emerald-200" },
  cancelled:    { text: "Install cancelled.", role: "status",  className: "bg-slate-50 text-slate-700 border-slate-200" },
  expired:      { text: "Install session expired — please try again.", role: "alert", className: "bg-amber-50 text-amber-900 border-amber-200" },
  error:        { text: "Install failed. Please try again or check the logs.", role: "alert", className: "bg-rose-50 text-rose-900 border-rose-200" },
  session_lost: { text: "Your session expired during install. Please log in and try again.", role: "alert", className: "bg-amber-50 text-amber-900 border-amber-200" },
};
```

**TanStack Router search param schema:** The route definition needs to declare `slack_install` as an optional search param so `useSearch` returns the typed value. Pattern for defining a route's search schema is in TanStack Router docs — verify existing route declarations in the codebase first.

### 3.4 API Contract
N/A — this story consumes `/api/slack/teams` and `/api/slack/install`, both contracts already documented in STORY-005A-03 + STORY-005A-05.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |
| Component tests | 9 | One per Gherkin scenario |
| Integration tests | 0 — N/A (frontend only) | |
| E2E / acceptance | 1 manual | Click-through against staging or local backend |

### 4.2 Definition of Done
- [ ] TDD Red phase enforced — all 9 component scenarios written failing first.
- [ ] §4.1 minimum counts met.
- [ ] FLASHCARDS.md consulted (vi.hoisted, TanStack Query discipline, useSearch first-use if applicable).
- [ ] No `fetch` calls outside `lib/api.ts`.
- [ ] Install button is `<a href>`, not an `onClick` handler.
- [ ] Banner dismiss clears the query param via `navigate({ search: {} })`.
- [ ] Visual: empty state and team list render correctly in the local dev server (pnpm dev) at `http://localhost:5173/app`.
- [ ] No ADR violations (uses Tailwind + TanStack Router + TanStack Query per ADR-014; coral palette per ADR-022).

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 287 | 8,041 | 8,328 |
