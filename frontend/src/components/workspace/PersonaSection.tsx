/**
 * PersonaSection.tsx — Bot persona configuration (STORY-025-04).
 *
 * Extracted verbatim from the inline route function (STORY-019-01 original).
 * Preserved: textarea + Save mutation + character counter + saved/error toast.
 * Changed: inner Card + h2 removed — <ModuleSection> parent provides card border
 * and heading, so this component renders bare content only.
 *
 * NO voice presets (epic §6 Q2 owner directive).
 * Status resolver (behavior group): 'ok' if bot_persona non-empty, 'empty' otherwise.
 */

import { useState, useEffect } from 'react';
import { useUpdateWorkspaceMutation } from '../../hooks/useWorkspaces';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PersonaSectionProps {
  workspace: {
    id: string;
    name: string;
    bot_persona?: string | null;
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * PersonaSection — textarea + Save mutation + character counter + status pill.
 *
 * Renders inside ModuleSection (card + header provided by parent).
 * Does NOT render its own h2 or outer card border.
 */
export function PersonaSection({ workspace }: PersonaSectionProps) {
  const [persona, setPersona] = useState(workspace.bot_persona ?? '');
  const updateMutation = useUpdateWorkspaceMutation();

  // Sync internal state if the workspace object changes (e.g. after a refresh)
  useEffect(() => {
    setPersona(workspace.bot_persona ?? '');
  }, [workspace.bot_persona]);

  const hasChanged = persona !== (workspace.bot_persona ?? '');

  const handleSave = () => {
    updateMutation.mutate({
      id: workspace.id,
      name: workspace.name,
      bot_persona: persona,
    });
  };

  return (
    <div className="p-4 space-y-3">
      <textarea
        value={persona}
        onChange={(e) => setPersona(e.target.value)}
        placeholder="e.g. You are a senior project manager at a fast-paced tech startup. Be direct, efficient, and always check for blockers."
        rows={4}
        className="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        maxLength={2000}
      />

      <div className="flex items-center justify-between">
        <div className="text-[10px] text-slate-400">
          {persona.length} / 2000 characters
        </div>

        <div className="flex items-center gap-2">
          {updateMutation.isSuccess && !hasChanged && (
            <span className="text-xs text-emerald-600 animate-fade-in" data-testid="persona-saved-pill">
              Saved successfully
            </span>
          )}
          {updateMutation.error && (
            <span className="text-xs text-rose-600" data-testid="persona-error-pill">
              Failed to save
            </span>
          )}
          <button
            type="button"
            onClick={handleSave}
            disabled={updateMutation.isPending || !hasChanged}
            className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {updateMutation.isPending ? 'Saving…' : 'Save Persona'}
          </button>
        </div>
      </div>
    </div>
  );
}
