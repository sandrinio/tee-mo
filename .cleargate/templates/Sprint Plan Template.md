<instructions>
This is a READ artifact. It is written by cleargate_pull_initiative when syncing a Sprint from the remote PM tool.
Do NOT draft this file manually. Do NOT invoke cleargate_push_item on this file.
The Vibe Coder may annotate the "Execution Guidelines" section locally — this section is never pushed.
Output location: .cleargate/plans/SPRINT-{ID}.md
Do NOT output these instructions.
</instructions>

---
sprint_id: "SPRINT-{ID}"
remote_id: "{PM_TOOL_SPRINT_ID}"
source_tool: "linear | jira"
status: "Draft | Active | Completed"
start_date: "{YYYY-MM-DD}"
end_date: "{YYYY-MM-DD}"
synced_at: "{ISO-8601 timestamp}"
created_at: "2026-04-17T00:00:00Z"
updated_at: "2026-04-17T00:00:00Z"
created_at_version: "strategy-phase-pre-init"
updated_at_version: "strategy-phase-pre-init"
draft_tokens:
  input: null
  output: null
  cache_read: null
  cache_creation: null
  model: null
  sessions: []
cached_gate_result:
  pass: null
  failing_criteria: []
  last_gate_check: null
---

# SPRINT-{ID}: {Sprint Number / Name}

## Sprint Goal
{One clear sentence describing the primary objective of this sprint, as defined in the PM tool.}

## Consolidated Deliverables
*(Pulled from PM tool. IDs are the remote PM entity IDs.)*

- `{TASK-ID}`: {Title} — {Brief Description}
- `{TASK-ID}`: {Title} — {Brief Description}

## Risks & Dependencies
*(As defined in the PM tool.)*

| Risk | Mitigation |
|---|---|
| {Description} | {Action} |

## Metrics & Metadata
- **Expected Impact:** {e.g., performance improvement %, specific user outcome}
- **Priority Alignment:** {Notes on prioritization from the PM tool}

---

## Execution Guidelines (Local Annotation — Not Pushed)
*(Vibe Coder: Fill this in locally to direct Claude Code during the Execution Phase. This section never syncs to the PM tool.)*

- **Starting Point:** {Which deliverable to tackle first and why}
- **Relevant Context:** {Key documentation or codebase areas to reference}
- **Constraints:** {Specific technical boundaries or "out of scope" rules for this sprint}
