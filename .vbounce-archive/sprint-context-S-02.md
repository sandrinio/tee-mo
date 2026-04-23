---
sprint_id: "S-02"
created: "2026-04-11"
last_updated: "2026-04-11"
---

# Sprint Context: S-02

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions
> Applies to STORY-002-04 (login/register/app pages). UI work must follow the existing Tee-Mo design system.

- **Source of truth**: `product_plans/strategy/tee_mo_design_guide.md` — read before writing any JSX.
- **Primitives only**: Use existing `Button` and `Card` components. Do NOT introduce new UI libraries. ADR-022.
- **Tailwind 4**: `@theme` declares custom tokens only. Built-in slate/zinc/red/blue/etc. ship by default — never redefine them. (FLASHCARDS.md, STORY-001-03 lesson)
- **Brand tokens**: coral accent + semantic success/warning/danger/info are already declared in `frontend/src/app.css`. Reuse.

## Shared Patterns & Conventions
> Technical patterns all agents must follow. Derived from ADRs, FLASHCARDS.md, and sprint planning.

- **Backend — Supabase access**: All Supabase access goes through `app.core.db.get_supabase()`. Never call `create_client()` inline. (FLASHCARDS.md / STORY-001-01)
- **Backend — new tables**: Any new Supabase table must be added to `TEEMO_TABLES` in `backend/app/main.py` in the same commit that creates it.
- **Backend — table prefix**: All Tee-Mo tables are prefixed `teemo_` on the shared self-hosted Supabase. No new tables in this sprint, but if you must reference one, use the prefixed name.
- **Backend — password boundary validation**: `validate_password_length` from `app.core.security` MUST be called BEFORE `hash_password` on every registration path. bcrypt 5.0 raises `ValueError` on > 72-byte inputs (ADR-017).
- **Backend — JWT**: Access token 15 min, refresh token 7 days, httpOnly cookies, `samesite="lax"` (NOT strict — deviation from new_app, documented in sprint-02.md §2 Risk Flags).
- **Frontend — data fetching**: All frontend fetches go through `@tanstack/react-query` (`useQuery` / `useMutation`) calling typed wrappers in `frontend/src/lib/api.ts`. Never call `fetch` directly in components. Never instantiate a second `QueryClient`. (FLASHCARDS.md / STORY-001-04)
- **Frontend — base URL**: `VITE_API_BASE_URL` drives the API base; defaults to `http://localhost:8000`.
- **Frontend — auth store**: `useAuth` Zustand store exposes a tri-state `status` field (`"idle" | "authenticated" | "unauthenticated"`). `ProtectedRoute` reads `status`, never the raw `user`.
- **Copy-then-strip discipline**: S-02 copies verbatim from `/Users/ssuladze/Documents/Dev/new_app/`. Each story's §1.2 has an explicit **strip list** (no `chy_*`, no `_signup_allowed_for_email`, no `check_user_cap`, no `_maybe_promote_admin`, no `link_pending_invites`, no `setRealtimeAuth`, no `google*`, no `full_name`, no `avatar_url`, no `is_instance_admin`). Developer MUST run the strip-list grep audit at the end of STORY-002-02 and paste output into the Dev report. Zero hits required.

## Locked Dependencies
> Verbatim from Charter §3.2 Technical Foundation. Do NOT change these during this sprint.

| Package | Version | Reason |
|---------|---------|--------|
| `react` + `react-dom` | 19.2.5 | Charter §3.2 |
| `vite` | 8.0.8 | Charter §3.2 |
| `@tanstack/react-router` | 1.168.12 | Charter §3.2 |
| `@tanstack/react-query` | 5.97.0 | Charter §3.2 |
| `zustand` | 5.0.12 | Charter §3.2 (first use in S-02) |
| `fastapi[standard]` | 0.135.3 | Charter §3.2 |
| `supabase` (python) | 2.28.3 | Charter §3.2 |
| `bcrypt` | 5.0.0 | Charter §3.2 — **breaking change**: ValueError on > 72-byte passwords |
| `PyJWT` | 2.12.1 | Charter §3.2 — requires secret ≥ 32 bytes in production |

> Vitest is introduced in STORY-002-03 but is NOT pinned in Charter §3.2. Use the version declared in that story's spec (`vitest@^2.1.0`). Do not upgrade mid-sprint.

## Active Lessons (Broad Impact)
> FLASHCARDS.md entries that affect multiple stories in this sprint.

- **[2026-04-11] bcrypt 5.0 72-byte limit** — validate at the boundary, return 422 with `password_too_long`. Triple-enforced this sprint: `validate_password_length` in STORY-002-01, called in `/register` handler in STORY-002-02, mirrored client-side in STORY-002-04 `register.tsx`.
- **[2026-04-11] `get_supabase()` only** — never call `create_client()` ad-hoc. Update `TEEMO_TABLES` when adding tables.
- **[2026-04-11] TanStack Query is the only data-fetching path** — no raw `fetch` in components.
- **[2026-04-11] Tailwind 4 `@theme` declares custom tokens only** — do not redefine built-in slate/zinc/red/etc.
- **[2026-04-11] Sprint context is Charter-verbatim** — all "Locked Dependencies" rows here were quoted from Charter §3.2 (never from memory).

## Worktree Execution Notes
> Friction discovered during STORY-002-01 Red phase. All agents in this sprint must account for these.

- **Backend venv is NOT in the worktree.** Worktrees share the main repo's `backend/.venv`. Always run pytest with the absolute interpreter path: `/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest ...`. The shell's default `python` is 3.9 and will fail. Running `cd backend && python -m pytest` from inside a worktree also does NOT pick up the venv automatically.
- **`.env` symlink at the worktree root** is pre-created by the Team Lead at Step 1b of sprint setup. `backend/app/core/config.py` resolves `.env` three directories up from itself, which lands on the worktree root. If the symlink is missing, `pydantic_settings` raises `ValidationError` on `settings = Settings()` and masks the real test failure. If you find the symlink missing, recreate it: `ln -sf ../../.env .env` from the worktree root.

## Sprint-Specific Rules
> Decisions made during Sprint Planning (see sprint-02.md §3 Open Questions).

- **Auto-login on register** (Q1 resolved): `/register` response body must match `/login` — `{user}` + cookies set. Frontend calls `navigate('/app')` after success, not `navigate('/login')`.
- **`/app` path, not `/dashboard` or `/hello`** (Q2 resolved): STORY-002-04 ships a placeholder body at `/app`. EPIC-003 will replace the body, not the path.
- **`/register` path, not `/signup`** (Q3 resolved): matches backend endpoint.
- **CORS is env-driven** (Q4 resolved): do not hardcode origins in code. Leave `.env` as the control plane.
- **All 4 stories are Fast Track** (Q5 resolved): no QA or Architect agent pass. Gates collapse into the Developer's own checks:
  - STORY-002-01: 9 unit tests must pass + no lint errors.
  - STORY-002-02: 13 integration tests must pass + strip-list grep audit with zero hits (see `sprint-02.md §2 Execution Mode note`). Paste grep output into Dev report.
  - STORY-002-03: 10 Vitest unit tests must pass + `npm run build` must type-check clean.
  - STORY-002-04: 11-step manual verification checklist from story §2.2 + `npm run build` type-checks clean. (Tests from STORY-002-03 still pass.)
- **Cookie `samesite="lax"`** (deliberate): diverges from new_app's `strict` so EPIC-005/006 OAuth redirects don't drop the cookie. Record this in FLASHCARDS.md if not already there after STORY-002-02 merges.
- **Dev/test database**: `backend/tests/test_auth_routes.py` runs against the live self-hosted Supabase. Use `test+{uuid4}@teemo.test` emails and teardown fixtures. Verify `.env` points at the dev instance before running. DO NOT run the suite against prod.
- **No new dependencies** without Team Lead approval (beyond vitest in STORY-002-03 which is explicit in the spec).

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Sprint context created at Sprint S-02 Step 0 setup | Team Lead |
| 2026-04-11 | Added Worktree Execution Notes (venv path + `.env` symlink) after STORY-002-01 Red-phase friction | Team Lead |
