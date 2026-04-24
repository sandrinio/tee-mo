# Developer Checkpoint: STORY-015-02-route-refactor
## Completed
- All implementation done and committed (commit 999fcd3)
- 39 tests pass, 1 pre-existing failure unchanged

## Remaining
- Nothing — story complete

## Key Decisions
- document_service.create_document called from index_file route (SHA-256, AI description handled by service)
- 15-cap check still at route level (friendlier error before DB trigger fires)
- Duplicate check stays at route level (service doesn't check by external_id)
- _knowledge_table_mock renamed to _documents_table_mock with backward-compat alias
- MIME_TO_DOC_TYPE dict added to knowledge.py module level

## Files Modified
- backend/app/api/routes/knowledge.py
- backend/app/models/knowledge.py
- backend/tests/test_knowledge_routes.py
