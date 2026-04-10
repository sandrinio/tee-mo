# Tee-Mo Frontend

React 19 + Vite 5 + Tailwind 4 dashboard for the Tee-Mo BYOK Slack assistant.

## Quick Start

```bash
npm install
npm run dev
```

Dev server starts at **http://localhost:5173**.

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite dev server with HMR |
| `npm run build` | Type-check + production build to `dist/` |
| `npm run preview` | Preview the production build locally |
| `npm run typecheck` | TypeScript check without emit |

## Stack

- **React 19** — UI with new compiler, Actions, and `use()` hook
- **Tailwind CSS 4** — CSS-first design tokens via `src/app.css` `@theme` block (no config file)
- **TanStack Router** — file-based type-safe routing under `src/routes/`
- **Inter + JetBrains Mono** — loaded via `@fontsource/*` (no Google Fonts CDN)
- **Lucide React** — icon library

## Design Tokens

All tokens live in `src/app.css` under `@theme`. See `product_plans/strategy/tee_mo_design_guide.md` for the full design system specification.
