---
story_id: "STORY-005A-04"
agent: "architect"
status: "PASS"
adr_compliance: "ADR-001/002/010/021/024/025 all clean (6/6)"
bounce_count: 0
safe_zone_score: 10
ai_isms_detected: 0
regression_risk: "Low"
risks_for_phase_b:
  - "TOCTOU window on different-owner check — mitigate with ON CONFLICT WHERE owner_user_id=EXCLUDED.owner_user_id or a BEFORE UPDATE trigger rejecting owner_user_id mutation"
  - "oauth.v2.access response not Pydantic-validated — schema drift would degrade to generic error redirect without a clear log line"
  - "Coalesced missing-field warning — split into 3 per-field warnings for ops diagnostics"
  - "Brittle httpx monkeypatch — migrate to Depends(get_http_client) when app/core/http.py lands"
  - "No retry/backoff + no resp.status_code check before resp.json() — transient Slack 5xx will raise JSONDecodeError → 500. RISK REGISTRY candidate."
flashcards_approved:
  - "httpx.AsyncClient first use — import at module level for test monkeypatchability; migrate to Depends(get_http_client) when app/core/http.py lands"
  - "Supabase .upsert() — omit DEFAULT NOW() columns from payload to preserve original timestamps; applies to teemo_slack_teams.installed_at and any future ADR-024 tables"
flashcards_rejected:
  - "get_current_user_id_optional narrow catch — Python 101 generic hygiene, convert to inline comment at deps.py:88 instead"
template_version: "2.0"
---

# Architect Audit — STORY-005A-04 Slack OAuth Callback

## Verdict: PASS

L3 Full Bounce story passes Architect review on first Architect bounce. QA's 3 non-blocking recommendations confirmed as non-blocking. No ADR violations, no layering breaks, no token-leak compositions. Ready for DevOps merge to `sprint/S-04`.

## ADR Compliance Table

| ADR | Area | Verdict | Evidence |
|---|---|---|---|
| ADR-001 | JWT auth reuse | PASS | Callback uses `get_current_user_id_optional` → `decode_token` → `_JWT.decode` (security.py:149). Slack state token signed with same `supabase_jwt_secret` but namespaced by `aud="slack-install"` (security.py:186). No parallel auth stack. |
| ADR-002 | AES-256-GCM | PASS | Calls `encrypt(bot_token)` from `app.core.encryption` (slack_oauth.py:27, 201). Nonce is 12 random bytes per-call (encryption.py:59). No rolled crypto. |
| ADR-010 | Slack bot token encrypted at rest | PASS | Upsert writes `encrypted_slack_bot_token` (slack_oauth.py:207). Plaintext `bot_token` local never assigned to a dict field or interpolated into a log line. Only logger match is a field-name string literal (slack_oauth.py:178). |
| ADR-021 | 7-scope event surface | PASS | No `slack_bolt` handler registration in this story. `bot_user_id` persisted correctly for ADR-021 self-message filter in Phase B. |
| ADR-024 | 1 user : N SlackTeams | PASS | Upsert at slack_oauth.py:202-209 uses `slack_team_id` as PK, `owner_user_id` as FK to `teemo_users`. Different-owner 409 gate at 190-194 enforces 1-owner-per-team invariant in code (RLS disabled per migration:31). |
| ADR-025 | channels:read + groups:read | PASS | Both scopes present in `SLACK_SCOPES` tuple (slack_oauth.py:38-39). |

## Architectural Observations

1. **Single-import-point rule respected.** No `slack_bolt`/`slack_sdk` imports in the callback. The OAuth flow intentionally bypasses `slack_bolt.oauth_flow` because we don't want its installation store / success handler.
2. **First-party httpx is a clean seed pattern.** Module-level `import httpx` required for test monkeypatching (documented in a comment at line 17). Timeout 10s is appropriate for an OAuth code exchange (single-use code → no retry). Phase B recommendation: when a 2nd httpx use-case lands, extract `app/core/http.py`.
3. **Layering is unidirectional.** `slack_oauth.py` → `deps`, `config`, `db`, `encryption`, `security`. No reverse flow. `security.py::verify_slack_state_token` does a late import of `SlackInstallState` to avoid the known STORY-005A-03 circular dep — not a new violation.
4. **Error surface matches spec exactly.** 5 redirect branches + 3 hard-fail branches + 2 error-redirects. Traced top-to-bottom: `cancelled` (132), 400 missing (136), `expired` (142), 400 invalid (144), `session_lost` (148), 403 mismatch (152), `error` ok=false (172), `error` missing fields (179), 409 different owner (191), `ok` success (211). No silent exception swallowing.
5. **`get_current_user_id_optional` is scoped precisely** — catches `HTTPException` only, not bare `Exception`. Genuine server errors still propagate to FastAPI's 500 handler instead of masking as session-lost.

## Phase B Risks (Carry Forward)

1. **TOCTOU on different-owner check** — SELECT → upsert is not atomic under concurrent same-team installs by different users. Acceptable for hackathon; fix with `ON CONFLICT (slack_team_id) DO UPDATE ... WHERE teemo_slack_teams.owner_user_id = EXCLUDED.owner_user_id` when 005A-04 goes into hardening.
2. **Unvalidated oauth.v2.access response** — schema drift would degrade silently. Fix: introduce `OAuthV2AccessResponse` Pydantic model.
3. **Coalesced missing-field warning** — 3-line refactor, defer to Phase B ops hardening.
4. **Brittle httpx monkeypatch** — migrate to dependency injection when `app/core/http.py` extraction happens.
5. **No retry + no resp.status_code check before resp.json()** — a transient Slack 503 with HTML body will raise `JSONDecodeError` → 500 instead of redirecting to `slack_install=error`. **RISK REGISTRY candidate** — the most likely real-world failure mode during the hackathon demo if Slack is flaky.

## Trend Check

Consistent with STORY-005A-01/02/03 on all 5 dimensions: settings access, Supabase access, JWT exception handling, logging pattern, state-token audience namespacing. No style drift, no parallel abstractions.

## Flashcard Decisions

| # | Candidate | Decision | Rationale |
|---|---|---|---|
| 1 | httpx.AsyncClient monkeypatch requires module-level `import httpx` | APPROVE | First-use pattern, concrete rule, will bite the next httpx-using story |
| 2 | Supabase `.upsert()` — omit DEFAULT NOW() columns | APPROVE | First `.upsert()` use. Non-obvious gotcha — PostgREST's `Prefer: resolution=merge-duplicates` sets every field passed, including DEFAULT columns. Applies to all ADR-024 tables going forward. |
| 3 | `get_current_user_id_optional` narrow catch | REJECT | Python 101 generic hygiene. Convert to inline comment at deps.py:88. |

Net: 2 approved, 1 rejected → 2 flashcards to present at sprint close per flashcard batching policy.
