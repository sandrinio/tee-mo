---
story_id: "STORY-003-04-pyjwt-fix"
parent_epic_ref: "EPIC-002 (post-delivery maintenance)"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L1"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-12T00:00:00Z"
created_at_version: "vbounce-backlog"
updated_at_version: "cleargate-migration-2026-04-24"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/sprints/sprint-03/STORY-003-04-pyjwt-fix.md`. Shipped in sprint S-03, carried forward during ClearGate migration 2026-04-24.

# STORY-003-04: PyJWT Test-Order Flake Fix (BUG-20260411)

**Complexity: L1** — 6-line change to `decode_token` + 1 new regression-lock test + 10x stability run. ~30 minutes.

---

## 1. The Spec (The Contract)

### 1.1 Problem Statement

`test_decode_token_rejects_tampered_signature` (from STORY-002-01's `test_security.py`) fails intermittently when run AFTER certain tests in `test_auth_routes.py`. Root cause: some upstream test mutates PyJWT's module-level `options` dict (most likely a permissive `jwt.decode(..., options={"verify_signature": False})` call somewhere in the auth-routes flow), and the mutation leaks into `decode_token` via Python's module-level import. The workaround in S-02 was to hard-code test ordering (`tests/test_auth_routes.py tests/test_security.py`) and disable `pytest-randomly` — but this is test-harness debt. S-03 adds more backend tests; the flake will worsen if left.

### 1.2 Detailed Requirements

- **R1 — Refactor `backend/app/core/security.py::decode_token`** to use a module-local `jwt.PyJWT()` instance instead of the module-level `jwt.decode` interface. This isolates Tee-Mo's decode path from any global mutation elsewhere in the process.
- **R2 — Add a module-local constant** `_JWT = jwt.PyJWT()` near the top of `security.py`, alongside the other module-level state.
- **R3 — Replace** `jwt.decode(token, ...)` inside `decode_token` with `_JWT.decode(token, ...)`. The rest of the function body (exception translation, claim checks) stays identical.
- **R4 — Add a regression-lock test** in `backend/tests/test_security.py` that:
  1. Takes a valid access token via `create_access_token(uuid)`
  2. Tampers the signature segment (flip last char)
  3. BEFORE calling `decode_token`, runs a permissive decode to mutate global PyJWT state: `jwt.decode(token, options={"verify_signature": False}, algorithms=[settings.jwt_algorithm])` — this is the mutation vector we're guarding against
  4. Calls `decode_token(tampered_token)` and asserts it raises `jwt.InvalidTokenError` (or a subclass)
  5. Works regardless of the module-level global state being poisoned
- **R5 — Verify stability**: run the full backend test suite 10 consecutive times with `pytest-randomly` active (no `-p no:randomly`). All 10 runs must pass 100%. Paste the output into the Dev report.
- **R6 — Update BUG-20260411 report** status: `Open` → `Fixed`. Add a note referencing `STORY-003-04` as the fix.

### 1.3 Out of Scope

- Filing an upstream PyJWT issue — this is a hackathon, we ship workarounds and move on.
- Refactoring `create_access_token` / `create_refresh_token` to use the same instance — they use `jwt.encode` which doesn't have the same global-state issue. Only `decode_token` needs the fix.
- Touching the test files that CAUSED the global mutation (wherever that is). The fix works regardless of the root cause, which is appropriate for a defensive refactor.

### TDD Red Phase: No

Rationale: The regression-lock test IS the test, and it's written in the same Green-phase story. TDD Red would just mean "write the test first" and that's built into the L1 workflow anyway. No separate Red phase.

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria

```gherkin
Feature: PyJWT decode isolation — BUG-20260411 fix

  Scenario: decode_token rejects a tampered token even after global options are poisoned
    Given a valid access token T for a random user_id
    And the token is tampered by flipping the last character of the signature segment
    And jwt.decode(T, options={"verify_signature": False}, algorithms=[settings.jwt_algorithm]) has been called to poison module-level PyJWT state
    When I call decode_token(tampered_token)
    Then jwt.InvalidTokenError (or subclass) is raised
    And the exception is NOT jwt.DecodeError with verify_signature=False behavior

  Scenario: Full test suite passes 10 consecutive runs with pytest-randomly active
    Given all S-02 and S-03 backend tests exist
    When I run `pytest tests/` 10 times in a row with pytest-randomly enabled
    Then every run passes 100%
    And test order varies between runs
    And no test is order-dependent

  Scenario: Existing 9 test_security.py scenarios still pass
    Given the decode_token refactor is applied
    When I run `pytest tests/test_security.py -v`
    Then all 9 original tests pass + 1 new regression-lock test = 10 tests
    And no test requires ordering hints
```

### 2.2 Verification Steps (Manual)

- [ ] `cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/test_security.py -v` shows 10 tests passing (9 original + 1 regression-lock)
- [ ] Run the full suite 10 times:
  ```bash
  cd backend
  VENV=/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python
  for i in 1 2 3 4 5 6 7 8 9 10; do
    echo "=== Run $i ==="
    $VENV -m pytest tests/ -q || { echo "FAILED on run $i"; exit 1; }
  done
  echo "All 10 runs passed"
  ```
  Expected: "All 10 runs passed".
- [ ] Confirm `pytest-randomly` is active in the test run: look for `Using --randomly-seed=...` in the pytest header.
- [ ] Manual code inspection: `grep -n 'PyJWT()' backend/app/core/security.py` shows the module-local `_JWT` instance. `grep -n 'jwt\.decode' backend/app/core/security.py` shows NO hits inside `decode_token` (decode is now via `_JWT.decode`).

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **STORY-003-03** | Migrations applied; test suite now has the 6-table health test | [ ] |
| **Python venv** | `backend/.venv` has `PyJWT==2.12.1` (from S-01 pin) | [x] |
| **Test suite baseline** | 22 backend tests passing (9 security + 13 auth routes) from S-02 | [x] |

### 3.1 `backend/app/core/security.py` — exact diff

```diff
 from datetime import datetime, timedelta, timezone
 from uuid import UUID

 import bcrypt
 import jwt
+from jwt.api_jwt import PyJWT

 from app.core.config import settings

+# Module-local PyJWT instance — isolates our decode path from any global
+# mutation of jwt.api_jwt._jwt_global_obj (BUG-20260411). A permissive
+# jwt.decode(..., options={"verify_signature": False}) elsewhere in the
+# process mutates module-level state and can leak into jwt.decode here;
+# using a dedicated instance avoids that shared-options footgun.
+_JWT = PyJWT()

 # ... hash_password, verify_password, create_access_token, create_refresh_token unchanged ...

 def decode_token(token: str) -> dict:
     """
     Decode and verify a JWT token using the Tee-Mo JWT secret.

     ...existing docstring...
     """
-    return jwt.decode(
+    return _JWT.decode(
         token,
         settings.supabase_jwt_secret,
         algorithms=[settings.jwt_algorithm],
     )
```

Leave `hash_password`, `verify_password`, `create_access_token`, `create_refresh_token`, `validate_password_length` untouched. Only `decode_token` changes.

### 3.2 `backend/tests/test_security.py` — add regression-lock test

Append to the end of the file:

```python
def test_decode_token_resists_global_options_poison():
    """
    Regression lock for BUG-20260411: PyJWT module-level options leak.

    Some test paths call jwt.decode(options={"verify_signature": False}) which
    mutates module-level PyJWT state. If decode_token uses the module-level
    jwt.decode, the mutation leaks in and tampered tokens slip through.

    decode_token must use a dedicated jwt.PyJWT() instance so it is isolated
    from the global mutation. This test verifies the isolation.
    """
    import jwt as jwt_module

    # Step 1: build a tampered token
    token = create_access_token(uuid4())
    head, body, sig = token.split(".")
    flipped = "A" if sig[-1] != "A" else "B"
    tampered = f"{head}.{body}.{sig[:-1]}{flipped}"

    # Step 2: poison module-level PyJWT state by calling the module-level
    # jwt.decode with verify_signature=False. This mirrors the exact mutation
    # pattern observed during S-02 post-merge validation.
    try:
        jwt_module.decode(
            token,
            options={"verify_signature": False},
            algorithms=[settings.jwt_algorithm],
        )
    except Exception:
        pass  # We don't care whether this raises; we only care about the side effect.

    # Step 3: decode_token MUST still reject the tampered token despite the
    # poisoned global state. This is the isolation guarantee.
    with pytest.raises(jwt_module.InvalidTokenError):
        decode_token(tampered)
```

### 3.3 Run stability verification

After landing the diff + test, run:

```bash
cd backend
VENV=/Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== Run $i ==="
  $VENV -m pytest tests/ -q 2>&1 | tail -5
done
```

Paste the full output (30 lines max) into the Dev report under `## Stability Verification`.

### 3.4 Update the BUG report

Edit `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md`:

```diff
 ---
 bug_id: "BUG-20260411-pyjwt-test-ordering"
-status: "Open"
+status: "Fixed"
 severity: "Low"
 found_during: "Sprint S-02 — STORY-002-04 post-merge validation and S-02 Integration Audit"
 affected_story: "STORY-002-01-security_primitives (test_security.py) and/or STORY-002-02-auth_routes (test_auth_routes.py)"
-reporter: "DevOps agent + Architect integration audit"
+reporter: "DevOps agent + Architect integration audit"
+fixed_in: "STORY-003-04 (Sprint S-03)"
 ---
```

Add a new section at the end:

```markdown
## Resolution (2026-04-12 — STORY-003-04)

Migrated `backend/app/core/security.py::decode_token` to use a module-local
`jwt.PyJWT()` instance via `from jwt.api_jwt import PyJWT; _JWT = PyJWT()`.
The decode path is now isolated from any global mutation of
`jwt.api_jwt._jwt_global_obj.options` elsewhere in the process.

Added `test_decode_token_resists_global_options_poison` regression-lock test
in `backend/tests/test_security.py` that explicitly poisons module-level PyJWT
options before calling `decode_token` on a tampered token, and asserts the
tampered token is still rejected.

Verification: `pytest tests/` passed 10 consecutive runs with `pytest-randomly`
active, no explicit ordering required.
```

### 3.5 Files to Modify

| File | Change |
|------|--------|
| `backend/app/core/security.py` | **EDIT** — add `_JWT = PyJWT()`, use in `decode_token` |
| `backend/tests/test_security.py` | **EDIT** — add 1 regression-lock test |
| `product_plans/backlog/EPIC-002_auth/BUG-20260411-pyjwt-test-ordering.md` | **EDIT** — status Open → Fixed + resolution section |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 1 new | Regression-lock for PyJWT isolation |
| Component tests | 0 — N/A | |
| E2E / acceptance tests | 0 — N/A | |
| Integration tests | 0 — N/A | |

Total test count after this story: `test_security.py` 9 → 10 tests. Cumulative backend suite: 22 → 23 tests (+ whatever STORY-003-03 added to health-DB test, so actual cumulative is 23-24).

### 4.2 Definition of Done

- [ ] `_JWT = PyJWT()` instance exists at module level in `security.py`.
- [ ] `decode_token` calls `_JWT.decode(...)`, not `jwt.decode(...)`.
- [ ] `test_decode_token_resists_global_options_poison` exists and passes.
- [ ] All 9 original `test_security.py` tests still pass.
- [ ] `pytest tests/` passes 10 consecutive runs with `pytest-randomly` active.
- [ ] BUG-20260411 report updated: status Fixed + resolution section added.
- [ ] Dev report includes the 10-run stability verification output.
- [ ] No explicit test ordering (`-p no:randomly` or specific argument ordering) is needed to pass the suite anymore.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 45 | 4,348 | 4,393 |
