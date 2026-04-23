---
sprint_id: "S-08"
created: "2026-04-12"
last_updated: "2026-04-12"
---

# Sprint Context: S-08

> Cross-cutting rules for ALL agents in this sprint. Read this before starting any work.

## Design Tokens & UI Conventions
> Applies to STORY-006-05 (Frontend Drive).

- **Color palette**: Brand coral `#F43F5E`, slate neutrals, dark text on light backgrounds
- **Typography**: Inter 600 headings, Inter 400 body, JetBrains Mono code
- **Spacing rhythm**: 4px base, 8/16/24/32px scale
- **Component patterns**: Reuse existing components from `frontend/src/components/`. Div-based overlay modals (not native `<dialog>` — jsdom limitation). All forms use controlled inputs.
- **Design system**: ADR-022 Asana-inspired warm minimalism. Full spec in `tee_mo_design_guide.md`. No shadcn, no MUI, no Framer Motion.

## Shared Patterns & Conventions

- **API calls (frontend)**: All fetches through TanStack Query. Typed wrappers in `frontend/src/lib/api.ts`. Never call `fetch` directly from components.
- **Supabase client (backend)**: Always use `from app.core.db import get_supabase`. Never instantiate `create_client()` ad-hoc.
- **Outbound HTTP (backend)**: `import httpx` at module top level (never inside functions) so tests can monkeypatch. See FLASHCARDS.md "httpx.AsyncClient first use".
- **Encryption**: Use `backend/app/core/encryption.py` for all secret storage (AES-256-GCM per ADR-002). Refresh tokens MUST be encrypted before DB write. Token NEVER logged.
- **Upsert with DEFAULT NOW()**: Omit `DEFAULT NOW()` columns from upsert payloads entirely — do not pass `None` or `datetime.utcnow()`. See FLASHCARDS.md.
- **Health check probes**: Use `select("*").limit(0)`, never `select("id")` — not all tables have an `id` column.
- **base64url from .env**: Always pad before decoding: `padded = raw + "=" * (-len(raw) % 4)`.
- **Worktree discipline**: Use worktree-relative paths for ALL Edit/Write calls. NEVER use absolute paths starting with `/Users/ssuladze/...`.

## Locked Dependencies
> Copied verbatim from Charter §3.2. Do NOT change versions.

| Package | Version | Reason (Charter §3.2) |
|---------|---------|----------------------|
| `fastapi[standard]` | 0.135.3 | Charter §3.2 Backend |
| `pydantic-ai[openai,anthropic,google]` | 1.79.0 | Charter §3.2 Backend |
| `supabase` | 2.28.3 | Charter §3.2 Backend |
| `cryptography` | 46.0.7 | Charter §3.2 Backend |
| `PyJWT` | 2.12.1 | Charter §3.2 Backend |
| `google-api-python-client` | 2.194.0 | Charter §3.2 Backend — Drive API |
| `google-auth` | 2.49.2 | Charter §3.2 Backend — OAuth credential flow |
| `pypdf` | latest stable | Charter §3.2 Backend — PDF extraction |
| `python-docx` | latest stable | Charter §3.2 Backend — Word extraction |
| `openpyxl` | latest stable | Charter §3.2 Backend — Excel extraction |
| `react` | 19.2.5 | Charter §3.2 Frontend |
| `vite` | 8.0.8 | Charter §3.2 Frontend |
| `@tanstack/react-router` | 1.168.12 | Charter §3.2 Frontend |
| `@tanstack/react-query` | 5.97.0 | Charter §3.2 Frontend |
| `tailwindcss` | 4.2.x | Charter §3.2 Frontend |

## Active Lessons (Broad Impact)
> FLASHCARDS.md entries affecting multiple S-08 stories.

- **Supabase upsert + DEFAULT NOW()**: Omit timestamp columns from payload dicts entirely.
- **httpx top-level import**: Module-level `import httpx` required for monkeypatch in tests.
- **base64url padding**: Always pad before `urlsafe_b64decode`.
- **Worktree path discipline**: Worktree-relative paths only — absolute paths bypass branch isolation.
- **Health probes**: `select("*").limit(0)` — never assume `id` column.
- **TanStack Router layouts**: Any route that has children MUST render `<Outlet>`. Content moves to index route.

## Sprint-Specific Rules

- **MIME types (ADR-016)**: Support exactly 6 types — Google Docs, Google Sheets, Google Slides (export API), PDF (pypdf), Word/docx (python-docx), Excel/xlsx (openpyxl). Reject unsupported types at index time with clear error.
- **Knowledge cap (ADR-007)**: 15 files per workspace, enforced server-side. Frontend may show the limit but backend is the authority.
- **Drive scope**: `drive.file` only (non-sensitive). No broad `drive.readonly`.
- **Two-tier models (ADR-004)**: Scan tier uses smallest model per provider (gemini-2.5-flash / claude-haiku-4-5 / gpt-4o-mini). Same BYOK key, different model_id.
- **Self-healing descriptions (ADR-006)**: `ai_description` generated at index time via scan-tier model. `read_drive_file` checks content hash — if changed, re-generates description.
- **Real-time retrieval (ADR-005)**: NO vector DB, NO RAG, NO embeddings. Agent uses ai_description to pick files, reads content on-demand from Drive.
- **Copy source for OAuth**: `backend/app/api/routes/slack_oauth.py` → adapt for Google. Keep state JWT pattern, encryption pattern, redirect feedback pattern.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint context created | Team Lead |
