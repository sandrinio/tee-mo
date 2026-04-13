/**
 * KeySection.tsx — Standalone BYOK key management section (STORY-008-01 R1).
 *
 * Extracted from WorkspaceCard.tsx so it can be reused inside SetupStepper
 * (step 2 content) without duplicating logic. Zero behavior changes from the
 * original inline implementation.
 *
 * States:
 *   - Loading: skeleton pulse while key status is fetched.
 *   - Collapsed / no key: warning label + "+ Add key" button.
 *   - Collapsed / has key: masked key + provider badge + Update / Delete buttons.
 *   - Expanded form: provider dropdown, password input, Validate → Save flow.
 *   - Delete confirm: inline "Sure? [Yes, Delete] [Cancel]" row.
 *
 * Design rules (ADR-022 + Design Guide):
 *   - Section border: `border border-slate-200 rounded-lg p-3 mt-3`
 *   - Coral accent: `text-rose-500`
 *   - No Lucide icons — plain text/emoji only
 *   - Max font weight: `font-semibold` (600)
 *
 * ADR-002 hard rule: plaintext key is NEVER stored in component state beyond
 * the controlled input value. It is sent directly to the API and discarded.
 */
import { useState } from 'react';
import type { ValidateKeyResponse } from '../../lib/api';
import { validateKey } from '../../lib/api';
import { useKeyQuery, useSaveKeyMutation, useDeleteKeyMutation } from '../../hooks/useKey';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Provider options for the BYOK key dropdown.
 * Values must match the backend's `SupportedProvider` enum in ADR-002.
 */
const PROVIDERS = [
  { value: 'openai' as const, label: 'OpenAI' },
  { value: 'anthropic' as const, label: 'Anthropic' },
  { value: 'google' as const, label: 'Google (Gemini)' },
] as const;

/** Provider union type derived from PROVIDERS to keep it DRY. */
type Provider = (typeof PROVIDERS)[number]['value'];

// ---------------------------------------------------------------------------
// KeySection component
// ---------------------------------------------------------------------------

/**
 * KeySection — compact component for BYOK key management.
 *
 * Can be embedded in WorkspaceCard (collapsed summary view) or in
 * SetupStepper step 2 (guided setup flow). Same logic and UI in both cases.
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
  const providerLabel =
    PROVIDERS.find((p) => p.value === keyData?.provider)?.label ?? keyData?.provider ?? '';

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
