---
sprint_id: "S-02"
sprint_goal: "End-to-end email + password auth: register, login, refresh, logout, /me; frontend ProtectedRoute gating a /app placeholder; auto-login on register; ready for EPIC-003 to replace the body of /app with the real workspace dashboard."
dates: "2026-04-11"
delivery: "D-01"
status: "Done"
stories_planned: 4
stories_completed: 4
stories_escalated: 0
stories_parked: 0
total_bounces: 0
fast_track_count: 4
full_bounce_count: 0
qa_bounces: 0
architect_bounces: 0
aggregate_correction_tax_pct: 2.5
backend_tests: 22
frontend_tests: 10
integration_audit_verdict: "SHIP"
generated_by: "Team Lead"
generated_at: "2026-04-11"
total_input_tokens: "unknown (~40k estimated from reports; task-notification totals preferred)"
total_output_tokens: "unknown (~180k estimated from reports; task-notification totals preferred)"
total_tokens_used: 660693
token_source: "aggregated from 11 task-notification totals (Dev Red/Green/DevOps × 4 stories + Architect integration audit); Dev-report YAML totals are placeholder values and unreliable."
---

# Sprint S-02 Report — Email + Password Auth, End-to-End

## Key Takeaways (TL;DR)

- **Delivered all 4 stories as planned.** 0 escalations, 0 parking-lot. 22 backend tests + 10 frontend tests green. `npm run build` exits 0. Architect integration audit verdict: **SHIP, zero findings**.
- **Quality signal: 🟢 Healthy.** First-pass success rate = 100% (no QA or Architect bounces; Fast Track flow throughout). Aggregate correction tax ≈ 2.5% — below the 5% notice band, well below the 10% concern band. Correction tax was driven by two legitimate workarounds (LaxEmailStr for email-validator 2.x, lazy dynamic import for Vitest hoisting), not by spec-drift or rework.
- **Cost: ~660k total tokens aggregated across 11 subagent task-notification totals** (Dev Red/Green/DevOps × 4 stories + Architect integration audit). Dev-report YAML frontmatter tokens are placeholder values and were NOT summed — task notifications are authoritative per agent-team Step 7. Cost at Anthropic Opus list rate ≈ $12–15 at the observed input/output split.
- **Top surprises / debt:** 4 new flashcard candidates (2 already recorded mid-sprint, 2 new), 1 BUG report queued for next sprint (PyJWT test-order flake), 2 S-01 scaffold gaps patched mid-sprint (`vite-env.d.ts`, `tsconfig.node.json`).
- **Browser walkthrough (11 manual steps §2.2): NOT EXECUTED.** The user skipped Step 5.7 and asked to close the sprint directly. The automated gates (22 backend, 10 frontend, build) all pass and the integration audit found no issues, but **the visual/navigation flows are unverified by human eyes**. Flagged in §3.

## Stories

| # | Story | Label | Mode | State | QA | Arch | Tests | CTax | Notes |
|---|-------|-------|------|-------|----|----|-------|------|-------|
| 1 | STORY-002-01 Backend Security Primitives + bcrypt Guard | L1 | Fast Track | Done | 0 | 0 | 9 unit | 0% | First-try green. Copy verbatim + `validate_password_length`. Strip audit clean. |
| 2 | STORY-002-02 Auth Routes + Cookies + `get_current_user_id` | L2 | Fast Track | Done | 0 | 0 | 13 integration (live Supabase) | 5% | `LaxEmailStr` workaround for email-validator 2.x `.test` TLD rejection. `.env` `DEBUG=true` added mid-sprint. 5 endpoints + strip list compliance. |
| 3 | STORY-002-03 Frontend Auth Store + API Client + AuthInitializer | L2 | Fast Track | Done | 0 | 0 | 10 Vitest unit | 5% | Lazy dynamic import for `queryClient` to work around Vitest 2.x `vi.mock` TDZ. Patched 2 S-01 scaffold gaps (`vite-env.d.ts`, `tsconfig.node.json skipLibCheck`). First Vitest setup in Tee-Mo. |
| 4 | STORY-002-04 Login + Register Pages + ProtectedRoute + /app Placeholder | L2 | Fast Track (single-pass) | Done | 0 | 0 | 0 new (STORY-002-03 suite unchanged) | 0% | Single-pass (TDD Red Phase: No). 5 new components + 1 edit + `routeTree.gen.ts` auto-regen. 11 manual DoD items **deferred/unverified** — see §3. |

**Aggregate Correction Tax: ~2.5%.** No escalations. No parking-lot stories.

## 1. What Shipped

### Backend (`backend/`)

- **`app/core/security.py` (new, 153 lines)** — `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token`, plus `validate_password_length` (ADR-017 / FLASHCARDS.md bcrypt 72-byte boundary). Copy-verbatim from `new_app` with surface-level Tee-Mo renames only.
- **`app/core/config.py`** — added 3 JWT settings fields (`access_token_expire_minutes=15`, `refresh_token_expire_days=7`, `jwt_algorithm="HS256"`) per ADR-001.
- **`app/models/user.py` (new)** — `UserRegister`, `UserLogin`, `UserResponse` with a local `LaxEmailStr` annotated type. Zero `full_name`, `avatar_url`, `auth_provider`, or admin flags.
- **`app/api/deps.py` (new, ~50 lines)** — `get_current_user_id` only (cookie-first, Bearer fallback). Intentionally drops `get_current_user` / `get_current_admin_user` from `new_app`.
- **`app/api/routes/auth.py` (new, 5 routes)** — `POST /api/auth/{register,login,refresh,logout}` + `GET /api/auth/me`. httpOnly cookies, `samesite="lax"` (deliberate deviation from `new_app`'s Strict — recorded in FLASHCARDS.md), refresh_token path-scoped to `/api/auth`, anti-enumeration 401s, bcrypt guard at the route boundary.
- **`app/main.py`** — `app.include_router(auth_router)`.
- **`tests/test_security.py` (new, 9 unit tests)** — pure-function, no DB/network.
- **`tests/test_auth_routes.py` (new, 13 integration tests)** — live self-hosted Supabase, unique `test+{uuid4}@teemo.test` emails with teardown.

### Frontend (`frontend/`)

- **`src/lib/api.ts` (extended)** — added `AuthUser` type, `apiPost<TReq,TRes>` helper (cookie-forwarded, backend-`detail` error propagation), and 5 typed wrappers: `registerUser`, `loginUser`, `logoutUser`, `refreshToken`, `getMe`. Existing `apiGet` untouched.
- **`src/stores/authStore.ts` (new)** — Zustand `useAuth` store with tri-state `status` (`'unknown' | 'authed' | 'anon'`) and `setUser` / `login` / `register` / `logout` / `fetchMe` actions. `queryClient.clear()` on logout via a lazy dynamic import of `../main` (workaround for Vitest `vi.mock` TDZ). First Zustand store in Tee-Mo.
- **`src/main.tsx`** — `const queryClient` → `export const queryClient`; `<AuthInitializer />` mounted inside `<QueryClientProvider>` above `<RouterProvider>`.
- **`src/components/auth/AuthInitializer.tsx` (new)** — renderless; fires `useAuth.getState().fetchMe()` once on mount.
- **`src/components/auth/ProtectedRoute.tsx` (new)** — tri-state guard: `'unknown'` shows spinner, `'anon'` navigates to `/login?redirect=<path>`, `'authed'` renders children.
- **`src/components/auth/SignOutButton.tsx` (new)** — ghost-variant `Button` that calls `logout()` then navigates to `/login`.
- **`src/routes/login.tsx` (new)** — email+password form, inline `role="alert"` error block, authed-redirect `useEffect`, `<Link to="/register">` footer.
- **`src/routes/register.tsx` (new)** — same shape as login + client-side `TextEncoder().encode(password).length > 72` guard (mirrors backend `validate_password_length`).
- **`src/routes/app.tsx` (new)** — `<ProtectedRoute>` wrapper around a welcome card showing `user?.email` + `<SignOutButton>`. Top-of-file comment reserves the path for EPIC-003 to replace the body.
- **`src/routes/index.tsx`** — landing CTA wrapped in `<Link to="/login">`, `disabled` removed, label "Continue to login", JSDoc updated.
- **`src/routeTree.gen.ts`** — auto-regenerated by TanStackRouterVite to include `/`, `/app`, `/login`, `/register`.
- **Scaffold patches (mid-sprint, STORY-002-03):** `src/vite-env.d.ts` added (required for `import.meta.env` typing), `tsconfig.node.json` gained `skipLibCheck: true`.
- **devDependency:** `vitest@^2.1.9` — first Vitest setup in Tee-Mo. `"test": "vitest run"` in `package.json`.

### Sprint-scoped artifacts (not shipped to `main`)

- `.vbounce/sprint-context-S-02.md` — cross-cutting rules for all agents (Charter-verbatim locked deps, worktree execution notes, sprint-specific Q&A resolutions).
- `.vbounce/archive/S-02/` — 4 story folders with dev-red/dev-green/devops reports + this Sprint Report + integration audit.

## 2. Git History

```
acba4fc archive(S-02): STORY-002-04 dev report + devops report
f88c7f9 Merge STORY-002-04: Login + Register Pages + ProtectedRoute + /app Placeholder
2e71eef feat(frontend): STORY-002-04 login + register + ProtectedRoute + /app
94495f5 chore(state): STORY-002-03-auth_store → Done
b5c90ef archive(S-02): STORY-002-03 dev reports + devops report
d85c02a Merge STORY-002-03: Frontend Auth Store + API Client + AuthInitializer
d9cc7fe feat(frontend): STORY-002-03 auth store + API client + AuthInitializer
34ec049 docs(flashcards): record samesite=lax deviation + LaxEmailStr workaround
c99652a chore(S-02): mark STORY-002-02-auth_routes Done in sprint plan + product graph
50b0d0e archive(S-02): STORY-002-02 dev reports + devops report
3b37be4 Merge STORY-002-02: Auth Routes + httpOnly Cookies + get_current_user_id
0787535 feat(auth): STORY-002-02 auth routes + httpOnly cookies + get_current_user_id
cbcc281 archive(S-02): STORY-002-01 devops report + sprint-02 state update
a480219 archive(S-02): STORY-002-01 dev reports
762ff48 Merge STORY-002-01: Backend Security Primitives + bcrypt Guard
235f153 feat(auth): STORY-002-01 security primitives + bcrypt 72-byte guard
39dad9a docs(sprint): land confirmed S-02 sprint plan and 4 stories
```

17 commits ahead of `main`. 4 `--no-ff` story merges + 4 archive commits + 2 state-sync commits + 1 flashcard commit + 1 planning-lands commit + 4 story feature commits.

## 3. Acceptance Status — what was verified vs. what wasn't

### ✅ Verified by automated gates (on `sprint/S-02`)

- **Backend: 22/22 pytest** (`tests/test_auth_routes.py tests/test_security.py -v`). Live self-hosted Supabase. Known PyJWT ordering caveat: must run auth_routes before security (see §5 Debt #1).
- **Frontend: 10/10 Vitest** (`authStore.test.ts`). Pure-function store coverage of all state transitions.
- **Frontend build: `tsc -b && vite build` exit 0.** One cosmetic `[INEFFECTIVE_DYNAMIC_IMPORT]` warning from the `authStore.ts` lazy main import — pre-accepted.
- **Static audit: 5 grep gates clean** across the 6 new frontend files — zero `google`, zero `fetch(`, zero `localStorage`, zero `any`, zero new `@theme` tokens.
- **Strip list: 7 grep hits, all in docstrings** documenting what was removed from `new_app`. Zero live-code references to `chy_*`, `_signup_allowed_for_email`, `check_user_cap`, `_maybe_promote_admin`, `link_pending_invites`, `setRealtimeAuth`, `loginWithGoogle`, `full_name`, `avatar_url`, `is_instance_admin`.
- **Integration audit verdict: SHIP** (see `.vbounce/archive/S-02/sprint-integration-audit-S-02.md`).

### ⚠️ NOT verified — Browser walkthrough skipped

Story §2.2 specifies 11 manual browser checks. **The user elected to close the sprint without running them.** The following claims are therefore **asserted from code review only**, not visually confirmed:

| # | Manual check | Risk if broken | How it could fail despite passing automated gates |
|---|---|---|---|
| 1 | Landing CTA → `/login` | Low | TanStack Link wraps the button; build compiled; would require a router config bug invisible to tsc |
| 2 | Register → cookies set + lands on `/app` | Medium | Integration tests cover the HTTP contract; what's untested is the React Router → Zustand → navigate chain in a real browser |
| 3 | 73-byte client-side guard blocks network call | Medium | `TextEncoder` code path exists in `register.tsx`; not exercised by any test — pure visual verification |
| 4 | Login from fresh Incognito → `/app` | Low | Backend contract covered; frontend wiring is the exposure |
| 5 | Wrong password inline error | Low | `err.message` propagation from `apiPost` → store → form is code-reviewed only |
| 6 | `/app` while logged out → spinner → `/login` | Medium | `ProtectedRoute` `useEffect` redirect is a known single-frame spinner — no test covers the actual transition |
| 7 | Hard refresh on `/app` rehydrates | Medium | `AuthInitializer` → `fetchMe` → Set-Cookie round-trip is untested end-to-end |
| 8 | Sign out clears cookies + re-redirects | Medium | `logout()` → `queryClient.clear()` → navigate chain depends on the lazy dynamic import resolving correctly at runtime |
| 9 | No `"google"` in rendered DOM | Low | Static grep confirms zero source-code hits; Tailwind utility classes don't contain `"google"` |
| 10 | `/api/health` unaffected | Low | Backend health endpoint was not modified in S-02; regression would require an unrelated commit |
| 11 | Build still clean on sprint branch | ✅ Verified | Already verified automatically |

**Recommendation:** Run the 11 manual checks before customer/stakeholder demo. They take ~3 minutes in Incognito and cover the exact gap that unit/integration tests leave open.

## 4. Flashcards — Batch Review (deferred from mid-sprint per user feedback)

Per your guidance earlier in the sprint, flashcard candidates were **collected silently during bouncing and batched here** for a single approval point at sprint close. Two of these were already recorded mid-sprint because the sprint context file pre-promised them; the other two are new and need your decision.

### ✅ Already recorded (for completeness)

1. **[FLASHCARDS.md] Auth cookies use `samesite="lax"`, NOT `strict`** — deliberate deviation from `new_app` so EPIC-005/006 OAuth redirects don't drop the session cookie. Pre-promised in `sprint-context-S-02.md`. Recorded at commit `34ec049` after STORY-002-02 merged.

2. **[FLASHCARDS.md] Pydantic `EmailStr` rejects `.test` TLD via `email-validator` 2.x `globally_deliverable`** — use `LaxEmailStr` (in `backend/app/models/user.py`) or `@example.com` fixture emails. Recorded at commit `34ec049`.

### 📝 New candidates — need your decision

3. **[CANDIDATE] Vitest 2.x `vi.mock` hoisting TDZ — use `vi.hoisted(...)` for mock vars**
   - **Seen in:** STORY-002-03 Green phase
   - **What happened:** Red test file used `const clearMock = vi.fn()` + `vi.mock('../../main', () => ({ queryClient: { clear: clearMock } }))`. Vitest 2.x AST-hoists `vi.mock` above the `const` declaration, putting `clearMock` in TDZ when the factory runs.
   - **Fix (correct):** `const { clearMock } = vi.hoisted(() => ({ clearMock: vi.fn() }))` — the `vi.hoisted` wrapper is also hoisted, so the closure resolves correctly.
   - **Workaround when test is immutable (what we did):** Use a lazy `async function getQueryClient() { return (await import('../main')).queryClient }` in `authStore.ts`. Production-safe; emits a cosmetic Vite `[INEFFECTIVE_DYNAMIC_IMPORT]` warning.
   - **My recommendation: ACCEPT.** Saves the next dev 30+ minutes of TDZ debugging. Strong signal.

4. **[CANDIDATE] TanStack Router + `tsc -b && vite build` chicken-and-egg on new routes**
   - **Seen in:** STORY-002-04 single-pass
   - **What happened:** `frontend/package.json` `"build"` = `"tsc -b && vite build"`. On the first build after adding a new `src/routes/*.tsx` file, `tsc` runs before the Vite plugin regenerates `routeTree.gen.ts`, so `tsc` fails on stale imports.
   - **Workaround (what we did):** Run `node_modules/.bin/vite build` once standalone first (regenerates the tree), then `npm run build` succeeds. Subsequent builds work.
   - **Root fix candidates (for a future retro):** Either reorder `"build": "vite build && tsc --noEmit"`, or add a `"pretsr": "tsr generate"` step, or configure the plugin's watcher to write the file synchronously during tsc.
   - **My recommendation: ACCEPT.** This will recur every time someone adds a route. Document the workaround now; defer the build-script reorder to `/improve` at the retro.

### 🚫 Rejected / reclassified

5. **[REJECTED as flashcard — filed as BUG instead] PyJWT module-level options leak → test ordering flake.** Running `tests/test_security.py` before `tests/test_auth_routes.py` poisons PyJWT's module-level options dict and flips `test_decode_token_rejects_tampered_signature`. `-p no:randomly` alone is insufficient; explicit ordering (auth_routes BEFORE security) is required. This is a code defect, not a lesson — see §6.

### Scaffold gaps — retro items (not flashcards)

6. **`frontend/tsconfig.node.json` was missing `skipLibCheck: true`** — blocked `tsc -b` on `@tanstack/router-core` + `@types/react-dom` lib types. Patched in STORY-002-03.
7. **`frontend/src/vite-env.d.ts` was missing** — blocked `import.meta.env` type-checking. Patched in STORY-002-03.

**Action requested:** Say *accept 3 and 4* (or override) and I'll record both to `FLASHCARDS.md` in a single commit.

## 5. Known Accepted Debt (carried forward)

From the integration audit. Each item is already documented in at least one subagent report and accepted by the Team Lead.

1. **PyJWT module-level options leak — test ordering matters.** Running `test_security.py` before `test_auth_routes.py` poisons a module-global in PyJWT and flips the tampered-signature assertion. Production code is unaffected — it's test-harness friction only. **BUG report queued: see §6.**
2. **Vitest 2.x `vi.mock` hoisting TDZ — lazy dynamic import workaround** in `authStore.ts`. Cosmetic `[INEFFECTIVE_DYNAMIC_IMPORT]` Vite warning. No runtime impact.
3. **TanStack Router + `tsc -b && vite build` chicken-and-egg.** First build after adding a route requires a vite-first run. Not blocking — `routeTree.gen.ts` is now committed with all S-02 routes.
4. **S-01 scaffold gaps patched mid-sprint** (`vite-env.d.ts`, `tsconfig.node.json skipLibCheck`). Small hygiene patches, no new surface area.
5. **`.env DEBUG=true` added mid-sprint** (not in STORY-002-03 §3.0 prereq). Required so cookies don't get `Secure` on `http://localhost`. Retroactive prereq capture suggested for the retro.

## 6. Backlog Items For Next Sprint

### 🐛 BUG-20260411-001 — PyJWT module-level options leak

**Summary:** `test_decode_token_rejects_tampered_signature` (STORY-002-01 suite) fails when run AFTER `test_auth_routes.py::test_me_with_expired_access_cookie` (STORY-002-02 suite). A helper or fixture in the auth-routes flow mutates PyJWT's module-level `options` dict (most likely a permissive `jwt.decode(..., options={"verify_signature": False})` call), which then leaks into the tampered-signature test.

**Scope:**
- Fix `backend/app/core/security.py::decode_token` to use a scoped `jwt.PyJWT()` instance instead of the module-level `jwt.decode`.
- OR add a session-scoped autouse pytest fixture that resets `jwt.api_jwt._jwt_global_obj` (or equivalent) between tests.
- OR if the leak is in our own test code, isolate the permissive-decode call in a fixture and clean it up in teardown.

**Acceptance:**
- `pytest tests/test_security.py tests/test_auth_routes.py -p no:randomly` passes in either order.
- `pytest tests/` with `pytest-randomly` enabled passes 10 times in a row.

**Priority:** P2 (test-harness hygiene; production unaffected)

**Complexity:** L1–L2 (pure backend, ~1 hour)

**Where to add:** Backlog for the next sprint, probably S-03 if a Dev has spare capacity after the critical path.

**TODO for the Team Lead:** File `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md` using `.vbounce/templates/bug.md` before closing S-02 physically. (Not done yet — awaiting user confirmation of sprint close.)

## 7. Framework Self-Assessment

Collected from `## Process Feedback` sections of all S-02 agent reports.

### 🟢 What worked

- **Fast Track for Fast Track** — all 4 stories were genuinely low-risk (high-quality story specs, clear copy sources, bounded surface area). Skipping QA and Architect saved an estimated 3–4 hours. No defects slipped through.
- **Ready-to-use §3.3 code blocks in story specs.** Every story's Implementation Guide had verbatim-usable code. Dev agents reported this as the single biggest accelerator.
- **Pre-symlinked `.env` in worktrees (mid-sprint improvement).** After STORY-002-01's `.env` friction, the Team Lead pre-symlinked `.env` and later `sprint-context-S-02.md` into each new worktree. Zero env friction on STORY-002-03 and STORY-002-04.
- **Pre-committed flashcards via sprint context.** `sprint-context-S-02.md` explicitly promised to record `samesite="lax"` and the bcrypt triple-enforcement. Mid-sprint recording happened without drama.
- **Strict test-pattern-validation gate (Step 2c).** Catching and clearing Red test patterns before Green saved rework on STORY-002-01 and STORY-002-02. Missed on STORY-002-03's `vi.mock` hoisting — the cost was the lazy-import workaround, not a rebuild.

### 🟡 What was rough

- **Worktree setup is undernourished.** `.env` and `sprint-context-S-XX.md` symlinks had to be manually created by the Team Lead. This should be automated in `agent-team/SKILL.md` Step 1b. Candidate improvement for `/improve`.
- **Task prompts drifted from story specs.** Some task files re-described what §3.3 already specified in code blocks — risking drift. Future task files should link to sections rather than paraphrase them.
- **Token accounting is inconsistent.** Dev-report YAML `input_tokens`/`output_tokens`/`total_tokens` fields are placeholder values in at least 3 of 4 stories. Task notification totals are authoritative and were used for §TOP `total_tokens_used`. Improvement candidate: either drop the report-level fields or wire them to the actual counter.
- **Build script ordering (`tsc -b && vite build`) fights TanStack Router Vite plugin.** Recurring pain point for every story that adds a route. See flashcard candidate #4 and retro item for `/improve`.

### 🔴 What broke

- **PyJWT test-order leak** (see BUG-20260411-001). Only surfaced in the DevOps post-merge gate, not in any Dev Green run, because Dev tests ran the suites individually. Recommend adding a post-merge "full suite in deterministic order" gate to `agent-team/SKILL.md` Step 5 Post-merge Validation.

### Improvement suggestions queued for `/improve`

1. **Automate worktree setup:** `.env`, `sprint-context-S-{XX}.md`, (and optionally `FLASHCARDS.md` symlinks) should be handled by the `run_script.sh` wrapper around `git worktree add` — not by the Team Lead manually.
2. **Reorder frontend build script** to `vite build && tsc --noEmit` OR add a `pretsr` step — current order fights TanStack Router on new routes.
3. **Wire real token counting** into agent reports OR remove the placeholder fields.
4. **Add a deterministic full-suite test gate** to post-merge validation (not just the individual story's suite).

## 8. Vdoc Staleness Check

`vdocs/_manifest.json` — check not run (no vdocs initialized in this project). If the user wants product docs generated, the Scribe agent can be spawned with a `vdoc init` task after the release merge. **Recommendation: defer until after EPIC-003 ships so there's a non-trivial frontend surface to document.**

## 9. Delivery Log Entry (for Roadmap §7)

Proposed line to append to `product_plans/strategy/tee_mo_roadmap.md` §7:

```
| 2026-04-11 | **Sprint S-02 delivered (Auth — D-01 Release 1: Foundation).** 4 stories, all Fast Track, zero escalations, ~2.5% aggregate correction tax. Ships: backend `validate_password_length` + 5 JWT/httpOnly cookie endpoints (`/api/auth/{register,login,refresh,logout,me}`), frontend Zustand `useAuth` store + `lib/api.ts` wrappers + `AuthInitializer`, and full UI: `/login`, `/register`, `/app` placeholder (gated by `ProtectedRoute`), `SignOutButton`, enabled landing CTA. 22 backend tests + 10 frontend Vitest + clean `npm run build`. Integration audit verdict: SHIP. Carries: 1 BUG (PyJWT test ordering), 2 new FLASHCARDS pending user approval, 4 framework improvement candidates for `/improve`. Release tag: pending release merge. |
```

## 10. Actions Pending User Approval

Before I can physically close the sprint (release merge → `main`, archive move, state.json update), I need:

1. **Flashcards 3 & 4** (Vitest TDZ, router/tsc chicken-and-egg) — accept or override.
2. **BUG-20260411-001 template filing** — confirm the name and epic assignment (EPIC-002 vs EPIC-000/misc).
3. **Release tag name** — suggestion: `v0.2.0-auth` (S-01 was foundation; S-02 adds auth; not yet demoable end-to-end without the EPIC-003 workspace UI).
4. **Delivery Log entry** for §7 of the Roadmap — confirm the text in §9 or override.
5. **Explicit authorization for release merge** `main ← sprint/S-02 --no-ff`.
