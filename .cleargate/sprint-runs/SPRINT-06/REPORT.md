---
sprint_id: "SPRINT-06"
report_type: "retrospective"
generated_by: "cleargate-migration-2026-04-24"
generated_at: "2026-04-24T00:00:00Z"
source_origin: "vbounce-sprint-report-S-06.md"
---

# SPRINT-06 Retrospective

> **Ported from V-Bounce.** Synthesized from `.vbounce-archive/sprint-report-S-06.md` during ClearGate migration 2026-04-24. V-Bounce's report format was more freeform; this is a best-effort remap into ClearGate's 6-section retrospective shape.

Sprint Goal: Ship full EPIC-004 — BYOK key management end-to-end.

## §1 What Was Delivered

**User-facing:**
- Key Section on WorkspaceCard — each workspace card now shows BYOK key status.
- Add key flow — user selects provider (OpenAI / Anthropic / Google), types API key, clicks Validate, then Save.
- Validate before save — key is probed against the live provider API before storage; clear inline feedback.
- Masked key display — stored keys show as `sk-ab...xyz9` with provider badge; plaintext never exposed.
- Update key — click Update to replace an existing key with a new one.
- Delete key — click Delete with inline confirmation; clears key, provider, and model from workspace.

**Internal / infrastructure:**
- 4 REST endpoints: `POST /api/keys/validate`, `POST/GET/DELETE /api/workspaces/{id}/keys`.
- Pydantic models with `__repr__` redaction (ADR-002 plaintext key safety).
- `key_validator.py` — httpx provider probes for OpenAI, Anthropic, Google.
- Migration 008: `key_mask VARCHAR(20)` column on `teemo_workspaces`.
- `get_workspace_key()` — non-inference BYOK resolver (for EPIC-006 file indexing).
- `resolve_provider_key()` — inference-path resolver (for EPIC-007 agent factory).
- 3 TanStack Query hooks: `useKeyQuery`, `useSaveKeyMutation`, `useDeleteKeyMutation`.
- 4 typed API wrappers in `lib/api.ts`.

**Carried over (if any):**
- None — all 4 stories delivered.
- No model picker in UI (defaults silently applied) — EPIC-008 scope, could cause confusion.

## §2 Story Results + CR Change Log

| Story | Title | Outcome | QA Bounces | Arch Bounces | Correction Tax | Notes |
|---|---|---|---|---|---|---|
| STORY-004-01 | Backend Key Routes + Models + Validator | Done | 0 | 0 | 0% | L2. Copy+strip pattern from new_app spec (new_app not in repo — built from story §3 skeletons). FakeAsyncClient httpx mock pattern reused from S-04. |
| STORY-004-02 | Provider Key Resolvers | Done | 0 | 0 | 0% | L1. Lightest story — 2 pure functions, 5 unit tests. `resolve_provider_key()` gates EPIC-007. |
| STORY-004-03 | Frontend API Wrappers + Hooks | Done | 0 | 0 | 0% | L2. Additive `api.ts` changes only. 5 hook tests with `vi.hoisted()` + `vi.clearAllMocks()`. |
| STORY-004-04 | Key Section UI | Done | 0 | 0 | 0% | L2. KeySection inline component on WorkspaceCard. Existing tests needed `vi.mock` stubs for new hooks. |

**Change Requests / User Requests during sprint:**
- None.

## §3 Execution Metrics

- **Stories planned → shipped:** 4/4
- **First-pass success rate:** 100% (0 QA bounces, 0 Arch bounces, 0% bounce ratio)
- **Bug-Fix Tax:** 0
- **Enhancement Tax:** 0
- **Total tokens used:** Not tracked (V-Bounce S-06 report did not aggregate token usage)
- **Aggregate correction tax:** 0% average
- **Tests added:** 23 (12 backend + 11 frontend). Avg 5.75 tests/story.
- **Post-merge validation:** Backend 99 passed (2 pre-existing supabase deprecation warnings). Frontend 34 passed. Build clean (`tsc -b && vite build`, pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` warning).
- **Merge conflicts:** 0 (worktree isolation + zero shared files in Phase 2).
- **Release tag:** `v0.6.0`.

## §4 Lessons

Top themes from flashcards flagged during this sprint (pending approval at sprint close):
- **#migration-path:** Story spec migration path `backend/migrations/` is wrong — actual path is `database/migrations/`. Dev agent self-corrected. Standardize on `database/migrations/` in all future story specs.
- **#copy-source-stale:** `new_app/` referenced in story specs doesn't exist in this repo — specs are stale on copy source references. Future stories should remove copy-source references OR note "spec-only, no copy available".
- **#vitest-clearAllMocks:** `vi.clearAllMocks()` in `beforeEach` needed alongside `vi.hoisted()` — call-count bleed is a distinct failure mode from TDZ.
- **#tanstack-mock-stubs:** New TanStack Query hooks in existing components break pre-existing tests — add `vi.mock` stubs in all test files rendering the parent.

(See `.cleargate/FLASHCARD.md` for full text once ported.)

## §5 Tooling

- **Friction signals:**
  - Migration path mismatch between story spec (`backend/migrations/`) and reality (`database/migrations/`) — Dev self-corrected.
  - Story specs reference `new_app/` copy sources that don't exist in repo — future stories should note "spec-only, no copy available".
- **Framework issues filed:**
  - Standardize migration path in story templates (Low severity, Team Lead).
  - Remove/clarify copy-source references in future stories (Low severity, Team Lead).
- **Hook failures:** N/A (V-Bounce had no hooks).

## §6 Roadmap

**Next sprint preview (as understood when this report was written):**
- `resolve_provider_key()` unblocks EPIC-007 (agent factory / inference path).
- `get_workspace_key()` unblocks EPIC-006 file indexing BYOK resolution.
- Model picker UI deferred to EPIC-008 (no way to choose a model today; defaults silently applied).
- Vdoc staleness check N/A — vdoc not installed.
