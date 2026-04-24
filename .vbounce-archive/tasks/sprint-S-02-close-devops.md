# DevOps Task — Sprint S-02 Release Close

> **Working directory:** `/Users/ssuladze/Documents/Dev/SlaXadeL` (main repo)
> **Branch at start:** `sprint/S-02` (4 stories all Done; flashcards + BUG committed; ready for release)
> **Objective:** Release `sprint/S-02` to `main`, tag it, physically archive the sprint folder, update the Roadmap Delivery Log (backfill S-01 AND S-02), close sprint state, push to remote, and delete the sprint branch.

---

## Read First

1. `FLASHCARDS.md` (latest — includes S-02 additions)
2. `.vbounce/sprint-report-S-02.md` — the Sprint Report the Team Lead just wrote (gitignored, local only). Its §9 has the proposed Delivery Log entry.
3. `.vbounce/archive/S-01/sprint-report-S-01.md` — existing S-01 sprint report. Used to build the S-01 Delivery Log entry that was never backfilled.
4. `.vbounce/archive/S-02/sprint-integration-audit-S-02.md` — architect's integration audit (currently untracked in `.vbounce/archive/` — needs to be staged with the archive).
5. `product_plans/strategy/tee_mo_roadmap.md` §7 Delivery Log (currently empty: `*(No deliveries yet — Planning phase.)*`)
6. `.vbounce/state.json` (currently `sprint_id: "S-02"`, all 4 stories `Done`, phase `Phase 3`)

---

## Release Close Plan

All 13 steps must succeed. If any step fails, STOP and return a failure report — do NOT continue forward.

### Step 1 — Sanity check the sprint branch

```bash
git status --porcelain   # must be empty
git branch --show-current   # must be sprint/S-02
git log --oneline main..sprint/S-02 | wc -l   # expect ≥ 18
```

All must pass. If working tree is dirty, STOP.

### Step 2 — Stage the integration audit report

```bash
git add .vbounce/archive/S-02/sprint-integration-audit-S-02.md
git status --short
```

Must show only that single new file staged. Commit:

```bash
git commit -m "archive(S-02): sprint integration audit (SHIP verdict)

Architect Step 6 Integration Audit on sprint/S-02. Verdict: SHIP.
Zero integration findings. 22 backend + 10 frontend tests green,
npm run build exit 0. Strip list clean (all 7 grep hits are
docstring-only). All 5 known-debt items acknowledged.

Sprint: S-02 (close)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 3 — Copy Sprint Report into the archive (on sprint branch)

`.vbounce/sprint-report-S-*.md` is gitignored per `.gitignore` line 37. It must be physically copied into the committed archive at `.vbounce/archive/S-02/sprint-report-S-02.md` (that directory pattern IS committed — note the archive subdir is NOT matched by the gitignore wildcard).

```bash
cp .vbounce/sprint-report-S-02.md .vbounce/archive/S-02/sprint-report-S-02.md
git add .vbounce/archive/S-02/sprint-report-S-02.md
```

**Important gitignore check:** `.gitignore` line 37 says `.vbounce/sprint-report-S-*.md`. Confirm this pattern does NOT match the archive path. If `git check-ignore .vbounce/archive/S-02/sprint-report-S-02.md` returns a match, the gitignore rule is too broad — tighten it at the end of the gitignore with a negation `!.vbounce/archive/**` before committing. If no match, proceed.

```bash
git check-ignore .vbounce/archive/S-02/sprint-report-S-02.md || echo "not ignored — safe to add"
```

If the above prints "not ignored — safe to add", stage the file (already done above) and continue. If it's ignored, you need to add `!.vbounce/archive/**` to `.gitignore` BEFORE the `git add`:

```bash
# Only if the check-ignore matched:
echo "!.vbounce/archive/**" >> .gitignore
git add .gitignore .vbounce/archive/S-02/sprint-report-S-02.md
```

Commit the archived sprint report:

```bash
git commit -m "archive(S-02): sprint report — SHIP verdict, 4/4 stories Done

Team Lead Sprint S-02 Report: all 4 stories Fast Track, zero
escalations, ~2.5% aggregate correction tax, 22 backend + 10
frontend tests green, integration audit SHIP, zero findings.
Browser walkthrough deferred by user; automated gates authoritative.

Sprint: S-02 (close)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 4 — Physically archive the sprint folder

Per the doc-manager skill's Physical Move Rules, move the entire sprint folder to `product_plans/archive/sprints/`:

```bash
git mv product_plans/sprints/sprint-02 product_plans/archive/sprints/sprint-02
git status --short
```

Expected: all 5 files (sprint-02.md + 4 story files) show as renamed (`R`) to the archive path.

Commit:

```bash
git commit -m "archive(sprints): move sprint-02/ → archive/sprints/sprint-02/

Per doc-manager Physical Move Rules, a completed sprint folder moves
to product_plans/archive/sprints/ at release close. The 5 files
(sprint-02.md + 4 story files) are preserved for historical record.

Sprint: S-02 (close)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 5 — Update sprint-02.md frontmatter status to Completed

The archived sprint plan's frontmatter should reflect its final state. Edit `product_plans/archive/sprints/sprint-02/sprint-02.md` frontmatter:

- Change `status: "Active"` → `status: "Completed"`
- (Leave `confirmed_by` / `confirmed_at` as-is — those capture planning-phase human approval, not close.)

Commit:

```bash
git add product_plans/archive/sprints/sprint-02/sprint-02.md
git commit -m "chore(S-02): sprint-02.md status Active → Completed

Sprint closure per Team Lead Sprint Report. All 4 stories Done,
integration audit SHIP, release merge pending.

Sprint: S-02 (close)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 6 — Update Roadmap §7 Delivery Log (backfill S-01 AND S-02)

The Delivery Log at `product_plans/strategy/tee_mo_roadmap.md` §7 currently reads:
```
## 7. Delivery Log

> Appended by Team Lead when each release is archived.

*(No deliveries yet — Planning phase.)*
```

S-01 was never backfilled. Replace the placeholder line with a proper table and two rows — S-01 first (chronological), then S-02:

```markdown
## 7. Delivery Log

> Appended by Team Lead when each release is archived.

| Sprint | Delivery | Date | Summary | Tag |
|--------|----------|------|---------|-----|
| S-01 | D-01 Release 1: Foundation | 2026-04-11 | **Scaffold delivered.** 4/4 stories Done (Fast Track), ~1.75% aggregate correction tax, 1 Dev bounce on STORY-001-03 (version-pin fix from Team Lead sprint-context error — lesson recorded). Ships: FastAPI 0.135.3 scaffold with `/api/health` (per-table `teemo_*` aggregate, cached Supabase singleton, 6 hermetic tests), Vite 8.0.8 + React 19.2.5 + Tailwind 4.2 CSS-first `@theme`, Inter/JetBrains Mono via `@fontsource`, 3 design-system primitives (Button/Card/Badge), TanStack Router file-based routes, landing page with live backend health smoke test via TanStack Query. 3 flashcards recorded (sprint-context must quote Charter verbatim; don't redefine Tailwind 4 built-in slate tokens; bcrypt 5.0 72-byte boundary). | (untagged — release tagging introduced in S-02) |
| S-02 | D-01 Release 1: Foundation | 2026-04-11 | **Auth delivered end-to-end.** 4/4 stories Done (Fast Track), ~2.5% aggregate correction tax, 0 bounces, 0 escalations. Ships: backend `app/core/security.py` (bcrypt + JWT + `validate_password_length` 72-byte guard per ADR-017), 5 auth routes (`/register`, `/login`, `/refresh`, `/logout`, `/me`) with httpOnly cookies (`samesite="lax"` — deliberate deviation for EPIC-005/006 OAuth redirects), `get_current_user_id` dependency, frontend Zustand `useAuth` store + 5 typed `lib/api.ts` wrappers + `AuthInitializer`, and full UI: `/login`, `/register`, `/app` placeholder (gated by `ProtectedRoute`), `SignOutButton`, enabled landing CTA. 22 backend pytest (9 unit + 13 live Supabase integration) + 10 frontend Vitest (first Vitest setup in Tee-Mo, `vitest@^2.1.9`). Architect integration audit verdict: **SHIP** (zero findings). 4 flashcards recorded (samesite=lax, LaxEmailStr for email-validator 2.x `.test` TLD, Vitest `vi.mock` TDZ, TanStack Router `tsc -b && vite build` ordering). 1 BUG filed for S-03 backlog: PyJWT module-level options leak causing test-order flake (production unaffected). Browser walkthrough (11 steps §2.2) deferred by user — not human-verified. | v0.2.0-auth |
```

Also append a Change Log row to §8:

```markdown
| 2026-04-11 | §7 Delivery Log backfilled with S-01 and S-02 entries. Both delivered into D-01 Release 1: Foundation. S-02 tagged v0.2.0-auth. | Team Lead (S-02 close) |
```

Commit:

```bash
git add product_plans/strategy/tee_mo_roadmap.md
git commit -m "docs(roadmap): backfill §7 Delivery Log — S-01 + S-02 delivered

Both sprints ship into D-01 Release 1: Foundation. S-01 was never
backfilled; this closes both gaps in one edit.

S-01: scaffold (FastAPI + health + Vite + Tailwind 4 + design system).
S-02: auth end-to-end (security primitives + 5 routes + httpOnly
      cookies + Zustand store + login/register/app pages). Tagged
      v0.2.0-auth.

Sprint: S-02 (close)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Step 7 — Update `.vbounce/state.json` to closed

`.vbounce/state.json` is gitignored. Edit it to reflect sprint closure. Expected final shape:

```json
{
  "sprint_id": null,
  "sprint_plan": null,
  "roadmap": "product_plans/strategy/tee_mo_roadmap.md",
  "stories": {},
  "phase": "Idle",
  "last_action": "Sprint S-02 closed and released to main as v0.2.0-auth on 2026-04-11. All 4 stories Done. Integration audit SHIP. Sprint folder archived. Roadmap §7 Delivery Log backfilled for S-01 and S-02. Ready for next sprint planning.",
  "updated_at": "2026-04-11T23:59:59.000Z"
}
```

No commit — this file is gitignored.

### Step 8 — Switch to main and merge the sprint branch

```bash
git checkout main
git pull --ff-only origin main   # sync if anything slipped in (should be up-to-date)
git merge sprint/S-02 --no-ff -m "Sprint S-02: Email + password auth end-to-end (D-01)

4 Fast Track stories merged cleanly. 22 backend pytest + 10 frontend
Vitest green. Integration audit SHIP (zero findings).

Ships:
- backend/app/core/security.py — bcrypt + JWT + validate_password_length
- backend/app/api/routes/auth.py — /register /login /refresh /logout /me
- backend/app/api/deps.py — get_current_user_id (cookie-first, Bearer fallback)
- backend/app/models/user.py — UserRegister/UserLogin/UserResponse (LaxEmailStr)
- frontend/src/stores/authStore.ts — first Zustand store in Tee-Mo
- frontend/src/lib/api.ts — apiPost + 5 auth wrappers (AuthUser type)
- frontend/src/components/auth/{AuthInitializer,ProtectedRoute,SignOutButton}.tsx
- frontend/src/routes/{login,register,app}.tsx + landing CTA enabled
- vitest@^2.1.9 (first frontend test runner setup)

4 FLASHCARDS recorded. 1 BUG filed (PyJWT test-order, production unaffected).

Release: v0.2.0-auth
Sprint Report: .vbounce/archive/S-02/sprint-report-S-02.md
Integration Audit: .vbounce/archive/S-02/sprint-integration-audit-S-02.md"
```

### Step 9 — Post-release validation on `main`

Run the full gate one more time on `main`:

```bash
# Backend — use the explicit order to sidestep the known PyJWT flake (BUG-20260411)
cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/test_auth_routes.py tests/test_security.py -v -p no:randomly
```

Expected: **22 passed**.

```bash
cd frontend && npm test
```

Expected: **10 passed**.

```bash
cd frontend && npm run build
```

Expected: **exit 0** (cosmetic `[INEFFECTIVE_DYNAMIC_IMPORT]` warning is fine). If the first invocation fails in `tsc -b` because the route tree is stale, run `node_modules/.bin/vite build` once standalone, then retry `npm run build`.

If ANY gate fails → STOP, write a Post-Release Failure Report, and consider reverting the release merge with `git reset --hard HEAD~1` before pushing. Report back to Team Lead.

### Step 10 — Tag the release

```bash
git tag -a v0.2.0-auth -m "v0.2.0-auth — Sprint S-02 (Email + Password Auth)

End-to-end auth vertical slice shipped in 4 Fast Track stories:
STORY-002-01 security primitives, STORY-002-02 auth routes,
STORY-002-03 frontend auth store, STORY-002-04 login/register pages.

22 backend tests (9 unit + 13 live Supabase integration) + 10
frontend Vitest + clean build. Integration audit: SHIP.

See .vbounce/archive/S-02/sprint-report-S-02.md for the full
sprint report and .vbounce/archive/S-02/sprint-integration-audit-S-02.md
for the architect's findings."
```

### Step 11 — Push to remote

User has authorized push to remote at the close gate.

```bash
git push origin main
git push origin v0.2.0-auth
```

**Do NOT force-push under any circumstances.** If the push is rejected, STOP and return a failure report — investigate before pushing.

### Step 12 — Delete the sprint branch

```bash
git branch -d sprint/S-02   # Must be fully merged — use -d not -D
```

If `-d` is rejected because git thinks the branch isn't merged, investigate — do NOT escalate to `-D`. Something is wrong with the merge.

Also delete from remote if it exists there:
```bash
git push origin --delete sprint/S-02 2>&1 || echo "no remote sprint branch (ok)"
```

Do NOT force-delete. Do NOT remove `story/*` branches — those are already gone from per-story cleanup.

### Step 13 — DevOps Release Report

Write to `.vbounce/archive/S-02/sprint-S-02-devops.md`.

**Required YAML frontmatter:**

```yaml
---
sprint_id: "S-02"
agent: "devops"
phase: "release"
started_at: "<ISO 8601>"
completed_at: "<ISO 8601>"
release_merge_commit: "<SHA>"
release_tag: "v0.2.0-auth"
merged_into: "main"
from_branch: "sprint/S-02"
post_release_backend_tests: "22 passed"
post_release_frontend_tests: "10 passed"
post_release_build: "exit 0"
sprint_branch_deleted: true
pushed_to_remote: true
roadmap_delivery_log_updated: true
sprint_folder_archived: true
state_json_closed: true
input_tokens: 0
output_tokens: 0
total_tokens: 0
---
```

Body sections:

- `## Summary` — 3-4 sentences
- `## Pre-Merge State` — git log summary of sprint/S-02 commits
- `## Closeout Commits` — list of commits made during Steps 2-6 (integration audit, sprint report, sprint folder archive, sprint-02.md status, roadmap backfill)
- `## Release Merge` — merge commit SHA + the message
- `## Post-Release Validation` — backend + frontend + build output tails
- `## Tag` — `v0.2.0-auth` SHA + message
- `## Push` — `git push origin main` + tag push confirmation
- `## Cleanup` — sprint branch deletion (local + remote) confirmation
- `## State` — confirm `.vbounce/state.json` closed, `product_plans/archive/sprints/sprint-02/` present, Roadmap §7 has S-01 + S-02 rows
- `## Concerns`

Then commit the report:

```bash
git add .vbounce/archive/S-02/sprint-S-02-devops.md
git commit -m "archive(S-02): DevOps release report

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
git push origin main
```

(This is an extra commit on top of the tag — the tag already points at the release merge. That's fine; the history is linear.)

---

## Hard Rules

- **NEVER `git add -A` / `git add .`** — always name files explicitly.
- **NEVER force push** (`--force`, `-f`). Pushes use plain `git push origin main` and `git push origin v0.2.0-auth`.
- **NEVER force-delete branches** (`branch -D`). Use `-d` only; if it's rejected, STOP.
- **NEVER skip hooks** (`--no-verify`). Investigate if a hook fails.
- **NEVER commit `.env`, `.vbounce/state.json`, or `.vbounce/reports/*`** (the gitignored runtime files).
- **Use the explicit pytest order** `tests/test_auth_routes.py tests/test_security.py` to sidestep BUG-20260411.
- **If ANY gate fails during post-release validation (Step 9)**, consider reverting the merge BEFORE pushing. The release is NOT committed until Step 11 push. Return a failure report.
- **Only push after Step 9 passes.** Never push a broken `main`.

When Steps 1–13 are done and the DevOps release report is written + committed + pushed, exit with a final summary including:
- Release merge commit SHA
- Tag SHA
- Roadmap §7 final row count (should be 2: S-01 + S-02)
- Confirmation that `product_plans/sprints/` is now empty (or missing)
- Confirmation that `.vbounce/state.json` is closed
