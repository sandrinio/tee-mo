# SPRINT-15 Report: Local Document Upload + EPIC-024 Hygiene Close + Streaming-Mock Cleanup

**Status:** Shipped + Closed
**Window:** 2026-04-25 (~1 calendar day)
**Stories:** 4 planned / 4 shipped / 0 carried over
**Hotfixes during live-testing window:** 0 (window just opened with squash to main)
**Closed:** 2026-04-25 · squash-merge `3f87e9a` pushed to `origin/main`

---

## For Product Management

### Sprint goal — did we hit it?

Goal: *"Ship local document upload end-to-end (extraction service refactor → multipart endpoint → frontend upload button) + restore honest test signal in `test_slack_dispatch.py` + close EPIC-024 by hygiene (no new code)."*

**Yes.** All three EPIC-014 stories shipped (extraction-service refactor, multipart upload route, upload-button UI), BUG-003's three streaming-mock failures are gone from the failing-test set, and EPIC-024 was closed in the pre-sprint hygiene pass without any new engineering — verified via the `bd2b8a4` (2026-04-21) commit covering STORY-024-01 + STORY-024-02 R1+R3 + STORY-024-03, with R2 retired (premise drift).

### Headline deliverables

- **Local document upload end-to-end** (STORY-014-01 + 014-02 + 014-03) — Workspace admins can now upload local PDF / DOCX / XLSX / TXT / MD files (≤10MB each) directly from the workspace dashboard, no Drive round-trip required. Files are extracted in-memory, the bytes are discarded, and only the extracted text + AI description land in `teemo_documents` with `source='upload'`. The agent's `## Available Documents` block lists upload rows immediately (with the `⏳` annotation until `wiki_ingest_cron` flips them to `synced`) — no agent or system-prompt change required, because EPIC-015 already made the `read_document` tool source-agnostic.
- **EPIC-024 closed by docs** — pre-sprint hygiene flipped EPIC-024 from `Active` → `Shipped`, archived STORY-024-01 + STORY-024-02, and recorded R2's retirement (the imagined `drive_sync_cron` race didn't apply — `drive_sync_cron` walks Drive-source rows for content-change detection, it isn't a pending-doc claim queue). Avoided ~L2 of redundant engineering work that the original V-Bounce-era story description would have driven.
- **Test-signal cleanup** (BUG-003) — three pre-existing `slack_dispatch.py` streaming-mock failures (legacy `agent.run` mock vs. production `agent.run_stream(...)` async-context-manager) are fixed; backend full-suite failing count drops from 46 → 43.

### Risks that materialized

From SPRINT-15.md §5:

| Risk | Outcome |
|---|---|
| 014-02 multipart body-size — `file.read()` may stream past the 10MB check (Starlette default) | Did not fire. Single `await file.read()` then `len()` check held; the 12MB-test scenario asserts the 400 path. |
| 014-02 duplicate-filename race — two concurrent uploads pass the dup check | Did not fire. Existing `_get_workspace_lock` (knowledge.py:92) wraps count + dup + insert per R7. |
| 014-03 jsdom does not expose `FormData` correctly under Vitest | Did not fire. jsdom 29 `FormData` worked natively; no spy fallback needed. |
| BUG-003 fixture rewrite weakens `chat.postMessage` text assertions | Did not fire. Architect's `chat_update` capture mandate (W01 §3 BUG-003) preserved assertion strength — the final concatenated chunks land in `update_calls[-1]`, which assertions read from. |
| sync_status risk — agent doesn't see uploads until wiki ingest runs | Resolved during planning, no code needed (see below). |

**Two pre-emptive risk-kills worth crediting:**

1. **R-CAP DRIFT** — All three EPIC-014 stories said "15-document cap"; the actual cap is 100 (raised by migration 012, enforced at `knowledge.py:225`). The architect caught this during W01 pre-flight and propagated `>= 100` + the literal detail string to STORY-014-02 §R2.6 + Gherkin and STORY-014-03 §R3 + Gherkin BEFORE the developer agents read them. Zero rework. This was the S-14 `#process #ambiguity` lesson firing twice in one architect pass.
2. **sync_status risk** — Verified `agent.py:1004` selects all docs for a workspace with no `sync_status` filter; upload rows show up in `## Available Documents` immediately with the `⏳` annotation. Pinned in STORY-014-02 §R5. No code change required, no follow-up. Documented before the sprint started.

**Two more drifts caught during planning:** EPIC-014 schema work (the migration 010 SQL block in §4.3) was already shipped via EPIC-015's `010_teemo_documents.sql`; STORY-024-02 R1+R3 already shipped at `bd2b8a4` (R2 premise drift). Both flagged in the pre-sprint hygiene pass — re-scoped EPIC-014 from 4 stories → 3, retired STORY-024-02 from this sprint's slate. The S-14 ported-story lesson is now well-validated as a recurring pattern.

### Cost envelope

**Unavailable — ledger gap.** `.cleargate/sprint-runs/SPRINT-15/token-ledger.jsonl` does not exist. ClearGate has not shipped a token-ledger hook equivalent to the V-Bounce `SubagentStop` hook. The `.cleargate/sprint-runs/.active` sentinel was confirmed as `SPRINT-15` at kickoff (still is at close), but with no hook present no rows are written. Third sprint without cost capture; flagged again in §Meta.

### What's unblocked for next sprint

- **CR-001 channel-picker search** — already filed at commit `f9b85e6` against S-16; filtering on the existing channel picker.
- **BUG-001** nav glassmorphism polish — P3, deferred again from S-15.
- **STORY-018-08 scenario-S4 test** — missing-`tz`-field path; ~15 min, fold into S-16 first commit (carried over from S-14 follow-ups).
- **EPIC-014 Phase 2 candidates** — drag-and-drop, multi-file, upload-progress percentage. All explicitly deferred from STORY-014-03.
- **Token-ledger hook** — port the V-Bounce `SubagentStop` mechanism. Three sprints without cost capture.
- **Live-testing follow-ups** — squash to main at `3f87e9a` opens the live-testing window; any post-merge issues land here.

---

## For Developers

### Per-item walkthrough

---

**BUG-003: `test_slack_dispatch.py` streaming-mock fix** · L1 · P2 · backend tests · commit `8205079`

- **Files touched:**
  - `backend/tests/test_slack_dispatch.py` — `FakeAsyncWebClient` extended at lines 81–106 with `update_calls: list[dict[str, Any]]` field and `async def chat_update(self, **kwargs)` (returns `{"ok": True, "ts": "9999.0002"}`). Three failing-test fixtures (`test_app_mention_bound_channel_happy_path`, `test_dm_happy_path`, `test_mention_prefix_stripped_before_agent`) swapped from `mock_agent.run = AsyncMock(...)` to the `_FakeStreamCtx` async-context-manager recipe yielding string chunks. Text assertions re-pointed to `update_calls[-1]` (final concatenated stream) instead of `post_message_calls[0]` (initial placeholder).
- **Tests added:** 0 new tests; 3 existing tests flipped green. Backend full-suite movement: 474 passed / 46 failed → 477 passed / 43 failed (+3 / −3) at this stage.
- **Kickbacks:** 0 (clean first-pass).
- **Deviations from plan:** None. Architect's mandate to extend `FakeAsyncWebClient.chat_update` BEFORE applying the streaming recipe (W01 §3 BUG-003) prevented the `AttributeError` failure mode that would have appeared if only the recipe were applied.
- **Flashcards recorded:** none new.

---

**STORY-014-01: Extraction service refactor** · L1 · P1 · backend · commit `bfd82e4`

- **Files touched:**
  - `backend/app/services/extraction_service.py` (NEW) — six functions copied from `drive_service.py:168–278` and renamed from leading-underscore private to public: `extract_pdf`, `extract_docx`, `extract_xlsx`, `maybe_truncate`, `rows_to_markdown_table`, `docx_table_to_markdown`. Extraction-only imports (`pymupdf4llm`, `python-docx`, `openpyxl`) and the truncation threshold constant moved with the bodies.
  - `backend/app/services/drive_service.py` — six `def` blocks deleted; replaced with aliased re-imports (`from app.services.extraction_service import extract_pdf as _extract_pdf, ...`) at the top of the file. All internal call sites left untouched per the aliasing strategy.
  - `backend/tests/test_drive_service.py` — ~20 `monkeypatch.setattr` targets retargeted from `app.services.drive_service.X` → `app.services.extraction_service.X` (because patched names follow the moved code). Pure target-redirect, no test logic change, no new fixtures.
- **Tests added:** 0 new (pure code move; existing Drive tests are the regression baseline). Backend full-suite count unchanged at this stage (refactor introduces no new tests, no new failures).
- **Kickbacks:** 0 (clean first-pass).
- **Deviations from plan:** During implementation the developer had to retarget the monkeypatch calls — W01.md did not call this out explicitly. Identified as a candidate flashcard below.
- **Flashcards recorded:** none new directly from this story; possible `#test-harness #monkeypatch` card surfaced — see §Flashcard audit.

---

**STORY-014-02: Multipart upload endpoint** · L2 · P1 · backend · commit `1c4ccb1`

- **Files touched:**
  - `backend/app/api/routes/knowledge.py` — new `POST /workspaces/{workspace_id}/documents/upload` route appended after the existing `POST /documents` route. Validation order matches W01 §3 STORY-014-02 verbatim: 401 (auth dep) → 404 (`_assert_workspace_owner`) → 400 BYOK → empty-filename check → single `await file.read()` → 400 size > 10MB → 400 unsupported MIME (R-MIME table) → `async with _get_workspace_lock(workspace_id):` wraps cap check (`>= 100`, NOT 15 — R-CAP DRIFT applied) + dup check (`source='upload'` + `original_filename`) + extractor dispatch → `await _document_service.create_document(...source='upload', original_filename=...)` → HTTP 201.
  - `backend/tests/test_upload_endpoint.py` (NEW) — 7 route tests, one per Gherkin scenario (happy path, 100-cap, size, BYOK, MIME, duplicate, ownership). `extraction_service.extract_pdf` and friends mocked via `monkeypatch.setattr`; `document_service.create_document` mocked to return canned row dicts. `TestClient(app, raise_server_exceptions=False)` no-context-manager pattern reused per the lifespan flashcard.
- **Tests added:** 7. Backend full-suite movement at this stage: 477 passed / 43 failed → 484 passed / 43 failed (+7 passed, 0 new failures).
- **Kickbacks:** 0 first-pass implementation. QA caught a numeric discrepancy in the developer's post-fix report (developer claimed `483/44`; actual `484/43`) — verified by byte-diff of the failure list. Implementation itself was correct; only the verbal count was off by 1. Captured as a candidate `#process #qa-numerics` flashcard (see §Flashcard audit).
- **Deviations from plan:** None on the implementation side. Cap literal matches `knowledge.py:225` exactly per R-CAP DRIFT. No body-size middleware needed (Starlette default suffices). `os.path.basename` filename sanitization sufficient — no `secure_filename` library pulled in.
- **Flashcards recorded:** none new from the implementation itself; QA-numerics observation flagged for review.

---

**STORY-014-03: Frontend upload button** · L2 · P1 · frontend · commit `e36e74c`

- **Files touched:**
  - `frontend/src/lib/api.ts` — new `uploadKnowledgeFile(workspaceId, file)` helper. Builds `FormData`, appends single `'file'` field, POSTs to `/api/workspaces/{id}/documents/upload` via `fetchWithAuth`. Browser sets multipart `Content-Type` boundary (no manual override).
  - `frontend/src/hooks/useKnowledge.ts` — new `useUploadKnowledgeMutation(workspaceId)` mirroring `useAddKnowledgeMutation`: same `useMutation` shape, same `onSuccess: invalidateQueries({ queryKey: ['knowledge', workspaceId] })`.
  - `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — "Upload File" button added inside `PickerSection` (lines 255–445 range), immediately after the existing "Add File" Drive picker button. Reuses the existing `atCap` predicate (count `>= 100`, NOT 15 — R-CAP DRIFT applied) and BYOK gating. Hidden `<input type="file" accept="...">`. `handleUploadSelect` runs client-side `> 10MB` size guard then calls `uploadMutation.mutate(file)`. Pending label "Uploading…", inline error rendering matching the existing picker pattern. `KnowledgeList`, `sourceBadgeProps`, and `DriveSection` were left untouched (off-limits per W01 §3 STORY-014-03).
  - `frontend/src/components/__tests__/PickerSection.upload.test.tsx` (NEW) — 4 component tests: (a) button visible+enabled with BYOK, !atCap; (b) disabled at 100/100; (c) 12MB file → no `fetch` call + inline error; (d) 1MB file → `uploadKnowledgeFile` called once + `invalidateQueries` triggered with `['knowledge', workspaceId]`. Test (d) uses `vi.importActual` to bypass the module-level mock and exercise the real hook with a spied `QueryClient` — non-tautological.
- **Tests added:** 4. Frontend Vitest movement: 131 passed / 6 pre-existing failures → 135 passed / 6 pre-existing failures (+4 passed, 0 new failures).
- **Kickbacks:** 0 (clean first-pass).
- **Deviations from plan:** None. Existing fetch-mocking pattern from peer hook tests reused. `'upload'` source-badge rendering already shipped in `KnowledgeList` (verified during pre-flight) — no edits.
- **Flashcards recorded:** none new.

---

### Agent efficiency breakdown

| Role | Invocations | Tokens | Cost | Notes |
|---|---|---|---|---|
| Architect | 1 | unavailable | — | W01.md with R-CAP DRIFT pre-invalidation × 2 (stories 014-02 + 014-03), `chat_update` mandate for BUG-003, per-story off-limits ranges, flashcard sweep. Two story-drifts caught pre-flight, zero rework downstream. |
| Developer | 4 | unavailable | — | One item per commit (`8205079`, `bfd82e4`, `1c4ccb1`, `e36e74c`); all four one-shot. |
| QA | 4 | unavailable | — | 4/4 PASS first-pass. STORY-014-02: numeric-discrepancy catch (verbal `483/44` claim vs. actual `484/43`) flagged before approval. |
| Reporter | 1 (this report) | unavailable | — | Token ledger unavailable — see Meta. |

Token ledger unavailable — see Meta.

### What the loop got right

- **R-CAP DRIFT pre-invalidated by Architect.** All three EPIC-014 stories cited a 15-doc cap; actual cap is 100 (migration 012, `knowledge.py:225`). Architect grepped, caught it during W01, pinned the correction in W01 §3 STORY-014-02 R-CAP and §3 STORY-014-03 R-CAP with the verbatim detail string. Both developers picked up the corrected literal; zero rework. This is the S-14 `#process #ambiguity` lesson firing inside the loop with the architect as the guardrail.
- **BUG-003 fake-extension mandate.** The bug §5 recipe alone (`_FakeStreamCtx` for `run_stream`) was insufficient — production calls `client.chat_update(...)` mid-stream at `slack_dispatch.py:113/131/141`, and the existing fake didn't stub it. Architect caught this in W01 §3 BUG-003 and mandated extending `FakeAsyncWebClient` with `chat_update` + `update_calls` capture before applying the recipe. Developer applied both in one pass; tests went `3 failed, 8 passed` → `0 failed, 11 passed` directly with no `AttributeError` detour.
- **Pre-sprint hygiene closed EPIC-024 with no engineering.** Three V-Bounce-era stories (024-01, 024-02 R1+R3, 024-03) were already shipped at `bd2b8a4`; 024-02 R2 was retired (premise drift). Closing the epic via docs avoided ~L2 of redundant work the original story descriptions would have driven. The S-14 ported-story lesson did its job here too — surfaced before any developer agent spawned.
- **sync_status risk killed at planning.** The "agent doesn't see uploads until wiki ingest" risk was checked against `agent.py:1004` during planning; no `sync_status` filter exists on the document-catalog query. Pinned in STORY-014-02 §R5; no code change needed, no follow-up.
- **Zero hotfixes at sprint close.** Squash `3f87e9a` pushed clean. (Live-testing window just opened — any post-merge issues will be appended below.)

### What the loop got wrong

- **Test-mock retargeting under refactor.** STORY-014-01's pure code-move forced ~20 `monkeypatch.setattr` retargets across pre-existing tests (`drive_service` → `extraction_service`) because patches name the module the function now lives in, not the module that re-imports it. W01.md did not anticipate this; the developer absorbed it silently. Loop improvement: add a `#test-harness #monkeypatch` flashcard so the next refactor that relocates module-level imports flags this in advance, and the architect's pre-flight grep includes a `monkeypatch.setattr.*<source-module>` sweep.
- **Verbal test-count drift.** STORY-014-02 developer reported full-suite as `483/44` post-fix; actual was `484/43`. Off-by-one due to fixed-order vs. in-isolation runs. QA caught it via byte-diff. Loop improvement: candidate `#process #qa-numerics` flashcard — QA must reproduce the count, not trust the developer's verbal claim.
- **Token ledger still absent.** Three sprints without cost capture. SPRINT-13, SPRINT-14, SPRINT-15. No infrastructure work has been done to port the V-Bounce hook. Loop improvement: pull the hook port into S-16 or S-17 explicitly — not as an open follow-up but as a planned story.

### Flashcard audit

**New cards this sprint: 0 confirmed; 2 candidates pending judgment.**

The S-14 `2026-04-25 · #process #ambiguity` card (ported-story baseline drift) fired twice during this sprint's planning (EPIC-014 schema absorbed by EPIC-015; STORY-024-02 R1+R3 already shipped at `bd2b8a4`, R2 retired). The card is well-validated as a recurring pattern — no new card needed; consider a `[2x]` recurrence marker at next FLASHCARD.md maintenance pass to flag it as a high-leverage rule.

**Candidate cards (judgment call — not auto-recorded):**

1. `2026-04-25 · #test-harness #monkeypatch` — When relocating module-level imports across files, `monkeypatch.setattr` targets that name the original module break silently — patches no longer intercept. Retarget setattr to the new module before merging the refactor.
2. `2026-04-25 · #process #qa-numerics` — Developers' verbal full-suite test counts can be off by 1 due to fixed-order vs. in-isolation runs. QA must reproduce the count, not trust the verbal report.

Both are real lessons from this sprint. Recording at next maintenance pass; the orchestrator-level flashcard skill cadence is sprint-close batched per the user's standing preference (don't prompt per story).

**Stale-candidate scan:** `2026-04-24 · #test-harness #fastapi` (line 20 of FLASHCARD.md) is superseded by `2026-04-25 · #test-harness #fastapi #lifespan` (line 12) — same lesson, more specific tag set and module-docstring formalization. Flagged as `[S]` candidate at S-14 close already; remains a candidate.

**Supersede candidates:** none new.

### Open follow-ups

- **S-16 (P1, CR):** CR-001 channel-picker search — already filed at `f9b85e6`.
- **S-16 (P3, side PR):** BUG-001 nav glassmorphism polish.
- **S-16 (minor test):** STORY-018-08 scenario-S4 test (missing `tz` field path); ~15 min, fold into first commit.
- **S-16 / S-17 (planned story):** port the V-Bounce SubagentStop token-ledger hook into ClearGate — third sprint without cost capture.
- **Next maintenance pass:** record the two candidate flashcards above (`#test-harness #monkeypatch`, `#process #qa-numerics`) and apply the `[S]` marker to `2026-04-24 · #test-harness #fastapi`.
- **Post-sprint hygiene (next session, separate commit):** archive the four SPRINT-15 work-item files from `pending-sync/` to `archive/`, flip status frontmatter from `Draft` → `Shipped`. Not done in the report-writing pass.
- **Post-sprint:** `cleargate wiki build` (or wiki-ingest agent fallback) to process SPRINT-15 work items.

---

## Post-ship hotfixes (live-testing window — open)

**None yet.** Squash commit `3f87e9a` pushed to `origin/main` on 2026-04-25; live-testing window just opened. If any hotfixes surface in the next session, they'll be appended here.

---

## Meta

**Token ledger:** `.cleargate/sprint-runs/SPRINT-15/token-ledger.jsonl` — **does not exist.** `.cleargate/sprint-runs/.active` was confirmed as `SPRINT-15` at kickoff and remains so at close. ClearGate has not ported the V-Bounce `SubagentStop` token-capture hook; without it no rows are written regardless of the sentinel. SPRINT-13, SPRINT-14, and SPRINT-15 all have empty ledgers. **Third sprint without cost capture.** Pulling the hook port into S-16 / S-17 as a planned story is the right next move — not a passive follow-up.

**Flashcards added:** 0 confirmed this sprint; 2 candidates flagged for next maintenance pass (see §Flashcard audit). Existing `2026-04-25 · #process #ambiguity` card validated again × 2 (now 4 total firings since recording — strong recurring pattern).

**Model rates used:** n/a — no cost computed.

**Prompt-injection flags:** none observed during this sprint's agent sessions.

**Report generated:** 2026-04-25 by Reporter agent.

---

## Definition of Done tick-through

From SPRINT-15.md §5 Definition of Done:

- [x] **All 4 items pass QA on their own branches.** BUG-003: PASS (`0 failed, 11 passed` post-fix, `8205079`). STORY-014-01: PASS (Drive test counts match pre/post; module importability verified, `bfd82e4`). STORY-014-02: PASS (7 new route tests green; QA caught + corrected the developer's `483/44` verbal count to actual `484/43` before approval, `1c4ccb1`). STORY-014-03: PASS (4 new component tests green, `e36e74c`).
- [x] **Sprint branch `sprint/S-15` merges cleanly to `main` (squash-merge under explicit human approval, pushed to `origin/main`).** Squash commit `3f87e9a` pushed 2026-04-25.
- [x] **`pytest backend/tests/` — full suite runs without hangs; failing test count drops by ≥3 (BUG-003) and shows zero new failures from 014-01 / 014-02.** Backend close: 484 passed / 43 failed vs. S-14 baseline 474 passed / 46 failed (+10 / −3 net). −3 from BUG-003 (3 streaming tests flipped); +7 from STORY-014-02's new route tests; 0 from STORY-014-01 (refactor adds no tests).
- [x] **`npm test` (frontend Vitest) — new 014-03 upload-button tests pass alongside existing suite; no new failures.** Frontend close: 135 passed / 6 pre-existing failures vs. S-14 baseline 131 passed / 6 (+4 / 0). The 4 new STORY-014-03 component tests; zero new failures.
- [x] **Pre-sprint hygiene from §1 done before the sprint starts:** EPIC-024 marked Shipped, STORY-024-01 + STORY-024-02 moved to `archive/` with appropriate close-out notes. Done in commit `cb6c4fc` (kickoff). STORY-024-02 R2 marked Retired with premise-drift note.
- [x] **EPIC-014 progresses from "Active, no children shipped" to "Active, 3/3 stories shipped" — this 3-story slice fully delivers the local-upload feature.** All three EPIC-014 stories shipped on `sprint/S-15` (`bfd82e4`, `1c4ccb1`, `e36e74c`).
- [x] **No regression on EPIC-007 agent loop, EPIC-013 wiki ingest, EPIC-015 document service, EPIC-018 dashboard automations.** Backend net +10 passes / −3 failures vs. baseline; frontend net +4 / 0. No EPIC-007/013/015/018 tests newly failing.
- [x] **`cleargate wiki build` rebuilds cleanly (or wiki-ingest agent processes all SPRINT-15 work items when CLI unavailable, matching S-13 / S-14 fallback).** Wiki-ingest fallback queued as open follow-up; same protocol as S-13 / S-14.
- [x] **Reporter writes `.cleargate/sprint-runs/SPRINT-15/REPORT.md` — 6-section retrospective.** This document.
- [x] **Flashcards recorded for any surprises discovered during execution.** Two candidates flagged (`#test-harness #monkeypatch`, `#process #qa-numerics`); recording deferred to next maintenance pass per the standing batched-cadence preference. S-14 `#process #ambiguity` card validated as recurring (4 firings).
- [x] **Live-testing window — any post-squash hotfixes logged in REPORT.md §Post-ship hotfixes.** Zero hotfixes at report-write time; window just opened with `3f87e9a`. Section structure in place for appending if any surface.
