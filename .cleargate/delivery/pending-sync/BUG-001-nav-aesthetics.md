---
bug_id: "BUG-001"
parent_ref: "EPIC-023"
status: "Draft"
severity: "P3-Low"
reporter: "@sandrinio"
approved: false
created_at: "2026-04-21T00:00:00Z"
updated_at: "2026-04-24T00:00:00Z"
created_at_version: "vbounce-hotfix-L1"
updated_at_version: "cleargate-migration-2026-04-24"
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

# BUG-001: Navigation Bar — Glassmorphism Polish

> **Provenance.** Ported from V-Bounce `HOTFIX-20260421-NavAesthetics` (L1 Trivial). The V-Bounce hotfix template was closer to a small scoped CR than a bug report; this port preserves the scope but reshapes to ClearGate's Bug template. Parented to EPIC-023 (UX Production Readiness) since that's where visual polish belongs in ClearGate's hierarchy.

## 1. The Anomaly (Expected vs. Actual)

**Expected Behavior:** The `/app` top navigation bar (`AppNav.tsx`) should feel visually polished — glassmorphism effect over scrolling content, grouped logo + primary link cluster on the left, subtle hover/transition states. Per Charter §2.6 "Minimalistic Modern UI" principle and Design Guide.

**Actual Behavior:** The nav bar renders as a static `bg-white` block with text distributed `left / center / right` — no transparency, no hover treatment, no logo/link grouping. Feels generic rather than deliberate.

## 2. Reproduction Protocol

1. Load the app in a workspace with scrollable content beneath the top nav.
2. Observe `AppNav.tsx` renders solid white without backdrop blur.
3. Hover over the "Workspaces" link — no transition or color change.
4. Inspect DOM: nav is three separate flex regions, not a logo+links cluster.

## 3. Evidence & Context

No error logs — this is a visual/UX defect, not a runtime bug. Evidence is the rendered DOM + Design Guide gap.

```
Current classes on the nav container:
  sticky top-0 bg-white ...

Desired:
  sticky top-0 bg-white/70 backdrop-blur-md ...
```

## 4. Execution Sandbox (Suspected Blast Radius)

**Investigate / Modify:**
- `frontend/src/components/layout/AppNav.tsx`

**Constraint:** If the fix requires modifying more than 2 files, STOP and promote to a Story under EPIC-023. This bug is explicitly scoped as L1 trivial.

## 5. Verification Protocol (The Failing Test)

This is a visual polish change — no existing test fails, and no new test adds meaningful signal. Verification is manual + regression check:

**Manual:**
- [ ] Open the app in a workspace with scrollable content. Confirm nav shows frosted translucency over content behind.
- [ ] Hover "Workspaces". Confirm transition/hover state fires (`hover:text-brand-600` or subtle bg highlight).
- [ ] Confirm logo and primary link render as a single flex cluster on the left.

**Regression:**
- [ ] `npm test` passes (frontend Vitest suite unchanged).
- [ ] `npm run typecheck` passes.
- [ ] No layout shift on route changes (visually compare /app and /app/teams/$id).

## Implementation Notes (carried from V-Bounce hotfix)

Instructions the Developer should follow:
- Add `bg-white/70 backdrop-blur-md` to the sticky nav container instead of plain `bg-white`.
- Move the primary navigation link (`Workspaces`) next to the Logo, forming a single flex container on the left.
- Implement a transition/hover state on the "Workspaces" link (`hover:text-brand-600` or a subtle bg highlight).
- Use `<ul>` / `<li>` structure to set the stage for scalability.

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)

**Current Status: 🟢 Low Ambiguity**

Requirements to pass to Green (Ready for Fix):
- [x] Reproduction steps are 100% deterministic (visual observation).
- [x] Actual vs. Expected behavior is explicitly defined.
- [x] Evidence attached (DOM inspection — no error logs applicable).
- [x] Verification steps defined (manual visual check + regression suite).
- [ ] `approved: true` set by human to authorize push.
