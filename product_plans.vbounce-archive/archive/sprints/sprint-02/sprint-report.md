---
sprint_id: "S-02"
sprint_goal: "End-to-end email + password auth: register, login, refresh, logout, /me; frontend ProtectedRoute gating /app placeholder; auto-login on register; ready for EPIC-003."
dates: "2026-04-11"
status: "Achieved"
total_tokens_used: "N/A (not instrumented)"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
tag: "v0.2.0-auth"
---

# Sprint Report: S-02

## 1. What Was Delivered

### User-Facing (Accessible Now)

- `/login` page — email + password login with error handling
- `/register` page — registration with auto-login on success
- `/app` placeholder behind `ProtectedRoute` — authenticated users reach it; unauthenticated users redirected to `/login`
- `SignOutButton` clears cookies and redirects

### Internal / Backend (Not Directly Visible)

- `backend/app/core/security.py` — bcrypt hash/verify, JWT sign/verify/refresh, 72-byte password validation (ADR-017)
- 5 auth routes: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me` — all using httpOnly cookies with `samesite="lax"` (deliberate deviation from new_app for EPIC-005/006 OAuth redirect compatibility)
- `get_current_user_id` FastAPI dependency
- Zustand `useAuth` store + 5 typed `lib/api.ts` wrappers + `AuthInitializer` component

### Not Completed

None. All 4 stories delivered.

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| STORY-002-01: Security primitives | EPIC-002 | L1 | Done | 0 | 0 | 0% | — |
| STORY-002-02: Auth routes | EPIC-002 | L2 | Done | 0 | 0 | 5% | Enhancement |
| STORY-002-03: Auth store | EPIC-002 | L2 | Done | 0 | 0 | 5% | Enhancement |
| STORY-002-04: Login/register pages | EPIC-002 | L2 | Done | 0 | 0 | 0% | — |

### Story Highlights

- **STORY-002-02**: `LaxEmailStr` workaround required for `email-validator` 2.x `.test` TLD rejection in integration tests. 13 live Supabase integration tests green. Flashcard recorded.
- **STORY-002-03**: Vitest 2.x `vi.mock` hoisting TDZ — `vi.hoisted()` pattern discovered and applied. First Vitest setup in Tee-Mo (`vitest@^2.1.9`). Flashcard recorded.
- **STORY-002-01**: `validate_password_length` guard (ADR-017) applied at register boundary; bcrypt 5.0 ValueError risk closed.

### Escalated Stories

None.

### 2.1 Change Requests

None.

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value |
|--------|-------|
| Stories Planned | 4 |
| Stories Delivered | 4 |
| Stories Escalated | 0 |
| Total QA Bounces | 0 |
| Total Architect Bounces | 0 |
| Average Correction Tax | ~2.5% |
| Bug Fix Tax | 0% |
| Enhancement Tax | ~2.5% |
| First-Pass Success Rate | 100% |
| Total Tests Written | ~32 (9 backend unit + 13 live integration + 10 frontend Vitest) |

---

## 4. Lessons Learned

| Source | Lesson | Recorded? | When |
|--------|--------|-----------|------|
| STORY-002-02 | samesite="lax" deliberate deviation from new_app for OAuth redirect compatibility | Yes | Sprint close |
| STORY-002-02 | LaxEmailStr for email-validator 2.x .test TLD rejection | Yes | Sprint close |
| STORY-002-03 | Vitest 2.x vi.mock hoisting TDZ — use vi.hoisted() | Yes | Sprint close |
| STORY-002-04 | tsc -b && vite build chicken-and-egg on new routes | Yes | Sprint close |

---

## 5. Retrospective

### What Went Well

- 0 QA/Arch bounces across all 4 stories. 2.5% correction tax all Enhancement.
- Architect integration audit verdict: **SHIP** (zero findings).
- 22 backend + 10 frontend tests — first frontend Vitest infrastructure in Tee-Mo.
- `samesite="lax"` decision made proactively for EPIC-005/006 compatibility — no rework needed later.

### What Didn't Go Well

- Browser walkthrough (11 steps §2.2) deferred by user — not human-verified this sprint. Carried forward as assumption.
- BUG-20260411 (PyJWT module-level options leak) discovered and filed for S-03 backlog. Production unaffected.

### Framework Self-Assessment

#### Process Flow

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| Browser walkthrough deferred — no human verification gate in Fast Track process | Team Lead | Friction | Add optional manual verification step to Fast Track stories touching auth flows |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-15 | Sprint Report generated retroactively at S-11 close audit | Team Lead |
