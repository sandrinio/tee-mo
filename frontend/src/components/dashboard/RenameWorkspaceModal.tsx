/**
 * RenameWorkspaceModal — modal dialog for renaming an existing Tee-Mo workspace.
 *
 * Follows the same structure as `CreateWorkspaceModal.tsx`:
 *   - Div-based overlay (not native `<dialog>`) for jsdom compatibility.
 *   - Native `<form>` element inside the overlay panel.
 *   - Single `name` input, pre-filled with the current workspace name.
 *   - Toast error on mutation failure (STORY-008-04 — replaces inline error paragraph).
 *
 * Behavior contract:
 *   - Renders the overlay when `open === true`; returns null when `open === false`.
 *   - Input is pre-filled with `workspace.name` and re-synced when `workspace` changes.
 *   - Submitting a non-empty name calls `useRenameWorkspaceMutation`.
 *   - On mutation success the modal closes via `onClose()`.
 *   - On mutation error a toast.error is shown — no inline error paragraph.
 *   - Clicking the backdrop closes the modal without saving.
 *   - "Cancel" button closes the modal without saving.
 *
 * STORY-008-03 changes:
 *   - Replaced hardcoded hex with `brand-500` design token (R8).
 *   - Replaced ad-hoc `<button>` elements with `<Button>` component (R9).
 *
 * Design Guide compliance:
 *   - Brand accent via `brand-500` Tailwind class.
 *   - Max font weight: `font-semibold` (600). Never `font-bold` (700).
 *   - No new `@theme` tokens — uses built-in Tailwind 4 classes.
 */
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useRenameWorkspaceMutation } from '../../hooks/useWorkspaces';
import { Button } from '../ui/Button';
import type { Workspace } from '../../lib/api';

/** Props accepted by RenameWorkspaceModal. */
export interface RenameWorkspaceModalProps {
  /** The workspace to rename — used to pre-fill the name input. */
  workspace: Workspace;
  /** Whether the modal is currently open. */
  open: boolean;
  /** Callback invoked when the modal should close (success or cancel). */
  onClose: () => void;
}

/**
 * RenameWorkspaceModal — controlled overlay modal for renaming a workspace.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false);
 * <RenameWorkspaceModal
 *   workspace={ws}
 *   open={open}
 *   onClose={() => setOpen(false)}
 * />
 * ```
 */
export function RenameWorkspaceModal({
  workspace,
  open,
  onClose,
}: RenameWorkspaceModalProps) {
  const [name, setName] = useState(workspace.name);

  // Sync input with the workspace prop whenever the modal opens or the workspace changes.
  useEffect(() => {
    if (open) {
      setName(workspace.name);
    }
  }, [open, workspace.name]);

  const mutation = useRenameWorkspaceMutation();

  /** Reset form state and close. */
  function handleClose() {
    setName(workspace.name);
    mutation.reset();
    onClose();
  }

  /** Handle form submission — calls rename mutation with current input value. */
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    try {
      await mutation.mutateAsync({ id: workspace.id, name: trimmed });
      onClose();
    } catch (err) {
      // Show error as a toast — no inline error paragraph (STORY-008-04).
      const message = err instanceof Error ? err.message : 'Failed to rename workspace';
      toast.error(message);
    }
  }

  if (!open) return null;

  return (
    /* Backdrop overlay */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50"
      onClick={(e) => {
        // Close when clicking the backdrop (but not the modal content).
        if (e.target === e.currentTarget) handleClose();
      }}
      aria-label="Rename workspace"
      role="dialog"
      aria-modal="true"
    >
      {/* Modal panel */}
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          Rename Workspace
        </h2>

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label
              htmlFor="rename-workspace-name"
              className="mb-1 block text-sm font-semibold text-slate-700"
            >
              Name
            </label>
            <input
              id="rename-workspace-name"
              type="text"
              name="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* Action buttons — R9: use Button component */}
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleClose}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={mutation.isPending || !name.trim()}
            >
              {mutation.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
