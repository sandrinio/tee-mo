---
sprint_id: "S-04"
sprint_goal: "Ship EPIC-005 Phase A — real Slack OAuth install end-to-end: signed-state JWT, OAuth code exchange, AES-256-GCM token encryption, bot token upsert, hardened events signing."
dates: "2026-04-12"
status: "Achieved"
total_tokens_used: "N/A (not instrumented)"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
tag: "v0.4.0"
---

# Sprint Report: S-04

## 1. What Was Delivered

### User-Facing (Accessible Now)

- **Real Slack OAuth install** — "Install Slack" button on `/app` is a real `<a href>` initiating OAuth; callback writes `teemo_slack_teams` row and redirects to `/app`
- Slack Teams list on `/app` with empty state, loading skeleton, 5 flash banner variants, inline error with retry
- Hardened `POST /api/slack/events` — HMAC-SHA256 v0 signature verification (closes S-03 TODO)

### Internal / Backend (Not Directly Visible)

- `backend/app/core/encryption.py` — first use of `cryptography.hazmat.primitives.ciphers.aead.AESGCM` (ADR-002)
- `backend/app/core/slack.py` — single-import-point for slack-bolt, `request_verification_enabled=True`
- `GET /api/slack/install` — signed-state JWT OAuth URL builder
- `GET /api/slack/oauth/callback` — code exchange → `oauth.v2.access` → `auth.test` → AES-256-GCM encrypt → upsert `teemo_slack_teams` → redirect (5 success branches, 3 hard-fail branches)
- `GET /api/slack/teams` — explicit-column select (no token leakage)
- `get_current_user_id_optional` FastAPI dependency for OAuth redirect flows
- RTL component test infrastructure — `vitest.config.ts`, `test-setup.ts`, jest-dom/jsdom devDeps
- First-use `httpx.AsyncClient` monkeypatch pattern established

### Not Completed

None. All 6 stories delivered.

### Product Docs Affected

N/A — vdoc not installed.

---

## 2. Story Results

| Story | Epic | Label | Final State | Bounces (QA) | Bounces (Arch) | Correction Tax | Tax Type |
|-------|------|-------|-------------|--------------|----------------|----------------|----------|
| STORY-005A-01: Slack bootstrap | EPIC-005 | L2 | Done | 0 | 0 | 5% | Enhancement |
| STORY-005A-02: Events signing verification | EPIC-005 | L2 | Done | 0 | 0 | 0% | — |
| STORY-005A-03: Slack teams endpoint | EPIC-005 | L1 | Done | 0 | 0 | 5% | Enhancement |
| STORY-005A-04: OAuth callback | EPIC-005 | L3 | Done | 0 | 0 | 0% | — |
| STORY-005A-05: Teams list API | EPIC-005 | L1 | Done | 0 | 0 | 0% | — |
| STORY-005A-06: Frontend install UI | EPIC-005 | L2 | Done | 0 | 0 | 5% | Enhancement |

### Story Highlights

- **STORY-005A-04 (L3, Full Bounce)**: OAuth callback passed QA + Architect on first attempt with zero security findings. 5 Phase B risks documented by Architect for post-hackathon hardening.
- **STORY-005A-01**: Two issues discovered in Green phase: base64url padding required for `TEEMO_ENCRYPTION_KEY`; `AsyncApp` constructor uses `request_verification_enabled` not `token_verification_enabled`. Both flashcards recorded.
- **STORY-005A-06**: RTL component test infrastructure added as legitimate scope expansion (no prior component test setup existed).

### 2.1 Change Requests

None mid-sprint. `complete_story.mjs` table cell corruption required 5 manual hand-patches; filed as P0 framework issue.

---

## 3. Execution Metrics

### V-Bounce Quality

| Metric | Value |
|--------|-------|
| Stories Planned | 6 |
| Stories Delivered | 6 |
| Stories Escalated | 0 |
| Total QA Bounces | 0 |
| Total Architect Bounces | 0 |
| Average Correction Tax | ~2.5% |
| Bug Fix Tax | 0% |
| Enhancement Tax | ~2.5% |
| First-Pass Success Rate | 100% |
| Total Tests Written | 46 new (8+8+6+10+5+9); 92 total passing |

---

## 4. Lessons Learned

| Source | Lesson | Recorded? | When |
|--------|--------|-----------|------|
| STORY-005A-01 | httpx must be imported at module level for monkeypatching | Yes | Sprint close |
| STORY-005A-01 | Supabase upsert — omit DEFAULT NOW() columns from payload | Yes | Sprint close |
| STORY-005A-01 | base64url padding required before urlsafe_b64decode | Yes | Sprint close |
| STORY-005A-01 | slack_bolt AsyncApp uses request_verification_enabled, not token_verification_enabled | Yes | Sprint close |
| STORY-005A-02 | /api/slack/events 400 body changed from JSON to bare Response | Yes | Sprint close |
| STORY-005A-06 | vitest@2.1.9 + vite@8 — separate vitest.config.ts avoids ProxyOptions type conflict | Yes | Sprint close |
| STORY-005A-06 | @testing-library/react auto-cleanup requires globals:true in vitest config | Yes | Sprint close |

---

## 5. Retrospective

### What Went Well

- 0 QA/Arch bounces across all 6 stories including the L3 OAuth callback. EPIC-005 Phase A complete with zero security findings from Architect.
- Encryption (AES-256-GCM), signing verification, and token storage all implemented correctly first pass.
- 7 flashcards recorded at sprint close — richest single-sprint lesson harvest in the project.

### What Didn't Go Well

- `complete_story.mjs` table corruption was a recurring pain point (5 manual repairs). P0 framework bug filed.
- One process deviation: Team Lead nearly bypassed subagents during a rate-limit block; user course-corrected. No code landed outside the subagent path.

### Framework Self-Assessment

#### Tooling & Scripts

| Finding | Source Agent | Severity | Suggested Fix |
|---------|-------------|----------|---------------|
| complete_story.mjs corrupted sprint plan table cells 5× — persistent from S-03 | Team Lead | Blocker | Replace with markdown-table-parser + golden-file test (same fix as S-03) |

---

## 6. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-15 | Sprint Report generated retroactively at S-11 close audit | Team Lead |
