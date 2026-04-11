# Flashcards

Project-specific lessons recorded after each story merge. Read this before writing code.

---

## Framework & Process

### [2026-04-11] Sprint context must be derived from the Charter, never guessed
**Seen in:** S-01, mid-sprint (corrupted STORY-001-03 dev prompt)
**What happened:** Team Lead authored `.vbounce/sprint-context-S-01.md` with locked-dependency versions from memory rather than copying them verbatim from Charter §3.2. The Dev agent on STORY-001-03 trusted the sprint context over the story spec and pinned `vite@5.x` when the real pin is `vite@^8.0.8`, forcing a bounce.
**Rule:** Every "Locked Dependencies" row in `sprint-context-S-{XX}.md` must quote Charter §3.2 verbatim, with the row's "Reason" cell naming the Charter section. If the Charter doesn't list a package, the context file doesn't either.
**How to apply:** When creating any future sprint context file, open Charter §3.2 side-by-side and copy/paste the rows. Do NOT work from memory. Do NOT summarize or "simplify" the Charter's version constraints.

---

## Tailwind 4

### [2026-04-11] Do not redefine Tailwind 4's built-in slate/neutral tokens in `@theme`
**Seen in:** STORY-001-03
**What happened:** The `@theme` block in `frontend/src/app.css` only needs the custom tokens (brand coral, semantic success/warning/danger/info, font aliases). Tailwind 4 ships full slate/zinc/stone/gray/neutral palettes by default — redefining them produces "duplicate CSS variable" warnings and doesn't change output.
**Rule:** `@theme` declares **custom** design tokens only. Built-ins (slate, zinc, red, blue, etc.) come free.
**How to apply:** When wiring a Tailwind 4 `@theme` block, list only (a) brand colors, (b) semantic aliases, (c) custom fonts/spacing/shadows that aren't already in Tailwind 4 defaults. If a token maps 1:1 onto a built-in, omit it.

---

## Frontend Data Fetching

### [2026-04-11] All frontend fetches go through TanStack Query — `QueryClientProvider` is already mounted
**Seen in:** STORY-001-04
**What happened:** Sprint 1 established the frontend data-fetching pattern. `frontend/src/main.tsx` mounts a `QueryClient` + `QueryClientProvider` at the app root, and `frontend/src/lib/api.ts` exposes typed fetch wrappers (`getHealth()`, etc.). The landing route uses `useQuery` against `getHealth`, not raw `fetch` or a bespoke hook.
**Rule:** Every new frontend data fetch must use `useQuery` / `useMutation` from `@tanstack/react-query`, calling a typed function in `frontend/src/lib/api.ts`. Never call `fetch` directly from a component. Never instantiate a second `QueryClient`.
**How to apply:** When adding a new API endpoint, add a typed wrapper to `frontend/src/lib/api.ts` first, then consume it via `useQuery(['queryKey'], apiFn)` in the component. For POSTs, add a `useMutation` hook. The `VITE_API_BASE_URL` env var (defaults to `http://localhost:8000`) is the base.

---

## Backend Health Contract

### [2026-04-11] `/api/health` returns `status: ok|degraded` + per-table `database.teemo_*` breakdown
**Seen in:** STORY-001-01 + STORY-001-02 (extended)
**What happened:** The backend health contract is now `{"status": "ok" | "degraded", "service": "tee-mo", "database": {"teemo_users": "ok", "teemo_workspaces": "ok", "teemo_knowledge_index": "ok", "teemo_skills": "ok"}}`. `status` aggregates to `"degraded"` if any table query fails. Tables are queried via a cached `@lru_cache`-wrapped Supabase client (service role key, NOT anon).
**Rule:** Do not instantiate `create_client()` ad-hoc inside routes. Always go through `backend/app/core/db.get_supabase()`. When adding new tables, update the `TEEMO_TABLES` tuple in `backend/app/main.py` so the smoke check covers them.
**How to apply:** New Supabase-touching code imports `from app.core.db import get_supabase`. New tables get added to `TEEMO_TABLES` in the same commit that creates the migration. The frontend types `HealthResponse.database` as `Record<string, string> | undefined` — keep it optional for forward compatibility.

---

## bcrypt 5.0

### [2026-04-11] bcrypt 5.0 raises ValueError on passwords > 72 bytes — validate at the boundary
**Seen in:** Charter §3.2 pin, flagged by Roadmap §5, relevant from STORY-001-01 onward
**What happened:** Charter pins `bcrypt==5.0.0`. Unlike bcrypt 4.x (which silently truncated), 5.0 raises `ValueError` on passwords longer than 72 bytes. An unvalidated `/api/auth/register` will 500 instead of 422.
**Rule:** The first auth story MUST add a `len(password.encode("utf-8")) <= 72` check at the `POST /api/auth/register` handler, returning HTTP 422 with a clear message when exceeded.
**How to apply:** When Story 001-01 grows into an auth story (Sprint 2+), wire this validator into the Pydantic request model or the route handler before the bcrypt hash call. Add a Gherkin scenario to the acceptance criteria: "Given a 73-byte password, when I POST /api/auth/register, then I get 422 with `password_too_long`."

---

## Auth Cookies

### [2026-04-11] Tee-Mo auth cookies use `samesite="lax"`, NOT `strict` — deliberate deviation from new_app
**Seen in:** STORY-002-02 (auth routes)
**What happened:** new_app ships `_set_auth_cookies` with `samesite="strict"`. Tee-Mo deliberately uses `lax` because EPIC-005 (Slack install callback) and EPIC-006 (Google Drive consent) both redirect back to the frontend after a third-party OAuth flow, and browsers drop Strict cookies on cross-site redirects. Lax still blocks CSRF on the Tee-Mo auth endpoints because they all accept JSON bodies, not form posts — so the `Content-Type: application/json` header requirement (which cross-site forms can't set) gives us the protection Strict would.
**Rule:** Keep `samesite="lax"` in `backend/app/api/routes/auth.py::_set_auth_cookies` and `_clear_auth_cookies`. Do not switch to `strict` without first auditing EPIC-005 and EPIC-006 OAuth redirect flows for breakage.
**How to apply:** When editing the cookie helpers, leave `samesite="lax"` in place. If a future security review pushes for Strict, either (a) confirm all third-party OAuth redirects are gone from the codebase and then upgrade, or (b) split into two cookie sets — one Strict for same-origin endpoints, one Lax scoped to `/api/auth` and `/api/slack/oauth` for redirect flows. Document the decision in a new ADR before changing code.

---

## Pydantic + email-validator

### [2026-04-11] Pydantic `EmailStr` rejects `.test` TLD fixture addresses — use `LaxEmailStr` or `@example.com`
**Seen in:** STORY-002-02 Green phase
**What happened:** Test fixtures used `test+{uuid4}@teemo.test` addresses so they'd never collide with real users. Pydantic `EmailStr` rejected them with `"The domain name teemo.test is a special-use or reserved name that cannot be used with email."`. This is `email-validator` 2.x's `globally_deliverable=True` check, which fires even when `check_deliverability=False` — the two flags are independent. Pydantic's built-in `EmailStr` has no way to set `test_environment=True`, so a custom annotated type is required.
**Rule:** When a Pydantic model accepting email input will be exercised by integration tests, either (a) use `backend/app/models/user.py::LaxEmailStr` (which calls `email_validator.validate_email(v, check_deliverability=False, test_environment=True)` and accepts `.test` / `.localhost` / `.invalid` / `.example` TLDs) or (b) switch test fixtures to `@example.com` and keep plain `EmailStr` in the model.
**How to apply:** New request models for `/api/*` endpoints that land in tests — import `LaxEmailStr` from `app.models.user` rather than `EmailStr` from `pydantic`. Response models can use plain `str` for the email field (the data is already validated on write). If you're adding an endpoint with NO integration tests against `.test` addresses, `EmailStr` is fine.
