---
story_id: "STORY-005A-05-teams-list-endpoint"
parent_epic_ref: "EPIC-005-phase-a"
status: "Draft"
ambiguity: "🟢 Low"
context_source: "Epic §2, §8 Q6 (decided 2026-04-12) / Codebase"
actor: "Developer Agent"
complexity_label: "L1"
---

# STORY-005A-05: `GET /api/slack/teams` — List User's Installed Teams

**Complexity: L1** — Trivial, single file modify, known pattern (auth-required GET, Supabase select, Pydantic response model). The encrypted token MUST NOT appear in the response — that's the only non-trivial concern.

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As an **authenticated Tee-Mo user**,
> I want to **fetch the list of Slack teams I've installed**,
> So that **the `/app` dashboard can render a list of cards** (consumed by STORY-005A-06).

### 1.2 Detailed Requirements

- **Req 1 — Endpoint shape:** `GET /api/slack/teams` in `backend/app/api/routes/slack_oauth.py` (modify — add a third route alongside `/install` and `/oauth/callback`).
- **Req 2 — Auth required:** Use `get_current_user_id` dep. Anonymous → 401.
- **Req 3 — Query:** `SELECT slack_team_id, slack_bot_user_id, installed_at FROM teemo_slack_teams WHERE owner_user_id = $1 ORDER BY installed_at DESC` via the Supabase client.
- **Req 4 — Response model:** Add `SlackTeamResponse` to `backend/app/models/slack.py`:
  ```python
  class SlackTeamResponse(BaseModel):
      slack_team_id: str
      slack_bot_user_id: str
      installed_at: datetime
  ```
- **Req 5 — Response shape:** `{"teams": [SlackTeamResponse, ...]}` (wrapped in an object so future fields can be added without breaking the API contract).
- **Req 6 — `encrypted_slack_bot_token` MUST NEVER be in the response.** Not in any field, not in any nested object, not as a debug log. Test for this explicitly.
- **Req 7 — Empty list is valid:** A user with zero installed teams gets `{"teams": []}` and HTTP 200, NOT 404.

### 1.3 Out of Scope
- Decrypting the bot token to call any Slack API — Phase B (event handlers will need this; not yet).
- Returning team display name — would require an extra Slack API call (`team.info`); deferred until S-05 if needed for the workspace cards.
- Pagination — a single user owning >50 Slack teams in the hackathon is impossible.
- Per-team workspace nesting — S-05 / EPIC-003 Slice B.

### TDD Red Phase: Yes

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin)
```gherkin
Feature: List user's installed Slack teams

  Background:
    Given alice is logged in with id "alice-uuid"

  Scenario: empty list
    Given no teemo_slack_teams rows exist for alice
    When GET /api/slack/teams with alice's cookie
    Then the response status is 200
    And the response body is {"teams": []}

  Scenario: single team
    Given alice has one row: slack_team_id="T1", slack_bot_user_id="UBOT1", encrypted_slack_bot_token="<ciphertext>"
    When GET /api/slack/teams with alice's cookie
    Then the response status is 200
    And the response body has teams[0].slack_team_id = "T1"
    And teams[0].slack_bot_user_id = "UBOT1"
    And teams[0] has an installed_at field
    And teams[0] does NOT contain "encrypted_slack_bot_token"
    And the entire response body, serialized, does NOT contain the ciphertext

  Scenario: only my teams
    Given alice owns team T1, and bob owns team T2
    When alice GETs /api/slack/teams
    Then the response contains exactly 1 team with slack_team_id="T1"
    And it does NOT contain T2

  Scenario: anonymous → 401
    Given no auth cookie
    When GET /api/slack/teams
    Then the response status is 401

  Scenario: ordering — newest first
    Given alice owns 3 teams installed at t1 < t2 < t3
    When alice GETs /api/slack/teams
    Then the response.teams[0] is the one installed at t3
    And response.teams[2] is the one installed at t1
```

### 2.2 Verification Steps (Manual)
- [ ] `cd backend && uv run pytest tests/test_slack_teams_list.py -v`
- [ ] After STORY-005A-04 lands and a real install exists, `curl -b "access_token=<jwt>" https://teemo.soula.ge/api/slack/teams` returns the installed team.

---

## 3. The Implementation Guide

### 3.0 Environment Prerequisites
| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-005A-03 (slack_oauth.py file exists, models/slack.py exists, router registered) | [ ] |
| **Test fixtures** | Need to seed `teemo_slack_teams` rows in tests with valid encrypted tokens — call `encrypt("xoxb-fake")` from the test setup. | [ ] |

### 3.1 Test Implementation
- Create `backend/tests/test_slack_teams_list.py`.
- 5 tests (one per scenario).
- Use the same DB cleanup pattern as `test_slack_oauth_callback.py` (delete by `slack_team_id` prefix `T_LIST_*`).
- For the "no ciphertext in response" assertion, use:
  ```python
  body_text = json.dumps(response.json())
  assert "encrypted" not in body_text.lower()
  assert ciphertext not in body_text
  ```

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary Files** | `backend/app/api/routes/slack_oauth.py` (MODIFY — add `GET /teams`) |
| **Related Files** | `backend/app/models/slack.py` (MODIFY — add `SlackTeamResponse`), `backend/app/core/db.py` (READ) |
| **New Test Files** | `backend/tests/test_slack_teams_list.py` |
| **ADR References** | ADR-010 (token never plaintext — extends to "never in API responses either") |
| **First-Use Pattern** | No — straight Supabase select + Pydantic response. |

### 3.3 Technical Logic

```python
@router.get("/teams")
async def list_slack_teams(user_id: str = Depends(get_current_user_id)):
    sb = get_supabase()
    result = (
        sb.table("teemo_slack_teams")
        .select("slack_team_id, slack_bot_user_id, installed_at")  # explicit columns — no token
        .eq("owner_user_id", user_id)
        .order("installed_at", desc=True)
        .execute()
    )
    return {"teams": [SlackTeamResponse(**row) for row in (result.data or [])]}
```

**Critical:** the `.select(...)` MUST list columns explicitly. Do NOT use `.select("*")` here — that would pull `encrypted_slack_bot_token` into memory and risk it leaking via a future refactor or debug log. Defense in depth.

### 3.4 API Contract

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/api/slack/teams` | GET | Auth cookie | None | 200 `{"teams": [{"slack_team_id": "T...", "slack_bot_user_id": "U...", "installed_at": "2026-..."}]}`. 401 if anonymous. |

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations
| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 0 — N/A | |
| Integration tests | 5 | One per Gherkin scenario |
| Component tests | 0 — N/A | |
| E2E / acceptance | 1 manual curl | Post-merge sanity |

### 4.2 Definition of Done
- [ ] TDD Red phase enforced — all 5 scenarios written failing first.
- [ ] §4.1 minimum counts met.
- [ ] Token-leakage assertion passes (no "encrypted" substring in any response).
- [ ] `.select()` uses explicit column list, not `*`.
- [ ] No ADR violations.

---

## Token Usage
| Agent | Input | Output | Total |
|-------|-------|--------|-------|
