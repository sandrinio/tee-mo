---
proposal_id: "sprint-S-03-scope"
status: "Proposal — awaiting human confirmation"
sprint_id: "S-03 (not yet active)"
owner: "Solo dev"
generated_at: "2026-04-12"
---

# Sprint S-03 Scope Proposal — Deploy + Schema Foundation

> **Not a Sprint Plan yet.** This is a scope proposal. Once you confirm, I'll write the formal `product_plans/sprints/sprint-03/sprint-03.md` using the V-Bounce Sprint Plan template and draft the individual story files.

## Sprint goal

Land `https://teemo.soula.ge` as a live deploy from GitHub `main`, apply the three ADR-024 schema migrations, fix BUG-20260411 (PyJWT test-order flake), and ship the minimal Slack verification endpoint so the user can finish the Slack app setup guide in parallel.

**End state**: you can `git push origin main` → Coolify auto-deploys → `https://teemo.soula.ge/api/health` returns 200 with all **6** `teemo_*` tables `"ok"` → `https://teemo.soula.ge/api/slack/events` responds to Slack's `url_verification` challenge → you can verify the Slack Events Request URL in api.slack.com and finish Steps 5–7 of the Slack app setup guide.

## Release target

S-03 does NOT close Release 1. Release 1 still needs S-04 (Slack OAuth Phase A) + S-05 (EPIC-003 Slice B workspace CRUD) per ADR-026 reshape.

## Story inventory (6 stories, all Fast Track)

| # | Story | Label | ~time | Owner |
|---|---|---|---|---|
| STORY-003-01 | **Dockerfile + docker deploy target**: multi-stage Dockerfile at repo root. Stage 1: `node:22-alpine` builds `frontend/` via `npm ci && npm run build` → produces `/dist`. Stage 2: `python:3.11-slim` installs `backend/` via `pip install -e .` → copies frontend `/dist` to `/app/static` → runs `uvicorn app.main:app --host 0.0.0.0 --port 8000`. `backend/app/main.py` extended to serve the static directory at `/` with SPA fallback (`StaticFiles(directory="static", html=True)` mounted AFTER the API router). `.dockerignore` at repo root. Local `docker build . -t teemo-test && docker run -p 8000:8000 --env-file .env teemo-test` exits clean and `curl localhost:8000/api/health` returns the health JSON, `curl localhost:8000/` returns the frontend HTML. | L2 | Developer |
| STORY-003-02 | **Coolify wiring + first auto-deploy** — push the Dockerfile from STORY-003-01 to `origin/main`. User (solo dev) finishes Coolify project configuration in the Coolify web UI: service type = Dockerfile, build context = repo root, port = 8000, domain = `teemo.soula.ge`, env vars pasted (full list below), healthcheck = `GET /api/health` → expects 200. Verify `https://teemo.soula.ge/api/health` returns 200 with all 4 `teemo_*` tables `"ok"` (S-01 baseline). Verify `https://teemo.soula.ge/` serves the React landing page with live backend health badge. Verify `https://teemo.soula.ge/login` and `https://teemo.soula.ge/register` render correctly. | L2 | Developer writes wiring docs + DevOps verifies deploy; user does Coolify UI clicks |
| STORY-003-03 | **Migrations 005 + 006 + 007** (EPIC-003 Slice A story 1): create `teemo_slack_teams`, create `teemo_workspace_channels`, ALTER `teemo_workspaces` (drop `slack_bot_user_id` + `encrypted_slack_bot_token`, drop old unique constraint, add `slack_team_id` FK → `teemo_slack_teams`, add `is_default_for_team` + partial unique index `one_default_per_team`). Update `TEEMO_TABLES` tuple in `backend/app/main.py` to include the 2 new tables. Extend `backend/tests/test_health_db.py` (if it exists) or add a new test confirming all 6 tables return `"ok"` from `GET /api/health`. DO-block pre-check in migration 007 RAISES EXCEPTION if any existing workspace has data in `slack_bot_user_id` / `encrypted_slack_bot_token` (safety guard). User runs the migrations against self-hosted Supabase via SQL editor or migration runner. | L2 | Developer + user runs SQL |
| STORY-003-04 | **BUG-20260411 fix — PyJWT `decode_token` isolation** (EPIC-003 Slice A story 2). Migrate `backend/app/core/security.py::decode_token` to use a module-local `_JWT = PyJWT()` instance instead of the module-level `jwt.decode` interface. Add regression-lock test in `backend/tests/test_security.py` that mutates global `jwt.api_jwt._jwt_global_obj` options BEFORE calling `decode_token` on a tampered token, asserting the tampered token is still rejected. Run `pytest tests/ -p no:randomly` (should be 22 passed). Run `pytest tests/` (with `pytest-randomly` active) 10 times in a row — all green. | L1 | Developer |
| STORY-003-05 | **Minimal Slack events verification endpoint** (EPIC-005 Phase A prep). Create `backend/app/api/routes/slack_events.py` with ONE handler: `POST /api/slack/events`. On receiving a body with `type == "url_verification"`, return the `challenge` field as plain text (200). On any other body, return 202 Accepted + empty response (this is a placeholder — real event handlers come in EPIC-005 Phase B later). Mount the router in `backend/app/main.py`. Add a unit test that mocks the `url_verification` POST and asserts the challenge round-trips. This story is NOT required for the Slack app to exist — Steps 1–4 of the Slack app setup guide can happen without it — but it IS required for Step 5 (Event Subscriptions URL verification) to succeed. | L1 | Developer |
| STORY-003-06 | **Production deploy verification + Slack setup guide unblock**: Push all prior stories' merged changes to `origin/main`, wait for Coolify auto-deploy to succeed, verify `https://teemo.soula.ge/api/health` reports 6 tables (NOT 4 — Story 03 migrations must have been applied to prod Supabase), verify `https://teemo.soula.ge/api/slack/events` responds to a simulated `url_verification` curl. User follows Steps 5–7 of `product_plans/backlog/EPIC-005_slack_integration/slack-app-setup-guide.md` to verify the Slack app Event Subscriptions Request URL. Once verified, user reports back that the Slack app is fully configured (Client ID / Client Secret / Signing Secret in `.env`) and ready for EPIC-005 Phase A in S-04. | L1 (manual) | Developer verifies deploy; user does Slack UI |

**Total:** 6 stories (4 × L1, 2 × L2). Estimated ~4 hours of dev work.

## Coolify env vars — paste into Coolify web UI before STORY-003-02

Log into Coolify → Tee-Mo service → **Environment Variables** tab → paste (one per line). Values come from your existing `.env`:

```
# Supabase (same values as your local .env)
SUPABASE_URL=https://sulabase.soula.ge
SUPABASE_ANON_KEY=<copy from .env>
SUPABASE_SERVICE_ROLE_KEY=<copy from .env>
SUPABASE_JWT_SECRET=<copy from .env>

# Production flags
DEBUG=false
CORS_ORIGINS=https://teemo.soula.ge

# Google OAuth (already in .env; not consumed until EPIC-006 but safe to inject now)
GOOGLE_API_CLIENT_ID=<copy from .env>
GOOGLE_API_SECRET=<copy from .env>

# Slack — add these AFTER completing Steps 1–3 of the Slack app setup guide,
# BEFORE STORY-003-06 runs Step 5 URL verification. Empty strings are fine
# for now if you haven't created the Slack app yet — the S-03 code doesn't
# consume them (EPIC-005 Phase A / S-04 is the consumer).
SLACK_CLIENT_ID=
SLACK_CLIENT_SECRET=
SLACK_SIGNING_SECRET=
```

**Important differences from local `.env`:**

- `DEBUG=false` in prod. **Do NOT set `DEBUG=true` on Coolify.** Dev-only endpoints (once any exist) must fail closed in prod.
- `CORS_ORIGINS=https://teemo.soula.ge` in prod (not `http://localhost:5173`). This is the origin from which the frontend will call the backend. Since we're deploying same-origin (frontend served from the same Coolify container), CORS is technically unnecessary for requests from `teemo.soula.ge` itself — but it's still required for the `OPTIONS` preflight pattern that FastAPI needs for cookie-bearing `credentials: 'include'` requests. Worth keeping.
- `VITE_API_URL` does NOT need to be set in Coolify because same-origin deploy means `lib/api.ts` defaults (`/api`) work. If Vite's build step demands it, add `VITE_API_URL=/api` — but verify first during STORY-003-01 whether Vite complains.

## Parallel work the user can start NOW (before S-03 is bounced)

These are independent of S-03 code. Start them whenever you want:

1. **Slack app setup** — Steps 1–4 of `product_plans/backlog/EPIC-005_slack_integration/slack-app-setup-guide.md`. This creates the app, captures the three credentials, stops at Step 4. Steps 5–7 need S-03's deploy + verification endpoint first.
2. **Coolify env vars** — paste the full list above into the Coolify web UI. Leave the Slack ones empty if you haven't done (1) yet — they can be updated later without redeploying (well, Coolify re-deploys on env change, but that's fine).
3. **Google Cloud OAuth origins + redirect URIs** — follow `product_plans/backlog/EPIC-006_google_drive/google-cloud-setup-guide.md`. Not blocking anything, but now's a good time.
4. **Optional: Run the 11-step S-02 browser walkthrough** (`product_plans/archive/sprints/sprint-02/STORY-002-04-login_register_pages.md` §2.2) — if you want the S-02 regression insurance before we build on top. ~3 minutes.

## Sprint Readiness Gate (before S-03 starts bouncing)

I need explicit confirmation on:

1. **Scope OK** — 6 stories as listed, or adjust?
2. **Story 01 Dockerfile approach** — single multi-stage Dockerfile serving frontend+backend same-origin via FastAPI `StaticFiles`, OR two separate Dockerfiles + `docker-compose.yml` with nginx in front? I'm proposing **single Dockerfile** because it's simpler and matches the Coolify "one service, one port" mental model.
3. **Migration runner** — there's no migration runner script in the repo. For STORY-003-03, I'm assuming you'll run the SQL files manually via Supabase SQL editor (matching S-01). Confirm?
4. **Production Supabase** — is `https://sulabase.soula.ge` the only Supabase instance, or is there a separate "production" one? If only one, dev and prod share a database. That's fine for a hackathon, but it means S-03 migrations land on the same DB you've been using for S-01/S-02 tests. There's no "stage migrations on dev Supabase first" separation. Confirm you're OK with this.
5. **Release tag** — S-03 tag name when released. Suggestion: `v0.3.0-deploy` (signals the release milestone: deploy + schema refactor).
6. **Authorization scope** — permission to push to `origin/main` during S-03, trigger Coolify auto-deploys, and run SQL migrations against `sulabase.soula.ge`? These are each a different "blast radius" and I want explicit pre-authorization.

## Key risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Dockerfile + Coolify first-deploy discovers something we didn't predict (frontend env var, static file serving order, uvicorn worker config, healthcheck timing) | STORY-003-01 validates locally via `docker build && docker run` before STORY-003-02 pushes anything. Fail fast locally. |
| 2 | Migration 007 ALTER fails because the `teemo_workspaces` table isn't actually empty when user runs the SQL | DO-block pre-check raises EXCEPTION; user investigates; we don't force it. |
| 3 | PyJWT fix (STORY-003-04) turns out to be wrong root cause and the flake persists | Regression-lock test covers the specific known pattern. If it still flakes, rollback the `decode_token` change and file a deeper investigation. |
| 4 | Slack verification endpoint (STORY-003-05) subtly wrong — Slack's challenge format changes or I get the content-type wrong | Slack's URL verification format has been stable for years. Unit test mocks the exact Slack payload shape. If prod verification fails despite passing unit test, it's Coolify cold-start latency (3-second Slack timeout). |
| 5 | Coolify auto-deploy triggers on every push to main, potentially exposing work-in-progress during the sprint | Accept — this is Coolify auto-deploy working as designed. Only **merge** commits from story worktrees → sprint branch → main should land on prod. DevOps agent enforces this in S-03 just like it did in S-02. No direct pushes to main during the sprint. |

## Definition of Done (sprint-level)

- [ ] `https://teemo.soula.ge/api/health` returns 200 with 6 `teemo_*` tables, all `"ok"`.
- [ ] `https://teemo.soula.ge/` serves the React landing page with live backend health badge.
- [ ] `https://teemo.soula.ge/login` and `/register` render correctly (S-02 auth regression preserved).
- [ ] `https://teemo.soula.ge/api/slack/events` POST with `{"type": "url_verification", "challenge": "abc"}` returns `abc`.
- [ ] `pytest tests/` with `pytest-randomly` active passes 10 consecutive runs (BUG-20260411 fixed).
- [ ] `backend/tests/` test count: 22 → 24 (migration health regression + PyJWT regression-lock).
- [ ] User has completed Slack app setup guide Steps 1–6 and has `SLACK_CLIENT_ID` / `SLACK_CLIENT_SECRET` / `SLACK_SIGNING_SECRET` in `.env` + Coolify.
- [ ] Tag `v0.3.0-deploy` on `main` (if you approve the tag name).
- [ ] Roadmap §7 Delivery Log row appended for S-03.

## What S-03 does NOT include

- Slack OAuth Phase A routes — S-04
- EPIC-003 Slice B workspace CRUD — S-05
- Any frontend dashboard shell changes — S-04 (team list + header chrome)
- Any BYOK / Drive / Skills / Agent work
- Production monitoring / logging / observability beyond Coolify's built-in container logs
- Database backup / restore procedures
- CI (no GitHub Actions — Coolify auto-deploy is the only pipeline)
