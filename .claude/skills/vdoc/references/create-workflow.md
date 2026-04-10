# Create Workflow

Create one feature doc based on the user's description. Do NOT create scripts, shell files, scanners, or any tooling — use your built-in tools (Read, Glob, Grep) for everything.

## Step 1 — Locate

Use the user's description to find the relevant source files:

1. If `vdocs/_planning/_exploration_log.md` exists, read it first — it maps the codebase and may already have the feature signal you need
2. Otherwise, search the codebase with Glob and Grep to find files matching the user's description
3. Read ALL relevant source files — not just the main file, but helpers, types, middleware, tests, API routes, components
4. **Trace the end-to-end flow** — pick the primary user action and follow it through every layer: frontend → API route → service/lib → database → external service → response. Read each file in the chain. Don't stop at the service layer.
5. **Search for consumers** — grep for the feature's key types, table names, API endpoints, and module imports across the entire codebase. This catches secondary workflows (exports, scheduled jobs, webhooks, notifications, external automation) that live in different directories but depend on this feature. If you find consumers, read them and include those workflows in the doc.

Do not skim. Understand how the feature actually works before writing.

## Step 2 — Generate

1. Read the template from [doc-template.md](./doc-template.md) and follow it exactly
2. Write to `vdocs/FEATURE_NAME_DOC.md`

**Writing rules:**

- **YAML frontmatter** — every doc MUST start with frontmatter: `title`, `description`, `tags`, `version` (start at 1), `keyFiles` (array of primary source file paths), `relatedDocs` (array of other doc filenames), `lastUpdated` (YYYY-MM-DD). This metadata is the machine-readable contract — keep it in sync with the doc body.
- **CORE vs CONDITIONAL sections** — follow the `[CORE]` and `[CONDITIONAL]` markers in the template. Omit conditional sections entirely when not relevant. Do NOT leave empty sections or write "N/A".
- **Overview** must open with the value proposition — what problem does this feature solve for the user? Not just "manages X" but "enables users to Y without Z." A PM should understand the feature from this section alone.
- **Business Rules** — plain-language rules that govern behavior. No code. If you can't find explicit rules, derive them from the code and mark with `Inferred from code — verify with team`.
- **User Workflows** — describe 1-3 primary user journeys. [CONDITIONAL: omit for non-user-facing features]
- **"How It Works" must use sequence diagrams** for the primary flow — show every actor. Trace the COMPLETE path.
- **Key Files** — list every file in the execution path with a Type column (Source, Test, Config, Migration, etc.). Include test files and config files.
- **Testing** — include the test run command, test file locations, coverage gaps, and manual testing steps.
- **Common Tasks** — cookbook recipes for recurring modifications. [CONDITIONAL: omit when not applicable]
- **Data Model** — actual column names, types, descriptions. [CONDITIONAL: omit for features without persistent state]
- **Error Handling & Edge Cases** — specific failure scenarios, not generic. [CONDITIONAL: omit for features with no non-obvious failure modes]
- **Constraints & Decisions** — non-obvious choices + security considerations (auth, access control, secrets).
- **Related Features** — structured table: Doc, Relationship, Blast radius. Also populate `relatedDocs` frontmatter.
- **Change Log** — add initial entry with today's date.

## Step 3 — Update Manifest

Read `vdocs/_manifest.json` and add the new doc entry using the schema in [manifest-schema.json](./manifest-schema.json).

Include the `deps` array — list feature names (matching other manifest entries' titles) that would break if this feature changes. Populate from the Related Features table.

If `vdocs/_manifest.json` doesn't exist, create it with the project name, version, and this doc as the first entry.

## Step 4 — Generate Context Slice

Create a token-optimized context slice at `vdocs/_slices/{FEATURE_NAME}_SLICE.md`.

Extract ONLY these sections from the full doc:
- **Overview** (first paragraph only)
- **Business Rules** (full section)
- **Key Files** table (full table)
- **Constraints & Decisions** (full section)
- **Related Features** table (full table)

Add a header comment: `<!-- Context slice for {Feature Title} — auto-generated, do not edit manually -->` and a link back to the full doc.

## Step 5 — Self-Review

Before finishing, verify:

- [ ] Doc has valid YAML frontmatter (title, description, tags, version, keyFiles, relatedDocs, lastUpdated)
- [ ] Frontmatter `keyFiles` matches Key Files table entries
- [ ] Frontmatter `relatedDocs` matches Related Features table doc filenames
- [ ] Doc has at least one mermaid diagram in "How It Works"
- [ ] Doc has at least 2 entries in "Constraints & Decisions"
- [ ] Key Files lists real paths with Type column
- [ ] Doc has a Testing section with run command and coverage info
- [ ] Doc has Business Rules with at least one plain-language rule
- [ ] CONDITIONAL sections are omitted (not left empty) when not relevant
- [ ] Related Features uses structured table format (Doc, Relationship, Blast radius)
- [ ] Manifest entry includes `deps` array populated from Related Features
- [ ] Manifest `description` is detailed enough for semantic routing
- [ ] Context slice exists in `vdocs/_slices/`
- [ ] Doc explains WHY and HOW, not just WHAT
