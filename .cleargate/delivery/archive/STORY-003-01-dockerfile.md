---
story_id: "STORY-003-01-dockerfile"
parent_epic_ref: "ADR-026 (Deploy Infrastructure)"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-03/STORY-003-01-dockerfile.md`. Shipped in sprint S-03, carried forward during ClearGate migration 2026-04-24.

# STORY-003-01: Multi-stage Dockerfile + Same-Origin Static Serving

**Complexity: L2** — Root-level Dockerfile (multi-stage: Node 22 → Python 3.11), `.dockerignore`, `backend/app/main.py` edit to mount `StaticFiles` with SPA fallback. 3-4 files touched, ~1 hour.

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

ADR-026 pulls deploy infrastructure forward to S-03 so Slack webhooks, Google OAuth production redirect_uri, and cross-origin cookie concerns can be tested in production shape from Day 2. Coolify auto-deploys from a `Dockerfile` at the repo root when changes land on `origin/main`. We need a single-container, same-origin deploy that serves the Vite-built frontend statically AND handles `/api/*` routes via FastAPI — no docker-compose, no nginx sidecar, no split subdomains.

### 1.2 Detailed Requirements

- **R1 — Root `Dockerfile`**: Multi-stage build.
  - **Stage 1** (`builder-frontend`): base `node:22-alpine`. Copy `frontend/package.json` + `frontend/package-lock.json`. `npm ci`. Copy `frontend/` source. Run `npm run build`. Output is `/build/dist` containing the Vite production bundle.
  - **Stage 2** (`runtime`): base `python:3.11-slim`. Install OS deps (`build-essential` + `libpq-dev` only if needed — verify first). Copy `backend/pyproject.toml` + backend source. `pip install --no-cache-dir -e backend/`. Copy `/build/dist` from Stage 1 into `/app/static/`. `WORKDIR /app`. `EXPOSE 8000`. `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
  - Multi-stage keeps the final image small (no Node runtime, no `node_modules`).

- **R2 — `.dockerignore` at repo root**: Exclude everything that shouldn't land in the build context:
  ```
  .git
  .worktrees
  .vbounce
  node_modules
  frontend/node_modules
  frontend/dist
  backend/.venv
  backend/.pytest_cache
  backend/__pycache__
  .env
  .env.*
  *.pyc
  .DS_Store
  .idea
  .vscode
  product_plans
  FLASHCARDS.md
  README.md
  ```
  `.env` exclusion is critical — Coolify injects env vars via its own mechanism, NEVER from a baked-in file.

- **R3 — `backend/app/main.py` edit**: Mount `StaticFiles` AFTER the API router. Order matters — FastAPI matches routes top-down, so `/api/*` must register first.
  ```python
  from fastapi.staticfiles import StaticFiles
  from pathlib import Path

  # ... existing imports + app + middleware + include_router(auth_router) ...

  # Static file serving — MUST be mounted LAST so /api/* routes take precedence.
  # Coolify deploys the Vite dist/ into /app/static/ via the Dockerfile.
  _static_dir = Path(__file__).resolve().parent.parent.parent / "static"
  if _static_dir.is_dir():
      app.mount(
          "/",
          StaticFiles(directory=str(_static_dir), html=True),
          name="static",
      )
  ```
  The `html=True` flag makes StaticFiles serve `index.html` for unmatched routes — this is the SPA fallback TanStack Router needs for `/login`, `/register`, `/app`, etc.
  The `if _static_dir.is_dir()` guard means local dev (`uvicorn app.main:app --reload` from `backend/`) still works when `static/` doesn't exist. Only the Docker runtime has `static/` populated.

- **R4 — `backend/app/core/config.py`**: Add `cors_origins_list()` should already return a list from the comma-separated `CORS_ORIGINS` env var (verify S-01 implementation). In production, `CORS_ORIGINS=https://teemo.soula.ge`. No code change needed IF the helper already handles this — verify first.

- **R5 — `backend/app/main.py` CORS update**: Add `https://teemo.soula.ge` to the default `CORS_ORIGINS` if it's not env-overridable. Prefer env-driven — if `cors_origins_list()` reads the env var, no code change. If it hardcodes `http://localhost:5173`, update to read from env.

- **R6 — `frontend/vite.config.ts`**: Verify the build output path. Default Vite output is `frontend/dist`. The Dockerfile Stage 1 expects this — if the project uses a custom `build.outDir`, update the Dockerfile COPY step.

- **R7 — `frontend/src/lib/api.ts`** already defaults `VITE_API_URL` to `http://localhost:8000`. **Change the default to `/api`** so same-origin production deploy works without needing `VITE_API_URL` injected at build time. Local dev continues to work because local users set `VITE_API_URL=http://localhost:8000` in `frontend/.env` (or the Vite dev server proxy handles it).

  Actually — verify first whether `VITE_API_URL` is currently injected at build time. If yes, changing the default is fine (build-time override still works). If it's a runtime lookup, change is still fine because Vite inlines `import.meta.env` values at build time.

  **Implementation note**: Change `const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';` to `const API_URL = import.meta.env.VITE_API_URL ?? '';` — empty string means "same origin", so `fetch('/api/health')` resolves to whatever domain the frontend was served from. Local dev via Vite on :5173 will proxy `/api/*` to :8000 via `vite.config.ts` `server.proxy` (add if missing). Prod deploy on `teemo.soula.ge` serves both frontend and `/api/*` from the same origin.

- **R8 — `frontend/vite.config.ts` dev proxy** (only if not already configured): Add
  ```ts
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  ```
  so that `npm run dev` on port 5173 can still call the backend without CORS hassles and without hardcoding `http://localhost:8000` in `api.ts`.

### 1.3 Out of Scope

- Coolify UI configuration — that's STORY-003-02 (this story stops at "Dockerfile builds cleanly locally").
- HTTPS / TLS — Coolify Traefik handles automatically.
- CI/CD (GitHub Actions) — Coolify auto-deploy IS the pipeline.
- Production health probe tuning (response time thresholds, readiness vs liveness split) — future optimization.
- Multi-region / horizontal scaling — Coolify single-node deploy.
- Docker image size optimization beyond the multi-stage pattern (no Alpine Python, no distroless) — can revisit if image becomes problematic.
- CDN / static asset caching headers — Coolify Traefik handles basic caching.

### TDD Red Phase: No

Rationale: Dockerfile + config changes are infrastructure. No Gherkin-ready logic to drive Red tests. Verification is declarative via `docker build` + `docker run` + `curl`. The Gherkin in §2.1 is for manual verification, not unit tests.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Multi-stage Dockerfile with same-origin serving

  Scenario: Docker build completes
    Given the repo root contains the new Dockerfile and .dockerignore
    When I run `docker build . -t teemo-test`
    Then the build completes with exit 0
    And the final image size is under 500 MB

  Scenario: Container serves backend API at /api/*
    Given the image is built as "teemo-test"
    When I run `docker run --rm -p 8000:8000 --env-file .env teemo-test`
    And I curl http://localhost:8000/api/health
    Then the response status is 200
    And the response JSON has "status" == "ok"
    And the response JSON has "database" with 4 teemo_* tables all "ok"

  Scenario: Container serves frontend at /
    Given the container is running
    When I curl http://localhost:8000/
    Then the response status is 200
    And the response content-type is text/html
    And the response body contains "Tee-Mo"

  Scenario: SPA fallback for client-side routes
    Given the container is running
    When I curl http://localhost:8000/login
    Then the response status is 200
    And the response content-type is text/html
    And the response body contains "Tee-Mo"
    # Note: the body is the same index.html — TanStack Router renders /login client-side

  Scenario: API routes take precedence over static fallback
    Given the container is running
    When I curl http://localhost:8000/api/health
    Then the response content-type is application/json
    # NOT text/html — the API router must match before StaticFiles

  Scenario: Local dev still works without the static directory
    Given no docker container is running
    When I run `cd backend && uvicorn app.main:app --reload` on host
    And I curl http://localhost:8000/api/health
    Then the response status is 200
    # Static mount is skipped because /app/static/ doesn't exist on host

  Scenario: .env is not baked into the image
    Given the image is built as "teemo-test"
    When I run `docker run --rm teemo-test ls /app/.env`
    Then the response is "No such file or directory"
    And the exit code is non-zero
```

### 2.2 Verification Steps (Manual)

- [ ] `docker build . -t teemo-test` exits 0 from repo root.
- [ ] `docker images teemo-test` shows a size < 500 MB.
- [ ] `docker run --rm -p 8000:8000 --env-file .env teemo-test` starts without error (backend prints Uvicorn startup banner).
- [ ] `curl -s http://localhost:8000/api/health | jq .status` returns `"ok"`.
- [ ] `curl -s http://localhost:8000/api/health | jq '.database | keys | length'` returns `4`.
- [ ] `curl -s http://localhost:8000/` returns HTML containing `<title>Tee-Mo` or similar.
- [ ] `curl -s http://localhost:8000/login` returns the same HTML (SPA fallback).
- [ ] `curl -I http://localhost:8000/api/health` shows `content-type: application/json`.
- [ ] `curl -I http://localhost:8000/` shows `content-type: text/html`.
- [ ] Stop the container. Run `cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m uvicorn app.main:app --reload` from the backend dir. `curl http://localhost:8000/api/health` still works (local dev preserved).
- [ ] `docker run --rm teemo-test ls /app/.env 2>&1 || echo "ok — env not baked"` prints "ok — env not baked".
- [ ] `grep -n '.env' .dockerignore` shows `.env` is listed.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Docker** | Docker Desktop running on the host machine | [ ] |
| **Local .env** | Repo-root `.env` exists with valid Supabase creds | [x] (from S-01) |
| **Python venv** | `backend/.venv` exists with all backend deps installed (for local dev verification step) | [x] |
| **Node/npm** | Node 22 + npm present (only for verifying Vite build output path — not required for Docker build) | [x] |
| **Services Running** | `sulabase.soula.ge` reachable (container will hit this for `/api/health`) | [x] |
| **Migrations** | None (S-01 migrations are already applied) | [x] |

### 3.1 Files to Modify

| File | Change Type | Lines |
|------|-------------|-------|
| `Dockerfile` (repo root) | **NEW** | ~50 |
| `.dockerignore` (repo root) | **NEW** | ~20 |
| `backend/app/main.py` | **EDIT** (append StaticFiles mount) | +10 |
| `frontend/src/lib/api.ts` | **EDIT** (change API_URL default to empty string) | 1 line |
| `frontend/vite.config.ts` | **EDIT** (add dev proxy for `/api`) | +8 if missing |

### 3.2 Dockerfile — full content

```dockerfile
# syntax=docker/dockerfile:1.7

# ---------------------------------------------------------------------------
# Stage 1 — frontend build
# ---------------------------------------------------------------------------
FROM node:22-alpine AS builder-frontend
WORKDIR /build

# Copy package manifests first for layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy source + build
COPY frontend/ ./
RUN npm run build
# Output: /build/dist/

# ---------------------------------------------------------------------------
# Stage 2 — runtime (Python 3.11 + FastAPI + built frontend)
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# System deps (libpq for psycopg if needed — verify by running pip install first;
# remove if unused)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend Python deps first for layer caching
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
RUN pip install --no-cache-dir -e ./backend

# Copy the built frontend from Stage 1 into /app/static/
COPY --from=builder-frontend /build/dist /app/static

# Runtime
WORKDIR /app/backend
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Notes:**
- `WORKDIR /app/backend` at the end means uvicorn runs from the backend directory, so `app.main:app` resolves relative to the backend package.
- `static/` lives at `/app/static/`, which is one level up from the uvicorn working directory (`/app/backend`). The `main.py` path logic needs to compute it correctly — see R3.
- If the `build-essential` layer turns out to be unnecessary (i.e., pip install doesn't need a C compiler for any backend dep), remove it and the image shrinks by ~200 MB. Verify on first build.

### 3.3 backend/app/main.py edit — exact diff

Find the location just after `app.include_router(auth_router)` and add:

```python
# At the top with other imports:
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# ... existing app = FastAPI(...), middleware, include_router(auth_router) ...

# Mount frontend static files for same-origin deploy.
# Must be mounted LAST so /api/* routes take precedence in FastAPI's routing table.
# Local dev skips this mount because static_dir doesn't exist outside the container.
_static_dir = Path(__file__).resolve().parent.parent.parent / "static"
if _static_dir.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=str(_static_dir), html=True),
        name="frontend",
    )
```

**Path calculation explained**: `backend/app/main.py` → `parent` = `app/` → `parent.parent` = `backend/` → `parent.parent.parent` = repo root → then `/static` = `/app/static` in the container. Works for both the container layout and refuses to crash locally (directory doesn't exist → mount skipped).

### 3.4 frontend/src/lib/api.ts edit — exact diff

```diff
- const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
+ const API_URL = import.meta.env.VITE_API_URL ?? '';
```

Empty string means all fetch URLs are relative (`/api/health` → same origin). Local dev needs `VITE_API_URL=http://localhost:8000` in `frontend/.env` OR the Vite dev proxy (see R8).

### 3.5 frontend/vite.config.ts edit (only if missing)

Verify first via `cat frontend/vite.config.ts | grep -A5 proxy`. If no `server.proxy` block exists, add:

```ts
export default defineConfig({
  plugins: [/* existing */],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

This makes `npm run dev` route `/api/*` to the local FastAPI backend at port 8000, preserving the S-02 dev workflow.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A (no logic to unit-test; main.py StaticFiles mount is a single declarative line) | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — covered by manual docker-run verification in §2.2 | |
| Integration tests | 0 — covered by manual verification | |

This story is infrastructure. Its "tests" are the §2.2 manual verification checklist.

### 4.2 Definition of Done

- [ ] `Dockerfile` exists at repo root with multi-stage build per §3.2.
- [ ] `.dockerignore` exists at repo root and excludes `.env`, `.vbounce/`, `.worktrees/`, `node_modules/`, etc.
- [ ] `backend/app/main.py` mounts `StaticFiles(directory="<computed>/static", html=True)` AFTER the API router, guarded by `is_dir()` check.
- [ ] `frontend/src/lib/api.ts` default `API_URL` is empty string (same-origin).
- [ ] `frontend/vite.config.ts` has a `/api` dev proxy (or verified it already did).
- [ ] All 7 Gherkin scenarios in §2.1 verified manually.
- [ ] `docker build . -t teemo-test` exits 0.
- [ ] `docker run --rm -p 8000:8000 --env-file .env teemo-test` serves both `/api/health` and `/`.
- [ ] Local dev (`uvicorn app.main:app --reload` from backend dir) still works.
- [ ] `.env` is NOT baked into the image (`docker run --rm teemo-test ls /app/.env` fails).
- [ ] Existing backend + frontend test suites still pass (`pytest tests/` + `npm test`).
- [ ] No new backend or frontend dependencies added.
- [ ] Every new file and every edit has a clear purpose documented in either a code comment or this story spec.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| DevOps | 26 | 185 | 211 |
