/**
 * KeySection.test.tsx — Unit tests for the extracted KeySection component (STORY-008-01 R1).
 *
 * RED PHASE: Tests are written to describe the expected behavior of the standalone
 * KeySection component that will be extracted from WorkspaceCard.tsx. These tests
 * WILL FAIL until the implementation is complete (GREEN phase).
 *
 * The KeySection component will live at:
 *   frontend/src/components/workspace/KeySection.tsx
 *
 * Mocking strategy:
 *   - vi.mock hoists the factory above imports (Vitest 2.x TDZ rule from FLASHCARDS.md).
 *   - Mock functions created directly in the factory (no closures) so vi.hoisted() is not needed.
 *   - Each test creates a fresh QueryClient to prevent cross-test cache pollution.
 *
 * Test coverage:
 *   1. Render: collapsed with no key — shows warning and "+ Add key" button
 *   2. Render: collapsed with key configured — shows provider badge and masked key
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mock hook dependencies
// All vi.mock factories run before imports — no vi.hoisted() needed here since
// mock functions are created inline (no closure over outer variables).
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useKey', () => ({
  useKeyQuery: vi.fn(),
  useSaveKeyMutation: vi.fn(),
  useDeleteKeyMutation: vi.fn(),
}));

vi.mock('../../../lib/api', () => ({
  validateKey: vi.fn(),
}));

import * as useKeyModule from '../../../hooks/useKey';
import { KeySection } from '../KeySection';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Creates a fresh QueryClient + Provider wrapper per test. */
function makeWrapper(queryClient: QueryClient) {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

/** Returns a minimal idle mutation stub (not pending, no error). */
function idleMutation() {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('KeySection', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default stubs for mutations — override in individual tests when needed.
    vi.mocked(useKeyModule.useSaveKeyMutation).mockReturnValue(idleMutation() as ReturnType<typeof useKeyModule.useSaveKeyMutation>);
    vi.mocked(useKeyModule.useDeleteKeyMutation).mockReturnValue(idleMutation() as ReturnType<typeof useKeyModule.useDeleteKeyMutation>);
  });

  describe('collapsed state — no key configured', () => {
    it('shows warning message when no key is configured', () => {
      // Arrange: query returns no key
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: { has_key: false, provider: null, key_mask: null, ai_model: null },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-123" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: no-key warning label is shown
      expect(screen.getByTestId('no-key-label')).toBeInTheDocument();
    });

    it('shows "+ Add key" button when no key is configured', () => {
      // Arrange: query returns no key
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: { has_key: false, provider: null, key_mask: null, ai_model: null },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-123" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: add-key button is present
      expect(screen.getByTestId('add-key-button')).toBeInTheDocument();
      expect(screen.getByTestId('add-key-button')).toHaveTextContent('+ Add key');
    });

    it('does not show a provider badge or masked key when no key configured', () => {
      // Arrange
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: { has_key: false, provider: null, key_mask: null, ai_model: null },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-123" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: masked key element is absent
      expect(screen.queryByTestId('key-mask')).not.toBeInTheDocument();
    });
  });

  describe('collapsed state — key configured', () => {
    it('shows the provider badge when a key is configured', () => {
      // Arrange: query returns a configured OpenAI key
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: {
          has_key: true,
          provider: 'openai',
          key_mask: 'sk-a...xyz9',
          ai_model: 'gpt-4o',
        },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-456" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: human-readable provider label shown (OpenAI)
      expect(screen.getByText('OpenAI')).toBeInTheDocument();
    });

    it('shows the masked key when a key is configured', () => {
      // Arrange
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: {
          has_key: true,
          provider: 'openai',
          key_mask: 'sk-a...xyz9',
          ai_model: 'gpt-4o',
        },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-456" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: masked key displayed
      const keyMask = screen.getByTestId('key-mask');
      expect(keyMask).toBeInTheDocument();
      expect(keyMask).toHaveTextContent('sk-a...xyz9');
    });

    it('shows Update and Delete controls when a key is configured', () => {
      // Arrange
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: {
          has_key: true,
          provider: 'anthropic',
          key_mask: 'sk-ant...abc',
          ai_model: null,
        },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-456" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: both action buttons present
      expect(screen.getByText('Update')).toBeInTheDocument();
      expect(screen.getByText('Delete')).toBeInTheDocument();
    });

    it('does not show the no-key warning when a key is configured', () => {
      // Arrange
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: {
          has_key: true,
          provider: 'google',
          key_mask: 'AIza...def',
          ai_model: null,
        },
        isLoading: false,
        isSuccess: true,
        isError: false,
        error: null,
        status: 'success',
        fetchStatus: 'idle',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-456" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: no-key warning absent
      expect(screen.queryByTestId('no-key-label')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('renders a skeleton loader while key data is loading', () => {
      // Arrange
      vi.mocked(useKeyModule.useKeyQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isSuccess: false,
        isError: false,
        error: null,
        status: 'pending',
        fetchStatus: 'fetching',
      } as ReturnType<typeof useKeyModule.useKeyQuery>);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Act
      const { container } = render(
        <QueryClientProvider client={queryClient}>
          <KeySection workspaceId="ws-789" teamId="T-TEAM1" />
        </QueryClientProvider>,
      );

      // Assert: skeleton pulse div present, no interactive controls shown
      expect(container.querySelector('.animate-pulse')).toBeInTheDocument();
      expect(screen.queryByTestId('add-key-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('key-mask')).not.toBeInTheDocument();
    });
  });
});
