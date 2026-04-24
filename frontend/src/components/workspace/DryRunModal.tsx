/**
 * DryRunModal.tsx — One-shot dry-run preview modal for an existing automation (STORY-018-06).
 *
 * Opens with a pre-filled `prompt` from the parent's state (set by AutomationsSection's
 * onDryRunClick callback). Immediately fires `useTestRunMutation.mutate(prompt)` when
 * `open` becomes true — the test-run is auto-fired without any user interaction.
 *
 * Renders a div-based overlay modal (NOT native `<dialog>`) so it works in jsdom test
 * environments. jsdom does not implement HTMLDialogElement.showModal().
 * (FLASHCARD 2026-04-12 #vitest #frontend)
 *
 * Banner: "This preview runs your prompt now. No message will be posted to Slack."
 *
 * States:
 *   - Loading  — spinner while `useTestRunMutation.isPending`
 *   - Success  — output in a sky-blue card + token count
 *   - Error    — rose card with error message
 *
 * Footer: "Close" button + backdrop click to close.
 *
 * All data fetching goes through TanStack hooks — no raw fetch() calls
 * (FLASHCARD 2026-04-11 #frontend #recipe).
 */
import { useEffect } from 'react';
import { useTestRunMutation } from '../../hooks/useAutomations';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

/**
 * Props for DryRunModal.
 */
export interface DryRunModalProps {
  /** UUID of the workspace to run the test against. */
  workspaceId: string;
  /** Human-readable name of the automation (displayed in the modal header). */
  automationName: string;
  /** The prompt text to run. Set by parent before opening the modal. */
  prompt: string;
  /** Whether the modal is currently open. */
  open: boolean;
  /** Callback invoked when the modal should close. */
  onClose: () => void;
}

// ---------------------------------------------------------------------------
// DryRunModal
// ---------------------------------------------------------------------------

/**
 * DryRunModal — auto-fires a test-run for an automation's prompt on open.
 *
 * Pure consumer of STORY-018-05 hooks.
 *
 * @example
 * ```tsx
 * <DryRunModal
 *   workspaceId={workspaceId}
 *   automationName={dryRunName}
 *   prompt={dryRunPrompt}
 *   open={dryRunOpen}
 *   onClose={() => setDryRunOpen(false)}
 * />
 * ```
 */
export function DryRunModal({
  workspaceId,
  automationName,
  prompt,
  open,
  onClose,
}: DryRunModalProps) {
  const testRunMutation = useTestRunMutation(workspaceId);

  /**
   * Auto-fire the test-run when the modal opens (one-shot).
   * Resets mutation state first so stale results from a previous open cycle
   * don't flash before the new result arrives.
   */
  useEffect(() => {
    if (open && prompt) {
      testRunMutation.reset();
      testRunMutation.mutate({ prompt });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, prompt]);

  if (!open) return null;

  const { isPending, data: result, error } = testRunMutation;

  return (
    /* Backdrop overlay — div-based (FLASHCARD 2026-04-12 #vitest #frontend) */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label={`Preview: ${automationName}`}
    >
      {/* Modal panel */}
      <div className="w-full max-w-lg rounded-lg border border-slate-200 bg-white shadow-lg">
        <div className="p-6">
          {/* Header */}
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Preview: {automationName}
          </h2>

          {/* Disclaimer banner */}
          <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-800">
            This preview runs your prompt now. No message will be posted to Slack.
          </div>

          {/* Result area */}
          <div className="min-h-[80px]">
            {isPending && (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <span
                  className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand-500 border-t-transparent"
                  role="status"
                  aria-label="Running preview"
                />
                <span>Running preview…</span>
              </div>
            )}

            {!isPending && error && (
              <div
                className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800"
                role="alert"
              >
                Preview error:{' '}
                {error instanceof Error ? error.message : 'Unknown error'}
              </div>
            )}

            {!isPending && !error && result && (
              <>
                {result.success ? (
                  <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-slate-700">
                    <pre className="whitespace-pre-wrap text-xs">{result.output}</pre>
                    {result.tokens_used != null && (
                      <p className="mt-2 text-xs text-slate-400">
                        {result.tokens_used} tokens used
                      </p>
                    )}
                  </div>
                ) : (
                  <div
                    className="rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-800"
                    role="alert"
                  >
                    {result.error === 'no_key_configured'
                      ? 'No API key configured. Configure a key in the Key section first.'
                      : `Preview failed: ${result.error ?? 'Unknown error'}`}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="mt-6 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
