/**
 * KeySection.test.tsx — unit tests for the KeySection inline component
 * embedded in WorkspaceCard (STORY-004-04).
 *
 * Strategy:
 *   - `useKeyQuery` is mocked via vi.mock so we can control its return value.
 *   - `useSaveKeyMutation` and `useDeleteKeyMutation` are mocked to provide
 *     stub mutation objects.
 *   - `validateKey` from lib/api is mocked to verify it is called correctly
 *     when the user clicks Validate.
 *
 * FLASHCARDS.md rule: mock variables referenced inside vi.mock factories
 * MUST be wrapped in vi.hoisted() to avoid TDZ errors (Vitest 2.x hoists
 * vi.mock() calls above const declarations).
 *
 * All tests wrap WorkspaceCard in a QueryClientProvider because the component
 * uses TanStack Query hooks that require the provider to be present.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WorkspaceCard } from '../WorkspaceCard';
import type { Workspace } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Hoisted mock variables (vi.hoisted prevents TDZ errors in Vitest 2.x)
// ---------------------------------------------------------------------------

const { mockUseKeyQuery, mockUseSaveKeyMutation, mockUseDeleteKeyMutation, mockValidateKey } =
  vi.hoisted(() => ({
    mockUseKeyQuery: vi.fn(),
    mockUseSaveKeyMutation: vi.fn(),
    mockUseDeleteKeyMutation: vi.fn(),
    mockValidateKey: vi.fn(),
  }));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useKey', () => ({
  useKeyQuery: mockUseKeyQuery,
  useSaveKeyMutation: mockUseSaveKeyMutation,
  useDeleteKeyMutation: mockUseDeleteKeyMutation,
}));

vi.mock('../../../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../lib/api')>();
  return {
    ...actual,
    validateKey: mockValidateKey,
  };
});

// useMakeDefaultMutation is used by WorkspaceCard — provide a stub so renders don't error
vi.mock('../../../hooks/useWorkspaces', () => ({
  useMakeDefaultMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    error: null,
  })),
}));

// RenameWorkspaceModal is a heavy component — stub it out for unit tests
vi.mock('../RenameWorkspaceModal', () => ({
  RenameWorkspaceModal: () => null,
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns a fresh QueryClient for each test to prevent cache bleed-over. */
function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/** Wraps children in a QueryClientProvider to satisfy TanStack Query hooks. */
function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;
}

/** Minimal workspace fixture used across tests. */
const workspace: Workspace = {
  id: 'ws-001',
  name: 'Test Workspace',
  slack_team_id: 'T-TEAM',
  owner_user_id: 'user-001',
  is_default_for_team: false,
  created_at: '2026-01-01T00:00:00Z',
};

/** Default no-op stubs for save/delete mutations — override per test if needed. */
const stubSaveMutation = { mutate: vi.fn(), isPending: false, error: null };
const stubDeleteMutation = { mutate: vi.fn(), isPending: false, error: null };

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('KeySection', () => {
  beforeEach(() => {
    mockUseSaveKeyMutation.mockReturnValue(stubSaveMutation);
    mockUseDeleteKeyMutation.mockReturnValue(stubDeleteMutation);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  /**
   * Scenario: Card shows "No key" state for unconfigured workspace.
   * Gherkin: Given useKeyQuery returns {has_key: false}, Then "No key configured" and "+ Add key" visible.
   */
  it('renders no-key state when has_key is false', () => {
    mockUseKeyQuery.mockReturnValue({
      data: { has_key: false, provider: null, key_mask: null, ai_model: null },
      isLoading: false,
    });

    render(
      <Wrapper>
        <WorkspaceCard workspace={workspace} teamId="T-TEAM" />
      </Wrapper>,
    );

    // "No key configured" label must be visible
    expect(screen.getByTestId('no-key-label')).toBeInTheDocument();

    // "+ Add key" button must be visible
    expect(screen.getByTestId('add-key-button')).toBeInTheDocument();
    expect(screen.getByTestId('add-key-button')).toHaveTextContent('+ Add key');
  });

  /**
   * Scenario: Card shows masked key for configured workspace.
   * Gherkin: Given useKeyQuery returns {has_key: true, provider: "openai", key_mask: "sk-a...xyz9"},
   *          Then masked key and "OpenAI" badge are visible.
   */
  it('renders masked key and provider badge when has_key is true', () => {
    mockUseKeyQuery.mockReturnValue({
      data: {
        has_key: true,
        provider: 'openai',
        key_mask: 'sk-a...xyz9',
        ai_model: 'gpt-4o',
      },
      isLoading: false,
    });

    render(
      <Wrapper>
        <WorkspaceCard workspace={workspace} teamId="T-TEAM" />
      </Wrapper>,
    );

    // Masked key text must be visible
    expect(screen.getByTestId('key-mask')).toHaveTextContent('sk-a...xyz9');

    // Provider badge — "OpenAI" label derived from PROVIDERS constant
    expect(screen.getByText('OpenAI')).toBeInTheDocument();

    // Update and Delete buttons must be present
    expect(screen.getByRole('button', { name: /update/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
  });

  /**
   * Scenario: Validate button calls validateKey API.
   * Gherkin: Given the key input form is expanded with provider="openai" key="sk-valid",
   *          When the user clicks Validate, Then POST /api/keys/validate is called.
   */
  it('validate button calls validateKey with provider and key', async () => {
    mockUseKeyQuery.mockReturnValue({
      data: { has_key: false, provider: null, key_mask: null, ai_model: null },
      isLoading: false,
    });
    mockValidateKey.mockResolvedValue({ valid: true, message: 'OK' });

    render(
      <Wrapper>
        <WorkspaceCard workspace={workspace} teamId="T-TEAM" />
      </Wrapper>,
    );

    // Open the add-key form
    fireEvent.click(screen.getByTestId('add-key-button'));

    // Type a key into the input
    fireEvent.change(screen.getByTestId('key-input'), {
      target: { value: 'sk-valid' },
    });

    // Click Validate
    fireEvent.click(screen.getByTestId('validate-button'));

    // validateKey must have been called with the correct arguments
    await waitFor(() => {
      expect(mockValidateKey).toHaveBeenCalledWith({
        provider: 'openai',
        key: 'sk-valid',
      });
    });
  });
});
