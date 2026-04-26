/**
 * KnowledgeModules.test.tsx — 4 Vitest scenarios for STORY-025-03.
 *
 * One test per Gherkin scenario:
 *   1. Header strip renders count + actions
 *   2. Divider list renders rows without per-row cards
 *   3. Remove button hover-reveals
 *   4. Existing add/upload behavior preserved
 *
 * Strategy:
 *   - All hooks mocked via vi.mock (hoisted above imports).
 *   - Mock variables wrapped in vi.hoisted() to avoid TDZ errors (Vitest 2.x).
 *   - QueryClientProvider mounted per-test to satisfy TanStack Query.
 *   - Google Picker API globals stubbed on window for Scenario 4.
 *   - No real network calls.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// ---------------------------------------------------------------------------
// Hoisted mock variables
// ---------------------------------------------------------------------------

const {
  mockUseKnowledgeQuery,
  mockUseAddKnowledgeMutation,
  mockUseRemoveKnowledgeMutation,
  mockUseReindexKnowledgeMutation,
  mockUseUploadKnowledgeMutation,
  mockGetPickerToken,
} = vi.hoisted(() => ({
  mockUseKnowledgeQuery: vi.fn(),
  mockUseAddKnowledgeMutation: vi.fn(),
  mockUseRemoveKnowledgeMutation: vi.fn(),
  mockUseReindexKnowledgeMutation: vi.fn(),
  mockUseUploadKnowledgeMutation: vi.fn(),
  mockGetPickerToken: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Module mocks
// ---------------------------------------------------------------------------

vi.mock('../../../hooks/useKnowledge', () => ({
  useKnowledgeQuery: mockUseKnowledgeQuery,
  useAddKnowledgeMutation: mockUseAddKnowledgeMutation,
  useRemoveKnowledgeMutation: mockUseRemoveKnowledgeMutation,
  useReindexKnowledgeMutation: mockUseReindexKnowledgeMutation,
  useUploadKnowledgeMutation: mockUseUploadKnowledgeMutation,
}));

vi.mock('../../../lib/api', () => ({
  getPickerToken: mockGetPickerToken,
}));

// ---------------------------------------------------------------------------
// Import component after mocks are registered
// ---------------------------------------------------------------------------

import { FilesSection } from '../FilesSection';
import type { KnowledgeFile } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeFile(overrides: Partial<KnowledgeFile> = {}): KnowledgeFile {
  return {
    id: `file-${Math.random().toString(36).slice(2)}`,
    workspace_id: 'ws-001',
    title: 'Test Document',
    source: 'google_drive',
    doc_type: 'google_doc',
    external_id: 'gdrive-id-1',
    external_link: 'https://docs.google.com/doc/1',
    ai_description: 'A test document AI description.',
    content_hash: null,
    created_at: '2026-01-01T00:00:00Z',
    last_scanned_at: null,
    ...overrides,
  };
}

function idleMutation(overrides?: Record<string, unknown>) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
    ...overrides,
  };
}

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeClient()}>{children}</QueryClientProvider>;
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Default idle hook stubs
  mockUseKnowledgeQuery.mockReturnValue({ data: [], isLoading: false, isError: false });
  mockUseAddKnowledgeMutation.mockReturnValue(idleMutation());
  mockUseRemoveKnowledgeMutation.mockReturnValue(idleMutation());
  mockUseReindexKnowledgeMutation.mockReturnValue(idleMutation());
  mockUseUploadKnowledgeMutation.mockReturnValue(idleMutation());
});

afterEach(() => {
  vi.clearAllMocks();
  // Clean up any google/gapi globals added per test
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).gapi;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (window as any).google;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('STORY-025-03 knowledge modules', () => {

  // -------------------------------------------------------------------------
  // Scenario 1: Header strip renders count + actions
  // -------------------------------------------------------------------------

  it('Header strip renders count + actions', () => {
    const files = Array.from({ length: 12 }, (_, i) =>
      makeFile({ id: `f-${i}`, title: `File ${i}` }),
    );
    mockUseKnowledgeQuery.mockReturnValue({ data: files, isLoading: false, isError: false });

    render(
      <Wrapper>
        <FilesSection workspaceId="ws-001" driveConnected={true} hasKey={true} />
      </Wrapper>,
    );

    // Count text
    expect(screen.getByText('12 of 100 files indexed')).toBeInTheDocument();

    // "Add file" primary button
    expect(screen.getByRole('button', { name: /add file/i })).toBeInTheDocument();

    // "Upload" secondary button
    expect(screen.getByRole('button', { name: /^upload$/i })).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Scenario 2: Divider list renders rows without per-row cards
  // -------------------------------------------------------------------------

  it('Divider list renders rows without per-row cards', () => {
    const files = [
      makeFile({ id: 'f1', title: 'Alpha' }),
      makeFile({ id: 'f2', title: 'Beta' }),
      makeFile({ id: 'f3', title: 'Gamma' }),
    ];
    mockUseKnowledgeQuery.mockReturnValue({ data: files, isLoading: false, isError: false });

    const { container } = render(
      <Wrapper>
        <FilesSection workspaceId="ws-001" driveConnected={true} hasKey={true} />
      </Wrapper>,
    );

    // 3 <li> rows inside .divide-y container
    const rows = container.querySelectorAll('.divide-y > li');
    expect(rows.length).toBe(3);

    // All three file titles are visible
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('Gamma')).toBeInTheDocument();

    // No per-row Card border class — individual rows should NOT be wrapped in
    // a bordered card (W01 §5.7 divider-list pattern: no per-row Card).
    // Rows are <li> elements, not Card components with rounded-lg border.
    rows.forEach((row) => {
      expect(row.className).not.toMatch(/rounded-lg border/);
    });
  });

  // -------------------------------------------------------------------------
  // Scenario 3: Remove button hover-reveals
  // -------------------------------------------------------------------------

  it('Remove button hover-reveals', () => {
    const files = [makeFile({ id: 'f1', title: 'Test File' })];
    mockUseKnowledgeQuery.mockReturnValue({ data: files, isLoading: false, isError: false });

    render(
      <Wrapper>
        <FilesSection workspaceId="ws-001" driveConnected={true} hasKey={true} />
      </Wrapper>,
    );

    // Remove button should exist (aria-label set to "Remove {title}")
    const removeButton = screen.getByRole('button', { name: /remove test file/i });

    // Remove button has opacity-0 class (hidden by default)
    expect(removeButton.className).toMatch(/opacity-0/);

    // Remove button has group-hover:opacity-100 class (hover-reveal pattern W01 §5.7)
    // In jsdom, CSS hover-reveal is not functional but the class string must be present.
    expect(removeButton.className).toMatch(/group-hover:opacity-100/);

    // transition-opacity duration-150 also present (per W01 §5.7 frozen markup)
    expect(removeButton.className).toMatch(/transition-opacity/);
  });

  // -------------------------------------------------------------------------
  // Scenario 4: Existing add/upload behavior preserved
  // -------------------------------------------------------------------------

  it('Existing add/upload behavior preserved', async () => {
    // Stub Google Picker API globals
    const mockSetVisible = vi.fn();
    const mockPickerBuild = vi.fn().mockReturnValue({ setVisible: mockSetVisible });
    const mockAddView = vi.fn().mockReturnThis();
    const mockSetCallback = vi.fn().mockReturnThis();
    const mockSetOAuthToken = vi.fn().mockReturnThis();
    const mockSetDeveloperKey = vi.fn().mockReturnThis();

    const MockPickerBuilder = vi.fn().mockImplementation(() => ({
      setOAuthToken: mockSetOAuthToken,
      setDeveloperKey: mockSetDeveloperKey,
      addView: mockAddView,
      setCallback: mockSetCallback,
      build: mockPickerBuild,
    }));

    const mockDocsViewInstance = {
      setMimeTypes: vi.fn().mockReturnThis(),
    };
    const MockDocsView = vi.fn().mockImplementation(() => mockDocsViewInstance);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).gapi = {
      load: vi.fn((module: string, cb: () => void) => {
        cb();
      }),
    };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).google = {
      picker: {
        PickerBuilder: MockPickerBuilder,
        DocsView: MockDocsView,
        ViewId: { DOCS: 'DOCS' },
        Action: { PICKED: 'picked' },
      },
    };

    mockGetPickerToken.mockResolvedValue({
      access_token: 'test-access-token',
      picker_api_key: 'test-api-key',
    });

    const mockUploadMutate = vi.fn();
    mockUseUploadKnowledgeMutation.mockReturnValue(
      idleMutation({ mutate: mockUploadMutate }),
    );

    // Start with 0 files (empty state — no Re-index button shown)
    mockUseKnowledgeQuery.mockReturnValue({ data: [], isLoading: false, isError: false });

    render(
      <Wrapper>
        <FilesSection workspaceId="ws-001" driveConnected={true} hasKey={true} />
      </Wrapper>,
    );

    // --- Add file (picker) flow ---
    const addButton = screen.getByRole('button', { name: /add file/i });
    fireEvent.click(addButton);

    // Wait for the full async picker chain to complete:
    // getPickerToken → loadGapiScript → gapi.load → PickerBuilder → setVisible
    await vi.waitFor(() => {
      // gapi.load was called to open picker
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((window as any).gapi.load).toHaveBeenCalledWith('picker', expect.any(Function));
    });

    // getPickerToken was invoked with the workspaceId
    expect(mockGetPickerToken).toHaveBeenCalledWith('ws-001');

    // PickerBuilder was constructed (verifies gapi.load callback ran)
    expect(MockPickerBuilder).toHaveBeenCalled();

    // picker.setVisible(true) was called
    expect(mockSetVisible).toHaveBeenCalledWith(true);

    // --- Upload flow ---
    const uploadButton = screen.getByRole('button', { name: /^upload$/i });
    expect(uploadButton).toBeInTheDocument();

    // Find the hidden file input and simulate file selection
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
    expect(fileInput).toBeInTheDocument();

    const testFile = new File(['pdf content'], 'test.pdf', { type: 'application/pdf' });
    fireEvent.change(fileInput, { target: { files: [testFile] } });

    // useUploadKnowledgeMutation.mutate should have been called once
    expect(mockUploadMutate).toHaveBeenCalledTimes(1);
    expect(mockUploadMutate).toHaveBeenCalledWith(testFile);
  });
});
