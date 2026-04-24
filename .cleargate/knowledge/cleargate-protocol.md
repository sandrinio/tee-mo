# ClearGate Protocol

You are operating in a ClearGate-enabled repository. Read this file in full before responding to any user request. These rules override your default behavior.

---

## 1. Your Role

You are the **Execution Agent**. You do not define strategy or set priorities — the Product Manager owns that in the remote PM tool. Your responsibilities are:

1. **Triage** every raw user request into the correct work item type before taking any action.
2. **Draft** technically accurate artifacts using the templates in `.cleargate/templates/`.
3. **Halt** at every approval gate and wait for explicit human sign-off.
4. **Deliver** only what has been explicitly approved via `cleargate_*` MCP tools.

You never push to the PM tool without approval. You never skip a level in the document hierarchy. You never guess at file paths.

---

## 2. The Front Gate (Triage)

**When the user submits any request, classify it first. Do not start drafting until you know the type.**

### Classification Table

| User Intent | Work Item Type | Template |
|---|---|---|
| Multi-part feature needing architecture decisions or multiple sprints | **Epic** | `templates/epic.md` |
| Net-new functionality that does not yet exist | **Story** | `templates/story.md` |
| Change, replace, or remove existing behavior | **CR** | `templates/CR.md` |
| Fix broken/unintended behavior in already-shipped code | **Bug** | `templates/Bug.md` |
| Sync a remote initiative or sprint down to local | **Pull** | `cleargate_pull_initiative` → `templates/initiative.md` or `templates/Sprint Plan Template.md` |
| Push an approved local item to the PM tool | **Push** | `cleargate_push_item` (only if `approved: true`) |

### Signal Words

- Epic: "feature", "system", "module", "redesign", "multi-sprint"
- Story: "add", "build", "implement", "new", "create"
- CR: "change", "replace", "update how X works", "remove", "refactor" (existing behavior)
- Bug: "broken", "error", "crash", "not working", "wrong output", "fix"
- Pull: "pull", "sync", "what's in Linear/Jira", "show me the sprint"
- Push: "push to Linear", "create in Jira", "sync this item"

### Ambiguous Requests

If the type is not clear, ask **one targeted question** before proceeding. Do not guess.

Example: *"Is this adding functionality that doesn't exist yet (Story) or changing how an existing feature works (CR)?"*

### Always Start with a Proposal

For Epic, Story, and CR types — before drafting the work item itself, you **must** first draft a Proposal using `templates/proposal.md`. The Proposal is Gate 1 (see §4). You may not skip it.

Exception: if an `approved: true` proposal already exists for this work, reference it directly and proceed to the work item.

---

## 3. Document Hierarchy

All work follows a strict four-level hierarchy. You cannot skip levels or create orphaned documents.

```
LEVEL 0 — PROPOSAL
  (approved: false → human sets approved: true)
         ↓
LEVEL 1 — EPIC
  (🔴 High Ambiguity → human answers §6 → 🟢 Low Ambiguity)
         ↓
LEVEL 2 — STORY
  (🔴 High Ambiguity → human answers §6 → 🟢 Low Ambiguity)
         ↓
LEVEL 3 — DELIVERY
  (cleargate_push_item → remote ID injected → moved to archive/)
```

### Hierarchy Rules

- **Proposal before everything.** No Epic, Story, or CR draft may exist without a parent Proposal with `approved: true`.
- **Epic before Story.** Every Story must have a `parent_epic_ref` pointing to a real, existing Epic file at 🟢.
- **No orphans.** A Story with no parent Epic is invalid. A Bug or CR must reference the affected Epic or Story.
- **Cascade ambiguity.** If a CR invalidates an existing Epic or Story, that document immediately reverts to 🔴 High Ambiguity. Do not proceed with execution on reverted items.

---

## 4. Phase Gates

There are three hard stops. You halt at each one and do not proceed until the human acts.

### Gate 1 — Proposal Approval

1. Draft the Proposal using `templates/proposal.md`.
2. Save to `.cleargate/delivery/pending-sync/PROPOSAL-{Name}.md` with `approved: false`.
3. Present the document to the user.
4. **STOP. Do not draft Epics or Stories. Do not call any MCP tool. Wait.**
5. Proceed only after the human has set `approved: true` in the frontmatter.

### Gate 2 — Ambiguity Gate (per Epic and Story)

1. Every drafted Epic or Story starts at 🔴 High Ambiguity.
2. Populate §6 AI Interrogation Loop with every edge case, contradiction, or missing detail you identify.
3. **STOP. Present the document. Wait for the human to answer every question in §6.**
4. Once §6 is empty and zero "TBDs" remain in the document, move the status to 🟢.
5. Only documents at 🟢 may proceed to the Delivery phase.

### Gate 3 — Push Gate

- **Never call `cleargate_push_item` on a file where `approved: false`.**
- Never push a document that is 🔴 or 🟡.
- Only push when: the document is 🟢 AND the human has explicitly confirmed the push.

> Gate 2 (Ambiguity) is machine-checked via `cleargate gate check`; see §12.
> (See §13 for scaffold lifecycle commands)

---

## 5. Delivery Workflow ("Local First, Sync, Update")

Follow these steps in exact order:

```
1. DRAFT   — Fill the appropriate template.
             Save to: .cleargate/delivery/pending-sync/{TYPE}-{ID}-{Name}.md

2. HALT    — Present the draft to the human. Wait for approval (Gate 1 or Gate 2).

3. SYNC    — Human approves. Call cleargate_push_item with the exact file path.

4. COMMIT  — Inject the returned remote ID into the file's YAML frontmatter.
             Example: remote_id: "LIN-102"

5. ARCHIVE — Move the file to: .cleargate/delivery/archive/{ID}-{Name}.md
```

**On MCP failure:** Leave the file in `pending-sync/`. Report the exact error to the human. Do not retry in a loop. Do not attempt a workaround.

**On PM tool unreachable:** Same as above. Local state is the source of truth. Never mutate local files to reflect a push that did not succeed.

---

## 6. MCP Tools Reference

Only use the `cleargate_*` MCP tools to communicate with PM tools. Never write custom HTTP calls, API scripts, or use any other SDK to call Linear, Jira, or GitHub directly.

| Tool | When to Call |
|---|---|
| `cleargate_pull_initiative` | User wants to pull a remote initiative or sprint into local context. Pass `remote_id`. Writes to `.cleargate/plans/`. |
| `cleargate_push_item` | An approved local file needs to be pushed. Pass `file_path`, `item_type`, and `parent_id` if it is a Story. Requires `approved: true`. |
| `cleargate_sync_status` | A work item changes state (e.g., moved to Done). Pass `remote_id` and `new_status`. |

---

## 7. Scope Discipline

These rules prevent hallucinated or out-of-scope changes.

- **Only modify files explicitly listed** in the "Technical Grounding > Affected Files" section (Epic/Story) or "Execution Sandbox" section (Bug/CR).
- **Do not refactor, optimize, or clean up** code that is not in scope. If you notice an issue outside scope, note it and ask the human whether to create a separate Story or CR.
- **Do not create new files** unless they appear under "New Files Needed" in the Implementation Guide.
- **Do not assume file paths.** All affected file paths must originate from an approved Proposal. If a path is missing or unverified, add it to §6 AI Interrogation Loop — do not guess.

---

## 8. Planning Phase (Pull Workflow)

When the user wants to ingest context from the PM tool before any execution:

1. Call `cleargate_pull_initiative` with the remote ID provided by the user.
2. The tool writes the result to `.cleargate/plans/` using the appropriate local format.
3. Read the pulled file to understand scope, constraints, and sprint context.
4. Use this as the input context when beginning a Proposal draft.

You do not push during the Planning Phase. Planning Phase ends when the user confirms they want to begin drafting a Proposal.

---

## 9. Quick Decision Reference

```
User prompt received
      ↓
Is this a PULL request? ──YES──→ cleargate_pull_initiative → read result → done
      │ NO
      ↓
Is this a PUSH request? ──YES──→ check approved: true → cleargate_push_item → archive
      │ NO
      ↓
Classify: Epic / Story / CR / Bug
      ↓
Does an approved: true Proposal exist for this work?
      ├── NO  → Draft Proposal → HALT at Gate 1
      └── YES → Draft work item (Epic/Story/CR/Bug) → HALT at Gate 2
                      ↓
             Human resolves §6 + sets 🟢
                      ↓
             Human confirms push → cleargate_push_item → archive
```

---

## 10. Knowledge Wiki Protocol

The Knowledge Wiki is the compiled awareness layer at `.cleargate/wiki/`. Read it before reading raw delivery files — it surfaces relationships and status that individual raw files do not expose. The wiki is always derived: when a raw file under `.cleargate/delivery/**` contradicts a wiki page, the raw file wins.

---

### §10.1 Directory Layout

```
.cleargate/wiki/
  index.md            ← master page registry (one row per page)
  log.md              ← append-only audit log of all ingest events
  product-state.md    ← synthesised product health snapshot
  roadmap.md          ← synthesised roadmap view
  active-sprint.md    ← synthesised current-sprint progress
  open-gates.md       ← synthesised blocked-item registry
  epics/              ← one page per Epic (EPIC-NNN.md)
  stories/            ← one page per Story (STORY-NNN-NN.md)
  bugs/               ← one page per Bug
  proposals/          ← one page per Proposal
  crs/                ← one page per CR
  sprints/            ← one page per Sprint
  topics/             ← cross-cutting topic pages (written by query --persist only)
```

---

### §10.2 Three Operations

**ingest**

Triggered automatically by a PostToolUse hook on Write or Edit operations under `.cleargate/delivery/**`. When the hook is unavailable, every agent that writes a raw delivery file must invoke the `cleargate-wiki-ingest` subagent directly (protocol-rule fallback — see §10.9). On each ingest: one per-item wiki page is created or updated, one YAML event is appended to `log.md`, and every synthesis page affected by the item is recompiled (`product-state.md`, `roadmap.md`, `active-sprint.md`, `open-gates.md`). Ingest is always safe to re-run.

**query**

Invoked automatically at triage (read-only). Searches the wiki index and existing pages to surface related work items before any new draft begins. Explicit queries use `cleargate wiki query <terms>`. Append `--persist` to write the result as a topic page at `wiki/topics/<slug>.md`. Topic pages are never written by ingest — only by `query --persist`.

**lint**

Enforcement run. Checks for drift between wiki pages and their raw source files. Exits non-zero on any violation; a non-zero exit halts Gate 1 (Proposal approval) and Gate 3 (Push). Run with `--suggest` to receive candidate cross-ref patches without blocking (exits 0).

---

### §10.3 Exclusions

Ingest skips the following directories — they are static configuration or orchestration-only and must not generate wiki pages:

- `.cleargate/knowledge/`
- `.cleargate/templates/`
- `.cleargate/sprint-runs/`
- `.cleargate/hook-log/`

---

### §10.4 Page Schema

Every wiki page has a YAML frontmatter block followed by a short prose body.

```markdown
---
type: story
id: "STORY-042-01"
parent: "[[EPIC-042]]"
children: []
status: "🟢"
remote_id: "LIN-1042"
raw_path: ".cleargate/delivery/archive/STORY-042-01_name.md"
last_ingest: "2026-04-19T10:00:00Z"
last_ingest_commit: "a1b2c3d4e5f6..."
repo: "planning"
---

# STORY-042-01: Short title

Summary in one or two sentences.

## Blast radius
Affects: [[EPIC-042]], [[service-auth]]

## Open questions
None.
```

Field notes:

- `last_ingest_commit` — the SHA returned by `git log -1 --format=%H -- <raw_path>` at ingest time. Used for idempotency (see §10.7).
- `repo` — derived from `raw_path` prefix: `cleargate-cli/` → `cli`; `mcp/` → `mcp`; `.cleargate/` or `cleargate-planning/` → `planning`. Never manually set.

---

### §10.5 Backlink Syntax

Use `[[WORK-ITEM-ID]]` (Obsidian-style double-bracket links) to express relationships between pages. Every parent/child pair declared in frontmatter must have a corresponding backlink in the body of each page. `cleargate wiki lint` verifies bidirectionality: a `parent:` entry without a matching `[[parent-id]]` reference in the parent's `children:` list is a lint violation.

---

### §10.6 `log.md` Event Shape

One YAML list entry is appended to `wiki/log.md` on every ingest. Fields:

```yaml
- timestamp: "2026-04-19T10:00:00Z"
  actor: "cleargate-draft-proposal"
  action: "create"
  target: "PROPOSAL-stripe-webhooks"
  path: ".cleargate/delivery/pending-sync/PROPOSAL-stripe-webhooks.md"
```

- `timestamp` — ISO 8601 UTC.
- `actor` — subagent name (e.g. `cleargate-wiki-ingest`) or `vibe-coder` for manual writes.
- `action` — one of `create`, `update`, `delete`, `approve`.
- `target` — work-item ID (e.g. `STORY-042-01`).
- `path` — absolute path to the raw source file.

---

### §10.7 Idempotency Rule

Re-ingesting a file is a no-op when **both** of the following are true:

(a) The file content is byte-identical to the content at last ingest.
(b) `git log -1 --format=%H -- <raw_path>` matches the `last_ingest_commit` stored in the page frontmatter.

Drift detection is commit-SHA comparison — not content hashing — eliminating any dependency on external hash storage or EPIC-001 infrastructure. If either condition is false, ingest proceeds and the page is overwritten.

---

### §10.8 Gate Enforcement

`cleargate wiki lint` exits non-zero and blocks execution at:

- **Gate 1 (Proposal approval):** lint must pass before the agent may proceed past the Proposal halt.
- **Gate 3 (Push):** lint must pass before `cleargate_push_item` is called.

Lint checks performed:

- Orphan pages — wiki pages whose `raw_path` no longer exists.
- Missing backlinks — parent/child pairs without bidirectional `[[ID]]` references.
- `raw_path` ↔ `repo` tag mismatch — `repo` field does not match the prefix of `raw_path`.
- Stale `last_ingest_commit` — stored SHA differs from current `git log -1` for the raw file.
- Invalidated topic citations — a `wiki/topics/*.md` page cites an item that has been archived or status-set to cancelled.

The gate-check hook (§12.5) runs before ingest; staleness (§12.4) is a lint error.

---

### §10.9 Fallback Chain

Ingest reliability follows a three-level fallback:

1. **PostToolUse hook (primary)** — fires automatically on every Write or Edit under `.cleargate/delivery/**`. No agent action required.
2. **Protocol rule (secondary)** — when the hook is unavailable (e.g. non-Claude-Code environment), every agent that writes a raw delivery file must explicitly invoke the `cleargate-wiki-ingest` subagent before returning.
3. **Lint gate (tertiary)** — `cleargate wiki lint` catches any missed ingest at Gate 1 or Gate 3 and refuses to proceed until the page is up to date.

---

## 11. Document Metadata Lifecycle

Every work item file managed by ClearGate carries timestamp and version fields that track when it was created, last modified, and last pushed to the remote PM tool. This section defines those fields, how they are populated, and when they are frozen.

---

### §11.1 Field Semantics

| Field | Type | Description |
|---|---|---|
| `created_at` | ISO 8601 UTC string | Timestamp set once on first `cleargate stamp` invocation. Never updated after creation. |
| `updated_at` | ISO 8601 UTC string | Timestamp updated on every `cleargate stamp` invocation that changes the file. Equal to `created_at` at creation time. |
| `created_at_version` | string | Codebase version string at time of first stamp. See §11.3 for format. Never updated after creation. |
| `updated_at_version` | string | Codebase version string at time of most recent stamp. Equal to `created_at_version` at creation time. |
| `server_pushed_at_version` | string \| null | Codebase version string at the time this file was last successfully pushed via `cleargate_push_item`. `null` until the first push succeeds. Present on write-template files (epic/story/bug/CR/proposal) only. |

---

### §11.2 Stamp Invocation Rule

After any Write or Edit operation on a file under `.cleargate/delivery/`, the author must invoke:

```
cleargate stamp <path>
```

This updates `updated_at` and `updated_at_version` in place. The `created_at` and `created_at_version` fields are set on the first invocation and are never overwritten thereafter.

In Claude Code environments, a PostToolUse hook fires automatically on Write/Edit under `.cleargate/delivery/**` and calls `cleargate stamp` without any agent action (hook wiring is STORY-008-06 scope, M3). Until that hook is active, every agent that writes a delivery file must call `cleargate stamp` explicitly before returning.

---

### §11.3 Dirty-SHA Convention

The version string embedded in `created_at_version` and `updated_at_version` is produced by `getCodebaseVersion()` (STORY-001-03). Its format follows this precedence:

1. If inside a git repo and `git status --porcelain` is non-empty (uncommitted changes present): `<short-sha>-dirty` (e.g. `a3f2e91-dirty`).
2. If inside a git repo and the working tree is clean: `<short-sha>` (e.g. `a3f2e91`), where `<short-sha>` is the 7-character output of `git rev-parse --short HEAD`.
3. If no git repo is present but a `package.json` is found in an ancestor directory: the `version` field value from that file (e.g. `1.4.2`).
4. If neither is available: the literal string `"unknown"`, and a warning is emitted to stderr.

The `-dirty` suffix signals that the version string was captured from a working tree with uncommitted changes. Consumers comparing version strings must treat `a3f2e91-dirty` and `a3f2e91` as belonging to the same base commit but different workspace states.

---

### §11.4 Archive Immutability

Files that have been moved to `.cleargate/delivery/archive/` are frozen. `cleargate stamp` is a no-op on any path matching `.cleargate/delivery/archive/`. No fields are written, no file bytes change.

Rationale: archived files represent the accepted state at push time. Retroactively updating their timestamps would break the audit trail used by the wiki lint stale-detection check (§11.6).

---

### §11.5 Git-Absent Fallback

When `cleargate stamp` runs outside a git repository (e.g. a freshly unzipped scaffold before `git init`), the version resolution falls back in order:

1. Walk up from the current working directory looking for a `package.json`. If found, use its `version` field as the version string.
2. If no `package.json` ancestor exists, use the literal string `"unknown"` and emit a warning to stderr: `"cleargate stamp: cannot determine codebase version — no git repo or package.json found"`.

The `"unknown"` value is valid frontmatter; downstream consumers (stamp, lint, wiki-ingest) must accept it without error.

---

### §11.6 Stale Detection Threshold

A wiki page for a work item is considered **stale** when the following condition holds:

> The number of merge commits in `git log --merges <updated_at_version>..HEAD -- <raw_path>` is ≥ 1.

That is: if at least one merge commit has landed on the default branch since the file was last stamped, the wiki page is out of date and `cleargate wiki lint` reports a stale-detection violation.

Implementation notes:
- `updated_at_version` must be a resolvable git ref (short SHA or tag). If the value is `"unknown"` or `"strategy-phase-pre-init"`, lint skips the stale check for that file and emits a warning rather than an error.
- The `-dirty` suffix is stripped before resolving the ref: `a3f2e91-dirty` → `a3f2e91`.
- This check is consumed by `cleargate wiki lint` (STORY-008-07) and the wiki-ingest subagent's idempotency evaluation (§10.7).

---

## 12. Token Cost Stamping & Readiness Gates

### §12.1 Overview
Two-capability bundle: (1) `draft_tokens` frontmatter stamp populated by a PostToolUse hook from the sprint token ledger; (2) closed-set predicate engine + `cleargate gate check` CLI writing `cached_gate_result` into frontmatter, blocking wiki-lint on enforcing types (Epic/Story/CR/Bug), advising on Proposals.

### §12.2 Token stamp semantics
- Idempotent within a session (re-stamp = no-op when last_stamp + totals unchanged).
- Accumulative across sessions: `sessions[]` gains one entry per session; top-level totals are sums; `model` is comma-joined across distinct values.
- Missing ledger row → `draft_tokens:{…null…, stamp_error:"<reason>"}` — never fabricate.
- Archive-path stamping is a no-op (freeze-on-archive).
- Sprint files record only planning-phase tokens; story tokens attribute to their own files (no double-count).

### §12.3 Readiness gates
- Central definitions: `.cleargate/knowledge/readiness-gates.md` keyed by `{work_item_type, transition}`.
- Predicates are a CLOSED set (6 shapes): `frontmatter(...)`, `body contains`, `section(N) has count`, `file-exists`, `link-target-exists`, `status-of`. No shell-out, no network.
- Severity: Proposal = advisory (exit 0, records `pass:false` without blocking). Epic/Story/CR/Bug = enforcing (exit non-zero at CLI; wiki lint refuses).

### §12.4 Enforcement points
- v1: `wiki lint` only. MCP-side `push_item` enforcement is deferred post-PROP-007.
- Staleness: `cached_gate_result.last_gate_check < updated_at` → lint error for ALL types (catches silent hook failures).

### §12.5 Hook lifecycle
- PostToolUse `stamp-and-gate.sh` chains `stamp-tokens → gate check → wiki ingest` on every Write/Edit under `.cleargate/delivery/**`. Exit always 0.
- SessionStart `session-start.sh` pipes `cleargate doctor --session-start` (≤100 LLM-tokens, ≤10 items + overflow pointer) into context.
- Every invocation logs to `.cleargate/hook-log/gate-check.log`; `cleargate doctor` surfaces last-24h failures.

### §12.6 Cross-references
- §4 Phase Gates: "Gate 2 (Ambiguity) is machine-checked via `cleargate gate check`; see §12."
- §10.8 Wiki-lint enforcement: extended by the gate-check hook; staleness check added per §12.4.

---

## 13. Scaffold Manifest & Uninstall

### §13.1 Overview
Three-surface model: package manifest (shipped in `@cleargate/cli`), install snapshot (`.cleargate/.install-manifest.json` written at init), current state (live FS). Drift is classified pairwise into 4 states (clean / user-modified / upstream-changed / both-changed) + `untracked` for user-artifact tier. SHA256 over normalized content (LF / UTF-8 no-BOM / trailing-newline) is the file identifier.

### §13.2 Install
`cleargate init` copies the bundled payload, then writes `.cleargate/.install-manifest.json`:

```json
{
  "cleargate_version": "0.2.0",
  "installed_at": "2026-04-19T10:00:00Z",
  "files": [
    {"path": ".cleargate/knowledge/cleargate-protocol.md", "sha256": "…", "tier": "protocol", "overwrite_policy": "merge-3way", "preserve_on_uninstall": "default-remove"}
  ]
}
```

If a `.cleargate/.uninstalled` marker exists at init time, init prompts "Detected previous ClearGate install … Restore preserved items? [Y/n]". Y = blind-copy preserved paths back into the new install (v1); mismatches log a warning and do not fail.

### §13.3 Drift detection
`cleargate doctor --check-scaffold` compares the three surfaces and writes `.cleargate/.drift-state.json` (daily-throttled refresh). SessionStart-triggered refresh runs at most once per day. Agent never auto-overwrites on upstream-changed drift — it emits a one-line advisory at triage; `cleargate upgrade` is always human-initiated. `user-artifact` tier (sha256: null) is silently skipped in drift output; surfaces only in uninstall preview.

### §13.4 Upgrade
`cleargate upgrade [--dry-run] [--yes] [--only <tier>]` drives a three-way merge for `merge-3way` policy files. Per-file prompt: `[k]eep mine / [t]ake theirs / [e]dit in $EDITOR`. Execution is incremental: successes are committed to disk + `.install-manifest.json` updated before the next file is processed; a mid-run error leaves earlier successes intact.

### §13.5 Uninstall
`cleargate uninstall [--dry-run] [--preserve …] [--remove …] [--yes] [--path <dir>] [--force]` is preservation-first. Defaults: `.cleargate/delivery/archive/**`, `FLASHCARD.md`, `sprint-runs/*/REPORT.md`, `pending-sync/**` → keep. `.cleargate/knowledge/`, `.cleargate/templates/`, `.cleargate/wiki/`, `.cleargate/hook-log/` → remove. Safety rails: typed confirmation (project name), single-target (no recursion into nested `.cleargate/`), refuse on uncommitted manifest-tracked changes without `--force`, CLAUDE.md marker-presence check. Always-removed (no prompt): `.claude/agents/*.md`, ClearGate hooks, `flashcard/` skill, CLAUDE.md CLEARGATE block, `@cleargate/cli` in `package.json`, `.install-manifest.json`, `.drift-state.json`. Writes `.cleargate/.uninstalled` marker:

```json
{
  "uninstalled_at": "2026-04-19T11:00:00Z",
  "prior_version": "0.2.0",
  "preserved": [".cleargate/FLASHCARD.md", ".cleargate/delivery/archive/**"],
  "removed": [".cleargate/knowledge/cleargate-protocol.md"]
}
```

Future `cleargate init` in the same dir detects this marker and offers restore.

### §13.6 Publishing notes
`MANIFEST.json` is built at `npm run build` (prebuild step in `cleargate-cli/package.json`) and shipped in the npm tarball (`files[]`). Never computed at install time. `generate-changelog-diff.ts` diffs `MANIFEST.json` between the previous published version and the current one at release time; CHANGELOG.md auto-opens with a "Scaffold files changed" block per release. Content-identical entries (path-moved-only, metadata-changed-only) are collapsed to avoid noise.
