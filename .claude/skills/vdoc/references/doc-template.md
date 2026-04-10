---
title: "{Feature Title}"
description: "{One-line description of what this covers}"
tags: ["{domain}", "{capability}"]
version: 1
keyFiles: ["{src/path/main-file.ts}"]
relatedDocs: []
lastUpdated: "{YYYY-MM-DD}"
---

# {Feature Title}

> {One-line description — same as frontmatter description}

<!-- TEMPLATE GUIDANCE
  Sections marked [CORE] — always include.
  Sections marked [CONDITIONAL] — include only when relevant, omit entirely otherwise.
  Do NOT leave empty sections or write "N/A".
-->

---

## Overview
<!-- [CORE] -->

{What it does, why it exists, and who it's for. Lead with the user value — what problem does this solve? Then explain how it fits in the broader system. A PM should be able to read this section alone and understand the feature.}

---

## Business Rules
<!-- [CORE] -->

{Plain-language rules that govern this feature's behavior. No code, no implementation details — just the "what" and "why" a PM or stakeholder needs to know.}

- {Rule}: {Description}

<!-- Examples:
- **Trial limit**: Free users get 3 projects. Creating a 4th triggers the upgrade prompt.
- **Auto-archive**: Inactive workspaces are archived after 90 days. Owners get email warnings at 60 and 80 days.
- **Rate limiting**: API consumers are capped at 100 req/min per API key. Exceeding returns 429.
-->

---

## User Workflows
<!-- [CONDITIONAL: include for user-facing features] -->

{Step-by-step journeys for the 1-3 primary user actions.}

1. **{Workflow Name}**
   - **Trigger:** {What the user does}
   - **Steps:** {What happens — keep it sequential}
   - **Result:** {What the user sees or gets}

---

## How It Works
<!-- [CORE] -->

{Trace at least one complete request from trigger to final effect. Show the full path through every service, database call, and external system. Don't skip intermediaries.}

{Use a sequence diagram for the primary flow — show all actors. Use flowcharts for branching logic only. Max 7-9 nodes per diagram, split into multiple if larger.}

---

## Key Files

<!-- [CORE] -->

| File | Type | Purpose |
|------|------|---------|
| `src/path/file.ts` | Source | {What this file does} |
| `src/path/file.test.ts` | Test | {What it validates} |
| `.env` / `config.ts` | Config | {What it controls} |

<!-- Type = Source, Test, Config, Migration, Script, Route, Hook, Store, Template, etc. -->

---

## Testing
<!-- [CORE] -->

**Run:** `{test command — e.g. npm test -- --grep "feature-name"}`

| What | Location | Notes |
|------|----------|-------|
| Unit tests | `{path}` | {What's covered} |
| Integration tests | `{path}` | {What's covered} |
| E2E tests | `{path}` | {What's covered} |

**Coverage gaps:** {What is NOT tested and why — honest assessment. "None" if fully covered.}

**Manual testing:** {Steps for anything that requires manual verification, or "Fully automated" if none.}

---

## Common Tasks
<!-- [CONDITIONAL: include when feature has recurring modification patterns] -->

{Cookbook-style recipes for the things developers actually do with this feature. Each recipe should be copy-paste actionable.}

### {Task name — e.g. "Add a new payment method"}
1. {Step}
2. {Step}
3. {Step}

<!-- Keep recipes short (3-6 steps). If a task needs more, it's probably a workflow, not a recipe. -->

---

## Data Model
<!-- [CONDITIONAL: include when feature owns database tables or persistent state] -->

{Primary tables/collections this feature owns.}

| Column | Type | Description |
|--------|------|-------------|
| `column_name` | `type` | What it stores |

{Mermaid ER diagram for relationships between tables.}

---

## Dependencies & Integrations
<!-- [CONDITIONAL: include when feature depends on external services or other features] -->

| Dependency | Type | What breaks if it's down |
|------------|------|--------------------------|
| `{service/package/feature}` | External / Internal | {Impact} |

---

## Error Handling & Edge Cases
<!-- [CONDITIONAL: include when feature has non-obvious failure modes] -->

- **{Scenario}** — {What triggers it}. User sees: {what}. System does: {recovery/logging}.

---

## Constraints & Decisions
<!-- [CORE] -->

{Why it's built this way. What you CANNOT change without breaking things. Include security considerations here — auth patterns, access control, secrets — when relevant.}

- **{Decision}**: {What was decided and why. What alternative was rejected.}

---

## Related Features
<!-- [CORE] -->

| Doc | Relationship | Blast radius |
|-----|-------------|--------------|
| `{filename.md}` | {depends on / depended by / shares data with} | {What breaks if this feature changes} |

---

## Change Log

| Date | Change | By |
|------|--------|-----|
| {YYYY-MM-DD} | Initial documentation | vdoc |
