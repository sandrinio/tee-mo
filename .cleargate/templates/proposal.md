<instructions> FOLLOW THIS EXACT STRUCTURE. Output sections in order 1-4.
YAML Frontmatter: Proposal ID, Status, Author, and the crucial approved boolean.
§1 Initiative & Context: The "Why" and "What".
§2 Technical Architecture & Constraints: Architecture constraints, data flow, dependencies.
§3 Touched Files: Real files that will need modification.
Output location: .cleargate/delivery/pending-sync/PROPOSAL-{Name}.md

Document Hierarchy Position: LEVEL 0 (Proposal → Epic → Story)

CRITICAL PHASE GATE: Do NOT generate Epics or Stories, and do NOT invoke cleargate_push_item, until the Human has reviewed this document and manually changed approved: false to approved: true in the frontmatter.

Do NOT output these instructions. </instructions>

proposal_id: "PROP-{ID}" status: "Draft / In Review / Approved" author: "{AI Agent / Vibe Coder}" approved: false
created_at: "2026-04-17T00:00:00Z"
updated_at: "2026-04-17T00:00:00Z"
created_at_version: "strategy-phase-pre-init"
updated_at_version: "strategy-phase-pre-init"
server_pushed_at_version: null
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
PROPOSAL-{ID}: {Initiative Name}
1. Initiative & Context
1.1 Objective
{1-2 sentences explaining the high-level goal and business value.}

1.2 The "Why"
{Reason 1}
{Reason 2}
2. Technical Architecture & Constraints
2.1 Dependencies
{List required external APIs, packages, or systems}
2.2 System Constraints
Constraint	Details
Architectural Rules	{e.g., Must use purely functional components, etc.}
Security	{e.g., Data must be encrypted at rest.}
3. Scope Impact (Touched Files & Data)
3.1 Known Files
path/to/existing/file.ext - {Explanation of expected change}
3.2 Expected New Entities
path/to/new/file.ext - {Explanation of purpose}
🔒 Approval Gate
(Vibe Coder: Review this proposal. If the architecture and context are correct, change approved: false to approved: true in the YAML frontmatter. Only then is the AI authorized to proceed with Epic/Story decomposition.)