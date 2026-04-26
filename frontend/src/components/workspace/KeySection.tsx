/**
 * KeySection.tsx — BYOK key management module (STORY-025-02 re-skin).
 *
 * Re-skinned from the stacked form to a segmented control + masked-key box
 * per the workspace v2 design handoff (WorkspaceV2Modules.jsx KeyBody).
 *
 * Changes (chrome only — zero behavior changes):
 *   - 3-button segmented control (Google / OpenAI / Anthropic) replacing the dropdown.
 *   - Masked key rendered in `rounded-md bg-slate-50 p-3 font-mono text-xs` box.
 *   - "Update" renamed to "Rotate" (design §KeyBody).
 *   - AES-256-GCM caption added.
 *   - Outer container removes redundant border (ModuleSection provides the card).
 *
 * Behaviour preserved verbatim:
 *   - useKeyQuery, useSaveKeyMutation, useDeleteKeyMutation hooks unchanged.
 *   - Validate → Save flow unchanged.
 *   - Delete confirm flow unchanged.
 *
 * ADR-002 hard rule: plaintext key is NEVER stored in component state beyond
 * the controlled input value. It is sent directly to the API and discarded.
 */
import { useState, useEffect } from 'react';
import type { ValidateKeyResponse } from '../../lib/api';
import { validateKey } from '../../lib/api';
import { useKeyQuery, useSaveKeyMutation, useDeleteKeyMutation } from '../../hooks/useKey';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Provider options for the BYOK key segmented control.
 * Values must match the backend's `SupportedProvider` enum in ADR-002.
 */
const PROVIDERS = [
  { value: 'google' as const,    label: 'Google' },
  { value: 'openai' as const,    label: 'OpenAI' },
  { value: 'anthropic' as const, label: 'Anthropic' },
] as const;

/** Provider union type derived from PROVIDERS to keep it DRY. */
type Provider = (typeof PROVIDERS)[number]['value'];

// ---------------------------------------------------------------------------
// KeySection component
// ---------------------------------------------------------------------------

/**
 * KeySection — BYOK key management for the workspace v2 connections group.
 *
 * @param workspaceId - UUID of the workspace this key belongs to.
 * @param teamId      - Slack team ID — passed to mutations for cache invalidation.
 */
export function KeySection({ workspaceId, teamId }: { workspaceId: string; teamId: string }) {
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

  // Sync local provider state from saved key data when it loads.
  // This ensures the segmented control reflects the persisted provider immediately
  // without requiring the user to open the form first.
  useEffect(() => {
    if (keyData?.provider && !showForm) {
      const match = PROVIDERS.find((p) => p.value === keyData.provider);
      if (match) setProvider(match.value);
    }
  }, [keyData?.provider, showForm]);

  /** Reset all transient form state back to defaults. */
  function resetForm() {
    setShowForm(false);
    setKeyInput('');
    setShowKey(false);
    setValidationResult(null);
    setValidating(false);
  }

  /** Open the form, pre-selecting the current provider when rotating. */
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
      <div className="p-5 animate-pulse">
        <div className="h-3 w-1/3 rounded bg-slate-100" />
      </div>
    );
  }

  const hasKey = keyData?.has_key === true;

  // The segmented control always reflects local `provider` state,
  // which is synced from keyData.provider via useEffect above.
  const activeProvider = provider;

  return (
    <div className="p-5 space-y-4">
      {/* ------------------------------------------------------------------ */}
      {/* Segmented control — provider selection                              */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex gap-2">
        {PROVIDERS.map((p) => {
          const isActive = activeProvider === p.value;
          return (
            <button
              key={p.value}
              type="button"
              onClick={() => {
                setProvider(p.value);
                setValidationResult(null);
              }}
              data-testid={`provider-segment-${p.value}`}
              className={[
                'h-8 px-3 rounded-md text-xs font-medium border transition-colors',
                isActive
                  ? 'bg-brand-50 text-brand-700 border-brand-200'
                  : 'bg-white text-slate-700 border-slate-200 hover:border-slate-300',
              ].join(' ')}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Collapsed display — no form open                                    */}
      {/* ------------------------------------------------------------------ */}
      {!showForm && (
        <div className="space-y-3">
          {hasKey ? (
            <>
              {/* Masked key box */}
              <div className="flex items-center justify-between gap-3">
                <div
                  className="rounded-md bg-slate-50 border border-slate-200 p-3 font-mono text-xs text-slate-700 flex-1 truncate"
                  data-testid="key-mask"
                >
                  {keyData?.key_mask}
                </div>
                <button
                  type="button"
                  onClick={openForm}
                  className="text-xs font-semibold text-slate-500 hover:text-slate-800 whitespace-nowrap"
                  data-testid="rotate-button"
                >
                  Rotate
                </button>
              </div>

              {/* Caption */}
              <p className="text-xs text-slate-500">
                Encrypted with AES-256-GCM.
              </p>

              {/* Delete control */}
              <div className="flex items-center gap-2">
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
              </div>
            </>
          ) : (
            /* No key state */
            <div className="flex items-center gap-2">
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
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Expanded add/rotate form                                            */}
      {/* ------------------------------------------------------------------ */}
      {showForm && (
        <div className="flex flex-col gap-2">
          {/* Form row: key input + validate + save + cancel */}
          <div className="flex flex-wrap items-center gap-2">
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
