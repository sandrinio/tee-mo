/**
 * WorkspaceCard — displays a single Tee-Mo workspace within the team detail page.
 *
 * Design Guide §9.2: Uses the `Card` primitive with `bg-white rounded-lg shadow-sm
 * border border-slate-200 p-6`. Displays workspace name, an optional "Default"
 * badge when `is_default_for_team` is true, and the creation date.
 *
 * Action buttons:
 *   - "Rename" — opens the RenameWorkspaceModal, available on all workspaces.
 *   - "Make Default" — triggers `useMakeDefaultMutation` with optimistic UI update.
 *     Only shown on non-default workspaces (no-op to show it on the current default).
 *
 * Error handling:
 *   - Inline error message below the action row when make-default mutation fails.
 *   - No external toast library (Design Guide §9.2 / STORY-003-B06).
 *
 * Max font weight is `font-semibold` (600) — never `font-bold` (700) per sprint
 * design rules in sprint-context-S-05.md.
 *
 * Date formatting uses `Intl.DateTimeFormat` (locale-aware, zero extra deps).
 *
 * STORY-004-04: Adds inline `KeySection` component for BYOK key management.
 * KeySection uses useKeyQuery, useSaveKeyMutation, useDeleteKeyMutation hooks
 * and the validateKey API call directly (not via a hook) for pre-save validation.
 */
import { useState } from 'react';
import { Link } from '@tanstack/react-router';
import { Card } from '../ui/Card';
import type { Workspace, ValidateKeyResponse } from '../../lib/api';
import { validateKey } from '../../lib/api';
import { useMakeDefaultMutation } from '../../hooks/useWorkspaces';
import { useKeyQuery, useSaveKeyMutation, useDeleteKeyMutation } from '../../hooks/useKey';
import { RenameWorkspaceModal } from './RenameWorkspaceModal';

// ---------------------------------------------------------------------------
// KeySection — inline BYOK key management section (STORY-004-04)
// ---------------------------------------------------------------------------

/**
 * Provider options for the BYOK key dropdown.
 * Used by KeySection to build the provider select element.
 * Values must match the backend's `SupportedProvider` enum in ADR-002.
 */
const PROVIDERS = [
  { value: 'openai' as const, label: 'OpenAI' },
  { value: 'anthropic' as const, label: 'Anthropic' },
  { value: 'google' as const, label: 'Google (Gemini)' },
] as const;

/** Provider union type derived from PROVIDERS to keep it DRY. */
type Provider = (typeof PROVIDERS)[number]['value'];

/**
 * KeySection — compact inline component for BYOK key management within a WorkspaceCard.
 *
 * States:
 *   - Collapsed / no key: shows warning + "+ Add key" button.
 *   - Collapsed / has key: shows masked key + provider badge + Update / Delete buttons.
 *   - Expanded form: provider dropdown, password input with show/hide toggle, Validate
 *     button (calls validateKey API directly), Save and Cancel.
 *   - Delete confirm: inline "Sure? [Yes, Delete] [Cancel]" replaces Delete button.
 *
 * Design rules (ADR-022 + Design Guide):
 *   - Section border: `border border-slate-200 rounded-lg p-3 mt-3`
 *   - Coral accent: `text-rose-500`
 *   - No Lucide icons — plain text/emoji only (sprint task requirement)
 *   - Max font weight: `font-semibold` (600)
 *
 * ADR-002 hard rule: plaintext key is NEVER stored in component state beyond
 * the controlled input value. It is sent directly to the API and discarded.
 *
 * @param workspaceId - UUID of the workspace this key belongs to.
 * @param teamId      - Slack team ID — passed to mutations for cache invalidation.
 */
function KeySection({ workspaceId, teamId }: { workspaceId: string; teamId: string }) {
  const { data: keyData, isLoading } = useKeyQuery(workspaceId);
  const saveMutation = useSaveKeyMutation(teamId);
  const deleteMutation = useDeleteKeyMutation(teamId);

  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState<Provider>('openai');
  const [keyInput, setKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidateKeyResponse | null>(null);
  const [validating, setValidating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  /** Reset all transient form state back to defaults. */
  function resetForm() {
    setShowForm(false);
    setKeyInput('');
    setShowKey(false);
    setValidationResult(null);
    setValidating(false);
  }

  /** Open the form, pre-selecting the current provider when updating. */
  function openForm() {
    if (keyData?.provider) {
      const match = PROVIDERS.find((p) => p.value === keyData.provider);
      if (match) setProvider(match.value);
    }
    setShowForm(true);
    setValidationResult(null);
    setKeyInput('');
  }

  /** Call the validateKey API and surface the result inline. */
  async function handleValidate() {
    if (!keyInput.trim()) return;
    setValidating(true);
    setValidationResult(null);
    try {
      const result = await validateKey({ provider, key: keyInput });
      setValidationResult(result);
    } catch (err) {
      setValidationResult({
        valid: false,
        message: err instanceof Error ? err.message : 'Validation failed',
      });
    } finally {
      setValidating(false);
    }
  }

  /** Save the key via mutation and collapse the form on success. */
  function handleSave() {
    saveMutation.mutate(
      { workspaceId, provider, key: keyInput },
      { onSuccess: resetForm },
    );
  }

  /** Delete the key after confirmation. */
  function handleDelete() {
    deleteMutation.mutate(workspaceId, {
      onSuccess: () => setShowDeleteConfirm(false),
    });
  }

  if (isLoading) {
    return (
      <div className="border border-slate-200 rounded-lg p-3 mt-3 animate-pulse">
        <div className="h-3 w-1/3 rounded bg-slate-100" />
      </div>
    );
  }

  const hasKey = keyData?.has_key === true;

  // Human-readable provider label for the badge (e.g. "openai" → "OpenAI")
  const providerLabel = PROVIDERS.find((p) => p.value === keyData?.provider)?.label ?? keyData?.provider ?? '';

  return (
    <div className="border border-slate-200 rounded-lg p-3 mt-3">
      {/* ------------------------------------------------------------------ */}
      {/* Collapsed display — no form open                                    */}
      {/* ------------------------------------------------------------------ */}
      {!showForm && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500 font-semibold">API Key:</span>

          {hasKey ? (
            <>
              {/* Provider badge */}
              <span className="text-xs bg-slate-100 text-slate-700 rounded px-1.5 py-0.5 font-semibold">
                {providerLabel}
              </span>
              {/* Masked key */}
              <span className="text-xs font-mono text-slate-700" data-testid="key-mask">
                {keyData?.key_mask}
              </span>

              {/* Update / Delete buttons */}
              <button
                type="button"
                onClick={openForm}
                className="text-xs font-semibold text-slate-500 hover:text-slate-800"
              >
                Update
              </button>

              {!showDeleteConfirm ? (
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(true)}
                  className="text-xs font-semibold text-rose-500 hover:opacity-70"
                >
                  Delete
                </button>
              ) : (
                <>
                  <span className="text-xs text-slate-500">Sure?</span>
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleteMutation.isPending}
                    className="text-xs font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
                  >
                    {deleteMutation.isPending ? 'Deleting…' : 'Yes, Delete'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(false)}
                    className="text-xs font-semibold text-slate-500 hover:text-slate-800"
                  >
                    Cancel
                  </button>
                </>
              )}
            </>
          ) : (
            <>
              {/* No key state */}
              <span className="text-xs text-rose-500" data-testid="no-key-label">
                ⚠ No key configured
              </span>
              <button
                type="button"
                onClick={openForm}
                className="text-xs font-semibold text-rose-500 hover:opacity-70"
                data-testid="add-key-button"
              >
                + Add key
              </button>
            </>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Expanded add/update form                                            */}
      {/* ------------------------------------------------------------------ */}
      {showForm && (
        <div className="flex flex-col gap-2">
          {/* Form row: provider dropdown + key input + validate */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Provider dropdown */}
            <select
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value as Provider);
                setValidationResult(null);
              }}
              className="text-xs rounded border border-slate-300 px-2 py-1 text-slate-700"
              aria-label="Provider"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>

            {/* Key input with show/hide toggle */}
            <div className="flex items-center gap-1">
              <input
                type={showKey ? 'text' : 'password'}
                value={keyInput}
                onChange={(e) => {
                  setKeyInput(e.target.value);
                  setValidationResult(null);
                }}
                placeholder="Paste API key…"
                className="text-xs rounded border border-slate-300 px-2 py-1 font-mono text-slate-700 w-44"
                aria-label="API Key"
                data-testid="key-input"
              />
              <button
                type="button"
                onClick={() => setShowKey((prev) => !prev)}
                className="text-xs text-slate-400 hover:text-slate-700"
                aria-label={showKey ? 'Hide key' : 'Show key'}
              >
                {showKey ? 'Hide' : '👁'}
              </button>
            </div>

            {/* Validate button */}
            <button
              type="button"
              onClick={handleValidate}
              disabled={!keyInput.trim() || validating}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800 disabled:opacity-40"
              data-testid="validate-button"
            >
              {validating ? 'Validating…' : 'Validate'}
            </button>

            {/* Save button — only enabled after successful validation */}
            <button
              type="button"
              onClick={handleSave}
              disabled={!validationResult?.valid || saveMutation.isPending}
              className="text-xs font-semibold text-rose-500 hover:opacity-70 disabled:opacity-40"
              data-testid="save-button"
            >
              {saveMutation.isPending ? 'Saving…' : 'Save'}
            </button>

            {/* Cancel */}
            <button
              type="button"
              onClick={resetForm}
              className="text-xs font-semibold text-slate-400 hover:text-slate-700"
            >
              Cancel
            </button>
          </div>

          {/* Inline validation result */}
          {validationResult && (
            <p
              className={`text-xs ${validationResult.valid ? 'text-emerald-600' : 'text-rose-600'}`}
              data-testid="validation-result"
            >
              {validationResult.valid
                ? '✅ Valid'
                : `❌ Invalid: ${validationResult.message}`}
            </p>
          )}

          {/* Inline save error */}
          {saveMutation.error && (
            <p className="text-xs text-rose-600" role="alert">
              {saveMutation.error instanceof Error
                ? saveMutation.error.message
                : 'Failed to save key. Please try again.'}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add File placeholder guard (EPIC-006 wires the real button)
// ---------------------------------------------------------------------------

/**
 * canAddFile — evaluates whether the workspace has a configured BYOK key.
 *
 * This function exists as a placeholder so EPIC-006 can import it and wire
 * the real "Add File" button without re-reading the key status.
 *
 * @param hasKey - The `has_key` field from `ProviderKey`.
 * @returns `true` when an API key is configured and the Add File action is allowed.
 */
export function canAddFile(hasKey: boolean | undefined): boolean {
  return hasKey === true;
}

// ---------------------------------------------------------------------------
// WorkspaceCard props
// ---------------------------------------------------------------------------

/** Props accepted by WorkspaceCard. */
export interface WorkspaceCardProps {
  /** The workspace record to display. */
  workspace: Workspace;
  /**
   * Slack team ID the workspace belongs to.
   * Required so `useMakeDefaultMutation` can target the correct query cache key
   * for its optimistic update.
   */
  teamId: string;
}

/**
 * WorkspaceCard — card UI for one workspace record.
 *
 * Shows:
 *   - Workspace name (semibold)
 *   - "Default" badge when `workspace.is_default_for_team === true`
 *   - Human-readable creation date (locale-aware via Intl)
 *   - "Rename" action button (all workspaces)
 *   - "Make Default" action button (non-default workspaces only)
 *   - Inline error if the make-default mutation fails
 *
 * @example
 * ```tsx
 * <WorkspaceCard workspace={ws} teamId={teamId} />
 * ```
 */
export function WorkspaceCard({ workspace, teamId }: WorkspaceCardProps) {
  const [renameOpen, setRenameOpen] = useState(false);

  const makeDefaultMutation = useMakeDefaultMutation(teamId);

  const createdDate = new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
  }).format(new Date(workspace.created_at));

  return (
    <>
      <Card className="shadow-sm">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-1 min-w-0">
            {/* Workspace name — links to detail page */}
            <Link
              to="/app/teams/$teamId/$workspaceId"
              params={{ teamId, workspaceId: workspace.id }}
              className="font-semibold text-slate-900 truncate hover:text-rose-500 transition-colors"
            >
              {workspace.name}
            </Link>

            {/* Creation date */}
            <div className="text-xs text-slate-400">
              Created {createdDate}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {/* Default badge — only shown when this workspace is the team default */}
            {workspace.is_default_for_team && (
              <span
                className="rounded-full bg-[#E94560] px-2 py-0.5 text-xs font-semibold text-white"
                aria-label="Default workspace"
              >
                Default
              </span>
            )}

            {/* Action buttons */}
            <button
              type="button"
              onClick={() => setRenameOpen(true)}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800"
            >
              Rename
            </button>

            {/* Make Default — only shown on non-default workspaces */}
            {!workspace.is_default_for_team && (
              <button
                type="button"
                onClick={() => makeDefaultMutation.mutate(workspace.id)}
                disabled={makeDefaultMutation.isPending}
                className="text-xs font-semibold text-[#E94560] hover:opacity-70 disabled:opacity-40"
              >
                {makeDefaultMutation.isPending ? 'Saving…' : 'Make Default'}
              </button>
            )}
          </div>
        </div>

        {/* BYOK Key Section — STORY-004-04 */}
        <KeySection workspaceId={workspace.id} teamId={teamId} />

        {/* Placeholder guard for EPIC-006 "Add File" button.
            When canAddFile is false, the future button should render with
            disabled={true} and title="Configure your AI provider first". */}

        {/* Inline error if make-default mutation fails */}
        {makeDefaultMutation.error != null && (
          <p
            role="alert"
            className="mt-2 text-xs text-rose-700"
          >
            {makeDefaultMutation.error instanceof Error
              ? makeDefaultMutation.error.message
              : 'An error occurred. Please try again.'}
          </p>
        )}
      </Card>

      {/* Rename modal — mounted outside Card so it renders above everything */}
      <RenameWorkspaceModal
        workspace={workspace}
        open={renameOpen}
        onClose={() => setRenameOpen(false)}
      />
    </>
  );
}
