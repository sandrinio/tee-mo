/**
 * IntegrationsSection.tsx — MCP server management body for the workspace shell.
 *
 * Mounted as the `integrations` module under the `workspace` group in
 * moduleRegistry.tsx. ModuleSection provides the h2 + caption + card border —
 * this body renders only the action button + server list (KeySection convention).
 *
 * Rendered elements:
 *   - Top-right "Add Integration" button.
 *   - Empty state when zero servers: "No integrations connected yet."
 *   - Mini-card list: one row per server with transport badge, status badge,
 *     Test button, Enable toggle, Delete button (with confirm).
 *
 * Status badge state machine (STORY-012-04 §3.2):
 *   CardStatus = 'untested' | 'active' | 'disabled' | 'failed'
 *   - untested: server.is_active && no test result yet
 *   - active:   server.is_active && last test ok=true
 *   - disabled: !server.is_active
 *   - failed:   server.is_active && last test ok=false
 *
 * Status lives in local state (map keyed by server.name), NOT in the server
 * response — V1 only.
 *
 * Risk guard: /test returns HTTP 200 always; read body.ok, not status code.
 */
import { useState } from 'react';
import {
  useMcpServersQuery,
  useCreateMcpServerMutation,
  useUpdateMcpServerMutation,
  useDeleteMcpServerMutation,
  useTestMcpServerMutation,
} from '../../hooks/useMcpServers';
import { AddMcpServerModal } from './AddMcpServerModal';
import type { McpServer, McpTransport } from '../../lib/api';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type CardStatus = 'untested' | 'active' | 'disabled' | 'failed';

interface TestResult {
  ok: boolean;
  tool_count: number;
  error: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function computeStatus(
  server: McpServer,
  testResults: Map<string, TestResult>,
): CardStatus {
  if (!server.is_active) return 'disabled';
  const result = testResults.get(server.name);
  if (!result) return 'untested';
  return result.ok ? 'active' : 'failed';
}

function TransportBadge({ transport }: { transport: McpTransport }) {
  return (
    <span
      className={[
        'text-xs font-medium rounded-full px-2 py-0.5 shrink-0',
        transport === 'sse'
          ? 'bg-amber-50 text-amber-700'
          : 'bg-blue-50 text-blue-700',
      ].join(' ')}
      data-testid="transport-badge"
    >
      {transport === 'sse' ? 'SSE' : 'Streamable HTTP'}
    </span>
  );
}

function StatusBadge({
  status,
  toolCount,
  error,
}: {
  status: CardStatus;
  toolCount?: number;
  error?: string | null;
}) {
  if (status === 'disabled') {
    return (
      <span
        className="text-xs font-medium rounded-full px-2 py-0.5 bg-slate-100 text-slate-500 shrink-0"
        data-testid="status-badge"
      >
        Disabled
      </span>
    );
  }
  if (status === 'active') {
    return (
      <span
        className="text-xs font-medium rounded-full px-2 py-0.5 bg-emerald-50 text-emerald-700 shrink-0"
        data-testid="status-badge"
      >
        Active{toolCount !== undefined ? ` (${toolCount} tools)` : ''}
      </span>
    );
  }
  if (status === 'failed') {
    return (
      <span
        className="text-xs font-medium rounded-full px-2 py-0.5 bg-rose-50 text-rose-700 shrink-0 cursor-help"
        title={error ?? undefined}
        data-testid="status-badge"
      >
        Failed
      </span>
    );
  }
  // untested
  return (
    <span
      className="text-xs font-medium rounded-full px-2 py-0.5 bg-amber-50 text-amber-700 shrink-0"
      data-testid="status-badge"
    >
      Untested
    </span>
  );
}

// ---------------------------------------------------------------------------
// MCP Server card row
// ---------------------------------------------------------------------------

interface ServerCardProps {
  server: McpServer;
  status: CardStatus;
  testResult: TestResult | undefined;
  onTest: () => void;
  onToggle: (isActive: boolean) => void;
  onDelete: () => void;
  isTestPending: boolean;
  isTogglePending: boolean;
  isDeletePending: boolean;
}

function ServerCard({
  server,
  status,
  testResult,
  onTest,
  onToggle,
  onDelete,
  isTestPending,
  isTogglePending,
  isDeletePending,
}: ServerCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  return (
    <li
      className="flex flex-wrap items-center gap-2 py-2 border-b border-slate-100 last:border-b-0"
      data-testid="mcp-server-card"
    >
      {/* Name */}
      <span className="text-xs font-semibold text-slate-800 min-w-0 shrink-0">
        {server.name}
      </span>

      {/* Transport badge */}
      <TransportBadge transport={server.transport} />

      {/* URL — truncated */}
      <span
        className="text-xs font-mono text-slate-500 truncate flex-1 min-w-0"
        title={server.url}
        data-testid="server-url"
      >
        {server.url}
      </span>

      {/* Status badge */}
      <StatusBadge
        status={status}
        toolCount={testResult?.ok ? testResult.tool_count : undefined}
        error={testResult?.error}
      />

      {/* Test button */}
      <button
        type="button"
        onClick={onTest}
        disabled={isTestPending}
        data-testid="test-button"
        className="text-xs font-semibold text-slate-500 hover:text-slate-800 disabled:opacity-40 shrink-0"
      >
        {isTestPending ? '…' : 'Test'}
      </button>

      {/* Enable toggle */}
      <button
        type="button"
        onClick={() => onToggle(!server.is_active)}
        disabled={isTogglePending}
        data-testid="toggle-button"
        aria-label={server.is_active ? 'Disable server' : 'Enable server'}
        className={[
          'relative inline-flex h-4 w-8 rounded-full transition-colors shrink-0 disabled:opacity-40',
          server.is_active ? 'bg-emerald-500' : 'bg-slate-300',
        ].join(' ')}
      >
        <span
          className={[
            'absolute top-0.5 left-0.5 h-3 w-3 rounded-full bg-white transition-transform',
            server.is_active ? 'translate-x-4' : 'translate-x-0',
          ].join(' ')}
        />
      </button>

      {/* Delete button / confirm */}
      {!confirmDelete ? (
        <button
          type="button"
          onClick={() => setConfirmDelete(true)}
          data-testid="delete-button"
          className="text-xs font-semibold text-rose-500 hover:opacity-70 shrink-0"
        >
          Delete
        </button>
      ) : (
        <span className="flex items-center gap-1 shrink-0">
          <span className="text-xs text-slate-500">Sure?</span>
          <button
            type="button"
            onClick={() => {
              setConfirmDelete(false);
              onDelete();
            }}
            disabled={isDeletePending}
            data-testid="delete-confirm-button"
            className="text-xs font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
          >
            {isDeletePending ? 'Deleting…' : 'Yes, Delete'}
          </button>
          <button
            type="button"
            onClick={() => setConfirmDelete(false)}
            data-testid="delete-cancel-button"
            className="text-xs font-semibold text-slate-400 hover:text-slate-700"
          >
            Cancel
          </button>
        </span>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// IntegrationsSection
// ---------------------------------------------------------------------------

export interface IntegrationsSectionProps {
  workspaceId: string;
  teamId: string;
}

/**
 * IntegrationsSection — inline MCP server management for WorkspaceCard.
 *
 * Mounts below KeySection in WorkspaceCard. Follows the same chrome pattern.
 */
export function IntegrationsSection({ workspaceId }: IntegrationsSectionProps) {
  const { data: servers = [], isLoading } = useMcpServersQuery(workspaceId);

  const createMutation = useCreateMcpServerMutation(workspaceId);
  const updateMutation = useUpdateMcpServerMutation(workspaceId);
  const deleteMutation = useDeleteMcpServerMutation(workspaceId);
  const testMutation = useTestMcpServerMutation(workspaceId);

  // Local test-result state — maps server.name → TestResult
  const [testResults, setTestResults] = useState<Map<string, TestResult>>(new Map());
  // Track which server is being tested (for spinner)
  const [testingName, setTestingName] = useState<string | null>(null);
  // Track which server is being toggled
  const [togglingName, setTogglingName] = useState<string | null>(null);
  // Track which server is being deleted
  const [deletingName, setDeletingName] = useState<string | null>(null);

  const [addModalOpen, setAddModalOpen] = useState(false);

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleTest(name: string) {
    setTestingName(name);
    testMutation.mutate(name, {
      onSuccess: (result) => {
        setTestResults((prev) => new Map(prev).set(name, result));
        setTestingName(null);
      },
      onError: () => {
        setTestingName(null);
      },
    });
  }

  function handleToggle(name: string, isActive: boolean) {
    setTogglingName(name);
    updateMutation.mutate(
      { name, patch: { is_active: isActive } },
      {
        onSettled: () => setTogglingName(null),
      },
    );
  }

  function handleDelete(name: string) {
    setDeletingName(name);
    deleteMutation.mutate(name, {
      onSettled: () => setDeletingName(null),
    });
  }

  async function handleCreate(body: Parameters<typeof createMutation.mutate>[0]) {
    return new Promise<void>((resolve, reject) => {
      createMutation.mutate(body, {
        onSuccess: () => {
          setAddModalOpen(false);
          resolve();
        },
        onError: (err) => {
          reject(err);
        },
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className="p-5 animate-pulse">
        <div className="h-3 w-1/3 rounded bg-slate-100" />
      </div>
    );
  }

  const createError =
    createMutation.error instanceof Error ? createMutation.error.message : null;

  return (
    <>
      <div className="space-y-3" data-testid="integrations-section">
        {/* Action row — ModuleSection provides the heading; we render only the action. */}
        <div className="flex items-center justify-end">
          <button
            type="button"
            onClick={() => {
              createMutation.reset();
              setAddModalOpen(true);
            }}
            data-testid="add-integration-button"
            className="text-xs font-semibold text-brand-600 hover:opacity-70 shrink-0"
          >
            + Add Integration
          </button>
        </div>

        {/* Server list or empty state */}
        {servers.length === 0 ? (
          <p className="text-xs text-slate-400" data-testid="empty-state">
            No integrations connected yet. Add one to give the agent extra tools.
          </p>
        ) : (
          <ul className="space-y-0 divide-y divide-slate-100" data-testid="server-list">
            {servers.map((server) => {
              const status = computeStatus(server, testResults);
              const testResult = testResults.get(server.name);
              return (
                <ServerCard
                  key={server.name}
                  server={server}
                  status={status}
                  testResult={testResult}
                  onTest={() => handleTest(server.name)}
                  onToggle={(active) => handleToggle(server.name, active)}
                  onDelete={() => handleDelete(server.name)}
                  isTestPending={testingName === server.name}
                  isTogglePending={togglingName === server.name}
                  isDeletePending={deletingName === server.name}
                />
              );
            })}
          </ul>
        )}
      </div>

      {/* Add MCP Server modal */}
      {addModalOpen && (
        <AddMcpServerModal
          workspaceId={workspaceId}
          onClose={() => setAddModalOpen(false)}
          onCreate={handleCreate}
          isPending={createMutation.isPending}
          serverError={createError}
        />
      )}
    </>
  );
}
