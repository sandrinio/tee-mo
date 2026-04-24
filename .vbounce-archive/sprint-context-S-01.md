---
sprint_id: "S-01"
created: "2026-04-11"
last_updated: "2026-04-11"
---

# Sprint Context: S-01

> Cross-cutting rules for ALL agents in Sprint 1 (End-to-End Scaffold). Read this before starting any work.

## Project Facts (non-negotiable)

- **Table prefix**: Every DB table is prefixed `teemo_*`. Never query a bare `users` / `workspaces` / `skills` / `knowledge_index` table — it does not exist.
- **Supabase**: Self-hosted at `https://sulabase.soula.ge`. All 4 `teemo_*` migrations have already been applied manually by the user. Do **not** re-run migrations.
- **Env vars**: Read `backend/.env` (via Pydantic Settings). Source of truth for local dev is repo-root `.env` — copy what the backend needs into `backend/.env.example` (values redacted). Never commit a real `.env`.
- **Python version**: 3.11 (pin in `backend/pyproject.toml` as `requires-python = ">=3.11,<3.12"`).
- **Frontend package manager**: `npm`. No pnpm / bun / yarn workspaces.
- **Ports**: Backend `:8000`, Frontend `:5173`. CORS on backend must allow `http://localhost:5173`.

## Design Tokens & UI Conventions (Design Guide §2, §3, §4, §6)

- **Brand color**: Coral `#F43F5E` (primary). Slate neutrals. Light mode only in v1.
- **Typography**: `Inter` (display + body), `JetBrains Mono` (mono). Load via `@fontsource/inter` and `@fontsource/jetbrains-mono` — NOT Google Fonts CDN (CORS/CSP risk, offline dev breaks).
- **Display heading style**: `text-4xl font-semibold tracking-tight` per Design Guide §3.
- **Tailwind**: v4.2 CSS-first. All tokens go in an `@theme` block inside `frontend/src/app.css`. **Do not** create `tailwind.config.js` — that is the v3 pattern and is banned by ADR-022.
- **Component library**: Build primitives from scratch following Design Guide §6. Allowed: Radix UI primitives (headless), Lucide icons. **Banned**: shadcn, MUI, Chakra, Framer Motion.
- **Spacing**: 4px base unit, 8/16/24/32 scale (Design Guide §4).

## Shared Patterns & Conventions

- **Monorepo layout**: Top-level `frontend/` and `backend/` folders. No workspace tool — each has its own `package.json` / `pyproject.toml`.
- **Backend imports**: `from app.core.config import settings` style (absolute from `app/`).
- **Frontend API client**: `frontend/src/lib/api.ts` wraps all backend calls. Do not call `fetch` directly from components.
- **TanStack Router**: File-based routing under `frontend/src/routes/`. Root + index routes only for Sprint 1.
- **Self-documenting code**: Every export has a JSDoc / Python docstring. No uncommented public API.
- **Pydantic Settings**: Use `BaseSettings` with `model_config = SettingsConfigDict(env_file=".env", extra="ignore")`.

## Locked Dependencies (ADR compliance)

| Package | Version | Reason |
|---------|---------|--------|
| `fastapi` | `0.135.3` (with `[standard]` extras) | Charter §3.2 |
| `supabase` (python) | `2.28.3` | Roadmap ADR-015 — 3.0 is pre-release, banned |
| `bcrypt` | `5.0.0` (exact pin) | Charter §3.2. Gotcha: raises `ValueError` on passwords > 72 bytes — Roadmap §5 requires the 72-char validator at the `/api/auth/register` boundary. |
| `react` / `react-dom` | `19.2.5` (exact pin) | Charter §3.2 |
| `tailwindcss` | `^4.2.0` | Charter §3.2 + ADR-022 — v4 CSS-first only |
| `vite` | `^8.0.8` | Charter §3.2 |
| `@tanstack/react-router` | `^1.168.12` | Charter §3.2 |
| `@tanstack/react-query` | `^5.97.0` | Charter §3.2 |
| `zustand` | `^5.0.12` | Charter §3.2 |
| `@supabase/supabase-js` | `^2.50.0` | Charter §3.2 |
| `pydantic-ai` | `1.79.0` with `[openai,anthropic,google]` | Charter §3.2 |
| `cryptography` | `46.0.7` | Charter §3.2 |
| `PyJWT` | `2.12.1` | Charter §3.2 |
| `slack-bolt` | `1.28.0` | Charter §3.2 |
| `google-api-python-client` | `2.194.0` | Charter §3.2 |
| `google-auth` | `2.49.2` | Charter §3.2 |

> **Source of truth**: Charter §3.2 is authoritative. Story specs quote these pins verbatim. If this table ever drifts from Charter §3.2, fix the sprint context, not the code.

## Active Lessons (Broad Impact)

- **Table prefix `teemo_*`**: shared Supabase, namespace isolation required. Applies to every SQL statement, RLS policy, foreign key, and Python/TS reference.
- **Supabase client singleton**: Create the client once, cache it. Do not instantiate per-request — exhausts connection pool on the self-hosted instance.
- **Self-hosted Supabase quirks**: Custom JWT secret length (32 bytes), custom ports. When the backend first connects, test it BEFORE building anything on top of it (fail fast).

## Sprint-Specific Rules

- **Fast Track is APPROVED** for all 3 L2 stories (001-01, 001-03) and both L1 stories (001-02, 001-04). Flow is **Dev → DevOps merge**. QA and Architect bounces are **skipped** for Sprint 1 scaffold work.
- **Scope discipline**: Implement exactly what the §3 Implementation Guide specifies. No extra middleware, no "while I'm here" refactors, no new dependencies beyond the story spec. This is scaffold — keep surface minimal.
- **Migrations are frozen**: Do NOT create new SQL files or modify existing ones in `database/migrations/`. The 4 tables are live.
- **`.env` handling**: Read the repo-root `.env` for the Supabase credentials. Create `backend/.env.example` with the key names and empty values. Never commit a real `.env` inside `backend/`.
- **All reports** go to `.worktrees/STORY-{ID}-{name}/.vbounce/reports/` during the bounce, not to the main repo.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Sprint context created from confirmed sprint-01 plan, memory, Charter, Design Guide, Roadmap | Team Lead |
| 2026-04-11 | **Corrected locked dependencies table** — earlier version incorrectly listed `vite@5.x` and `bcrypt<5.0`; actual Charter §3.2 pins are `vite@^8.0.8` and `bcrypt==5.0.0`. Triggered a bounce on STORY-001-03 (vite version downgrade). Lesson recorded to FLASHCARDS.md. | Team Lead |
