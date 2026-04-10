# Init Workflow

## Step 1 — Explore

Follow the two-phase exploration strategy in `references/exploration-strategies.md`:

**Phase 1 — Fingerprint** (3-5 file reads max)
Read package/config files and directory structure using Read, Glob, and Grep to identify the project's language, framework, and archetype. Also check for existing documentation (`vdocs/`, `docs/`, `product_documentation/`, substantial `*.md` files). If found, read them first — they're a head start. See the "Existing Documentation" section in `references/exploration-strategies.md`.

**Phase 2 — Targeted Exploration** (archetype-specific)
Apply the matching archetype playbook from `references/exploration-strategies.md`. Read files in priority order using the glob patterns listed. Identify feature signals — each signal maps to a documentable feature. Combine multiple playbooks when the project doesn't fit a single archetype (see "Composing Archetypes" in the strategies file).

If no archetype matches, use the Fallback strategy and confirm with the user.

Do not skim. Understand how the system actually works before proposing docs.

**Phase 2b — Behavior Discovery** (universal — runs after archetype playbook)
Apply the 4-layer discovery protocol from `references/discovery-protocol.md`:
1. **Capability Surface** — Map every entry point (routes, endpoints, commands, exports)
2. **Data Flows** — For each capability, trace data from source to screen to mutation
3. **Shared Behaviors** — Find cross-cutting concerns (auth, error handling, notifications, feature flags)
4. **Integration Boundary** — Map every external touchpoint (outgoing API calls, incoming webhooks, background jobs, env vars)

This catches behaviors that file-structure exploration misses: background jobs, event-driven workflows, hidden integrations, cross-feature dependencies.

**Important:** Use your built-in tools (Read, Glob, Grep) to explore. Do NOT create scanner scripts, shell scripts, or any tooling. vdoc is purely AI-driven — no scripts, no build steps, no infrastructure.

**Phase 3 — Write Exploration Log**
After exploring, write `vdocs/_planning/_exploration_log.md` documenting what you found:

```markdown
# Exploration Log

## Fingerprint
- **Language(s):** e.g., TypeScript, Python
- **Framework(s):** e.g., Next.js 14, FastAPI
- **Archetype(s):** e.g., Full-stack Framework
- **Scope:** e.g., ~85 files, medium

## Files Read
| # | File | Why | What I Found |
|---|------|-----|--------------|
| 1 | package.json | Fingerprint | Next.js 14, Prisma, NextAuth |
| 2 | src/app/ (listing) | Page tree | 12 routes, 3 API routes |
| ... | ... | ... | ... |

## Feature Signals Detected
| Signal | Source File(s) | Proposed Doc |
|--------|---------------|--------------|
| Auth middleware + login page | middleware.ts, app/login/page.tsx | AUTHENTICATION_DOC.md |
| Prisma schema with 8 models | prisma/schema.prisma | DATA_MODEL_DOC.md |
| ... | ... | ... |

## Capability Surface
| Entry Point | Type | Proposed Doc |
|-------------|------|--------------|
| /api/auth/* | Auth routes (5 endpoints) | AUTHENTICATION_DOC.md |
| /dashboard | Page + 3 sub-routes | DASHBOARD_DOC.md |

## Data Flows
| Feature | State Source | API Calls | Mutations |
|---------|-------------|-----------|----------|
| Dashboard | useDashboardStore | GET /api/stats | None (read-only) |

## Shared Behaviors
| Behavior | Scope | Implementation |
|----------|-------|----------------|
| Auth | All /app/* routes | NextAuth middleware + useSession hook |

## Integration Boundary
| Direction | System | Purpose | Env Var |
|-----------|--------|---------|--------|
| Outgoing | Stripe API | Payments | STRIPE_SECRET_KEY |
| Incoming | Stripe webhooks | Payment events | /api/webhooks/stripe |
| Background | Cron: cleanup-sessions | Expire old sessions | Vercel Cron |

## Cross-Feature Dependencies
After identifying all feature signals, grep for imports/references between features to map which features consume each other's data, types, or APIs. This prevents missing secondary workflows during doc generation.

| Feature A | Feature B | Connection | Impact |
|-----------|-----------|------------|--------|
| Azure DevOps Integration | Google Sheets Export | Sheets exports work items fetched by Azure module | Azure doc must cover the export workflow |
| Auth (NextAuth) | All API routes | Every route uses auth middleware | Auth doc must list all protected routes |
| ... | ... | ... | ... |

## Ambiguities / Open Questions
- Could not determine why Redis is in dependencies — no usage found. Ask user.
- Payments folder exists but appears incomplete / WIP.
```

This log is your working memory. It feeds directly into Step 2 (Plan).

## Step 2 — Plan

Write `vdocs/_planning/_DOCUMENTATION_PLAN.md` to disk AND present it to the user in the same step. The file must be persisted — do not just show it in chat.

Use this format:

```markdown
# Documentation Plan

## Fingerprint
- **Language(s):** e.g., TypeScript, Python
- **Framework(s):** e.g., Next.js 14, FastAPI
- **Archetype(s):** e.g., Full-stack Framework
- **Scope:** e.g., ~85 files, medium

## Proposed Documents

1. **PROJECT_OVERVIEW_DOC.md** — Tech stack, architecture, project structure, dev setup
2. **AUTHENTICATION_DOC.md** — OAuth2 flow, JWT lifecycle, session management, RBAC
3. **API_REFERENCE_DOC.md** — All endpoints, request/response shapes, error codes
...

## Notes
- Each doc covers one logical feature, not one file
- Docs should be useful for onboarding AND as AI context for planning changes
```

After writing the file, present the plan to the user. Actively suggest changes:
- "Should I merge X and Y into one doc?"
- "I found a websocket system — want that documented separately?"
- "Any internal/legacy systems I should skip?"

Wait for user approval before proceeding.

## Step 3 — Generate

Read the template from [doc-template.md](./doc-template.md) once before starting.

Then generate docs **one at a time, sequentially**. For each approved doc:

1. Read ALL relevant source files for that feature — not just the main file, but helpers, types, middleware, tests
2. **Trace the end-to-end flow** — pick the primary user action and follow it through every layer: frontend → API route → service/lib → database → external service → response. Read each file in the chain. Don't stop at the service layer.
3. **Search for consumers** — grep for the feature's key types, table names, API endpoints, and module imports across the entire codebase. This catches secondary workflows (exports, scheduled jobs, webhooks, notifications, external automation) that live in different directories but depend on this feature. If you find consumers, read them and include those workflows in the doc.
4. Write `vdocs/FEATURE_NAME_DOC.md` following the template exactly
5. Confirm the file was written before moving to the next doc

Do NOT attempt to generate multiple docs from memory. Each doc is a fresh cycle: read sources → trace flows → search consumers → write doc → next.

**Writing rules:**

- **YAML frontmatter** — every doc MUST start with frontmatter: `title`, `description`, `tags`, `version` (start at 1), `keyFiles` (array of primary source file paths), `relatedDocs` (array of other doc filenames), `lastUpdated` (YYYY-MM-DD). This metadata is the machine-readable contract — keep it in sync with the doc body.
- **CORE vs CONDITIONAL sections** — follow the `[CORE]` and `[CONDITIONAL]` markers in the template. Omit conditional sections entirely when not relevant. Do NOT leave empty sections or write "N/A".
- **Overview** must open with the value proposition — what problem does this feature solve for the user? Not just "manages X" but "enables users to Y without Z." A PM should understand the feature from this section alone.
- **Business Rules** — plain-language rules that govern behavior. No code. "Free users get 3 projects", "Sessions expire after 30 min of inactivity", "Rate limit: 100 req/min per API key." If you can't find explicit rules, derive them from the code and mark with `Inferred from code — verify with team`.
- **User Workflows** — describe 1-3 primary user journeys step by step: what the user does, what the system does, what the user sees. This grounds the doc in product reality. [CONDITIONAL: omit for non-user-facing features like background jobs]
- **"How It Works" must use sequence diagrams** for the primary flow — show every actor (user, frontend, API, service, database, external systems). Flowcharts are for branching logic only. Trace the COMPLETE path — if there's a cron job that calls an executor that calls an external API, show all three, not just "cron → external API."
- **Key Files** — list every file in the execution path with a Type column (Source, Test, Config, Migration, Script, Route, Hook, Store). Include test files and config files, not just source. If a cron handler, executor, service, and DB helper are all involved, list all of them.
- **Testing** — include the test run command, test file locations, what's covered, coverage gaps (honest assessment), and manual testing steps. This is critical for AI coders and onboarding developers.
- **Common Tasks** — cookbook-style recipes for recurring modifications: "To add a new payment method, do X, Y, Z." [CONDITIONAL: omit for features with no recurring modification patterns]
- **Data Model** must show actual column names, types, and descriptions for primary tables — not just entity names in an ER diagram. Read the actual schema/types files. [CONDITIONAL: omit for features without persistent state]
- **Error Handling & Edge Cases** — list specific failure scenarios: "If the user's OAuth token expires, the system does X. The user sees Y." Not generic "errors are logged." Think: what breaks at 2 AM with no user present? [CONDITIONAL: omit for features with no non-obvious failure modes]
- **Constraints & Decisions** is the most valuable section. Dig into the code for non-obvious choices: "Uses polling instead of websockets because...", "Auth tokens expire in 15min because...". Include security considerations here — auth patterns, access control, secrets. If you can't find the reason, state the constraint and mark it: `Reason: unknown — verify with team`.
- **Related Features** — structured table with Doc, Relationship (depends on / depended by / shares data with), and Blast radius columns. Reference other docs by filename. Also populate the `relatedDocs` frontmatter array with the same filenames.
- **Change Log** — add initial entry with today's date and "Initial documentation".

## Step 4 — Manifest

Create `vdocs/_manifest.json` using the schema in [manifest-schema.json](./manifest-schema.json).

**Transfer the Fingerprint** from the exploration log into the manifest's top-level `fingerprint` object. This preserves the project identity metadata alongside the documentation inventory.

The `description` field is critical — write it rich enough that you can route any user question to the right doc by matching against descriptions. Include specific technology names, patterns, and concepts.

The `deps` field lists feature names (matching other entries' titles) that would break or behave differently if this feature changes. Populate from the Related Features table's "depends on" and "depended by" relationships. This enables blast radius analysis by downstream consumers.

Example:

```json
{
  "project": "my-project",
  "fingerprint": {
    "languages": ["TypeScript"],
    "frameworks": ["Next.js 14", "Prisma", "NextAuth"],
    "archetypes": ["Full-stack Framework"],
    "scope": "~85 files, medium"
  },
  "documentation": [
    {
      "filepath": "AUTHENTICATION_DOC.md",
      "title": "Authentication - OAuth2 & JWT",
      "version": "1.0.0",
      "description": "OAuth2 flow with Google/GitHub providers, JWT token lifecycle, session management via NextAuth.js, route protection middleware, and role-based access control.",
      "tags": ["oauth2", "jwt", "session-management", "rbac"],
      "deps": ["user-profile", "billing", "api-reference"]
    }
  ]
}
```

## Step 5 — Generate Context Slices

For each generated doc, create a token-optimized context slice at `vdocs/_slices/{FEATURE_NAME}_SLICE.md`.

A context slice contains ONLY these sections extracted from the full doc:
- **Overview** (first paragraph only)
- **Business Rules** (full section)
- **Key Files** table (full table)
- **Constraints & Decisions** (full section)
- **Related Features** table (full table)

Format:

```markdown
<!-- Context slice for {Feature Title} — auto-generated, do not edit manually -->
<!-- Full doc: vdocs/{FEATURE_NAME_DOC}.md -->

# {Feature Title}

{First paragraph of Overview}

## Business Rules
{Full Business Rules section}

## Key Files
{Full Key Files table}

## Constraints & Decisions
{Full Constraints & Decisions section}

## Related Features
{Full Related Features table}
```

These slices are designed for AI agent consumption — compact enough to include in context packs without exceeding token budgets. They auto-regenerate whenever the parent doc is created or updated.

## Step 6 — Self-Review

Before finishing, verify:

- [ ] Every doc has valid YAML frontmatter (title, description, tags, version, keyFiles, relatedDocs, lastUpdated)
- [ ] Frontmatter `keyFiles` matches the Key Files table entries
- [ ] Frontmatter `relatedDocs` matches the Related Features table doc filenames
- [ ] Every doc has at least one mermaid diagram in "How It Works"
- [ ] Every doc has at least 2 entries in "Constraints & Decisions"
- [ ] Every doc's Key Files lists real paths that exist in the codebase (include Type column)
- [ ] Every doc has a Testing section with run command and coverage info
- [ ] Every doc's Related Features uses the structured table format (Doc, Relationship, Blast radius)
- [ ] Manifest entries include `deps` arrays populated from Related Features
- [ ] Manifest `description` is detailed enough for semantic routing
- [ ] No doc is just a shallow restatement of file names — each explains WHY and HOW
- [ ] Every doc has "Business Rules" with at least one plain-language rule
- [ ] CONDITIONAL sections are omitted (not left empty) when not relevant
- [ ] Context slices exist in `vdocs/_slices/` for every generated doc
- [ ] Planning artifacts are in `vdocs/_planning/` (exploration log, doc plan)
