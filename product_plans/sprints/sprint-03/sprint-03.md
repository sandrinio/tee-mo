---
sprint_id: "sprint-03"
sprint_goal: "Land https://teemo.soula.ge as a live Coolify auto-deploy, apply the 3 ADR-024 schema migrations, fix BUG-20260411 (PyJWT test-order flake), and ship the minimal Slack events verification endpoint so EPIC-005 Phase A can start in S-04."
dates: "2026-04-12"
status: "Active"
delivery: "D-01 (Release 1: Foundation + Deploy + Slack Install)"
confirmed_by: "Solo dev (user)"
confirmed_at: "2026-04-12"
---

# Sprint S-03 Plan — Deploy + Schema Foundation

## 0. Sprint Readiness Gate

> Sprint is Confirmed. Human authorized scope + all 6 readiness-gate questions (Dockerfile approach A, migration runner A, single Supabase instance, release tag `v0.3.0-deploy`, authorization scope a-yes/b-user-runs/c-ok/d-ok). Transition to Active happens at Step 0 Sprint Setup.

### Pre-Sprint Checklist

- [x] Prior sprint (S-02) released as `v0.2.0-auth`, archived to `product_plans/archive/sprints/sprint-02/`
- [x] Roadmap §2 reshaped per ADR-026 — EPIC-003 split into Slice A (this sprint) + Slice B (S-05); EPIC-005 split into Phase A (S-04) + Phase B (deferred)
- [x] EPIC-003 document ambiguity 🟢 Low (all 10 open questions resolved by ADR-026 reshape)
- [x] BUG-20260411 filed at `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md`
- [x] ADR-026 Decided: deploy pulled forward to S-03
- [x] Slack app setup guide written — user can start Steps 1–4 in parallel during S-03
- [x] Google Cloud setup guide written — user can configure OAuth consent screen scopes in parallel (doesn't block S-03)
- [x] `sulabase.soula.ge` confirmed as the single Supabase instance — S-03 migrations land there
- [x] Dockerfile approach confirmed: single multi-stage (Vite build → FastAPI serving frontend static + `/api/*` routes, same-origin deploy)
- [x] Migration runner confirmed: manual via Supabase SQL editor (user pastes + runs)
- [x] Release tag confirmed: `v0.3.0-deploy`
- [x] Authorization: push to `origin/main` during sprint YES; DevOps prepares SQL, user runs it manually; tag creation OK; auto-deploy via Coolify on push OK
- [x] **Architect Sprint Design Review — waived** by Team Lead (sprint scope is linear backend infra + deploy; no architectural conflicts; matches S-02 waiver pattern)
- [x] **Human has confirmed this sprint plan** — confirmed 2026-04-12 via answers to 6 readiness-gate questions

---

## 1. Active Scope

> 6 stories: 4× L1, 2× L2. Target: ~4 hours total. All Fast Track. Strict sequential order (each story produces artifacts the next consumes).

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-003-01: Multi-stage Dockerfile + same-origin static serving](./STORY-003-01-dockerfile.md) | ADR-026 | L2 | Done | — |
| 2 | [STORY-003-02: Coolify wiring + first auto-deploy](./STORY-003-02-coolify-wiring.md) | ADR-026 | L2 | Ready to Bounce | STORY-003-01 |
| 3 | [STORY-003-03: Migrations 005 + 006 + 007 + TEEMO_TABLES extension](./STORY-003-03-migrations.md) | EPIC-003 Slice A | L2 | Ready to Bounce | STORY-003-02 |
| 4 | [STORY-003-04: BUG-20260411 PyJWT fix + regression-lock test](./STORY-003-04-pyjwt-fix.md) | EPIC-002 (maintenance) | L1 | Ready to Bounce | STORY-003-03 |
| 5 | [STORY-003-05: Slack events verification stub endpoint](./STORY-003-05-slack-events-stub.md) | EPIC-005 Phase A prep | L1 | Ready to Bounce | STORY-003-04 |
| 6 | [STORY-003-06: Production deploy verification + Slack setup Step 5 unblock](./STORY-003-06-deploy-verification.md) | ADR-026 | L1 (manual) | Ready to Bounce | STORY-003-05 |

### Story Summaries

**STORY-003-01: Multi-stage Dockerfile** (L2, ~1 h)
- Goal: Ship a root-level `Dockerfile` that builds the frontend and serves it from FastAPI at `/`, with `/api/*` routes handled by the existing router stack. `.dockerignore` excludes `.vbounce/`, `.worktrees/`, `node_modules/`, `.env`, `.git`.
- Files: `Dockerfile` (new), `.dockerignore` (new), `backend/app/main.py` (edit — mount `StaticFiles(directory="static", html=True)` AFTER the API router), `frontend/package.json` (edit — verify `build` script is `vite build` and produces `dist/`).
- Deliverable: `docker build . -t teemo-test && docker run -p 8000:8000 --env-file .env teemo-test` exits clean. `curl http://localhost:8000/api/health` returns the 4-table health JSON. `curl http://localhost:8000/` returns the frontend HTML with the Tee-Mo landing page. `curl http://localhost:8000/login` returns the same HTML (SPA fallback).
- Out of scope: HTTPS (Coolify Traefik handles it in S-03-02), CI/CD (none — Coolify auto-deploy is the pipeline), health probe refinement.

**STORY-003-02: Coolify wiring + first auto-deploy** (L2, ~1 h)
- Goal: Push the Dockerfile to `origin/main`, user completes Coolify UI config (service type, domain, env vars, healthcheck), verify `https://teemo.soula.ge` serves the full S-02 app.
- Files: `product_plans/sprints/sprint-03/coolify-setup-steps.md` (new — handoff doc for user), `backend/app/main.py` may need CORS_ORIGINS update for prod domain.
- Deliverable: `https://teemo.soula.ge/api/health` returns 200 + 4 `teemo_*` tables `"ok"`. `https://teemo.soula.ge/` serves landing. `/login`, `/register` render. User pastes full env var list into Coolify. Coolify healthcheck green.
- Execution note: This story straddles Dev (writes setup steps) and User (clicks in Coolify UI). Dev agent cannot touch Coolify directly — it writes the runbook, the user executes.

**STORY-003-03: Migrations 005 + 006 + 007** (L2, ~45 min)
- Goal: Create `teemo_slack_teams` + `teemo_workspace_channels` tables per ADR-024. ALTER `teemo_workspaces` to drop deprecated columns, convert `slack_team_id` to FK, add `is_default_for_team` + `one_default_per_team` partial unique index. Update `TEEMO_TABLES` in `backend/app/main.py` to include the 2 new tables.
- Files: `database/migrations/005_teemo_slack_teams.sql` (new), `database/migrations/006_teemo_workspace_channels.sql` (new), `database/migrations/007_teemo_workspaces_alter.sql` (new — DO-block pre-check, ALTERs, partial unique index), `backend/app/main.py` (edit — `TEEMO_TABLES` tuple), `backend/tests/test_health_db.py` (edit — assert 6 tables in health payload).
- Deliverable: User runs the 3 SQL files against `https://sulabase.soula.ge` via SQL editor in order. `GET /api/health` from the deployed backend returns 6 `teemo_*` tables, all `"ok"`.

**STORY-003-04: PyJWT BUG-20260411 fix** (L1, ~30 min)
- Goal: Migrate `backend/app/core/security.py::decode_token` to use a module-local `_JWT = PyJWT()` instance so module-level `jwt.decode` option mutations cannot poison our decode path. Add regression-lock test.
- Files: `backend/app/core/security.py` (edit — ~6 line change), `backend/tests/test_security.py` (edit — add 1 test asserting options isolation).
- Deliverable: `pytest tests/ -p no:randomly` passes 22 + 1 = 23 tests. `pytest tests/` with `pytest-randomly` active passes 10 consecutive runs. BUG-20260411 marked Fixed.

**STORY-003-05: Slack events verification stub** (L1, ~20 min)
- Goal: Ship `backend/app/api/routes/slack_events.py` with ONE handler: `POST /api/slack/events` that echoes the `challenge` field from `url_verification` payloads. Any other body type returns 202 Accepted. This unblocks the user from completing Slack app setup guide Steps 5–7.
- Files: `backend/app/api/routes/slack_events.py` (new), `backend/app/main.py` (edit — `include_router`), `backend/tests/test_slack_events_stub.py` (new — 1 unit test mocking the Slack url_verification POST).
- Deliverable: `curl -X POST https://teemo.soula.ge/api/slack/events -H 'Content-Type: application/json' -d '{"type":"url_verification","challenge":"abc123"}'` returns `abc123`. Any other POST returns 202.

**STORY-003-06: Production deploy verification + Slack setup Step 5 unblock** (L1 manual, ~15 min)
- Goal: Final sprint verification. After STORY-003-05 merges to `main` and Coolify auto-deploys, the sprint branch reflects the full production state. User completes Slack app setup guide Steps 5–7 (verify Request URL, install to dev workspace).
- Files: None — this story is pure verification and doc update.
- Deliverable: All S-03 DoD checks pass (see §4 Execution Log). User confirms Slack Request URL verified in api.slack.com. Sprint ready for close.

### Context Pack Readiness

**STORY-003-01**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-003-02**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3 — straddles Dev + User)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-003-03**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3 — full SQL in story)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-003-04**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — regression-lock pattern)
- [x] Implementation guide written (§3 — full code delta)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-003-05**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3 — full endpoint code)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-003-06**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — manual checklist)
- [x] Implementation guide written (§3 — verification runbook)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

### Escalated / Parking Lot
- None.

---

## 2. Execution Strategy

> Architect Sprint Design Review waived (S-02 pattern repeated). Team Lead owns this section.

### Phase Plan

Strict linear dependency chain — no parallelism:

```
STORY-003-01 → STORY-003-02 → STORY-003-03 → STORY-003-04 → STORY-003-05 → STORY-003-06
  (Dockerfile)   (Coolify)      (migrations)    (PyJWT)        (Slack stub)   (verify)
```

Each story unblocks the next by adding deployable surface:
- 01 ships the Dockerfile; 02 needs it to deploy.
- 02 ships the live Coolify URL; 03 needs it so `/api/health` post-migration reports from a real running backend.
- 03 ships the schema; 04+ write new tests that land in the test suite.
- 04 fixes the test-order flake; 05 adds new tests without triggering it.
- 05 ships the Slack verification endpoint; 06 uses it to unblock the Slack app setup guide.

### Merge Ordering

| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-003-01 | Ships `Dockerfile` + `main.py` `StaticFiles` mount; blocks all subsequent deploys. |
| 2 | STORY-003-02 | Ships Coolify env var runbook; reads from STORY-003-01's Dockerfile. |
| 3 | STORY-003-03 | Ships 3 SQL + `TEEMO_TABLES` + health test update; depends on deploy being live to verify end-to-end. |
| 4 | STORY-003-04 | Independent of 03 schema-wise but must land AFTER 03 so the BUG fix verification runs against the full 6-table backend. |
| 5 | STORY-003-05 | Mounts new router in `main.py`; low merge risk since 01-04 don't touch the same router mount block. |
| 6 | STORY-003-06 | Pure verification + doc updates. Last merge. |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|--------------------|------|
| `backend/app/main.py` | 001 (mount `StaticFiles` + `CORS_ORIGINS` prod update), 003 (update `TEEMO_TABLES` tuple), 005 (mount `slack_events_router`) | **Medium** — 3 stories edit the same file. Merge order preserves linearity. Each edit is additive and targets distinct sections. |
| `backend/tests/` | 003 (health test update), 004 (PyJWT regression-lock test), 005 (Slack events stub test) | Low — 3 distinct new/edited test files, no file overlap. |
| `backend/pyproject.toml` | None (no new deps expected) | — |

### Execution Mode

| Story | Label | Mode | Reason |
|-------|-------|------|--------|
| STORY-003-01 | L2 | Fast Track | Dockerfile work is boilerplate, verifiable by local `docker build && docker run`. |
| STORY-003-02 | L2 | Fast Track | Straddles Dev + User; Dev writes doc, User clicks Coolify UI. No code review surface to QA. |
| STORY-003-03 | L2 | Fast Track | Migrations are declarative SQL; DO-block pre-check covers the one real risk. |
| STORY-003-04 | L1 | Fast Track | Trivial 6-line change with a regression-lock test. |
| STORY-003-05 | L1 | Fast Track | 1 file + 1 test. Smallest possible Slack-facing surface. |
| STORY-003-06 | L1 manual | Fast Track | No code change. Pure verification. |

### ADR Compliance Notes

- **ADR-019 (Deploy target: VPS + Coolify)**: STORY-003-01 + 003-02 are the first implementation of this ADR. Dockerfile targets Coolify's auto-deploy workflow.
- **ADR-020 (Database hosting: self-hosted Supabase)**: STORY-003-03 migrations land on `https://sulabase.soula.ge`, which is the user's self-hosted Supabase per ADR-020.
- **ADR-024 (Workspace model — 1 user : N SlackTeams : N Workspaces : N channel bindings)**: STORY-003-03 is the direct implementation. Schema matches the shape declared in ADR-024.
- **ADR-025 (Explicit channel binding)**: STORY-003-03 creates the `teemo_workspace_channels` table that ADR-025 relies on.
- **ADR-026 (Deploy infrastructure pulled forward)**: S-03 IS the implementation of this ADR. Every story is in service of either the deploy or the schema foundation.
- **FLASHCARDS.md (bcrypt 72-byte, cookie samesite=lax, Tailwind 4 @theme, Vitest vi.mock TDZ, TanStack Router tsc ordering)**: All 7 entries read by Dev agents during task file intake. No new @theme tokens, no test-mock changes to existing Vitest tests.

### Dependency Chain

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-003-02 | STORY-003-01 | Needs the Dockerfile to exist on `main` so Coolify has something to build. |
| STORY-003-03 | STORY-003-02 | Needs the live deploy at `teemo.soula.ge` to verify `/api/health` from prod after migrations run. |
| STORY-003-04 | STORY-003-03 | Not strictly dependent schema-wise, but must land after 003 so pytest-randomly 10× run covers the full expanded test suite. |
| STORY-003-05 | STORY-003-04 | Avoids landing a new test file into an order-flaky suite. |
| STORY-003-06 | STORY-003-05 | Final verification story — needs all prior work merged. |

### Risk Flags

**Sprint-specific:**

- **First-time Dockerfile build.** STORY-003-01 is the first Docker build in the project. Risk: undocumented runtime issues (backend can't find `static/` directory, FastAPI route ordering wrong, frontend bundled with wrong `VITE_API_URL`). Mitigation: verify locally via `docker build && docker run && curl` before STORY-003-02 pushes anything. Fail fast locally.
- **First-time Coolify auto-deploy.** STORY-003-02's first push to `main` triggers Coolify's first build. Risk: Coolify config mismatch (wrong port, wrong healthcheck path, env var typos). Mitigation: user pastes env var list from a tested template; healthcheck points at `/api/health` which is known green from S-01/S-02 regression suite.
- **Migration 007 ALTER is destructive** (drops columns). DO-block pre-check aborts if any `teemo_workspaces` row has data in `slack_bot_user_id` or `encrypted_slack_bot_token`. Current state: table is empty (verified via S-01/S-02 — only the auth routes write to `teemo_users`, no workspace creation path exists yet).
- **Cookie `secure=true` on production HTTPS** — S-02 auth cookies were tested on `http://localhost` with `secure=false` (via `DEBUG=true`). In prod with `DEBUG=false`, cookies become `secure=true`. Browser will enforce HTTPS-only. Risk: if the deploy serves over HTTP by accident, auth breaks silently. Mitigation: Coolify Traefik handles HTTPS automatically; verify `https://` prefix in Coolify service config.
- **CORS_ORIGINS env var** must be `https://teemo.soula.ge` in prod (not `http://localhost:5173`). If the env var is wrong, CORS preflight fails silently on cookie requests. Mitigation: explicit in STORY-003-02 env var runbook.
- **PyJWT fix might not fully resolve the flake.** The regression-lock test covers the specific known pattern (`jwt.decode(options={"verify_signature": False})`). If there's a deeper leak path, `pytest-randomly` 10× will still catch it — but the fix might not ship clean. Mitigation: if 10× still flakes, roll back the `decode_token` change and file deeper investigation.

**From FLASHCARDS.md:**

- **bcrypt 5.0 72-byte rule** — already enforced by S-02 auth routes, no change.
- **Cookie samesite=lax** — already enforced by S-02 `_set_auth_cookies`, no change.
- **TanStack Router + `tsc -b && vite build` chicken-and-egg** — applies to any new frontend route files. S-03 adds NO new frontend routes (EPIC-003 Slice B is S-05). Not a risk this sprint.

### Fast Track audit requirement

Because QA is skipped for all stories, each Dev agent MUST:
- Run the anti-regression greps (no `any`, no `@ts-ignore`, no raw `fetch`, no `localStorage`) where applicable.
- Paste test output for every new test added (pytest or Vitest).
- Include the `docker build` output (STORY-003-01) and the `curl` verification output (STORY-003-02, -05, -06) in the Dev report.

---

## 3. Sprint Open Questions

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| **Q1**: Dockerfile approach — single multi-stage vs two Dockerfiles + compose | Single multi-stage (A) | Defines STORY-003-01 shape | Solo dev | **Resolved** 2026-04-12 — A |
| **Q2**: Migration runner — manual SQL editor vs script | Manual via Supabase SQL editor (A) | Defines STORY-003-03 user handoff | Solo dev | **Resolved** 2026-04-12 — A |
| **Q3**: Single Supabase instance (dev == prod DB) | Confirmed yes | Migration 007 DO-block pre-check covers the only risk | Solo dev | **Resolved** 2026-04-12 — yes |
| **Q4**: Release tag name | `v0.3.0-deploy` | Sprint close | Solo dev | **Resolved** 2026-04-12 — `v0.3.0-deploy` |
| **Q5**: Authorization to push `origin/main` during sprint | Yes — expected Coolify auto-deploy noise on first push (fails until 003-01 Dockerfile lands) | Enables DevOps agent to merge stories to main | Solo dev | **Resolved** 2026-04-12 — yes |
| **Q6**: SQL migration execution | User runs SQL manually in Supabase editor; DevOps only prepares the files | Defines STORY-003-03 handoff boundary | Solo dev | **Resolved** 2026-04-12 — user runs |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-003-01 | — | — | — | — | — | Not yet started |
| STORY-003-02 | — | — | — | — | — | Not yet started |
| STORY-003-03 | — | — | — | — | — | Not yet started |
| STORY-003-04 | — | — | — | — | — | Not yet started |
| STORY-003-05 | — | — | — | — | — | Not yet started |
| STORY-003-06 | — | — | — | — | — | Not yet started |

**Aggregate Correction Tax**: —

**Process lessons recorded to FLASHCARDS.md**: —
| STORY-003-01-dockerfile | Done | 0 | 0 | 5% | Fast Track L2 single-pass. Multi-stage Dockerfile verified locally. Image 962MB. Two legit Starlette 1.0.0 spec deviations (StaticFiles html=True not SPA fallback; HEAD not auto-handled). |
<!-- EXECUTION_LOG_END -->