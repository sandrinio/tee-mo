---
story_id: "STORY-006-11"
parent_epic_ref: "EPIC-006"
status: "Shipped"
ambiguity: "🟢"
context_source: "PROPOSAL-001-teemo-platform.md"
complexity_label: "L2"
parallel_eligible: false
expected_bounce_exposure: "low"
approved: true
created_at: "2026-04-10T00:00:00Z"
updated_at: "2026-04-13T00:00:00Z"
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
> **Ported from V-Bounce (shipped).** Original: `product_plans.vbounce-archive/archive/epics/EPIC-006_google_drive/STORY-006-11-reindex.md`. Shipped in sprint S-08, carried forward during ClearGate migration 2026-04-24.

# STORY-006-11: Re-Index Existing Files

**Complexity: L2** — 1 backend endpoint + 1 frontend button + hooks, known pattern, ~2-4hr

---

## 1. The Spec (The Contract)

### 1.1 User Story
> As a **Workspace Admin**,
> I want to re-index all my Drive files with the improved extractors,
> So that existing files get accurate markdown extraction, fresh AI descriptions, and cached content.

### 1.2 Detailed Requirements

- **R1: Backend endpoint** — `POST /api/workspaces/{workspace_id}/knowledge/reindex` triggers re-extraction of all indexed files in the workspace.
- **R2: Per-file re-processing** — For each file in `teemo_knowledge_index`:
  1. Fetch fresh content from Drive API (using stored refresh token)
  2. Extract using the improved extractors (pymupdf4llm, markdown tables, etc.)
  3. Compute new content hash
  4. Re-generate AI description using scan-tier model
  5. Update `cached_content`, `content_hash`, `ai_description`, `last_scanned_at` in the DB
- **R3: Owner-only** — Only the workspace owner can trigger re-index. Returns 404 for non-owners.
- **R4: BYOK required** — Returns 400 if no BYOK key configured (scan-tier LLM needed for AI descriptions).
- **R5: Drive required** — Returns 400 if Drive not connected (need refresh token to fetch files).
- **R6: Response** — Returns a summary: `{ "reindexed": N, "failed": N, "errors": [...] }`. Files that fail (revoked access, deleted from Drive) are reported but don't abort the whole operation.
- **R7: Sequential processing** — Files are processed one at a time (not parallel) to avoid BYOK rate limits and Drive API quotas.
- **R8: Frontend** — "Re-index All Files" button on the workspace detail page (in the knowledge/files section). Shows a loading spinner during re-index. On completion, refreshes the knowledge list to show updated AI descriptions.
- **R9: API client + hook** — Add `reindexKnowledge(workspaceId)` to `api.ts`. Add `useReindexKnowledgeMutation` to `useKnowledge.ts`. Invalidate knowledge list query on success.

### 1.3 Out of Scope
- Per-file re-index (only bulk re-index all files)
- Background/async re-index with progress updates — runs synchronously in the request for V1
- Automatic re-index on extractor upgrade (manual trigger only)
- Re-index from Slack chat (dashboard only)

### TDD Red Phase: No

---

## 2. The Truth (Executable Tests)

### 2.1 Acceptance Criteria (Gherkin/Pseudocode)
```gherkin
Feature: Re-Index Existing Files

  Scenario: Re-index all files in a workspace
    Given a workspace with 3 indexed files and a BYOK key
    When the owner sends POST /api/workspaces/{id}/knowledge/reindex
    Then all 3 files are re-fetched from Drive
    And content is re-extracted with current extractors
    And ai_description is re-generated for each file
    And cached_content is updated for each file
    And content_hash is updated for each file
    And the response is { "reindexed": 3, "failed": 0, "errors": [] }

  Scenario: Re-index with one failed file
    Given a workspace with 3 indexed files
    And file #2 has been deleted from Google Drive
    When the owner sends POST /api/workspaces/{id}/knowledge/reindex
    Then files #1 and #3 are re-indexed successfully
    And file #2 fails with an error message
    And the response is { "reindexed": 2, "failed": 1, "errors": ["file #2: ..."] }

  Scenario: Re-index without BYOK key
    Given a workspace with indexed files but no BYOK key
    When the owner sends POST /api/workspaces/{id}/knowledge/reindex
    Then the response is 400 "BYOK key required"

  Scenario: Re-index without Drive connected
    Given a workspace with indexed files but Drive disconnected
    When the owner sends POST /api/workspaces/{id}/knowledge/reindex
    Then the response is 400 "Google Drive not connected"

  Scenario: Re-index empty workspace
    Given a workspace with 0 indexed files
    When the owner sends POST /api/workspaces/{id}/knowledge/reindex
    Then the response is { "reindexed": 0, "failed": 0, "errors": [] }

  Scenario: Non-owner cannot re-index
    Given user "bob" does NOT own the workspace
    When bob sends POST /api/workspaces/{id}/knowledge/reindex
    Then the response is 404

  Scenario: Frontend re-index button
    Given the admin is on the workspace detail page with 3 indexed files
    When they click "Re-index All Files"
    Then a loading spinner appears
    And when complete, the knowledge list refreshes with updated AI descriptions
    And a success toast shows "3 files re-indexed"
```

### 2.2 Verification Steps (Manual)
- [ ] Index files with old extractors (before 006-07) → re-index → verify AI descriptions improved
- [ ] Re-index with one file deleted from Drive → verify partial success response
- [ ] Check `cached_content` column populated after re-index for all files

---

## 3. The Implementation Guide (AI-to-AI)

### 3.0 Environment Prerequisites

| Prerequisite | Value | Verified? |
|-------------|-------|-----------|
| **Depends on** | STORY-006-07 (improved extractors) + STORY-006-10 (cached_content column) merged | [ ] |
| **Services Running** | Backend + frontend dev servers | [ ] |
| **Env Vars** | None new | [x] |

### 3.1 Test Implementation
- Add to `backend/tests/test_knowledge_routes.py`:
  - Test: reindex returns 200 with correct counts
  - Test: reindex with no BYOK key returns 400
  - Test: reindex with no Drive returns 400
  - Test: reindex with non-owner returns 404
  - Test: reindex with empty workspace returns { reindexed: 0 }

### 3.2 Context & Files
| Item | Value |
|------|-------|
| **Primary File** | `backend/app/api/routes/knowledge.py` |
| **Related Files** | `frontend/src/lib/api.ts`, `frontend/src/hooks/useKnowledge.ts`, `frontend/src/routes/app.teams.$teamId.$workspaceId.tsx` (or wherever the knowledge file list lives) |
| **New Files Needed** | No |
| **ADR References** | ADR-004 (scan tier), ADR-005 (Drive read), ADR-006 (AI descriptions) |
| **First-Use Pattern** | No |

### 3.3 Technical Logic

#### 3.3.1 Backend — `knowledge.py`

Add a new endpoint after `delete_knowledge`:

```python
@router.post("/api/workspaces/{workspace_id}/knowledge/reindex")
async def reindex_knowledge(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Re-extract and re-describe all indexed files in the workspace."""
    workspace = await _assert_workspace_owner(workspace_id, user_id)

    # Gate checks
    encrypted_refresh_token = workspace.get("encrypted_google_refresh_token")
    if not encrypted_refresh_token:
        raise HTTPException(status_code=400, detail="Google Drive not connected")

    encrypted_api_key = workspace.get("encrypted_api_key")
    if not encrypted_api_key:
        raise HTTPException(status_code=400, detail="BYOK key required to re-index files")

    # Fetch all indexed files
    files_result = (
        _db.get_supabase()
        .table("teemo_knowledge_index")
        .select("*")
        .eq("workspace_id", workspace_id)
        .execute()
    )
    files = files_result.data or []

    if not files:
        return {"reindexed": 0, "failed": 0, "errors": []}

    # Build Drive client once for all files
    drive_client = _drive_service.get_drive_client(encrypted_refresh_token)
    provider = workspace.get("ai_provider", "anthropic")
    api_key_plaintext = _enc.decrypt(encrypted_api_key)

    reindexed = 0
    failed = 0
    errors = []

    for file_row in files:
        try:
            # Fetch fresh content
            _fetch = _drive_service.fetch_file_content
            if asyncio.iscoroutinefunction(_fetch):
                content = await _fetch(
                    drive_client, file_row["drive_file_id"], file_row["mime_type"],
                    provider=provider, api_key=api_key_plaintext,
                )
            else:
                content = _fetch(
                    drive_client, file_row["drive_file_id"], file_row["mime_type"],
                )

            # Compute hash + generate description
            content_hash = _drive_service.compute_content_hash(content)
            ai_description = await _scan_service.generate_ai_description(
                content, provider, api_key_plaintext,
            )

            # Update row
            _db.get_supabase().table("teemo_knowledge_index").update({
                "cached_content": content,
                "content_hash": content_hash,
                "ai_description": ai_description,
                "last_scanned_at": "now()",
            }).eq("id", file_row["id"]).execute()

            reindexed += 1

        except Exception as e:
            failed += 1
            errors.append(f"{file_row.get('title', file_row['drive_file_id'])}: {e}")

    return {"reindexed": reindexed, "failed": failed, "errors": errors}
```

**Note on `last_scanned_at`:** Check if Supabase/PostgREST accepts `"now()"` as a string value for timestamptz. If not, use `datetime.utcnow().isoformat()` from Python. Test this during implementation.

#### 3.3.2 Frontend — `api.ts`

```typescript
export async function reindexKnowledge(
  workspaceId: string,
): Promise<{ reindexed: number; failed: number; errors: string[] }> {
  return fetchApi(`/api/workspaces/${workspaceId}/knowledge/reindex`, {
    method: "POST",
  });
}
```

#### 3.3.3 Frontend — `useKnowledge.ts`

Add a mutation hook:

```typescript
export function useReindexKnowledgeMutation(workspaceId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => reindexKnowledge(workspaceId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge", workspaceId] });
    },
  });
}
```

#### 3.3.4 Frontend — workspace detail page

Add a "Re-index All Files" button in the knowledge section:
- Disabled when no files indexed or when mutation is pending
- Shows spinner during re-index
- On success: toast with "N files re-indexed" (or "N re-indexed, M failed" if errors)
- On error: toast with error message

---

## 4. Quality Gates

### 4.1 Minimum Test Expectations

| Test Type | Minimum Count | Notes |
|-----------|--------------|-------|
| Unit tests | 5 | Success with counts, no BYOK 400, no Drive 400, non-owner 404, empty workspace |
| Component tests | 0 | N/A |
| E2E / acceptance tests | 0 | Manual (§2.2) |

### 4.2 Definition of Done (The Gate)
- [ ] Minimum test expectations (§4.1) met — 5 tests.
- [ ] FLASHCARDS.md consulted.
- [ ] Endpoint returns correct counts for success and partial failure.
- [ ] `cached_content`, `content_hash`, `ai_description` all updated per file.
- [ ] Frontend button triggers re-index and refreshes knowledge list.
- [ ] Failed files don't abort the operation.

---

## Token Usage

| Agent | Input | Output | Total |
|-------|-------|--------|-------|
| Developer | 38 | 2,429 | 2,467 |
