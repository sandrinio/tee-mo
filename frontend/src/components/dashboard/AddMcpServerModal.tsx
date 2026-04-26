/**
 * AddMcpServerModal.tsx — Modal for adding a new MCP server to a workspace.
 *
 * Form fields (STORY-012-04 §1.2.5):
 *   - Name — slug regex ^[a-z0-9_-]{2,32}$ enforced client-side before submit.
 *   - Transport — radio group (Streamable HTTP / SSE); default Streamable HTTP.
 *   - URL — must start with https://.
 *   - Headers — dynamic key-value table via HeadersEditor. Default first row:
 *       key="Authorization", value="" (placeholder covers 80% case).
 *   - "Paste from another client" — collapsible textarea + Import button.
 *     Calls parseMcpJson on Import; populates form on success; error inline on failure.
 *     The textarea is a one-shot import helper, never the source of truth on submit.
 *
 * Submit: builds { name, transport, url, headers: Record<string,string> } from form
 *   state, calls useCreateMcpServerMutation. On success: close modal + list invalidated
 *   by the hook. On 400, surfaces backend `detail` inline.
 *
 * jsdom note (FLASHCARD 2026-04-12): no HTMLDialogElement — uses div overlay pattern.
 *
 * TDZ note (FLASHCARD 2026-04-11 #vitest): vi.mock for this module must wrap spies
 *   in vi.hoisted() in tests.
 */
import { useState } from 'react';
import { HeadersEditor, type HeaderRow } from './HeadersEditor';
import { parseMcpJson } from '../../lib/mcpJsonImport';
import type { McpTransport } from '../../lib/api';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Slug pattern for MCP server names — matches backend validation. */
const SLUG_RE = /^[a-z0-9_-]{2,32}$/;

/** Default first header row (covers Authorization / Bearer 80% case). */
const DEFAULT_HEADER: HeaderRow = { key: 'Authorization', value: '' };

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface AddMcpServerModalProps {
  workspaceId: string;
  onClose: () => void;
  onCreate: (body: {
    name: string;
    transport: McpTransport;
    url: string;
    headers: Record<string, string>;
  }) => Promise<void>;
  isPending: boolean;
  serverError: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AddMcpServerModal — form-driven MCP server creation dialog.
 *
 * Uses a div overlay pattern (not <dialog>) for jsdom compatibility in Vitest.
 *
 * @param onClose     - Called when the user cancels or after successful submit.
 * @param onCreate    - Async submit handler; resolves on success, throws on error.
 * @param isPending   - Set to true while the create mutation is in flight.
 * @param serverError - Inline error from server (400 detail) or null.
 */
export function AddMcpServerModal({
  onClose,
  onCreate,
  isPending,
  serverError,
}: AddMcpServerModalProps) {
  // Form state
  const [name, setName] = useState('');
  const [transport, setTransport] = useState<McpTransport>('streamable_http');
  const [url, setUrl] = useState('');
  const [headers, setHeaders] = useState<HeaderRow[]>([{ ...DEFAULT_HEADER }]);

  // Paste-import panel
  const [importPanelOpen, setImportPanelOpen] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [importError, setImportError] = useState<string | null>(null);
  const [importWarning, setImportWarning] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Validation
  // ---------------------------------------------------------------------------

  const nameValid = SLUG_RE.test(name);
  const urlValid = url.startsWith('https://');
  const canSubmit = nameValid && urlValid && !isPending;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleImport() {
    setImportError(null);
    setImportWarning(null);
    const result = parseMcpJson(pasteText);
    if (!result.ok) {
      setImportError(result.error);
      return;
    }
    const { server } = result;
    if (server.name) setName(server.name);
    setTransport(server.transport);
    setUrl(server.url);
    // Map ParsedMcpHeader[] → HeaderRow[] (strip the placeholder field)
    setHeaders(
      server.headers.length > 0
        ? server.headers.map((h) => ({ key: h.key, value: h.value }))
        : [{ ...DEFAULT_HEADER }],
    );
    if (server.warning) setImportWarning(server.warning);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    // Build headers dict — filter out rows with empty keys
    const headersDict: Record<string, string> = {};
    for (const row of headers) {
      if (row.key.trim()) headersDict[row.key.trim()] = row.value;
    }

    try {
      await onCreate({ name, transport, url, headers: headersDict });
    } catch {
      // Error is surfaced via serverError prop from parent
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    /* Overlay */
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Add MCP Server"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 p-6 space-y-4 max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">Add MCP Server</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="text-slate-400 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {/* Name */}
          <div className="space-y-1">
            <label htmlFor="mcp-name" className="text-xs font-medium text-slate-700">
              Name
            </label>
            <input
              id="mcp-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="github"
              data-testid="mcp-name-input"
              className="w-full text-xs rounded border border-slate-300 px-2 py-1.5 text-slate-700"
            />
            <p className="text-xs text-slate-400">
              Slug: <code>^[a-z0-9_-]{'{2,32}'}$</code>
              {name && !nameValid && (
                <span className="ml-1 text-rose-600" data-testid="name-error">
                  — invalid slug format
                </span>
              )}
            </p>
          </div>

          {/* Transport */}
          <div className="space-y-1">
            <span className="text-xs font-medium text-slate-700">Transport</span>
            <div className="flex flex-col gap-1 mt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="transport"
                  value="streamable_http"
                  checked={transport === 'streamable_http'}
                  onChange={() => setTransport('streamable_http')}
                  data-testid="transport-streamable"
                />
                <span className="text-xs text-slate-700">Streamable HTTP (recommended)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="transport"
                  value="sse"
                  checked={transport === 'sse'}
                  onChange={() => setTransport('sse')}
                  data-testid="transport-sse"
                />
                <span className="text-xs text-slate-700">SSE (legacy)</span>
              </label>
            </div>
          </div>

          {/* URL */}
          <div className="space-y-1">
            <label htmlFor="mcp-url" className="text-xs font-medium text-slate-700">
              URL
            </label>
            <input
              id="mcp-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.example.com/mcp/"
              data-testid="mcp-url-input"
              className="w-full text-xs rounded border border-slate-300 px-2 py-1.5 text-slate-700 font-mono"
            />
            {url && !urlValid && (
              <p className="text-xs text-rose-600" data-testid="url-error">
                URL must start with https://
              </p>
            )}
          </div>

          {/* Headers */}
          <div className="space-y-1">
            <span className="text-xs font-medium text-slate-700">Auth Headers</span>
            <HeadersEditor rows={headers} onChange={setHeaders} valueInputType="password" />
          </div>

          {/* Paste-from-another-client panel */}
          <div className="border border-slate-200 rounded-md overflow-hidden">
            <button
              type="button"
              onClick={() => setImportPanelOpen((prev) => !prev)}
              data-testid="import-panel-toggle"
              className="w-full text-left px-3 py-2 text-xs font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 flex items-center gap-1"
            >
              <span>{importPanelOpen ? '▲' : '▼'}</span>
              Paste from another client (advanced)
            </button>

            {importPanelOpen && (
              <div className="p-3 space-y-2">
                <textarea
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder={
                    'Paste an entry from claude_desktop_config.json, .vscode/mcp.json,\nor any MCP-compatible JSON config.'
                  }
                  rows={5}
                  data-testid="import-textarea"
                  className="w-full text-xs rounded border border-slate-300 px-2 py-1.5 text-slate-700 font-mono resize-y"
                />
                <button
                  type="button"
                  onClick={handleImport}
                  disabled={!pasteText.trim()}
                  data-testid="import-button"
                  className="text-xs font-semibold text-brand-600 hover:opacity-70 disabled:opacity-40"
                >
                  Import
                </button>
                {importError && (
                  <p className="text-xs text-rose-600" data-testid="import-error">
                    {importError}
                  </p>
                )}
                {importWarning && (
                  <p className="text-xs text-amber-600" data-testid="import-warning">
                    {importWarning}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Server error (from mutation) */}
          {serverError && (
            <p className="text-xs text-rose-600" role="alert" data-testid="server-error">
              {serverError}
            </p>
          )}

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              data-testid="submit-button"
              className="text-xs font-semibold text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-40 rounded px-3 py-1.5"
            >
              {isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
