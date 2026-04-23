<instructions>
FOLLOW THIS EXACT STRUCTURE. Output sections in order 1-4.
YAML Frontmatter: CR ID, Parent Ref (Epic or Story being changed), Status, Approved gate.
Use this template when CHANGING an existing feature. For net-new functionality, use story.md instead.
§1 The Context Override: What to remove/forget + the new truth. AI agents hallucinate when old context conflicts with new requests.
§2 Blast Radius & Invalidation: Which downstream items does this CR break? A CR acts as a "Gate Reset" on affected items.
§3 Execution Sandbox: Exact file paths to modify.
§4 Verification Protocol: How to confirm new logic works and old logic is fully evicted.
Output location: .cleargate/delivery/pending-sync/CR-{ID}.md

CRITICAL PHASE GATE: Do NOT invoke cleargate_push_item until all impacted downstream Epics/Stories are identified and reverted to 🔴 High Ambiguity.
Do NOT output these instructions.
</instructions>

---
cr_id: "CR-{ID}"
parent_ref: "EPIC-{ID} | STORY-{ID}"
status: "Draft | In Review | Approved"
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

# CR-{ID}: {Change Request Name}

## 1. The Context Override (Old vs. New)
*(AI agents hallucinate when old context conflicts with new requests. Explicitly declare what to evict.)*

**Obsolete Logic (What to Remove / Forget):**
- {e.g., We no longer use Stripe for this flow.}

**New Logic (The New Truth):**
- {e.g., Route all payments through PayPal.}

## 2. Blast Radius & Invalidation
*(A CR acts as a "Gate Reset" — all affected downstream items revert to 🔴 High Ambiguity.)*

- [ ] Invalidate/Update Story: [Link]
- [ ] Invalidate/Update Epic: [Link]
- [ ] Database schema impacts? {Yes/No — describe}

## 3. Execution Sandbox
*(Restrict the agent's scope to prevent unrelated refactoring.)*

**Modify:**
- `src/...`

## 4. Verification Protocol
*(How do we confirm new logic works and old logic is completely removed?)*

**Command/Test:** `npm test ...`

---

## ClearGate Ambiguity Gate (🟢 / 🟡 / 🔴)
**Current Status: 🔴 High Ambiguity**

Requirements to pass to Green (Ready for Execution):
- [ ] "Obsolete Logic" to be evicted is explicitly declared.
- [ ] All impacted downstream Epics/Stories are identified and reverted to 🔴 High Ambiguity.
- [ ] Execution Sandbox contains exact file paths.
- [ ] Verification command is provided.
- [ ] `approved: true` is set in the YAML frontmatter.
