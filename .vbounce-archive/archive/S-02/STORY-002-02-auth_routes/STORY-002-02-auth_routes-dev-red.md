---
story_id: "STORY-002-02-auth_routes"
agent: "developer"
phase: "red"
bounce: 1
started_at: "2026-04-11T00:00:00Z"
completed_at: "2026-04-11T00:30:00Z"
files_modified:
  - "backend/tests/test_auth_routes.py"
tests_written: 13
tests_passing: 0
tests_failing: 13
correction_tax_pct: 0
flashcards_flagged: []
input_tokens: 73
output_tokens: 43091
total_tokens: 43164
---

# Developer Red Phase Report: STORY-002-02-auth_routes

## Summary

Wrote 13 pytest test functions covering all Gherkin scenarios in STORY-002-02 §2.1. The test file imports from `app.api.routes.auth`, `app.models.user`, and `app.api.deps` — none of which exist yet. pytest collection fails immediately with `ModuleNotFoundError: No module named 'app.api'`, confirming all 13 tests are in the failing set for the correct reason. No implementation code was written.

## Files Modified

- `backend/tests/test_auth_routes.py` — new file, 13 test functions, one per Gherkin scenario.

## Test Coverage Map

| # | Gherkin Scenario | pytest Function |
|---|-----------------|-----------------|
| 1 | Register happy path with auto-login | `test_register_happy_path` |
| 2 | Register with 73-byte password | `test_register_73_byte_password` |
| 3 | Register with duplicate email | `test_register_duplicate_email` |
| 4 | Register with malformed email | `test_register_malformed_email` |
| 5 | Login happy path | `test_login_happy_path` |
| 6 | Login with wrong password | `test_login_wrong_password` |
| 7 | Login with unknown email | `test_login_unknown_email` |
| 8 | GET /me with valid access cookie | `test_me_with_valid_access_cookie` |
| 9 | GET /me without cookie | `test_me_without_cookie` |
| 10 | GET /me with expired access cookie | `test_me_with_expired_access_cookie` |
| 11 | Refresh happy path | `test_refresh_happy_path` |
| 12 | Refresh with an access token in the refresh slot | `test_refresh_with_access_token_in_refresh_slot` |
| 13 | Logout clears cookies | `test_logout_clears_cookies` |

## Fixture Design

**`unique_email` fixture:**
- Generates `test+{uuid4}@teemo.test` on each test invocation (function scope, default).
- `yield`s the email string to the test.
- Teardown calls `get_supabase().table("teemo_users").delete().eq("email", email).execute()` unconditionally — if the test never inserted a row, the delete is a no-op.
- All tests that touch the DB receive this fixture. Tests 4, 7, and 9 do not receive it because they never insert a row.

**`client` fixture:**
- Returns `TestClient(app)` — a fresh HTTPX-backed test client wrapping `app.main.app`.
- The client stores cookies between calls within the same test (important for multi-step tests like Scenarios 1, 8, 11, 13 where register sets cookies that subsequent calls in the same test use automatically).
- For scenarios that need a clean cookie slate (Scenarios 5 and 12), a new `TestClient(app)` is instantiated inline within the test itself to avoid cookie bleed-over.

**Expired token (Scenario 10):**
- Uses `jwt.encode` directly with `exp` set to 1 second in the past, signing with `settings.supabase_jwt_secret` and `settings.jwt_algorithm` — the same pattern from `test_security.py::test_decode_token_rejects_expired_token`.
- Sets the expired token via `client.cookies.set("access_token", expired_token)` after a register call (which populates the `unique_email` row for teardown purposes).

**Access-token-in-refresh-slot (Scenario 12):**
- Registers first to get a valid access_token cookie value.
- Extracts `client.cookies.get("access_token")` and places it as the `refresh_token` cookie on a fresh client instance.
- Asserts 401 with `"Invalid token type"` — the handler checks `payload.get("type") != "refresh"` (access tokens have no `type` claim).

## Red Output

```
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.0.3, pluggy-1.6.0 -- /Users/ssuladze/Documents/Dev/SlaXadeL/backend/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-002-02-auth_routes/backend
configfile: pyproject.toml
plugins: logfire-4.32.0, anyio-4.13.0
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
__________________ ERROR collecting tests/test_auth_routes.py __________________
ImportError while importing test module '/Users/ssuladze/Documents/Dev/SlaXadeL/.worktrees/STORY-002-02-auth_routes/backend/tests/test_auth_routes.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/opt/homebrew/Cellar/python@3.11/3.11.15/Frameworks/Python.framework/Versions/3.11/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
tests/test_auth_routes.py:42: in <module>
    from app.api.routes.auth import router as auth_router  # noqa: F401 — must fail in Red
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   ModuleNotFoundError: No module named 'app.api'
=========================== short test summary info ============================
ERROR tests/test_auth_routes.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.74s ===============================
```

All 13 tests are in the failing set — the collection error prevents any test from running, which is the correct Red failure mode. The error is `ModuleNotFoundError: No module named 'app.api'` on the first missing import line.

## Concerns

None. No test accidentally passes. The collection error is exactly what is expected in Red phase — the first missing import terminates collection before any test function can be discovered or executed. The remaining missing modules (`app.models.user`, `app.api.deps`) would produce the same failure type if the first import were somehow available.

One design choice to flag for the Team Lead: Scenarios 5 and 12 create a second `TestClient(app)` inline to avoid cookie bleed-over from the register call in the same test. This is intentional and correct — the fixture-level `client` carries cookies across calls, so login/refresh tests that need a clean cookie state must use a fresh client. The Green phase Developer should not change this pattern.

## Process Feedback

- The story spec §3.1 fixture skeleton was provided verbatim and matched exactly what is needed — zero deviation required. Good template quality.
- Reading `test_security.py` before writing tests was essential: it shows the exact `jwt.encode` pattern for crafting expired tokens, avoiding any temptation to add `freezegun`.
- The `get_list("set-cookie")` method on TestClient response headers is the correct way to inspect multiple Set-Cookie headers. The story instructions mentioned this pattern; it was followed.
- Token tracking script ran successfully.
