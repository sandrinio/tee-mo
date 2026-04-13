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
 *   - On mutation error a toast.error is shown (STORY-008-04 — replaces inline error).
 *   - Clicking the backdrop closes the modal without creating a workspace.
 *   - "Cancel" button closes the modal without creating a workspace.
 *
 * Design Guide compliance:
 *   - Coral brand accent `#E94560` for the submit button.
 *   - Max font weight: `font-semibold` (600). Never `font-bold` (700).
 *   - No new `@theme` tokens — uses built-in Tailwind 4 classes.
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { useCreateWorkspaceMutation } from '../../hooks/useWorkspaces';

/** Props accepted by CreateWorkspaceModal. */
export interface CreateWorkspaceModalProps {
  /** Slack team ID that the new workspace will belong to. */
  teamId: string;
  /** Whether the modal is currently open. */
  open: boolean;
  /** Callback invoked when the modal should close (success or cancel). */
  onClose: () => void;
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
 * />
 * ```
 */
export function CreateWorkspaceModal({
  teamId,
  open,
  onClose,
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
      await mutation.mutateAsync(trimmed);
      setName('');
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
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-[#E94560] focus:outline-none focus:ring-1 focus:ring-[#E94560]"
            />
          </div>

          {/* Action buttons */}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={handleClose}
              disabled={mutation.isPending}
              className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !name.trim()}
              className="rounded-md bg-[#E94560] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              {mutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
