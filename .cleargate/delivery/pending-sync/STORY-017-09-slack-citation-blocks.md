---
story_id: "STORY-017-09-slack-citation-blocks"
parent_epic_ref: "EPIC-017"
status: "Draft"
ambiguity: "🟡"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "TBD"
target_date: "TBD"
complexity_label: "L3"
parallel_eligible: false
expected_bounce_exposure: "low"
created_at: "2026-04-21T00:00:00Z"
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

> **Ported from V-Bounce.** Original: `product_plans.vbounce-archive/backlog/EPIC-017_wiki_karpathy_parity/STORY-017-09-slack-citation-blocks.md`. Carried forward during ClearGate migration 2026-04-24.

# STORY-017-09: Slack Citation Blocks — Sources Footer on Grounded Replies

**Complexity: L3** — Cross-cutting. Touches source-producing tool return shapes (wiki + document + web), adds a citation collector on `AgentDeps`, and upgrades `slack_dispatch` from `text=` posts to Block Kit payloads with a sources footer. No new infra, but the contract change between agent tools and the dispatcher is the risky part.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Slack user asking Tee-Mo a question**,
> I want to **see which workspace documents, wiki pages, or URLs the answer came from as clickable chips under the reply**,
> So that **I can verify the answer against the source without pestering the agent for "where did you get that?" follow-ups**.

Reference UX (provided by user in 2026-04-21 conversation): a Block Kit context footer titled **SOURCES** followed by one row per cited source — document icon + filename as a clickable mrkdwn link + a muted category tag.

### 1.2 Detailed Requirements

**R1 — Source-producing tools attach citation metadata to a per-run collector**
- `search_wiki`, `read_wiki_page`, `read_document` and `web_search`, `crawl_page`, `http_request` MUST append structured citation records to a list living on `ctx.deps.citations` during tool execution.
- Record shape:
  ```python
  class Citation:
      kind: Literal["wiki", "document", "web"]
      title: str
      url: str | None
      category: str | None
      source_id: str
  ```
- Tools append — they do NOT overwrite.
- Tools that return nothing useful MUST NOT append.

**R2 — Wiki pages cite via deep-link to the dashboard wiki viewer**
- `read_wiki_page` cites with `url=f"{settings.frontend_url}/app/teams/{team}/{workspace}/wiki/{slug}"` when `frontend_url` is set; otherwise `url=None`.

**R3 — Documents cite via Google Drive `webViewLink`**

**R4 — Dispatcher builds a Block Kit payload when citations are present**
- If the citations list is empty: post as today (`chat_postMessage(text=reply)`).
- If non-empty: post a `blocks=[...]` payload AND keep `text=` populated with the reply.

**R5 — Deduplication and cap**
- Collapse citations by `source_id` (keep first occurrence).
- Cap to **5 displayed sources** after dedupe. If more, render the first 5 and a 6th chip reading `+N more` with no link.

**R6 — No citations leak when the agent didn't use a source tool**

**R7 — System prompt instruction**
- Add one sentence to the preamble in `_build_system_prompt`: *"Citations are attached automatically from the tools you call — do not fabricate a 'Sources:' section in your reply text."*

### 1.3 Out of Scope
- Inline per-sentence superscript citations.
- Dashboard / web surface — only Slack posting is in scope.
- Thread-level citation aggregation across multi-turn threads.
- Editing / dismissing sources from chips.
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

---

## 3. The Implementation Guide (AI-to-AI)

### 3.2 Context & Files

| Item | Value |
|---|---|
| **Primary Files** | `backend/app/agents/agent.py`, `backend/app/services/slack_dispatch.py`, `backend/app/services/slack_formatter.py` |
| **New Files Needed** | `backend/app/services/citation_collector.py`, `backend/app/services/slack_blocks.py` |
| **ADR References** | New ADR-032 (proposed): "Citations are attached to Slack replies via Block Kit, collected from tool execution rather than parsed from LLM output." |
| **First-Use Pattern** | Yes — first use of Block Kit `blocks=` payloads in `slack_dispatch`. |

### 3.3 Technical Logic

**Citation collector** — `AgentDeps` gains `citations: list[Citation] = field(default_factory=list)`. Every source-producing tool appends before returning.

**Block builder** — Entry point: `build_reply_blocks(reply_mrkdwn: str, citations: list[Citation]) -> list[dict] | None`. Returns `None` when `citations` is empty.

**Dedupe + cap** — Dedup on `(kind, source_id)`. Preserve first-occurrence order. Slice to 5. If pre-slice length > 5, append synthetic "+N more" chip.

**System prompt** — Append one line to `_build_system_prompt` preamble: `"Citations: sources are attached automatically from the tools you call. Do NOT add a manual 'Sources:' section in your reply text."`

---

## Token Usage

| Agent | Input | Output | Total |
|---|---|---|---|
