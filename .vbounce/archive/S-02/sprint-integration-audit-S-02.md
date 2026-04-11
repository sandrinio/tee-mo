---
sprint_id: "S-02"
agent: "architect"
phase: "integration-audit"
started_at: "2026-04-11T12:00:12Z"
completed_at: "2026-04-11T12:02:43Z"
branch: "sprint/S-02"
stories_audited:
  - "STORY-002-01-security_primitives"
  - "STORY-002-02-auth_routes"
  - "STORY-002-03-auth_store"
  - "STORY-002-04-login_register_pages"
backend_tests_passed: 22
frontend_tests_passed: 10
frontend_build: "exit 0"
issues_found: 0
severity_high: 0
severity_medium: 0
severity_low: 0
input_tokens: 0
output_tokens: 0
total_tokens: 0
---

# Sprint S-02 Integration Audit

## Summary

Sprint S-02 delivered a complete email+password auth vertical slice (backend primitives,
routes, frontend store, pages) across 4 Fast Track stories. All 4 stories merged cleanly
into `sprint/S-02` with no symbol collisions, no duplicate infrastructure, and strict
ADR-001 / ADR-014 / ADR-017 / ADR-022 compliance. Backend (22/22) and frontend (10/10)
test suites green; `npm run build` exits 0. The 5 known-debt items (PyJWT module-state
leak, vitest hoisting TDZ workaround, router/tsc chicken-and-egg, S-01 scaffold patches,
mid-sprint .env DEBUG addition) are acknowledged and carried into the next sprint
backlog — none block release. **Verdict: SHIP.**

## What was audited

| # | Area | Result |
|---|------|--------|
| 1 | Duplicate routes / stores / queryClient | PASS — single `APIRouter(prefix="/api/auth")`, single `create<AuthState>()`, single `new QueryClient()` |
| 2 | Import graph sanity (lazy dynamic import) | PASS — dynamic `import('../main')` resolves to the same ESM singleton; no runtime double-instantiation |
| 3 | ADR compliance (sprint-level) | PASS — ADR-001, ADR-014, ADR-017, ADR-022 all verified |
| 4 | Strip-list grep (all 11 forbidden tokens) | PASS — only docstring references remain |
| 5 | Cookie attribute consistency | PASS — `samesite=lax`, access path `/`, refresh path `/api/auth`, set/clear paths match |
| 6 | Test suite harmony (22 + 10 + build) | PASS — 22 backend, 10 frontend, build exit 0 |
| 7 | Route tree sanity (`/`, `/app`, `/login`, `/register`) | PASS — all 4 present in `routeTree.gen.ts` |
| 8 | Known accepted debt surfaced | PASS — acknowledged below |

## Findings

No findings. The four stories compose cleanly at the integration level.

Detailed verification notes (supporting the "no findings" verdict):

- **Single auth router.** Only `backend/app/api/routes/auth.py` constructs an `APIRouter` with
  `prefix="/api/auth"`; `main.py` calls `app.include_router(auth_router)` exactly once. No
  duplicate route registration possible.
- **Single Zustand store.** Only `frontend/src/stores/authStore.ts` calls `create<AuthState>()`.
  Only one `zustand` import in the entire `src/` tree. ADR-014 honored.
- **Single queryClient.** `new QueryClient()` appears exactly once (`frontend/src/main.tsx:30`).
  The lazy `async function getQueryClient()` in `authStore.ts` resolves the same ESM module
  instance — not a second construction. The Vite `[INEFFECTIVE_DYNAMIC_IMPORT]` warning is
  a bundler chunking notice, not a runtime bug.
- **bcrypt guard at the boundary (ADR-017).** `auth.py::register` calls `validate_password_length`
  on line 106 BEFORE `hash_password` on line 129. Mirrored client-side in `register.tsx`
  lines 60–64 (UTF-8 byte count, 72-byte ceiling, identical error semantics).
- **JWT expiry fields flow end-to-end (ADR-001).** `config.py` pins `access_token_expire_minutes=15`
  and `refresh_token_expire_days=7`; `security.py::create_access_token` / `create_refresh_token`
  read those fields; `auth.py::_set_auth_cookies` uses them for `max_age`. No magic numbers.
- **Cookie paths match on set and clear.** `_set_auth_cookies` sets access_token with `path="/"`
  and refresh_token with `path="/api/auth"`. `_clear_auth_cookies` deletes both with the same
  paths — browsers will honor the clear. `/refresh` re-sets only access_token with `path="/"`
  (matching the original). `/logout` clears both. Fully consistent.
- **CORS allows credentials.** `main.py` sets `allow_credentials=True` and
  `frontend/src/lib/api.ts` uses `credentials: 'include'` on every fetch. Cookie round-trip
  is wired correctly.
- **No new design-system tokens or UI deps.** `git diff main...sprint/S-02` on
  `frontend/src/app.css` and `frontend/src/components/ui/` is empty. ADR-022 honored. The
  sprint adds exactly 3 auth components (`AuthInitializer`, `ProtectedRoute`, `SignOutButton`)
  that consume existing `Button` / `Card` primitives.
- **FLASHCARDS constraints honored.** The bcrypt 72-byte flashcard (2026-04-11) and the
  `samesite="lax"` deviation flashcard (2026-04-11) both match the implementation exactly.

## Known accepted debt

These items are intentionally carried forward. Each was already documented in at least one
Dev report and/or flashcard and is accepted by the Team Lead.

1. **PyJWT module-level options leak — test ordering matters.** Running `test_security.py`
   before `test_auth_routes.py` poisons a module-global in PyJWT and flips an expiry-related
   assertion. `-p no:randomly` alone is insufficient; explicit ordering
   (`test_auth_routes.py tests/test_security.py`) is required. A BUG report is queued to
   either (a) file an upstream PyJWT issue or (b) add a session-scoped reset fixture. This
   is test-harness friction only — production code is unaffected.

2. **Vitest 2.x `vi.mock` hoisting TDZ — lazy dynamic import workaround.** Vitest hoists
   `vi.mock('../../main', ...)` above any module-level `clearMock = vi.fn()` initializer,
   producing a TDZ error if `authStore.ts` statically imports `queryClient` from `../main`.
   `authStore.ts` uses a lazy `async function getQueryClient()` so the mock factory resolves
   after `clearMock` is initialized. Vite emits a cosmetic `[INEFFECTIVE_DYNAMIC_IMPORT]`
   warning at build time (expected, harmless — the module is statically reachable from
   `index.html` via `main.tsx`, so Vite keeps it in the main chunk anyway). Accepted.

3. **TanStack Router + `tsc -b && vite build` chicken-and-egg.** On the very first build
   after adding a new route file, `tsc` runs before the Vite plugin regenerates
   `routeTree.gen.ts`, so `tsc` fails on stale type exports. Workaround: run `vite build`
   once (which regenerates the file), then the normal `npm run build` succeeds. Current
   sprint build is green because `routeTree.gen.ts` is committed with `/app`, `/login`,
   `/register` already wired.

4. **S-01 scaffold gaps patched mid-sprint (STORY-002-03).** The developer added
   `frontend/src/vite-env.d.ts` and enabled `skipLibCheck: true` in
   `frontend/tsconfig.node.json` to unblock the test runner on Node types. These are small
   hygiene patches to the S-01 scaffold and don't introduce new surface area; the
   corresponding Dev report documents both.

5. **`.env DEBUG=true` added mid-sprint (not in STORY-002-03 §3.0 prereq).** Required to
   get `is_secure = not settings.debug` evaluating `False` during local dev so cookies
   don't get `Secure` on http://localhost. The story spec didn't flag this in advance;
   it was added as a developer workaround. Retroactive prereq capture suggested for the
   sprint retrospective.

## Test results

### Backend — `pytest tests/test_auth_routes.py tests/test_security.py -v`

```
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0
configfile: pyproject.toml
collecting ... collected 22 items

tests/test_auth_routes.py::test_register_happy_path PASSED               [  4%]
tests/test_auth_routes.py::test_register_73_byte_password PASSED         [  9%]
tests/test_auth_routes.py::test_register_duplicate_email PASSED          [ 13%]
tests/test_auth_routes.py::test_register_malformed_email PASSED          [ 18%]
tests/test_auth_routes.py::test_login_happy_path PASSED                  [ 22%]
tests/test_auth_routes.py::test_login_wrong_password PASSED              [ 27%]
tests/test_auth_routes.py::test_login_unknown_email PASSED               [ 31%]
tests/test_auth_routes.py::test_me_with_valid_access_cookie PASSED       [ 36%]
tests/test_auth_routes.py::test_me_without_cookie PASSED                 [ 40%]
tests/test_auth_routes.py::test_me_with_expired_access_cookie PASSED     [ 45%]
tests/test_auth_routes.py::test_refresh_happy_path PASSED                [ 50%]
tests/test_auth_routes.py::test_refresh_with_access_token_in_refresh_slot PASSED [ 54%]
tests/test_auth_routes.py::test_logout_clears_cookies PASSED             [ 59%]
tests/test_security.py::test_hash_and_verify_roundtrip PASSED            [ 63%]
tests/test_security.py::test_hash_password_is_salted PASSED              [ 68%]
tests/test_security.py::test_access_token_has_15_minute_expiry PASSED    [ 72%]
tests/test_security.py::test_refresh_token_has_7_day_expiry_and_type_claim PASSED [ 77%]
tests/test_security.py::test_decode_token_rejects_expired_token PASSED   [ 81%]
tests/test_security.py::test_decode_token_rejects_tampered_signature PASSED [ 86%]
tests/test_security.py::test_validate_password_length_rejects_73_bytes PASSED [ 90%]
tests/test_security.py::test_validate_password_length_accepts_72_bytes PASSED [ 95%]
tests/test_security.py::test_validate_password_length_counts_utf8_bytes PASSED [100%]

======================== 22 passed, 2 warnings in 8.11s ========================
```

2 Supabase client `DeprecationWarning`s (`timeout` / `verify` parameters) — upstream
library issue, non-actionable.

### Frontend — `npm test`

```
> tee-mo-frontend@0.0.1 test
> vitest run

 RUN  v2.1.9 /Users/ssuladze/Documents/Dev/SlaXadeL/frontend

 ✓ src/stores/__tests__/authStore.test.ts (10 tests) 6ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
   Duration  545ms
```

### Frontend — `npm run build`

```
> tee-mo-frontend@0.0.1 build
> tsc -b && vite build

vite v8.0.8 building client environment for production...
✓ 163 modules transformed.
...
dist/assets/index-C0F_2HxH.css    34.26 kB │ gzip: 12.59 kB
dist/assets/index-Kd16qvx5.js    321.20 kB │ gzip: 99.79 kB

[INEFFECTIVE_DYNAMIC_IMPORT] Warning: src/main.tsx is dynamically imported by
  src/stores/authStore.ts but also statically imported by index.html, dynamic
  import will not move module into another chunk.

✓ built in 170ms
EXIT=0
```

Cosmetic warning only (see accepted debt §2). Exit code 0.

## Strip audit results

```
backend/app/api/routes/auth.py:11:  - Removed: _signup_allowed_for_email invite gate
backend/app/api/routes/auth.py:12:  - Removed: check_user_cap license enforcement
backend/app/api/routes/auth.py:13:  - Removed: link_pending_invites RPC
backend/app/api/routes/auth.py:14:  - Removed: _maybe_promote_admin
backend/app/api/routes/auth.py:16:  - Table renamed: chy_users → teemo_users
backend/app/models/user.py:7:created_at, updated_at) — no full_name, no avatar_url, no auth_provider,
frontend/src/lib/api.ts:18: * Does NOT include avatar_url or auth_provider — those fields
```

All 7 hits are docstring-only (they document what was stripped for future
copy-then-optimize audits). Zero live-code hits across all 11 forbidden tokens
(`chy_`, `_signup_allowed_for_email`, `check_user_cap`, `_maybe_promote_admin`,
`link_pending_invites`, `setRealtimeAuth`, `loginWithGoogle`, `google`, `full_name`,
`avatar_url`, `is_instance_admin`) in the 9 audited files. The strip from `new_app`
is clean.

## Verdict

**SHIP.**
