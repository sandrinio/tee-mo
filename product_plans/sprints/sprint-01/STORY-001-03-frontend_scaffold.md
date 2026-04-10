---
story_id: "STORY-001-03-frontend_scaffold"
parent_epic_ref: "EPIC-001"
status: "Ready to Bounce — Fast Track approved"
ambiguity: "🟢 Low"
context_source: "Charter §3.2 + Design Guide §2, §3, §11.1 + Roadmap ADR-022"
actor: "Frontend Dev (Solo)"
complexity_label: "L2"
---

# STORY-001-03: Frontend Scaffold + Design System Foundation

**Complexity: L2** — Vite + React 19 + Tailwind 4 CSS-first config with ALL design tokens from the Design Guide, Inter + JetBrains Mono fonts, TanStack Router, landing page with design-system typography. ~1.5 hours.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **frontend developer**, I want **a working React scaffold with Tailwind 4 pre-configured with every design token and font from the Design Guide**, so that every subsequent frontend story can use `bg-brand-500` / `text-heading` / `font-sans` without any further setup.

### 1.2 Detailed Requirements

- **R1**: Scaffold a Vite 8.0.8 React TypeScript project in `frontend/`. Use `npm create vite@latest frontend -- --template react-ts` then upgrade/pin per Charter §3.2.
- **R2**: Pin exact versions from Charter §3.2: `react@19.2.5`, `react-dom@19.2.5`, `tailwindcss@^4.2.0`, `vite@^8.0.8`, `@tanstack/react-router@^1.168.12`, `@tanstack/react-query@^5.97.0`, `zustand@^5.0.12`, `@supabase/supabase-js@^2.50.0`.
- **R3**: Install design system deps: `@fontsource/inter`, `@fontsource/jetbrains-mono`, `lucide-react`.
- **R4**: Create `frontend/src/app.css` using Tailwind 4's **CSS-first config** via `@theme` (see Design Guide §11.1). Every color token from Design Guide §2 must be defined: all 5 brand shades, all 8 slate neutrals, all 4 semantic colors.
- **R5**: Load Inter and JetBrains Mono via `@fontsource` imports in `app.css` or `main.tsx`. Apply Inter feature settings (`'cv11', 'ss01', 'ss03'`) per Design Guide §3.1.
- **R6**: Configure `font-sans` and `font-mono` in the `@theme` block to map to Inter and JetBrains Mono respectively.
- **R7**: Set up TanStack Router with file-based routes: `src/routes/__root.tsx` (shell layout with `<Outlet />`) and `src/routes/index.tsx` (landing page).
- **R8**: Landing page (`index.tsx`) renders a typography demo:
  - Display: "Tee-Mo" using `text-4xl font-semibold tracking-tight text-slate-900`
  - Subtitle: "Your BYOK Slack assistant" using `text-base text-slate-500`
  - Monospace sample: `font-mono text-sm text-slate-700` showing a dummy code snippet like `GET /api/health`
  - Brand color swatch: a small `h-8 w-8 rounded-md bg-brand-500` box next to the title to prove tokens work
- **R9**: `vite.config.ts` uses `@tailwindcss/vite` plugin (Tailwind 4's canonical setup), not PostCSS.
- **R10**: Dev server runs on port 5173 (Vite default). Landing page renders at `http://localhost:5173/`.

### 1.3 Out of Scope
- No API calls (STORY-001-04).
- No `Button`, `Card`, `Badge` components (STORY-001-04).
- No auth, no routes beyond `/`.
- No production build config tuning.
- No dark mode (Design Guide §2.4 defers dark mode).

### TDD Red Phase: No
Rationale: Scaffold and design tokens. Visual verification is the right gate, not automated tests.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Frontend scaffold with design system

  Scenario: Dev server boots
    Given the frontend directory is set up
    When I run `npm install && npm run dev`
    Then the Vite dev server starts on port 5173
    And no errors are printed to the console

  Scenario: Landing page renders with typography
    Given the dev server is running
    When I open http://localhost:5173/ in a browser
    Then I see the heading "Tee-Mo" in Inter font-semibold
    And I see the subtitle "Your BYOK Slack assistant" in slate-500
    And I see a coral (#F43F5E) square swatch next to the heading
    And I see a monospace code sample in JetBrains Mono

  Scenario: Brand tokens are queryable from any component
    Given a React component uses `className="bg-brand-500"`
    When the page renders
    Then that element has background-color: rgb(244, 63, 94)

  Scenario: No Tailwind config file exists
    Given Tailwind 4 is installed
    Then there is no tailwind.config.js or tailwind.config.ts file
    And all theme customization lives in src/app.css under @theme
```

### 2.2 Verification Steps (Manual)
- [ ] `npm install` in `frontend/` succeeds with zero deprecation warnings on critical deps
- [ ] `npm run dev` starts the Vite server
- [ ] Browser at `localhost:5173` shows the styled landing page
- [ ] DevTools Computed tab on the swatch shows `rgb(244, 63, 94)` (brand-500)
- [ ] DevTools Fonts tab shows "Inter" loaded (not system fallback)
- [ ] `ls frontend/` shows NO `tailwind.config.*` file
- [ ] TypeScript has no errors (`npm run build` or `tsc --noEmit`)

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Node.js** | 20.x or 22.x installed | [ ] |
| **npm** | 10+ (`npm -v`) | [ ] |
| **Env Vars** | None for this story | [x] |
| **Services** | None for this story | [x] |

### 3.1 Test Implementation
No unit tests — visual inspection is the test. L2 scaffolds are exempted from the normal test floor because the "logic" is declarative config.

Add `"test": "echo 'No tests yet — see story acceptance criteria'"` to `package.json` as a placeholder so the contract is honest.

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/app.css` (new — the design token home) |
| **Related Files** | `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/routes/__root.tsx`, `frontend/src/routes/index.tsx`, `frontend/tsr.config.json` |
| **New Files Needed** | Yes — entire directory |
| **ADR References** | ADR-022 (Design System), ADR-014 (Frontend Stack), Design Guide §2, §3, §6, §11.1 |
| **First-Use Pattern** | Yes — first React + Tailwind 4 in the repo. Tailwind 4 is newer so **read Design Guide §11.1 before writing app.css**. |

### 3.3 Technical Logic

**`frontend/src/app.css`** (exact contents):
```css
@import "tailwindcss";
@import "@fontsource/inter/400.css";
@import "@fontsource/inter/500.css";
@import "@fontsource/inter/600.css";
@import "@fontsource/jetbrains-mono/400.css";

@theme {
  /* Brand — coral/rose, Design Guide §2.1 */
  --color-brand-50:  #FFF1F2;
  --color-brand-100: #FFE4E6;
  --color-brand-500: #F43F5E;
  --color-brand-600: #E11D48;
  --color-brand-700: #BE123C;

  /* Semantic — Design Guide §2.3 */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-danger:  #E11D48;
  --color-info:    #0EA5E9;

  /* Typography — Design Guide §3.1 */
  --font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', monospace;
}

/* Apply Inter stylistic alternates globally */
html {
  font-feature-settings: 'cv11', 'ss01', 'ss03';
}

body {
  @apply bg-slate-50 text-slate-900 font-sans antialiased;
}
```

> **Note**: Tailwind slate colors are built in — no need to redefine them in `@theme`. Only add custom colors (brand + semantic).

**`frontend/vite.config.ts`**:
```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { TanStackRouterVite } from '@tanstack/router-plugin/vite';

export default defineConfig({
  plugins: [TanStackRouterVite(), react(), tailwindcss()],
  server: { port: 5173 },
});
```

**`frontend/index.html`** — standard Vite template with `<title>Tee-Mo</title>`.

**`frontend/src/main.tsx`**:
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { routeTree } from './routeTree.gen';
import './app.css';

const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
```

**`frontend/src/routes/__root.tsx`**:
```tsx
import { createRootRoute, Outlet } from '@tanstack/react-router';

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50">
      <Outlet />
    </div>
  ),
});
```

**`frontend/src/routes/index.tsx`**:
```tsx
import { createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: Landing,
});

function Landing() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <div className="flex items-center gap-4">
        <div className="h-10 w-10 rounded-md bg-brand-500" aria-hidden />
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">Tee-Mo</h1>
      </div>
      <p className="mt-3 text-base text-slate-500">Your BYOK Slack assistant.</p>
      <pre className="mt-8 rounded-md bg-slate-100 px-4 py-3 font-mono text-sm text-slate-700">
        GET /api/health → {'{'}"status":"ok"{'}'}
      </pre>
    </main>
  );
}
```

**`frontend/package.json`** — confirm `"type": "module"` and the `dev`, `build`, `preview` scripts from the Vite template. Pin versions per Charter §3.2.

### 3.4 API Contract
No API surface. STORY-001-04 adds the `/api/health` fetch.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (scaffold) | |
| Component tests | 0 — N/A (scaffold) | |
| E2E / acceptance tests | 0 — N/A (visual) | |
| Integration tests | 0 — N/A | |

> Tests exempt: L2 scaffolds with no business logic. Visual verification per §2.2 is the gate.

### 4.2 Definition of Done
- [ ] `npm install` succeeds
- [ ] `npm run dev` starts on 5173
- [ ] Landing page renders with correct typography (Inter), brand swatch (coral), and monospace sample (JetBrains Mono)
- [ ] Brand token accessible as `bg-brand-500` utility class
- [ ] No `tailwind.config.*` file exists — all config in `app.css`
- [ ] `npm run build` compiles without TypeScript errors
- [ ] No ADR violations (Design Guide §11.3 forbidden packages NOT installed)

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
