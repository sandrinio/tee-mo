# Handoff: Workspace page redesign

## Overview

Replaces the long, scroll-only workspace settings page in the Tee-Mo admin dashboard with a modular, navigable layout that scales as more modules are added (Skills, Automation, Persona, Audit, Usage, etc.).

The current page stacks every section vertically; admins must scroll past Drive, Key, Files, Channels to reach later modules. The redesign groups modules and gives them a navigation surface so any module is reachable in one click.

## About the Design Files

The files in this bundle are **design references created in HTML** — a clickable prototype showing intended look and behavior, **not production code to copy directly**.

The task is to **recreate these designs inside the existing Tee-Mo React/Tailwind codebase** (`frontend/src/components/...`), using its established patterns:

- Tailwind 4 CSS-first tokens already defined in `frontend/src/app.css`
- Existing UI primitives in `frontend/src/components/ui/*` (Button, Card, Badge)
- Existing dashboard scaffolding in `frontend/src/components/dashboard/*` and `frontend/src/components/workspace/*`
- `lucide-react` for icons (NOT the Lucide CDN used in the prototype)
- `@fontsource/inter` + `@fontsource/jetbrains-mono` (NOT Google Fonts CDN)

Do not lift the inline Tailwind CDN, Babel-in-browser, or window-scoped components from the prototype. They exist only to make the prototype runnable as a single HTML file.

## Fidelity

**High-fidelity.** Final colors, typography, spacing, radii, and module groupings are decided. Recreate pixel-perfectly using the codebase's primitives. The single open question is the **final list of modules** (see Open Questions below).

## Layouts (two variations, user-toggleable in the prototype)

### Variation A — Sidebar settings rail (default)

Two-column layout under the existing `AppNav`:

- **Left rail** — `width: 240px`, `bg: white`, `border-r: 1px slate-200`, full-height.
  - Header block: kicker "WORKSPACE" (11px, slate-500, uppercase, tracking-wider), name "Acme Corp" (16px / 600, slate-900, letter-spacing -0.01em). Below: 1px progress bar (slate-100 track, emerald-500 fill) + percentage + caption "Setup complete".
  - Grouped nav. Each group has an 11px slate-400 uppercase header. Inside each group, items are buttons: 14px slate-700 text, lucide icon (16px) on the left in slate-400, status dot (1.5px circle) on the right. Active item: `bg-brand-50`, text `brand-700`, icon `brand-600`. Hover: `bg-slate-50`.
  - Footer: "Jump to setting" button with ⌘K kbd badge.
- **Right column** — flex-1, `bg: slate-50`. Centered content at `max-w-3xl`, `px-8 py-8`.
  - Breadcrumb (12px slate-500): "Connections / Slack".
  - H1: 24px / 600, slate-900, letter-spacing -0.015em.
  - One-line summary (14px slate-500).
  - Module body inside a card: `rounded-lg border border-slate-200 bg-white`.
  - Footer line: 12px slate-400, "Last edited 2m ago" left, mono workspace_id right.

### Variation B — Status strip + sticky tab bar

Single scrolling page, `max-w-5xl` centered, `px-8 pt-6 pb-16`:

1. **Header**: back link, H1 + Connected badge + "DMs route here" pill, secondary actions on the right.
2. **Status strip**: 5-cell card grid, equal columns. Cells: Workspace, Slack, Provider, Knowledge, Setup. Each cell has 11px uppercase kicker + 14px / 600 value + 12px slate-500 caption.
3. **Sticky tab bar** (`top-14`, `bg-slate-50/90`, `backdrop-blur-sm`, full-bleed within content column): one tab per group. Active tab: `bg-white`, `border slate-200`, `shadow-sm`. Each tab shows "ok-count / total" pill.
4. **Anchored sections** (`scroll-mt-24`): one per module, grouped by group header. Module section is identical to Variation A's content card.
5. **Scrollspy**: when a section's top crosses 200px from viewport top, the corresponding group tab activates. Click a tab to smooth-scroll to that group's first section (offset 140px).

## Modules (current proposal)

Grouped into 5 groups. **Confirm this list with the team** before implementation.

| Group | Module | Icon (lucide-react) | Source of data | Status |
|---|---|---|---|---|
| Connections | Slack | `message-square` | OAuth install record | existing |
| Connections | Google Drive | `folder-open` | OAuth token + email | existing |
| Connections | AI provider | `key-round` | encrypted_keys table | existing |
| Connections | Channels | `hash` | channel_bindings | existing |
| Knowledge | Files | `file-text` | indexed_files | existing |
| Behavior | Persona | `user-round` | new — voice presets + custom instructions textarea | **new** |
| Behavior | Skills | `sparkles` | skills table (+ skills created via `/teemo skill create`) | **new** |
| Behavior | Automation | `zap` | new — triggers (schedule / Slack event / webhook) | **new** |
| Observability | Audit log | `scroll-text` | audit_events | speculative |
| Observability | Usage | `bar-chart-3` | api_call_log aggregate | speculative |
| Workspace | Danger zone | `alert-triangle` | delete workspace action | existing |

## Status semantics

Each module reports one of: `ok` (emerald-500), `partial` (amber-500), `empty` (slate-300), `error` (rose-500), `neutral` (slate-300). Used for sidebar dots in A and tab counts in B. Logic for partial vs. empty is per-module:

- Files: `ok` if 1+ indexed, `partial` if <15 (current rule), `empty` if 0.
- Channels: `ok` if any bound, `empty` otherwise.
- Persona: `partial` until customized at least once.
- Automation: `empty` until first trigger.

## Module bodies — content inventory

### Slack
Avatar tile (40×40 slate-100 bg) + workspace name + mono `team_id · domain` + Installed badge + Reinstall button.

### Google Drive
Avatar tile + connected email + caption "Read-only access · scoped to selected files" + Disconnect button.

### AI provider
3-button segmented control (Google / OpenAI / Anthropic, sentence case in UI). Below: monospace masked key in a slate-50 box (`sk-proj-•••• G7vT`) + Rotate button. Caption: "Encrypted with AES-256-GCM. Last validated 2 minutes ago."

### Channels
Divider list. Each row: `#channel-name` + Bound badge if bound + Bind/Unbind button on right. Inactive rows use the secondary button variant.

### Files
Header strip: "12 of 15 files indexed" left, "Add file" primary button right. Below: divider list, each row = lucide file icon + filename + 1-line italic AI description + Remove button (revealed on hover).

### Persona
Voice picker: 4-button row (Default / Concise / Warm / Formal), same pattern as provider picker. Below: 80px textarea labeled "Custom instructions", placeholder "Always cite the source file. Default to bullets for lists of >3 items."

### Skills
Divider list. Each row: sparkles icon + mono `/teemo skill-name` + caption "{built-in | created in Slack} · {N} uses this month" + Edit button.

### Automation
Empty state: 40×40 slate-100 tile with zap icon, "No automations yet" headline, caption "Trigger Tee-Mo on a schedule, on a Slack event, or from a webhook.", "Create automation" secondary button.

### Audit log
Mono table (12px), 3 columns: relative time (40px) / actor (180px) / action (flex-1). Divider rows.

### Usage
2×2 grid (md: 1×4) of stat cells. Each cell: 12px label + 20px / 600 value + 12px emerald-600 delta. Borders between cells only (no outer card border duplication).

### Danger zone
Single row: title + caption left, danger-variant Delete button right.

## Design Tokens

All tokens come from the existing system (`colors_and_type.css` / `frontend/src/app.css`):

- **Brand**: `#FFF1F2` (50), `#FFE4E6` (100), `#FECDD3` (200), `#F43F5E` (500), `#E11D48` (600), `#BE123C` (700)
- **Surfaces**: white, `#F8FAFC` (page), `#F1F5F9` (muted)
- **Borders**: `#E2E8F0` (subtle), `#CBD5E1` (strong)
- **Text**: `#0F172A` heading, `#334155` body, `#64748B` muted, `#94A3B8` (slate-400) caption
- **Semantic**: emerald-500 success, amber-500 warning, rose-500 danger, sky-500 info
- **Radii**: 6px inputs/sm buttons, 8px cards/lg buttons, 12px sheets, full pills/avatars
- **Shadow**: none / subtle / elevated (only `shadow-sm` used on active tab in B)
- **Type**: Inter (400/500/600 only — no 700), JetBrains Mono, feature settings `cv11 ss01 ss03`
- **Motion**: 150ms hover, 200ms enter, all `ease-out`

## State Management

Per-workspace, the page reads:

- `workspace` — id, name, default flag, install timestamps
- `integrations` — Slack install, Drive connection, provider key (masked)
- `channels` — bound list
- `files` — indexed (id, title, ai_description, source mime)
- `persona` — voice preset, custom instructions
- `skills` — list with usage counts (already in domain model)
- `automations` — triggers (new table)
- `audit_events` — last 50, optionally filtered (existing)
- `usage_aggregate` — 7-day rollup (existing or new — confirm)

For Variation A, also track `activeModuleId` (URL hash or local state). For Variation B, use scroll position; the URL hash should still update on tab click for shareable deep links.

## Interactions & Behavior

- **A**: clicking a sidebar item swaps the right pane immediately. Persist `activeModuleId` in the URL hash (`#m=files`) so refresh keeps state.
- **A**: ⌘K opens a command palette listing every module by label + keyword aliases. Not implemented in prototype — defer until module list stabilizes.
- **B**: scrollspy uses a window scroll listener, threshold 200px from top. Smooth-scroll on tab click, offset 140px to clear the sticky tab bar.
- **B**: each module section's anchor id is `tm-{moduleId}`; deep-links like `#tm-files` should jump on load.
- All buttons, segmented controls, and toggles use the existing focus ring (`ring-2 ring-brand-500 ring-offset-2`).
- Hover on rail items: 150ms color swap. No spring, no bounce, no scale.

## Responsive

- `md` (≥768px): both layouts as designed.
- Below `md`: sidebar rail collapses into a top `<select>` or sheet trigger (not designed in prototype — defer or follow existing dashboard mobile pattern).
- Status strip in B: 5 columns at md+, 2 columns below.

## Open questions for the team

1. **Module list**: confirm Persona / Skills / Automation are all v1. Are Audit log and Usage actually planned, or speculative?
2. **Default layout**: prototype defaults to sidebar (A). The team should pick one before implementation; supporting both in prod is over-scope.
3. **Mobile**: nothing in the prototype handles narrow widths well. Specify before merging.
4. **Permissions**: are all modules visible to all admins, or do Audit / Danger zone gate behind owner role?

## Files in this bundle

- `Workspace v2.html` — runnable single-file prototype.
- `WorkspaceV2A.jsx` — Variation A (sidebar rail) component.
- `WorkspaceV2B.jsx` — Variation B (sticky tabs + scrollspy) component.
- `WorkspaceV2Modules.jsx` — module registry + per-module bodies. Source of truth for the module inventory.
- `Primitives.jsx` / `AppNav.jsx` — shared UI for the prototype (mirror existing codebase primitives).
- `tweaks-panel.jsx` — tweak panel wiring; not part of production.
- `colors_and_type.css` — token reference (already in repo as `frontend/src/app.css`).

## Reference paths in the existing repo

- `frontend/src/components/ui/Button.tsx`, `Card.tsx`, `Badge.tsx`
- `frontend/src/components/layout/AppNav.tsx`
- `frontend/src/components/workspace/*` — current workspace page lives here
- `frontend/src/app.css` — tokens
- `product_plans/strategy/tee_mo_design_guide.md` — full design guide
- `docs/ARCHITECTURE.md` — data model + BYOK flow
