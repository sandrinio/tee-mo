---
story_id: "STORY-013-01"
parent_epic_ref: "EPIC-013"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-14T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
server_pushed_at_version: null
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-013-01-wiki-tables-read-tool.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-013-01: Wiki Tables + read_wiki_page Agent Tool + System Prompt

**Complexity: L2** — 1 migration + 1 agent tool + system prompt change, ~3hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Create the `teemo_wiki_pages` and `teemo_wiki_log` tables. Add the `read_wiki_page(slug)` agent tool and replace the transitional `## Available Documents` system prompt section with the wiki index (slug + TLDR per page).

### 1.2 Detailed Requirements

- **R1 — Migration**: Create `teemo_wiki_pages` table per EPIC-013 §4.5 schema. Create `teemo_wiki_log` table.
- **R2 — `read_wiki_page(slug)` agent tool**: Queries `teemo_wiki_pages` by `slug` + `workspace_id`. Returns page `content`. Returns "Wiki page not found" if no match.
- **R3 — Wiki index in system prompt**: Replace EPIC-015's transitional `## Available Documents` with `## Wiki Index`. Lists all wiki pages for the workspace: `- [{slug}] {title} — {tldr}`. If no wiki pages exist yet, fall back to the transitional document list.
- **R4 — Health check**: Add `teemo_wiki_pages` and `teemo_wiki_log` to `TEEMO_TABLES`.

### 1.3 Out of Scope
- Wiki ingest pipeline (STORY-013-02)
- Wiki ingest cron (STORY-013-03)
- Lint (STORY-013-04)

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Wiki Tables + Agent Read Tool

  Scenario: teemo_wiki_pages table exists
    Given the migration has been applied
    Then teemo_wiki_pages and teemo_wiki_log tables exist

  Scenario: read_wiki_page returns page content
    Given a wiki page with slug "onboarding-process" exists
    When the agent calls read_wiki_page("onboarding-process")
    Then the page content is returned

  Scenario: read_wiki_page returns not found
    When the agent calls read_wiki_page("nonexistent-slug")
    Then "Wiki page not found" is returned

  Scenario: System prompt shows wiki index when pages exist
    Given a workspace with 5 wiki pages
    When the agent system prompt is built
    Then ## Wiki Index lists all 5 pages with slug, title, TLDR

  Scenario: System prompt falls back to document list when no wiki pages
    Given a workspace with 3 documents but 0 wiki pages
    When the agent system prompt is built
    Then ## Available Documents lists the 3 documents (transitional behavior)
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **New files** | `database/migrations/0XX_teemo_wiki_pages.sql` |
| **Modified files** | `backend/app/agents/agent.py` (add tool, update system prompt), `backend/app/main.py` (TEEMO_TABLES) |

### 3.2 Technical Logic
1. Write migration per EPIC-013 §4.5 — `source_document_ids` is `UUID[]`.
2. Add `read_wiki_page` tool to agent.py, register in tools list.
3. Update `_build_system_prompt()`: query `teemo_wiki_pages` for the workspace. If pages exist, render wiki index. Otherwise, fall back to document catalog.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 1,995 | 4,677 | 6,672 |
