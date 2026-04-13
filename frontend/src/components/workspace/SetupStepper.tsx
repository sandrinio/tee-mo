/**
 * SetupStepper.tsx — Guided workspace setup wizard (STORY-008-01 R2–R8).
 *
 * Renders a horizontal 4-step indicator that walks a user through the initial
 * workspace configuration:
 *   1. Drive  — Connect Google Drive (OAuth)
 *   2. AI Key — Configure BYOK API key
 *   3. Files  — Index at least one Drive file
 *   4. Channels — Bind Slack channels (placeholder, future EPIC)
 *
 * Step completion is derived purely from live query data — no persisted state:
 *   - Step 1 complete: `useDriveStatusQuery(workspaceId).data.connected === true`
 *   - Step 2 complete: `useKeyQuery(workspaceId).data.has_key === true`
 *   - Step 3 complete: `useKnowledgeQuery(workspaceId).data.length >= 1`
 *   - Step 4: no completion criterion (placeholder only)
 *
 * Gating (R4):
 *   - Step 2 is only unlocked once step 1 is complete.
 *   - Step 3 is only unlocked once step 2 is complete.
 *   - Step 4 is always visible but becomes active only when steps 1–3 are done.
 *     Because R5 dismisses the stepper at that point, step 4 content is effectively
 *     shown only in edge scenarios where step 4 could be the active step.
 *
 * Dismissal (R5): When Drive connected AND key configured AND ≥1 file indexed,
 * the component returns `null` — the caller renders the normal workspace detail view.
 *
 * Step content:
 *   - Step 1: DriveSection — Connect/disconnect Google Drive
 *   - Step 2: KeySection — BYOK key management (R8)
 *   - Step 3: PickerSection + file list guidance
 *   - Step 4: Placeholder card "Bind Slack channels to this workspace" (R7)
 *
 * Design tokens (Design Guide §9.3 + sprint-context-S-09):
 *   - Step circles: `h-8 w-8 rounded-full flex items-center justify-center text-sm`
 *   - Complete: `bg-brand-500 text-white` with checkmark "✓"
 *   - Active: `ring-2 ring-brand-500 bg-white text-brand-500`
 *   - Future: `bg-slate-200 text-slate-400`
 *   - Connector lines: `h-0.5 flex-1` — complete: `bg-brand-500`, future: `bg-slate-200`
 *   - Labels: `text-xs font-medium` — active: `text-brand-600`, else: `text-slate-500`
 */
import { useState, useCallback } from 'react';
import { useDriveStatusQuery } from '../../hooks/useDrive';
import { useKeyQuery } from '../../hooks/useKey';
import { useKnowledgeQuery, useAddKnowledgeMutation, useRemoveKnowledgeMutation } from '../../hooks/useKnowledge';
import { getPickerToken } from '../../lib/api';
import { Card } from '../ui/Card';
import { KeySection } from './KeySection';
import { ChannelSection } from './ChannelSection';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** 1-indexed step numbers for clarity. */
type StepNumber = 1 | 2 | 3 | 4;

/** Per-step metadata used to build the step indicator row. */
interface StepMeta {
  number: StepNumber;
  label: string;
}

const STEPS: StepMeta[] = [
  { number: 1, label: 'Drive' },
  { number: 2, label: 'AI Key' },
  { number: 3, label: 'Files' },
  { number: 4, label: 'Channels' },
];

// ---------------------------------------------------------------------------
// SetupStepper
// ---------------------------------------------------------------------------

/**
 * SetupStepper — guided workspace setup wizard.
 *
 * Returns `null` when all three prerequisite steps (Drive, AI Key, Files) are
 * complete so the parent page can render the normal workspace detail view.
 *
 * @param workspaceId - UUID of the workspace being set up.
 * @param teamId      - Slack team ID — forwarded to KeySection for cache invalidation.
 */
export function SetupStepper({
  workspaceId,
  teamId,
  onSkip,
}: {
  workspaceId: string;
  teamId: string;
  /** Called when user clicks "Skip setup" to dismiss the wizard. */
  onSkip?: () => void;
}) {
  // -------------------------------------------------------------------------
  // Data queries — completion state derived from live data (R3, R6)
  // -------------------------------------------------------------------------

  const { data: driveStatus } = useDriveStatusQuery(workspaceId);
  const { data: keyData } = useKeyQuery(workspaceId);
  const { data: knowledgeFiles } = useKnowledgeQuery(workspaceId);

  const step1Complete = driveStatus?.connected === true;
  const step2Complete = keyData?.has_key === true;
  const step3Complete = (knowledgeFiles?.length ?? 0) >= 1;

  // -------------------------------------------------------------------------
  // Active step computation (R4: gating)
  // The active step is the first incomplete step whose prerequisite is met.
  // When steps 1-3 are all done, step 4 (Channels) becomes active so the
  // user can bind channels before the wizard dismisses.
  // -------------------------------------------------------------------------

  let activeStep: StepNumber;
  if (!step1Complete) {
    activeStep = 1;
  } else if (!step2Complete) {
    activeStep = 2;
  } else if (!step3Complete) {
    activeStep = 3;
  } else {
    activeStep = 4;
  }

  // -------------------------------------------------------------------------
  // Step state helpers
  // -------------------------------------------------------------------------

  function isComplete(step: StepNumber): boolean {
    if (step === 1) return step1Complete;
    if (step === 2) return step2Complete;
    if (step === 3) return step3Complete;
    return false; // Step 4 has no completion criterion
  }

  function isActive(step: StepNumber): boolean {
    return step === activeStep;
  }

  // -------------------------------------------------------------------------
  // Connector line: complete when the step BEFORE it is complete
  // (i.e. line between step N and N+1 is complete when step N is complete)
  // -------------------------------------------------------------------------

  function lineComplete(afterStep: StepNumber): boolean {
    return isComplete(afterStep);
  }

  // -------------------------------------------------------------------------
  // Step circle class helpers (Design Guide §9.3)
  // -------------------------------------------------------------------------

  function circleClasses(step: StepNumber): string {
    const base = 'h-8 w-8 rounded-full flex items-center justify-center text-sm';
    if (isComplete(step)) return `${base} bg-brand-500 text-white`;
    if (isActive(step)) return `${base} ring-2 ring-brand-500 bg-white text-brand-500`;
    return `${base} bg-slate-200 text-slate-400`;
  }

  function labelClasses(step: StepNumber): string {
    const base = 'text-xs font-medium mt-1 text-center';
    if (isActive(step)) return `${base} text-brand-600`;
    return `${base} text-slate-500`;
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-8">
      <div className="mx-auto max-w-2xl space-y-8">

        {/* Skip button */}
        {onSkip && (
          <div className="flex justify-end">
            <button
              type="button"
              onClick={onSkip}
              data-testid="skip-setup"
              className="text-sm text-slate-400 hover:text-slate-600"
            >
              Skip setup
            </button>
          </div>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Step indicator row                                               */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex items-start">
          {STEPS.map((step, index) => (
            <div key={step.number} className="flex items-start flex-1 last:flex-none">
              {/* Step circle + label column */}
              <div className="flex flex-col items-center">
                <div
                  data-testid={`step-${step.number}`}
                  data-active={String(isActive(step.number))}
                  data-complete={String(isComplete(step.number))}
                  className={circleClasses(step.number)}
                >
                  {isComplete(step.number) ? '✓' : step.number}
                </div>
                <span className={labelClasses(step.number)}>{step.label}</span>
              </div>

              {/* Connector line between this step and the next */}
              {index < STEPS.length - 1 && (
                <div
                  className={`h-0.5 flex-1 mt-4 ${
                    lineComplete(step.number) ? 'bg-brand-500' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Active step content — only the active step renders its panel    */}
        {/* ---------------------------------------------------------------- */}

        {/* Step 1: Google Drive connection */}
        {activeStep === 1 && (
          <div data-testid="step-1-content">
            <DriveStepContent workspaceId={workspaceId} />
          </div>
        )}

        {/* Step 2: AI Key (embeds KeySection — R8) */}
        {activeStep === 2 && (
          <div data-testid="step-2-content">
            <KeySection workspaceId={workspaceId} teamId={teamId} />
          </div>
        )}

        {/* Step 3: Index files from Drive — real Picker + file list */}
        {activeStep === 3 && (
          <div data-testid="step-3-content">
            <FilesStepContent workspaceId={workspaceId} />
          </div>
        )}

        {/* Step 4: Channel binding — real ChannelSection */}
        {activeStep === 4 && (
          <div data-testid="step-4-content">
            <ChannelSection workspaceId={workspaceId} teamId={teamId} />
          </div>
        )}

      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step content sub-components
// ---------------------------------------------------------------------------

/**
 * DriveStepContent — step 1 content.
 * Prompts the user to connect Google Drive via OAuth redirect.
 *
 * @param workspaceId - UUID of the workspace to connect Drive to.
 */
function DriveStepContent({ workspaceId }: { workspaceId: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6">
      <h2 className="text-base font-semibold text-slate-900 mb-3">Connect Google Drive</h2>
      <p className="text-sm text-slate-500 mb-4">
        Connect your Google Drive so Tee-Mo can index files for this workspace.
      </p>
      <a
        href={`/api/workspaces/${encodeURIComponent(workspaceId)}/drive/connect`}
        className="rounded-md bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:opacity-90"
      >
        Connect Google Drive
      </a>
    </div>
  );
}

/** Max files per workspace (matches backend 15-file cap). */
const MAX_FILES = 15;

/** GAPI script URL for Google Picker. */
const GAPI_SCRIPT_URL = 'https://apis.google.com/js/api.js';

/** Load Google API script (idempotent). */
function loadGapiScript(): Promise<void> {
  return new Promise((resolve) => {
    if (typeof gapi !== 'undefined') { resolve(); return; }
    const script = document.createElement('script');
    script.src = GAPI_SCRIPT_URL;
    script.onload = () => resolve();
    document.head.appendChild(script);
  });
}

/**
 * FilesStepContent — step 3 content.
 * Renders the Google Picker button and indexed file list directly within
 * the guided setup flow so users can add files without leaving the wizard.
 */
function FilesStepContent({ workspaceId }: { workspaceId: string }) {
  const { data: files, isLoading } = useKnowledgeQuery(workspaceId);
  const addMutation = useAddKnowledgeMutation(workspaceId);
  const removeMutation = useRemoveKnowledgeMutation(workspaceId);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileCount = files?.length ?? 0;
  const atCap = fileCount >= MAX_FILES;

  const handleOpenPicker = useCallback(async () => {
    setError(null);
    try {
      const { access_token, picker_api_key } = await getPickerToken(workspaceId);
      await loadGapiScript();
      gapi.load('picker', () => {
        const picker = new google.picker.PickerBuilder()
          .setOAuthToken(access_token)
          .setDeveloperKey(picker_api_key)
          .addView(google.picker.ViewId.DOCS)
          .setCallback(async (data: google.picker.CallbackData) => {
            if (data.action !== google.picker.Action.PICKED) return;
            const doc = data.docs?.[0];
            if (!doc) return;
            setIndexing(true);
            try {
              await addMutation.mutateAsync({
                drive_file_id: doc.id,
                title: doc.name,
                link: doc.url,
                mime_type: doc.mimeType,
                access_token,
              });
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to index file.');
            } finally {
              setIndexing(false);
            }
          })
          .build();
        picker.setVisible(true);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open file picker.');
    }
  }, [workspaceId, addMutation]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <h2 className="text-base font-semibold text-slate-900">Knowledge Files</h2>
          <div className="flex items-center gap-3">
            <span className="text-sm text-slate-500">{fileCount}/{MAX_FILES} files</span>
            <button
              type="button"
              onClick={handleOpenPicker}
              disabled={atCap || indexing}
              className="rounded-md bg-brand-500 px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {indexing ? 'Indexing…' : 'Add File'}
            </button>
          </div>
        </div>
        {error && <p className="text-xs text-rose-600 mt-1" role="alert">{error}</p>}
      </Card>

      {/* File list */}
      {isLoading ? (
        <div className="animate-pulse h-20 bg-slate-100 rounded-lg" />
      ) : files && files.length > 0 ? (
        <Card>
          <ul className="divide-y divide-slate-100">
            {files.map((f) => (
              <li key={f.id} className="py-3 flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <a href={f.external_link ?? f.link ?? undefined} target="_blank" rel="noopener noreferrer" className="text-sm font-medium text-brand-500 hover:underline truncate block">
                    {f.title}
                  </a>
                  {f.ai_description && (
                    <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">{f.ai_description}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => removeMutation.mutate(f.id)}
                  className="text-xs text-slate-400 hover:text-rose-500 shrink-0"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <p className="text-sm text-slate-400 text-center py-4">No files indexed yet. Use the picker above to add your first file.</p>
      )}
    </div>
  );
}

