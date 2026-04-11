/**
 * vitest.config.ts — Vitest-specific configuration for the Tee-Mo frontend.
 *
 * Kept separate from vite.config.ts to avoid TypeScript type conflicts between
 * vitest@2.1.9 (which peers with vite@5.x) and the project's vite@8.0.8.
 * vitest picks up this file automatically when present.
 *
 * Environment strategy:
 *   - Default: jsdom — component tests in src/routes/__tests__/ need a DOM.
 *   - src/stores/** override: node — authStore tests are pure Zustand/fetch
 *     and don't need a browser environment.
 *
 * setupFiles loads @testing-library/jest-dom matchers so all test files can
 * use toBeInTheDocument(), toBeVisible(), etc. without per-file imports.
 *
 * globals: true is required for @testing-library/react's automatic afterEach
 * cleanup (which checks `typeof afterEach === 'function'` at module load time).
 */
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    environmentMatchGlobs: [
      ['src/stores/**', 'node'],
    ],
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
});
