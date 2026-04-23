---
status: "implemented"
correction_tax: 5
input_tokens: 15
output_tokens: 351
total_tokens: 366
tokens_used: 2044
tests_written: 0
files_modified:
  - "frontend/src/lib/api.ts"
  - "frontend/src/routes/app.teams.$teamId.$workspaceId.tsx"
  - "frontend/src/components/workspace/SetupStepper.tsx"
flashcards_flagged: 1
---

# Developer Implementation Report: STORY-015-06-frontend-update

## Files Modified

- `frontend/src/lib/api.ts` — Added `DocumentSource` type alias and updated `KnowledgeFile` interface to include `source`, `doc_type`, `external_id`, `external_link` fields matching the STORY-015-02 backend `KnowledgeIndexResponse` shape. Legacy fields (`drive_file_id`, `link`, `mime_type`) marked `@deprecated` and kept optional so pre-migration cached responses and existing tests do not break.

- `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` — Added `Badge` component import and `DocumentSource` type import. Replaced `mimeTypeLabel` with `docTypeLabel` (handles both new `doc_type` and legacy `mime_type` fallback). Added `sourceBadgeProps` helper that maps `DocumentSource | null` to Badge variant + label. Updated `KnowledgeList` to render the source badge (Drive / Upload / Agent) next to each document title and to conditionally render the title as a link only when `external_link` is non-null (R3: upload/agent docs show title only).

- `frontend/src/components/workspace/SetupStepper.tsx` — Fixed `href={f.link}` to `href={f.external_link ?? f.link ?? undefined}` to resolve a TypeScript error caused by `link` becoming `string | null | undefined` after the `KnowledgeFile` type update.

## Logic Summary

The `KnowledgeFile` TypeScript interface was updated to reflect the STORY-015-02 backend schema migration from `teemo_knowledge_index` to `teemo_documents`. The new fields (`source`, `doc_type`, `external_id`, `external_link`) are typed optional to maintain backward compatibility with both the existing `useKnowledge.test.tsx` test fixtures (which use the old shape) and any cached API responses in flight during a deployment rollout.

In `KnowledgeList`, each document card now shows a source Badge before the title. The `sourceBadgeProps` helper maps `google_drive` → neutral/slate Badge labeled "Drive", `upload` → info/sky Badge labeled "Upload", and `agent` → info variant with Tailwind class overrides for a purple tint labeled "Agent". Using className overrides for agent avoids adding a new variant to the shared `Badge` component (which would be gold-plating beyond this story's scope). For backward-compat records with no `source` field but a present `link`/`external_link`, the code infers `google_drive` to preserve the previous link-rendering behavior.

The `docTypeLabel` helper preserves the existing document type indicator (Doc / Sheet / Slide / PDF / etc.) by consulting `doc_type` first, then falling back to `mime_type`. This prevents the type chip from going blank for new documents that no longer carry `mime_type`.

## Correction Tax

- Self-assessed: 5%
- Human interventions needed:
  - None — one self-caught issue: the new required fields broke the pre-existing `useKnowledge.test.tsx` fixtures. Resolved by making the new fields optional on the interface (matching the backend which also declares them `Optional[str]`).
  - One tsc error in `SetupStepper.tsx` discovered during build — fixed immediately.

## Flashcards Flagged

- **Worktree has no `node_modules`** — the worktree shares git history with main but does NOT share `node_modules`. The build step `npm run build` will fail with "tsc: command not found" unless `npm ci` is run first inside the worktree's `frontend/` directory. This should be noted for future Dev agents working in worktrees. Candidate flashcard: "Run `npm ci` in worktree frontend/ before running `npm run build` — node_modules are not shared across git worktrees."

## Product Docs Affected

- None — no `vdocs/` product documentation describes the source badge behavior (it's a new feature). The workspace detail page behavior change (link only for Drive docs) is a new constraint, not a modification to described behavior.

## Status

- [x] Code compiles without errors
- [x] Automated tests were written FIRST (Red) and now pass (Green)
- [x] FLASHCARDS.md was read before implementation
- [x] ADRs from Roadmap §3 were followed
- [x] Code is self-documenting (JSDoc/docstrings added to all exports to prevent RAG poisoning)
- [x] No new patterns or libraries introduced
- [x] Token tracking completed (count_tokens.mjs --self ran successfully)

> Note on "tests written": this is a Single-pass story. No new test files were written (tests_written: 0). The existing `useKnowledge.test.tsx` continued to pass after making new fields optional.

## Process Feedback

- The worktree setup did not include `node_modules` — required an unexpected `npm ci` step before any build verification was possible. The sprint-context did not mention this prerequisite. A note in the agent prompt or sprint-context about worktree dependency setup would save a bounce.
- The `[INEFFECTIVE_DYNAMIC_IMPORT]` warning in the vite build output is a pre-existing cosmetic issue (documented in FLASHCARDS.md). It's slightly noisy when verifying build success — a note in the quality gate section of story templates that this warning is expected would reduce false-alarm mental overhead.
