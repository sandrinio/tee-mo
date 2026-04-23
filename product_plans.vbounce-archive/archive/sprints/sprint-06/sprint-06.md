---
sprint_id: "sprint-06"
sprint_goal: "Ship full EPIC-004 — BYOK key management end-to-end (backend routes, resolvers, frontend hooks, Key Section UI)."
dates: "2026-04-12 – 2026-04-13"
status: "Completed"
delivery: "D-02"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-12"
---

# Sprint S-06 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry
- [x] **Human has confirmed this sprint plan** (2026-04-12)

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1 | [STORY-004-01: Backend Key Routes + Models + Validator](./STORY-004-01-backend-key-routes.md) | EPIC-004 | L2 | Done | — |
| 2 | [STORY-004-02: Provider Key Resolvers](./STORY-004-02-provider-resolvers.md) | EPIC-004 | L1 | Done | 004-01 |
| 3 | [STORY-004-03: Frontend API Wrappers + Hooks](./STORY-004-03-frontend-hooks.md) | EPIC-004 | L2 | Done | 004-01 |
| 4 | [STORY-004-04: Key Section UI + Manual E2E](./STORY-004-04-key-section-ui.md) | EPIC-004 | L2 | Done | 004-03 |

### Context Pack Readiness

**STORY-004-01: Backend Key Routes + Models + Validator**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-004-02: Provider Key Resolvers**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-004-03: Frontend API Wrappers + Hooks**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

**STORY-004-04: Key Section UI + Manual E2E**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

V-Bounce State: Ready to Bounce

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1**: STORY-004-01 (backend routes + models + validator + migration — the foundation)
- **Phase 2 (parallel after 004-01 merges)**: STORY-004-02 + STORY-004-03 (backend resolvers + frontend hooks — zero shared files, parallel worktrees)
- **Phase 3 (after 004-03 merges)**: STORY-004-04 (Key Section UI + manual E2E verification)

### Merge Ordering
| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-004-01 | Foundation — models, routes, validator, migration, `services/` dir |
| 2 | STORY-004-02 | Backend resolvers — imports `decrypt()` via `core/keys.py` |
| 3 | STORY-004-03 | Frontend hooks — consumes backend endpoints from 004-01 |
| 4 | STORY-004-04 | UI — consumes hooks from 004-03, manual E2E validates full stack |

> 004-02 and 004-03 can merge in either order — they touch completely disjoint file sets (backend `core/` + `services/` vs frontend `lib/` + `hooks/`).

### Shared Surface Warnings
| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `backend/app/main.py` | 004-01 (mount `keys_router`) | Low — one `include_router()` call |
| `backend/app/core/encryption.py` | 004-01 (read), 004-02 (read) | None — read-only |
| `backend/app/services/__init__.py` | 004-01 (create dir), 004-02 (add file) | Low — 004-01 merges first |
| `frontend/src/lib/api.ts` | 004-03 (additive), 004-04 (read) | Low — additive types + wrappers only, no modifications to existing S-04/S-05 exports |
| `frontend/src/routes/app.teams.$teamId.tsx` | 004-04 (add KeySection to WorkspaceCard) | **Medium** — modifies S-05-shipped WorkspaceCard. Review for regressions to rename/make-default. |

### Execution Mode
| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-004-01 | L2 | Full Bounce | — | 4 routes + new models + migration + httpx mocking — touches auth layer and encryption |
| STORY-004-02 | L1 | Fast Track | — | 2 pure functions, 5 unit tests, no external deps |
| STORY-004-03 | L2 | Fast Track | — | Standard TanStack Query hooks following established S-05 pattern |
| STORY-004-04 | L2 | Full Bounce | — | New UI component on existing WorkspaceCard + manual E2E across full stack |

### ADR Compliance Notes
- 004-01: AES-256-GCM encryption via `backend/app/core/encryption.py` (ADR-002). Key never logged, never returned in plaintext. Ownership filter `.eq("user_id", user_id)` on all workspace queries.
- 004-01: `httpx.AsyncClient` for provider validation probes — import at module level per FLASHCARDS.md S-04 lesson.
- 004-01: New migration `008_workspaces_add_key_mask.sql` adds `key_mask VARCHAR(20)` to `teemo_workspaces`. No conflicts — last migration was `007` from S-03.
- 004-02: `decrypt()` only called inside `get_workspace_key()` — centralized access point per ADR-002.
- 004-03: All fetches via TanStack Query + typed `api.ts` wrappers per FLASHCARDS.md frontend data-fetching rule. No raw `fetch` in components.
- 004-04: Styling via Tailwind 4 utility classes (ADR-022). No heavy component libraries. Div overlay pattern for any modals (FLASHCARDS.md jsdom lesson).

### Copy Source Reference
> Stories 004-01 and 004-02 use copy+strip from new_app:

| Target | Copy Source | Strip |
|--------|-----------|-------|
| `backend/app/models/key.py` | `new_app/backend/app/models/key.py` | `id`, `created_at`, `last_used_at`, `is_active`, `scope`, `editable`, `name`, `KeyRename`, `KeyUpdate` |
| `backend/app/api/routes/keys.py` | `new_app/backend/app/api/routes/keys.py` | `update_key`, `rename_key`, `activate_key`, `get_key_impact`, instance-key logic |
| `backend/app/services/key_validator.py` | `new_app/backend/app/services/key_validator.py` | Nothing — copy wholesale |
| `backend/app/core/keys.py` | `new_app/backend/app/core/keys.py` | Instance-key fallback, settings fallback path |
| `backend/app/services/provider_resolver.py` | `new_app/backend/app/services/provider_resolver.py` | `scope`, `key_id` metadata return |

### Dependency Chain
| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-004-02 | STORY-004-01 | Resolvers depend on encryption patterns + workspace query shapes |
| STORY-004-03 | STORY-004-01 | Frontend hooks call backend endpoints created by 004-01 |
| STORY-004-04 | STORY-004-03 | UI imports hooks from 004-03 |

### Risk Flags
- **Provider API rate-limiting during tests (Low):** All backend tests mock `httpx.AsyncClient` — no live provider calls. Live validation exercised during 004-04 manual E2E only.
- **S-05 regression on workspace routes (Low):** 004-01 adds routes under `/api/workspaces/{id}/keys` — coexists with S-05's `/api/workspaces/{id}`. Different paths, no overlap. Full backend suite (87 tests) run post-merge.
- **S-05 regression on WorkspaceCard UI (Medium):** 004-04 modifies `app.teams.$teamId.tsx` to add KeySection. Must verify rename + make-default still work after the change. Manual E2E checklist covers this.
- **Migration ordering (Low):** `008_workspaces_add_key_mask.sql` follows `007_alter_workspaces.sql`. Must be applied to production Supabase before deploying 004-01.
- **Frontend test infrastructure proven (Low):** S-05 established Vitest + RTL + jsdom for component tests. 004-03 and 004-04 reuse the same setup — no new test infrastructure.

---

## 3. Sprint Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| (None — all EPIC-004 open questions already decided in epic §8) | — | — | — | — |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Lead after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-004-01 | Done | 0 | 0 | — | 0% | 7 tests, clean merge, 94/94 suite pass |
| STORY-004-02 | Done | 0 | 0 | — | 0% | 5 unit tests, Fast Track, 99/99 suite pass |
| STORY-004-03 | Done | 0 | 0 | — | 0% | 5 tests, Fast Track, 31/31 frontend + 99/99 backend pass |
| STORY-004-04 | Done | 0 | 0 | — | 0% | 3 new + 3 updated tests, 34/34 frontend + 99/99 backend pass |
<!-- EXECUTION_LOG_END -->
