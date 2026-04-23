<instructions>
FOLLOW THIS EXACT STRUCTURE. Output sections in order 1-5.
YAML Frontmatter: Bug ID, Parent Ref, Status, Severity, Reporter, Approved gate.
§1 The Anomaly: Expected vs. Actual behavior.
§2 Reproduction Protocol: Deterministic steps to recreate.
§3 Evidence & Context: Raw logs, stack traces, payloads — no paraphrasing.
§4 Execution Sandbox: Exact file paths to investigate. Restrict scope to prevent unrelated refactoring.
§5 Verification Protocol: The failing test that proves the bug exists and proves the fix resolves it.
Output location: .cleargate/delivery/pending-sync/BUG-{ID}.md

CRITICAL PHASE GATE: Do NOT invoke cleargate_push_item until reproduction steps are 100% deterministic and a failing test is attached.
Do NOT output these instructions.
</instructions>

---
bug_id: "BUG-{ID}"
parent_ref: "EPIC-{ID} | STORY-{ID}"
status: "Draft | Triaged | In Fix | Verified"
severity: "P0-Critical | P1-High | P2-Medium | P3-Low"
reporter: "{name}"
approved: false
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
---

# BUG-{ID}: {Bug Name}

## 1. The Anomaly (Expected vs. Actual)
**Expected Behavior:** {What the system should do under normal conditions.}

**Actual Behavior:** {What it is doing right now.}

## 2. Reproduction Protocol
*(AI agents need strict, deterministic steps. "If it can't be reproduced reliably, it can't be fixed safely.")*

1. Go to...
2. Click...
3. Observe...

## 3. Evidence & Context
*(Provide the raw truth: stack traces, terminal errors, network payloads. Do not paraphrase.)*

```
[Paste exact logs or error messages here]
```

## 4. Execution Sandbox (Suspected Blast Radius)
*(Restrict the agent's focus to prevent unrelated refactoring.)*

**Investigate / Modify:**
- `src/...`

## 5. Verification Protocol (The Failing Test)
*(The agent must write or run a specific test that proves the bug exists, then prove the fix resolves it.)*

**Command:** `npm test ...`

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🔴 High Ambiguity**

Requirements to pass to Green (Ready for Fix):
- [ ] Reproduction steps are 100% deterministic.
- [ ] Actual vs. Expected behavior is explicitly defined.
- [ ] Raw error logs/evidence are attached.
- [ ] Verification command (failing test) is provided.
- [ ] `approved: true` is set in the YAML frontmatter.
