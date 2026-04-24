# Migration Port Map: V-Bounce → ClearGate

**Companion to:** `MIGRATION_CLEARGATE.md`
**Scope:** ~160 planning documents to transform. Covers Phases 7.1–7.7 of the migration.

---

## Locked decisions

1. **Design Guide** (`tee_mo_design_guide.md`) → goes into the ClearGate wiki. Target placement TBD post-install (likely `.cleargate/knowledge/design-guide.md` so the session-start reader picks it up, or as a standing `PROPOSAL-002-design-system` so `wiki build` auto-ingests it into `wiki/proposals/`). Verify after `cleargate init`.
2. **Per-story V-Bounce dev/QA/devops/arch reports** (~42 files) → not ported. Left in `.vbounce-archive/archive/` as historical record. Git history + commits are the primary audit trail.
3. **Sprint contexts** (12 files) → lift only *Locked Dependencies* + *Relevant Lessons* into the corresponding ClearGate Sprint Plan §0. Everything else stays in `.vbounce-archive/`.
4. **S-12** → transfer as-is. `status: Active`, lives in `pending-sync/` until closed.
5. **Active epics (11)** → all go to `pending-sync/`. Differentiation via frontmatter (`status`, `ambiguity`), not physical path. Archived epics (7 shipped) go to `archive/`.

---

## Source → target mapping

| Source | Target | Status | Template |
|---|---|---|---|
| `product_plans.vbounce-archive/strategy/tee_mo_charter.md` | `.cleargate/delivery/archive/PROPOSAL-001-teemo-platform.md` | `approved: true`, `status: Shipped` | `proposal.md` |
| `tee_mo_roadmap.md` | `.cleargate/delivery/INDEX.md` (content), plus `PROPOSAL-001` context | — | INDEX (free-form curated table) |
| `tee_mo_design_guide.md` | `.cleargate/knowledge/design-guide.md` *(provisional — verify post-install)* | — | — (reference doc) |
| `product_plans.vbounce-archive/backlog/EPIC-*/EPIC-*.md` (10 active) | `.cleargate/delivery/pending-sync/EPIC-XXX-short-name.md` | `status: Draft\|Ready\|Active`, `ambiguity: 🔴\|🟡\|🟢` | `epic.md` |
| `product_plans.vbounce-archive/archive/epics/EPIC-*/EPIC-*.md` (7 archived) | `.cleargate/delivery/archive/EPIC-XXX-short-name.md` | `status: Shipped`, `approved: true` | `epic.md` |
| Active stories inside each EPIC dir (14) | `.cleargate/delivery/pending-sync/STORY-XXX-YY-short-name.md` | `status: Ready` (mostly); `ambiguity: 🟢` (mostly) | `story.md` |
| Archived stories inside `product_plans.vbounce-archive/archive/epics/*/STORY-*.md` (~53) | `.cleargate/delivery/archive/STORY-XXX-YY-short-name.md` | `status: Shipped` | `story.md` |
| `product_plans.vbounce-archive/sprints/sprint-12/sprint-12.md` | `.cleargate/delivery/pending-sync/SPRINT-12.md` | `status: Active` | `Sprint Plan Template.md` |
| `product_plans.vbounce-archive/archive/sprints/sprint-XX/sprint-XX.md` (11) | `.cleargate/delivery/archive/SPRINT-XX.md` | `status: Shipped` | `Sprint Plan Template.md` |
| `.vbounce-archive/sprint-report-S-XX.md` (7: S-02, 03, 04, 06, 08, 09, 12) | `.cleargate/sprint-runs/SPRINT-XX/REPORT.md` | — | `sprint_report.md` (6-section) |
| `.vbounce-archive/sprint-context-S-XX.md` (12) | Extract *Locked Deps* + *Relevant Lessons* into corresponding `SPRINT-XX.md` §0; drop rest | — | — (extraction, no new file) |
| `product_plans.vbounce-archive/hotfixes/HOTFIX-20260421-NavAesthetics.md` | `.cleargate/delivery/pending-sync/BUG-001-nav-aesthetics.md` | `status: Ready` | `Bug.md` |
| `FLASHCARDS.vbounce-archive.md` (32 cards) | `.cleargate/FLASHCARD.md` | one-liner format, `#tags` | flashcard protocol |
| `.vbounce-archive/archive/S-XX/STORY-*/STORY-*-{dev,qa,devops,architect}.md` (~42) | **Not ported.** Stay in `.vbounce-archive/` as historical. | — | — |

---

## Frontmatter translation tables

### Epic (V-Bounce → ClearGate)

| V-Bounce field | ClearGate field | Notes |
|---|---|---|
| `epic_id` | `epic_id` | Keep as-is (`EPIC-024`) |
| `status: "Draft"` / `"Backlog"` | `status: "Draft"` | |
| `status: "Active"` | `status: "Active"` | |
| `status: "Done"` / `"Completed"` | `status: "Shipped"` + `approved: true` | For archived epics |
| `ambiguity: "🟢 Low"` | `ambiguity: "🟢"` | Glyph only; ClearGate drops qualifier |
| `ambiguity: "🟡 Medium"` | `ambiguity: "🟡"` | |
| `ambiguity: "🔴 High"` | `ambiguity: "🔴"` | |
| `context_source` | `context_source: "PROPOSAL-001"` | Point to Charter proposal by default |
| `release` | — | Drop; roadmap content lives in INDEX.md |
| `owner` | `owner` | Keep |
| `priority` | — | Drop; sequence via sprint plans + INDEX |
| `tags: [...]` | — | Drop (ClearGate uses wiki topics, not epic tags) |
| `target_date` | `target_date` | Keep |
| — | `created_at`, `updated_at` | Stamp from git blame/log, or leave for `stamp-and-gate.sh` hook |
| — | `pushed_at`, `pushed_by`, `source` | MCP sync fields; leave blank (local-only install) |

### Story

| V-Bounce field | ClearGate field | Notes |
|---|---|---|
| `story_id` | `story_id` | Keep (`STORY-024-01`) |
| `parent_epic_ref: "EPIC-024"` | `parent_epic_ref: "EPIC-024"` | Keep |
| `status: "Ready to Bounce"` | `status: "Ready"` | |
| `status: "Done"` | `status: "Shipped"` | Archived only |
| `ambiguity` | `ambiguity` | Glyph transform as above |
| `context_source` | `context_source` | Usually `EPIC-XXX §4` |
| `actor` | — | Drop (V-Bounce-specific; ClearGate story focuses on user story) |
| `complexity_label: "L1"` | `complexity_label: "L1"` | Keep (L1-L4) |
| — | `parallel_eligible: false` | Default; set true if story is independent |
| — | `expected_bounce_exposure: "low"` | Default |

### Sprint Plan

| V-Bounce field | ClearGate field | Notes |
|---|---|---|
| `sprint_id: "sprint-12"` | `sprint_id: "SPRINT-12"` | Uppercase + `SPRINT-XX` convention |
| `sprint_goal` | `sprint_goal` | Keep |
| `dates` | `dates` | Keep |
| `status: "Active"` / `"Planning"` / `"Done"` | `status: "Active"` / `"Planning"` / `"Shipped"` | |
| `delivery: "D-07"` | — | Drop (V-Bounce release code, not meaningful) |
| `confirmed_by`, `confirmed_at` | `approved_by`, `approved_at` | Remap |
| — | `execution_mode: "v1"` | Default (ClearGate v1 simple bounce) |

### Body section remap (Story example)

| V-Bounce section | ClearGate section |
|---|---|
| §0 Complexity Label & Brief | §0 Complexity Label & Brief |
| §1.1 User Story | §1 User Story |
| §1.2 Detailed Requirements | §2 Detailed Requirements |
| §1.3 Out of Scope | §3 Out of Scope |
| §2.1 Acceptance Criteria (Gherkin) | §4 Gherkin Scenarios |
| §2.2 Verification Steps | §5 Verification Steps |
| §3 Implementation Guide | §6 Implementation Guide |
| §4 Testing Strategy | §7 Quality Gates |
| — | §8 Ambiguity Gate (new; mark 🟢 if no open questions) |

### Sprint Report (V-Bounce → ClearGate 6-section)

| V-Bounce section | ClearGate 6-section |
|---|---|
| Key Takeaways | §1 What Was Delivered (summary lead-in) |
| §1 Stories Delivered | §2 Story Results + CR Change Log |
| §2 Execution Log | §3 Execution Metrics (Bug-Fix Tax, Enhancement Tax, first-pass) |
| §3 Metrics | §3 Execution Metrics (merged) |
| §4 Risk Flags | §5 Tooling (friction signals) + §6 Roadmap (forward look) |
| (FLASHCARDS flagged) | §4 Lessons |

---

## Filename convention

V-Bounce: `EPIC-024_concurrency_hardening.md` (underscore-separated, epic dir nesting)
ClearGate: `EPIC-024-concurrency-hardening.md` (hyphen-separated, flat in `delivery/`)

V-Bounce story: `STORY-024-01-database-queue-rpc.md` (already flat-compatible)
ClearGate story: `STORY-024-01-database-queue-rpc.md` (same)

Sprint: V-Bounce `sprint-12.md` → ClearGate `SPRINT-12.md` (uppercase).

---

## Execution plan

**Step 1** — Hand-port Charter + Roadmap + Design Guide (Phase 7.1). These are unique; a script can't help.

**Step 2** — Write `scripts/port-to-cleargate.mjs` (~200 LOC):
- Reads V-Bounce doc → detects type by path + frontmatter
- Remaps frontmatter per tables above
- Remaps filename (underscore → hyphen, SPRINT uppercase)
- Writes to `.cleargate/delivery/{pending-sync,archive}/`
- Body copied verbatim (section headings translate naturally — V-Bounce and ClearGate templates are structurally close)
- After each write, invokes `cleargate gate check` and logs result
- Idempotent; re-runnable

**Step 3** — Run script over active epics → pending-sync (Phase 7.2a).
**Step 4** — Run script over active stories → pending-sync (Phase 7.2b).
**Step 5** — Run script over archived epics + stories → archive (Phase 7.2c).
**Step 6** — Run script over sprint plans (12 files) → pending-sync/archive (Phase 7.3).
**Step 7** — Delegate sprint-report synthesis to an agent; one REPORT.md per sprint-run dir (Phase 7.4).
**Step 8** — Run script over hotfix → pending-sync as BUG-001 (Phase 7.5).
**Step 9** — Delegate FLASHCARDS distillation to an agent: 32 long-form cards → 32 one-liner entries in `.cleargate/FLASHCARD.md` (Phase 7.6).
**Step 10** — `npx cleargate wiki build && npx cleargate wiki lint` (Phase 7.7). Fix broken parent refs iteratively.

---

## Open items to verify post-install

- [ ] Exact ClearGate template frontmatter spec — compare against field tables here; adjust script.
- [ ] Where design guide belongs — `.cleargate/knowledge/design-guide.md` vs `PROPOSAL-002-design-system` (via `delivery/archive`). Test which one the wiki indexer picks up at session start.
- [ ] Does `stamp-and-gate.sh` auto-populate `created_at` / `updated_at`, or should the script do it?
- [ ] Does ClearGate accept `context_source: "PROPOSAL-001"` as a string, or does it expect a path/link? May need `[[PROPOSAL-001]]` wikilink style.
- [ ] Does `cleargate gate check` tolerate the large volume of bulk-imported docs without rate-limit? (May need to disable hooks during bulk import.)
- [ ] Sprint report synthesis: S-12 is mid-sprint; its REPORT.md may be partial. Handle as skeleton with "active" sections.

---

## Non-goals (explicit)

- Not porting per-story V-Bounce dev/QA/devops/architect reports.
- Not porting `.vbounce-archive/improvement-*` (V-Bounce meta-process artifact).
- Not porting `.vbounce-archive/product-graph.json` (ClearGate's wiki supersedes it).
- Not porting `state.json` (V-Bounce's global state has no analog in ClearGate's per-sprint model).
- Not reconstructing a historical `token-ledger.jsonl` for past sprints.
