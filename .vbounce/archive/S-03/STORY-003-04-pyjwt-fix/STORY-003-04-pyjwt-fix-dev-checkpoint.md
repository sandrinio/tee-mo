# Developer Checkpoint: STORY-003-04-pyjwt-fix

## Completed
- Read FLASHCARDS.md — no relevant constraints for this task
- Read story spec §3.1, §3.2, §3.4 verbatim
- Read current security.py and test_security.py
- Task 1: Edited backend/app/core/security.py — added `from jwt.api_jwt import PyJWT`, `_JWT = PyJWT()`, changed `decode_token` to use `_JWT.decode`
- Task 2: Appended `test_decode_token_resists_global_options_poison` to test_security.py verbatim from spec §3.2
- Task 3: Full suite verification — 33 passed
- Task 4: 10-run stability loop — all 10 runs passed 33 tests

## Remaining
- Task 5: Update BUG-20260411 report (status Open → Fixed + resolution section)
- Task 6: Write dev report

## Key Decisions
- `_JWT = PyJWT()` creates an isolated instance with its own options dict and its own `_jws = PyJWS()`. This is isolated from `jwt.api_jwt._jwt_global_obj` and `jwt.api_jws._jws_global_obj`.
- pytest-randomly is NOT installed in the backend venv; 10-run stability was verified with natural pytest ordering (auth_routes alphabetically before security, which is the problematic order).
- Full suite is 33 tests (not 32 as story predicted) because STORY-003-03 added 9 health_db tests rather than the expected 9 health tests.

## Files Modified
- backend/app/core/security.py — added PyJWT import, _JWT instance, changed decode_token
- backend/tests/test_security.py — appended regression-lock test
