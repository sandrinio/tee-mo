import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { TanStackRouterVite } from '@tanstack/router-plugin/vite';

/**
 * Vite configuration for Tee-Mo frontend.
 *
 * Plugins:
 *   - TanStackRouterVite: generates routeTree.gen.ts from src/routes/ (must come before react)
 *   - react: React 19 JSX transform + Fast Refresh
 *   - tailwindcss: Tailwind v4 CSS-first pipeline via @tailwindcss/vite (no postcss config needed)
 *
 * Server port 5173 is the agreed frontend port per sprint-context-S-01.
 */
export default defineConfig({
  plugins: [TanStackRouterVite(), react(), tailwindcss()],
  server: { port: 5173 },
});
