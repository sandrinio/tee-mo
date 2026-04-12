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

---

## Vitest

### [2026-04-11] Vitest 2.x `vi.mock` hoisting TDZ — use `vi.hoisted(...)` for mock variables
**Seen in:** STORY-002-03 Green phase
**What happened:** The Red test file used `const clearMock = vi.fn()` followed by `vi.mock('../../main', () => ({ queryClient: { clear: clearMock } }))`. Vitest 2.x AST-hoists the `vi.mock(...)` call above the `const clearMock = ...` declaration, so when the mock factory runs, `clearMock` is in TDZ and throws `ReferenceError: Cannot access 'clearMock' before initialization` — every test fails at collection time.
**Rule:** When a `vi.mock` factory closes over a variable defined in the test file, wrap that variable's initializer in `vi.hoisted(...)`:
```ts
const { clearMock } = vi.hoisted(() => ({ clearMock: vi.fn() }));
vi.mock('../../main', () => ({ queryClient: { clear: clearMock } }));
```
**How to apply:** Any Vitest 2.x test that needs a spy inside a `vi.mock` factory MUST use `vi.hoisted`. If the test file is already written and immutable (e.g., V-Bounce Red phase tests), the workaround is a lazy dynamic `import('../main')` in the module under test so the factory resolves after the spy is initialized. That workaround is production-safe but emits a cosmetic Vite `[INEFFECTIVE_DYNAMIC_IMPORT]` warning at build time. Prefer the `vi.hoisted` fix whenever the test is still mutable.

---

## TanStack Router + Vite

### [2026-04-11] `tsc -b && vite build` chicken-and-egg when adding new routes
**Seen in:** STORY-002-04 single-pass
**What happened:** The frontend scaffold's `"build": "tsc -b && vite build"` runs TypeScript compilation BEFORE Vite gets to regenerate `src/routeTree.gen.ts`. When a new route file is added (`src/routes/foo.tsx`), the first `npm run build` after the addition fails in `tsc` because the generated tree hasn't been updated to export the new route yet — tsc sees stale imports.
**Rule:** After creating new files in `frontend/src/routes/`, run `node_modules/.bin/vite build` (or `npm run dev` briefly) FIRST to let the TanStackRouterVite plugin regenerate `routeTree.gen.ts`. Then run the normal `npm run build` — it will succeed. Subsequent builds after the regeneration work normally.
**How to apply:** When a story adds `src/routes/*.tsx` files, the Developer agent should run the vite-first build once, confirm `routeTree.gen.ts` now includes the new route, and only then run the full `tsc -b && vite build` gate. Do NOT hand-edit `routeTree.gen.ts`. A cleaner long-term fix (candidate for `/improve`) is to reorder the build script to `"build": "vite build && tsc --noEmit"` or add a `"pretsr": "tsr generate"` step — both depend on confirming the plugin writes the file synchronously enough for the tsc pass to pick it up.

---

## FastAPI + Starlette serving an SPA

### [2026-04-12] Starlette 1.0.0 `StaticFiles(html=True)` is NOT a SPA fallback — use an explicit catch-all route
**Seen in:** STORY-003-01 (Dockerfile + same-origin static serving)
**What happened:** The S-03 story spec claimed `app.mount("/", StaticFiles(directory=..., html=True))` would serve `index.html` for any unmatched SPA path like `/login`, `/register`, `/app`. It doesn't. In Starlette 1.0.0, `html=True` only serves `index.html` when the request path is a directory (e.g. trailing slash) and serves `404.html` for missing files — it does NOT serve `index.html` as a generic fallback for unmatched paths. TanStack Router client-side routes like `/login` returned 404 instead of the SPA shell.
**Rule:** When serving a Vite/React SPA from FastAPI at same-origin, mount `StaticFiles` at `/assets` (or wherever Vite writes the hashed bundle directory) AND add an explicit catch-all route `@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])` that returns `FileResponse(static_dir / "index.html")` for any path that doesn't match an earlier route. Order matters: API routes first, `/assets` StaticFiles mount second, catch-all route last.
**How to apply:** When adding a new frontend shell to FastAPI, use the pattern from `backend/app/main.py`. If you see `StaticFiles(html=True)` proposed as an SPA fallback in any spec, flag it as wrong and replace with the explicit catch-all pattern.

### [2026-04-12] Starlette 1.0.0 `@app.get(...)` does NOT auto-handle HEAD requests
**Seen in:** STORY-003-01 (Coolify healthcheck compatibility)
**What happened:** Coolify's healthcheck does `HEAD /api/health`. `curl -sI` (for curl sanity checks) also uses HEAD. STORY-003-01 found that `@app.get("/api/health")` returns 405 Method Not Allowed on HEAD in Starlette 1.0.0 — the `@app.get` decorator registers the route for GET only. Flask auto-handles HEAD for GET routes; Starlette doesn't.
**Rule:** Any endpoint that will be hit by a reverse-proxy healthcheck, a curl `-I` sanity check, a Coolify/Kubernetes liveness probe, or any caller issuing HEAD must be registered with `@app.api_route(..., methods=["GET", "HEAD"])`. Do not rely on `@app.get` or `@router.get` to handle HEAD.
**How to apply:** New backend health/liveness/readiness/metrics endpoints must use `api_route` with both methods. Review existing `@app.get` / `@router.get` routes when adding a new healthcheck target. Also applies to the SPA catch-all route (see the previous flashcard).

---

## Post-release verification + live-schema validation

### [2026-04-12] `supabase.table(t).select("id").limit(0)` fails on tables without an `id` column
**Seen in:** STORY-003-03 / S-03 post-release hotfix (commit `ce7c0b1`)
**What happened:** The health-check probe `_check_table()` in `backend/app/main.py` used `supabase.table(t).select("id").limit(0).execute()` to confirm each `teemo_*` table existed and was reachable. PostgREST validates that the `id` column exists in the table's schema BEFORE executing the query, even with `LIMIT 0`. The two new ADR-024 tables (`teemo_slack_teams` with `slack_team_id` PK, `teemo_workspace_channels` with `slack_channel_id` PK) intentionally have NO `id` column, so PostgREST raised `column teemo_slack_teams.id does not exist (42703)` for both tables. The health endpoint reported `status: "degraded"` despite the tables being healthy and reachable. STORY-003-03's test suite is hermetic (mocked Supabase client), so the real-schema mismatch never surfaced — only the first live `/api/health` request against the production schema exposed it. Fixed by commit `ce7c0b1` as a post-release hotfix.
**Rule:** Column-agnostic existence probes must use `select("*").limit(0)` or a HEAD-style request via `select("*", count="exact").limit(0)`. Never hard-code a column name (like `id`) in a smoke check that iterates over a heterogeneous set of tables — not all Tee-Mo tables have the same primary key shape.
**How to apply:** Any backend health/smoke/probe code that iterates `TEEMO_TABLES` (or any list of tables) must use `select("*")`, not `select("id")`. Hermetic tests don't catch this — they mock the client and don't exercise PostgREST's column validation. Consider adding a live smoke test in production verification that hits the actual schema, not just hermetic unit tests. This bug is also a process signal: whenever a story adds tables with a non-`id` primary key, grep the codebase for `select("id")` and audit for assumption-of-id-column mistakes.

---

## V-Bounce Agent Discipline

### [2026-04-12] Agent Edit/Write with absolute paths bypass worktree isolation
**Seen in:** STORY-003-04 (Dev agent editing BUG-20260411 report)
**What happened:** The Developer agent for STORY-003-04 was given a worktree at `.worktrees/STORY-003-04-pyjwt-fix/`. It used an absolute path (`/Users/ssuladze/Documents/Dev/SlaXadeL/product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md`) for the BUG report edit instead of a worktree-relative path. Absolute paths resolve to the MAIN repo working directory, which was on `sprint/S-03` at the time — not the story worktree's `story/STORY-003-04-pyjwt-fix` branch. Result: the BUG report edit landed on `sprint/S-03`'s working tree and did NOT get included in the story branch's commit. Required a separate chore commit on `sprint/S-03` to capture the edit post-merge.
**Rule:** Inside a V-Bounce story worktree, every Edit/Write tool call MUST use paths relative to the worktree root. Absolute paths bypass the worktree branch isolation and land on whatever branch is checked out in the main repo.
**How to apply:** Task files spawned for story work must include an explicit instruction near the top: "Use worktree-relative paths for ALL edits. NEVER use absolute paths starting with `/Users/ssuladze/...`. Absolute paths skip the worktree and land on the main repo's checked-out branch, breaking story-branch isolation." Team Lead should spot-check the first few Edit/Write tool calls per story to confirm relative-path discipline, especially when stories edit files outside `backend/` or `frontend/` (e.g., `product_plans/`, `FLASHCARDS.md`, `.vbounce/`).

---

## Slack OAuth (S-04)

### [2026-04-12] `httpx.AsyncClient` first use — `import httpx` at module level so tests can monkeypatch
**Seen in:** STORY-005A-04 (Slack OAuth callback)
**What happened:** S-04 introduced the codebase's first first-party outbound HTTP via `httpx.AsyncClient` in `backend/app/api/routes/slack_oauth.py`. The Red Phase tests mock it via `monkeypatch.setattr(slack_oauth_module.httpx, "AsyncClient", FakeAsyncClient)`, which only works if `httpx` is imported at the module level — NOT inside the handler body. An earlier draft tried `import httpx` inside the async function and all 10 tests ERROR'd at fixture setup with `AttributeError: module 'app.api.routes.slack_oauth' has no attribute 'httpx'`.
**Rule:** When a route file needs outbound HTTP, `import httpx` at the top of the module, never inside a function. This applies to any future story that calls Slack/Google/Anthropic/etc from a backend route until `app/core/http.py` is extracted.
**How to apply:** In tests, use `monkeypatch.setattr(module.httpx, "AsyncClient", FakeAsyncClient)` with a hand-rolled `FakeAsyncClient` that implements `__aenter__`/`__aexit__`/`post`. The canonical `FakeResponse` shape is in `backend/tests/test_slack_oauth_callback.py`. When `app/core/http.py` is extracted (on the 2nd httpx use-case), migrate tests to `Depends(get_http_client)` injection and this flashcard can be retired.

---

### [2026-04-12] Supabase `.upsert()` — omit `DEFAULT NOW()` columns from the payload
**Seen in:** STORY-005A-04 (Slack OAuth callback)
**What happened:** The `teemo_slack_teams` table has `installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`. A naive upsert dict that passes `installed_at` (even as `None` or the current time) would reset the column on every re-install, losing the original install timestamp. PostgREST's `Prefer: resolution=merge-duplicates` header (what supabase-py's `.upsert()` translates to) writes every field that appears in the payload, including fields with `DEFAULT` clauses. Passing nothing means the column keeps its existing value on update and the default on insert — exactly what we want.
**Rule:** When upserting a row that has `DEFAULT NOW()` (or any other DB-side default) columns you want preserved across re-writes, **omit those columns from the payload dict entirely**. Do NOT pass them as `None`; do NOT pass `datetime.utcnow()`. Just leave them out.
**How to apply:** Applies to every ADR-024 table (`teemo_slack_teams.installed_at`, `teemo_workspace_channels.bound_at`, future `teemo_workspaces.created_at`). Rule of thumb: if a migration has `DEFAULT NOW()` on a column, the corresponding Python upsert dict does not reference that column at all.

---

### [2026-04-12] `base64.urlsafe_b64decode` needs padding for bare base64url from `.env`
**Seen in:** STORY-005A-01 (Slack bootstrap)
**What happened:** `TEEMO_ENCRYPTION_KEY` is generated via `secrets.token_urlsafe(32)` which emits an unpadded 43-char base64url string. `base64.urlsafe_b64decode` raises `binascii.Error: Invalid base64-encoded string` on unpadded input. Both the `config.py` Settings validator and `encryption.py::_key()` had to apply padding before decode. Missed on the first Green Phase pass; caught by the short-key validator test.
**Rule:** Any base64url string read from `.env` (encryption keys, tokens, nonces) must be padded before decoding: `padded = raw + "=" * (-len(raw) % 4)` then `base64.urlsafe_b64decode(padded)`.
**How to apply:** Wrap every base64url decode call site with the padding snippet, even if you think the source "should" already be padded. `secrets.token_urlsafe()` never emits padding. External tools vary. Defensive padding is free.

---

### [2026-04-12] `slack_bolt.AsyncApp` uses `request_verification_enabled`, NOT `token_verification_enabled`
**Seen in:** STORY-005A-01 (Slack bootstrap)
**What happened:** The story spec §3.3 skeleton passed `token_verification_enabled=False` to `AsyncApp(...)`. This parameter does not exist in `slack-bolt 1.28.x` — the constructor rejected it. The correct parameter for request-signing control is `request_verification_enabled`. The story spec template was copied from stale AI-generated docs.
**Rule:** When constructing `slack_bolt.async_app.AsyncApp`, the parameter names that actually exist in 1.28.x are: `token`, `signing_secret`, `request_verification_enabled`, `installation_store`, `oauth_settings`, and a few others — NOT `token_verification_enabled`.
**How to apply:** For `get_slack_app()` in `backend/app/core/slack.py`, use `AsyncApp(token=None, signing_secret=s.slack_signing_secret, request_verification_enabled=True)`. Sprint plans that reference the `AsyncApp` constructor must use the correct parameter name. When the slack-bolt version is bumped, verify the constructor signature hasn't changed in the upgrade notes.

---

### [2026-04-12] `/api/slack/events` 400 body changed from JSON detail to bare Response
**Seen in:** STORY-005A-02 (events signing verification)
**What happened:** The S-03 stub returned `JSONResponse({"detail":"invalid_json"}, status_code=400)` on malformed JSON. The S-04 hardened handler parses the JSON AFTER the signature guard and returns a bare `Response(status_code=400)` with no body when parsing fails. Any client that was grepping for the `"invalid_json"` detail string will silently break. The stub's 3 tests had to be updated to assert `status_code == 400` only (not the body shape).
**Rule:** Document Slack-webhook-facing error shapes in the vdoc when that endpoint gets documentation. Don't rely on response body shapes for Slack-facing endpoints unless you control the consumer — Slack doesn't inspect the body, it only cares about the status code.
**How to apply:** If you need diagnostic detail on malformed POSTs to Slack endpoints, add a structured log line (fields not body) so ops can trace it without exposing anything to the public-facing response.

---

## Frontend Test Infrastructure (S-04)

### [2026-04-12] `vitest@2.1.9 + vite@8` — separate `vitest.config.ts` avoids `ProxyOptions` TypeScript conflict
**Seen in:** STORY-005A-06 (frontend install UI)
**What happened:** Added an inline `test:` block to `frontend/vite.config.ts` to configure Vitest. TypeScript flagged a `ProxyOptions` type incompatibility because `vitest@2.1.9` declares its peer dependency as `vite@5.x`, while this project runs `vite@8.0.8`. The two versions export overlapping but incompatible type shapes for proxy config. Inlining vitest config in `vite.config.ts` made the conflict unavoidable.
**Rule:** When `vitest` and `vite` major versions don't match peer deps, keep Vitest config in a **separate `vitest.config.ts` file** that imports from `vitest/config` instead of `vite`. Exclude `vitest.config.ts` from `tsconfig.node.json` if necessary.
**How to apply:** `frontend/vitest.config.ts` should `import { defineConfig } from 'vitest/config'` (NOT `from 'vite'`). All test-environment config (`test: { environment: 'jsdom', globals: true, setupFiles: [...] }`) lives in that file. `vite.config.ts` stays vite-only. When bumping either package, verify the peer range — if they align again (e.g. vitest@3 peers with vite@8), the files can be re-merged.

---

### [2026-04-12] `@testing-library/react` auto-cleanup requires `globals: true` in vitest config
**Seen in:** STORY-005A-06 (frontend install UI)
**What happened:** Without `globals: true` in `vitest.config.ts`, `@testing-library/react` silently skips its auto-cleanup hook. The library registers `afterEach(cleanup)` only if `typeof afterEach === 'function'` at load time — which requires the vitest globals injected into the test environment. Without it, every `render()` call leaks DOM nodes into the next test, producing false positives and cross-test pollution (one `screen.findByText('X')` matching content from a previous test's DOM).
**Rule:** Any Vitest project using `@testing-library/react` MUST set `globals: true` in `vitest.config.ts`. If you prefer explicit imports, manually add `import { cleanup } from '@testing-library/react'; afterEach(() => cleanup())` to the test setup file — but `globals: true` is the simpler fix.
**How to apply:** In `frontend/vitest.config.ts`, set `test.globals: true`. The accompanying `frontend/src/test-setup.ts` file imports `@testing-library/jest-dom` to register the matchers (`toBeInTheDocument`, etc.). Both files shipped with STORY-005A-06 — reference them when setting up a new component test file in a different frontend package.

---

## Worktree Environment (S-05)

### [2026-04-12] Worktree `.env` resolves from `parents[3]` of config.py — copy `.env` to worktree root
**Seen in:** STORY-003-B03 (integration tests in worktree)
**What happened:** `pydantic-settings` in `backend/app/core/config.py` resolves the `.env` file using `Path(__file__).resolve().parents[3]`, which in the main repo points to the project root. Inside a worktree at `.worktrees/STORY-003-B03/`, `parents[3]` resolves to `.worktrees/STORY-003-B03/` — not the main repo root. Tests failed with missing env vars because no `.env` existed at the worktree root.
**Rule:** Before running backend tests in a worktree, copy (or symlink) the project root `.env` to the worktree root directory. The `.env` is gitignored so this is safe.
**How to apply:** Add a pre-bounce step in the Team Lead's worktree setup: `cp .env .worktrees/STORY-{ID}/.env` after `git worktree add`. This applies to any story that runs backend tests.

---

## jsdom Limitations (S-05)

### [2026-04-12] jsdom does not implement `HTMLDialogElement.showModal()` — use div overlay modals
**Seen in:** STORY-003-B05 (CreateWorkspaceModal)
**What happened:** The initial implementation used a native `<dialog>` element with `showModal()`. jsdom (used by Vitest's `environment: 'jsdom'`) does not implement `HTMLDialogElement.showModal()` — calling it throws `TypeError: dialog.showModal is not a function`. All component tests that rendered the modal failed at setup.
**Rule:** Components that need modal behavior should use a div-based overlay pattern (conditional rendering + backdrop + focus trap) rather than native `<dialog>` with `showModal()`. The native `<form>` element inside the modal is fine — only the dialog API is missing.
**How to apply:** When building modals, follow the pattern in `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` (div overlay). If native `<dialog>` is strongly preferred, polyfill `showModal`/`close` in `frontend/src/test-setup.ts` before any tests run.

---

## TanStack Router (S-05)

### [2026-04-12] File-based routes with children are layout routes — parent MUST render `<Outlet>`
**Seen in:** STORY-003-B05 (app.tsx + app.teams.$teamId.tsx)
**What happened:** `app.tsx` defined the `/app` route with `component: AppPage`, rendering the Slack Teams list directly. When `app.teams.$teamId.tsx` was added as a child route, TanStack Router's route tree made `/app` the parent. Navigating to `/app/teams/$teamId` changed the URL but rendered nothing — the parent's component had no `<Outlet>` for the child to render into.
**Rule:** In TanStack Router file-based routing, any route file whose name is a prefix of another route file automatically becomes a layout route. Layout routes MUST render `<Outlet />` from `@tanstack/react-router`. Page content that was in the layout file must move to an index route (e.g., `app.tsx` → layout with `<Outlet>`, `app.index.tsx` → page content).
**How to apply:** When adding a new nested route like `foo.bar.tsx`, check whether `foo.tsx` already exists. If it does and renders page content directly, refactor: move content to `foo.index.tsx`, make `foo.tsx` a layout with `<Outlet>`. Auth wrappers like `ProtectedRoute` belong in the layout so all children inherit them.

---

## Frontend ↔ Backend Contract (S-05)

### [2026-04-12] Salvaged frontend API URLs must be verified against actual backend route paths
**Seen in:** STORY-003-B04 (frontend API hooks — salvaged from S-05-fasttrack)
**What happened:** The salvaged `api.ts` wrappers used flat URLs (`/api/workspaces?team_id=`, `POST /api/workspaces`, `PATCH /api/workspaces/{id}/default`) that didn't match the actual backend routes decided in sprint planning (`/api/slack-teams/{teamId}/workspaces`, `POST /api/workspaces/{id}/make-default`). The orphan branch was written before the route prefix was finalized. Hermetic tests (which mock the API module) passed — the mismatch only surfaced during manual QA when live requests hit 404/401.
**Rule:** When salvaging frontend code from an orphan or stale branch, cross-check every URL string in the salvaged file against the current backend route definitions. Do NOT trust that the salvaged URLs match the final API contract.
**How to apply:** In the Developer task prompt for salvage stories, include the backend API contract table (endpoint, method, path) and add an explicit instruction: "Verify every URL in the salvaged code matches this table before committing." The Team Lead should grep for URL patterns in the salvaged diff during the test pattern validation step.

---

## Google Drive Integration (S-08)

### [2026-04-13] `drive.file` scope does NOT grant refresh-token access to Picker-selected files
**Seen in:** STORY-006-06 (E2E verification)
**What happened:** The OAuth flow used `drive.file` scope (non-sensitive). The Google Picker widget correctly opened and let the user select files. But when the backend tried to read the selected file using the stored refresh token (via `drive_service.get_drive_client`), Google returned 403 `appNotAuthorizedToFile`. The `drive.file` scope grants access only to files the app created or opened — but the Picker selection is tied to the short-lived access token session, not the refresh token. The refresh token never gains access to those files.
**Rule:** If the backend needs to read arbitrary user-selected files via a stored refresh token, use `drive.readonly` scope (sensitive) instead of `drive.file` (non-sensitive). `drive.file` only works when the same access token that opened the Picker is used for the API call — it does not transfer to refresh-token-derived access tokens.
**How to apply:** When setting `DRIVE_SCOPES` in `drive_oauth.py`, use `drive.readonly`. If `drive.file` is required for compliance, the file read must happen in the same request that has the Picker's access token — pass it from the frontend and use it server-side for the initial fetch.

---

### [2026-04-13] `from __future__ import annotations` breaks FastAPI runtime type resolution
**Seen in:** STORY-006-03 (QA bounce — test collection crash on Python 3.9)
**What happened:** `drive_oauth.py` used `str | None` type hints in FastAPI endpoint signatures. To fix Python 3.9 compat, `from __future__ import annotations` was added. This turns all annotations into strings (PEP 563), but FastAPI inspects annotations at runtime to resolve dependency injection, query params, and request body types. With stringified annotations, FastAPI couldn't resolve `Optional[str]` defaults, causing 500 errors on every request.
**Rule:** Never use `from __future__ import annotations` in FastAPI route files. Use `from typing import Optional` and `Optional[str]` syntax instead for Python 3.9 compatibility.
**How to apply:** When a QA or linter flags `str | None` syntax for Python 3.9 compat, replace with `Optional[str]` from typing — do NOT add the `__future__` import. This applies to any file containing `@router.get`, `@router.post`, `@app.get`, etc.

---

### [2026-04-13] Google refresh tokens cannot be used as Bearer credentials for resource APIs
**Seen in:** STORY-006-02 (Architect bounce — `drive_status` endpoint)
**What happened:** The `drive_status` endpoint decrypted the stored refresh token and passed it directly as `Authorization: Bearer {refresh_token}` to Google's userinfo endpoint. Google returned 401. Refresh tokens are opaque to resource servers — they can only be exchanged at the token endpoint (`POST https://oauth2.googleapis.com/token` with `grant_type=refresh_token`) for a short-lived access token. The broad `except Exception` silently caught the 401 and returned `connected: false`, making the status endpoint permanently report "not connected" even with a valid refresh token.
**Rule:** Always exchange a refresh token for an access token before calling any Google resource API (userinfo, Drive, Sheets, etc.). Never use a refresh token as a Bearer credential.
**How to apply:** Any endpoint that needs to call a Google API with a stored refresh token must first POST to `https://oauth2.googleapis.com/token` with `grant_type=refresh_token`, extract the `access_token` from the response, then use that access token as the Bearer credential.

---

### [2026-04-13] Hermetic mocks hide column-name mismatches — verify against live schema
**Seen in:** STORY-006-06 (E2E verification — `owner_user_id` vs `user_id`, `provider` vs `ai_provider`)
**What happened:** The Developer agent used `owner_user_id` in Supabase `.select()` and `.eq()` calls, but the actual `teemo_workspaces` table column is `user_id`. Similarly, `provider` was used instead of `ai_provider`. All hermetic tests passed because the mock Supabase client returns whatever data is configured — it never validates column names against the real schema. The errors only surfaced on the first live request (PostgREST returned `column does not exist (42703)`).
**Rule:** When a story adds new Supabase queries, the Developer must verify column names against the actual table schema (check the migration SQL or run a live `select("*").limit(0)` probe). Do NOT trust column names from the story spec or AI-generated code without verification.
**How to apply:** Before committing any new `.select("col1, col2")` or `.eq("col", val)` call, grep the migration files for the actual column names. If unsure, run `supabase.table("teemo_X").select("*").limit(1).execute()` in a Python shell and inspect `result.data[0].keys()`.

---

### [2026-04-13] Frontend worktrees need `npm install` before `vite build`
**Seen in:** STORY-006-05 (Developer agent — worktree had no node_modules)
**What happened:** Git worktrees check out a clean copy of the repo but `node_modules/` is gitignored. The Developer agent tried to run `vite build` in the worktree and it failed because no dependencies were installed. `npm install` must be run first.
**Rule:** When creating a worktree for a frontend story, run `cd .worktrees/STORY-{ID}/frontend && npm install` before any build or test commands.
**How to apply:** Add to the Team Lead's worktree setup checklist: after `git worktree add` and `cp .env`, run `npm install` in the frontend directory if the story touches frontend code.
