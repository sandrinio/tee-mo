---
story_id: "STORY-003-01-dockerfile"
agent: "developer"
phase: "single-pass"
bounce: 1
started_at: "2026-04-11T16:00:00Z"
completed_at: "2026-04-11T20:30:00Z"
files_modified:
  - "Dockerfile"
  - ".dockerignore"
  - "backend/app/main.py"
  - "frontend/src/lib/api.ts"
  - "frontend/vite.config.ts"
tests_written: 0
tests_passing: 32
tests_failing: 0
correction_tax_pct: 5
flashcards_flagged:
  - "Starlette 1.0.0 StaticFiles(html=True) does NOT implement SPA fallback for arbitrary paths"
  - "Starlette 1.0.0 does NOT auto-handle HEAD for @app.get routes — must use api_route with methods=['GET','HEAD']"
  - "Docker on macOS via OrbStack requires --context orbstack flag (default socket path is orbstack-specific)"
input_tokens: 486
output_tokens: 11125
total_tokens: 11611
---

# Developer Implementation Report: STORY-003-01-dockerfile

## Summary

Created a multi-stage root-level `Dockerfile` (Node 22 Alpine builder + Python 3.11 slim runtime) that builds the Vite frontend and copies the output into the FastAPI container at `/app/static/`. Edited `backend/app/main.py` to mount the static assets and serve a SPA catch-all after all API routes. Changed `frontend/src/lib/api.ts` default API URL to empty string for same-origin production deploys, and added a `/api` dev proxy to `vite.config.ts` to preserve the local dev workflow.

The key implementation deviation from the spec was that the story claimed `StaticFiles(html=True)` implements SPA fallback for arbitrary paths — it does not in Starlette 1.0.0. Starlette's `html=True` only serves `index.html` for directory URLs, not for paths like `/login`. The solution uses a two-part pattern: `StaticFiles` mounted at `/assets` for actual static files, plus an explicit `@app.api_route("/{full_path:path}")` catch-all that returns `index.html`.

## Files Modified

- `Dockerfile` (NEW) — multi-stage build per §3.2 verbatim; Node 22 Alpine builds frontend, Python 3.11 slim runs FastAPI
- `.dockerignore` (NEW) — excludes `.env`, `.git`, `.worktrees`, `.vbounce`, `node_modules`, `backend/.venv`, `product_plans`, and other non-essential paths per §1.2 R2
- `backend/app/main.py` (EDIT) — added `StaticFiles`, `FileResponse`, `Path` imports; moved `@app.get("/api/health")` to `@app.api_route` with HEAD support; added SPA static serving block at end of file guarded by `_static_dir.is_dir()`
- `frontend/src/lib/api.ts` (EDIT) — changed `VITE_API_URL` fallback from `'http://localhost:8000'` to `''` (empty string = same origin) per §3.4
- `frontend/vite.config.ts` (EDIT) — added `server.proxy` for `/api` → `http://localhost:8000` per §3.5, preserving existing `port: 5173`

## Dockerfile Build Output

```
#21 [runtime 8/8] WORKDIR /app/backend
#21 DONE 0.0s

#22 exporting to image
#22 exporting layers
#22 exporting layers 1.6s done
#22 writing image sha256:e9cd9883ba07e0ea242c49fb3644140912a35f53dce15bc0a066a3641669a355 done
#22 naming to docker.io/library/teemo-test done
#22 DONE 1.7s
```

Image size: **962 MB** (see Concerns below — over 500 MB target)

## Container Curl Verification

All 7 Gherkin scenarios from §2.1 verified with container on port 8002 (port 8000 occupied by another service on the dev machine):

```
=== Scenario 2: GET /api/health ===
{
    "status": "ok",
    "service": "tee-mo",
    "version": "0.1.0",
    "database": {
        "teemo_users": "ok",
        "teemo_workspaces": "ok",
        "teemo_knowledge_index": "ok",
        "teemo_skills": "ok"
    }
}

=== Scenario 3: GET / (frontend HTML) ===
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>Tee-Mo</title>
    <script type="module" crossorigin src="/assets/index-BrifKaDH.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-BPJM0awe.css">
  </head>
  <body>
    <div id="root"></div>

=== Scenario 4: GET /login (SPA fallback) ===
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Tee-Mo</title>
    ...

=== Scenario 5a: HEAD /api/health content-type ===
HTTP/1.1 200 OK
content-type: application/json

=== Scenario 5b: HEAD / content-type ===
HTTP/1.1 200 OK
content-type: text/html; charset=utf-8

=== Scenario 7: .env not baked ===
ls: cannot access '/app/.env': No such file or directory
ok — env not baked
```

## Local Dev Verification

Scenario 6 — local uvicorn on port 8001 (to avoid collision with chyro-api-1 on 8000):

```
$ cd backend && /Users/ssuladze/.../backend/.venv/bin/python -m uvicorn app.main:app --port 8001 --log-level warning &
$ curl -s http://localhost:8001/api/health | python3 -m json.tool
{
    "status": "ok",
    "service": "tee-mo",
    "version": "0.1.0",
    "database": {
        "teemo_users": "ok",
        "teemo_workspaces": "ok",
        "teemo_knowledge_index": "ok",
        "teemo_skills": "ok"
    }
}
```

Static mount skipped — `is_dir()` returns False on host (no `/app/static` outside Docker).

## Regression Tests

**Backend pytest (22 passed):**
```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3
plugins: logfire-4.32.0, anyio-4.13.0
collected 22 items

tests/test_auth_routes.py::test_register_happy_path PASSED                [  4%]
tests/test_auth_routes.py::test_register_73_byte_password PASSED          [  9%]
tests/test_auth_routes.py::test_register_duplicate_email PASSED           [ 13%]
tests/test_auth_routes.py::test_register_malformed_email PASSED           [ 18%]
tests/test_auth_routes.py::test_login_happy_path PASSED                   [ 22%]
tests/test_auth_routes.py::test_login_wrong_password PASSED               [ 27%]
tests/test_auth_routes.py::test_login_unknown_email PASSED                [ 31%]
tests/test_auth_routes.py::test_me_with_valid_access_cookie PASSED        [ 36%]
tests/test_auth_routes.py::test_me_without_cookie PASSED                  [ 40%]
tests/test_auth_routes.py::test_me_with_expired_access_cookie PASSED      [ 45%]
tests/test_auth_routes.py::test_refresh_happy_path PASSED                 [ 50%]
tests/test_auth_routes.py::test_refresh_with_access_token_in_refresh_slot PASSED [ 54%]
tests/test_auth_routes.py::test_logout_clears_cookies PASSED              [ 59%]
tests/test_security.py::test_hash_and_verify_roundtrip PASSED             [ 63%]
tests/test_security.py::test_hash_password_is_salted PASSED               [ 68%]
tests/test_security.py::test_access_token_has_15_minute_expiry PASSED     [ 72%]
tests/test_security.py::test_refresh_token_has_7_day_expiry_and_type_claim PASSED [ 77%]
tests/test_security.py::test_decode_token_rejects_expired_token PASSED    [ 81%]
tests/test_security.py::test_decode_token_rejects_tampered_signature PASSED [ 86%]
tests/test_security.py::test_validate_password_length_rejects_73_bytes PASSED [ 90%]
tests/test_security.py::test_validate_password_length_accepts_72_bytes PASSED [ 95%]
tests/test_security.py::test_validate_password_length_counts_utf8_bytes PASSED [100%]

======================== 22 passed, 2 warnings in 8.00s ========================
```

**Frontend vitest (10 passed):**
```
 RUN  v2.1.9 /Users/ssuladze/.../STORY-003-01-dockerfile/frontend

 ✓ src/stores/__tests__/authStore.test.ts (10 tests) 7ms

 Test Files  1 passed (1)
      Tests  10 passed (10)
   Start at  20:24:16
   Duration  591ms
```

Note: worktree `frontend/node_modules` was absent (worktree doesn't share node_modules with main repo). A symlink was created from the main repo's `frontend/node_modules` to the worktree's `frontend/node_modules` to run tests without `npm install`.

## TanStack Router Workaround

Not needed — the first build passed cleanly. The TanStack Router chicken-and-egg flashcard did not trigger because the worktree's `routeTree.gen.ts` was already up to date with existing routes. `tsc -b && vite build` succeeded on first attempt.

## DoD Self-Check

- [x] `Dockerfile` exists at repo root with multi-stage build per §3.2
- [x] `.dockerignore` exists at repo root and excludes `.env`, `.vbounce/`, `.worktrees/`, `node_modules/`, etc.
- [x] `backend/app/main.py` mounts static files AFTER the API router, guarded by `is_dir()` check. Deviation from spec: uses explicit SPA catch-all route + `/assets` StaticFiles mount instead of a single `StaticFiles(html=True)` at `/` (Starlette 1.0.0 does not support `html=True` as SPA fallback)
- [x] `frontend/src/lib/api.ts` default `API_URL` is empty string (same-origin)
- [x] `frontend/vite.config.ts` has a `/api` dev proxy
- [x] All 7 Gherkin scenarios in §2.1 verified manually
- [x] `docker build . -t teemo-test` exits 0
- [x] Container serves both `/api/health` (JSON) and `/` (HTML) and `/login` (HTML SPA fallback)
- [x] Local dev (`uvicorn app.main:app` from backend dir) still works
- [x] `.env` is NOT baked into the image (`ls /app/.env` fails in container)
- [x] Backend 22 + frontend 10 = 32 regression tests passing
- [x] No new backend or frontend dependencies added
- [x] All new code has JSDoc/docstrings

## Concerns

**Image size: 962 MB (spec target: < 500 MB)**

The 962 MB image is driven by:
1. `build-essential` in the runtime stage (~200 MB for gcc + binutils + libc-dev). This is needed because `pydantic-ai` and `cryptography` deps require C compilation during `pip install`. Could potentially be removed in a later optimization pass if pre-built wheels become available.
2. `pydantic-ai[openai,anthropic,google]==1.79.0` + `slack-bolt` + `google-api-python-client` install ~600 packages totaling the bulk of the image. These are all pre-existing backend deps in `pyproject.toml`.

Optimization options for a future story: (a) remove `build-essential` after confirming all wheels ship as pre-compiled binaries, (b) split `pydantic-ai` extras to only install what's needed in production vs all three LLM providers, (c) consider Alpine Python with manual wheel compilation if image size becomes a blocker for Coolify deploy times.

**Spec inaccuracy: StaticFiles(html=True) SPA fallback**

The story spec §3.3 states `html=True` makes StaticFiles "serve index.html for unmatched routes." This is incorrect for Starlette 1.0.0. `html=True` only serves `index.html` for directory paths, and serves `404.html` (if present) for missing files — not a generic SPA fallback. The implemented solution uses a two-part pattern that achieves the same result: `/assets` StaticFiles mount + explicit `/{full_path:path}` catch-all route. Team Lead should update the story spec or flag for a future FLASHCARD.

**HEAD method handling in Starlette 1.0.0**

`@app.get()` in Starlette 1.0.0 does NOT automatically handle HEAD requests — `Route.handle()` returns 405 if the method is not in `route.methods`. The `/api/health` route was changed from `@app.get` to `@app.api_route` with `methods=["GET", "HEAD"]` to pass Scenario 5's `curl -sI` check. This is a minor but surprising Starlette 1.0.0 behavior.

**Docker port collision on dev machine**

Port 8000 was occupied by `chyro-api-1` on the dev host. Container verification ran on port 8002 (`-p 8002:8000`). All scenarios verified successfully. Production deploy on Coolify uses a fresh port namespace so this is dev-only.

**Docker context**

OrbStack is the Docker runtime on this machine. All `docker` commands require `--context orbstack`. The default socket path `/Users/ssuladze/.orbstack/run/docker.sock` requires the context flag explicitly.

## Process Feedback

- Story spec §3.3 contained an incorrect claim about `StaticFiles(html=True)` implementing SPA fallback. This required investigating Starlette internals and designing an alternative approach. A spec fact-check pass by the Architect before stories go to "Ready to Bounce" would catch this class of error.
- The TanStack Router chicken-and-egg flashcard was relevant (confirmed in Read First list) but did not trigger — noting it as a near-miss to preserve the warning.
- Worktree node_modules absence required a manual symlink workaround. The Team Lead setup script for new worktrees should consider symlinking frontend/node_modules from the main repo, or the task file should document this as a prerequisite for running frontend tests in a worktree.
