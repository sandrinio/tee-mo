# Readiness Gates

This file is the single source of truth for ClearGate's machine-checkable readiness gates. Each gate entry declares the `{work_item_type, transition}` pair it governs, along with a list of criteria expressed in the closed-set predicate vocabulary defined below. The predicate evaluator in `cleargate-cli/src/lib/readiness-predicates.ts` (STORY-008-02) reads these YAML blocks and evaluates them against a target document's frontmatter and body. Gate check results are cached in the document's own frontmatter under `cached_gate_result:` by `cleargate gate check <file>`.

---

## Predicate Vocabulary

There are exactly **6 predicate shapes**. No other shapes are recognized; a check string that does not match one of these forms throws a parse error at evaluation time.

**1. `frontmatter(<ref>).<field> <op> <value>`**
Reads a frontmatter field from a document. `<ref>` is either `.` (the document being evaluated) or a frontmatter key whose value is a relative path to another document (e.g. `context_source`). `<op>` is one of `==`, `!=`, `>=`, `<=`. `<value>` is a literal string, number, or boolean. Example: `frontmatter(context_source).approved == true` reads the file named by the evaluated document's `context_source` key and asserts its `approved` field equals `true`.

**2. `body contains "<string>"` / `body does not contain "<string>"`**
Performs a case-sensitive substring search on the document body (everything after the frontmatter block). The negated form `body does not contain` passes when the string is absent. Example: `body does not contain 'TBD'` fails if the literal string `TBD` appears anywhere in the body.

**3. `section(<N>) has <count> <item-type>`**
Splits the document body on `## ` heading boundaries (1-indexed) and counts items of a given type within section N. `<count>` is an expression like `≥1`, `≥3`, or `0` (exact zero). `<item-type>` is one of `checked-checkbox` (lines matching `- [x]`), `unchecked-checkbox` (lines matching `- [ ]`), or `listed-item` (lines matching `- ` regardless of checkbox state). Example: `section(2) has ≥1 checked-checkbox` asserts that the second `##` section contains at least one checked markdown checkbox.

**4. `file-exists(<path>)`**
Asserts that a file exists on disk at the given path, resolved relative to the project root. Example: `file-exists(.cleargate/knowledge/cleargate-protocol.md)` passes when that file is present in the working tree.

**5. `link-target-exists(<[[WORK-ITEM-ID]]>)`**
Reads `.cleargate/wiki/index.md` and asserts that the wiki index contains a reference to the given ID. Passes when the wiki has an entry for the linked item, meaning it has been ingested at least once. Example: `link-target-exists([[EPIC-008]])` passes when EPIC-008 appears in the compiled wiki index.

**6. `status-of(<[[ID]]>) == <value>`**
Resolves the given ID via the wiki index, reads that page's compiled frontmatter `status:` field, and compares it to `<value>`. Status values in the live corpus are textual strings (`Draft`, `Ready`, `Active`, `Done`) — not emoji. Example: `status-of([[EPIC-008]]) == Active` passes when EPIC-008's wiki page has `status: Active`. Note: this predicate returns `unknown` (evaluates to fail) when the wiki index is stale and the item is not yet compiled. Run `cleargate wiki build` before relying on `status-of` predicates.

---

## Severity Model

Gates are classified as either **advisory** or **enforcing**.

**Advisory** gates (Proposal only) emit warnings and exit 0 regardless of pass/fail. They are informational checkpoints — they record `cached_gate_result.pass: false` in the document's frontmatter so an agent can read the state, but they never block a downstream action. Crucially, a Proposal's `approved: true` field is a pure human judgment: a Vibe Coder manually sets it after reviewing the document. The gate cannot and must not intercept that. Failing an advisory gate means "the document could be stronger" — it does not mean "the human may not approve."

**Enforcing** gates (Epic, Story, CR, Bug) exit non-zero on any failing criterion. `cleargate wiki lint` refuses to mark an Epic/Story/CR/Bug as 🟢-candidate when `cached_gate_result.pass == false` or when `last_gate_check < updated_at` (stale result). This ensures every enforcing gate check is fresh at the time of promotion.

The asymmetry exists because Proposal documents are human-authored strategy artifacts where partial drafts are normal and iterative. Epics, Stories, CRs, and Bugs represent engineering commitments where incomplete specification directly causes execution failures.

---

## Gate Definitions

```yaml
- work_item_type: proposal
  transition: ready-for-decomposition
  severity: advisory
  criteria:
    - id: architecture-populated
      check: "section(2) has ≥1 listed-item"
    - id: touched-files-populated
      check: "section(3) has ≥1 listed-item"
    - id: no-tbds
      check: "body does not contain 'TBD'"
```

```yaml
- work_item_type: epic
  transition: ready-for-decomposition
  severity: enforcing
  criteria:
    - id: proposal-approved
      check: "frontmatter(context_source).approved == true"
    - id: no-tbds
      check: "body does not contain 'TBD'"
    - id: scope-in-populated
      check: "section(2) has ≥1 listed-item"
    - id: affected-files-declared
      check: "section(4) has ≥1 listed-item"
    - id: interrogation-resolved
      check: "body does not contain 'Unresolved'"
```

```yaml
- work_item_type: epic
  transition: ready-for-coding
  severity: enforcing
  criteria:
    - id: stories-referenced
      check: "body contains 'STORY-'"
    - id: gherkin-happy-path
      check: "body contains 'Scenario:'"
    - id: gherkin-error-path
      check: "body contains 'Error'"
    - id: no-tbds
      check: "body does not contain 'TBD'"
    - id: interrogation-resolved
      check: "body does not contain 'Unresolved'"
```

```yaml
- work_item_type: story
  transition: ready-for-execution
  severity: enforcing
  criteria:
    - id: parent-epic-ref-set
      check: "frontmatter(.).parent_epic_ref != null"
    - id: no-tbds
      check: "body does not contain 'TBD'"
    - id: implementation-files-declared
      check: "section(3) has ≥1 listed-item"
    - id: dod-declared
      check: "section(4) has ≥1 listed-item"
    - id: gherkin-present
      check: "body contains 'Scenario:'"
```

```yaml
- work_item_type: cr
  transition: ready-to-apply
  severity: enforcing
  criteria:
    - id: blast-radius-populated
      check: "section(1) has ≥1 listed-item"
    - id: no-tbds
      check: "body does not contain 'TBD'"
    - id: sandbox-paths-declared
      check: "section(2) has ≥1 listed-item"
```

```yaml
- work_item_type: bug
  transition: ready-for-fix
  severity: enforcing
  criteria:
    - id: repro-steps-deterministic
      check: "section(2) has ≥3 listed-item"
    - id: severity-set
      check: "frontmatter(.).severity != null"
    - id: no-tbds
      check: "body does not contain 'TBD'"
```
