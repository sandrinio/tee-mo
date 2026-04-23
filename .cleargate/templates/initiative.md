<instructions>
This is a READ artifact. It is written by cleargate_pull_initiative when syncing from the remote PM tool.
Do NOT draft this file from scratch. Do NOT invoke cleargate_push_item on this file — it is already synced from the remote.
Use this file as context input when drafting a Proposal or Epic.
Output location: .cleargate/plans/INIT-{ID}.md
Do NOT output these instructions.
</instructions>

---
initiative_id: "INIT-{ID}"
remote_id: "{PM_TOOL_ID}"
source_tool: "linear | jira"
status: "{PM native status}"
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

# INIT-{ID}: {Initiative Name}

## 1. Objective & Business Value
{High-level summary of what this initiative achieves and the expected outcome for the user or system.}

## 2. Success Criteria
- {Concrete metric or functional requirement 1}
- {Concrete metric or functional requirement 2}

## 3. Scope & Constraints

**In scope:**
- {What is included}

**Out of scope:**
- {What is explicitly excluded}

**Hard constraints:**
- {Deadlines, architectural rules, compliance requirements}

## 4. Target Sprint / Timeline
{Sprint number or date range as defined in the PM tool.}
