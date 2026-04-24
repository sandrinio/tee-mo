---
sprint_id: "SPRINT-02"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-02.md"
---

# SPRINT-02 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-02.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: End-to-end email + password auth — register, login, refresh, logout, /me; frontend ProtectedRoute gating a /app placeholder; auto-login on register; ready for EPIC-003 to replace the body of /app with the real workspace dashboard.

## §1 What Was Delivered

**User-facing:**
- Landing CTA now routes to `/login` (previously disabled).
- `/login` and `/register` routes — email+password forms with inline error alerts, authed-redirect guard, 73-byte client-side password guard on register.
- `/app` placeholder — gated by `ProtectedRoute` (tri-state: unknown → spinner, anon → `/login?redirect=<path>`, authed → children), shows `user?.email` plus `SignOutButton`.
- Auto-login on register; hard-refresh rehydrates auth via `AuthInitializer` → `GET /api/auth/me`.

**Internal / infrastructure:**
- Backend `app/core/security.py` (153 lines): `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token`, `validate_password_length` (bcrypt 72-byte guard per ADR-017).
- 5 auth routes: `POST /api/auth/{register,login,refresh,logout}` + `GET /api/auth/me`. httpOnly cookies, `samesite="lax"` (deliberate deviation from new_app Strict — recorded in FLASHCARDS.md), refresh_token path-scoped to `/api/auth`, anti-enumeration 401s.
- `app/api/deps.py`: `get_current_user_id` (cookie-first, Bearer fallback). Dropped `get_current_user`/`get_current_admin_user` from new_app.
- Frontend Zustand `useAuth` store with tri-state `status`; `lib/api.ts` extended with `apiPost`, 5 typed wrappers; first Vitest setup in Tee-Mo (vitest@^2.1.9).
- Scaffold patches mid-sprint: `src/vite-env.d.ts` added, `tsconfig.node.json` gained `skipLibCheck: true`.

**Carried over (if any):**
- BUG-20260411-001 (PyJWT module-level options leak, test-ordering flake) — filed for next sprint.
- 11-step manual browser walkthrough NOT executed — user skipped the checks and closed sprint directly. Visual/navigation flows unverified despite all automated gates green.

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-002-01 | Backend Security Primitives + bcrypt Guard | Done | 0 | 0 | 0% | L1, Fast Track. First-try green. 9 unit tests. Strip audit clean. |
| STORY-002-02 | Auth Routes + Cookies + get_current_user_id | Done | 0 | 0 | 5% | L2, Fast Track. `LaxEmailStr` workaround for email-validator 2.x `.test` TLD rejection. `.env DEBUG=true` added mid-sprint. 13 integration tests (live Supabase). |
| STORY-002-03 | Frontend Auth Store + API Client + AuthInitializer | Done | 0 | 0 | 5% | L2, Fast Track. Lazy dynamic import for `queryClient` (Vitest 2.x `vi.mock` TDZ workaround). 10 Vitest unit tests. Patched S-01 scaffold gaps. |
| STORY-002-04 | Login + Register Pages + ProtectedRoute + /app Placeholder | Done | 0 | 0 | 0% | L2, Fast Track (single-pass). 5 new components + `routeTree.gen.ts` regen. 11 manual DoD items deferred/unverified. |

**Change Requests / User Requests during sprint:**
- No mid-sprint scope changes.
- User explicitly deferred flashcard approval to sprint close (batch review instead of per-story).
- User skipped manual browser walkthrough and closed sprint directly.

## §3 Execution Metrics

- **Stories planned → shipped:** 4/4
- **First-pass success rate:** 100% (Fast Track throughout; zero QA or Architect bounces)
- **Bug-Fix Tax:** 0 bugs fixed in-sprint (1 BUG filed for next sprint: BUG-20260411-001 PyJWT test-ordering)
- **Enhancement Tax:** 2 mid-sprint scaffold patches (vite-env.d.ts, tsconfig.node.json) absorbed during STORY-002-03
- **Total tokens used:** 660,693 (aggregated from 11 task-notification totals — Dev Red/Green/DevOps × 4 stories + Architect integration audit)
- **Aggregate correction tax:** ~2.5%
- **Backend tests:** 22 (9 security + 13 auth_routes integration). **Frontend tests:** 10 (authStore Vitest).
- **Integration audit verdict:** SHIP (zero findings).

## §4 Lessons

Top themes from flashcards recorded during this sprint:
- **#auth-cookies:** Auth cookies use `samesite="lax"`, NOT `strict` — deliberate deviation from new_app so EPIC-005/006 OAuth redirects don't drop the session cookie. _(Recorded mid-sprint.)_
- **#pydantic-email:** Pydantic `EmailStr` rejects `.test` TLD via `email-validator` 2.x `globally_deliverable` — use `LaxEmailStr` or `@example.com` fixture emails. _(Recorded mid-sprint.)_
- **#vitest-tdz:** Vitest 2.x `vi.mock` hoisting TDZ — use `vi.hoisted(...)` for mock vars, OR lazy dynamic import when test is immutable. _(Candidate, pending approval.)_
- **#tanstack-router-build:** TanStack Router + `tsc -b && vite build` chicken-and-egg — first build after adding a new route requires standalone `vite build` first to regenerate `routeTree.gen.ts`. _(Candidate, pending approval.)_

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals:**
  - PyJWT module-level options leak surfaced only in DevOps post-merge gate (not Dev Green runs) because individual Dev tests ran suites separately — test-harness hygiene issue, not production.
  - Worktree setup undernourished: `.env` and `sprint-context-S-XX.md` symlinks required manual Team Lead intervention.
  - Task prompts drifted from story specs (some task files re-described §3.3 code blocks, risking drift).
  - Token accounting inconsistent: Dev-report YAML fields are placeholder values in 3 of 4 stories — task-notification totals used as authoritative.
  - `tsc -b && vite build` ordering fights TanStack Router Vite plugin on new routes.
- **Framework issues filed:** 4 improvement candidates queued for V-Bounce `/improve`:
  1. Automate worktree setup (`.env` + `sprint-context-S-XX.md` symlinks via `run_script.sh`)
  2. Reorder frontend build script to `vite build && tsc --noEmit` OR add `pretsr` step
  3. Wire real token counting into agent reports OR remove placeholder fields
  4. Add deterministic full-suite test gate to post-merge validation
- **Hook failures:** N/A (V-Bounce had no hooks)

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- EPIC-003 Workspace Dashboard will replace `/app` placeholder body (top-of-file comment already reserves path).
- File BUG-20260411-001 (PyJWT scoped `jwt.PyJWT()` instance fix) as next-sprint backlog item.
- Candidate release tag `v0.2.0-auth` (foundation was S-01; auth adds S-02; not yet demoable end-to-end without EPIC-003 workspace UI).
- Run 11 manual browser walkthrough checks before any customer/stakeholder demo (~3 minutes in Incognito).
- Vdoc init deferred until after EPIC-003 ships a non-trivial frontend surface to document.
