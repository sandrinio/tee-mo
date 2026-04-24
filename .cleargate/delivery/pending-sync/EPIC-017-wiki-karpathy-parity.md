---
epic_id: "EPIC-017"
status: "Active"
children:
  - "STORY-017-09-slack-citation-blocks"
ambiguity: "🟡"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "Solo dev"
target_date: "TBD"
created_at: "2026-04-14T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
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
> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-017_wiki_karpathy_parity/EPIC-017_wiki_karpathy_parity.md`. Carried forward during ClearGate migration 2026-04-24.

> **Phase A shipped.** Phase A (STORY-017-01 `search_wiki` tool + STORY-017-02 compact system prompt) was delivered via direct commit `89f81d0` outside V-Bounce after S-11 close. Phases B–E (synthesis pages, cascade, ingest prompt tuning, curation + LLM lint) remain. This epic is `Active` with work in flight on Phase F (STORY-017-09 Slack citation blocks) in SPRINT-12.

# EPIC-017: Wiki Karpathy-Parity — Retrieval, Synthesis, Cascade

## 1. Problem & Value

### 1.1 The Problem

Sprint S-11 shipped the Karpathy-inspired wiki pipeline (EPIC-013). It **mechanically works** — 5 documents → 86 pages — but live production usage revealed gaps vs Karpathy's actual design:

1. **Prompt stuffing breaks at scale.** We stuff the entire Wiki Index (slug + full TLDR per page) into every agent system prompt. With 86 pages the prompt hits 30K chars (85% wiki index). At this size, Gemini 3 Flash **ignores the catalog and hallucinates fake document titles** ("Customer Support Playbook", "Product Roadmap 2024"). Karpathy explicitly notes this breaks past ~20 pages and points to retrieval (`qmd` — BM25 + vector + re-rank).

2. **Knowledge doesn't compound.** When the agent answers a multi-source question, the synthesis disappears into chat history. Karpathy's rule: *"Valuable findings become new wiki pages rather than disappearing."* We lose every insight the agent produces.

3. **Re-ingest has no cascade.** When a document changes, we delete pages sourced from that doc and re-ingest. Karpathy: *"A single source typically touches 10-15 existing pages."* We never update related existing pages — cross-refs drift, contradictions accumulate.

4. **Missing page types.** Karpathy's pattern calls out **comparison** and **synthesis** pages as first-class citizens. Our enum has `source-summary`, `concept`, `entity` only.

5. **Wiki is agent-only, not human-curated.** Karpathy's design is a *co-evolution loop* — human reviews, re-titles, removes bad pages. Our wiki has no review surface.

6. **Lint only catches structural issues.** Our lint finds orphans / stale / missing coverage / low-confidence pages. Karpathy's lint also catches **contradictions** and **stale claims** across sources.

### 1.2 The Solution

Bring Tee-Mo's wiki to **Karpathy parity** in five incremental steps:

> **Phase A is complete** (shipped via direct commit 89f81d0 outside V-Bounce — see Status note above). Phases B–F are pending.

1. **Replace prompt stuffing with retrieval (Phase A — SHIPPED).** `search_wiki(query)` agent tool. System prompt shows only compact slug catalog + search guidance. BM25 via Postgres `tsvector`.

2. **Synthesis page creation from queries (Phase B).** `create_wiki_page(type='synthesis', ...)` agent tool. Future queries benefit.

3. **Re-ingest cascade (Phase C).** When a source document changes, identify related existing pages via cross-refs and update them.

4. **Add `comparison` and `synthesis` page types (Phase B).** Expand the enum, update ingest prompts.

5. **Human curation surface + LLM lint (Phase E).** Minimal dashboard view of wiki pages with approve/delete actions. Extend `lint_wiki` with an optional LLM pass.

### 1.3 Success Metrics (North Star)

- **No more hallucinated document titles** — agent references only real pages from retrieval results
- **Wiki grows organically** — at least 20% of new wiki pages in steady state are `synthesis` pages
- **Prompt size stays bounded** — system prompt < 8K chars regardless of wiki size
- **Re-ingest cascade works** — updating a source document modifies at least 3 related pages on average
- **Lint catches contradictions** — opt-in LLM lint identifies at least one real contradiction per 50 pages in a test corpus

---

## 2. Scope Boundaries

### IN-SCOPE (Build This)

**Phase A — Retrieval (SHIPPED via direct commit 89f81d0)**
- [x] `search_wiki(query: str, top_k: int = 10) → list[dict]` agent tool
- [x] BM25 via Postgres `tsvector` full-text search
- [x] `search_vector` generated column to `teemo_wiki_pages` (tsvector over title + tldr + content)
- [x] GIN index on `search_vector` for fast BM25
- [x] Replace full `## Wiki Index` in system prompt with compact slug list + `search_wiki` instruction

**Phase B — Synthesis page creation**
- [ ] Add `synthesis` and `comparison` to `teemo_wiki_pages.page_type` CHECK constraint (migration)
- [ ] `create_wiki_page(slug, title, content, tldr, page_type, related_slugs)` agent tool
- [ ] System prompt rule: "When you produce a non-trivial multi-source answer, offer to save it as a `synthesis` page"
- [ ] `page_type='synthesis'` pages skip the ingest cascade (agent-authored, human-curated)

**Phase C — Re-ingest cascade**
- [ ] When `ingest_document` runs on a changed source, identify related pages via existing `related_slugs`
- [ ] For each related page, run a **light update pass** (scan-tier LLM) — "Here's new info from document X; update this page if the facts changed"
- [ ] Log cascade updates in `teemo_wiki_log` with `operation='cascade_update'`
- [ ] Bounded fan-out: max 10 pages updated per source change

**Phase D — Ingest prompt improvements**
- [ ] Update ingest prompt to detect comparison candidates
- [ ] Examples added to the prompt for each page type
- [ ] AI judge tuning loop extended with `comparison` and `synthesis` criteria

**Phase E — Human curation & LLM lint**
- [ ] Frontend wiki list page — `/app/teams/{team}/{workspace}/wiki` — browse pages, filter by type/source, delete bad pages
- [ ] Delete-page hook — when a page is deleted, log it and optionally trigger re-ingest of the source to backfill
- [ ] `lint_wiki(mode='llm')` — opt-in LLM pass that scans pages for contradictions; returns a report (no auto-fix)

**Phase F — Slack citation blocks**
- [ ] STORY-017-09: Slack citation footer — sources footer with clickable chips on grounded replies

### OUT-OF-SCOPE (Do NOT Build This)

- **Vector embeddings / pgvector** — BM25 first; vector only if BM25 proves insufficient
- **Automatic synthesis creation** — agent *may* create synthesis pages but must be prompted or asked
- **Real-time wiki editing in the UI** — v1 is read + delete only; edits require re-ingest
- **Cross-workspace knowledge sharing** — each workspace stays isolated
- **Wiki export to Obsidian / markdown** — defer to EPIC-018
- **Continuous LLM lint cron** — manual trigger only; too expensive for background
- **Graph view / backlinks UI** — `related_slugs` is the data model; visual graph deferred

---

## 3. Context

### 3.1 User Personas

- **Workspace Admin**: Adds documents, periodically checks wiki health, prunes bad pages
- **Slack User**: Asks questions; expects accurate, non-hallucinated answers grounded in real workspace content
- **Agent (Tee-Mo)**: Retrieves relevant pages via search; authors synthesis when producing novel multi-source insights

### 3.2 User Journey (Happy Path)

```mermaid
flowchart LR
    A["User asks cross-doc question"] --> B["Agent calls search_wiki(query)"]
    B --> C["Top-10 relevant pages returned"]
    C --> D["Agent reads 2-3 via read_wiki_page"]
    D --> E["Agent synthesizes answer"]
    E --> F["Agent offers: 'Save as wiki page?'"]
    F -->|Yes| G["create_wiki_page(type='synthesis')"]
    F -->|No| H["Answer only"]
    G --> I["Future queries benefit"]
```

### 3.3 Key Architecture Decisions (ADRs to add in Roadmap §3)

- **ADR-028**: BM25 via Postgres `tsvector` is the v1 retrieval layer. pgvector deferred until BM25 proves insufficient.
- **ADR-029**: Wiki index injection switches from full TLDR dump to compact slug list + `search_wiki` tool when workspace has >15 wiki pages.
- **ADR-030**: Synthesis pages are agent-authored and survive re-ingest. Source-summary/concept/entity pages are auto-regenerated on re-ingest (ephemeral).
- **ADR-031**: Re-ingest cascade is bounded to 10 related pages per source to prevent runaway LLM costs.

### 3.4 Technical Context (Adjacent Modules)

- `backend/app/services/wiki_service.py` — ingest, reingest, lint. Will gain: `search_wiki`, `create_wiki_page`, cascade logic.
- `backend/app/agents/agent.py` — add `search_wiki` and `create_wiki_page` tools; change system prompt assembly.
- `backend/app/services/wiki_ingest_cron.py` — trigger cascade after ingest.
- `database/migrations/` — new migration for `page_type` enum expansion + `search_vector` column + GIN index.
- `frontend/src/routes/` — new wiki viewer route.

### 3.5 Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| BM25 ranking insufficient for semantic queries | 🟡 Medium | 🟡 Medium | Fall back to combined search (BM25 + trigram similarity). Escalate to pgvector if still insufficient. |
| Cascade updates produce worse pages than the originals | 🟡 Medium | 🔴 High | Bounded fan-out (max 10 pages). AI judge evaluation loop on cascade output before commit. |
| Synthesis page creation becomes a hallucination vector | 🟢 Low | 🟡 Medium | Only allow agent to synthesize from pages it has actually read in the same conversation. |
| Human curation UI is never used | 🟢 Low | 🟢 Low | Keep UI minimal; ship without if solo-dev pushback. |
| LLM lint produces too many false positives | 🟡 Medium | 🟡 Medium | Ship as opt-in only. |

---

## 4. Technical Context

### 4.1 Current State (Post S-11)

- 86 wiki pages from 5 Drive documents in production workspace
- System prompt: 30K chars (85% wiki index)
- Gemini 3 Flash Preview hallucinates fake doc titles when asked "what documents do you have"
- `read_wiki_page(slug)` works — when the LLM picks the right slug
- Cross-refs via word-overlap on titles/tldr (naive but functional)
- Lint detects orphans/stale/missing/low-confidence (structural only)

### 4.2 Target State

- System prompt < 8K chars regardless of wiki size
- Agent uses `search_wiki(query)` as first retrieval step
- Synthesis pages created on demand from user queries
- Re-ingest propagates to related pages (bounded)
- Wiki curation surface in dashboard (delete + view)
- LLM-powered contradiction detection available on demand

### 4.3 Dependency Map

```
EPIC-013 (wiki pipeline baseline) ─┐
EPIC-015 (documents foundation)    ├─► EPIC-017 (this epic)
EPIC-016 (structured logging)     ─┘
```

---

## 5. Story Candidates (to be refined during sprint planning)

| ID | Story | Label | Phase | Est. |
|---|---|---|---|---|
| STORY-017-01 | BM25 search_wiki tool + tsvector migration | L2 | A — SHIPPED | 3-4h |
| STORY-017-02 | Compact system prompt — replace full index with slug catalog + search guidance | L1 | A — SHIPPED | 1-2h |
| STORY-017-03 | Add synthesis + comparison page types (enum migration) | L1 | B | 1h |
| STORY-017-04 | create_wiki_page agent tool + system prompt rule | L2 | B | 2-3h |
| STORY-017-05 | Re-ingest cascade (light update pass, bounded fan-out) | L3 | C | 4-6h |
| STORY-017-06 | Ingest prompt tuning for comparison detection | L2 | D | 3-4h |
| STORY-017-07 | Dashboard wiki viewer (list + delete) | L2 | E | 3-4h |
| STORY-017-08 | LLM-powered lint mode (opt-in contradiction detection) | L2 | E | 2-3h |
| STORY-017-09 | Slack citation blocks — sources footer on grounded replies | L3 | F | 5-7h |

**Estimated total: 24-34 hours (~2-3 sprints at 10-12h/sprint).**

---

## 6. Open Questions

| Question | Options | Impact | Status |
|---|---|---|---|
| BM25 vs BM25+trigram vs pgvector for v1 retrieval | (a) Pure BM25, (b) BM25 + pg_trgm similarity, (c) pgvector | Ranking quality vs migration complexity | **Open** — lean toward (b) |
| Should synthesis pages survive re-ingest? | Yes (agent-authored = durable) / No (regenerate everything) | Knowledge continuity | **Decided: Yes** (ADR-030) |
| How strict should the cascade fan-out cap be? | 5 / 10 / 20 / unlimited | Cost vs coverage | **Decided: 10** (ADR-031) |
| Should LLM lint run on the conversation-tier or scan-tier model? | Conversation (accurate) / Scan (cheap) | Cost vs quality | **Open** — lean toward scan-tier |
| Should frontend wiki viewer allow inline editing? | Yes / No (delete+reingest only) | Scope creep | **Decided: No** (v1) |

---

## 7. Non-Functional Requirements

- **Performance**: `search_wiki` returns in < 200ms for workspaces with <500 pages
- **Cost**: Cascade must not exceed $0.50/document (scan-tier model, bounded fan-out)
- **Observability**: Every cascade update logged to `teemo_wiki_log` with before/after hashes
- **Reliability**: Failed cascade updates do not block the initial ingest's success

---

## Change Log

| Date | Author | Change |
|---|---|---|
| 2026-04-14 | Claude (doc-manager) | Initial draft. Based on S-11 production post-mortem + Karpathy gist review. Addresses: hallucination from prompt stuffing, missing synthesis creation, no re-ingest cascade, missing page types, no human curation. |
| 2026-04-20 | Team Lead (status audit) | Status Draft → In Progress. Phase A (STORY-017-01 search_wiki + 017-02 compact prompt) shipped via direct commit 89f81d0 after S-11 close — verified in backend/app/agents/agent.py + wiki_service.py. Phases B/C/D/E remain. |
| 2026-04-21 | Claude (doc-manager) | Added STORY-017-09 (Slack citation blocks) under new Phase F. Triggered by user request with UX reference screenshot. L3 cross-cutting: touches source-tool return contracts, new citation collector on AgentDeps, Block Kit upgrade in slack_dispatch. Depends on FRONTEND_URL setting landed on main 2026-04-21 (commit 02b2864). |
