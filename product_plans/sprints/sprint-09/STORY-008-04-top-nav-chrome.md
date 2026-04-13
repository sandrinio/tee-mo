---
story_id: "STORY-008-04-top-nav-chrome"
parent_epic_ref: "EPIC-008"
status: "Refinement"
ambiguity: "🟢 Low"
context_source: "Epic §2, §4.1 / Design Guide §9.2 / Codebase"
actor: "All Users"
complexity_label: "L2"
---

# STORY-008-04: Top Nav, Layout Chrome & Toast Infrastructure

**Complexity: L2** — 2-3 files, known pattern, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
As a **user on any dashboard page**,
I want to **see a persistent top navigation bar with the Tee-Mo logo and my account controls**,
So that **I always know where I am, can navigate back to my workspaces, and can log out**.

### 1.2 Detailed Requirements

**Top nav bar (`AppNav` component):**
- **R1**: Build `frontend/src/components/layout/AppNav.tsx` — a persistent top nav rendered from the app layout route (`app.tsx`), visible on all `/app/*` pages.
- **R2**: Layout per design guide §9.2 mockup:
  - Left: "Tee-Mo" text logo (`text-lg font-semibold text-brand-500`)
  - Center: Page context — "Workspaces" as a link to `/app`
  - Right: User email (from `getMe()` or auth context) + "Log out" button (`Button variant="ghost"`)
- **R3**: Nav bar styling: `bg-white border-b border-slate-200 px-6 h-14 flex items-center justify-between`. Sticky: `sticky top-0 z-10`.
- **R4**: Logout button calls `logoutUser()` from `api.ts` and navigates to `/login`.

**Toast infrastructure:**
- **R5**: Install `sonner` (`npm install sonner`).
- **R6**: Mount `<Toaster />` from `sonner` in the root layout (`__root.tsx`). Config: `position="bottom-right"`, `richColors`, `duration={4000}` per design guide §6.5.
- **R7**: Replace the `FlashBanner` component in `app.index.tsx` with `sonner` toasts. On page load, if `slack_install` or `drive_connect` search param is present, fire the appropriate `toast.success()` or `toast.error()` and strip the param from the URL. Remove the `FlashBanner` component entirely.
- **R8**: Use `toast.success` / `toast.error` for mutation feedback where currently using inline `<p>` error messages — specifically in `CreateWorkspaceModal` and `RenameWorkspaceModal` (replace `{mutation.error && <p>...}` pattern).

**Design token cleanup (`app.index.tsx`):**
- **R9**: Replace the 1 hardcoded `bg-brand-600` ad-hoc button in the empty state with `<Button variant="primary">` component. (Note: `app.index.tsx` already uses `brand-*` tokens correctly — only the Button component import is missing.)
- **R10**: Update empty state on teams page to use dashed border pattern per design guide §6.7.

### 1.3 Out of Scope
- Workspace card changes (STORY-008-03)
- Guided setup mode (STORY-008-01)
- Channel binding UI (STORY-008-02)
- User avatar / profile page (not in scope for v1)

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Top Nav & Layout Chrome

  Scenario: Top nav renders on all /app pages
    Given a logged-in user on /app
    When the page renders
    Then a top nav bar is visible with "Tee-Mo" logo, "Workspaces" link, user email, and "Log out" button

  Scenario: Top nav persists across navigation
    Given a user on /app who clicks into a team detail page
    When /app/teams/$teamId renders
    Then the same top nav bar is visible

  Scenario: Logout navigates to login
    Given a user on /app
    When they click "Log out"
    Then logoutUser() is called
    And the browser navigates to /login

  Scenario: Slack OAuth toast replaces FlashBanner
    Given a redirect to /app?slack_install=ok
    When the page loads
    Then a success toast appears: "Slack workspace installed successfully"
    And the ?slack_install param is stripped from the URL
    And no FlashBanner component is rendered

  Scenario: Drive OAuth toast
    Given a redirect to /app?drive_connect=ok
    When the page loads
    Then a success toast appears: "Google Drive connected"
    And the param is stripped

  Scenario: Error toast on OAuth failure
    Given a redirect to /app?slack_install=error
    When the page loads
    Then an error toast appears with the appropriate message

  Scenario: Modal errors use toasts
    Given a user submitting the Create Workspace modal
    When the creation fails (e.g., duplicate name)
    Then a toast.error appears with the error message
    And no inline <p> error is rendered
```

### 2.2 Verification Steps (Manual)
- [ ] `npm run build` succeeds
- [ ] `npx vitest run` — all tests pass
- [ ] Top nav visible on `/app`, `/app/teams/$teamId`, `/app/teams/$teamId/$workspaceId`
- [ ] Logout works and redirects to `/login`
- [ ] Navigating to `/app?slack_install=ok` shows a toast (not FlashBanner)
- [ ] Creating a workspace with an error shows a toast
- [ ] Toasts auto-dismiss after 4 seconds

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Dependencies** | `npm install sonner` | [ ] |
| **Dev Server** | `npm run dev` in `frontend/` | [ ] |

### 3.1 Test Implementation
- Create `frontend/src/components/layout/__tests__/AppNav.test.tsx` — render test (logo, email, logout button), logout click handler
- Update `app.index.tsx` tests — verify toast fires on search param, verify FlashBanner removed
- Update modal tests — verify toast on error instead of inline error

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/components/layout/AppNav.tsx` (new) |
| **Related Files** | `frontend/src/routes/app.tsx` (modify — render AppNav + Outlet), `frontend/src/routes/__root.tsx` (modify — mount Toaster), `frontend/src/routes/app.index.tsx` (modify — remove FlashBanner, add toast logic), `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` (modify — toast errors), `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` (modify — toast errors) |
| **New Files Needed** | Yes — `AppNav.tsx` |
| **ADR References** | ADR-022 (design system) |
| **First-Use Pattern** | Yes — `sonner` toast library (first use in this codebase) |

### 3.3 Technical Logic

**AppNav component:**
```tsx
// frontend/src/components/layout/AppNav.tsx
import { Link, useNavigate } from '@tanstack/react-router';
import { Button } from '../ui/Button';
import { logoutUser } from '../../lib/api';

export function AppNav({ userEmail }: { userEmail: string }) {
  const navigate = useNavigate();

  async function handleLogout() {
    await logoutUser();
    navigate({ to: '/login' });
  }

  return (
    <nav className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 h-14 flex items-center justify-between">
      <Link to="/app" className="text-lg font-semibold text-brand-500">Tee-Mo</Link>
      <Link to="/app" className="text-sm font-medium text-slate-600 hover:text-slate-900">Workspaces</Link>
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-500">{userEmail}</span>
        <Button variant="ghost" size="sm" onClick={handleLogout}>Log out</Button>
      </div>
    </nav>
  );
}
```

**App layout integration (`app.tsx`):**
```tsx
// Current: just <ProtectedRoute><Outlet /></ProtectedRoute>
// Change to:
<ProtectedRoute>
  <AppNav userEmail={user.email} />
  <main className="px-6 lg:px-8 py-8 lg:py-12 max-w-7xl mx-auto">
    <Outlet />
  </main>
</ProtectedRoute>
```
Note: The user email needs to come from the auth context. Check how `ProtectedRoute` currently fetches the user — likely via `getMe()` or a Zustand store. Pass the email down as a prop or use the same context.

**Sonner setup (`__root.tsx`):**
```tsx
import { Toaster } from 'sonner';

// In the root component:
<div className="min-h-screen bg-slate-50">
  <Outlet />
  <Toaster position="bottom-right" richColors duration={4000} />
</div>
```

**Flash banner → toast migration (`app.index.tsx`):**
```tsx
// Remove FlashBanner component entirely
// In AppContent, use useEffect:
import { toast } from 'sonner';

useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const slackStatus = params.get('slack_install');
  const driveStatus = params.get('drive_connect');

  if (slackStatus === 'ok') toast.success('Slack workspace installed successfully');
  else if (slackStatus === 'cancelled') toast.error('Slack installation was cancelled');
  else if (slackStatus === 'error') toast.error('Slack installation failed');
  // ... etc for other statuses

  if (driveStatus === 'ok') toast.success('Google Drive connected');
  // ... etc

  // Strip params from URL
  if (slackStatus || driveStatus) {
    const url = new URL(window.location.href);
    url.searchParams.delete('slack_install');
    url.searchParams.delete('drive_connect');
    window.history.replaceState({}, '', url.toString());
  }
}, []);
```

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Component tests | 4 | AppNav render, AppNav logout, toast on OAuth param, modal toast on error |
| Unit tests | 0 | N/A |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] Minimum test expectations met.
- [ ] FLASHCARDS.md consulted (jsdom limitation, vitest globals, TanStack Router layout routes).
- [ ] No ADR violations.
- [ ] `sonner` installed and `<Toaster>` mounted.
- [ ] FlashBanner component fully removed.
- [ ] `npm run build` passes.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| QA | 26 | 928 | 954 |
