---
story_id: "STORY-001-04-ui_primitives_smoke"
parent_epic_ref: "EPIC-001"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-11T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-01/STORY-001-04-ui_primitives_smoke.md`. Shipped in sprint S-01, carried forward during ClearGate migration 2026-04-24.

# STORY-001-04: UI Primitives + End-to-End Smoke Test

**Complexity: L1** — Build 3 reusable primitives (Button, Card, Badge) exactly per Design Guide §6. Update landing page to fetch backend `/api/health` and render the result via these primitives. ~30-45 min.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **hackathon developer**, I want **the first three design system primitives and an end-to-end smoke test that proves the whole stack is wired**, so that I can open the browser on Day 1 and see a Card showing "Backend: ok" as proof the plumbing works.

### 1.2 Detailed Requirements

- **R1**: Create `frontend/src/components/ui/Button.tsx` implementing exactly the 4 variants from Design Guide §6.1 (`primary`, `secondary`, `ghost`, `danger`) and 3 sizes (`sm`, `md`, `lg`). Default size `md`, default variant `primary`. All spacing, radius, transition, focus-ring classes must match the Design Guide spec verbatim.
- **R2**: Create `frontend/src/components/ui/Card.tsx` — `rounded-lg border border-slate-200 bg-white p-6`. Accepts `className` for composition. Exports both `Card` and optional `CardHeader` / `CardBody` for semantic clarity.
- **R3**: Create `frontend/src/components/ui/Badge.tsx` implementing the 5 variants from Design Guide §6.6: `success`, `warning`, `danger`, `info`, `neutral`. Includes the colored dot per the spec.
- **R4**: Create `frontend/src/lib/api.ts` exporting a typed `apiGet<T>(path: string): Promise<T>` helper. Uses `fetch` against `VITE_API_URL` env var (default `http://localhost:8000`). Throws on non-2xx. Includes `credentials: 'include'` for future auth compat.
- **R5**: Update `frontend/src/routes/index.tsx` — fetch `/api/health` on mount using TanStack Query (`useQuery`). Render:
  - Display heading "Tee-Mo" (from STORY-001-03 — keep as-is)
  - Subtitle (from STORY-001-03 — keep as-is)
  - A `<Card>` containing:
    - Section title "System Status" (`text-lg font-semibold`)
    - For each of the 4 tables: row with table name (mono) + `<Badge>` (success if "ok", danger otherwise)
    - Overall backend badge: success if `status === "ok"`, warning if `"degraded"`, danger on fetch error
  - A `<Button variant="primary">Continue</Button>` below the card (disabled, no click handler yet)
- **R6**: Install `@tanstack/react-query` client in `main.tsx` with a `QueryClientProvider` wrapping the `RouterProvider`.
- **R7**: Create `frontend/.env.example` with `VITE_API_URL=http://localhost:8000` documented.

### 1.3 Out of Scope
- No full `Input` component (deferred to Sprint 2 auth).
- No `Modal`, `Skeleton`, `Empty State` (deferred).
- No Button `onClick` wiring — the button is visually present only.
- No routing beyond the landing page.
- No tests beyond the single smoke test.

### TDD Red Phase: No
Rationale: L1 story, 45min budget, primitives are pure presentational. Visual verification is the gate.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: End-to-end smoke test

  Scenario: Happy path — backend is up, all tables exist
    Given the backend is running on port 8000
    And all migrations have been applied
    And the frontend is running on port 5173
    When I open http://localhost:5173/
    Then I see the heading "Tee-Mo"
    And I see a Card with section title "System Status"
    And I see a green Badge for "teemo_users" saying "ok"
    And I see a green Badge for "teemo_workspaces" saying "ok"
    And I see a green Badge for "teemo_knowledge_index" saying "ok"
    And I see a green Badge for "teemo_skills" saying "ok"
    And I see an overall "Backend" badge in green saying "ok"
    And I see a disabled "Continue" primary button below the card

  Scenario: Backend down — fetch fails
    Given the backend is NOT running
    When I open http://localhost:5173/
    Then the overall Backend badge is red saying "error"
    And the Card still renders (no blank page)
    And the Button is still visible

  Scenario: One table missing — degraded
    Given the backend is running
    And the teemo_skills table has been temporarily renamed
    When I open http://localhost:5173/
    Then the overall Backend badge is amber saying "degraded"
    And the teemo_skills row badge is red
    And the other 3 table badges are green
```

### 2.2 Verification Steps (Manual)
- [ ] Visit `http://localhost:5173/` with backend running — see all-green Card
- [ ] Stop backend with `Ctrl+C` — refresh browser — Card shows red "error" badge but still renders
- [ ] Restart backend — refresh — back to all-green
- [ ] DevTools Network tab confirms ONE `/api/health` request (not a loop)
- [ ] Inspect a primary button in DevTools — computed `background-color: rgb(244, 63, 94)` (brand-500)
- [ ] Tab through the page with keyboard — Button shows a coral focus ring (brand-500)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-001-01 merged** | `backend/app/main.py` has `/api/health` | [ ] |
| **STORY-001-02 merged** | Health endpoint reports all 4 teemo_ tables | [ ] |
| **STORY-001-03 merged** | Design tokens, Tailwind 4, TanStack Router working | [ ] |
| **Both servers running** | Backend on 8000, frontend on 5173 | [ ] |

### 3.1 Test Implementation
No automated tests required (L1 L1 scaffold). Visual verification per §2.2 is the gate.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/index.tsx` (update from STORY-001-03) |
| **Related Files** | `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/Card.tsx`, `frontend/src/components/ui/Badge.tsx`, `frontend/src/lib/api.ts`, `frontend/src/main.tsx` (add QueryClientProvider), `frontend/.env.example` |
| **New Files Needed** | Yes — 6 new files + 2 updates |
| **ADR References** | ADR-022 (Design System), Design Guide §6.1/§6.3/§6.6 |
| **First-Use Pattern** | Yes — first TanStack Query usage in Tee-Mo. Keep it minimal — one `useQuery` call. |

### 3.3 Technical Logic

**`frontend/src/components/ui/Button.tsx`** — per Design Guide §6.1:
```tsx
import { forwardRef, type ButtonHTMLAttributes } from 'react';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const variantClasses: Record<Variant, string> = {
  primary:   'bg-brand-500 text-white hover:bg-brand-600',
  secondary: 'bg-white text-slate-900 border border-slate-300 hover:bg-slate-50 hover:border-slate-400',
  ghost:     'text-slate-700 hover:bg-slate-100',
  danger:    'bg-rose-600 text-white hover:bg-rose-700',
};

const sizeClasses: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', ...rest }, ref) => (
    <button
      ref={ref}
      className={[
        'inline-flex items-center gap-2 font-medium rounded-md transition-colors duration-150',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white',
        variantClasses[variant],
        sizeClasses[size],
        className,
      ].join(' ')}
      {...rest}
    />
  ),
);
Button.displayName = 'Button';
```

**`frontend/src/components/ui/Card.tsx`** — per Design Guide §6.3:
```tsx
import type { HTMLAttributes } from 'react';

export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={['rounded-lg border border-slate-200 bg-white p-6', className].join(' ')}
      {...rest}
    />
  );
}
```

**`frontend/src/components/ui/Badge.tsx`** — per Design Guide §6.6:
```tsx
import type { HTMLAttributes } from 'react';

type BadgeVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const variantClasses: Record<BadgeVariant, { bg: string; text: string; dot: string }> = {
  success: { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  warning: { bg: 'bg-amber-50',   text: 'text-amber-700',   dot: 'bg-amber-500'   },
  danger:  { bg: 'bg-rose-50',    text: 'text-rose-700',    dot: 'bg-rose-500'    },
  info:    { bg: 'bg-sky-50',     text: 'text-sky-700',     dot: 'bg-sky-500'     },
  neutral: { bg: 'bg-slate-100',  text: 'text-slate-700',   dot: 'bg-slate-400'   },
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

export function Badge({ variant = 'neutral', className = '', children, ...rest }: BadgeProps) {
  const v = variantClasses[variant];
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium',
        v.bg, v.text, className,
      ].join(' ')}
      {...rest}
    >
      <span className={['h-1.5 w-1.5 rounded-full', v.dot].join(' ')} />
      {children}
    </span>
  );
}
```

**`frontend/src/lib/api.ts`**:
```ts
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, { credentials: 'include' });
  if (!r.ok) throw new Error(`API ${path} failed: ${r.status}`);
  return r.json() as Promise<T>;
}
```

**Update `frontend/src/main.tsx`** — add QueryClientProvider:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { routeTree } from './routeTree.gen';
import './app.css';

const router = createRouter({ routeTree });
const queryClient = new QueryClient();

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
```

**Update `frontend/src/routes/index.tsx`**:
```tsx
import { createFileRoute } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../lib/api';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';

interface HealthResponse {
  status: 'ok' | 'degraded';
  service: string;
  version: string;
  database: Record<string, string>;
}

export const Route = createFileRoute('/')({
  component: Landing,
});

const TABLES = ['teemo_users', 'teemo_workspaces', 'teemo_knowledge_index', 'teemo_skills'] as const;

function Landing() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/api/health'),
    retry: false,
  });

  const overallVariant = isError
    ? 'danger'
    : isLoading
      ? 'neutral'
      : data?.status === 'ok'
        ? 'success'
        : 'warning';

  const overallLabel = isError ? 'error' : isLoading ? 'loading…' : data?.status ?? 'unknown';

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 rounded-md bg-brand-500" aria-hidden />
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">Tee-Mo</h1>
      </div>
      <p className="mt-3 text-base text-slate-500">Your BYOK Slack assistant.</p>

      <Card className="mt-8">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">System Status</h2>
          <Badge variant={overallVariant}>Backend: {overallLabel}</Badge>
        </div>
        <ul className="space-y-2">
          {TABLES.map((t) => {
            const tableStatus = data?.database?.[t] ?? (isError ? 'unreachable' : '…');
            const ok = tableStatus === 'ok';
            return (
              <li key={t} className="flex items-center justify-between">
                <code className="font-mono text-sm text-slate-700">{t}</code>
                <Badge variant={ok ? 'success' : isError ? 'danger' : 'warning'}>
                  {tableStatus}
                </Badge>
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="mt-6">
        <Button variant="primary" disabled>Continue</Button>
      </div>
    </main>
  );
}
```

### 3.4 API Contract
Consumes `GET /api/health` from STORY-001-02. Shape defined in that story.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | L1 presentational |
| Component tests | 0 — N/A | Visual verification |
| E2E / acceptance tests | 0 — N/A | Manual per §2.2 |
| Integration tests | 0 — N/A | |

### 4.2 Definition of Done
- [ ] All 3 primitives render per Design Guide specs verbatim
- [ ] Landing page renders all 3 Gherkin scenarios correctly (happy path, backend down, degraded)
- [ ] Primary button has coral background (`rgb(244, 63, 94)`) and a working focus ring
- [ ] Only ONE `/api/health` request per page load (no retry loop)
- [ ] `.env.example` committed with `VITE_API_URL` documented
- [ ] No ADR violations

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
