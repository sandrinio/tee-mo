---
story_id: "STORY-007-02-agent-factory"
parent_epic_ref: "EPIC-007"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §4.5 / Charter §3.3, §3.4, §5.1 / new_app orchestrator.py"
actor: "Agent (internal consumer)"
complexity_label: "L3"
---

# STORY-007-02: Agent Factory + Model Helpers + Skill Tools

**Complexity: L3** — Cross-cutting: copy+strip orchestrator, 3 provider model helpers, system prompt assembly, 4 skill tools. Core of the agent system.

---

## 1. The Spec (The Contract)

### 1.1 User Story
This story creates the Pydantic AI agent factory — the `build_agent()` function that takes a workspace config and returns a fully configured Agent with skill tools registered. This is the engine that STORY-007-05 (Slack dispatch) will call on every event.

### 1.2 Detailed Requirements
- **R1**: `AgentDeps` dataclass with `workspace_id: str`, `supabase: Any`, `user_id: str`.
- **R2**: `_ensure_model_imports(provider)` — lazy import of Pydantic AI model classes per provider (google, anthropic, openai). Same pattern as new_app.
- **R3**: `_build_pydantic_ai_model(model_id, provider, api_key)` — instantiate the correct Model+Provider combo. Raises `ValueError` for unsupported providers.
- **R4**: `build_agent(workspace_id, user_id, supabase) -> tuple[Agent, AgentDeps]` — async factory that:
    1. Queries `teemo_workspaces` for `ai_provider`, `ai_model`, `encrypted_api_key`.
    2. Raises `ValueError("no_workspace")` if workspace not found.
    3. Raises `ValueError("no_key_configured")` if `encrypted_api_key` is null.
    4. Decrypts the API key via `core.encryption.decrypt()`.
    5. Calls `_ensure_model_imports` + `_build_pydantic_ai_model`.
    6. Assembles the system prompt with skill catalog (R5).
    7. Constructs `Agent(model, system_prompt=..., deps_type=AgentDeps, tools=[...])` with 4 skill tools.
    8. Returns `(agent, deps)`.
- **R5**: System prompt assembly:
    - Static preamble: identity ("You are Tee-Mo..."), response style, thread context instruction.
    - Dynamic `## Available Skills` section: bulleted list of `- name: summary` for all active workspace skills. Omitted entirely if no skills exist.
    - Instruction: "Use `load_skill(name)` to read full instructions before applying a skill."
    - NO `## Available Files` section (deferred to EPIC-006).
- **R6**: 4 skill tools registered on the agent (all take `ctx: RunContext[AgentDeps]`):
    - `load_skill(ctx, skill_name: str) -> str` — calls `skill_service.get_skill()`, returns instructions or "Skill not found."
    - `create_skill(ctx, name: str, summary: str, instructions: str) -> str` — calls `skill_service.create_skill()`, returns confirmation or validation error.
    - `update_skill(ctx, skill_name: str, summary: str | None, instructions: str | None) -> str` — partial update.
    - `delete_skill(ctx, skill_name: str) -> str` — deletes, returns confirmation.
- **R7**: The `backend/app/agents/` package has NO FastAPI imports. It depends on: `app.core.encryption`, `app.services.skill_service`, `pydantic_ai`. Nothing else.
- **R8**: Provider is determined from `ai_provider` column on the workspace row. Model ID from `ai_model`. Both are already stored by EPIC-004 (BYOK key management).

### 1.3 Out of Scope
- `read_drive_file` tool — EPIC-006
- `## Available Files` in system prompt — EPIC-006
- Scan-tier model resolution — EPIC-006
- Persona injection, team roster, response formatting — stripped from new_app
- REST endpoints for the agent — the agent is only invoked from Slack dispatch
- Token counting / context pruning — EPIC-009

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
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
    # Same pattern for anthropic -> AnthropicModel, openai -> OpenAIChatModel

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

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | Standard `.env` + `TEEMO_ENCRYPTION_KEY` | [ ] |
| **Dependencies** | `pydantic-ai[openai,anthropic,google]==1.79.0` — verify in requirements.txt | [ ] |
| **Prior Story** | STORY-007-01 (skill_service.py) must be merged | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_agent_factory.py`
- 7+ tests matching Gherkin scenarios
- Mock: Supabase client (workspace queries), `app.core.encryption.decrypt`, Pydantic AI model classes
- Use `monkeypatch` to replace module-level model class globals (same pattern as new_app tests)
- Do NOT make live LLM calls in tests

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/agents/agent.py` (new) |
| **Related Files** | `backend/app/agents/__init__.py` (new), `backend/app/services/skill_service.py` (from 007-01), `backend/app/core/encryption.py` (read) |
| **New Files Needed** | Yes — `agents/__init__.py`, `agents/agent.py`, `tests/test_agent_factory.py` |
| **ADR References** | ADR-003 (Pydantic AI), ADR-004 (Two-Tier — conversation tier only), ADR-023 (Skills) |
| **First-Use Pattern** | **Yes** — first use of `pydantic_ai.Agent` in Tee-Mo. Search FLASHCARDS.md for Pydantic AI gotchas. |
| **Copy Source** | `Documents/Dev/new_app/backend/app/agents/orchestrator.py` |

### 3.3 Technical Logic

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
5. `build_orchestrator()` → rename to `build_agent()`, strip:
   - `chy_agent_definitions` DB lookup (no agent definitions table in Tee-Mo)
   - `chy_workspace_agent_config` DB lookup (model comes from workspace row)
   - `internet_search` param
   - `full_prompt` param
   - Persona injection, team roster, response formatting, blueprint catalog
   - All tool registration except skill tools
6. Add: direct workspace query `supabase.table("teemo_workspaces").select("ai_provider, ai_model, encrypted_api_key").eq("id", workspace_id).maybe_single()`.
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

Where `{skills_section}` is either empty or:
```
## Available Skills
- skill-name: summary text
- another-skill: summary text

Use `load_skill("name")` to read full instructions before applying a skill.
```

**Skill tools pattern (from new_app, simplified):**
```python
@agent.tool
async def load_skill(ctx: RunContext[AgentDeps], skill_name: str) -> str:
    skill = get_skill(ctx.deps.workspace_id, skill_name, supabase=ctx.deps.supabase)
    if not skill:
        return f"Skill '{skill_name}' not found."
    return f"## {skill['name']}\n{skill['instructions']}"
```

**Module isolation rule (R7):** `agents/agent.py` imports:
- `from dataclasses import dataclass`
- `from app.core.encryption import decrypt`
- `from app.services.skill_service import list_skills, get_skill, create_skill, update_skill, delete_skill`
- `pydantic_ai` (lazy via `_ensure_model_imports`)
- NO `fastapi`, NO `Request`, NO `Depends`

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 7 | Factory, 3 providers, no-workspace, no-key, system prompt with/without skills |
| Integration tests | 0 | N/A — all mocked |

### 4.2 Definition of Done (The Gate)
- [ ] TDD enforced: Red phase tests written and verified failing before Green phase.
- [ ] 7+ tests passing.
- [ ] FLASHCARDS.md consulted (especially first-use Pydantic AI pattern).
- [ ] No FastAPI imports in `backend/app/agents/`.
- [ ] No ADR violations.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
