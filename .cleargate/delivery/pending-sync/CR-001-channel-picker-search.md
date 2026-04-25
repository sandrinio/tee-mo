---
cr_id: "CR-001"
parent_ref: "EPIC-005-phase-a"
status: "Draft"
approved: false
severity: "P3-Low"
target_sprint: "S-16"
reporter: "@sandrinio"
created_at: "2026-04-25T00:00:00Z"
updated_at: "2026-04-25T00:00:00Z"
created_at_version: "cleargate-during-S15"
updated_at_version: "cleargate-during-S15"
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

# CR-001: Channel Picker — Add Name Search

> **Origin.** Surfaced during SPRINT-15 manual testing of EPIC-014 upload flow (2026-04-25). After a user installs Tee-Mo into a Slack workspace with many channels, the picker dropdown in `ChannelSection.tsx` becomes unwieldy — there is no filter and the user must scroll through the entire list to find the channel they want to bind. Filed mid-sprint and deferred to S-16 to keep SPRINT-15's scope clean.

## 1. The Context Override (Old vs. New)

**Obsolete Logic (What to Remove / Forget):**
- The picker renders the entire `allChannels` list verbatim via `allChannels.map(channel => …)` at `frontend/src/components/workspace/ChannelSection.tsx:239`. There is no filter input, no name-match predicate, and no count badge — the list scales linearly with the workspace's channel count. Forget the "small workspace" assumption baked into the original EPIC-005 Phase A picker.

**New Logic (The New Truth):**
- The picker renders a top-row `<input type="text">` placeholder `"Search channels…"` that debounces a `query` state.
- The displayed list is `allChannels.filter(ch => ch.name.toLowerCase().includes(query.trim().toLowerCase()))`. Empty query → full list (current behavior preserved).
- Above the list, render a count: `"{filtered.length} of {allChannels.length} channels"` to make the filtering effect obvious.
- Empty filtered result renders the existing "No channels found in this Slack team." copy with the substring appended: e.g. `"No channels match \"foo\""`.

## 2. Blast Radius & Invalidation

- [ ] Invalidate/Update Story: none. EPIC-005 Phase A's STORY-005A-* are all shipped; this CR adds new behavior on top, doesn't break their acceptance.
- [ ] Invalidate/Update Epic: none. EPIC-005 Phase A is closed; this CR is a UX enhancement, not a contract change.
- [ ] Database schema impacts: **No.** Pure client-side filter. No backend / Slack API / Supabase change.
- [ ] Backend impacts: **No.** The list of channels still arrives via the existing `GET /api/workspaces/{id}/channels/list-from-slack` route (or whatever the route name is — this CR doesn't touch it).
- [ ] Vitest fixtures: existing `ChannelSection` tests at `frontend/src/components/workspace/__tests__/` (if any) need a quick read to confirm they don't assert on the absolute list count being unfiltered. If they do, update those assertions or scope-narrow them.

## 3. Execution Sandbox

**Modify:**
- `frontend/src/components/workspace/ChannelSection.tsx` — add `query` state at component scope, render the search input above the picker `<ul>`, filter `allChannels` before `.map()`, render the count badge.

**Do NOT modify:**
- `backend/app/api/routes/channels.py` — Slack-side latency is a separate concern (already debated 2026-04-25; flagged for a future caching CR). This CR does NOT add caching, debouncing on the network side, or pagination.
- `frontend/src/components/workspace/SetupStepper.tsx` — channel-binding step's wrapper unchanged.
- `KnowledgeList`, `PickerSection`, `KeySection` — out of scope.
- Any test other than the existing `ChannelSection` test file (if one exists).

**Estimated size:** L1 trivial. ~15–25 net lines including the count badge. One commit, no architect, no QA agent — single-file UI change with 2–3 component tests sufficient.

## 4. Verification Protocol

**Command/Test:**
```
cd frontend
npm run typecheck
npm test -- ChannelSection
```

**New tests required (≥3):**
1. Renders the search input + full list when `query === ''`.
2. Typing `"general"` filters the list to channels whose name (case-insensitive) contains `"general"` and updates the count badge.
3. Typing a substring with zero matches renders the empty-state copy with the substring quoted.

**Manual verification:**
- `npm run dev` → install Tee-Mo into a workspace with ≥10 channels → open the picker → type a substring → list narrows in real time → backspace → list restores.

**Regression guard:**
- Existing "No channels found in this Slack team." path (when `allChannels.length === 0` from the API) must still render unchanged. The new substring-mismatch copy is a separate branch — both must coexist.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🟢 Green — Ready for S-16 inclusion (pending `approved: true`).**

- [x] Obsolete logic to evict is explicitly declared (§1).
- [x] No downstream items invalidated (§2 — pure additive UX).
- [x] Execution Sandbox contains exact file path (`ChannelSection.tsx`) + clear out-of-scope list.
- [x] Verification command provided.
- [ ] `approved: true` — pending human Gate-1 sign-off as part of SPRINT-16 plan approval.
