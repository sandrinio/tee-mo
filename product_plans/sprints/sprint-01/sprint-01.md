---
sprint_id: "sprint-01"
sprint_goal: "End-to-end scaffold: both servers run, database schema applied, design system foundation in place, smoke test renders backend health via UI primitives."
dates: "2026-04-11"
status: "Done"
delivery: "D-01"
confirmed_by: "Solo dev (user)"
confirmed_at: "2026-04-11"
---

# Sprint S-01 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.
> Status is "Planning". Human confirmation moves to "Confirmed". Execution moves to "Active".

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] **Self-hosted Supabase credentials provided** — verified working against `sulabase.soula.ge` with both anon and service_role keys
- [x] **All 4 `teemo_*` migrations executed by user** — verified via REST (all 4 tables return HTTP 200)
- [x] All 4 story files authored with full context packs (§1 spec, §2 acceptance, §3 implementation, §4 quality gates)
- [x] No stories have 🔴 High ambiguity (all 🟢 Low)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Roadmap §5 and Charter §6
- [x] **Design Guide (`tee_mo_design_guide.md`) read and referenced in stories**
- [x] **Table prefix convention saved to memory** — all tables use `teemo_*`
- [x] **Human has confirmed this sprint plan** — confirmed 2026-04-11, Q2/Q3/Q4 all resolved

---

## 1. Active Scope

> 4 stories, all L1-L2. Target: 4 hours total. First half of Day 1.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-001-01: Backend FastAPI Scaffold + Health Endpoint](./STORY-001-01-backend_scaffold.md) | EPIC-001 | L2 | Ready to Bounce | — |
| 2 | [STORY-001-02: Supabase Client Wiring + Schema Smoke Check](./STORY-001-02-supabase_schema.md) | EPIC-001 | **L1** | Ready to Bounce | STORY-001-01 |
| 3 | [STORY-001-03: Frontend Scaffold + Design System Foundation](./STORY-001-03-frontend_scaffold.md) | EPIC-001 | L2 | Ready to Bounce | — |
| 4 | [STORY-001-04: UI Primitives + E2E Smoke Test](./STORY-001-04-ui_primitives_smoke.md) | EPIC-001 | L1 | Ready to Bounce | STORY-001-01, STORY-001-03 |

> **Note**: STORY-001-02 downgraded from L2 → L1 because migrations are pre-written (`database/migrations/`) and the user has already applied them. The story now only wires the Python Supabase client and extends `/api/health` to verify table reachability. Estimate dropped from ~1h to ~30min.

### Story Summaries

**STORY-001-01: Backend FastAPI Scaffold + Health Endpoint** (L2, ~1h)
- Goal: FastAPI app boots, loads env config, exposes `GET /api/health` returning `{"status": "ok", "service": "tee-mo"}`.
- Files: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/.env.example`, `backend/.gitignore`
- Deliverable: `uvicorn app.main:app --reload` starts server on port 8000. Browser hits `/api/health` and sees JSON. CORS configured for `http://localhost:5173`.
- Dependencies: Charter §3.2 (FastAPI 0.135.3, Pydantic Settings), Roadmap ADR-019 (VPS/Coolify compatible).

**STORY-001-02: Supabase Client Wiring + Schema Smoke Check** (L1, ~30min)
- Goal: Backend connects to self-hosted Supabase. `/api/health` verifies all 4 `teemo_*` tables are reachable.
- Files: `backend/app/core/db.py` (new), `backend/app/main.py` (update health endpoint), `backend/tests/test_health_db.py` (new)
- Deliverable: Health endpoint returns a `database` object with status per table. Cached singleton Supabase client using service role key.
- Pre-written: All migrations live in `database/migrations/` with `teemo_` prefix. User has already applied them to the live Supabase instance. All 4 tables confirmed reachable via REST during sprint planning.
- Dependencies: STORY-001-01 (needs config + FastAPI app).
- Schema notes: All 4 tables now prefixed `teemo_*`:
  - `teemo_users`: id, email, password_hash, created_at, updated_at
  - `teemo_workspaces`: id, user_id, name, slack_team_id, slack_bot_user_id, encrypted_slack_bot_token, ai_provider, ai_model, encrypted_api_key, encrypted_google_refresh_token, created_at, updated_at
  - `teemo_knowledge_index`: id, workspace_id, drive_file_id, title, link, mime_type, ai_description, content_hash, last_scanned_at, created_at (+ 15-file cap trigger + MIME type check)
  - `teemo_skills`: id, workspace_id, name, summary, instructions, is_active, created_at, updated_at (+ UNIQUE + slug regex + length checks)

**STORY-001-03: Frontend Scaffold + Design System Foundation** (L2, ~1.5h)
- Goal: Vite + React 19 + Tailwind 4 running with full design token set from Design Guide §2. Inter + JetBrains Mono fonts loaded. TanStack Router initialized with root + index routes.
- Files: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/app.css`, `frontend/src/routes/__root.tsx`, `frontend/src/routes/index.tsx`
- Deliverable: `npm run dev` starts Vite on port 5173. Landing page renders the display heading "Tee-Mo" styled per Design Guide §3. `@theme` block in `app.css` defines all brand + neutral + semantic tokens from Design Guide §2. All typography classes work (`text-4xl font-semibold tracking-tight`, etc.).
- Dependencies: Design Guide §2 (colors), §3 (typography), §11.1 (Tailwind 4 setup), Charter §3.2 (versions).

**STORY-001-04: UI Primitives + E2E Smoke Test** (L1, ~30min)
- Goal: Ship 3 reusable primitives (Button, Card, Badge) per Design Guide §6. Landing page renders a Card containing the backend health status via a colored Badge, with a Primary Button CTA.
- Files: `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/Card.tsx`, `frontend/src/components/ui/Badge.tsx`, `frontend/src/lib/api.ts`, `frontend/src/routes/index.tsx` (updated)
- Deliverable: Visiting `http://localhost:5173` shows:
  - "Tee-Mo" display heading
  - "Your BYOK Slack assistant" subtitle
  - Card containing: badge showing "Backend: ok" (green) if `/api/health` returns ok, "Backend: error" (red) otherwise
  - Primary Button "Continue to login" (disabled for now — routes to nothing)
- Dependencies: STORY-001-01 (health endpoint), STORY-001-03 (Tailwind + tokens).
- Design Guide refs: §6.1 Button, §6.3 Card, §6.6 Badge, §3 Typography, §4 Spacing.

### Context Pack Readiness

**STORY-001-01**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 4 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code snippets)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-001-02**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2 — 3 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code snippets)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-001-03**
- [x] Story spec complete (§1 — 10 detailed requirements)
- [x] Acceptance criteria defined (§2 — 4 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code snippets including `app.css` @theme block)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

**STORY-001-04**
- [x] Story spec complete (§1 — 7 detailed requirements)
- [x] Acceptance criteria defined (§2 — 3 Gherkin scenarios)
- [x] Implementation guide written (§3 — full code for all 3 primitives)
- [x] Ambiguity: 🟢 Low
- V-Bounce State: **Ready to Bounce**

### Escalated / Parking Lot
- None — this is the first sprint.

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1 (parallel)**: STORY-001-01 (backend scaffold) + STORY-001-03 (frontend scaffold) — zero shared files, fully independent.
- **Phase 2 (parallel)**: STORY-001-02 (Supabase + migrations, depends on 01) + STORY-001-04 (UI primitives + smoke test, depends on 01 + 03).

### Merge Ordering
> Stories have zero shared file surfaces — no merge conflicts expected.

| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-001-01 | Unblocks 02 and 04 |
| 2 | STORY-001-03 | Unblocks 04 |
| 3 | STORY-001-02 | Independent of 04 |
| 4 | STORY-001-04 | Final integration, touches both frontend and backend surface via `api.ts` |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|--------------------|------|
| `frontend/src/routes/index.tsx` | STORY-001-03 (creates), STORY-001-04 (updates) | Low — strict sequential order (03 then 04) |
| `backend/app/main.py` | STORY-001-01 (creates), STORY-001-02 (updates health endpoint) | Low — strict sequential order (01 then 02) |

### Execution Mode

| Story | Label | Mode | Reason |
|-------|-------|------|--------|
| STORY-001-01 | L2 | Fast Track (approval requested) | Scaffold work, no ADR conflicts, well-known FastAPI patterns |
| STORY-001-02 | L1 | Fast Track | L1 auto-qualifies |
| STORY-001-03 | L2 | Fast Track (approval requested) | Scaffold work, Tailwind 4 CSS-first well-documented in Design Guide §11.1 |
| STORY-001-04 | L1 | Fast Track | L1 auto-qualifies |

> **Human approval needed: Fast Track for all 3 L2 stories?** Full Bounce adds ~1-1.5hr to each story (QA + Architect bounces). For hackathon pace, Fast Track recommended unless the human wants gate validation on scaffold.

### ADR Compliance Notes
- STORY-001-01 uses FastAPI 0.135.3 with `[standard]` extras → complies with Charter §3.2.
- STORY-001-02 uses `supabase==2.28.3` (not 3.0 pre-release) → complies with Roadmap ADR-015.
- STORY-001-03 uses Tailwind 4 CSS-first via `@theme` (not v3 `tailwind.config.js`) → complies with Design Guide §11.1 + Roadmap ADR-022.
- STORY-001-04 uses Lucide icons + primitives styled per Design Guide §6 → complies with Roadmap ADR-022. No shadcn, no MUI.

### Dependency Chain

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-001-02 | STORY-001-01 | Needs `backend/app/core/config.py` for env loading |
| STORY-001-04 | STORY-001-01 | Fetches from `/api/health` |
| STORY-001-04 | STORY-001-03 | Uses Tailwind classes + design tokens defined in `app.css` |

### Risk Flags

**From Roadmap §5:**
- **VPS + Coolify deploy is Sprint 5 concern** — Sprint 1 targets local dev only. No deploy work here.
- **bcrypt 5.0 breaking change** — not applicable to Sprint 1 (no auth yet).
- **Supabase JS 3.0 pre-release** — ADR-015 locks us to 2.28.3. Double-check `requirements.txt` pin.

**Sprint-specific:**
- **Tailwind 4 is newer** — v4.2 CSS-first config pattern may have undocumented quirks. Mitigation: keep the `@theme` block minimal for Sprint 1, expand in later sprints.
- **Inter font loading** — use `@fontsource/inter` package (not Google Fonts CDN) to avoid CORS/CSP issues and keep offline dev working.
- **Self-hosted Supabase quirks** — custom JWT secret length, custom ports, potential auth middleware differences. Mitigation: run the DB connection test as the first thing in STORY-001-02, not the last.
- **Monorepo tooling** — no pnpm/yarn workspaces for v1. Separate `package.json` + `pyproject.toml` in `frontend/` and `backend/` folders. Root has only `README.md` and `.gitignore`.

---

## 3. Sprint Open Questions

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| **Q1**: Self-hosted Supabase credentials | Provided in `.env`: `SUPABASE_URL=https://sulabase.soula.ge`, all 4 keys present, JWT secret exactly 32 bytes. Connection verified with both anon and service_role keys during planning. | — | Solo dev | **Resolved** 2026-04-11 |
| **Q5**: Migration application strategy | Migrations pre-written in `database/migrations/` with `teemo_` prefix. User ran them manually. All 4 tables confirmed reachable via REST (HTTP 200 on `teemo_users`, `teemo_workspaces`, `teemo_knowledge_index`, `teemo_skills`). | — | Solo dev | **Resolved** 2026-04-11 |
| Q2: Python version for backend | **Python 3.11** — matches new_app, maximizes copy-reuse, stable. `pyproject.toml` sets `requires-python = ">=3.11,<3.12"`. | — | Solo dev | **Resolved** 2026-04-11 |
| Q3: Frontend package manager | **npm** — zero setup, matches Vite scaffold default. No pnpm/bun workspaces. | — | Solo dev | **Resolved** 2026-04-11 |
| Q4: Fast Track for L2 stories | **Yes — all L2s Fast Track.** STORY-001-01 and STORY-001-03 are scaffold work with no ADR conflicts. Saves ~2h across the sprint. Dev → DevOps flow, skip QA/Arch bounces. | — | Solo dev | **Resolved** 2026-04-11 |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-001-01 | Done | 0 (Fast Track) | 0 (Fast Track) | 1 (`test_health.py`) | ~5% | Dev included `bcrypt==5.0.0` + `test_health.py` per the story spec, overriding an incorrect Team Lead task prompt. Followed ADR-locked Charter §3.2 pins exactly. |
| STORY-001-03 | Done | 0 (Fast Track) | 0 (Fast Track, 1 bounce for version fix) | 0 | ~2% | Bounce-2 needed: Team Lead sprint-context incorrectly listed `vite@5.x` / `bcrypt<5.0`. Charter §3.2 (authoritative) pins `vite@^8.0.8` / `bcrypt==5.0.0`. Corrected via targeted patch. Lesson recorded in `FLASHCARDS.md`. Also recorded: do not redefine Tailwind 4 built-in slate tokens. |
| STORY-001-02 | Done | 0 (Fast Track) | 0 (Fast Track) | 5 hermetic (`test_health_db.py`) | 0% | Clean single pass. Cached Supabase client via `@lru_cache`, `/api/health` extended with per-table `teemo_*` status + aggregate `status: ok/degraded`. Dev correctly preferred the story spec over task-prompt ambiguity on the `database_ok` boolean field. |
| STORY-001-04 | Done | 0 (Fast Track) | 0 (Fast Track) | 0 | 0% | Clean single pass. Button (4 variants per spec, not 3 as the task prompt said), Card, Badge primitives. Added `QueryClient` + `QueryClientProvider` to `main.tsx` and used `useQuery` for `/api/health` per story §R5. Typed `HealthResponse.database` as optional to survive the pre-merge race. |

**Aggregate Correction Tax**: ~1.75% average — well within tolerance. All corrections driven by Team Lead sprint-context errors, not Dev errors.

**Process lessons recorded to FLASHCARDS.md**:
1. Sprint context locked-dependency rows must be copied verbatim from Charter §3.2 (not from memory).
2. Do not redefine Tailwind 4 built-in slate/zinc tokens in `@theme`.
3. bcrypt 5.0 raises `ValueError` on passwords >72 bytes — validate at the `/api/auth/register` boundary in Sprint 2.
<!-- EXECUTION_LOG_END -->
