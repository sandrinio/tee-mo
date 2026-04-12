---
type: "sprint-release"
sprint_id: "S-05"
agent: "devops"
action: "sprint-release"
status: "released"
release_tag: "v0.5.0"
merge_commit: "f5839c1"
sprint_branch_deleted: true
origin_pushed: true
post_merge_test_result: "87 backend + 26 frontend passing"
version: "0.5.0"
---

# DevOps Report: Sprint S-05 Release

## Merge

- **From:** `sprint/S-05` (HEAD `b9219e3`)
- **Into:** `main`
- **Strategy:** `--no-ff` (ort strategy)
- **Merge commit SHA:** `f5839c1`
- **Merge message:** `Sprint S-05: Workspace CRUD end-to-end (EPIC-003 Slice B)`
- **Files changed:** 21 files, 2966 insertions, 290 deletions
- **Conflicts:** None

## Release Tag

- **Tag:** `v0.5.0`
- **Type:** Annotated (`git tag -a`)
- **Message:** `Release 1: Workspace CRUD (Sprint S-05)`

## Origin Push

Both `main` and `v0.5.0` pushed successfully without `--force`.

## Cleanup

- `sprint/S-05` branch deleted locally
- `sprint/S-05-fasttrack` orphan branch remains (contains salvage source — can be deleted manually)

## Stories Included in This Release

| Story | Title | Merge SHA |
|---|---|---|
| STORY-003-B01 | Backend Workspace Models | c3d619f |
| STORY-003-B02 | Backend Workspace Routes | da7a7ff |
| STORY-003-B03 | Backend Integration Tests | e4413e3 |
| STORY-003-B04 | Frontend API Wrappers + Hooks | d58734b |
| STORY-003-B05 | Frontend Workspace List UI | 63c27d1 |
| STORY-003-B06 | Rename + Make Default | 31dd9b5 |
| STORY-003-B07 | Manual E2E Verification | (no code — verification only) |

## Post-Sprint Hotfixes (on sprint/S-05, before merge)

| Commit | Description |
|--------|-------------|
| 21e5311 | fix(router): split app.tsx into layout + index for child route rendering |
| b9219e3 | fix(api): align frontend workspace URLs with backend route paths |
