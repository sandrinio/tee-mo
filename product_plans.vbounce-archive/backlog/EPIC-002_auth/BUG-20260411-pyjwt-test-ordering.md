---
bug_id: "BUG-20260411-pyjwt-test-ordering"
status: "Fixed"
severity: "Low"
found_during: "Sprint S-02 — STORY-002-04 post-merge validation and S-02 Integration Audit"
affected_story: "STORY-002-01-security_primitives (test_security.py) and/or STORY-002-02-auth_routes (test_auth_routes.py)"
reporter: "DevOps agent + Architect integration audit"
fixed_in: "STORY-003-04 (Sprint S-03)"
---

# BUG: PyJWT module-level options leak causes test-order-dependent failure in `test_decode_token_rejects_tampered_signature`

## 1. The Bug

**Current Behavior:**
Running `pytest tests/test_security.py tests/test_auth_routes.py -v -p no:randomly` (STORY-002-01 suite first, then STORY-002-02 suite) produces 22/22 passed on a cold venv, but on some subsequent runs `test_security.py::test_decode_token_rejects_tampered_signature` fails because `decode_token(tampered_token)` returns a decoded payload instead of raising `jwt.InvalidTokenError`. The failure only appears when a test in `test_auth_routes.py` has previously exercised the auth-route `/me` path with an expired token (`test_me_with_expired_access_cookie`).

Concretely, the DevOps post-merge gate for STORY-002-04 hit this exact order-sensitive failure on `sprint/S-02`. Swapping the argument order (`pytest tests/test_auth_routes.py tests/test_security.py`) made the suite pass deterministically.

**Expected Behavior:**
`test_decode_token_rejects_tampered_signature` should ALWAYS raise `jwt.InvalidTokenError` (or a subclass) when given a token with a corrupted signature segment, regardless of which other tests ran before it.

**Reproduction Steps:**
1. Fresh `sprint/S-02` checkout, clean `backend/.venv`.
2. `cd backend && /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python -m pytest tests/test_security.py tests/test_auth_routes.py -v -p no:randomly`
3. Observe: `test_decode_token_rejects_tampered_signature` fails on the tampered-signature assertion.
4. Same command with `tests/test_auth_routes.py tests/test_security.py` (swapped order) → 22/22 passed.
5. Enable `pytest-randomly` and run 10 times → intermittent failures correlated with auth-routes running before security.

**Environment:**
- Python 3.11.15
- PyJWT 2.12.1 (Charter §3.2 pin)
- fastapi 0.135.3, fastapi TestClient + httpx
- Branch: `sprint/S-02` (at merge commit `f88c7f9` and later)

---

## 2. Impact

- **Blocking?** No — **production code is unaffected**. This is strictly a test-harness hygiene issue.
- **Affected Areas:** `backend/tests/test_security.py::test_decode_token_rejects_tampered_signature`. The bug only surfaces in specific test orderings.
- **Users Affected:** None in production. Affects CI reliability and developer trust in `pytest -p randomly`.
- **Data Impact:** None.
- **Sprint impact:** Worked around in S-02 post-merge gates by running suites in a known-good order (`-p no:randomly` + explicit order `auth_routes security`). The workaround is documented in STORY-002-04's DevOps merge task file and in the S-02 integration audit.

---

## 3. Fix Approach

**Root Cause (hypothesized):**
PyJWT 2.x stores its default decode options on a module-level singleton (`jwt.api_jwt._jwt_global_obj`). Calls like `jwt.decode(token, options={"verify_signature": False}, ...)` mutate that singleton in some execution paths, and the mutation leaks into subsequent `jwt.decode` calls from unrelated code. Our `app.core.security.decode_token` uses the module-level `jwt.decode` interface, so any upstream test or production path that went permissive can poison it for every caller until the process restarts.

`test_me_with_expired_access_cookie` in `test_auth_routes.py` manually crafts an expired token with `jwt.encode(...)` and sets it on the TestClient cookie jar. That path itself looks clean. The leak is likely inside `get_current_user_id` or `decode_token`'s error handling — worth tracing with a sentinel test that asserts the global options dict state before/after each module's tests.

**Proposed Fix (one of the following — pick during implementation):**

1. **(Preferred)** Refactor `backend/app/core/security.py::decode_token` to construct a scoped `jwt.PyJWT()` instance per call, instead of calling the module-level `jwt.decode`:
   ```python
   import jwt
   from jwt.api_jwt import PyJWT
   _JWT = PyJWT()  # module-local instance, not the library-global

   def decode_token(token: str) -> dict:
       return _JWT.decode(
           token,
           settings.supabase_jwt_secret,
           algorithms=[settings.jwt_algorithm],
       )
   ```
   This isolates Tee-Mo's decode path from any global mutation elsewhere in the process.

2. **(Fallback)** Add a session-scoped autouse pytest fixture that resets `jwt.api_jwt._jwt_global_obj` between test modules. This treats the symptom but leaves production code using the module-level interface.

3. **(Upstream)** File an issue against PyJWT 2.x documenting the non-obvious global mutation and request module-level state isolation. Not exclusive of (1).

**Files to Modify:**
- `backend/app/core/security.py` — migrate `decode_token` to the scoped `PyJWT()` instance.
- `backend/tests/test_security.py` — add a test that runs `jwt.decode(..., options={"verify_signature": False})` in a setup step and asserts the next `decode_token` call still rejects a tampered signature. This locks the fix in place.
- Optionally `backend/tests/conftest.py` — if we go the fixture route.

**Complexity:** L1 (Trivial) — ~1 hour. Single-file production change, one new test, one regression-lock test. No schema changes, no API contract changes.

> Per the template note: **L1 complexity → candidate for `.vbounce/templates/hotfix.md` instead of a full BUG story.** Team Lead recommends keeping this as a BUG (not a hotfix) because it requires a small design decision (option 1 vs 2 vs both) that benefits from sprint planning scrutiny rather than ad-hoc resolution.

---

## 4. Verification

- [ ] Reproduction step 2 (`pytest tests/test_security.py tests/test_auth_routes.py -v -p no:randomly`) passes 22/22 — the original failing order.
- [ ] Reproduction step 4 (swapped order) still passes 22/22 — no regression.
- [ ] With `pytest-randomly` enabled, the full suite passes 10 consecutive runs (use `for i in 1 2 3 4 5 6 7 8 9 10; do pytest tests/; done`).
- [ ] New sentinel test in `test_security.py` verifies that mutating global PyJWT options in one call does NOT leak into a subsequent `decode_token` call.
- [ ] Existing 22 tests still pass without changes to their bodies.
- [ ] `.worktrees/STORY-XXX/.vbounce/reports/STORY-XXX-dev-green.md` for whichever sprint picks this up — must paste the 10-run loop output.

---

## Resolution (2026-04-12 — STORY-003-04)

Migrated `backend/app/core/security.py::decode_token` to use a module-local
`jwt.PyJWT()` instance via `from jwt.api_jwt import PyJWT; _JWT = PyJWT()`.
The decode path is now isolated from any global mutation of
`jwt.api_jwt._jwt_global_obj.options` elsewhere in the process.

Added `test_decode_token_resists_global_options_poison` regression-lock test
in `backend/tests/test_security.py` that explicitly poisons module-level PyJWT
options before calling `decode_token` on a tampered token, and asserts the
tampered token is still rejected.

Verification: `pytest tests/` passed 10 consecutive runs with the full backend
suite (33 tests: 13 auth routes + 1 health + 9 health_db + 9 security + 1 new
regression-lock), no explicit ordering required.

## Change Log

| Date | Change | By |
|------|--------|-----|
| 2026-04-11 | BUG filed at S-02 close. Workaround (explicit test ordering) in place for sprint/S-02 and main post-release. Queued for S-03 planning. | Team Lead |
| 2026-04-12 | Fixed in STORY-003-04 (Sprint S-03). `decode_token` migrated to `_JWT = PyJWT()` instance. Regression-lock test added. 10-run stability verified. | Developer agent |
