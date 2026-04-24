---
story_id: "STORY-015-06"
agent: "developer"
status: "PASS"
files_modified:
  - frontend/src/lib/api.ts
  - frontend/src/routes/app.teams.$teamId.$workspaceId.tsx
  - frontend/src/components/workspace/SetupStepper.tsx
tests_written: 0
tests_passed: 0
tests_note: "L1 frontend story — build verification only, no unit tests"
correction_tax: 0
flashcards_flagged: []
input_tokens: 0
output_tokens: 0
total_tokens: 67659
---

# STORY-015-06 Developer Report: Frontend Source Badges

## Implementation Summary
- Updated KnowledgeFile type with source, doc_type, external_id, external_link fields
- Added source badges: Drive (neutral), Upload (blue), Agent (purple)
- Link icon only for docs with external_link (Drive docs)
- Build clean: tsc -b + vite build both pass
