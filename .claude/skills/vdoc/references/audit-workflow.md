# Audit Workflow

Detect stale, missing, dead, and low-quality documentation. Report and patch. Do NOT create scripts, shell files, scanners, or any tooling — use your built-in tools (Read, Glob, Grep, Bash for git commands) for everything.

## Step 1 — Read Current State

Read `vdocs/_manifest.json`. Load the list of documented features and their metadata.

## Step 2 — Detect Stale Docs

Run `git log --name-only --since="<last_updated>" --pretty=format:""` or use `git diff` to find all source files that changed since the last audit.

Cross-reference changed files against each doc's `keyFiles` frontmatter (or Key Files section) to identify which docs are stale.

## Step 3 — Detect Coverage Gaps

Scan the codebase for significant features not covered by any doc. Look for:
- New route files / API endpoints
- New service classes or modules
- New database models / schema changes
- New configuration or infrastructure files

If you find undocumented features, propose new docs.

## Step 4 — Detect Dead Docs

Check each doc's Key Files (from frontmatter `keyFiles` and the Key Files table) against the actual filesystem. If key files no longer exist, the doc may be dead. Flag it: "PAYMENT_PROCESSING_DOC.md references 3 files that no longer exist — remove or archive?"

## Step 5 — Check Cross-References

Read each doc's Related Features table and `relatedDocs` frontmatter. Verify that:
- Referenced doc filenames still exist in `vdocs/` and in `_manifest.json`
- The `deps` array in the manifest matches the Related Features table
- The described coupling is still accurate (skim the relevant code)

## Step 6 — Quality Score

Run mechanical quality checks on each doc. Score = percentage of checks passing.

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Valid YAML frontmatter | Has all required fields: title, description, tags, version, keyFiles, relatedDocs, lastUpdated |
| 2 | CORE sections present and non-empty | Overview, Business Rules, How It Works, Key Files, Testing, Constraints & Decisions, Related Features all exist with content |
| 3 | Key File paths exist | Every path in frontmatter `keyFiles` and Key Files table resolves to a real file |
| 4 | How It Works has a diagram | Contains at least one `mermaid` code block |
| 5 | Business Rules has ≥1 rule | At least one bullet point in the section |
| 6 | relatedDocs resolve | Every filename in frontmatter `relatedDocs` exists in `vdocs/` |
| 7 | lastUpdated freshness | Delta between `lastUpdated` and latest git blame on key files is within acceptable range |
| 8 | Testing section has run command | Contains a code-formatted command string |

**Score thresholds:**
- **80-100%** — Good quality
- **60-79%** — Acceptable, minor improvements suggested
- **Below 60%** — Low quality — generate a "quality fix" task

## Step 7 — Report

Present a clear report:

```
Audit Results:

STALE (source files changed):
  - AUTHENTICATION_DOC.md — src/lib/auth.ts changed (added GitHub provider)
  - API_REFERENCE_DOC.md — 2 new endpoints added

QUALITY SCORES:
  - AUTHENTICATION_DOC.md — 88% (Good) ✓
  - API_REFERENCE_DOC.md — 50% (Low) ✗ Missing: Business Rules, Testing section, mermaid diagram
  - DATABASE_SCHEMA_DOC.md — 75% (Acceptable) ~ Missing: Testing section

COVERAGE GAPS (undocumented features):
  - src/services/notification.ts — no doc covers notifications

DEAD DOCS (source files removed):
  - LEGACY_ADMIN_DOC.md — all 4 source files deleted

CROSS-REF ISSUES:
  - AUTHENTICATION_DOC.md references BILLING_DOC.md which no longer exists
  - Manifest deps for PAYMENTS_DOC.md lists "invoicing" but no invoicing doc exists

CURRENT (no changes needed):
  - PROJECT_OVERVIEW_DOC.md — 100% quality

Proceed with fixes?
```

Wait for user direction, then:
- Patch stale docs (re-read source files, update affected sections only)
- Fix low-quality docs (add missing CORE sections, fix broken key file paths)
- Generate new docs for coverage gaps (follow create workflow for each)
- Flag dead docs for user to confirm deletion
- Fix cross-reference issues (update relatedDocs frontmatter + manifest deps)
- Regenerate context slices for any patched/updated docs in `vdocs/_slices/`
- Update manifest: bump `version`, update `last_updated`, `last_commit`, fix `deps` arrays
- Bump frontmatter `version` (increment by 1) and `lastUpdated` on every patched doc
