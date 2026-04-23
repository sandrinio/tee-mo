# Improvement Suggestions (post S-01)
> Generated: 2026-04-10. Review each item. Approved items are applied by the Lead at sprint boundary.
> Rejected items go to `.vbounce/improvement-log.md` with reason.
> Applied items go to `.vbounce/improvement-log.md` under Applied.

## Impact Levels

| Level | Label | Meaning | Timeline |
|-------|-------|---------|----------|
| **P0** | 🔴 Critical | Blocks agent work or causes incorrect output | Fix before next sprint |
| **P1** | 🟠 High | Causes rework — bounces, wasted tokens, repeated manual steps | Fix this improvement cycle |
| **P2** | 🟡 Medium | Friction that slows agents but does not block | Fix within 2 sprints |
| **P3** | ⚪ Low | Polish — nice-to-have, batch with other improvements | Batch when convenient |

## Summary

| Source | Count |
|--------|-------|
| Retro (§5 findings) | 0 |
| Lesson → Automation | 0 |
| Effectiveness checks | 0 |
| Metric-driven | 0 |
| **Total** | **1** |

| Impact | Count |
|--------|-------|
| 🔴 P0 Critical | 0 (1 applied 2026-04-12) |
| 🟠 P1 High | 0 |
| 🟡 P2 Medium | 0 |
| ⚪ P3 Low | 1 |

---

### 1. [⚪ P3 Low] [Health] Run vbounce doctor
Verify the V-Bounce Engine installation is healthy after this sprint.

**Target:** `.vbounce/scripts/doctor.mjs`
**Effort:** Trivial

---

### 2. [🔴 P0 Critical] [Script Bug] `complete_story.mjs` corrupts sprint plan table cells — **✅ APPLIED 2026-04-12**

**Discovered:** 2026-04-12 during S-04 STORY-005A-01 completion (first Fast Track story of the sprint).

**Symptoms:** After running `./.vbounce/scripts/run_script.sh complete_story.mjs STORY-005A-01 --qa-bounces 0 --arch-bounces 0 --correction-tax 5 --notes "..."`, the sprint plan at `product_plans/sprints/sprint-04/sprint-04.md` had the following corruption:
1. **§1 Active Scope** — rows for STORY-005A-03, -04, -05 had their story-name/link column replaced with the literal string `Done`.
2. **§2 Merge Ordering** — the `Reason` column header was replaced with `Done`, AND the order number cell for row 2 (`2 | STORY-005A-02 OR STORY-005A-03`) was replaced with `Done`.
3. **§2 Execution Mode** — the Architect-Override cell for STORY-005A-01 (which was `—`) was replaced with `Done`.
4. **§2 Dependency Chain** — the `Reason` column header was replaced with `Done`, AND the Story-column cells for STORY-005A-03 and STORY-005A-05 were replaced with `Done`.
5. **§3 Sprint Open Questions** — the `Options` column header was replaced with `Done`.
6. **§4 Execution Log** — the placeholder row for STORY-005A-01 had one of its `_pending_` cells (Tests-Written column) replaced with `Done` instead of being populated with the real test count. Additionally, a DUPLICATE row for STORY-005A-01 was appended at the bottom of the table with the completion data, but missing the Tests-Written column entirely (pipe alignment off by one).

**Evidence:** Team Lead recovered all 6 sections manually in commit-pending state during the S-04 Phase 2 handoff. The git diff showed the corruption was a single `write_text(...)` from `complete_story.mjs` — not a subsequent edit.

**Probable root cause:** The script appears to do broad string/regex replacement of table-cell patterns with `Done`, targeting more than the intended Active-Scope "V-Bounce State" column and the Execution Log row. It seems to hit any table cell that starts with certain patterns (e.g. column-N cells, header words ending in `?` or column headers `Reason`/`Options`). The Execution Log update ALSO fails to locate the existing placeholder row and instead appends a new row with wrong column count.

**Impact:** P0 — this blocks every sprint that uses `complete_story.mjs`. Without the hand-patch, subsequent stories will inherit corrupted state, DevOps merges will fail to update §4 correctly, and the sprint report generator will choke on the malformed execution log at sprint close. S-03 may have also been affected but went unnoticed; worth auditing.

**Target:** `.vbounce/scripts/complete_story.mjs`

**Suggested fix approach:**
1. Replace free-form regex/string substitution with a proper markdown-table parser (e.g. the existing table readers in `.vbounce/scripts/constants.mjs` if any, otherwise a minimal row-by-row split on `|`).
2. Scope the "V-Bounce State → Done" rewrite to ONLY the §1 Active Scope row whose Story cell matches the story ID passed on the CLI. Do not touch any other table in the document.
3. Scope the §4 Execution Log update to REPLACE the existing placeholder row whose first cell equals the story ID (do not append). Populate ALL 7 columns (Story, Final State, QA Bounces, Arch Bounces, Tests Written, Correction Tax, Notes) — the current version appends 6 cells and breaks alignment.
4. Add a golden-file test: run `complete_story.mjs` against a fixture sprint plan and diff the result against an expected output. This would have caught the regression immediately.
5. Audit previous sprint plans (S-02, S-03) in `product_plans/archive/` for similar corruption and fix them retroactively.

**Effort:** Medium (half day — parser + test + audit).

**Blocks:** subsequent S-04 story completions (005A-02..06). Team Lead is working around by hand-patching after each call for S-04, but this is unsustainable and should be fixed before S-05 starts.

**✅ Fix applied 2026-04-12** (post-S-04 release):
- Rewrote `.vbounce/scripts/complete_story.mjs` with two dedicated helpers: `updateActiveScope()` (identifies §1 by its "V-Bounce State" + "Priority" + "Blocker" header signature, splits rows on `|`, mutates cell index 4 in-place for the one matching row) and `updateExecutionLog()` (detects 6-col vs 7-col layout by parsing the header, finds the existing row for the story by first-cell match, replaces in place instead of appending). No more `[^|]*` regex, no more `/g` flag, no more cross-row spanning.
- Added golden-file test at `.vbounce/scripts/__tests__/complete_story.test.mjs` with input fixture `sprint-test-input.md` and expected fixture `sprint-test-expected.md`. Test builds a throwaway sandbox, runs the script, byte-compares output. Asserts: (1) §1 row updated, (2) OTHER tables untouched (Merge Ordering, Dependency Chain, Open Questions headers all preserved), (3) §4 placeholder replaced in-place (not appended), (4) state.json updated, (5) unrelated stories in state.json not mutated.
- Script also now searches both `product_plans/sprints/` and `product_plans/archive/sprints/` for the sprint plan (useful for post-release completions).
- Audit of S-02/S-03 archived plans deferred — the corruption pattern damaged live sprint state but archived sprint plans were written manually or by the doc-manager, not by `complete_story.mjs`, so there's no retroactive damage to fix.

---

## How to Apply
- **Approve** → Lead applies change, records in `.vbounce/improvement-log.md` under Applied
- **Reject** → Record in `.vbounce/improvement-log.md` under Rejected with reason
- **Defer** → Record in `.vbounce/improvement-log.md` under Deferred

> Framework changes (.claude/agents/, .vbounce/skills/, .vbounce/templates/) are applied at sprint boundaries only — never mid-sprint.
> Use `/improve` skill to have the Team Lead apply approved changes with brain-file sync.