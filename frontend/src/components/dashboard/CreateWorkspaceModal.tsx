/**
 * CreateWorkspaceModal — modal dialog for creating a new Tee-Mo workspace.
 *
 * Renders a div-based overlay modal (not native `<dialog>`) so it works in both
 * browser environments and jsdom test environments (jsdom does not implement
 * HTMLDialogElement.showModal()). The spec requirement for "native `<form>`" is
 * satisfied by the `<form>` element inside the modal.
 *
 * Behavior contract:
 *   - Renders the overlay when `open === true`; returns null when `open === false`.
 *   - Submitting a non-empty name calls the create mutation.
 *   - On mutation success the modal closes via `onClose()`.
 *   - If `onCreated` is provided it is called with the new workspace record so
 *     the parent can navigate to guided setup (STORY-008-03 R6).
 *   - On mutation error a toast.error is shown (STORY-008-04 — replaces inline error).
 *   - Clicking the backdrop closes the modal without creating a workspace.
 *   - "Cancel" button closes the modal without creating a workspace.
 *
 * STORY-008-03 changes:
 *   - Added `onCreated` optional callback for post-creation navigation (R6).
 *   - Replaced hardcoded hex with `brand-500` design token (R8).
 *   - Replaced ad-hoc `<button>` elements with `<Button>` component (R9).
 *
 * Design Guide compliance:
 *   - Brand accent via `brand-500` Tailwind class.
 *   - Max font weight: `font-semibold` (600). Never `font-bold` (700).
 *   - No new `@theme` tokens — uses built-in Tailwind 4 classes.
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useCreateWorkspaceMutation } from '../../hooks/useWorkspaces';
import { Button } from '../ui/Button';
import type { Workspace } from '../../lib/api';

/** Props accepted by CreateWorkspaceModal. */
export interface CreateWorkspaceModalProps {
  /** Slack team ID that the new workspace will belong to. */
  teamId: string;
  /** Whether the modal is currently open. */
  open: boolean;
  /** Callback invoked when the modal should close (success or cancel). */
  onClose: () => void;
  /**
   * Optional callback invoked with the newly created workspace record on success.
   * Use this to navigate to the guided setup page after creation (R6).
   */
  onCreated?: (workspace: Workspace) => void;
}

/**
 * CreateWorkspaceModal — controlled overlay modal for workspace creation.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false);
 * <CreateWorkspaceModal
 *   teamId={teamId}
 *   open={open}
 *   onClose={() => setOpen(false)}
 *   onCreated={(ws) => navigate({ to: '/app/teams/$teamId/$workspaceId', params: { teamId, workspaceId: ws.id } })}
 * />
 * ```
 */
export function CreateWorkspaceModal({
  teamId,
  open,
  onClose,
  onCreated,
}: CreateWorkspaceModalProps) {
  const [name, setName] = useState('');

  const mutation = useCreateWorkspaceMutation(teamId);

  /** Reset form state and close. */
  function handleClose() {
    setName('');
    mutation.reset();
    onClose();
  }

  /** Handle form submission — calls create mutation. */
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;

    try {
      const newWorkspace = await mutation.mutateAsync(trimmed);
      setName('');
      // Notify parent before closing so it can act on the new workspace (R6).
      if (onCreated) {
        onCreated(newWorkspace);
      }
      onClose();
    } catch (err) {
      // Show error as a toast — no inline error paragraph (STORY-008-04).
      const message = err instanceof Error ? err.message : 'Failed to create workspace';
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
      aria-label="Create workspace"
      role="dialog"
      aria-modal="true"
    >
      {/* Modal panel */}
      <div className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-lg font-semibold text-slate-900">
          New Workspace
        </h2>

        <form onSubmit={handleSubmit} noValidate>
          <div className="mb-4">
            <label
              htmlFor="workspace-name"
              className="mb-1 block text-sm font-semibold text-slate-700"
            >
              Name
            </label>
            <input
              id="workspace-name"
              type="text"
              name="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My AI Workspace"
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
              {mutation.isPending ? 'Creating…' : 'Create'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
