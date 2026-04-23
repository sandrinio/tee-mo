# DevOps Task — Sprint S-03 Release Close (merge + tag + push)

> **Working directory:** `/Users/ssuladze/Documents/Dev/SlaXadeL` (main repo, currently on `sprint/S-03`)
> **Phase:** Steps 1–6 of the release plan. Does NOT include curl verification (pauses on user Coolify redeploy) or archive/Roadmap/state close (Team Lead handles after verification).

---

## Read First

1. `.vbounce/sprint-report-S-03.md` (gitignored working copy) or `.vbounce/archive/S-03/sprint-report-S-03.md` (tracked copy). §10 has the exact merge/tag/push command sequence.
2. `FLASHCARDS.md` — all current entries.
3. `product_plans/sprints/sprint-03/sprint-03.md` — §1 Active Scope shows 5/6 stories Done; STORY-003-06 collapsed into this sprint close per user decision.

---

## Preconditions (verify before touching git)

- [x] All 5 S-03 stories merged into `sprint/S-03` (log shows commits for STORY-003-01 through -005)
- [x] `sprint/S-03` is 22 commits ahead of `main`
- [x] `sprint/S-03` is pushed to `origin/sprint/S-03` (pushed earlier in sprint for visibility)
- [x] No worktrees remaining (all stories cleaned up)
- [x] `sprint-report-S-03.md` is in `.vbounce/archive/S-03/` ready to stage
- [x] User confirmed: "push to main and I'll redeploy manually"
- [x] User confirmed: tag name `v0.3.0-deploy`
- [x] User pre-authorized the full merge + pytest + tag + push sequence

## Safety rails

- **Do NOT push if post-merge pytest fails.** Revert the merge locally (`git reset --hard ORIG_HEAD` before pushing) and write a failure report.
- **Do NOT run the curl verification** against `https://teemo.soula.ge` in this task. User will manually redeploy Coolify first; Team Lead curls after.
- **Do NOT archive the sprint folder** yet — that runs post-verification.
- **Do NOT touch Roadmap §7 or state.json** — Team Lead owns those after verification.
- **Do NOT delete `sprint/S-03` branch** — Team Lead deletes after full close.

---

## Execution Plan (6 steps)

### Step 1 — Sanity check the sprint branch

```bash
git status --short   # Expect: M product_plans/sprints/sprint-03/sprint-03.md + A .vbounce/archive/S-03/sprint-report-S-03.md
git branch --show-current   # sprint/S-03
git rev-list --count origin/main..sprint/S-03   # expect ≥ 22
```

The dirty `sprint-03.md` (linter edits from the story merges) and the new sprint report file are expected.

### Step 2 — Stage and commit pre-release housekeeping

```bash
git add .vbounce/archive/S-03/sprint-report-S-03.md product_plans/sprints/sprint-03/sprint-03.md
git status --short   # Confirm only these 2 files staged
git commit -m "chore(S-03): stage sprint report + linter-updated sprint plan before release merge

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 3 — Switch to main and merge

```bash
git checkout main
git pull --ff-only origin main   # sync any slipped changes

git merge sprint/S-03 --no-ff -m "Sprint S-03: Deploy infrastructure + ADR-024 schema + PyJWT fix + Slack events stub

First production deploy infrastructure per ADR-026. Multi-stage Dockerfile
(Vite → FastAPI same-origin, port 8000) + .dockerignore + main.py StaticFiles
mount with SPA catch-all. Coolify setup runbook at
product_plans/sprints/sprint-03/coolify-setup-steps.md.

ADR-024 schema refactor applied: teemo_slack_teams (slack_team_id PK, owner FK,
encrypted bot token) + teemo_workspace_channels (slack_channel_id PK, workspace FK)
created; teemo_workspaces ALTERed with slack_team_id FK + is_default_for_team
+ one_default_per_team partial unique index. TEEMO_TABLES 4 → 6. User ran SQL
migrations manually in Supabase SQL editor.

BUG-20260411 FIXED: decode_token migrated to scoped jwt.PyJWT() instance.
Regression-lock test + 10-run stability loop green. Backend test suite now
passes in any order — no more -p no:randomly workaround.

Slack events verification stub shipped: POST /api/slack/events handles
url_verification challenge (200 with plain-text response); 202 for other
event types; 400 for malformed JSON. No signature verification yet (S-04).
Unblocks Slack app setup guide Steps 5–7 once live.

6 stories planned, 5 bounced + 1 (STORY-003-06 production verification)
collapsed into this release. Fast Track throughout, 0 QA bounces, 0 Arch
bounces, ~0.83% aggregate correction tax. Backend 22 → 36 tests. Frontend
10 unchanged. Image size 962 MB (accepted — optimization deferred).

Release: v0.3.0-deploy
Sprint report: .vbounce/archive/S-03/sprint-report-S-03.md"
```

### Step 4 — Post-merge regression on main

```bash
cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/ -v
```

Expected: **36 passed** in any order (no explicit ordering needed — BUG-20260411 is fixed). Also expect 1 warning about email-validator `.test` TLD (pre-existing from S-02, harmless).

If pytest returns anything other than 36 passed:

```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL
git reset --hard ORIG_HEAD   # undo the merge LOCALLY
git checkout sprint/S-03     # go back to sprint branch
```

Then write a Post-Merge Failure Report and STOP. Do NOT proceed to tag or push.

Also run frontend regression:

```bash
cd ../frontend && npm test
```

Expected: **10 passed**.

Also verify the Docker build still works on main:

```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL
docker --context orbstack build . -t teemo-main-verify 2>&1 | tail -5
docker --context orbstack rmi teemo-main-verify
```

Expected: exit 0.

### Step 5 — Tag the release

```bash
cd /Users/ssuladze/Documents/Dev/SlaXadeL
git tag -a v0.3.0-deploy -m "v0.3.0-deploy — Sprint S-03 (Deploy + Schema + PyJWT Fix)

Ships deploy infrastructure (ADR-026 implementation), ADR-024 schema refactor,
BUG-20260411 fix, and Slack events verification stub. Backend 22 → 36 tests.
Integration audit waived — all S-03 stories touch distinct sections, post-merge
pytest is the regression gate.

Release 1 (Foundation) now includes deploy at https://teemo.soula.ge.

See .vbounce/archive/S-03/sprint-report-S-03.md for the full sprint report."
```

### Step 6 — Push main + tag to origin

```bash
git push origin main
git push origin v0.3.0-deploy
```

**Do NOT force push. Do NOT skip this step.** User has authorized the push and is waiting to manually redeploy Coolify from this commit.

### Step 7 — Write the DevOps release report

Write to `.vbounce/archive/S-03/sprint-S-03-devops-release.md`. **Do this BEFORE exiting** so the Team Lead has an audit trail.

**Required YAML frontmatter:**

```yaml
---
sprint_id: "S-03"
agent: "devops"
phase: "release-close-partial"
started_at: "<ISO 8601>"
completed_at: "<ISO 8601>"
release_merge_commit: "<SHA>"
release_tag: "v0.3.0-deploy"
merged_into: "main"
from_branch: "sprint/S-03"
post_merge_backend_tests: "36 passed"
post_merge_frontend_tests: "10 passed"
post_merge_docker_build: "exit 0"
pushed_main: true
pushed_tag: true
sprint_branch_deleted: false   # Team Lead handles after Coolify deploy verification
archive_move_done: false        # Team Lead handles after Coolify deploy verification
roadmap_updated: false          # Team Lead handles after Coolify deploy verification
state_json_closed: false        # Team Lead handles after Coolify deploy verification
input_tokens: 0
output_tokens: 0
total_tokens: 0
---
```

Body sections: Summary, Pre-Merge Status, Commits Created, Post-Merge Validation (backend pytest + frontend vitest + docker build), Tag, Push Output, User Action Handoff (manual Coolify redeploy pending), Concerns.

Commit the report:

```bash
git add .vbounce/archive/S-03/sprint-S-03-devops-release.md
git commit -m "archive(S-03): DevOps release report — merge + tag + push done

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
git push origin main
```

### Step 8 — Exit

Return control to the Team Lead. Summary should include:
- Release merge commit SHA
- Tag SHA
- Post-merge pytest count (expected 36)
- Push confirmation
- Reminder that user needs to manually redeploy Coolify from `main`
- Reminder that archive/Roadmap/state close is the Team Lead's task after user Coolify redeploy + curl verification

---

## Hard Rules

- NEVER `git add -A` / `git add .`.
- NEVER force push.
- NEVER push on post-merge test failure — revert with `git reset --hard ORIG_HEAD` first.
- NEVER skip hooks (`--no-verify`).
- Use `--context orbstack` for all docker commands.
- Stop at Step 7 (report + push). Do NOT archive the sprint folder, do NOT update Roadmap, do NOT close state.json, do NOT delete `sprint/S-03` branch. Those are Team Lead tasks after Coolify redeploy + curl verification.
