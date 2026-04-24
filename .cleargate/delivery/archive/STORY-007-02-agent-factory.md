---
story_id: "STORY-007-02-agent-factory"
parent_epic_ref: "EPIC-007"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L3"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-12T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
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

> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-07/STORY-007-02-agent-factory.md`. Shipped in sprint S-07, carried forward during ClearGate migration 2026-04-24.

# STORY-007-02: Agent Factory + Model Helpers + Skill Tools

**Complexity: L3** — Cross-cutting: copy+strip orchestrator, 3 provider model helpers, system prompt assembly, 4 skill tools. Core of the agent system.

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story creates the Pydantic AI agent factory — the `build_agent()` function that takes a workspace config and returns a fully configured Agent with skill tools registered. This is the engine that STORY-007-05 (Slack dispatch) will call on every event.

### 1.2 Detailed Requirements
- **R1**: `AgentDeps` dataclass with `workspace_id: str`, `supabase: Any`, `user_id: str`.
- **R2**: `_ensure_model_imports(provider)` — lazy import of Pydantic AI model classes per provider.
- **R3**: `_build_pydantic_ai_model(model_id, provider, api_key)` — instantiate the correct Model+Provider combo. Raises `ValueError` for unsupported providers.
- **R4**: `build_agent(workspace_id, user_id, supabase) -> tuple[Agent, AgentDeps]` — async factory that queries workspace, decrypts key, builds model, assembles system prompt, constructs agent with 4 skill tools.
- **R5**: System prompt includes dynamic `## Available Skills` section (omitted entirely if no skills exist). NO `## Available Files` section (deferred to EPIC-006).
- **R6**: 4 skill tools: `load_skill`, `create_skill`, `update_skill`, `delete_skill`.
- **R7**: The `backend/app/agents/` package has NO FastAPI imports.
- **R8**: Provider and model ID come from `ai_provider` and `ai_model` columns on workspace row.

### 1.3 Out of Scope
- `read_drive_file` tool — EPIC-006
- `## Available Files` in system prompt — EPIC-006
- Scan-tier model resolution — EPIC-006
- Persona injection, team roster, response formatting — stripped from new_app
- Token counting / context pruning — EPIC-009

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: Agent Factory

  Scenario: Build agent with valid workspace
    Given workspace W1 has ai_provider="openai", ai_model="gpt-4o", encrypted_api_key set
    When build_agent(W1, user_id, supabase) is called
    Then a (Agent, AgentDeps) tuple is returned
    And agent has 4 tools registered (load_skill, create_skill, update_skill, delete_skill)
    And AgentDeps.workspace_id == W1

  Scenario: Build agent with no workspace
    Given workspace W999 does not exist
    When build_agent(W999, ...) is called
    Then ValueError("no_workspace") is raised

  Scenario: Build agent with no key
    Given workspace W1 exists but encrypted_api_key is null
    When build_agent(W1, ...) is called
    Then ValueError("no_key_configured") is raised

  Scenario: System prompt includes skill catalog
    Given workspace W1 has 2 active skills
    When build_agent(W1, ...) is called
    Then the agent's system_prompt contains "## Available Skills"
    And lists both skill names and summaries

  Scenario: System prompt omits skills section when none exist
    Given workspace W1 has 0 skills
    When build_agent(W1, ...) is called
    Then the agent's system_prompt does NOT contain "## Available Skills"

  Scenario: Model instantiation for each provider
    Given provider="google" and model_id="gemini-2.5-flash" and a valid api_key
    When _build_pydantic_ai_model() is called
    Then a GoogleModel instance is returned

  Scenario: Unsupported provider
    Given provider="azure"
    When _build_pydantic_ai_model() is called
    Then ValueError is raised
```

### 2.2 Verification Steps (Manual)
- [ ] All tests pass with `pytest backend/tests/test_agent_factory.py -v`
- [ ] Full backend suite passes
- [ ] `from app.agents.agent import build_agent` works from any backend module

---

## 3. The Implementation Guide

### 3.1 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/agents/agent.py` (new) |
| **Related Files** | `backend/app/agents/__init__.py` (new), `backend/app/services/skill_service.py` (from 007-01), `backend/app/core/encryption.py` (read) |
| **New Files Needed** | Yes — `agents/__init__.py`, `agents/agent.py`, `tests/test_agent_factory.py` |
| **ADR References** | ADR-003 (Pydantic AI), ADR-004 (Two-Tier — conversation tier only), ADR-023 (Skills) |
| **Copy Source** | `Documents/Dev/new_app/backend/app/agents/orchestrator.py` |

### 3.2 Technical Logic

**File structure:**
```
backend/app/agents/
├── __init__.py          # exports build_agent, AgentDeps
└── agent.py             # factory + helpers + tools
```

**Copy from new_app `orchestrator.py`:**
1. `OrchestratorDeps` → rename to `AgentDeps`, strip `inference_scope`, `inference_key_id`, `last_search_citations`.
2. Module-level globals: `Agent = None`, `GoogleModel = None`, etc.
3. `_ensure_model_imports(provider)` — copy as-is.
4. `_build_pydantic_ai_model(model_id, provider, api_key)` — copy as-is.
5. `build_orchestrator()` → rename to `build_agent()`, strip: persona injection, team roster, response formatting, blueprint catalog, agent definitions lookup, workspace agent config lookup.
6. Add: direct workspace query on `teemo_workspaces`.
7. Add: `_build_system_prompt(skills: list[dict]) -> str` helper.

**System prompt template:**
```
You are Tee-Mo, an AI assistant embedded in Slack. You help team members by answering questions using the conversation thread as context.

Rules:
- Answer based on the thread context. Be concise and helpful.
- When a user asks you to create, update, or delete a skill, use the appropriate tool.
- When a skill might be relevant to a question, use load_skill to read its full instructions before applying it.
- Always identify who you're responding to by name when the thread has multiple participants.

{skills_section}
```

**Module isolation rule (R7):** `agents/agent.py` imports only: `dataclasses`, `app.core.encryption`, `app.services.skill_service`, `pydantic_ai` (lazy). NO `fastapi`, NO `Request`, NO `Depends`.

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 7 | Factory, 3 providers, no-workspace, no-key, system prompt with/without skills |

### 4.2 Definition of Done (The Gate)
- [ ] 7+ tests passing.
- [ ] FLASHCARDS.md consulted (especially first-use Pydantic AI pattern).
- [ ] No FastAPI imports in `backend/app/agents/`.
- [ ] No ADR violations.
