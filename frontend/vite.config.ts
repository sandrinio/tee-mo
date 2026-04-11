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
 *
 * Dev proxy (STORY-003-01): routes /api/* from the Vite dev server (5173) to the
 * local FastAPI backend (8000). This preserves the S-02 dev workflow now that
 * api.ts defaults to same-origin (empty string) rather than http://localhost:8000.
 */
export default defineConfig({
  plugins: [TanStackRouterVite(), react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
