---
sprint_id: "SPRINT-02"
remote_id: "local:SPRINT-02"
source_tool: "vbounce-migration"
status: "Completed"
start_date: "2026-04-11"
end_date: "2026-04-11"
synced_at: "2026-04-24T00:00:00Z"
created_at: "2026-04-11T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-sprint-plan"
updated_at_version: "cleargate-migration-2026-04-24"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/archive/sprints/sprint-02/sprint-02.md`. Sprint Shipped in S-02. Body retains V-Bounce sprint-plan structure; not reshaped to ClearGate's PM-tool-pull template because V-Bounce plans encode more planning detail (§0 Readiness Gate, §4 Execution Strategy, §5 Metrics).

---
sprint_id: "sprint-02"
sprint_goal: "End-to-end email + password auth: register, login, refresh, logout, /me; frontend ProtectedRoute gating a /app placeholder; auto-login on register; ready for EPIC-003 to replace the body of /app with the real workspace dashboard."
dates: "2026-04-11"
status: "Completed"
delivery: "D-01 (Release 1: Foundation)"
confirmed_by: "Solo dev (user)"
confirmed_at: "2026-04-11"
---

# Sprint S-02 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.
> Status is "Planning". Human confirmation moves to "Confirmed". Execution moves to "Active".

### Pre-Sprint Checklist
- [x] Prior sprint (S-01) archived to `product_plans/archive/sprints/sprint-01/`
- [x] All 4 stories below authored with full context packs (§1 spec, §2 acceptance, §3 implementation, §4 quality gates)
- [x] No stories have 🔴 High ambiguity (all 🟢 Low)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Roadmap §5 and Charter §6
- [x] FLASHCARDS.md reviewed — bcrypt 5.0 rule is baked into STORY-002-01 + STORY-002-02
- [x] Design Guide referenced in UI stories (STORY-002-04)
- [x] Charter §10 Epic Seed Map (Authentication row) followed line-by-line for the strip list
- [x] **Architect Sprint Design Review — waived** by human 2026-04-11 (Q6). Team Lead owns §2 Execution Strategy.
- [x] **Human has confirmed this sprint plan** — confirmed 2026-04-11; Q5 and Q6 both resolved.

---

## 1. Active Scope

> 4 stories: 1× L1, 3× L2. Target: ~4 hours total. Second half of Day 1 / first half of Day 2 depending on first-try success.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-002-01: Backend Security Primitives + bcrypt Guard](./STORY-002-01-security_primitives.md) | EPIC-002 | L1 | Done | — |
| 2 | [STORY-002-02: Auth Routes + Cookies + `get_current_user_id`](./STORY-002-02-auth_routes.md) | EPIC-002 | L2 | Done | STORY-002-01 |
| 3 | [STORY-002-03: Frontend Auth Store + API Client + AuthInitializer](./STORY-002-03-auth_store.md) | EPIC-002 | L2 | Done | STORY-002-02 |
| 4 | [STORY-002-04: Login + Register Pages + ProtectedRoute + /app Placeholder](./STORY-002-04-login_register_pages.md) | EPIC-002 | L2 | Done | STORY-002-03 |

### Story Summaries

**STORY-002-01: Backend Security Primitives + bcrypt Guard** (L1, ~30 min)
- Goal: Ship `backend/app/core/security.py` with hash/verify/create/decode + a new `validate_password_length` guard enforcing the bcrypt-5.0 72-byte rule (ADR-017, FLASHCARDS.md).
- Files: `backend/app/core/security.py` (new), `backend/app/core/config.py` (edit — add 3 JWT fields), `backend/tests/test_security.py` (new).
- Deliverable: 9 unit tests covering salting, JWT expiry windows, tampered-signature rejection, and the 72-byte UTF-8 byte-length boundary. Pure-function module — no DB, no network.
- Copy source: `/Users/ssuladze/Documents/Dev/new_app/backend/app/core/security.py` (144 lines, verbatim).

**STORY-002-02: Auth Routes + Cookies + Deps** (L2, ~1.5 h)
- Goal: `POST /api/auth/{register,login,refresh,logout}` + `GET /api/auth/me`, httpOnly cookies, `get_current_user_id` dependency, minimal `UserRegister/UserLogin/UserResponse` models.
- Files: `backend/app/models/user.py`, `backend/app/api/deps.py`, `backend/app/api/routes/auth.py`, `backend/app/api/__init__.py`, `backend/app/api/routes/__init__.py`, `backend/app/models/__init__.py` (all new), `backend/app/main.py` (edit — include router), `backend/tests/test_auth_routes.py` (new).
- Deliverable: 13 integration tests hitting live self-hosted Supabase. Register returns auto-login cookies + `{user}`. Strip list from Charter §10 Epic Seed Map fully applied (no `chy_*`, no `_signup_allowed_for_email`, no `check_user_cap`, no `link_pending_invites`, no `_maybe_promote_admin`, no `google*`, no `full_name`, no `access_token` body echo).
- Notable design choice: **`samesite="lax"`** (not `strict` as in new_app) so that OAuth redirects in EPIC-005/006 don't drop the cookie on the return hop. Still CSRF-safe for JSON-body endpoints.

**STORY-002-03: Frontend Auth Store + API Client + AuthInitializer** (L2, ~1 h)
- Goal: Zustand `useAuth` store with tri-state `status` field, typed `lib/api.ts` wrappers, renderless `AuthInitializer` mounted in `main.tsx`.
- Files: `frontend/src/stores/authStore.ts` (new), `frontend/src/components/auth/AuthInitializer.tsx` (new), `frontend/src/lib/api.ts` (edit — add `apiPost` + `AuthUser` + 5 wrappers), `frontend/src/main.tsx` (edit — export `queryClient`, mount `AuthInitializer`), `frontend/src/stores/__tests__/authStore.test.ts` (new), `frontend/package.json` (edit — add `vitest@^2.1.0` if missing).
- Deliverable: 10 Vitest unit tests covering every state transition. On `npm run dev`, one `GET /api/auth/me` fires on mount with no console errors.
- Copy source: `/Users/ssuladze/Documents/Dev/new_app/frontend/src/hooks/useAuth.ts` (stripped of Realtime + Google).

**STORY-002-04: Login + Register Pages + ProtectedRoute + /app Placeholder** (L2, ~1.5 h)
- Goal: Full user-visible auth flow — register → auto-login → `/app` greeting → sign out → `/login`. `/app` is a temporary landing page whose body EPIC-003 will replace with the workspace list.
- Files: `frontend/src/routes/login.tsx`, `frontend/src/routes/register.tsx`, `frontend/src/routes/app.tsx`, `frontend/src/components/auth/ProtectedRoute.tsx`, `frontend/src/components/auth/SignOutButton.tsx` (all new), `frontend/src/routes/index.tsx` (edit — enable the "Continue to login" CTA).
- Deliverable: 11 manual verification steps pass (see story §2.2). Client-side 72-byte password guard mirroring the server. No Google OAuth leakage anywhere. `npm run build` type-checks clean.
- Tests: none automated in this story (store is already covered by STORY-002-03; Playwright deferred). Manual verification is the gate.

### Context Pack Readiness

**STORY-002-01**
- [x] Story spec complete (§1 — 6 detailed requirements)
- [x] Acceptance criteria defined (§2 — 9 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code snippets including test skeleton)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-002-02**
- [x] Story spec complete (§1 — 9 detailed requirements + strip list)
- [x] Acceptance criteria defined (§2 — 13 Gherkin scenarios)
- [x] Implementation guide written (§3 — full file-by-file code snippets)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-002-03**
- [x] Story spec complete (§1 — 7 detailed requirements)
- [x] Acceptance criteria defined (§2 — 10 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code for api.ts, authStore, AuthInitializer)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-002-04**
- [x] Story spec complete (§1 — 10 detailed requirements)
- [x] Acceptance criteria defined (§2 — 11 Gherkin scenarios + 11-item manual checklist)
- [x] Implementation guide written (§3 — full code for all new components)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

### Escalated / Parking Lot
- None.

---

## 2. Execution Strategy

> Team Lead authored. Architect Sprint Design Review waived by human 2026-04-11 (sprint §0 Q6).

### Phase Plan
The dependency chain is strictly linear — there is no parallelism to exploit in S-02:

```
STORY-002-01 → STORY-002-02 → STORY-002-03 → STORY-002-04
  (security)    (routes)        (store)         (pages)
```

- **Phase 1**: STORY-002-01 alone.
- **Phase 2**: STORY-002-02 alone.
- **Phase 3**: STORY-002-03 alone.
- **Phase 4**: STORY-002-04 alone.

Each story unblocks the next because the artifacts it produces are direct imports in the following story. There is no benefit to starting STORY-002-03 before STORY-002-02 lands because the frontend store's error messages and type shape come from the backend contract.

### Merge Ordering

| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-002-01 | Pure primitives; unblocks everything. Fastest Green → merge. |
| 2 | STORY-002-02 | Depends on primitives; owns the backend auth surface. |
| 3 | STORY-002-03 | Depends on the backend contract being live to validate end-to-end. |
| 4 | STORY-002-04 | Final integration; last merge. |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|--------------------|------|
| `backend/app/core/config.py` | STORY-002-01 (adds 3 JWT fields) | None — additive only. |
| `backend/app/main.py` | STORY-002-02 (adds `include_router(auth_router)`) | Low — single-line addition. |
| `frontend/src/lib/api.ts` | STORY-002-03 (adds `apiPost` + 5 wrappers + `AuthUser` type) | Low — additive, leaves existing `apiGet` untouched. |
| `frontend/src/main.tsx` | STORY-002-03 (exports `queryClient`, mounts `AuthInitializer`) | Low — minimal, additive. |
| `frontend/src/routes/index.tsx` | STORY-002-04 (wraps existing disabled CTA in `<Link>`) | Low — surgical edit. |

### Execution Mode

| Story | Label | Mode | Reason |
|-------|-------|------|--------|
| STORY-002-01 | L1 | Fast Track | L1 auto-qualifies. Copy-verbatim + one new guard function. |
| STORY-002-02 | L2 | Fast Track (human-approved 2026-04-11) | Security-critical, but the §1.2 R5/R6 strip list and §4.2 DoD grep audit are explicit. Dev must run the strip-list grep audit before marking Done — that audit becomes the de-facto QA gate. |
| STORY-002-03 | L2 | Fast Track (human-approved 2026-04-11) | Well-specified Zustand + Vitest. Unit-test coverage is the gate. |
| STORY-002-04 | L2 | Fast Track (human-approved 2026-04-11) | UI wiring on top of an already-tested store. Manual verification is the gate. |

> **Fast Track audit requirement for STORY-002-02**: because QA is skipped, the Developer agent MUST run and paste the output of this grep in the implementation report before marking the story Done. Zero hits is required:
>
> ```bash
> grep -rEn 'chy_|_signup_allowed_for_email|check_user_cap|_maybe_promote_admin|link_pending_invites|setRealtimeAuth|full_name|avatar_url|is_instance_admin|google' \
>   backend/app/api/routes/auth.py \
>   backend/app/api/deps.py \
>   backend/app/models/user.py
> ```

### ADR Compliance Notes

- **ADR-001 (Auth)**: 15-min access + 7-day refresh in httpOnly cookies — enforced by `access_token_expire_minutes=15` and `refresh_token_expire_days=7` defaults in `config.py` (STORY-002-01), consumed verbatim by `security.py`.
- **ADR-012 (Copy-then-optimize from new_app)**: Every single file in this sprint has a documented copy source from `/Users/ssuladze/Documents/Dev/new_app/`. Strip lists are explicit in STORY-002-02 §1.2 R5 / R6.
- **ADR-014 (Frontend stack: Zustand)**: STORY-002-03 introduces the first Zustand store in Tee-Mo.
- **ADR-017 (bcrypt 72-byte guard)**: Double-enforced — `validate_password_length` in `security.py` (STORY-002-01) AND called from the `/register` handler before `hash_password` (STORY-002-02) AND mirrored as client-side validation in `register.tsx` (STORY-002-04).
- **ADR-022 (Design System)**: STORY-002-04 uses only `Button`/`Card` primitives + built-in Tailwind 4 tokens. No new UI library.

### Dependency Chain

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-002-02 | STORY-002-01 | Imports `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `decode_token`, `validate_password_length`. |
| STORY-002-03 | STORY-002-02 | Backend routes must be live for the store's `fetchMe`/`login`/`register` wrappers to validate end-to-end. |
| STORY-002-04 | STORY-002-03 | `login.tsx`, `register.tsx`, `ProtectedRoute.tsx`, `SignOutButton.tsx`, `app.tsx` all import `useAuth` from the store. |

### Risk Flags

**From Roadmap §5 / Charter §6:**
- **bcrypt 5.0 breaking change** — triple-enforced (see ADR-017 note above). Primary risk is the client-side guard in `register.tsx` drifting from the server if the byte-limit changes. Mitigation: keep the "72 bytes" value in one place per tier (constant in `security.py`, literal in `register.tsx` with a comment pointing at `security.validate_password_length`).
- **Self-hosted Supabase behavior** — `teemo_users` RLS is bypassed by service_role key (verified in S-01). Insert conflict on duplicate email must return 409 before reaching Supabase's raw error surface — the `existing.data` check in the register handler covers this.
- **Hackathon deadline (2026-04-18)** — S-02 is on the critical path for Release 1. Sprint target ~4 h; hard stop at 8 h before we should escalate.

**Sprint-specific:**
- **Cookie SameSite=Lax vs Strict** — we deliberately deviate from new_app's `strict` because EPIC-005/006 OAuth redirects need Lax. If a future sprint re-enables Strict, EPIC-005 will immediately break and we'll need to remember why. Record this in FLASHCARDS.md after merge.
- **TanStack Router auto-generation** — `routeTree.gen.ts` is regenerated by the Vite plugin on dev/build. If the plugin is misconfigured, the 3 new routes will silently fail to register. Mitigation: the §2.2 manual checklist in STORY-002-04 includes a direct navigation test for each route.
- **Vitest first-use** — this is Tee-Mo's first Vitest setup. If the default config needs customization (e.g., JSDOM environment for future component tests), note it in FLASHCARDS.md.
- **Self-message in test DB** — `backend/tests/test_auth_routes.py` writes to the live Supabase. Using `test+{uuid4}@teemo.test` emails and teardown fixtures prevents collisions, but tests must NOT run against prod. Confirm `.env` points at the self-hosted dev instance before running the suite.
- **`backend/app/models/` package is new** — if `main.py` or `config.py` ever import from `models.*` in a way that creates a circular import with `api.deps`, we'll see it first in S-02. Mitigation: the story §3.3 deliberately avoids cross-imports between `models/user.py` and `api/deps.py` (deps uses only the raw JWT `sub` string, never `User`).

---

## 3. Sprint Open Questions

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| **Q1**: Register UX — auto-login or redirect to /login? | Auto-login (mirrors new_app; user drops straight into `/app`) | Defines response body + navigate target | Solo dev | **Resolved** 2026-04-11 — auto-login |
| **Q2**: `/app` vs `/hello` vs `/dashboard` for the post-login placeholder | `/app` (stable URL; EPIC-003 replaces the body not the path) | Saves a router refactor in Sprint 3 | Team Lead | **Resolved** 2026-04-11 — `/app` |
| **Q3**: Route name `/register` vs `/signup` | `/register` (mirrors new_app; matches backend endpoint name) | Cosmetic consistency | Team Lead | **Resolved** 2026-04-11 — `/register` |
| **Q4**: CORS origins for S-02 | Leave as `http://localhost:5173` via `.env`; Coolify domain added via env at deploy time (no code change) | None — env-driven already | Team Lead | **Resolved** 2026-04-11 — env only |
| **Q5**: Fast Track for STORY-002-02? | Fast Track all 4 stories. Dev runs the strip-list grep audit (see §2 Execution Mode note) as the de-facto QA gate for 002-02. | Saves ~30–45 min | Solo dev | **Resolved** 2026-04-11 — Fast Track |
| **Q6**: Architect Sprint Design Review | Skip — Team Lead owns §2 Execution Strategy. | Saves ~15 min | Solo dev | **Resolved** 2026-04-11 — skip |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-002-01 | — | — | — | — | — | Not yet started |
| STORY-002-02 | — | — | — | — | — | Not yet started |
| STORY-002-03 | — | — | — | — | — | Not yet started |
| STORY-002-04 | — | — | — | — | — | Not yet started |

**Aggregate Correction Tax**: —

**Process lessons recorded to FLASHCARDS.md**: —
| STORY-002-01-security_primitives | Done | 0 | 0 | 0% | Fast Track L1. 9/9 tests green first try. Strip audit clean. |
| STORY-002-02-auth_routes | Done | 0 | 0 | 5% | Fast Track L2. 13/13 live Supabase tests green. LaxEmailStr workaround for email-validator 2.x .test TLD rejection. DEBUG=true added to .env. |
| STORY-002-03-auth_store | Done | 0 | 0 | 5% | Fast Track L2. 10/10 Vitest store tests green. Lazy dynamic import workaround for Vitest 2.x vi.mock hoisting TDZ. Fixed two S-01 scaffold gaps (vite-env.d.ts, tsconfig.node.json skipLibCheck). Vitest 2.1.9 first use in Tee-Mo. |
| STORY-002-04-login_register_pages | Done | 0 | 0 | 0% | Fast Track L2 single-pass. 6 new/edited files + routeTree.gen.ts. Build + 10 Vitest tests green. Browser walkthrough deferred to Step 5.7. |
<!-- EXECUTION_LOG_END -->
