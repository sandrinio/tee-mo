---
sprint_id: "S-03"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-03

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Sprint Goal

Land `https://teemo.soula.ge` as a live Coolify auto-deploy, apply the 3 ADR-024 schema migrations, fix BUG-20260411 (PyJWT test-order flake), and ship the minimal Slack events verification endpoint so EPIC-005 Phase A can start in S-04.

## Design Tokens & UI Conventions

> Not applicable — S-03 is backend infra + deploy. No UI changes. If a story accidentally touches `frontend/src/app.css` or any `@theme` block, STOP and escalate — it's out of scope.

The only frontend change in this sprint is the `frontend/src/lib/api.ts` default for `VITE_API_URL` (from `http://localhost:8000` → empty string for same-origin deploy). Everything else is backend + Dockerfile + migrations.

## Shared Patterns & Conventions

- **FastAPI router pattern**: new routers follow the `auth.py` shape from S-02 — `APIRouter(prefix="/api/...")`, mounted via `app.include_router(...)` in `main.py`. No global state, no module-level database connections.
- **`get_supabase()` only**: All Supabase access goes through `app.core.db.get_supabase()`. Never call `create_client()` inline. (FLASHCARDS.md / STORY-001-01)
- **Table prefix**: All Tee-Mo tables are prefixed `teemo_` on the shared self-hosted Supabase. Memory feedback confirmed.
- **Cookie samesite=lax**: Already enforced by S-02 `_set_auth_cookies`. S-03 does NOT change any auth cookie behavior. (FLASHCARDS.md)
- **Migration file pattern**: Match S-01's shape — header comment with purpose + depends-on + ADR reference, `CREATE TABLE IF NOT EXISTS`, index creation, `updated_at` trigger reusing the function from migration 001, RLS disabled, trailing DO-block with `RAISE NOTICE` for visibility in the Supabase SQL editor.
- **Response models never return secrets**: No response model returns `encrypted_slack_bot_token`, `encrypted_api_key`, `encrypted_google_refresh_token`, `password_hash`, or any other ciphertext / hash. This is a strict rule — pytest should assert it when there's a model involved.

## Deploy Rules (new this sprint — ADR-026)

- **Production = `https://teemo.soula.ge`.** Single-origin deploy: frontend + `/api/*` served from one Coolify container.
- **Auto-deploy on push to `main`.** Every merge to main triggers a Coolify rebuild within ~60s. During story bouncing, merges go: story branch → sprint branch. Merges to main happen ONLY at sprint close via DevOps agent. **No direct pushes to main during the sprint.**
- **First push (S-03 setup commits)** already happened — Coolify will have attempted to deploy and FAILED because no Dockerfile was on main. Expected. Confirms auto-deploy is wired. The failing deploy does NOT block development.
- **Second push = STORY-003-01 merge** adds the Dockerfile. This is the first successful Coolify deploy.
- **Dockerfile is at the repo root.** Multi-stage: Node 22 Alpine → Python 3.11 slim. Final image runs `uvicorn app.main:app` on port 8000.
- **Coolify env vars injected** at runtime — NEVER from a baked-in `.env`. `.dockerignore` excludes `.env`.
- **Production `DEBUG=false`** — dev-only endpoints fail closed. No dev-only paths in S-03 anyway (EPIC-003 Slice B's dev-only team-create was eliminated by ADR-026).
- **Production `CORS_ORIGINS=https://teemo.soula.ge`** — same-origin means CORS is nominally unnecessary, but preflight still happens for credentialed requests. Keep it explicit.

## Locked Dependencies

> Verbatim from Charter §3.2 Technical Foundation. Do NOT change these during this sprint. Same lockdown as S-02, unchanged.

| Package | Version | Reason |
|---------|---------|--------|
| `fastapi[standard]` | 0.135.3 | Charter §3.2 |
| `supabase` (python) | 2.28.3 | Charter §3.2 |
| `bcrypt` | 5.0.0 | Charter §3.2 — validate at register boundary |
| `PyJWT` | 2.12.1 | Charter §3.2 — S-03 refactors `decode_token` to use `jwt.PyJWT()` instance per BUG-20260411 fix; version unchanged |
| `cryptography` | 46.0.7 | Charter §3.2 — NOT consumed in S-03 but pinned for EPIC-005 Phase A |
| `react` + `react-dom` | 19.2.5 | Charter §3.2 |
| `vite` | 8.0.8 | Charter §3.2 |
| `zustand` | 5.0.12 | Charter §3.2 |
| `@tanstack/react-router` | 1.168.12 | Charter §3.2 |
| `@tanstack/react-query` | 5.97.0 | Charter §3.2 |

> **No new dependencies this sprint.** Specifically: NO `slack-bolt` yet (that lands in S-04 Phase A), NO `google-api-python-client` (EPIC-006). The S-03 Slack events stub uses plain FastAPI `Request`/`Response` — no Bolt.

## Active Lessons (from FLASHCARDS.md — broad-impact)

- **[2026-04-11] bcrypt 5.0 72-byte limit** — validate at boundary. S-03 does NOT modify auth routes but the rule still applies everywhere.
- **[2026-04-11] `get_supabase()` only** — never call `create_client()` ad-hoc. S-03 health test uses the cached singleton.
- **[2026-04-11] Cookie samesite=lax** — deliberate deviation from new_app's strict. S-03 does NOT change auth cookies.
- **[2026-04-11] Pydantic `EmailStr` + `.test` TLD / `LaxEmailStr`** — not relevant to S-03 (no user-facing email input).
- **[2026-04-11] Vitest 2.x `vi.mock` hoisting TDZ** — not relevant to S-03 (no new Vitest tests; only backend pytest).
- **[2026-04-11] TanStack Router + `tsc -b && vite build` chicken-and-egg** — relevant to STORY-003-01 Dockerfile. The Docker build runs `npm run build` which is `tsc -b && vite build`. If the frontend has new route files (from S-02) that haven't been regenerated yet, the build could fail on the FIRST docker build after adding routes. Mitigation: STORY-003-01 tests locally first; if tsc fails on first build, run `vite build` standalone once in the builder stage. Add a fallback in the Dockerfile if needed.

## Worktree Execution Notes

> Inherited from S-02 sprint context. Same friction applies in S-03.

- **Backend venv is NOT in the worktree.** Worktrees share the main repo's `backend/.venv`. Always run pytest with the absolute interpreter path: `/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest ...`. The shell's default `python` is 3.9 and will fail.
- **`.env` symlink** at the worktree root is pre-created by the Team Lead at Step 1b of sprint setup. `backend/app/core/config.py` resolves `.env` three directories up from itself, which lands on the worktree root. If the symlink is missing, `pydantic_settings` raises `ValidationError` and masks the real test failure.
- **`sprint-context-S-03.md` symlink** at the worktree root is pre-created by the Team Lead (carried over from S-02 Step 1b improvement). Makes this file readable from inside the worktree at `.vbounce/sprint-context-S-03.md`.
- **Docker tests run from the main repo**, not inside a worktree. STORY-003-01's `docker build` needs the whole repo context. Dev agent cd's out of the worktree to run docker, then cd's back in for reports.

## Sprint-Specific Rules

- **Fast Track all 6 stories.** No QA agent, no Architect agent. Dev report + static gates are the review surface.
- **SQL migrations are user-run.** Dev agent writes the `.sql` files but does NOT execute them against Supabase. User runs them manually in the Supabase SQL editor at `https://sulabase.soula.ge` and reports back. Story task files MUST make this boundary explicit.
- **Coolify UI is user-run.** Dev agent writes runbook docs but does NOT click in the Coolify web UI. User executes the runbook and reports back.
- **Release tag at close**: `v0.3.0-deploy` (confirmed).
- **Authorization scope**:
  - (a) Push to `origin/main` during sprint: YES (expected Coolify auto-deploy attempts on each push)
  - (b) DevOps agent prepares SQL, user runs it: confirmed
  - (c) Tag creation by DevOps agent: OK
  - (d) Coolify auto-deploys on push: implicit via (a)
- **BUG-20260411 fix is in-scope** (STORY-003-04). Update the BUG report status to Fixed.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created at Sprint S-03 Step 0 setup | Team Lead |
