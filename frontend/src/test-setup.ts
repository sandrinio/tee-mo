/**
 * test-setup.ts — Global test setup for Vitest component tests.
 *
 * Extends Vitest's `expect` with @testing-library/jest-dom matchers so that
 * assertions like `toBeInTheDocument()`, `toBeVisible()`, etc. are available
 * in all test files without per-file imports.
 *
 * Referenced in vite.config.ts `test.setupFiles`.
 */
import '@testing-library/jest-dom';
