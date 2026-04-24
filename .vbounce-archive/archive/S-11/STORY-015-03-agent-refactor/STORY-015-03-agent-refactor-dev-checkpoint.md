# Developer Checkpoint: STORY-015-03-agent-refactor

## Completed
- Read FLASHCARDS.md (confirmed SHA-256 rule, omit DEFAULT NOW() cols, lazy imports pattern)
- Read sprint context S-11 (confirmed merge order: 015-03 first, teemo_ prefix, worktree paths)
- Read STORY spec (all 7 requirements captured)
- Read agent.py (full 730 lines — knows current structure)
- Read document_service.py (knows all function signatures)
- Identified test_read_drive_file.py (the old Drive tests — must be replaced)

## Remaining
- Modify backend/app/agents/agent.py:
  - Delete read_drive_file (lines 608-714) and replace with read_document (~15 lines)
  - Update _build_system_prompt() to use teemo_documents and new field names
  - Update build_agent() step 7.5 to query teemo_documents
  - Add create_document, update_document, delete_document tools
  - Update tools list (R7)
  - Add `from app.services import document_service as _doc_service` import
- Write new test file test_read_document.py (replacing old Drive test semantics)
- Run tests to verify

## Key Decisions
- Use `document_service.read_document_content()` not direct Supabase in read_document tool
- Source check in update/delete: query document row, check source field, guard if != 'agent'
- System prompt: rename `knowledge_files` param to `documents`, change field names to id/title/ai_description
- Old test_read_drive_file.py tests Drive behavior — they will fail after removal; new test file covers new behavior

## Files Modified
- None yet
