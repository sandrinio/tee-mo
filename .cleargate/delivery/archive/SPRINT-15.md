---
sprint_id: "SPRINT-15"
remote_id: "local:SPRINT-15"
source_tool: "cleargate-native"
status: "Completed"
start_date: "2026-04-25"
end_date: "2026-04-25"
activated_at: "2026-04-25T07:25:00Z"
human_approved_at: "2026-04-25T07:25:00Z"
completed_at: "2026-04-25T08:00:00Z"
shipping_commit: "3f87e9a"
synced_at: "2026-04-25T00:00:00Z"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-post-sprint-14"
updated_at_version: "cleargate-post-sprint-14"
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# SPRINT-15 Plan

> Third ClearGate-native sprint. Opens EPIC-014 (local document upload) with the 3-story re-scoped slate, closes EPIC-024 (concurrency hardening) via a docs-only status pass (already 80% shipped at commit `bd2b8a4`; remaining R2 targets a non-existent query — see §7), and clears the pre-existing `slack_dispatch` streaming-test noise.

## Sprint Goal

**Ship local document upload end-to-end (extraction service refactor → multipart endpoint → frontend upload button) + restore honest test signal in `test_slack_dispatch.py` + close EPIC-024 by hygiene (no new code).** After this sprint, users can upload local PDF / DOCX / XLSX / TXT / MD files without going through Drive, the failing-test count stops being inflated by stale streaming-mock fixtures, and EPIC-024 is properly archived in the wiki to match its actual repo state.

## 0. Sprint Readiness Gate

- [x] All items reviewed — five 🟢 Low-ambiguity items, all referencing already-approved epics or pre-existing bugs.
- [x] No 🔴 High-ambiguity items in scope (no spike needed).
- [x] Dependencies identified (see §3).
- [x] Risk flags reviewed (see §5).
- [x] **Human confirms this sprint plan before execution starts** ← GATE (approved 2026-04-25 via "kickoff")

## 1. Active Scope

| # | Priority | Item | Parent | Complexity | Ambiguity | Status | Blocker |
|---|---|---|---|---|---|---|---|
| 1 | P1 | [STORY-014-01: Extraction service refactor](./STORY-014-01-extraction-service-refactor.md) | EPIC-014 | L1 | 🟢 | Draft | — |
| 2 | P1 | [STORY-014-02: Multipart upload endpoint](./STORY-014-02-upload-endpoint.md) | EPIC-014 | L2 | 🟢 | Draft | STORY-014-01 (needs `extraction_service` module) |
| 3 | P1 | [STORY-014-03: Frontend upload button](./STORY-014-03-frontend-upload.md) | EPIC-014 | L2 | 🟢 | Draft | STORY-014-02 (needs `/documents/upload` route) |
| 4 | P2 | [BUG-003: `test_slack_dispatch.py` streaming-mock fix](./BUG-003-slack-dispatch-streaming-test-fixtures.md) | EPIC-007 | L1 | 🟢 | Draft | — |

**Total: 4 items · 2× L1 · 2× L2.** Same shape as S-14. STORY-024-02 retired pre-sprint — already shipped at commit `bd2b8a4` (2026-04-21); see §7.

### Pre-sprint hygiene (no engineering — bookkeeping only)

- [ ] Verify EPIC-024 children states match repo, then move shipped story files from `pending-sync/` to `archive/`:
  - `STORY-024-01-database-queue-rpc.md` — flip status to `Shipped` (commit `bd2b8a4`), move.
  - `STORY-024-02-background-worker-locks.md` — flip status to `Shipped (R1) + Retired (R2)`, add a closing note explaining R2's premise drift, move.
- [ ] Update `EPIC-024-concurrency-hardening.md` frontmatter to `status: "Shipped"`, add a Change Log entry dated 2026-04-25 capturing the SPRINT-14 + SPRINT-15-pre status pass.
- [ ] Run wiki-ingest fallback so the index reflects the new states.

This is ~15 min of file edits, not a sprint item — done by the human or a wiki-curation pass before the four-agent loop kicks off.

## 2. Context Pack Readiness

**STORY-014-01 — Extraction service refactor**
- [x] Source lines verified: `drive_service.py:168–278` contain the 6 functions to relocate (`_extract_pdf`, `_extract_docx`, `_extract_xlsx`, `_maybe_truncate`, `_rows_to_markdown_table`, `_docx_table_to_markdown`).
- [x] No new tests required — existing Drive tests are the regression baseline.
- [x] Pure code move. No behavior change. No schema. No API. No UI.

**STORY-014-02 — Multipart upload endpoint**
- [x] `document_service.create_document(...)` already accepts `source='upload'` + `original_filename` per its docstring (EPIC-015 work). Story §3.2 R-MIME table maps Content-Type → `doc_type` enum value verified against migration `010_teemo_documents.sql` (`'pdf' | 'docx' | 'xlsx' | 'text' | 'markdown'` all valid).
- [x] 7-path validation logic mirrors existing Drive-index route (`knowledge.py:153`). Per-workspace `asyncio.Lock` reused via `_get_workspace_lock` (`knowledge.py:92`).
- [x] AI description generation: handled inside `document_service.create_document` itself — no new scan call required in this story.
- [x] 7 Gherkin scenarios + 7 route tests minimum (one per scenario, all with mocked `extraction_service.*` and `document_service.create_document`).

**STORY-014-03 — Frontend upload button**
- [x] Source-badge UI **already shipped** in `KnowledgeList` (`frontend/src/routes/app.teams.$teamId.$workspaceId.tsx:546–556` — Drive / Upload / Agent variants via `sourceBadgeProps()`). Pre-flight verified during Gate-2 triage.
- [x] Agent-side path **already shipped** — `read_document` tool is source-agnostic (STORY-015-03), system prompt pulls all `teemo_documents` regardless of source.
- [x] Story scope is purely the upload trigger UI: `useUploadKnowledgeMutation` hook + `uploadKnowledgeFile` API helper + button next to the existing Drive picker. No KnowledgeList edits.
- [x] 4 Vitest expectations + 4 manual verification steps codified.

**BUG-003 — slack_dispatch streaming-mock fix**
- [x] Reproduction confirmed at sprint-tip baseline: `pytest backend/tests/test_slack_dispatch.py` → `3 failed, 8 passed`.
- [x] Root cause identified: legacy `AsyncMock` for `agent.run` in 3 fixtures; production code switched to `agent.run_stream(...)` async-context-manager. Recommended fixture shape included verbatim in §5 of the BUG file.
- [x] Pre-existing — does not flip from S-14 work. Fixing here removes 3 failures from the 46-failure baseline so future sprints can see real regressions clearly.

## 3. Sequencing + Dependencies

1. **BUG-003 first.** Independent, ~30 min. Landing it before EPIC-014 work merges means the failing-test count drops by 3 immediately, so any new failures from 014-01/02/03 are easy to spot in the diff signal.
2. **STORY-014-01 second.** Pure code move. Unblocks STORY-014-02.
3. **STORY-014-02 third.** Strictly blocked by 014-01 (imports `extraction_service`). One commit, full backend feature.
4. **STORY-014-03 fourth.** Strictly blocked by 014-02 (consumes the `/documents/upload` route). Frontend-only.

**Parallel-eligibility:** BUG-003 is fully parallel with everything (different file space — only test fixtures). Within EPIC-014: 01 → 02 → 03 is strictly sequential.

## 4. Execution Strategy

### Branching
- Sprint branch: `sprint/S-15` cut from current `main` (`d197ec0`).
- Per-story branches:
  - `bug/BUG-003-slack-dispatch-mocks`
  - `story/STORY-014-01-extraction-service`
  - `story/STORY-014-02-upload-endpoint`
  - `story/STORY-014-03-frontend-upload`
- One commit per item (ClearGate convention). Commit prefixes:
  - `test(epic-007): BUG-003 ...`
  - `refactor(epic-014): STORY-014-01 ...`
  - `feat(epic-014): STORY-014-02 ...`
  - `feat(epic-014): STORY-014-03 ...`
- Merge order follows §3 sequencing. DevOps merges sprint branch to `main` at sprint close under explicit human approval (matching S-13 / S-14 squash-merge pattern).

### Four-agent loop
- **Architect** — draft `.cleargate/sprint-runs/SPRINT-15/plans/W01.md` covering all 4 items: per-story blueprints (files to touch, exact test scenarios), cross-story risks (none — every item touches a different file space), and reuse opportunities. Particular attention to STORY-014-02's MIME → `doc_type` mapping table and STORY-014-03's gating reuse with the existing Drive picker section.
- **Developer** — one item per commit. Must grep `.cleargate/FLASHCARD.md` for relevant tags before implementing:
  - 014-0x: `#schema`, `#fastapi`, `#multipart`, `#vitest`
  - BUG-003: `#test-harness`, `#async-mock`, `#streaming`
  - Standing flashcard for ported items: verify baseline at sprint tip before implementing (S-14 `#process #ambiguity` lesson — applied twice already in this sprint's planning: EPIC-014 schema work and STORY-024-02 worker locks both turned out to be largely shipped).
- **QA** — independent verification gate.
  - BUG-003: run `pytest backend/tests/test_slack_dispatch.py` → expect `0 failed, 11 passed` post-fix.
  - 014-01: confirm `pytest backend/tests/test_drive_service.py` pre/post counts match.
  - 014-02: run the 7 new route tests; verify no temp files persist via `lsof` step; verify upload row appears in agent's `## Available Documents` immediately (sync_status='pending' annotation expected) before wiki ingest runs.
  - 014-03: run the 4 new Vitest tests; manually verify upload flow via `npm run dev`.
- **Reporter** — at sprint close, writes `.cleargate/sprint-runs/SPRINT-15/REPORT.md` with the 6-section retrospective. Remember to write `.cleargate/sprint-runs/.active = SPRINT-15` at kickoff (still no token-ledger hook in ClearGate; ledger gap will persist for a third sprint — flag this in the REPORT Meta section as a follow-up).

### Red-zone surfaces (3+ stories touch these)
- None. Every item lives in a different file space.

### Shared surface warnings (2 stories touch these)
- `backend/app/services/extraction_service.py` — created by STORY-014-01, consumed by STORY-014-02. Strict sequencing guarantees no conflict.
- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — modified by STORY-014-03 only this sprint. Single-story access.
- `backend/tests/test_slack_dispatch.py` — modified by BUG-003 only. The 5 currently-passing tests (including the S-14 `_sender_tz_*` additions) must not regress.

## 5. Risk & Definition of Done

### Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 014-02 multipart body-size limits not enforced before reading bytes (DoS surface) | Low | Medium | Story R2.4 enforces `len(bytes_) > 10MB` after a single `await file.read()`. Starlette default body-size limit is well above 10MB so the read does not stream around the check. |
| 014-02 duplicate-filename check race — two concurrent uploads of "report.pdf" both pass the duplicate check before either inserts | Low | Medium | R7 wraps the duplicate check + insert under the same per-workspace `asyncio.Lock` already used by the Drive-index route. |
| 014-03 jsdom does not expose `FormData` correctly under Vitest | Low | Low | jsdom 29 supports FormData natively; if a flake appears, fall back to the same `vi.spyOn(global, 'fetch')` pattern used by `useKnowledge.test.tsx`. |
| BUG-003 fixture rewrite accidentally weakens assertions on `chat.postMessage` text content | Low | Medium | Required-shape recipe in BUG-003 §5 yields concatenated chunks identical to legacy `agent.run.return_value.output` — assertions stay valid. QA diff-reviews the test file for assertion regressions. |
| sync_status risk (014-02 inserts `pending`, agent doesn't see uploads until wiki ingest) | n/a | n/a | **Resolved during planning.** Verified `agent.py:1004` selects all docs with no `sync_status` filter. Upload rows appear immediately with `⏳` annotation; wiki ingest later flips them to `'synced'` and removes the annotation. STORY-014-02 R5 pins this behavior. |

### Definition of Done
- [ ] All 4 items pass QA on their own branches.
- [ ] Sprint branch `sprint/S-15` merges cleanly to `main` (squash-merge under explicit human approval, pushed to `origin/main`).
- [ ] `pytest backend/tests/` — full suite runs without hangs; **failing test count drops by ≥3** (BUG-003) and shows zero new failures from 014-01 / 014-02.
- [ ] `npm test` (frontend Vitest) — new 014-03 upload-button tests pass alongside existing suite; no new failures.
- [ ] **Pre-sprint hygiene from §1 done before the sprint starts:** EPIC-024 marked Shipped, STORY-024-01 + STORY-024-02 moved to `archive/` with appropriate close-out notes.
- [ ] EPIC-014 progresses from "Active, no children shipped" to "Active, 3/3 stories shipped" — this 3-story slice fully delivers the local-upload feature.
- [ ] No regression on EPIC-007 agent loop, EPIC-013 wiki ingest, EPIC-015 document service, EPIC-018 dashboard automations.
- [ ] `cleargate wiki build` rebuilds cleanly (or wiki-ingest agent processes all SPRINT-15 work items when CLI unavailable, matching S-13 / S-14 fallback).
- [ ] Reporter writes `.cleargate/sprint-runs/SPRINT-15/REPORT.md` — 6-section retrospective.
- [ ] Flashcards recorded for any surprises discovered during execution.
- [ ] Live-testing window — any post-squash hotfixes logged in REPORT.md §Post-ship hotfixes.

## 6. Sprint Metrics & Goals

- **Stories planned:** 3 stories + 1 bug = 4 items.
- **Target first-pass success rate:** ≥ 75% (3/4 pass QA on first attempt).
- **Target Bug-Fix Tax:** 1/4 = 25% (BUG-003 is the planned bug — pre-existing test debt, not a regression from this sprint's new code).
- **Target Enhancement Tax:** 0 (no scope creep — anything past the §1 list goes to S-16; BUG-001 nav polish ships as a side PR if velocity allows).
- **Token budget:** no formal cap; Reporter aggregates post-hoc. Remember to write `.cleargate/sprint-runs/.active = SPRINT-15` at kickoff. Token-ledger hook still not built — third sprint without cost capture; Reporter notes this in REPORT Meta.

## 7. Out-of-Scope (deliberate)

- **STORY-024-02 background worker locks — RETIRED, not deferred.** R1 (wiki_ingest_cron RPC swap) shipped at commit `bd2b8a4` (2026-04-21) alongside STORY-024-01 + STORY-024-03. R3 (try/except → 'error' reset) is in place at `wiki_ingest_cron.py:251–256`. R2 (apply same refactor to `drive_sync_cron.py`) targets a query that doesn't exist — `drive_sync_cron` walks Drive-source rows to detect content changes and is **not** a pending-doc claim queue. The race condition R2 imagined doesn't apply (worst case: two redundant idempotent Drive API reads + matching hash). EPIC-024 is functionally complete; pre-sprint hygiene closes it on paper.
- **BUG-001** nav glassmorphism polish — P3 visual polish, `approved: false`. Side PR mid-sprint if bored, otherwise S-16.
- **STORY-018-08 scenario-S4 test** (missing `tz` field path) — P3, ~15 min. Fold into S-16's first commit.
- **Root-cause lifespan fix** (env-gated cron disable in tests) — deliberately deferred by STORY-024-05 §1.3; lands as a CR if the bypass pattern proves insufficient. Not yet.
- **EPIC-017 Phase B** (wiki synthesis pages — `create_wiki_page` agent tool) — high-leverage but a separate sprint of work. Earliest S-16 / S-17.
- **EPIC-014 drag-and-drop** — STORY-014-03 §1.3 explicitly defers; click-to-select only for v1.
- **EPIC-014 multi-file upload** — same — single file per click.
- **Token-ledger hook** — third sprint without cost capture; still backlogged. Reporter will flag again.

---

## ClearGate Readiness Gate

**Current Status: 🟢 Approved + Active.** Human approved 2026-04-25 via "kickoff".

- [x] Scope ≤ 4 items, all 🟢 ambiguity at entry.
- [x] Each item has a reachable parent (EPIC-014 for 014-0x, EPIC-007 for BUG-003).
- [x] Red-zone surfaces identified (none) and shared surfaces warned (§4).
- [x] Dependencies documented with explicit blocker columns.
- [x] Pre-sprint hygiene block enumerated (§1) — closes EPIC-024 by docs, not code.
- [x] sync_status risk resolved during planning (verified `agent.py:1004` — no filter).
- [x] **Human approval** — 2026-04-25 ("kickoff").
