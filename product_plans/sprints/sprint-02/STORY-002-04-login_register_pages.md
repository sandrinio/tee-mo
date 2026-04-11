---
story_id: "STORY-002-04-login_register_pages"
parent_epic_ref: "EPIC-002"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Charter §10 Epic Seed Map + Design Guide §6 (primitives) + new_app login.tsx / ProtectedRoute.tsx / SignOutButton.tsx"
actor: "Frontend Dev (Solo)"
complexity_label: "L2"
---

# STORY-002-04: Login + Register Pages + ProtectedRoute + `/app` Placeholder

**Complexity: L2** — Four new routes (`/login`, `/register`, `/app`), one route guard, one sign-out button. All styled with the S-01 design system primitives. ~1.5 hours.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **first-time Tee-Mo visitor**, I want to **register for an account, be auto-logged-in, land on a minimal "/app" page that greets me, and be able to log out**, So that **EPIC-003 can replace the body of `/app` with the real workspace dashboard in the next sprint without any router refactor**.

### 1.2 Detailed Requirements

- **R1 — Create `frontend/src/routes/login.tsx`** (TanStack Router file-based route):
  - Renders a centered `Card` containing:
    - Heading: "Sign in to Tee-Mo" (`text-2xl font-semibold tracking-tight text-slate-900`).
    - Email input (HTML `type="email"`, `required`, `autoComplete="email"`).
    - Password input (HTML `type="password"`, `required`, `autoComplete="current-password"`).
    - Primary `Button` labeled "Sign in".
    - Inline error display beneath the form when `login()` rejects — show `err.message` from the backend detail in a rose-colored block (`bg-rose-50 border border-rose-200 text-rose-800`).
    - Link below the form: "No account? [Create one](/register)".
  - On submit: call `useAuth.getState().login(email, password)`. On success, navigate to `/app` (TanStack `useNavigate`). On failure, render the error block.
  - **If the store's status is already `'authed'` when the page mounts, redirect to `/app` immediately** (via a `useEffect` that reads `useAuth((s) => s.status)`).
  - **No Google OAuth button, no "Continue with Google" text anywhere.**
- **R2 — Create `frontend/src/routes/register.tsx`**:
  - Same visual structure as login, but:
    - Heading: "Create your Tee-Mo account".
    - Password input has `autoComplete="new-password"`.
    - Helper text under password: "Up to 72 characters."
    - Primary `Button` labeled "Create account".
    - Link: "Already have an account? [Sign in](/login)".
  - **Client-side validation matching the backend** (run before hitting the network):
    - `password.length === 0` → "Password is required"
    - Encoded UTF-8 byte length > 72 → "Password is too long (max 72 bytes)". Compute with `new TextEncoder().encode(password).length` — **NOT** `password.length`, because `"é"` is 2 bytes.
  - On submit: call `useAuth.getState().register(email, password)`. On success, navigate to `/app`. On failure, show the error block.
  - Same authed-redirect `useEffect` as login.
- **R3 — Create `frontend/src/components/auth/ProtectedRoute.tsx`**:
  - Copy structurally from `new_app/frontend/src/components/auth/ProtectedRoute.tsx` with three adaptations:
    1. Import `useAuth` from `../../stores/authStore`.
    2. The new store exposes `status` (not `isLoading` / `isAuthenticated`). Rewrite the guard logic: `if (status === 'unknown') show spinner`; `if (status === 'anon') redirect to /login`; `else render children`.
    3. The spinner Tailwind classes `bg-bg-primary` and `border-accent` do NOT exist in Tee-Mo's `app.css`. Use `bg-slate-50` for the page background and `border-brand-500` for the spinner ring.
  - Redirect uses `navigate({ to: '/login', search: { redirect: location.pathname }, replace: true })` — preserve the current path so we can bounce back after login in a later story (this story does not consume the `redirect` param, but the login page is future-proof for it — document this in a JSDoc comment).
- **R4 — Create `frontend/src/components/auth/SignOutButton.tsx`**:
  - Renders a ghost-variant `Button` labeled "Sign out".
  - On click: call `useAuth.getState().logout()`, then `navigate({ to: '/login', replace: true })`.
- **R5 — Create `frontend/src/routes/app.tsx`** — the post-login placeholder:
  - Wraps all content in `<ProtectedRoute>`.
  - Renders a centered `Card` containing:
    - Heading: "Welcome to Tee-Mo" (`text-3xl font-semibold tracking-tight`).
    - Body: "Signed in as **{user.email}**."
    - A `SignOutButton` below the greeting.
  - **This route is a temporary landing page.** EPIC-003 will replace its body with the workspace list. Leave a comment at the top of `app.tsx` documenting this: `// EPIC-003 will replace the body of this route with <WorkspaceList />. Keep the route path "/app" stable.`
- **R6 — Landing page update (`frontend/src/routes/index.tsx`)**:
  - The S-01 landing page has a disabled "Continue to login" button. **Enable it** by wrapping it in a TanStack `Link to="/login"`. Keep the rest of the page (health badge, heading, subtitle) unchanged.
- **R7 — TanStack Router route registration**:
  - TanStack Router's Vite plugin auto-generates `routeTree.gen.ts` when files are added to `src/routes/`. **Do not hand-edit `routeTree.gen.ts`**.
  - After creating `login.tsx`, `register.tsx`, and `app.tsx`, run the dev server once — the plugin regenerates the tree. If the plugin is not configured, `npm run build` does the same.
- **R8 — Styling**:
  - Use ONLY the existing design-system primitives (`Button`, `Card`, `Badge`) + Tailwind 4 built-in utilities. No new dependencies.
  - Use Tee-Mo tokens: `bg-brand-500`, `text-slate-900`, `bg-slate-50`, `border-slate-300`, `focus:ring-brand-500`.
  - Form inputs: standard HTML `<input>` styled with Tailwind utilities (no new input primitive in this story — EPIC-003 may introduce one). Target shape:
    ```tsx
    <input
      className="w-full h-10 px-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
    />
    ```
- **R9 — Self-documenting code**: every exported component, every local helper, every TypeScript type MUST have a JSDoc comment.
- **R10 — No direct `fetch` calls** anywhere in this story. All auth actions go through the Zustand store from STORY-002-03, which goes through `lib/api.ts` (FLASHCARDS.md TanStack Query rule).

### 1.3 Out of Scope
- Redirect-after-login (the `?redirect=` query param is preserved by ProtectedRoute but NOT consumed by the login page in this story — deferred to EPIC-003).
- Password strength meter.
- "Forgot password" flow — not in EPIC-002.
- Email verification UX — none in Tee-Mo.
- Workspace list / creation UI — EPIC-003.
- Form libraries (React Hook Form, Formik) — overkill for two two-field forms; use native form state with `useState`.
- Toast notifications — defer to EPIC-009 (Error Handling & UX Polish).
- E2E browser tests (Playwright/Cypress) — verified manually in §2.2 for this sprint; automated E2E deferred to a later story.

### TDD Red Phase: No
Rationale: This is primarily UI + router wiring. The critical logic (state transitions, auth actions) is already covered by unit tests in STORY-002-03. A full E2E Playwright setup is out of scope (§1.3). The manual verification checklist in §2.2 is the gate.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Login, register, and protected dashboard placeholder

  Scenario: Register happy path
    Given I am on /register
    And no user with email "alice@example.com" exists
    When I fill in email "alice@example.com" and password "correcthorse"
    And I click "Create account"
    Then the POST /api/auth/register call succeeds
    And I am redirected to /app
    And the page shows "Signed in as alice@example.com"

  Scenario: Register with too-long password (client-side)
    Given I am on /register
    When I fill in a password whose UTF-8 byte length is 73
    And I click "Create account"
    Then an inline error reads "Password is too long (max 72 bytes)"
    And NO network call is made

  Scenario: Register with backend 409
    Given a user "alice@example.com" already exists
    When I fill in the same email on /register and click "Create account"
    Then the inline error reads "Email already registered"
    And I remain on /register

  Scenario: Login happy path
    Given I am on /login
    And a user "alice@example.com" with password "correcthorse" exists
    When I fill the form and click "Sign in"
    Then I am redirected to /app
    And the page shows "Signed in as alice@example.com"

  Scenario: Login with wrong password
    Given a user "alice@example.com" exists
    When I POST the login form with a wrong password
    Then the inline error reads "Invalid credentials"
    And I remain on /login

  Scenario: Visiting /app while logged out
    Given I have no session cookie
    When I navigate to /app
    Then the page shows a brief spinner (status 'unknown')
    And within ~1 second I am redirected to /login

  Scenario: Visiting /app while logged in
    Given I am logged in as "alice@example.com"
    When I navigate to /app
    Then I see the welcome card with my email

  Scenario: Hard refresh on /app preserves session
    Given I am logged in and viewing /app
    When I hard-refresh the browser tab
    Then after AuthInitializer runs I am still on /app
    And the welcome card still shows my email

  Scenario: Sign out from /app
    Given I am on /app
    When I click "Sign out"
    Then the cookies are cleared (verifiable in DevTools)
    And I am redirected to /login
    And navigating back to /app re-redirects me to /login

  Scenario: Landing page CTA
    Given I open /
    When I click "Continue to login"
    Then I am taken to /login

  Scenario: No Google OAuth leakage
    Given I inspect the full UI surface of /login, /register, /app
    Then no element contains the word "Google"
    And no element renders a Google logo
```

### 2.2 Verification Steps (Manual)

Run the backend (`uvicorn app.main:app --reload`) and frontend (`npm run dev`) simultaneously. Open `http://localhost:5173/` in a fresh browser (or Incognito, to clear cookies).

- [ ] **Landing CTA**: `/` → click "Continue to login" → lands on `/login`.
- [ ] **Register happy path**: `/register` → fill `test+{timestamp}@teemo.test` + `correcthorse` → click "Create account" → lands on `/app` showing the email. DevTools → Application → Cookies shows `access_token` and `refresh_token` set.
- [ ] **Client-side length guard**: `/register` → enter a 73-byte password → inline error, DevTools → Network shows zero `/api/auth/register` requests.
- [ ] **Login happy path**: open a fresh Incognito tab → `/login` → fill the same credentials → click "Sign in" → lands on `/app`.
- [ ] **Wrong password**: `/login` → wrong password → inline error "Invalid credentials".
- [ ] **Protected route**: in a fresh Incognito, navigate directly to `/app` → brief spinner, then bounced to `/login`.
- [ ] **Hard refresh**: on `/app`, press Cmd-R → page reloads, spinner briefly, then `/app` re-renders with the email (AuthInitializer fired `fetchMe`).
- [ ] **Sign out**: click "Sign out" on `/app` → redirects to `/login` → cookies gone in DevTools → navigate to `/app` → re-redirects to `/login`.
- [ ] **No Google leak**: search the rendered DOM (Cmd-F in DevTools) for "google" on `/login`, `/register`, `/app` — zero matches.
- [ ] **TypeScript**: `cd frontend && npm run build` completes with zero errors.
- [ ] **Existing tests still pass**: `cd frontend && npm test` → STORY-002-03 suite still green.
- [ ] **Backend health unaffected**: `curl http://localhost:8000/api/health` still returns `status: ok` with all 4 tables.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-002-02** | Backend auth routes reachable at `http://localhost:8000/api/auth/*` | [ ] |
| **STORY-002-03** | `frontend/src/stores/authStore.ts` exists and Vitest suite is green | [ ] |
| **Node / npm** | Same as prior sprint | [x] |
| **TanStack Router** | Vite plugin already configured in S-01 to auto-generate `routeTree.gen.ts` | [x] |
| **Design System** | `components/ui/{Button,Card,Badge}.tsx` exist from S-01 | [x] |
| **Env Vars** | `VITE_API_URL` set (defaults to `http://localhost:8000`) | [x] |

### 3.1 Test Implementation

No automated tests in this story (see §1.3 TDD Red Phase: No). The manual verification checklist in §2.2 is the gate, backed by the existing unit tests in STORY-002-03. If a future story wants to add Playwright, the routes are structured to support it (stable paths, accessible form labels).

### 3.2 Context & Files

| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/login.tsx` (new) |
| **Related Files** | `frontend/src/routes/register.tsx` (new), `frontend/src/routes/app.tsx` (new), `frontend/src/routes/index.tsx` (edit — enable CTA link), `frontend/src/components/auth/ProtectedRoute.tsx` (new), `frontend/src/components/auth/SignOutButton.tsx` (new) |
| **New Files Needed** | Yes — 5 new files, 1 edit |
| **ADR References** | ADR-001 (cookie auth), ADR-014 (Zustand), ADR-022 (Design System: primitives + Tailwind 4 tokens only) |
| **First-Use Pattern** | Yes — this is Tee-Mo's first `<Link>` navigation, first `useNavigate` call, first ProtectedRoute, first form submit. Reference: `/Users/ssuladze/Documents/Dev/new_app/frontend/src/routes/login.tsx` (strip the Google button, the providers query, and the SetupGate). If anything surprises you about TanStack Router file-based routes during implementation, record it in FLASHCARDS.md after merge. |

### 3.3 Technical Logic

**Step 1 — `frontend/src/components/auth/ProtectedRoute.tsx`:**

```tsx
/**
 * ProtectedRoute — guards a route behind the Zustand auth store.
 *
 * Behavior:
 *   - status === 'unknown' → centered spinner (AuthInitializer hasn't resolved yet).
 *   - status === 'anon'    → redirect to /login preserving the current path in ?redirect.
 *   - status === 'authed'  → render children.
 *
 * The ?redirect search param is populated for future stories (EPIC-003) to
 * consume. This story's /login does not read it yet.
 */
import { useEffect } from 'react';
import { useLocation, useNavigate } from '@tanstack/react-router';

import { useAuth } from '../../stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const status = useAuth((s) => s.status);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (status === 'anon') {
      navigate({
        to: '/login',
        search: { redirect: location.pathname },
        replace: true,
      });
    }
  }, [status, navigate, location.pathname]);

  if (status !== 'authed') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div
          role="status"
          aria-label="Checking authentication"
          className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent"
        />
      </div>
    );
  }

  return <>{children}</>;
}
```

**Step 2 — `frontend/src/components/auth/SignOutButton.tsx`:**

```tsx
/**
 * SignOutButton — calls useAuth.logout() then redirects to /login.
 * Ghost-variant button; safe to drop into any authenticated layout.
 */
import { useNavigate } from '@tanstack/react-router';

import { Button } from '../ui/Button';
import { useAuth } from '../../stores/authStore';

export function SignOutButton() {
  const navigate = useNavigate();

  const handleClick = async () => {
    await useAuth.getState().logout();
    navigate({ to: '/login', replace: true });
  };

  return (
    <Button variant="ghost" onClick={handleClick}>
      Sign out
    </Button>
  );
}
```

**Step 3 — `frontend/src/routes/login.tsx`:**

```tsx
/**
 * /login — email + password sign-in.
 *
 * Uses the Zustand auth store's login() action. Redirects to /app on success.
 * Shows backend detail as an inline error on failure.
 */
import { useEffect, useState } from 'react';
import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';

import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { useAuth } from '../stores/authStore';

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const status = useAuth((s) => s.status);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Already logged in — bounce to /app.
  useEffect(() => {
    if (status === 'authed') {
      navigate({ to: '/app', replace: true });
    }
  }, [status, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await useAuth.getState().login(email, password);
      navigate({ to: '/app', replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md p-8">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Sign in to Tee-Mo
        </h1>
        <p className="mt-1 text-sm text-slate-600">Your BYOK Slack assistant.</p>

        <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full h-10 px-3 rounded-md border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500"
            />
          </label>

          {error && (
            <div
              role="alert"
              className="rounded-md bg-rose-50 border border-rose-200 px-3 py-2 text-sm text-rose-800"
            >
              {error}
            </div>
          )}

          <Button type="submit" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-600">
          No account?{' '}
          <Link to="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Create one
          </Link>
        </p>
      </Card>
    </div>
  );
}
```

**Step 4 — `frontend/src/routes/register.tsx`:**

Structurally identical to `login.tsx`. Differences:
- `Route` path: `'/register'`.
- Heading: "Create your Tee-Mo account".
- Password helper text: "Up to 72 characters."
- `autoComplete="new-password"` on password input.
- Submit label: "Create account" / "Creating…".
- Client-side validation **before** calling `register()`:

```ts
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  setError(null);

  if (!password) {
    setError('Password is required');
    return;
  }
  const byteLength = new TextEncoder().encode(password).length;
  if (byteLength > 72) {
    setError('Password is too long (max 72 bytes)');
    return;
  }

  setSubmitting(true);
  try {
    await useAuth.getState().register(email, password);
    navigate({ to: '/app', replace: true });
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Registration failed');
  } finally {
    setSubmitting(false);
  }
};
```

- Footer link: "Already have an account? Sign in" → `/login`.

**Step 5 — `frontend/src/routes/app.tsx`:**

```tsx
// EPIC-003 will replace the body of this route with <WorkspaceList />.
// Keep the route path "/app" stable so the router does not need refactoring.

/**
 * /app — post-login placeholder (EPIC-002).
 *
 * Wraps content in <ProtectedRoute>, shows the signed-in email, and renders
 * a SignOutButton. EPIC-003 replaces the body with the real workspace list.
 */
import { createFileRoute } from '@tanstack/react-router';

import { Card } from '../components/ui/Card';
import { ProtectedRoute } from '../components/auth/ProtectedRoute';
import { SignOutButton } from '../components/auth/SignOutButton';
import { useAuth } from '../stores/authStore';

export const Route = createFileRoute('/app')({
  component: AppPage,
});

function AppPage() {
  return (
    <ProtectedRoute>
      <AppContent />
    </ProtectedRoute>
  );
}

function AppContent() {
  const user = useAuth((s) => s.user);
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md p-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Welcome to Tee-Mo
        </h1>
        <p className="mt-2 text-slate-600">
          Signed in as <span className="font-medium text-slate-900">{user?.email}</span>.
        </p>
        <div className="mt-6 flex justify-center">
          <SignOutButton />
        </div>
      </Card>
    </div>
  );
}
```

**Step 6 — Edit `frontend/src/routes/index.tsx`:**

Find the disabled "Continue to login" button and wrap it in a TanStack `<Link to="/login">` so it navigates. Remove the `disabled` prop. Do not touch any other part of the landing page. Keep the S-01 health-badge + welcome copy exactly as-is.

### 3.4 API Contract

This story consumes the API contracts defined in STORY-002-02 §3.4 via the wrappers from STORY-002-03. No new endpoints.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — store logic already covered in STORY-002-03 | |
| Component tests | 0 — skipped this sprint per §1.3 | |
| E2E / acceptance tests | 0 — manual verification only (§2.2) | |
| Integration tests | 0 — N/A | |

### 4.2 Definition of Done
- [ ] All 11 manual verification steps in §2.2 pass.
- [ ] `npm run build` in `frontend/` completes with zero TypeScript errors.
- [ ] `npm test` in `frontend/` — the STORY-002-03 suite is still green.
- [ ] `routeTree.gen.ts` has been auto-updated to include `/login`, `/register`, `/app`.
- [ ] Zero occurrences of the string "google" (case-insensitive) in any of the new or edited files.
- [ ] Zero direct `fetch(` calls in any new file — all network I/O flows through `stores/authStore` → `lib/api`.
- [ ] FLASHCARDS.md TanStack Query rule respected.
- [ ] ADR-022 respected — only design-system primitives and built-in Tailwind 4 tokens used.
- [ ] Sign-out verified to clear cookies (DevTools → Application → Cookies → empty for `localhost:8000`).

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
