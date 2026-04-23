---
sprint_id: "S-06"
sprint_goal: "Ship full EPIC-004 — BYOK key management end-to-end."
dates: "2026-04-12"
status: "Achieved"
release_tag: "v0.6.0"
merge_commit: "01ce0fc"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
---

# Sprint Report: S-06

## 1. What Was Delivered

### User-Facing (Accessible Now)

- **Key Section on WorkspaceCard** — each workspace card now shows BYOK key status
- **Add key flow** — user selects provider (OpenAI / Anthropic / Google), types API key, clicks Validate, then Save
- **Validate before save** — key is probed against the live provider API before storage; clear inline feedback
- **Masked key display** — stored keys show as `sk-ab...xyz9` with provider badge; plaintext never exposed
- **Update key** — click Update to replace an existing key with a new one
- **Delete key** — click Delete with inline confirmation; clears key, provider, and model from workspace

### Internal / Backend (Not Directly Visible)

- 4 REST endpoints: `POST /api/keys/validate`, `POST/GET/DELETE /api/workspaces/{id}/keys`
- Pydantic models with `__repr__` redaction (ADR-002 plaintext key safety)
- `key_validator.py` — httpx provider probes for OpenAI, Anthropic, Google
- Migration 008: `key_mask VARCHAR(20)` column on `teemo_workspaces`
- `get_workspace_key()` — non-inference BYOK resolver (for EPIC-006 file indexing)
- `resolve_provider_key()` — inference-path resolver (for EPIC-007 agent factory)
- 3 TanStack Query hooks: `useKeyQuery`, `useSaveKeyMutation`, `useDeleteKeyMutation`
- 4 typed API wrappers in `lib/api.ts`

### Not Completed

- None — all 4 stories delivered.

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| 004-01 — Backend Key Routes + Models + Validator | EPIC-004 | L2 | Done | 0 | 0 | 0% | — |
| 004-02 — Provider Key Resolvers | EPIC-004 | L1 | Done | 0 | 0 | 0% | — |
| 004-03 — Frontend API Wrappers + Hooks | EPIC-004 | L2 | Done | 0 | 0 | 0% | — |
| 004-04 — Key Section UI | EPIC-004 | L2 | Done | 0 | 0 | 0% | — |

### Story Highlights

- **004-01**: Copy+strip pattern from new_app spec (new_app not in repo — built from story §3 skeletons). FakeAsyncClient httpx mock pattern reused from S-04.
- **004-02**: Lightest story — 2 pure functions, 5 unit tests. `resolve_provider_key()` is the gate that unblocks EPIC-007.
- **004-03**: Additive api.ts changes only — zero modifications to S-04/S-05 exports. 5 hook tests with `vi.hoisted()` and `vi.clearAllMocks()`.
- **004-04**: KeySection inline component on WorkspaceCard. Existing tests needed `vi.mock` stubs for the new hooks.

### 2.1 Change Requests

| Story | Category | Description | Impact |
|-------|----------|-------------|--------|
| (None) | — | — | — |

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value | Notes |
|--------|-------|-------|
| **Stories Planned** | 4 | |
| **Stories Delivered** | 4 | |
| **Stories Escalated** | 0 | |
| **Total QA Bounces** | 0 | |
| **Total Architect Bounces** | 0 | |
| **Bounce Ratio** | 0% | |
| **Average Correction Tax** | 0% | |
| **First-Pass Success Rate** | 100% | |
| **Total Tests Written** | 23 | 12 backend + 11 frontend |
| **Tests per Story (avg)** | 5.75 | |
| **Merge Conflicts** | 0 | Worktree isolation + zero shared files in Phase 2 |

### Post-Merge Validation

- Backend: **99 passed**, 2 warnings (pre-existing supabase deprecation)
- Frontend: **34 passed**
- Build: clean (`tsc -b && vite build`, pre-existing `INEFFECTIVE_DYNAMIC_IMPORT` warning)

---

## 4. Lessons Learned

| Source | Lesson | Recorded? |
|--------|--------|-----------|
| 004-01 Dev | Story spec migration path `backend/migrations/` is wrong — actual path is `database/migrations/` | Pending |
| 004-01 Dev | `new_app/` referenced in story specs doesn't exist in this repo — specs are stale on copy source references | Pending |
| 004-03 Dev | `vi.clearAllMocks()` in `beforeEach` needed alongside `vi.hoisted()` — call-count bleed is a distinct failure mode | Pending |
| 004-04 Dev | New TanStack Query hooks in existing components break pre-existing tests — add `vi.mock` stubs in all test files rendering the parent | Pending |

---

## 5. Retrospective

### What Went Well

- **Full EPIC in one sprint**: EPIC-004 (4 stories, ~9h estimated) completed in one session with 0% bounce ratio.
- **Parallel worktrees**: 004-02 + 004-03 ran simultaneously with zero conflicts — completely disjoint file surfaces.
- **Copy+strip pattern worked**: Even without new_app source files in the repo, the story §3 implementation guides had enough detail for clean first-pass implementations.
- **Test coverage**: 23 new tests across backend and frontend. No regressions in the 133-test combined suite.

### What Didn't Go Well

- **Migration path mismatch**: Story spec said `backend/migrations/` but actual path is `database/migrations/`. Dev agent self-corrected but this should be fixed in future story templates.
- **No model picker**: User noticed during testing that there's no way to choose a model — defaults silently applied. EPIC-008 scope, but could cause confusion.

### Framework Self-Assessment

#### Process Flow

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| Story specs reference `new_app/` copy sources that don't exist in repo | Team Lead | Low | Remove copy source references from future stories or note "spec-only, no copy available" |
| Migration directory path inconsistent in specs vs reality | Team Lead | Low | Standardize on `database/migrations/` in all future story specs |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-12 | Sprint Report generated | Team Lead |
