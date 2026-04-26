/**
 * AddMcpServerModal.test.tsx — unit tests for the AddMcpServerModal component.
 *
 * Covers STORY-012-04 §4.1 Modal tests (4+) and §2.1 Gherkin scenarios:
 *   - Slug regex client-side rejection
 *   - Submit posts right body with single header
 *   - Submit posts with multiple headers
 *   - Submit posts with zero headers
 *   - SSE radio → transport:"sse" in POST body
 *   - Import Shape A populates form fields
 *   - Import rejects stdio config
 *   - Import strips placeholder header values
 *   - After import, form edits override imported state
 *
 * FLASHCARD 2026-04-11 #vitest: vi.mock vars in vi.hoisted() to avoid TDZ.
 * FLASHCARD 2026-04-12 #vitest #frontend: jsdom lacks HTMLDialogElement; use div overlay.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { AddMcpServerModal } from '../AddMcpServerModal';
import type { McpTransport } from '../../../lib/api';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface CreateBody {
  name: string;
  transport: McpTransport;
  url: string;
  headers: Record<string, string>;
}

function renderModal(overrides?: Partial<{
  onCreate: (body: CreateBody) => Promise<void>;
  isPending: boolean;
  serverError: string | null;
}>) {
  const onCreate = overrides?.onCreate ?? vi.fn().mockResolvedValue(undefined);
  const onClose = vi.fn();
  render(
    <AddMcpServerModal
      workspaceId="ws-001"
      onClose={onClose}
      onCreate={onCreate}
      isPending={overrides?.isPending ?? false}
      serverError={overrides?.serverError ?? null}
    />,
  );
  return { onCreate, onClose };
}

function fillBasicForm(name = 'github', url = 'https://api.githubcopilot.com/mcp/') {
  fireEvent.change(screen.getByTestId('mcp-name-input'), { target: { value: name } });
  fireEvent.change(screen.getByTestId('mcp-url-input'), { target: { value: url } });
}

// ---------------------------------------------------------------------------
// Slug validation
// ---------------------------------------------------------------------------

describe('Slug regex client-side rejection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('disables Submit and shows inline error for invalid name', () => {
    renderModal();
    // Type invalid name
    fireEvent.change(screen.getByTestId('mcp-name-input'), {
      target: { value: 'My GitHub!' },
    });
    // Fill valid URL so only name is blocking
    fireEvent.change(screen.getByTestId('mcp-url-input'), {
      target: { value: 'https://example.com/mcp' },
    });

    const submitBtn = screen.getByTestId('submit-button');
    expect(submitBtn).toBeDisabled();
    // Inline error hint visible
    expect(screen.getByTestId('name-error')).toBeInTheDocument();
  });

  it('enables Submit when name and URL are valid', () => {
    renderModal();
    fillBasicForm();
    expect(screen.getByTestId('submit-button')).not.toBeDisabled();
  });

  it('disables Submit when URL does not start with https://', () => {
    renderModal();
    fireEvent.change(screen.getByTestId('mcp-name-input'), { target: { value: 'github' } });
    fireEvent.change(screen.getByTestId('mcp-url-input'), {
      target: { value: 'http://insecure.example' },
    });
    expect(screen.getByTestId('submit-button')).toBeDisabled();
    expect(screen.getByTestId('url-error')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Submit body shape
// ---------------------------------------------------------------------------

describe('Submit POST body shape', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts correct body with single Authorization header', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AddMcpServerModal
        workspaceId="ws-001"
        onClose={vi.fn()}
        onCreate={onCreate}
        isPending={false}
        serverError={null}
      />,
    );

    fillBasicForm('github', 'https://api.githubcopilot.com/mcp/');

    // Default header key is "Authorization" — fill value
    fireEvent.change(screen.getByTestId('header-value-0'), {
      target: { value: 'Bearer ghp_xxx' },
    });

    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith({
        name: 'github',
        transport: 'streamable_http',
        url: 'https://api.githubcopilot.com/mcp/',
        headers: { Authorization: 'Bearer ghp_xxx' },
      });
    });
  });

  it('posts body with multiple headers', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AddMcpServerModal
        workspaceId="ws-001"
        onClose={vi.fn()}
        onCreate={onCreate}
        isPending={false}
        serverError={null}
      />,
    );

    fillBasicForm();
    // Fill first header
    fireEvent.change(screen.getByTestId('header-key-0'), {
      target: { value: 'Authorization' },
    });
    fireEvent.change(screen.getByTestId('header-value-0'), {
      target: { value: 'Bearer tok' },
    });
    // Add second header
    fireEvent.click(screen.getByTestId('header-add-row'));
    fireEvent.change(screen.getByTestId('header-key-1'), {
      target: { value: 'X-API-Key' },
    });
    fireEvent.change(screen.getByTestId('header-value-1'), {
      target: { value: 'k_abc' },
    });

    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer tok',
            'X-API-Key': 'k_abc',
          }),
        }),
      );
    });
  });

  it('posts empty headers dict when all rows are removed', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AddMcpServerModal
        workspaceId="ws-001"
        onClose={vi.fn()}
        onCreate={onCreate}
        isPending={false}
        serverError={null}
      />,
    );

    fillBasicForm();
    // Remove the default Authorization row
    fireEvent.click(screen.getByTestId('header-remove-0'));

    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({ headers: {} }),
      );
    });
  });

  it('posts transport:"sse" when SSE radio is selected', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AddMcpServerModal
        workspaceId="ws-001"
        onClose={vi.fn()}
        onCreate={onCreate}
        isPending={false}
        serverError={null}
      />,
    );

    fillBasicForm('mysse', 'https://sse.example.com/events');
    fireEvent.click(screen.getByTestId('transport-sse'));

    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({ transport: 'sse' }),
      );
    });
  });
});

// ---------------------------------------------------------------------------
// Paste-from-another-client import
// ---------------------------------------------------------------------------

describe('Paste-from-another-client import', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function openImportPanel() {
    fireEvent.click(screen.getByTestId('import-panel-toggle'));
  }

  it('Shape A — populates form fields from Claude Desktop wrapper', async () => {
    renderModal();
    openImportPanel();

    const pasteJson = JSON.stringify({
      mcpServers: {
        github: {
          url: 'https://api.githubcopilot.com/mcp/',
          transport: 'streamable-http',
          headers: { Authorization: 'Bearer ghp_xxx' },
        },
      },
    });

    fireEvent.change(screen.getByTestId('import-textarea'), {
      target: { value: pasteJson },
    });
    fireEvent.click(screen.getByTestId('import-button'));

    await waitFor(() => {
      expect((screen.getByTestId('mcp-name-input') as HTMLInputElement).value).toBe('github');
      expect((screen.getByTestId('mcp-url-input') as HTMLInputElement).value).toBe(
        'https://api.githubcopilot.com/mcp/',
      );
      // Transport radio for streamable_http should be checked
      expect(
        (screen.getByTestId('transport-streamable') as HTMLInputElement).checked,
      ).toBe(true);
      // Header row populated
      expect((screen.getByTestId('header-key-0') as HTMLInputElement).value).toBe(
        'Authorization',
      );
    });
  });

  it('Shape B — VS Code mcp.json import maps type:"http" → Streamable HTTP', async () => {
    renderModal();
    openImportPanel();

    const pasteJson = JSON.stringify({
      servers: {
        ado: { url: 'https://mcp.dev.azure.com/myorg', type: 'http' },
      },
    });

    fireEvent.change(screen.getByTestId('import-textarea'), { target: { value: pasteJson } });
    fireEvent.click(screen.getByTestId('import-button'));

    await waitFor(() => {
      expect((screen.getByTestId('mcp-name-input') as HTMLInputElement).value).toBe('ado');
      expect(
        (screen.getByTestId('transport-streamable') as HTMLInputElement).checked,
      ).toBe(true);
    });
  });

  it('rejects stdio config with the literal error string', async () => {
    renderModal();
    openImportPanel();

    const pasteJson = JSON.stringify({ command: 'npx', args: ['-y', 'azure-devops-mcp'] });

    fireEvent.change(screen.getByTestId('import-textarea'), { target: { value: pasteJson } });
    fireEvent.click(screen.getByTestId('import-button'));

    await waitFor(() => {
      const err = screen.getByTestId('import-error');
      expect(err).toBeInTheDocument();
      expect(err.textContent).toContain('stdio server');
    });
  });

  it('strips ${env:...} placeholder values and leaves key intact', async () => {
    renderModal();
    openImportPanel();

    const pasteJson = JSON.stringify({
      url: 'https://example.com/mcp',
      headers: { Authorization: '${env:GITHUB_TOKEN}' },
    });

    fireEvent.change(screen.getByTestId('import-textarea'), { target: { value: pasteJson } });
    fireEvent.click(screen.getByTestId('import-button'));

    await waitFor(() => {
      expect((screen.getByTestId('header-key-0') as HTMLInputElement).value).toBe(
        'Authorization',
      );
      // Value cleared for placeholder
      expect((screen.getByTestId('header-value-0') as HTMLInputElement).value).toBe('');
    });
  });

  it('after import, form edits override imported state on submit', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(
      <AddMcpServerModal
        workspaceId="ws-001"
        onClose={vi.fn()}
        onCreate={onCreate}
        isPending={false}
        serverError={null}
      />,
    );
    openImportPanel();

    // Import 2 headers
    const pasteJson = JSON.stringify({
      url: 'https://example.com/mcp',
      headers: { 'Key-A': 'val-a', 'Key-B': 'val-b' },
    });
    fireEvent.change(screen.getByTestId('import-textarea'), { target: { value: pasteJson } });
    fireEvent.click(screen.getByTestId('import-button'));

    await waitFor(() => {
      expect(screen.getByTestId('header-key-0')).toBeInTheDocument();
    });

    // Add a 3rd header row
    fireEvent.click(screen.getByTestId('header-add-row'));
    fireEvent.change(screen.getByTestId('header-key-2'), { target: { value: 'Key-C' } });
    fireEvent.change(screen.getByTestId('header-value-2'), { target: { value: 'val-c' } });

    // Remove the first row
    fireEvent.click(screen.getByTestId('header-remove-0'));

    // Edit the new first row's value
    fireEvent.change(screen.getByTestId('header-value-0'), { target: { value: 'UPDATED' } });

    // Fill name + URL
    fireEvent.change(screen.getByTestId('mcp-name-input'), { target: { value: 'myserver' } });
    fireEvent.change(screen.getByTestId('mcp-url-input'), {
      target: { value: 'https://example.com/mcp' },
    });

    fireEvent.click(screen.getByTestId('submit-button'));

    await waitFor(() => {
      expect(onCreate).toHaveBeenCalledOnce();
      const body = onCreate.mock.calls[0][0] as CreateBody;
      // Key-A was removed; Key-B updated; Key-C added
      expect(body.headers).not.toHaveProperty('Key-A');
    });
  });
});
