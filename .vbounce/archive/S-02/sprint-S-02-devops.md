---
sprint_id: "S-02"
agent: "devops"
phase: "release"
started_at: "2026-04-11T16:30:00.000Z"
completed_at: "2026-04-11T16:45:00.000Z"
release_merge_commit: "6d2cf01"
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
input_tokens: 3860
output_tokens: 1288
total_tokens: 5148
---

# DevOps Report: Sprint S-02 Release

## Summary

Sprint S-02 was merged into `main` as `v0.2.0-auth` following a clean 13-step release close procedure. All 4 stories (STORY-002-01 through STORY-002-04) were already merged into `sprint/S-02` with no outstanding conflicts. The sprint folder was physically archived via `git mv`, the Roadmap §7 Delivery Log was backfilled for both S-01 and S-02, and all post-release gates (22 backend + 10 frontend + build) passed on `main`. One gitignore tightening was required: `.vbounce/.gitignore` was missing `!archive/**` so `sprint-report-S-02.md` was masked by the `sprint-report-*` rule even inside the committed archive directory.

## Pre-Merge State

Sprint branch `sprint/S-02` was 17 commits ahead of `main` at the start of this DevOps task (after Team Lead committed flashcards + BUG in commit `4c11025`). Working tree was clean (only `.vbounce/archive/S-02/sprint-integration-audit-S-02.md` and `.vbounce/tasks/` were untracked). All 4 stories confirmed `Done` in `state.json`. No story worktrees remained.

Git log of `sprint/S-02` at handoff (17 commits above main):
```
4c11025 docs(sprint-close): S-02 flashcards batch + BUG-20260411 filed
acba4fc archive(S-02): STORY-002-04 dev report + devops report
f88c7f9 Merge STORY-002-04: Login + Register Pages + ProtectedRoute + /app Placeholder
2e71eef feat(frontend): STORY-002-04 login + register + ProtectedRoute + /app
94495f5 chore(state): STORY-002-03-auth_store → Done
b5c90ef archive(S-02): STORY-002-03 dev reports + devops report
d85c02a Merge STORY-002-03: Frontend Auth Store + API Client + AuthInitializer
d9cc7fe feat(frontend): STORY-002-03 auth store + API client + AuthInitializer
34ec049 docs(flashcards): record samesite=lax deviation + LaxEmailStr workaround
c99652a chore(S-02): mark STORY-002-02-auth_routes Done in sprint plan + product graph
50b0d0e archive(S-02): STORY-002-02 dev reports + devops report
3b37be4 Merge STORY-002-02: Auth Routes + httpOnly Cookies + get_current_user_id
0787535 feat(auth): STORY-002-02 auth routes + httpOnly cookies + get_current_user_id
cbcc281 archive(S-02): STORY-002-01 devops report + sprint-02 state update
a480219 archive(S-02): STORY-002-01 dev reports
762ff48 Merge STORY-002-01: Backend Security Primitives + bcrypt Guard
235f153 feat(auth): STORY-002-01 security primitives + bcrypt 72-byte guard
39dad9a docs(sprint): land confirmed S-02 sprint plan and 4 stories
```

## Closeout Commits

Commits made during Steps 2–6 on `sprint/S-02` before the release merge:

| SHA | Step | Message |
|-----|------|---------|
| `33567c4` | Step 2 | `archive(S-02): sprint integration audit (SHIP verdict)` |
| `cca7378` | Step 3 | `archive(S-02): sprint report — SHIP verdict, 4/4 stories Done` (+ .vbounce/.gitignore fix) |
| `9774586` | Step 4 | `archive(sprints): move sprint-02/ → archive/sprints/sprint-02/` |
| `b96e9c8` | Step 5 | `chore(S-02): sprint-02.md status Active → Completed` |
| `4c887ab` | Step 6 | `docs(roadmap): backfill §7 Delivery Log — S-01 + S-02 delivered` |

Note on Step 3: `.vbounce/.gitignore` had `sprint-report-*` and `!archive/` but was missing `!archive/**`. The `!archive/` negation un-ignores the directory node but does not cascade to files matched by `sprint-report-*` inside it. Added `!archive/**` to tighten the rule. Verified with `git check-ignore` before and after.

## Release Merge

- **Commit SHA:** `6d2cf01`
- **Branch:** `sprint/S-02` → `main`
- **Strategy:** `--no-ff` (preserves sprint history as a discrete block)
- **Conflicts:** None — ort strategy merged cleanly
- **Files changed:** 50 files, 6134 insertions, 85 deletions

Merge message:
```
Sprint S-02: Email + password auth end-to-end (D-01)

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
Integration Audit: .vbounce/archive/S-02/sprint-integration-audit-S-02.md
```

## Post-Release Validation

All gates run on `main` after the merge commit `6d2cf01`.

### Backend (22/22)

```
tests/test_auth_routes.py tests/test_security.py -v -p no:randomly

tests/test_auth_routes.py::test_register_happy_path PASSED
tests/test_auth_routes.py::test_register_duplicate_email PASSED
tests/test_auth_routes.py::test_register_password_too_long PASSED
tests/test_auth_routes.py::test_register_invalid_email PASSED
tests/test_auth_routes.py::test_login_happy_path PASSED
tests/test_auth_routes.py::test_login_wrong_password PASSED
tests/test_auth_routes.py::test_login_unknown_email PASSED
tests/test_auth_routes.py::test_me_with_valid_access_cookie PASSED
tests/test_auth_routes.py::test_me_without_cookie PASSED
tests/test_auth_routes.py::test_me_with_expired_access_cookie PASSED
tests/test_auth_routes.py::test_refresh_happy_path PASSED
tests/test_auth_routes.py::test_refresh_with_access_token_in_refresh_slot PASSED
tests/test_auth_routes.py::test_logout_clears_cookies PASSED
tests/test_security.py::test_hash_and_verify_roundtrip PASSED
tests/test_security.py::test_hash_password_is_salted PASSED
tests/test_security.py::test_access_token_has_15_minute_expiry PASSED
tests/test_security.py::test_refresh_token_has_7_day_expiry_and_type_claim PASSED
tests/test_security.py::test_decode_token_rejects_expired_token PASSED
tests/test_security.py::test_decode_token_rejects_tampered_signature PASSED
tests/test_security.py::test_validate_password_length_rejects_73_bytes PASSED
tests/test_security.py::test_validate_password_length_accepts_72_bytes PASSED
tests/test_security.py::test_validate_password_length_counts_utf8_bytes PASSED

22 passed, 2 warnings in 8.31s
```

Note: Explicit ordering `test_auth_routes.py` before `test_security.py` used per BUG-20260411 (PyJWT module-level options leak).

### Frontend (10/10)

```
vitest run

✓ src/stores/__tests__/authStore.test.ts (10 tests) 5ms

Test Files  1 passed (1)
     Tests  10 passed (10)
  Duration  590ms
```

### Build (exit 0)

```
npm run build

✓ built in 203ms

[INEFFECTIVE_DYNAMIC_IMPORT] Warning: src/main.tsx is dynamically imported by
src/stores/authStore.ts but also statically imported by index.html, dynamic
import will not move module into another chunk.
```

Cosmetic `[INEFFECTIVE_DYNAMIC_IMPORT]` warning is pre-accepted (documented in FLASHCARDS.md Vitest TDZ entry — it is the intentional workaround for the `vi.mock` hoisting issue in `authStore.ts`).

## Tag

- **Tag:** `v0.2.0-auth`
- **Tag SHA:** `22c1abaedf983490eaedeb507746d52334b8402e`
- **Type:** Annotated (`git tag -a`)
- **Points to merge commit:** `6d2cf01`

Tag message:
```
v0.2.0-auth — Sprint S-02 (Email + Password Auth)

End-to-end auth vertical slice shipped in 4 Fast Track stories:
STORY-002-01 security primitives, STORY-002-02 auth routes,
STORY-002-03 frontend auth store, STORY-002-04 login/register pages.

22 backend tests (9 unit + 13 live Supabase integration) + 10
frontend Vitest + clean build. Integration audit: SHIP.

See .vbounce/archive/S-02/sprint-report-S-02.md for the full
sprint report and .vbounce/archive/S-02/sprint-integration-audit-S-02.md
for the architect's findings.
```

## Push

```
git push origin main
→ 0ba72bd..6d2cf01  main -> main  ✓

git push origin v0.2.0-auth
→ * [new tag]  v0.2.0-auth -> v0.2.0-auth  ✓
```

No force push. No rejected pushes.

## Cleanup

- Local branch `sprint/S-02` deleted with `git branch -d sprint/S-02` (was `4c887ab`). `-d` accepted without error — branch was fully merged.
- Remote branch: `sprint/S-02` did not exist on origin (was never pushed to remote). `git push origin --delete sprint/S-02` returned "remote ref does not exist" — expected, not an error.

## State

- **`.vbounce/state.json`:** Updated to `"phase": "Idle"`, `"sprint_id": null`, `"stories": {}`. Gitignored — not committed.
- **`product_plans/archive/sprints/sprint-02/`:** Present with all 5 files (sprint-02.md status=Completed, 4 story files). Confirmed by `git mv` rename output.
- **`product_plans/sprints/`:** Empty. The `sprint-02/` directory was the only content; it has been moved to archive. `product_plans/sprints/` directory itself remains (empty).
- **Roadmap §7:** Contains 2 rows — S-01 (Foundation scaffold, untagged) and S-02 (Auth end-to-end, `v0.2.0-auth`). Change Log §8 updated with `2026-04-11` entry for the backfill.
- **`.vbounce/archive/S-02/`:** Contains sprint-integration-audit-S-02.md, sprint-report-S-02.md, and 4 story archive subdirectories with Dev and DevOps reports.

## Concerns

1. **Browser walkthrough deferred by user.** The 11 manual browser checks in STORY-002-04 §2.2 were not executed. All automated gates pass; the unverified exposure is the React → Zustand → navigate chain in a real browser session. Recommend running before any stakeholder demo.
2. **PyJWT test-order flake (BUG-20260411).** Running `test_security.py` before `test_auth_routes.py` flips `test_decode_token_rejects_tampered_signature`. Mitigated by explicit ordering in all DevOps gates. Filed as `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md` for S-03.
3. **gitignore gap fixed.** `.vbounce/.gitignore` was missing `!archive/**`. Fixed in Step 3 commit `cca7378`. No sprint report archives were previously lost (S-01 report was committed before this rule was an issue).

## Process Feedback

- The `.vbounce/.gitignore` negation for archive was incomplete (`!archive/` without `!archive/**`). This caused `git check-ignore` to still match the sprint report inside the archive subdirectory. Adding `!archive/**` was straightforward but took an extra investigation round. Suggest the template for `.vbounce/.gitignore` be pre-populated with both lines.
- The task file's gitignore check correctly anticipated this issue and provided the diagnostic command. The `!.vbounce/archive/**` negation proposed there works at the root `.gitignore` level, but the actual block was in `.vbounce/.gitignore` — the fix needed to go in the right file.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| DevOps | 3,864 | 1,633 | 5,497 |
