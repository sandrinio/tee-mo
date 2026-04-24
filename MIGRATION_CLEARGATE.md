# Migration: V-Bounce Engine → ClearGate

**Drafted:** 2026-04-24
**Branch:** `migration/cleargate`
**Safety tag (pre-migration state on `main`):** `vbounce-final-2.7.1`
**Target framework:** [ClearGate v0.2.1](https://github.com/sandrinio/cleargate)
**Current framework:** V-Bounce Engine v2.7.1 installed (manifest declares 2.8.0), platform `claude`

---

## 0. Goals & non-goals

**Goal.** Replace V-Bounce Engine with ClearGate as the active planning and execution harness, preserving sprint history and accumulated lessons without losing traceability. Run the first ClearGate sprint end-to-end to validate the swap.

**Non-goals.**
- Rewriting application code. `backend/`, `frontend/`, `database/`, `docs/` are untouched.
- Re-running closed sprints.
- Maintaining the Gemini / Antigravity lane. ClearGate is Claude-only; `GEMINI.md` and `.agents/skills/` are retired.
- Adopting ClearGate's optional MCP sync or SvelteKit admin UI in this migration (local-only).

---

## 1. Current V-Bounce footprint

**Framework surface** (removed by migration):

| Path | Description |
|---|---|
| `CLAUDE.md` | V-Bounce agent brain |
| `GEMINI.md` | V-Bounce brain for Gemini CLI |
| `.claude/agents/` | 6 subagents: explorer, developer, qa, architect, devops, scribe |
| `.claude/commands/vdoc-*.md` | vdoc slash commands (4 files) |
| `.claude/skills/vdoc/` | vdoc skill |
| `.claude/settings.local.json` | Local Claude Code settings (trim V-Bounce perms, keep file) |
| `.vbounce/` | Runtime: skills/, scripts/ (31 files), templates/ (13 files), VBOUNCE_MANIFEST.md, install-meta.json |
| `.agents/skills/` | Gemini/Antigravity mirror of V-Bounce skills |
| `.vbounce-studio/` | Studio marker |
| `.worktrees/` | Empty |

**User content surface** (preserved as archives):

| Path | Description | Disposition |
|---|---|---|
| `FLASHCARDS.md` | ~38 KB of long-form lessons | Rename to `FLASHCARDS.vbounce-archive.md` |
| `product_plans/` | Strategy, backlog, sprints, hotfixes, archive | Rename to `product_plans.vbounce-archive/` |
| `.vbounce/reports/`, `sprint-report-S-*.md`, `sprint-context-S-*.md`, `.vbounce/archive/`, `state.json`, `product-graph.json`, `gate-checks.json`, `improvement-*`, `tasks/` | Sprint history S-01…S-12 | Pre-archive to `.vbounce-archive/` before uninstall wipes `.vbounce/` |

---

## 2. Target state

After migration, ClearGate installs (idempotent `npx cleargate init`):

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Root brain with bounded block `<!-- CLEARGATE:START -->…<!-- CLEARGATE:END -->` |
| `.claude/agents/` | 4 core + 3 wiki agents: architect, developer, qa, reporter, cleargate-wiki-{ingest,lint,query} |
| `.claude/hooks/` | 4 bash hooks (token-ledger, stamp-and-gate, session-start, pending-task-sentinel) |
| `.claude/skills/flashcard/SKILL.md` | Flashcard protocol |
| `.claude/settings.json` | Hook wiring |
| `.cleargate/knowledge/` | `cleargate-protocol.md`, `readiness-gates.md` |
| `.cleargate/templates/` | 9 templates (proposal, epic, story, CR, Bug, Sprint Plan, initiative, sprint_context, sprint_report) |
| `.cleargate/delivery/{pending-sync,archive}/` | Work items (`TYPE-ID-Name.md`) |
| `.cleargate/FLASHCARD.md` | Append-only, tagged 120-char one-liners |
| `.cleargate/wiki/` | Compiled awareness layer (~3k tokens, session-start read) |
| `.cleargate/sprint-runs/<id>/` | Per-sprint plans, token-ledger.jsonl, state.json, REPORT.md |
| `MANIFEST.json` | ClearGate install manifest |

---

## 3. Concept mapping

| V-Bounce | ClearGate | Notes |
|---|---|---|
| CLAUDE.md (whole file) | CLAUDE.md bounded block | Non-V-Bounce content outside markers is preserved |
| Charter, Roadmap, Risk Registry | Proposal (Gate 1) | Collapsed to single Level-0 doc |
| Epic | Epic (Gate 2) | Adds `ambiguity: 🔴/🟡/🟢`, AI Interrogation Loop |
| Story | Story (Gate 2) | Adds `complexity_label: L1-L4`, `parallel_eligible` |
| Hotfix | Bug | |
| Change Request | CR | 1:1 |
| Sprint Plan | Sprint Plan | Different sections; readiness gate still §0 |
| Explorer (Haiku) | — | Folded into Architect |
| Developer | Developer | 1:1 |
| QA | QA | 1:1 |
| Architect | Architect | 1:1 |
| DevOps | — | Merge/deploy → orchestrator + hooks + human |
| Scribe (vdoc) | Reporter + compiled Wiki | Auto-compiled `.cleargate/wiki/` + per-sprint REPORT.md |
| `.vbounce/scripts/*.mjs` (31) | `cleargate` CLI (28 subcommands) | Shell scripts → Node CLI |
| `.vbounce/state.json` (global) | `.cleargate/sprint-runs/<id>/state.json` | Per-sprint scope |
| `.vbounce/product-graph.json` | `.cleargate/wiki/` + `delivery/INDEX.md` | Compiled wiki replaces graph |
| `.vbounce/gate-checks.json` | `.cleargate/knowledge/readiness-gates.md` | YAML predicates, machine-checkable |
| `FLASHCARDS.md` | `.cleargate/FLASHCARD.md` | Format change: 120-char one-liners with tags |
| `product_plans/{strategy,backlog,sprints,hotfixes,archive}/` | `.cleargate/delivery/{pending-sync,archive}/` | Filename carries type + ID |
| `.vbounce/reports/`, sprint-report-S-*.md | `.cleargate/sprint-runs/<id>/REPORT.md` | Per-sprint dir |
| `.claude/commands/vdoc-*`, `.claude/skills/vdoc/` | `cleargate wiki {build,ingest,lint,query}` | CLI + 3 subagents |
| `VBOUNCE_MANIFEST.md` | `MANIFEST.json` | Machine-readable |
| `.agents/skills/`, `GEMINI.md` | — | Dropped |

---

## 4. Decisions (defaults, override if needed)

| # | Question | Decision |
|---|---|---|
| 4.1 | In-flight EPIC-024 work? | Archive alongside the rest; decide later whether to port to ClearGate or finish on a V-Bounce revival branch cut from `vbounce-final-2.7.1` |
| 4.2 | Sprint numbering in ClearGate | Restart at `SPRINT-01` (ClearGate convention) |
| 4.3 | FLASHCARDS.md strategy | Option A — rename to `FLASHCARDS.vbounce-archive.md`, start `.cleargate/FLASHCARD.md` empty, backfill high-value cards as they resurface in work |
| 4.4 | `product_plans/` strategy | Rename to `product_plans.vbounce-archive/` (read-only, preserved in git) |
| 4.5 | Gemini lane | Abandon. Delete `GEMINI.md`, `.agents/skills/` |
| 4.6 | MCP sync / Admin UI | Skip for now |
| 4.7 | Node version | v24.14.0 confirmed (≥24 required) |
| 4.8 | CLAUDE.md customizations | None; whole file is V-Bounce, safe to replace |

---

## 5. The `vbounce uninstall` footgun

`bin/vbounce.mjs` auto-removes framework files from `install-meta.json` (for platform `claude`: `CLAUDE.md`, `.claude/agents/`, `.vbounce/templates/`, `.vbounce/skills/`, `.vbounce/scripts/`, `.vbounce/VBOUNCE_MANIFEST.md`). It prompts for user data (`FLASHCARDS.md`, `product_plans/`, `.vbounce/archive/`, `vdocs/`, `LESSONS.md`) — defaults to keep.

**Gotcha.** As the final step, the script unconditionally runs `fs.rmSync('.vbounce', { recursive: true, force: true })`. Even if you answer "no" to keeping `.vbounce/archive/`, the entire `.vbounce/` directory — including `reports/`, `state.json`, `product-graph.json`, `gate-checks.json`, all `sprint-context-S-*.md`, all `sprint-report-S-*.md`, `improvement-*`, `tasks/` — gets wiped.

**Mitigation.** Pre-archive everything worth keeping out of `.vbounce/` and into `.vbounce-archive/` *before* running uninstall. The uninstall then only deletes framework files (templates/, skills/, scripts/, manifest, install-meta.json) plus an almost-empty `.vbounce/` shell.

**Leftovers uninstall misses** (because our install is platform=claude):
- `GEMINI.md`
- `.agents/skills/`
- `.vbounce-studio/`
- `.worktrees/`
- `.claude/commands/vdoc-*.md`
- `.claude/skills/vdoc/`
- V-Bounce-specific permissions in `.claude/settings.local.json`

---

## 6. Phased execution

### Phase 0 — Safety net

```bash
git tag vbounce-final-2.7.1 main   # tag pre-migration state
git checkout -b migration/cleargate # uncommitted EPIC-024 edits carry across
```

### Phase 1 — Pre-archive V-Bounce history

Move everything worth keeping out of `.vbounce/` before uninstall wipes it.

```bash
mkdir -p .vbounce-archive
git mv .vbounce/reports              .vbounce-archive/reports
git mv .vbounce/archive              .vbounce-archive/archive
git mv .vbounce/tasks                .vbounce-archive/tasks
git mv .vbounce/state.json           .vbounce-archive/state.json
git mv .vbounce/product-graph.json   .vbounce-archive/product-graph.json
git mv .vbounce/gate-checks.json     .vbounce-archive/gate-checks.json
git mv .vbounce/install-meta.json    .vbounce-archive/install-meta.json.bak   # copy, not move — uninstall reads this
# (we actually need install-meta.json to remain for uninstall; copy instead)
```

Correction — uninstall *requires* `install-meta.json` to be in place. Do this instead:

```bash
mkdir -p .vbounce-archive
git mv .vbounce/reports              .vbounce-archive/
git mv .vbounce/archive              .vbounce-archive/
git mv .vbounce/tasks                .vbounce-archive/
git mv .vbounce/state.json           .vbounce-archive/
git mv .vbounce/product-graph.json   .vbounce-archive/
git mv .vbounce/gate-checks.json     .vbounce-archive/
# Sprint contexts/reports that live at .vbounce/ root:
for f in .vbounce/sprint-context-*.md .vbounce/sprint-report-*.md .vbounce/improvement-*; do
  [ -e "$f" ] && git mv "$f" .vbounce-archive/
done
# install-meta.json stays — uninstall needs it to do its job.
```

After this, `.vbounce/` contains only: `templates/`, `skills/`, `scripts/`, `VBOUNCE_MANIFEST.md`, `install-meta.json`, `.gitignore`. Uninstall will wipe all of those — that's the intent.

**Checkpoint.** Verify `.vbounce-archive/` contents before proceeding.

### Phase 2 — Run `vbounce uninstall` (destructive, interactive)

```bash
npx vbounce uninstall
# Prompt 1: "Proceed with uninstall? [y/N]" → y
# Prompt 2: "Also remove your project data ...? [y/N]" → N
#           (keeps FLASHCARDS.md, product_plans/; .vbounce-archive/ is untouched)
```

Expected post-state:
- Deleted: `CLAUDE.md`, `.claude/agents/`, `.vbounce/` (empty shell)
- Kept: `.vbounce-archive/`, `FLASHCARDS.md`, `product_plans/`, plus all leftover platform files below

### Phase 3 — Clean leftovers

```bash
git rm GEMINI.md
git rm -r .agents
git rm -r .vbounce-studio
rmdir .worktrees                          # empty; not git-tracked
git rm .claude/commands/vdoc-audit.md \
       .claude/commands/vdoc-create.md \
       .claude/commands/vdoc-init.md \
       .claude/commands/vdoc-update.md
git rm -r .claude/skills/vdoc
# settings.local.json: review and trim V-Bounce permissions (keep the file)
```

### Phase 4 — Rename user-content archives

```bash
git mv FLASHCARDS.md FLASHCARDS.vbounce-archive.md
git mv product_plans product_plans.vbounce-archive
```

### Phase 5 — Commit uninstall state

```bash
git status   # sanity check
git commit -m "chore: uninstall V-Bounce Engine; archive history for migration to ClearGate"
```

Leftover sweep — this must return zero matches (excluding archive paths):

```bash
find . -path ./node_modules -prune -o -path ./.git -prune -o \
       -path ./.vbounce-archive -prune -o \
       -path ./product_plans.vbounce-archive -prune -o \
       -path ./FLASHCARDS.vbounce-archive.md -prune -o \
       \( -iname '*vbounce*' -o -iname 'VBOUNCE_*' -o -name 'GEMINI.md' \
          -o -path '*/vdoc*' \) -print
```

### Phase 6 — Install ClearGate

```bash
node -v                   # ≥ 24 (confirmed 24.14.0)
npx cleargate init        # answer prompts
npx cleargate doctor      # environment + config checks
```

Expected new paths: `.cleargate/`, `.claude/hooks/`, `.claude/skills/flashcard/`, `.claude/settings.json`, `.claude/agents/` (4 core + 3 wiki), new `CLAUDE.md` with bounded block, `MANIFEST.json`, `.cleargate/.participants/<email>.json`.

Commit:
```bash
git commit -m "feat: install ClearGate v0.2.1"
```

### Phase 7 — Port work items through the wiki pipeline

For each work item to carry over (start with EPIC-024 if you intend to continue it; otherwise defer):

1. Read source from `product_plans.vbounce-archive/backlog/EPIC-XXX/`.
2. Create `.cleargate/delivery/pending-sync/EPIC-XXX-short-name.md` using `.cleargate/templates/epic.md`.
3. Fill frontmatter: `epic_id`, `ambiguity` (🟢 if the V-Bounce version was Ready), `status: Ready`, `context_source` pointing at archive path.
4. Repeat for child stories using `.cleargate/templates/story.md`.
5. Saving each file triggers the `stamp-and-gate.sh` PostToolUse hook (auto-stamps frontmatter + validates gates).
6. Run `npx cleargate gate check <file>` on each to confirm predicates pass.

After all items are drafted:

```bash
npx cleargate wiki build      # compile .cleargate/wiki/index.md + per-item pages
npx cleargate wiki lint       # catch drift / missing parents / stale backlinks
```

Commit:
```bash
git commit -m "feat: port work items to ClearGate delivery pipeline"
```

### Phase 8 — First ClearGate sprint smoke test

```bash
npx cleargate sprint init   # creates SPRINT-01 scaffold
# Draft .cleargate/delivery/pending-sync/SPRINT-01_<name>.md
# Scope to 1-2 small stories
# Run the four-agent loop:
#   - Architect produces .cleargate/sprint-runs/SPRINT-01/plans/W01.md
#   - Developer commits one story per commit with STORY=NNN-NN tag
#   - QA returns PASS/FAIL
#   - Reporter writes REPORT.md
# Verify:
#   - .cleargate/sprint-runs/SPRINT-01/token-ledger.jsonl populated
#   - .claude/hook-log/ shows hook firings
#   - .cleargate/wiki/ rebuilt on edits
```

Record any surprises as real flashcards via `Skill(flashcard, "record: ...")`.

### Phase 9 — Cutover gate

All must be green:

- [ ] `npx cleargate doctor` passes.
- [ ] Phase 8 smoke sprint completed end-to-end.
- [ ] EPIC-024 disposition decided (ported, deferred, or cancelled).
- [ ] `CLAUDE.md` contains the ClearGate block only (no V-Bounce residue).
- [ ] Leftover sweep (Phase 5 command) returns zero.
- [ ] Git working tree clean.

Then:

```bash
git checkout main
git merge --no-ff migration/cleargate -m "feat: migrate to ClearGate"
git tag cleargate-cutover
```

Keep archives for 1-2 sprints, then remove in a follow-up commit:

```bash
git rm -r .vbounce-archive product_plans.vbounce-archive FLASHCARDS.vbounce-archive.md
git commit -m "chore: drop V-Bounce archives after ClearGate validation"
```

---

## 7. Rollback

- **Before Phase 2 (uninstall):** `git checkout main` — V-Bounce is untouched on main.
- **After Phase 2 but before Phase 9:** `git reset --hard vbounce-final-2.7.1` on the migration branch (or just `git checkout main`).
- **After Phase 9 cutover:** `git revert` the merge commit, or hard-reset `main` to `vbounce-final-2.7.1` (destructive; coordinate).
- **If you need to resume V-Bounce work mid-migration for a hotfix:** `git checkout -b hotfix/vbounce-revival vbounce-final-2.7.1`, do the hotfix there, merge to `main`, and decide whether to re-apply the migration afterward.

---

## 8. Risks

- **macOS Bash 3.2 vs ClearGate hooks.** ClearGate flashcards mention Bash 3.2 portability issues (`mapfile` unavailable). Test hooks fire on your shell during Phase 8.
- **Wiki rebuild cost.** PostToolUse hook fires on every edit under `.cleargate/delivery/`. May slow editing on large imports; monitor.
- **Agent roster shrinkage.** Explorer/DevOps/Scribe tasks fold into other roles or become manual. First sprint may surface gaps.
- **FLASHCARD format discipline.** 38 KB of long-form lessons → 120-char one-liners is a behavior change; easy to regress to V-Bounce habits.
- **Per-sprint state semantics.** V-Bounce tracks global state; ClearGate scopes state per sprint run. Between-sprint continuity lives in `.cleargate/delivery/INDEX.md` + wiki.
- **Uncommitted EPIC-024 work.** Currently one modified + one untracked file under `product_plans/backlog/EPIC-024_*/`. Carried across on the branch; ends up inside `product_plans.vbounce-archive/` in Phase 4. If you want those preserved on `main` under V-Bounce, commit them on `main` before Phase 0.
