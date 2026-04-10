---
last_updated: "2026-04-11"
status: "Draft"
charter_ref: "product_plans/strategy/tee_mo_charter.md"
roadmap_ref: "product_plans/strategy/tee_mo_roadmap.md"
inspiration: "Asana (https://asana.com)"
---

# Tee-Mo Design Guide

> Implementation-ready design system for the Tee-Mo dashboard. Built on Tailwind CSS 4 + React 19 per Charter §3.2. Inspired by Asana's minimalistic, warm, modern aesthetic.

## 1. Design Principles

From Charter §2.6 (Minimalistic Modern UI), refined into actionable rules:

1. **Whitespace Before Ornament** — generous padding and line-height do more for polish than gradients, borders, or shadows. When in doubt, add space.
2. **One Accent Color** — a single coral brand color carries all emphasis. No secondary brand colors, no decorative gradients.
3. **Type-Led Hierarchy** — size, weight, and color on text communicate importance. Borders and backgrounds are last resort.
4. **Subtle Motion** — every interactive element animates, but under 200ms. No bouncing, no flourishes.
5. **Functional Color** — color only carries meaning (brand, success, warning, error, link). Decorative color is forbidden.
6. **Comfortable Density** — airy but not wasteful. Target ~60-70% content, ~30-40% whitespace on primary screens.

---

## 2. Color System

### 2.1 Brand

| Token | Value | Usage |
|-------|-------|-------|
| `brand-50` | `#FFF1F2` | Hover backgrounds, selected-row tint |
| `brand-100` | `#FFE4E6` | Subtle fills, avatar backgrounds |
| `brand-500` | `#F43F5E` | **Primary brand.** Buttons, links, focus rings, logo accent |
| `brand-600` | `#E11D48` | Button hover, pressed states |
| `brand-700` | `#BE123C` | Text on light brand backgrounds |

> Coral/rose hue chosen to echo Asana's warmth without copying. Tailwind equivalent: `rose-*`.

### 2.2 Neutrals (Slate)

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| `surface-0` | `#FFFFFF` | `white` | Cards, modals, input backgrounds |
| `surface-50` | `#F8FAFC` | `slate-50` | Page background |
| `surface-100` | `#F1F5F9` | `slate-100` | Hover states, muted sections |
| `border-subtle` | `#E2E8F0` | `slate-200` | Dividers, input borders |
| `border-strong` | `#CBD5E1` | `slate-300` | Hover borders, card outlines |
| `text-muted` | `#64748B` | `slate-500` | Secondary text, placeholder, captions |
| `text-body` | `#334155` | `slate-700` | Body paragraphs |
| `text-heading` | `#0F172A` | `slate-900` | Headings, emphasized text |

### 2.3 Semantic

| Token | Value | Tailwind | Usage |
|-------|-------|----------|-------|
| `success` | `#10B981` | `emerald-500` | BYOK key validated, file indexed, success toasts |
| `warning` | `#F59E0B` | `amber-500` | Context truncated, rate limit warnings |
| `danger` | `#E11D48` | `rose-600` | Error states, destructive action confirm |
| `info` | `#0EA5E9` | `sky-500` | Neutral info banners, tooltips |

### 2.4 Usage Rules

- **One accent per screen.** Never mix `brand` with `info` or `success` as co-equal emphasis.
- **Backgrounds stay neutral.** Never use semantic colors as page backgrounds — only for icon dots, badges, or thin borders.
- **Error states use `border-danger border-l-4`** on the left edge of the affected input/card, never full-background red.
- **Dark mode is out of scope for v1.** Ship light only. (Tailwind 4's `dark:` prefix stays off the HTML root.)

---

## 3. Typography

### 3.1 Font Stack

```css
/* app.css */
font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
font-feature-settings: 'cv11', 'ss01', 'ss03'; /* Inter stylistic alternates */

/* Monospace (code, API keys, masked tokens) */
font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', monospace;
```

Install via Google Fonts or `@fontsource/inter`. Inter is free, open, and renders beautifully at every size.

### 3.2 Scale

| Style | Tailwind Class | Size / Line | Weight | Usage |
|-------|---------------|-------------|--------|-------|
| **Display** | `text-4xl font-semibold tracking-tight` | 36px / 40px | 600 | Landing hero, setup welcome |
| **Page Title** | `text-2xl font-semibold tracking-tight` | 24px / 32px | 600 | Dashboard pages, workspace name |
| **Section Title** | `text-lg font-semibold` | 18px / 28px | 600 | Card headers, form sections |
| **Subtitle** | `text-base font-medium` | 16px / 24px | 500 | Subheads, emphasized body |
| **Body** | `text-sm` | 14px / 20px | 400 | Default body text, form fields |
| **Caption** | `text-xs text-slate-500` | 12px / 16px | 400 | Helper text, timestamps, labels |
| **Mono** | `font-mono text-sm` | 14px | 400 | API keys, file IDs, code |

### 3.3 Heading Rules

- Tight tracking (`tracking-tight`) only on `text-2xl` and larger — adds polish, never on body.
- Never use `font-bold` (700) — `font-semibold` (600) is the maximum weight for text. Bold feels shouty on Inter.
- Page titles sit directly on the page background, never inside a card. Cards get Section Titles only.

---

## 4. Spacing & Layout

### 4.1 Baseline

Tailwind's default 4px grid. All spacing rounds to these increments:

```
1 = 4px   2 = 8px   3 = 12px   4 = 16px   5 = 20px
6 = 24px  8 = 32px  10 = 40px  12 = 48px  16 = 64px
```

### 4.2 Standard Distances

| Usage | Value | Tailwind |
|-------|-------|----------|
| Card inner padding | 24px | `p-6` |
| Card gap (stacked) | 16px | `space-y-4` |
| Section gap (between logical groups) | 32px | `space-y-8` |
| Form field gap | 16px | `space-y-4` |
| Button padding (default) | 10px × 16px | `px-4 py-2.5` |
| Button padding (large) | 12px × 24px | `px-6 py-3` |
| Input padding | 10px × 12px | `px-3 py-2.5` |
| Page max width | 1280px | `max-w-7xl mx-auto` |
| Page horizontal padding | 24px → 32px | `px-6 lg:px-8` |
| Page vertical padding | 32px → 48px | `py-8 lg:py-12` |

### 4.3 Layout Grid

- **12-column** implied grid via Tailwind's built-in `grid-cols-12`
- **Gutter:** `gap-6` (24px) for cards, `gap-8` (32px) for major sections
- **Responsive breakpoints:** `sm: 640, md: 768, lg: 1024, xl: 1280, 2xl: 1536` (Tailwind defaults)

---

## 5. Radius & Shadows

### 5.1 Border Radius

| Element | Class | Value |
|---------|-------|-------|
| Inputs, small buttons | `rounded-md` | 6px |
| Cards, modals, large buttons | `rounded-lg` | 8px |
| Sheets, major containers | `rounded-xl` | 12px |
| Avatars, pills, tags | `rounded-full` | — |

> Slightly more rounded than Asana's 3px — feels more modern and less corporate. Never use `rounded-2xl` or greater except on decorative elements.

### 5.2 Shadows

Four tiers, all subtle:

| Tier | Class | Usage |
|------|-------|-------|
| **Flat** | none | Default card resting state |
| **Subtle** | `shadow-sm` | Hovered card, dropdown trigger |
| **Elevated** | `shadow-md` | Popovers, menus, dropdowns |
| **Modal** | `shadow-xl` | Dialogs, command palette |

**Rule:** never combine a border AND a shadow on the same element. Pick one. Borders imply equal-weight siblings; shadows imply floating.

### 5.3 Focus Rings

Every interactive element uses the same focus ring — consistency beats cleverness:

```html
focus-visible:outline-none
focus-visible:ring-2
focus-visible:ring-brand-500
focus-visible:ring-offset-2
focus-visible:ring-offset-white
```

---

## 6. Components

### 6.1 Button

Four variants. All share: `inline-flex items-center gap-2 font-medium rounded-md transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed`.

| Variant | Base | Hover | Usage |
|---------|------|-------|-------|
| **Primary** | `bg-brand-500 text-white` | `hover:bg-brand-600` | Main CTA (one per screen) |
| **Secondary** | `bg-white text-slate-900 border border-slate-300` | `hover:bg-slate-50 hover:border-slate-400` | Alternative actions, cancel |
| **Ghost** | `text-slate-700` | `hover:bg-slate-100` | Toolbar buttons, icon triggers |
| **Danger** | `bg-rose-600 text-white` | `hover:bg-rose-700` | Delete, disconnect, destructive |

Sizes: `sm` (`h-8 px-3 text-xs`), `md` default (`h-10 px-4 text-sm`), `lg` (`h-12 px-6 text-base`).

**Rule:** one primary button per screen. Every additional action is secondary or ghost.

### 6.2 Input

```html
<input class="
  w-full rounded-md border border-slate-300 bg-white
  px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
  focus-visible:border-brand-500
  disabled:bg-slate-50 disabled:text-slate-500
" />
```

**Label pattern** (stacked, never inline except checkboxes):
```html
<div class="space-y-1.5">
  <label class="text-sm font-medium text-slate-700">Workspace name</label>
  <input ... />
  <p class="text-xs text-slate-500">This appears in Slack and on your dashboard.</p>
</div>
```

**Error state:**
```html
<input class="... border-rose-500 focus-visible:ring-rose-500" />
<p class="text-xs text-rose-600 mt-1">Workspace name is required.</p>
```

**Masked secrets (API keys)**: use `type="password"` with a toggle icon-button on the right. Never show full keys after initial input — charter rule.

### 6.3 Card

```html
<div class="rounded-lg border border-slate-200 bg-white p-6">
  <!-- optional header -->
  <div class="mb-4 flex items-center justify-between">
    <h3 class="text-lg font-semibold text-slate-900">Slack Integration</h3>
    <StatusBadge variant="success">Connected</StatusBadge>
  </div>
  <!-- body -->
  <p class="text-sm text-slate-600">Connected to <span class="font-mono">workspace.slack.com</span></p>
</div>
```

**Interactive card** (clickable workspace tile):
```html
<button class="
  group rounded-lg border border-slate-200 bg-white p-6 text-left
  transition-all duration-150
  hover:border-slate-300 hover:shadow-sm
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500
">
  ...
</button>
```

### 6.4 Modal / Dialog

Use a headless modal library (Radix Dialog recommended) with these styles:

```html
<!-- Overlay -->
<div class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm" />

<!-- Content -->
<div class="
  fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
  w-full max-w-md rounded-xl bg-white p-6 shadow-xl
">
  <h2 class="text-lg font-semibold text-slate-900">Disconnect Google Drive?</h2>
  <p class="mt-2 text-sm text-slate-600">Your indexed files will be removed.</p>
  <div class="mt-6 flex justify-end gap-3">
    <button class="... secondary">Cancel</button>
    <button class="... danger">Disconnect</button>
  </div>
</div>
```

### 6.5 Toast / Notification

Use `sonner` (already in stack per new_app Context Pack).

```tsx
toast.success('API key validated', { description: 'Your OpenAI key is ready to use.' });
toast.error('Upload failed', { description: 'File must be a supported type.' });
```

Toasts appear bottom-right, auto-dismiss after 4s, stack vertically.

### 6.6 Badge / Status Pill

```html
<span class="
  inline-flex items-center gap-1.5 rounded-full
  bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700
">
  <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
  Connected
</span>
```

Variants: `success` (emerald), `warning` (amber), `danger` (rose), `info` (sky), `neutral` (slate).

### 6.7 Empty State

Used for: no workspaces, no files. (Skills have no dashboard presence — they're created via agent chat in Slack per ADR-023.)

```html
<div class="rounded-lg border-2 border-dashed border-slate-200 bg-slate-50 p-12 text-center">
  <Icon name="folder-open" class="mx-auto h-12 w-12 text-slate-400" />
  <h3 class="mt-4 text-base font-semibold text-slate-900">No files indexed yet</h3>
  <p class="mt-1 text-sm text-slate-500 max-w-sm mx-auto">
    Add up to 15 files from your Google Drive. Tee-Mo will scan each one to understand its contents.
  </p>
  <button class="mt-6 primary">Add from Drive</button>
</div>
```

### 6.8 Skeleton Loader

While fetching, show skeleton bars that match the target layout:

```html
<div class="animate-pulse space-y-3">
  <div class="h-4 w-1/3 rounded bg-slate-200"></div>
  <div class="h-4 w-2/3 rounded bg-slate-200"></div>
</div>
```

---

## 7. Motion & Transitions

| Purpose | Duration | Easing | Example |
|---------|----------|--------|---------|
| Hover color swap | 150ms | `ease-out` | Button background |
| Focus ring appear | 100ms | `ease-out` | Input focus |
| Modal enter | 200ms | `ease-out` | Fade + scale from 95% |
| Modal exit | 150ms | `ease-in` | Fade + scale to 95% |
| Toast slide | 250ms | `ease-out` | From bottom-right |
| Page transitions | none | — | Instant — no page-level animations |

**Forbidden:** spring animations, bounce, rotation, scale > 1.05, anything over 300ms.

Tailwind classes:
```
transition-colors duration-150 ease-out
transition-all duration-200 ease-out
```

---

## 8. Iconography

**Library:** Lucide React (`lucide-react`).

```bash
npm install lucide-react
```

**Sizes:**
- Inline with text: `h-4 w-4` (16px)
- Button icons: `h-5 w-5` (20px)
- Section headers: `h-6 w-6` (24px)
- Empty state illustrations: `h-12 w-12` (48px)

**Color:** inherit from parent text color via `text-current`. Never hard-code icon colors.

**Weight:** Lucide defaults to 1.5px stroke — keep it. Never use `stroke-width="2"` globally.

---

## 9. Key Screens — Layout Specs

### 9.1 Auth (Login / Register)

```
┌────────────────────────────────────────┐
│                                        │
│               [Tee-Mo Logo]            │
│                                        │
│          Sign in to Tee-Mo             │   <- text-2xl font-semibold
│   Connect your Slack workspace and     │   <- text-sm text-slate-500
│         your own AI provider.          │
│                                        │
│   ┌──────────────────────────────────┐ │
│   │ Email                            │ │
│   │ [________________________]       │ │
│   │                                  │ │
│   │ Password                         │ │
│   │ [________________________]       │ │
│   │                                  │ │
│   │ [      Sign in       ]           │ │   <- primary, full width
│   │                                  │ │
│   │ New to Tee-Mo? Create account    │ │   <- ghost link
│   └──────────────────────────────────┘ │
│                                        │
└────────────────────────────────────────┘
```

- Card max-width: `max-w-md` (448px)
- Vertically centered with `min-h-screen flex items-center justify-center bg-slate-50`
- Logo: 40px tall, coral wordmark
- No images, no illustrations — ruthlessly minimal

### 9.2 Workspace List (Dashboard Home)

```
┌──────────────────────────────────────────────────────────┐
│ [Tee-Mo]  Workspaces                           [Avatar]  │   <- top nav
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Your Workspaces                       [+ New Workspace] │   <- text-2xl + primary button
│                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Acme Corp   │  │ Side Project│  │ Personal    │       │   <- interactive cards
│  │ slack.acme  │  │ slack.side  │  │ slack.pers  │       │
│  │             │  │             │  │             │       │
│  │ • 8 files   │  │ • 2 files   │  │ • 0 files   │       │
│  │ • Connected │  │ • Setup...  │  │ • Setup...  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

- Grid: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6`
- Each card shows workspace name, slack domain, file count, setup status badge

### 9.3 Workspace Setup Wizard

4-step linear flow (per Charter §5.3). Each step is a dedicated screen with a progress indicator:

```
┌──────────────────────────────────────────────────────────┐
│  Setup: Acme Corp                                        │
│                                                          │
│  [●]───[○]───[○]───[○]    1 of 4: Slack                  │   <- step indicator
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │                                                    │  │
│  │  Connect Slack                                     │  │
│  │  Install Tee-Mo into your Slack workspace.         │  │
│  │                                                    │  │
│  │  [   Install to Slack   ]                          │  │   <- primary
│  │                                                    │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│                        [Back]  [Next: Connect Drive →]   │
└──────────────────────────────────────────────────────────┘
```

- Wizard card: `max-w-2xl mx-auto`
- Step indicator: row of 4 circles, active = brand-500, inactive = slate-300
- Nav footer: sticky or at card bottom, secondary button left + primary right

### 9.4 Workspace Detail (Files Tab)

```
┌──────────────────────────────────────────────────────────┐
│ [< Back to workspaces]                                   │
│                                                          │
│  Acme Corp                          [Settings]  [● Conn] │
│  slack.acme.com                                          │
│                                                          │
│  ┌─── Files ──────── Integrations ─────────────────────┐  │   <- tab bar
│  │                                                    │  │
│  │  Knowledge Base (8/15)            [+ Add File]     │  │
│  │                                                    │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │ 📄 Q1 Budget                                 │  │  │
│  │  │    AI: Q1 2026 marketing spend by channel... │  │  │
│  │  │    [Rescan]  [Remove]                        │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │ 📊 Sales Pipeline                            │  │  │
│  │  │    AI: Active deals with stage, owner, ...   │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

- File row: icon + title + italic AI description + action ghost buttons on hover
- File count badge in header shows current/max

### 9.5 Empty BYOK Gate

When user tries to add a file without BYOK configured:

```
┌────────────────────────────────────────┐
│  🔒 Configure your AI provider first   │
│                                        │
│  Tee-Mo needs your API key to scan     │
│  files. Your key stays encrypted and   │
│  never leaves your workspace.          │
│                                        │
│  [  Configure API Key →  ]             │
└────────────────────────────────────────┘
```

Inline empty state, not a modal. Replaces the "Add File" action area.

---

## 10. Accessibility

- **Contrast:** all text meets WCAG AA (4.5:1 for body, 3:1 for large). The neutrals above are pre-validated.
- **Focus:** every interactive element has a visible focus ring (see §5.3). Never `outline: none` without a replacement.
- **Keyboard:** Tab order follows visual order. Modals trap focus. Escape closes.
- **Semantics:** use `<button>` for actions, `<a>` for navigation, `<label>` + `htmlFor` for every input.
- **Screen readers:** every icon-only button has `aria-label`. Status changes (toasts, validation) use `aria-live="polite"`.

---

## 11. Implementation Notes

### 11.1 Tailwind 4 Setup

Tailwind 4 uses CSS-first config via `@theme`:

```css
/* app.css */
@import "tailwindcss";

@theme {
  --color-brand-50: #FFF1F2;
  --color-brand-100: #FFE4E6;
  --color-brand-500: #F43F5E;
  --color-brand-600: #E11D48;
  --color-brand-700: #BE123C;

  --font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}
```

Then use as `bg-brand-500`, `text-brand-600` everywhere — no config file needed.

### 11.2 Component File Structure

```
frontend/src/components/
├── ui/                    # primitives
│   ├── Button.tsx
│   ├── Input.tsx
│   ├── Card.tsx
│   ├── Badge.tsx
│   ├── Modal.tsx
│   └── Skeleton.tsx
├── auth/                  # copy from new_app (strip Google OAuth)
├── workspace/
│   ├── WorkspaceCard.tsx
│   ├── WorkspaceList.tsx
│   └── SetupWizard/
│       ├── StepSlack.tsx
│       ├── StepDrive.tsx
│       ├── StepBYOK.tsx
│       └── StepFiles.tsx
└── files/
    ├── FileList.tsx
    ├── FileRow.tsx
    └── FilePicker.tsx
# Note: no skills/ directory — skills have no dashboard UI (ADR-023, chat-only CRUD).
```

### 11.3 What NOT to Pull In

To keep the bundle small and the aesthetic clean:

- ❌ shadcn/ui — too big, too opinionated, costs hours to theme
- ❌ Material UI — anti-Asana aesthetic
- ❌ Chakra UI — too many wrapper components
- ❌ Styled Components / Emotion — Tailwind is the source of truth
- ❌ Framer Motion — over-spec for our sub-200ms transitions; CSS handles it
- ✅ Radix UI primitives (Dialog, Dropdown, Tooltip) — headless, unstyled, accessible. Wire into our Tailwind classes.
- ✅ Lucide React — icons
- ✅ sonner — toasts (already in new_app stack)
- ✅ `@fontsource/inter` — font loading

### 11.4 Demo Polish Checklist

Before the hackathon demo (Sprint 16), verify:

- [ ] All buttons have `transition-colors duration-150`
- [ ] All inputs have consistent focus rings
- [ ] No layout shift when loading (skeletons in place)
- [ ] Empty states exist for every list (workspaces, files, skills)
- [ ] Every error has a user-friendly message, no raw `500 Internal Server Error`
- [ ] Logo appears on every page (top-left)
- [ ] Typography renders with `font-feature-settings` enabled (Inter alternates)
- [ ] Favicon set
- [ ] Page title tag set per route

---

## 12. Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | Initial design guide created. Asana-inspired warm minimalism. Coral brand, slate neutrals, Inter typography, Tailwind 4 CSS-first config, Lucide icons. Covers all Tee-Mo v1 screens. | Claude (doc-manager) |
| 2026-04-11 | Removed Skills nav tab, Skills detail tab, and `skills/` component directory per ADR-023 — skill CRUD is chat-only, no dashboard UI. Empty state list updated to remove Skills reference. | Claude (doc-manager) |
