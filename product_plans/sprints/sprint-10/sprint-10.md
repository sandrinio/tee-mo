---
sprint_id: "sprint-10"
sprint_goal: "Upgrade Drive file extraction to produce structured markdown, cache content for fast reads, add re-index and workspace deletion. Agent answers from tabular data accurately without hitting Drive API on every query."
dates: "2026-04-13"
status: "Active"
delivery: "D-06"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-13"
---

# Sprint S-10 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry (inline in Epic §6 — no formal registry file)
- [x] **Human has confirmed this sprint plan**

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1a | [STORY-006-07: Markdown-Aware Extractors](./STORY-006-07-hybrid-extraction.md) | EPIC-006 | L2 | Done | — |
| 1b | [STORY-006-09: Delete Workspace](./STORY-006-09-delete-workspace.md) | EPIC-006 | L1 | Done | — |
| 2a | [STORY-006-08: Multimodal LLM Fallback](./STORY-006-08-multimodal-fallback.md) | EPIC-006 | L2 | Ready to Bounce | 006-07 |
| 2b | [STORY-006-10: Cached Content](./STORY-006-10-cached-content.md) | EPIC-006 | L2 | Ready to Bounce | 006-07 |
| 3 | [STORY-006-11: Re-Index Files](./STORY-006-11-reindex.md) | EPIC-006 | L2 | Ready to Bounce | 006-08, 006-10 |

### Context Pack Readiness

**STORY-006-07: Markdown-Aware Extractors**
- [x] Story spec complete (§1) — 7 requirements
- [x] Acceptance criteria defined (§2) — 10 Gherkin scenarios
- [x] Implementation guide written (§3) — file paths, code snippets, helpers
- [x] Ambiguity: 🟢 Low

**STORY-006-08: Multimodal LLM Fallback**
- [x] Story spec complete (§1) — 8 requirements
- [x] Acceptance criteria defined (§2) — 8 Gherkin scenarios
- [x] Implementation guide written (§3) — scan_service, drive_service, agent.py changes
- [x] Ambiguity: 🟢 Low

**STORY-006-09: Delete Workspace**
- [x] Story spec complete (§1) — 7 requirements
- [x] Acceptance criteria defined (§2) — 5 Gherkin scenarios
- [x] Implementation guide written (§3) — endpoint, api.ts, frontend button
- [x] Ambiguity: 🟢 Low

**STORY-006-10: Cached Content**
- [x] Story spec complete (§1) — 7 requirements
- [x] Acceptance criteria defined (§2) — 5 Gherkin scenarios
- [x] Implementation guide written (§3) — migration, knowledge.py, agent.py
- [x] Ambiguity: 🟢 Low

**STORY-006-11: Re-Index Files**
- [x] Story spec complete (§1) — 9 requirements
- [x] Acceptance criteria defined (§2) — 7 Gherkin scenarios
- [x] Implementation guide written (§3) — endpoint, api.ts, hooks, frontend button
- [x] Ambiguity: 🟢 Low

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1 (parallel — 2 worktrees)**: STORY-006-07 (extractors) + STORY-006-09 (delete workspace). Zero shared files.
- **Phase 2 (parallel — 2 worktrees)**: STORY-006-08 (multimodal fallback) + STORY-006-10 (cached content). Both depend on 006-07 being merged. 008 modifies `drive_service.py` + `scan_service.py` + `agent.py`. 010 modifies `knowledge.py` + `agent.py` + adds migration. Shared surface: `agent.py` (`read_drive_file` tool) — see merge ordering.
- **Phase 3 (sequential)**: STORY-006-11 (re-index). Depends on both 008 (async `fetch_file_content` + multimodal params) and 010 (`cached_content` column exists). Touches `knowledge.py` + frontend.

### Merge Ordering

| Order | Story | Reason |
|-------|-------|--------|
| 1a | STORY-006-09 | Fully independent — `workspaces.py` + frontend, no shared surfaces |
| 1b | STORY-006-07 | Fully independent — `drive_service.py` + `pyproject.toml` |
| 2 | STORY-006-08 | Depends on 007 — modifies `drive_service.py` (async + fallback), `scan_service.py`, `agent.py` |
| 3 | STORY-006-10 | After 008 — modifies `agent.py` (`read_drive_file`) which 008 already changed. Also adds migration + modifies `knowledge.py` |
| 4 | STORY-006-11 | After 008 + 010 — uses async `fetch_file_content` with multimodal params + `cached_content` column |

### Shared Surface Warnings

| File / Module | Stories Touching It | Risk |
|---------------|---------------------|------|
| `backend/app/services/drive_service.py` | 006-07, 006-08 | Medium — 007 rewrites extractors, 008 adds async + fallback. Sequential merge. |
| `backend/app/agents/agent.py` | 006-08, 006-10 | Medium — 008 adds provider/api_key params to `fetch_file_content` call; 010 rewrites `read_drive_file` for cache-first. Sequential merge (008 before 010). |
| `backend/app/api/routes/knowledge.py` | 006-10, 006-11 | Low — 010 adds `cached_content` to insert payload; 011 adds new endpoint. Disjoint changes but same file. Sequential merge. |
| `frontend/src/lib/api.ts` | 006-09, 006-11 | Low — additive changes (different functions). Can merge in any order. |

### Execution Mode

| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-006-07 | L2 | Fast Track | — | Pure extractor rewrite, no auth/security surfaces |
| STORY-006-08 | L2 | Fast Track | — | Adds multimodal fallback, uses existing scan-tier pattern |
| STORY-006-09 | L1 | Fast Track | — | Single CRUD endpoint, DB cascade handles cleanup |
| STORY-006-10 | L2 | Fast Track | — | Migration + transparent cache layer, no new auth surfaces |
| STORY-006-11 | L2 | Fast Track | — | New endpoint following existing knowledge.py patterns |

### ADR Compliance Notes
- STORY-006-07: Compliant with ADR-016 (same 6 MIME types, better extractors). Swaps pypdf → pymupdf4llm (not in Charter §3.2 but is a replacement dep, not new capability).
- STORY-006-08: Compliant with ADR-004 (scan tier — cheapest model per provider).
- STORY-006-09: Compliant with ADR-024 (ON DELETE CASCADE already in migrations).
- STORY-006-10: Evolves ADR-005 (Drive read) from real-time to cache-first. The change is additive — `read_drive_file` still exists, just reads from cache. No new ADR needed.
- STORY-006-11: Compliant with ADR-004 (scan tier for descriptions), ADR-006 (re-generates AI descriptions).

### Dependency Chain

| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-006-07 | — | Foundation — new extractors |
| STORY-006-09 | — | Fully independent |
| STORY-006-08 | 006-07 | Modifies `drive_service.py` that 007 rewrites |
| STORY-006-10 | 006-07 | Caches content produced by improved extractors; modifies `agent.py` after 008 |
| STORY-006-11 | 006-08, 006-10 | Uses async `fetch_file_content` (from 008) + `cached_content` column (from 010) |

### Risk Flags
- **pymupdf4llm C extension build** — PyMuPDF includes native code (~30MB). Pre-built wheels exist for amd64 Linux. Low risk.
- **Pydantic AI multimodal API** — 006-08 uses pseudocode; Developer must verify exact API. Non-blocking — flagged as first-use pattern in story.
- **`fetch_file_content` async conversion (006-08)** — All callers must be updated. Two known: `agent.py` (already async), `knowledge.py` (already handles async via `iscoroutinefunction` check on line 231).
- **`agent.py` shared surface** — 008 and 010 both modify `read_drive_file`. Strict merge order (008 → 010) prevents conflicts.
- **`last_scanned_at` update in re-index** — 006-11 uses `"now()"` string for Supabase timestamptz. May need Python `datetime.utcnow().isoformat()` instead. Developer verifies during implementation.

---

## 3. Sprint Open Questions

| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| pymupdf4llm wheel availability for deploy | A: Pre-built (likely). B: Need build deps in Dockerfile | Non-blocking — verify during 006-07 | sandrinio | Open |
| Pydantic AI 1.79 multimodal content API | Developer checks docs during 006-08 | Non-blocking — pseudocode in story | sandrinio | Open |
| Supabase `"now()"` for timestamptz update | A: Works as string. B: Use Python datetime | Non-blocking — verify during 006-11 | sandrinio | Open |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Lead after each story completes via `vbounce story complete STORY-ID`.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-006-09 | Done | 0 | 0 | — | 0% | Fast Track single-pass. 4 new tests, all 17 passing. Clean merge. |
| STORY-006-07 | Done | 0 | 0 | — | 0% | TDD Red/Green. 15 new tests (30 total). Team Lead fixed 1 mock pattern. Clean merge. |
<!-- EXECUTION_LOG_END -->
