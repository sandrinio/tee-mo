---
story_id: "STORY-023-01-skills-list-ui"
parent_epic_ref: "EPIC-023"
status: "Ready to Bounce"
ambiguity: "🟢 Low"
context_source: "Epic §4 / Codebase / User Input"
actor: "Dashboard User"
complexity_label: "L2"
---

# STORY-023-01: Visualize Skill Cards in UI

**Complexity: L2** — Adds new API wrappers and UI components to display a list of data, leveraging existing Workspace layouts.

---

## 1. The Spec (The Contract)
> Human-Readable Requirements. The "What".
> Target Audience: PM, BA, Stakeholders, Developer Agent.

### 1.1 User Story
> As a **Dashboard User**,
> I want to **see a list of active skills mapped to my workspace**,
> So that **I know what tasks and behaviors the bot has been trained to perform in Slack.**

### 1.2 Detailed Requirements
- **Requirement 1**: Create a new API wrapper `listWorkspaceSkills(workspaceId)` in `frontend/src/lib/api.ts` that fetches `GET /api/workspaces/{id}/skills`.
- **Requirement 2**: Create a TanStack query hook `useSkillsQuery` to consume this endpoint.
- **Requirement 3**: Render an 'Active Skills' section on the `/app/teams/$teamId/$workspaceId` page.
- **Requirement 4**: The UI must display the skill's name and description. Include a small helper text explaining that "Skills are created by whispering to Tee-Mo in Slack" to prevent users from looking for a missing UI Add button.

### 1.3 Out of Scope
- Forms or buttons to Create, Edit, or Delete skills via the dashboard.

### TDD Red Phase: No
> Component addition without heavy unit-test isolation required.

---

## 2. The Truth (Executable Tests)
> The QA Agent uses this to verify the work. If these don't pass, the Bounce failed.
> Target Audience: QA Agent (with vibe-code-review skill).

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Visuzalize Skills

  Scenario: Workspace Skills Visible
    Given a Workspace has 2 skills stored in the database
    When the user navigates to the detailed Workspace page
    Then an 'Active Skills' section is visible
    And the names and descriptions of those 2 skills are rendered in UI cards
    And text indicates how to create skills via Slack.
```

### 2.2 Verification Steps (Manual)
- [ ] Ensure the component gracefully handles the empty state (0 skills) with an empty-state message.

---

## 3. The Implementation Guide (AI-to-AI)
> Instructions for the Developer Agent. The "How".
> Target Audience: Developer Agent (with react-best-practices + lesson skills).

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Env Vars** | `.env` loaded via backend/frontend | [ ] |

### 3.1 Test Implementation
- Manually check UI rendering.

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` |
| **Related Files** | `frontend/src/lib/api.ts`, `frontend/src/hooks/useKnowledge.ts` (create a new `useSkills.ts` alongside it) |
| **New Files Needed** | Yes — `frontend/src/hooks/useSkills.ts` |
| **First-Use Pattern** | No |

### 3.3 Technical Logic
- Add the `Skill` interface in `api.ts` (matching backend response: `id`, `name`, `description`, `created_at`).
- Add the `listWorkspaceSkills(workspaceId: string): Promise<Skill[]>` function.
- Create `useSkillsQuery(workspaceId)` exporting the TanStack React Query.
- In `app.teams.$teamId.$workspaceId.tsx`, compose a new `SkillsSection` below or above the `PickerSection`/`KnowledgeList`. 
- **Design Rules:** Follow ADR-022 (Coral brand, Slate neutrals, Inter font, no heavy bold weights). Use `Card` and standard utility classes.

### 3.4 API Contract (If applicable)
| Endpoint | Method | Auth | Request Shape | Response Shape |
|----------|--------|------|---------------|----------------|
| `/api/workspaces/{id}/skills` | GET | Bearer | None | `[{ id, workspace_id, name, description, ... }]` |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 1 | Verify rendering of the section. |

### 4.2 Definition of Done (The Gate)
- [ ] Empty state explicitly handles zero skills.
- [ ] No violations of Roadmap ADRs.

---

## Token Usage
> Auto-populated by agents. Each agent runs `node .vbounce/scripts/count_tokens.mjs --self --append <this-file> --name <Agent>` before writing their report.

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
