---
story_id: "STORY-017-09-slack-citation-blocks"
parent_epic_ref: "EPIC-017"
status: "Draft"
ambiguity: "🟡 Medium"
context_source: "User request (Slack citations UX screenshot, 2026-04-21) / EPIC-017 §1.2 retrieval goals / backend/app/agents/agent.py tool pattern / backend/app/services/slack_dispatch.py posting surface / backend/app/services/slack_formatter.py mrkdwn conversion"
actor: "Slack user consuming agent replies"
complexity_label: "L3"
---

# STORY-017-09: Slack Citation Blocks — Sources Footer on Grounded Replies

**Complexity: L3** — Cross-cutting. Touches source-producing tool return shapes (wiki + document + web), adds a citation collector on `AgentDeps`, and upgrades `slack_dispatch` from `text=` posts to Block Kit payloads with a sources footer. No new infra, but the contract change between agent tools and the dispatcher is the risky part.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack user asking Tee-Mo a question**,
> I want to **see which workspace documents, wiki pages, or URLs the answer came from as clickable chips under the reply**,
> So that **I can verify the answer against the source without pestering the agent for "where did you get that?" follow-ups**.

Reference UX (provided by user in 2026-04-21 conversation): a Block Kit context footer titled **SOURCES** followed by one row per cited source — document icon + filename as a clickable mrkdwn link + a muted category tag (e.g. "52 Digital products").

### 1.2 Detailed Requirements

**R1 — Source-producing tools attach citation metadata to a per-run collector**
- `search_wiki`, `read_wiki_page`, `read_document` (wiki + documents tools) and `web_search`, `crawl_page`, `http_request` (web tools) MUST append structured citation records to a list living on `ctx.deps.citations` during tool execution.
- Record shape (pydantic dataclass or TypedDict — choose per codebase norm):
  ```python
  class Citation:
      kind: Literal["wiki", "document", "web"]
      title: str          # "Refund Policy.docx", "Onboarding Overview", "Stripe Docs"
      url: str | None     # Google Drive link for documents, canonical URL for web, None for wiki (see R2)
      category: str | None  # "Digital products", "drive", "web", a wiki page-type, etc.
      source_id: str      # stable dedupe key: doc_id, wiki_slug, sha256(url)
  ```
- Tools append — they do NOT overwrite. A single run can cite many sources.
- Tools that return nothing useful (empty search, failed crawl) MUST NOT append — no citations for empty results.

**R2 — Wiki pages cite via deep-link to the dashboard wiki viewer**
- `read_wiki_page` cites with `url=f"{settings.frontend_url}/app/teams/{team}/{workspace}/wiki/{slug}"` when `frontend_url` is set; otherwise `url=None` and the chip renders as plain label (no link).
- The viewer route itself is owned by STORY-017-07 (dashboard wiki viewer) — this story does NOT build the route, but its link shape must match STORY-017-07's eventual path.

**R3 — Documents cite via Google Drive `webViewLink`**
- `read_document` already has access to the document row in `teemo_documents`; it MUST pass `drive_file_url` (or whatever column stores the Drive webViewLink — confirm in implementation) into the Citation.
- When the Drive link is missing, `url=None` and the chip shows as plain-label.

**R4 — Dispatcher builds a Block Kit payload when citations are present**
- After `agent.run` completes, `slack_dispatch` inspects `deps.citations`.
- If the list is empty: post as today (`chat_postMessage(text=reply)`).
- If non-empty: post a `blocks=[...]` payload — see §3.3 — AND keep `text=` populated with the reply so Slack notifications still show content.

**R5 — Deduplication and cap**
- Collapse citations by `source_id` (keep first occurrence).
- Cap to **5 displayed sources** after dedupe. If more, render the first 5 and a 6th chip reading `+N more` with no link.

**R6 — No citations leak when the agent didn't use a source tool**
- A pure generative reply ("hi, how can I help?") MUST NOT emit a SOURCES footer.
- An answer that used `web_search` but decided none of the results were relevant (zero source-yielding tool calls) MUST NOT emit a footer.

**R7 — System prompt instruction**
- Add one sentence to the preamble in `_build_system_prompt`: *"Citations are attached automatically from the tools you call — do not fabricate a 'Sources:' section in your reply text."*

### 1.3 Out of Scope
- Inline per-sentence superscript citations (Perplexity-style `[¹]` markers). This story is footer-only.
- Dashboard / web surface — only Slack posting is in scope. The wiki viewer route (STORY-017-07) is a dependency for the wiki chip URL but not built here.
- Thread-level citation aggregation (e.g. showing all sources used across a multi-turn thread). Scope is per-reply.
- Editing / dismissing sources from the chip (Block Kit `actions` with buttons). Chips are links only.
- Citation analytics / click tracking.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: Slack citation footer

  Scenario: Wiki-grounded answer emits a sources footer
    Given a workspace with wiki page slug="refund-policy" title="Refund Policy" page_type="source-summary"
    And the agent is prompted "what is our refund policy?"
    When the agent calls read_wiki_page("refund-policy") and replies
    Then slack_dispatch posts a chat.postMessage with blocks=[...]
    And the blocks contain a section block with the reply text
    And the blocks contain a context block whose first element text is "*SOURCES*"
    And the blocks contain a context block whose mrkdwn element includes "<{frontend_url}/app/teams/.../wiki/refund-policy|Refund Policy>"
    And chat.postMessage is called with text=<the reply> so notifications still fire

  Scenario: Document-grounded answer cites with Drive webViewLink
    Given a document titled "Refund Policy.docx" with drive_file_url="https://drive.google.com/file/d/abc/view"
    When the agent calls read_document(doc_id) and replies
    Then the sources footer contains "<https://drive.google.com/file/d/abc/view|Refund Policy.docx>"

  Scenario: Web-tool answer cites the URL
    Given the agent calls crawl_page("https://stripe.com/docs/refunds")
    When the agent replies
    Then the sources footer contains a chip linking to "https://stripe.com/docs/refunds"
    And the chip title is the page <title> or hostname if title extraction failed

  Scenario: Pure generative reply has no sources footer
    Given the agent replies to "hi" without calling any source-producing tool
    Then chat.postMessage is called with text= only (no blocks field) OR blocks without a SOURCES context block

  Scenario: Citations dedupe by source_id
    Given the agent calls read_document(doc-1) twice in a single run
    Then the sources footer contains exactly one chip for doc-1

  Scenario: Overflow capped at 5 + "+N more"
    Given the agent cites 8 distinct sources in a single run
    Then the footer renders exactly 5 source chips
    And a trailing chip reads "+3 more" with no link

  Scenario: Missing frontend_url falls back to plain-label wiki chip
    Given settings.frontend_url = ""
    When read_wiki_page("x") is the only cited source
    Then the chip renders as plain text "x-title" (no <url|text> link)

  Scenario: Failed tool call contributes no citation
    Given web_search raises an exception or returns []
    Then no citation is appended for that call
```

### 2.2 Verification Steps (Manual)
- [ ] In the prod workspace, ask a wiki-backed question in Slack. Reply shows the SOURCES footer with a chip linking to the wiki viewer (or plain-label if the viewer route isn't live yet).
- [ ] Ask a document-backed question. Chip links to Google Drive and opens the doc.
- [ ] Ask an off-topic question ("what's 2+2?"). No SOURCES footer appears.
- [ ] Ask a question that forces 6+ distinct sources. Footer shows 5 + "+N more".
- [ ] Verify Slack notifications still preview the reply text (fallback `text=` is populated).
- [ ] Inspect one message via `chat.getPermalink` + Slack's "Copy text" to confirm the footer isn't duplicated in the plaintext view.

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|---|---|---|
| Env Vars | `FRONTEND_URL` (new, from the 2026-04-21 drive-oauth fix) controls wiki chip links | [ ] |
| Services Running | Slack bot installed into a test workspace | [ ] |
| Migrations | None — this story is code-only | [ ] |
| Seed Data | At least one wiki page, one document with `drive_file_url`, and one reachable web URL in the test workspace | [ ] |
| Dependencies | `pydantic-ai` already installed; no new Python packages | [ ] |

### 3.1 Test Implementation
- `backend/tests/test_citation_collector.py` (new) — unit tests for the collector: append, dedupe, cap, record shape.
- `backend/tests/test_agent_citations.py` (new) — integration-level: monkeypatch the source tools to append Citations, run `build_agent().run(...)` against a fake model, assert `deps.citations` contents per scenario.
- `backend/tests/test_slack_dispatch_blocks.py` (new) — unit: feed a reply + citations list into the block-builder, assert the produced Block Kit JSON matches each §2.1 scenario.
- Extend `backend/tests/test_slack_dispatch.py` with the "no citations → no blocks" scenario to lock the fallback path.

Every Gherkin scenario in §2.1 maps to at least one test above.

### 3.2 Context & Files

| Item | Value |
|---|---|
| **Primary Files** | `backend/app/agents/agent.py` (AgentDeps, source tools, system prompt), `backend/app/services/slack_dispatch.py` (block builder + chat_postMessage call site), `backend/app/services/slack_formatter.py` (already-existing mrkdwn converter — reuse for chip titles) |
| **Related Files** | `backend/app/services/wiki_service.py` (wiki read path), `backend/app/services/document_service.py` or equivalent (drive_file_url accessor), `backend/app/services/web_tools.py` (if web tools live there — confirm on implementation) |
| **New Files Needed** | Yes — `backend/app/services/citation_collector.py` (Citation dataclass + collector helpers) and `backend/app/services/slack_blocks.py` (pure block builders — input: reply + citations, output: Block Kit list) |
| **ADR References** | New ADR-032 (proposed): "Citations are attached to Slack replies via Block Kit, collected from tool execution rather than parsed from LLM output." Roadmap §3 entry added as part of this story. |
| **First-Use Pattern** | Yes — first use of Block Kit `blocks=` payloads in `slack_dispatch`; all existing posts use `text=` only. Developer MUST grep for prior Block Kit usage and flashcard the pattern after merge. |

### 3.3 Technical Logic

**Citation collector**
- `AgentDeps` (dataclass already in `agent.py`) gains `citations: list[Citation] = field(default_factory=list)`.
- Every source-producing tool, after computing its return value, calls `ctx.deps.citations.append(Citation(...))`. Do this BEFORE returning so a tool error skips the append naturally.

**Block builder (new `slack_blocks.py`)**
- Entry point: `build_reply_blocks(reply_mrkdwn: str, citations: list[Citation]) -> list[dict] | None`.
- Returns `None` when `citations` is empty — caller treats `None` as "use the text=-only path".
- Otherwise returns:
  ```python
  [
    {"type": "section", "text": {"type": "mrkdwn", "text": reply_mrkdwn}},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "*SOURCES*"}]},
    *[_chip_block(c) for c in deduped_and_capped(citations)],
  ]
  ```
- `_chip_block` renders a `context` block with:
  - a document/web icon `image` element (static asset URL — pick a public Slack-safe icon per kind; add to FLASHCARDS.md),
  - a `mrkdwn` element: `"<{url}|{title}>  `{category}`"` when `url` is set, else `"{title}  `{category}`"` (no link).

**Dispatcher integration**
- In `slack_dispatch.py`, locate the agent-reply post sites (lines 268, 389, 404, 417, 438, 523, 605, 620, 633, 654 per grep output). The agent's *final* reply post is the one at ~268/523 — confirm via tracing.
- After `result = await agent.run(...)`, read `deps.citations`. Call `blocks = build_reply_blocks(mrkdwn_reply, deps.citations)`.
- Post:
  - `blocks is None` → existing `chat_postMessage(text=mrkdwn_reply, thread_ts=...)`
  - `blocks is not None` → `chat_postMessage(text=mrkdwn_reply, blocks=blocks, thread_ts=...)`
- The other post sites (error messages, "no key configured" nudges) do NOT get citation footers — only the successful agent reply.

**Dedupe + cap**
- Dedup on `(kind, source_id)`. Preserve first-occurrence order (agent mentioned it first = more relevant).
- After dedupe, slice to 5. If the pre-slice length was > 5, append a synthetic "+N more" chip (no link, no icon) with `title=f"+{N} more", url=None`.

**System prompt**
- Append one line to the preamble in `_build_system_prompt` (agent.py:361): `"Citations: sources are attached automatically from the tools you call. Do NOT add a manual 'Sources:' section in your reply text."`
- No other prompt changes.

**Icon assets**
- Host three small icons (doc, wiki, web) on the SPA's static path (`frontend/public/icons/...`) and reference them via `{frontend_url}/icons/doc.png` etc. When `frontend_url` is empty, omit the `image` element entirely — text-only chips are valid Block Kit.

### 3.4 API Contract
No REST API changes. The external contract is the Slack `chat.postMessage` payload shape, which is a Slack Web API concern (documented — no code-side contract test needed beyond the block-builder unit tests).

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|---|---|---|
| Unit tests | 8 | Citation dedupe, cap overflow, missing-url fallback, icon element toggle on `frontend_url=""`, category-missing rendering, append-on-success vs skip-on-failure, record-shape validation, `+N more` chip rendering |
| Component tests | 0 — N/A (backend-only story) | |
| E2E / acceptance tests | 8 | One per Gherkin scenario in §2.1 |
| Integration tests | 2 | `slack_dispatch` end-to-end: (a) with citations produces blocks, (b) without citations produces text-only |

### 4.2 Definition of Done
- [ ] TDD Red → Green enforced. All 8 Gherkin scenarios from §2.1 have corresponding tests written failing first.
- [ ] Minimum test expectations (§4.1) met.
- [ ] FLASHCARDS.md consulted for prior Block Kit usage; a new flashcard for the `blocks=` pattern added after merge (First-Use Pattern gate).
- [ ] ADR-032 added to Roadmap §3 before merge.
- [ ] System prompt change verified via a local `build_agent` smoke test: the "Citations:" sentence is present in the rendered prompt.
- [ ] `chat_postMessage` callers that are NOT the final agent reply (error nudges, onboarding messages) confirmed unchanged via grep diff.
- [ ] No violations of Roadmap ADRs.
- [ ] Framework Integrity: no edits to `.claude/agents/`, `.vbounce/skills/`, `.vbounce/templates/`, `.vbounce/scripts/` — if any slipped in, log to `.vbounce/CHANGELOG.md`.

---

## Token Usage

| Agent | Input | Output | Total |
|---|---|---|---|

---

## Open Questions (to resolve during sprint planning / Probing/Spiking)

| Question | Options | Impact | Suggested Default |
|---|---|---|---|
| Where do web-tool citations pull their `title` from? | (a) `<title>` scraped by `crawl_page`, (b) hostname only, (c) LLM-generated summary | Chip readability | **(a) with (b) fallback** |
| Which Slack-safe icon host? | (a) SPA static (`frontend/public/icons/`), (b) external CDN, (c) no icons — text chips | Reliability vs visual fidelity | **(a)** — same-origin with the wiki viewer |
| Category string source for wiki chips? | (a) `page_type` ("source-summary"), (b) source document title, (c) omit | Chip density | **(b) source document title** — matches screenshot reference |
| Should citations survive across multi-step tool calls in a single run? | Yes / No (reset per tool call) | Matches scenario #4 | **Yes — per run, not per tool call** |
