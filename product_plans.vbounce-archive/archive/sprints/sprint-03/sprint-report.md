---
sprint_id: "S-03"
sprint_goal: "Ship deploy infrastructure to teemo.soula.ge, apply ADR-024 schema migrations, fix BUG-20260411 PyJWT, and add Slack events stub."
dates: "2026-04-12"
status: "Achieved"
total_tokens_used: "N/A (not instrumented)"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
tag: "v0.3.0-deploy"
---

# Sprint Report: S-03

## 1. What Was Delivered

### User-Facing (Accessible Now)

- **Live at `https://teemo.soula.ge`** — multi-stage Dockerfile, Coolify auto-deploy from GitHub `main`, Traefik HTTPS
- `/` serves React SPA; `/login`, `/register`, `/app` all work via explicit SPA catch-all route

### Internal / Backend (Not Directly Visible)

- Multi-stage Dockerfile (Node 22 Alpine → Python 3.11 slim, 962 MB image)
- SPA catch-all route pattern (`@app.api_route("/{full_path:path}", methods=["GET","HEAD"])`) — replaces broken `StaticFiles(html=True)` SPA fallback
- 3 ADR-024 schema migrations: `teemo_slack_teams`, `teemo_workspace_channels`, `teemo_workspaces` ALTER with FK + `is_default_for_team` + `one_default_per_team` partial unique index
- `TEEMO_TABLES` extended 4→6; health check updated
- **BUG-20260411 fixed**: `decode_token` now uses scoped `jwt.PyJWT()` instance — eliminates global-options leak; 10-run stability loop green
- `POST /api/slack/events` stub handles `url_verification` challenge (unblocks Slack app setup)

### Not Completed

None. All 5 stories delivered. (Sprint-06 production verification collapsed into sprint close.)

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| STORY-003-01: Dockerfile + static serving | EPIC-003 | L2 | Done | 0 | 0 | 5% | Enhancement |
| STORY-003-02: Coolify wiring | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| STORY-003-03: ADR-024 migrations | EPIC-003 | L2 | Done | 0 | 0 | 0% | — |
| STORY-003-04: PyJWT fix | EPIC-003 | L1 | Done | 0 | 0 | 0% | — |
| STORY-003-05: Slack events stub | EPIC-003 | L1 | Done | 0 | 0 | 0% | — |

### Story Highlights

- **STORY-003-01**: Discovered 2 Starlette 1.0.0 spec deviations: `StaticFiles(html=True)` is not an SPA fallback; `@app.get` doesn't auto-handle HEAD. Both flashcards recorded. Explicit catch-all route pattern established.
- **STORY-003-04**: BUG-20260411 (PyJWT module-level options leak) closed. Regression-lock test added; backend test suite passes in any order.
- **Post-release**: 2 incidents caught during sprint close verification: (1) Coolify routed port 3000 instead of 8000 — fixed in Coolify UI; (2) health check used `select("id")` on non-id-PK tables — hotfix commit `ce7c0b1` swapped to `select("*")`. Both flashcards recorded.

### 2.1 Change Requests

| Story | Category | Description | Impact |
|-------|----------|-------------|--------|
| STORY-003-03 | Bug | Hotfix `ce7c0b1`: health check `select("id")` fails on tables with non-id PK | Post-release hotfix, no bounce |

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value |
|--------|-------|
| Stories Planned | 5 |
| Stories Delivered | 5 |
| Stories Escalated | 0 |
| Total QA Bounces | 0 |
| Total Architect Bounces | 0 |
| Average Correction Tax | ~0.83% |
| Bug Fix Tax | 0% |
| Enhancement Tax | ~0.83% |
| First-Pass Success Rate | 100% |
| Total Tests Written | 36 (backend suite) |

---

## 4. Lessons Learned

| Source | Lesson | Recorded? | When |
|--------|--------|-----------|------|
| STORY-003-01 | Starlette StaticFiles(html=True) is not an SPA fallback | Yes | Sprint close |
| STORY-003-01 | Starlette @app.get does not auto-handle HEAD | Yes | Sprint close |
| Post-release | supabase.table().select("id") fails on non-id-PK tables — use select("*") | Yes | Sprint close |
| STORY-003-04 | Agent absolute paths bypass worktree isolation | Yes | Sprint close |

---

## 5. Retrospective

### What Went Well

- Deploy infrastructure shipped Day 2, eliminating the Day-7 cascade risk (per ADR-026).
- Fast Track throughout — 0 bounces, ~0.83% avg tax.
- 2 post-release incidents caught and resolved during sprint close verification before any user impact.
- PyJWT BUG-20260411 closed cleanly with a regression-lock test.

### What Didn't Go Well

- The `.vbounce/scripts/complete_story.mjs` script corrupted sprint plan table cells on multiple runs (over-aggressive cell replacement). Filed as P0 framework issue for `/improve`.
- Agent absolute paths bypassed worktree isolation during a doc edit (flashcard recorded).

### Framework Self-Assessment

#### Tooling & Scripts

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| complete_story.mjs over-aggressive cell replacement corrupted sprint plan 5× | Team Lead | Blocker | Replace with markdown-table-parser + golden-file test |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-15 | Sprint Report generated retroactively at S-11 close audit | Team Lead |
