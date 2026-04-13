---
sprint_id: "sprint-09"
sprint_goal: "Ship EPIC-008 — Guided setup wizard, channel binding UI, dashboard polish, top nav. First-time user can go from 'New Workspace' to fully configured workspace with bound channels in one guided flow."
dates: "2026-04-13"
status: "Confirmed"
delivery: "D-05"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-13"
---

# Sprint S-09 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry (inline in Epic §6 + Sprint §2 Risk Flags — no formal registry file)
- [x] **Human has confirmed this sprint plan** (2026-04-13)

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1a | [STORY-008-01: Guided Setup Mode](./STORY-008-01-guided-setup-mode.md) | EPIC-008 | L3 | Refinement | — |
| 1b | [STORY-008-02: Channel Binding UI](./STORY-008-02-channel-binding-ui.md) | EPIC-008 | L3 | Refinement | — |
| 1c | [STORY-008-04: Top Nav & Chrome](./STORY-008-04-top-nav-chrome.md) | EPIC-008 | L2 | Refinement | — |
| 2 | [STORY-008-03: Card & Dashboard Polish](./STORY-008-03-card-dashboard-polish.md) | EPIC-008 | L2 | Refinement | 008-02, 008-04 |
| 3 | [STORY-008-05: E2E Verification](./STORY-008-05-e2e-verification.md) | EPIC-008 | L2 | Refinement | All above |

### Context Pack Readiness

**STORY-008-01: Guided Setup Mode**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-008-02: Channel Binding UI**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-008-04: Top Nav & Chrome**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-008-03: Card & Dashboard Polish**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-008-05: E2E Verification**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1 (parallel — 3 worktrees)**: STORY-008-01 (guided setup mode) + STORY-008-02 (channel binding UI) + STORY-008-04 (top nav + chrome). These touch disjoint primary files:
  - 008-01: workspace detail page + new KeySection + new SetupStepper
  - 008-02: new ChannelSection + new useChannels + api.ts (additive) + backend channels.py
  - 008-04: new AppNav + app.tsx layout + __root.tsx + app.index.tsx (FlashBanner removal) + sonner
- **Phase 2 (after Phase 1 merges)**: STORY-008-03 (card + dashboard polish) — depends on channel chips from 008-02 and design tokens from 008-04.
- **Phase 3 (after all code merges + deploy)**: STORY-008-05 (manual E2E verification on deployed environment).

### Merge Ordering
| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-008-04 | Top nav + sonner — foundational layout change that 008-03 needs (Button import pattern, toast infrastructure) |
| 2 | STORY-008-02 | Channel binding — ChannelSection component needed by 008-01 (step 4 placeholder → real component) and 008-03 (card chips) |
| 3 | STORY-008-01 | Guided setup — consumes ChannelSection from 008-02. After merge, detail page has full wizard flow. |
| 4 | STORY-008-03 | Card + dashboard polish — consumes channel chips (008-02), Button component imports (008-04), navigates to guided setup (008-01) |
| 5 | STORY-008-05 | Manual E2E — no code, verifies full stack |

### Shared Surface Warnings
| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `frontend/src/routes/app.tsx` | 008-04 (add AppNav + main wrapper) | Low — single story modifies |
| `frontend/src/routes/app.index.tsx` | 008-04 (remove FlashBanner, add toasts) | Low — single story modifies |
| `frontend/src/routes/app.teams.$teamId.index.tsx` | 008-03 (grid layout, token cleanup, navigate after create) | Low — single story modifies |
| `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` | 008-01 (guided setup mode, import ChannelSection placeholder) | Low — single story modifies |
| `frontend/src/components/dashboard/WorkspaceCard.tsx` | 008-01 (extract KeySection), 008-03 (add channel chips, badges, token cleanup) | **Medium — merge 008-01 before 008-03** |
| `frontend/src/lib/api.ts` | 008-02 (add channel API functions) | Low — additive only |
| `frontend/src/components/dashboard/CreateWorkspaceModal.tsx` | 008-03 (token cleanup, Button), 008-04 (toast errors) | **Medium — merge 008-04 before 008-03** |
| `frontend/src/components/dashboard/RenameWorkspaceModal.tsx` | 008-03 (token cleanup, Button), 008-04 (toast errors) | **Medium — merge 008-04 before 008-03** |
| `backend/app/api/routes/channels.py` | 008-02 (is_member enrichment) | Low — single story modifies |

### Execution Mode
| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-008-01 | L3 | Full Bounce | — | Component extraction + new UI pattern, cross-cutting |
| STORY-008-02 | L3 | Full Bounce | — | New frontend + backend change, ADR-025 compliance critical |
| STORY-008-03 | L2 | Fast Track | — | Styling + layout changes, no security surface, consumes existing patterns |
| STORY-008-04 | L2 | Full Bounce | Yes — first-use sonner | First-use pattern (sonner). FlashBanner removal is destructive. Worth QA pass. |
| STORY-008-05 | L2 | Fast Track | — | Manual verification, defect fixes only |

### Human Notes (Sprint Confirmation)
- **Sonner migration must preserve all existing notifications.** STORY-008-04 R7 already covers the 5 Slack OAuth FlashBanner variants (`ok`, `cancelled`, `expired`, `error`, `session_lost`) and `drive_connect` param. Developer must ensure zero notification regressions — every existing FlashBanner variant maps to a sonner toast equivalent.

### ADR Compliance Notes
- 008-01: Design guide §9.3 step indicator layout. ADR-022 (design system). ADR-024 (workspace model — step completion derived from workspace state).
- 008-02: ADR-025 (explicit channel binding, no fallback, no auto-join). ADR-024 (workspace_channels PK is slack_channel_id). Chip status must distinguish Active vs Pending per ADR-025.
- 008-03: ADR-022 (design system — brand tokens, Button variants). No `#E94560` remaining after this story.
- 008-04: ADR-022 (design system — top nav, toast styling). sonner per design guide §6.5.
- All: No shadcn, no MUI, no Framer Motion (ADR-022 exclusions). Max font-weight: font-semibold.

### Copy Source Reference
| Target | Copy Source | Strip |
|--------|-----------|-------|
| `ChannelSection.tsx` chip pattern | Design guide §6.6 Badge/Status Pill | Use emerald for Active, amber for Pending |
| `AppNav.tsx` layout | Design guide §9.2 top nav mockup | Simplify — no avatar, just email + logout |
| `SetupStepper.tsx` indicator | Design guide §9.3 wizard mockup | Adapt for progressive reveal, not multi-page |

### Dependency Chain
| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-008-03 | STORY-008-02 | Card channel chips reuse ChannelSection chip styling + useChannelBindingsQuery hook |
| STORY-008-03 | STORY-008-04 | Modal toast pattern + Button component import established by 008-04 |
| STORY-008-03 | STORY-008-01 | "New Workspace" navigates to guided setup mode (must exist) |
| STORY-008-05 | ALL | E2E requires full stack deployed with all features merged |

### Risk Flags
- **Shared surface: WorkspaceCard.tsx (Medium):** 008-01 extracts KeySection (structural change), 008-03 adds channel chips + badges (content change). Merge 008-01 first so 008-03 builds on the post-extraction file. Sequential merge ordering eliminates conflict risk.
- **Shared surface: CreateWorkspaceModal + RenameWorkspaceModal (Medium):** 008-04 changes error handling (toast), 008-03 changes styling (tokens + Button). Merge 008-04 first. Sequential ordering eliminates conflict.
- **sonner first-use (Low):** First toast library in the codebase. Could have jsdom compatibility issues in tests. Mitigation: mock `toast` in component tests, verify real behavior in E2E (008-05).
- **Phase 1 parallelism with 3 worktrees (Low):** S-07 and S-08 both ran 2 parallel worktrees successfully. 3 is one more, but the stories have nearly disjoint file surfaces. The merge ordering handles the two medium-risk overlaps.
- **Sprint size (Low):** 5 stories (2x L3 + 3x L2). S-08 completed 6 stories (3x L3 + 2x L2 + 1x L1). This sprint is smaller. Phase 1 parallelism (3 stories at once) front-loads the work.

---

## 3. Sprint Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| None | — | — | — | — |

All questions resolved during EPIC-008 decomposition. No blockers for sprint execution.

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Lead after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
<!-- EXECUTION_LOG_END -->
