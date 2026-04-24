---
epic_id: "EPIC-008"
status: "Shipped"
children:
  - "STORY-008-01-guided-setup-mode"
  - "STORY-008-02-channel-binding-ui"
  - "STORY-008-03-card-dashboard-polish"
  - "STORY-008-04-top-nav-chrome"
  - "STORY-008-05-e2e-verification"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
owner: "sandrinio"
target_date: "2026-04-18"
approved: true
created_at: "2026-04-13T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-008_workspace_setup_wizard/EPIC-008_workspace_setup_wizard.md`. Shipped in sprint S-09, carried forward during ClearGate migration 2026-04-24.

# EPIC-008: Workspace Setup Wizard Polish

## 1. Problem & Value

### 1.1 The Problem
All setup building blocks (Slack OAuth, workspace creation, Drive OAuth, BYOK keys, file indexing) exist as standalone UI fragments scattered across different pages. A first-time user has no guided path from "I just registered" to "my Slack bot answers questions from my Drive files." The channel binding backend is fully implemented but has zero frontend UI — users cannot bind channels to workspaces from the dashboard. The existing dashboard also deviates from the design guide (hardcoded hex colors, no top nav, no Lucide icons, ad-hoc buttons bypassing the Button component).

### 1.2 The Solution
Enhance the workspace detail page with a **guided setup mode** that activates when setup is incomplete. The stepper walks users through: Connect Drive → Configure AI Key → Add Files → Bind Channels. Build the missing channel binding UI. Polish the workspace card and dashboard layout. Add persistent top nav chrome. Fix design system drift (hardcoded hex → brand tokens, ad-hoc buttons → Button component).

**Strategy decision:** A separate wizard route was considered but rejected. OAuth flows (Drive, Slack) are full-page redirects that return to fixed URLs. Routing back into a mid-wizard step requires state persistence + redirect plumbing. Enhancing the workspace detail page with guided mode reuses existing components, handles OAuth re-entry naturally, and avoids a parallel code path.

### 1.3 Success Metrics (North Star)
- A hackathon judge can go from registration to a working bot answering Drive questions in under 5 minutes with no confusion about what to do next
- Channel binding is fully operable from the dashboard (bind, unbind, see status)
- Dashboard looks polished and consistent with the Asana-inspired design guide

---

## 2. Scope Boundaries

### IN-SCOPE (Build This)
- [x] Guided setup mode on workspace detail page (step indicator, progressive reveal, gated steps)
- [x] Extract `KeySection` from `WorkspaceCard.tsx` into reusable standalone component
- [x] Channel binding frontend: API client, hooks, channel picker, status chips (Active/Pending), unbind
- [x] `is_member` enrichment on backend channel list endpoint
- [x] Workspace card polish: channel chips, default/DM badges, setup completeness
- [x] Dashboard workspace list: grid layout per design guide, new-workspace → guided setup
- [x] Persistent top nav with logo and user controls
- [x] Install `sonner` for toast notifications
- [x] Fix hardcoded `#E94560` → `brand-500` tokens across all dashboard files
- [x] Replace ad-hoc button styles with `Button` component in dashboard pages

### OUT-OF-SCOPE (Do NOT Build This)
- Lucide icon migration (emoji works for hackathon — low ROI)
- Radix UI migration (div modals are functional, not blocking)
- Separate wizard route (rejected — see §1.2)
- Dark mode (Charter and design guide explicitly defer this)
- Skills UI on dashboard (ADR-023: chat-only CRUD)
- Error handling improvements (EPIC-009 scope)
- Seed data / demo script (EPIC-010 scope)

---

## 3. Context

### 3.1 User Personas
- **New User (Judge)**: Evaluating Tee-Mo for the first time during hackathon demo. Needs clear, guided onboarding with zero ambiguity about next steps.
- **Returning User**: Has one workspace set up, wants to add a second knowledge silo under the same Slack team.

### 3.2 User Journey (Happy Path)
```
Register → Login → /app (empty teams list)
  → Install Slack (existing Phase A flow)
  → Team appears → Click team → /app/teams/$teamId (empty workspace list)
  → New Workspace → Name it → Navigate to /app/teams/$teamId/$workspaceId
  → Guided setup mode activates (4 steps):
      Step 1: Connect Drive (OAuth round-trip)
      Step 2: Configure AI Key (provider + key + validate + save)
      Step 3: Add Files (Google Picker, AI scan)
      Step 4: Bind Channels (pick channels, copy /invite snippet)
  → Setup complete → Detail view replaces wizard
  → Go to Slack → @mention bot → Answer in thread
```

### 3.3 Constraints
| Type | Constraint |
|------|------------|
| **Design** | Must follow `tee_mo_design_guide.md` — Asana-inspired warm minimalism, ADR-022 |
| **Channels** | Explicit binding only per ADR-025. No silent fallback. Unbound channels get setup-nudge reply. |
| **Workspace Model** | 1 User : N SlackTeams : N Workspaces : N channel bindings per ADR-024 |
| **Tech Stack** | React 19 + Tailwind 4 + TanStack Router/Query + Zustand per ADR-014. No shadcn, no MUI. |
| **File Cap** | 15 files per workspace (ADR-007) — enforced server-side + disabled button client-side |
| **Hackathon Deadline** | 2026-04-18 — polish over completeness |

---

## 4. Technical Context

### 4.1 Affected Areas
| Area | Files/Modules | Change Type |
|------|---------------|-------------|
| Workspace Detail | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (590 lines) | Major modify — add guided setup mode, step indicator, channel section |
| WorkspaceCard | `frontend/src/components/dashboard/WorkspaceCard.tsx` (477 lines) | Modify — extract KeySection, add channel chips, badges |
| KeySection | `frontend/src/components/workspace/KeySection.tsx` (new) | New — extracted from WorkspaceCard |
| Channel UI | `frontend/src/components/workspace/ChannelSection.tsx` (new) | New — picker, chips, status |
| App Layout | `frontend/src/routes/app.tsx` | Modify — add top nav |
| Teams Page | `frontend/src/routes/app.index.tsx` (326 lines) | Modify — fix tokens, empty state |
| Workspace List | `frontend/src/routes/app.teams.$teamId.index.tsx` (170 lines) | Modify — grid layout, fix tokens |
| Create Modal | `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` (152 lines) | Modify — fix tokens, use Button |
| Rename Modal | `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` (160 lines) | Modify — fix tokens, use Button |
| API Client | `frontend/src/lib/api.ts` (539 lines) | Modify — add channel API functions |
| Channel Hooks | `frontend/src/hooks/useChannels.ts` (new) | New — TanStack Query hooks |
| Backend Channels | `backend/app/api/routes/channels.py` | Modify — add `is_member` enrichment |
| Sonner | `package.json`, root layout | New dependency + Toaster mount |

### 4.2 Dependencies
| Type | Dependency | Status |
|------|------------|--------|
| **Requires** | EPIC-004: BYOK Key Management | Done (S-06, v0.6.0) |
| **Requires** | EPIC-005 Phase A: Slack OAuth Install | Done (S-04) |
| **Requires** | EPIC-006: Google Drive Integration | Done (S-08) |
| **Requires** | EPIC-007: AI Agent + Slack Event Loop | Done (S-07, v0.7.0) |
| **Unlocks** | EPIC-009: Error Handling & UX Polish | Waiting |
| **Unlocks** | EPIC-010: Demo Hardening & Deploy | Waiting |

### 4.3 Integration Points
| System | Purpose | Notes |
|--------|---------|-------|
| Slack API `conversations.list` | Fetch available channels for binding picker | Already called by backend `list_slack_team_channels` |
| Slack API `conversations.info` | Check `is_member` per binding | New — needed for Active/Pending status |

### 4.4 Data Changes
No schema changes. All tables exist (`teemo_workspace_channels`, `teemo_slack_teams`, `teemo_workspaces`). The only backend change is enriching the channel list response with `is_member` status.

---

## 5. Decomposition Guidance

### Affected Areas (for codebase research)
- [x] Workspace detail page: `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx`
- [x] WorkspaceCard + embedded KeySection: `frontend/src/components/dashboard/WorkspaceCard.tsx`
- [x] API client: `frontend/src/lib/api.ts` — no channel functions exist
- [x] Backend channels: `backend/app/api/routes/channels.py` — 4 endpoints, no `is_member`
- [x] App layout: `frontend/src/routes/app.tsx` — bare ProtectedRoute wrapper, no nav
- [x] Design tokens: `frontend/src/app.css` — @theme correct, 11 hardcoded hex in components

### Key Constraints for Story Sizing
- Each story should touch 1-3 files and have one clear goal
- Prefer vertical slices over horizontal layers
- Stories must be independently verifiable
- OAuth re-entry must be tested in e2e story

### Suggested Sequencing Hints
1. STORY-008-01 (guided setup), STORY-008-02 (channel binding), STORY-008-04 (top nav + chrome) — **parallel, no dependencies**
2. STORY-008-03 (card + dashboard polish) — depends on 008-02 (channel chips) and 008-04 (design tokens)
3. STORY-008-05 (e2e verification) — depends on all above

---

## 6. Risks & Edge Cases
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| OAuth re-entry lands outside setup context | Medium | Guided mode detects incomplete setup on page load — re-entering the workspace URL after OAuth redirect naturally re-activates the correct step |
| `conversations.info` rate-limited for many channel bindings | Low | Typical workspace has 1-5 bindings. If >10, batch or debounce. Not a hackathon concern. |
| Extracting KeySection introduces regression | Medium | KeySection is self-contained (hooks + state). Extract with zero logic changes, verify with existing WorkspaceCard behavior. |
| Design token cleanup accidentally changes auth pages | Low | Auth pages already use `brand-500` correctly. Only dashboard pages have hardcoded hex. |
| `is_member` enrichment slows channel list | Low | One `conversations.info` call per binding (typically 1-5). Async parallel calls keep it fast. |

---

## 7. Acceptance Criteria (Epic-Level)

```gherkin
Feature: Workspace Setup Wizard

  Scenario: First-time guided setup
    Given a user with a Slack team installed and zero workspaces
    When they create a new workspace
    Then they land on the workspace detail page in guided setup mode
    And they see a 4-step indicator (Drive, Key, Files, Channels)
    And later steps are gated until prerequisites are met

  Scenario: Channel binding from dashboard
    Given a workspace with Drive and BYOK configured
    When the user opens the channel binding step
    Then they see a list of available Slack channels
    And they can bind a channel and see "Pending /invite" status
    And after /invite in Slack, status updates to "Active"

  Scenario: Workspace card shows completeness
    Given a workspace with Drive connected but no BYOK key
    When the user views the workspace list
    Then the card shows setup status indicators
    And the default workspace shows "DMs route here" badge

  Scenario: Design consistency
    Given any dashboard page
    When the page renders
    Then all buttons use the Button component (no hardcoded #E94560)
    And a persistent top nav with logo is visible
    And typography follows the design guide
```

---

## 8. Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| None — all decisions made | — | — | — | — |

All architectural decisions resolved: guided setup mode over separate wizard route (§1.2), ADR-022/024/025 cover all design + model + channel decisions.

---

## 9. Artifact Links

**Stories (Status Tracking):**
- [ ] STORY-008-01-guided-setup-mode -> Sprint S-09
- [ ] STORY-008-02-channel-binding-ui -> Sprint S-09
- [ ] STORY-008-03-card-dashboard-polish -> Sprint S-09
- [ ] STORY-008-04-top-nav-chrome -> Sprint S-09
- [ ] STORY-008-05-e2e-verification -> Sprint S-09

**References:**
- Charter: `product_plans/strategy/tee_mo_charter.md` §4, §5.3, §5.5
- Design Guide: `product_plans/strategy/tee_mo_design_guide.md`
- Roadmap: `product_plans/strategy/tee_mo_roadmap.md` §2 Release 3

---

## Change Log
| Date | Change | By |
|------|--------|-----|
| 2026-04-13 | Epic created. 5 stories decomposed. Guided setup mode chosen over separate wizard route. All open questions resolved. | Claude (doc-manager) |
