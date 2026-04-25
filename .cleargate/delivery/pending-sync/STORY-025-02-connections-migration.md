---
story_id: "STORY-025-02"
parent_epic_ref: "EPIC-025"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "EPIC-025-workspace-v2-redesign.md"
actor: "Workspace admin"
complexity_label: "L2"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-s16-kickoff"
updated_at_version: "cleargate-s16-kickoff"
server_pushed_at_version: null
draft_tokens: { input: null, output: null, cache_read: null, cache_creation: null, model: null, sessions: [] }
cached_gate_result: { pass: null, failing_criteria: [], last_gate_check: null }
---

# STORY-025-02: Connections Group Migration
**Complexity:** L2 — 4 module re-skins, no behavior changes, ~3hr

## 1. The Spec

### 1.1 User Story
As a workspace admin, I want the Connections group (Slack / Drive / Provider / Channels) rendered inside the new shell with the redesigned content treatments, so that connection state is glanceable and consistent.

### 1.2 Detailed Requirements
- **SlackSection** — info-only card. 40×40 slate-100 avatar tile + workspace name (16px/600) + mono caption + `Installed` badge (success variant). NO Reinstall button. **Caption source (resolved OQ-3 = C):** `slack_team_id` and `slack_domain` are read from `useWorkspaceQuery` (workspace GET response, fields added by STORY-025-05). Render as ``${workspace.slack_team_id}${workspace.slack_domain ? ` · ${workspace.slack_domain}` : ''}``. If 025-05 has not yet merged when this story executes, `slack_domain` will be undefined and the caption shows `team_id` only — defensive and forward-compatible.
- **DriveSection** — extract from inline route. 40×40 avatar tile + connected email + caption "Read-only access · scoped to selected files" + Disconnect button (rose-500 text). Existing connect/disconnect mutations unchanged.
- **KeySection** — re-skin existing component. 3-button segmented control (Google / OpenAI / Anthropic) above a slate-50 box showing `sk-proj-•••• G7vT` mono + Rotate button. Caption: "Encrypted with AES-256-GCM. Last validated {N} {unit} ago." Existing key persistence/validation unchanged.
- **ChannelSection** — re-skin existing component. Divider list (no card per row). Each row: `#channel-name` + `Bound` badge (when bound) + Bind/Unbind button right-aligned. Inactive rows use secondary button variant. Existing binding mutations unchanged.
- All 4 mounted as ModuleSection children of the Connections group in moduleRegistry.
- Status resolvers wired: Slack `ok` if installed; Drive `ok` if connected, `empty` otherwise; Key `ok` if `has_key`, `empty` otherwise; Channels `ok` if any bound, `empty` otherwise.

### 1.3 Out of Scope
- Any new backend endpoints.
- Mobile responsive treatment beyond default flex/grid wrapping.
- Knowledge / Behavior / Workspace groups.

## 2. The Truth

### 2.1 Acceptance Criteria

```gherkin
Feature: Connections group migration

  Scenario: Slack module renders info-only with team_id + domain
    Given useWorkspaceQuery returns `{...workspace, slack_team_id: "T1", slack_domain: "acme.slack.com"}`
    Then the Slack module shows the avatar tile, workspace name, "T1 · acme.slack.com" mono caption, and an Installed badge
    And no Reinstall button is rendered

  Scenario: Slack module degrades to team_id when domain absent
    Given useWorkspaceQuery returns `{...workspace, slack_team_id: "T1", slack_domain: null}`
    Then the Slack module mono caption shows "T1" only (no separator, no domain)

  Scenario: Drive disconnect preserves existing behavior
    Given Drive is connected as alex@acme.com
    When the user clicks Disconnect
    Then the existing useDisconnectDriveMutation fires
    And on success the section re-renders to the empty state

  Scenario: Provider segmented control persists selection
    Given the workspace has an OpenAI key stored
    Then the OpenAI segment is active in the segmented control
    When the user clicks Google and saves a new key
    Then the active segment swaps to Google

  Scenario: Channels divider list renders bound badge
    Given two channels bound and one unbound
    Then the bound rows show a Bound badge and an Unbind button
    And the unbound row shows a Bind button
    And no card border separates rows — only horizontal dividers
```

### 2.2 Verification Steps (Manual)
- [ ] Open Connections tab — all 4 modules render correctly.
- [ ] Click Disconnect on Drive — existing mutation fires; section flips to empty.
- [ ] Switch provider via segmented control + save — key persists.
- [ ] Bind a channel — Bound badge appears, Unbind button replaces Bind.

## 3. Implementation Guide

### 3.1 Files

| Item | Value |
|---|---|
| New | `frontend/src/components/workspace/SlackSection.tsx` |
| New | `frontend/src/components/workspace/DriveSection.tsx` (extracted from route) |
| Modify | `frontend/src/components/workspace/KeySection.tsx` — re-skin to segmented control + masked-key box |
| Modify | `frontend/src/components/workspace/ChannelSection.tsx` — re-skin to divider list |
| Modify | `frontend/src/components/workspace/moduleRegistry.ts` — wire status resolvers |
| Modify | `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — remove inline DriveSection definition |

### 3.2 Technical Logic
- Avatar tile = `div.h-10.w-10.rounded-md.bg-slate-100.flex.items-center.justify-center` with lucide icon at 20px slate-500.
- Mono captions use `font-mono text-xs text-slate-500`.
- Segmented control reuses Persona's voice-picker pattern? — no, voice presets dropped. Build from scratch as a 3-button row with shared border-radius and `bg-brand-50` on the active segment. Pure Tailwind classes; no new primitive.

### 3.3 API Contract
None new in this story. SlackSection consumes `slack_domain` field added to workspace GET by STORY-025-05.

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Min | Notes |
|---|---|---|
| Vitest unit | 5 | One per Gherkin scenario (Slack-with-domain, Slack-degraded, Drive disconnect, Provider segmented, Channels divider list) |
| Existing | green | KeySection, ChannelSection existing tests must pass unchanged |

### 4.2 Definition of Done
- [ ] All §2.1 scenarios covered.
- [ ] `npm run typecheck` clean.
- [ ] No regression in existing KeySection / ChannelSection test suites.
- [ ] Manual verification §2.2 completed.

---

## ClearGate Ambiguity Gate
**Current Status: 🟢 Low — Ready for Execution**
