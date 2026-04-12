---
sprint_id: "sprint-08"
sprint_goal: "Ship EPIC-006 — Google Drive OAuth, file indexing with AI descriptions, read_drive_file agent tool, and frontend Picker. Complete the demo pipeline: register → workspace → Slack → Drive → @mention → answer from file."
dates: "2026-04-13"
status: "Active"
delivery: "D-04"
confirmed_by: "sandrinio"
confirmed_at: "2026-04-12"
---

# Sprint S-08 Plan

## 0. Sprint Readiness Gate
> This sprint CANNOT start until the human confirms this plan.

### Pre-Sprint Checklist
- [x] All stories below have been reviewed with the human
- [x] Open questions (§3) are resolved or non-blocking
- [x] No stories have 🔴 High ambiguity (spike first)
- [x] Dependencies identified and sequencing agreed
- [x] Risk flags reviewed from Risk Registry
- [x] **Human has confirmed this sprint plan**

---

## 1. Active Scope
> Stories pulled from the backlog for execution during this sprint window.

| Priority | Story | Epic | Label | V-Bounce State | Blocker |
|----------|-------|------|-------|----------------|---------|
| 1a | [STORY-006-01: Drive Service + Config](./STORY-006-01-drive-service.md) | EPIC-006 | L2 | Done | — |
| 1b | [STORY-006-04: Agent Drive Tool](./STORY-006-04-agent-drive-tool.md) | EPIC-006 | L2 | Ready to Bounce | — (can start in parallel, merges after 006-01) |
| 2 | [STORY-006-02: Drive OAuth](./STORY-006-02-drive-oauth.md) | EPIC-006 | L3 | Ready to Bounce | 006-01 |
| 3 | [STORY-006-03: Knowledge CRUD](./STORY-006-03-knowledge-crud.md) | EPIC-006 | L3 | Ready to Bounce | 006-01, 006-02 |
| 4 | [STORY-006-05: Frontend Drive](./STORY-006-05-frontend-drive.md) | EPIC-006 | L3 | Ready to Bounce | 006-02, 006-03 |
| 5 | [STORY-006-06: E2E Verification](./STORY-006-06-e2e-verification.md) | EPIC-006 | L1 | Ready to Bounce | All above |

### Context Pack Readiness

**STORY-006-01: Drive Service + Config**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-006-02: Drive OAuth**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-006-03: Knowledge CRUD**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-006-04: Agent Drive Tool**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-006-05: Frontend Drive**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

**STORY-006-06: E2E Verification**
- [x] Story spec complete (§1)
- [x] Acceptance criteria defined (§2)
- [x] Implementation guide written (§3)
- [x] Ambiguity: 🟢 Low

### Escalated / Parking Lot
- (None)

---

## 2. Execution Strategy

### Phase Plan
- **Phase 1 (parallel)**: STORY-006-01 (drive service + config) + STORY-006-04 (agent drive tool) — disjoint primary files. 006-04 creates the agent tool referencing drive_service, but the tool's internal imports will resolve after 006-01 merges. Start both in parallel worktrees; 006-01 merges first, then 006-04.
- **Phase 2 (after 006-01 merges)**: STORY-006-02 (Drive OAuth) — uses drive_service for token exchange, encryption for refresh token storage.
- **Phase 3 (after 006-02 merges)**: STORY-006-03 (Knowledge CRUD) — uses drive_service + scan_service for content fetch + AI description. Needs OAuth routes for the picker-token endpoint to live alongside.
- **Phase 4 (after 006-02 + 006-03 merge)**: STORY-006-05 (Frontend) — calls all backend routes.
- **Phase 5 (after all code merges + deploy)**: STORY-006-06 (Manual E2E) — requires live infrastructure + Google Cloud Console configuration.

### Merge Ordering
| Order | Story | Reason |
|-------|-------|--------|
| 1 | STORY-006-01 | Foundation — drive_service.py + scan_service.py consumed by all others |
| 2 | STORY-006-04 | Agent tool — imports drive_service, no shared files with OAuth/CRUD |
| 3 | STORY-006-02 | OAuth routes — uses encryption + drive_service, consumed by CRUD + frontend |
| 4 | STORY-006-03 | Knowledge CRUD — uses drive_service + scan_service + lives alongside OAuth routes in main.py |
| 5 | STORY-006-05 | Frontend — calls all backend routes, last code story |
| 6 | STORY-006-06 | Manual E2E — no code, verifies full stack |

### Shared Surface Warnings
| File / Module | Stories Touching It | Risk |
|---------------|--------------------:|------|
| `backend/app/core/config.py` | 006-01 (add Google settings) | Low — additive only |
| `backend/app/agents/agent.py` | 006-04 (add read_drive_file tool + modify _build_system_prompt) | Low — single story modifies it |
| `backend/app/main.py` | 006-02 (mount drive_oauth_router), 006-03 (mount knowledge_router) | Low — additive `include_router()` calls, merge sequentially |
| `backend/app/services/__init__.py` | 006-01 (drive_service, scan_service) | Low — additive only |
| `frontend/src/lib/api.ts` | 006-05 (add typed wrappers for Drive + Knowledge endpoints) | Low — additive only |

### Execution Mode
| Story | Label | Mode | Architect Override? | Reason |
|-------|-------|------|---------------------|--------|
| STORY-006-01 | L2 | Fast Track | — | Pure service files, known patterns, no security surface |
| STORY-006-02 | L3 | Full Bounce | — | OAuth callback handles tokens + encryption, security-sensitive |
| STORY-006-03 | L3 | Full Bounce | — | Cross-cutting: Drive + Scan + DB, BYOK gate logic |
| STORY-006-04 | L2 | Fast Track | — | Extends established agent tool pattern |
| STORY-006-05 | L3 | Full Bounce | — | New route, Google Picker first-use, design system compliance |
| STORY-006-06 | L1 | Fast Track | — | Manual verification, no code |

### ADR Compliance Notes
- 006-01: MIME routing must match ADR-016 exactly (6 types). Scan-tier model IDs must match ADR-004 mapping.
- 006-02: Refresh token encrypted with AES-256-GCM (ADR-002). Stored per-workspace (ADR-009/024). Token NEVER logged.
- 006-03: 15-file cap enforced backend-side (ADR-007). AI description generated via scan-tier (ADR-004/006).
- 006-04: Agent reads files on-demand (ADR-005). Self-healing hash check updates ai_description (ADR-006).
- 006-05: Design follows ADR-022 (Asana-inspired warm minimalism).
- All: Scopes are `drive.file` only (non-sensitive) — see setup guide §2.5.

### Copy Source Reference
| Target | Copy Source | Strip |
|--------|-----------|-------|
| `backend/app/api/routes/drive_oauth.py` | `backend/app/api/routes/slack_oauth.py` | Slack-specific token exchange, replace with Google token endpoint. Keep state JWT pattern, encryption pattern, redirect feedback pattern. |

### Dependency Chain
| Story | Depends On | Reason |
|-------|-----------|--------|
| STORY-006-04 | STORY-006-01 | Agent tool imports drive_service.fetch_file_content |
| STORY-006-02 | STORY-006-01 | OAuth uses drive_service.get_drive_client pattern + config settings |
| STORY-006-03 | STORY-006-01 | CRUD calls drive_service + scan_service |
| STORY-006-03 | STORY-006-02 | picker-token endpoint shares the drive OAuth router or needs refresh token logic |
| STORY-006-05 | STORY-006-02 | Frontend calls drive/connect, drive/status, drive/disconnect |
| STORY-006-05 | STORY-006-03 | Frontend calls knowledge CRUD + picker-token |
| STORY-006-06 | ALL | E2E requires full stack deployed |

### Risk Flags
- **Google Cloud Console not fully configured (Medium):** User has CLIENT_ID/SECRET but hasn't set JS origins, redirect URIs, or enabled APIs yet. Blocks STORY-006-06 (E2E) and real-world testing of 006-02 OAuth. Mitigation: user completes setup guide steps 1-5 during Phase 1-2 (while backend stories are bouncing). Non-blocking for code stories — tests use mocks.
- **Google Picker first-use in React (Medium):** No prior example in codebase. `gapi.load('picker')` is a CDN script, not an npm package. Mitigation: STORY-006-05 §3 has concrete Picker integration code. Follow Google's official React example.
- **Scan-tier model first-use (Low):** First time calling a non-conversation-tier model. Reuses existing `_build_pydantic_ai_model` — minimal risk.
- **Sprint size (Medium):** 6 stories (3x L3 + 2x L2 + 1x L1) in one sprint is the largest yet. S-07 had similar weight (2x L3 + 3x L2 + 1x L1) and completed cleanly. Mitigation: Phase 1 parallelism buys time; 006-06 is zero-code. If behind, 006-06 can slip to S-09 start.

---

## 3. Sprint Open Questions
| Question | Options | Impact | Owner | Status |
|----------|---------|--------|-------|--------|
| Google Cloud Console fully configured? | User must complete setup guide steps 1-5 (origins, redirects, APIs, test users). Env vars already set. | Blocks 006-06 E2E, non-blocking for code stories | sandrinio | **Open — user does this during Phase 1-2** |
| Large file handling? | Truncate at 50K chars + warn user in response + frontend toast | Decided — show warning | sandrinio | **Decided** |
| Refresh token lifecycle? | `prompt=consent` ensures fresh token on every connect. `invalid_grant` → null token + "Reconnect Drive" prompt. Token stays active indefinitely unless user revokes. | Decided — keep active | sandrinio | **Decided** |
| Picker token security? | Keep Google Picker with client-side token. Scoped to `drive.file`, 1hr TTL, HTTPS, requires JWT auth to obtain. | Accepted tradeoff for hackathon | sandrinio | **Decided** |
| Concurrent file indexing? | Sequential queue via asyncio.Lock per workspace. Prevents race conditions + rate limit spikes. | Decided — queue | sandrinio | **Decided** |

---

<!-- EXECUTION_LOG_START -->
## 4. Execution Log
> Updated by the Lead after each story completes.

| Story | Final State | QA Bounces | Arch Bounces | Tests Written | Correction Tax | Notes |
|-------|-------------|------------|--------------|---------------|----------------|-------|
| STORY-006-01 | Done | 0 | 0 | — | 0% | Fast Track. 30/30 tests pass. drive_service + scan_service + config Google vars. |
<!-- EXECUTION_LOG_END -->
