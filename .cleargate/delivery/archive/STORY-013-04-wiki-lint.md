---
story_id: "STORY-013-04"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-11/STORY-013-04-wiki-lint.md`. Shipped in sprint S-11, carried forward during ClearGate migration 2026-04-24.

# STORY-013-04: Wiki Lint Agent Tool

**Complexity: L2** — 1 tool function + wiki_service lint function, ~2hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> Add a `lint_wiki` agent tool that scans the workspace wiki for quality issues: orphan pages, contradictions, stale pages, missing cross-references. Returns a structured report. Manual trigger only for v1.

### 1.2 Detailed Requirements

- **R1 — `lint_wiki()` agent tool**: Calls `wiki_service.lint_wiki(supabase, workspace_id)`.
- **R2 — Lint checks**:
  - **Orphan pages**: pages with no incoming `related_slugs` from any other page.
  - **Stale pages**: pages whose `source_document_ids` reference documents with `sync_status='pending'` (content changed but wiki not yet re-ingested).
  - **Missing summaries**: documents in `teemo_documents` with no corresponding `source-summary` page in `teemo_wiki_pages`.
  - **Low confidence**: pages with `confidence='low'`.
- **R3 — Output format**: Returns a markdown report: "Wiki Health Report\n- X orphan pages\n- Y stale pages\n- Z documents missing wiki pages\n- W low-confidence pages\n\nDetails: ..."
- **R4 — Logging**: Log lint operation in `teemo_wiki_log`.

### 1.3 Out of Scope
- Automatic lint on cron (deferred to v2)
- LLM-powered contradiction detection (deferred — too expensive for v1, just check structural issues)
- Auto-fix for detected issues

---

## 2. The Truth (Executable Tests)

```gherkin
Feature: Wiki Lint

  Scenario: Lint detects orphan pages
    Given a wiki page with no incoming related_slugs
    When lint_wiki runs
    Then the report lists the page as orphaned

  Scenario: Lint detects stale pages
    Given a document with sync_status "pending" and existing wiki pages
    When lint_wiki runs
    Then the report flags those pages as stale

  Scenario: Lint detects missing wiki coverage
    Given a document in teemo_documents with no wiki pages
    When lint_wiki runs
    Then the report flags the document as missing wiki pages
```

---

## 3. The Implementation Guide (AI-to-AI)

### 3.1 Files
| Item | Value |
|------|-------|
| **Modified files** | `backend/app/services/wiki_service.py` (add lint function), `backend/app/agents/agent.py` (add lint tool) |

### 3.2 Technical Logic
1. Pure DB queries — no LLM calls. Query wiki pages for orphans, cross-check with documents for staleness/coverage.
2. Format results as readable markdown.
3. Register `lint_wiki` in agent tools list.

---

## Change Log
| Date | Author | Change |
|------|--------|--------|
| 2026-04-13 | Claude (doc-manager) | Initial draft for S-11. |
