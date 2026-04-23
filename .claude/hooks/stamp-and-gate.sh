#!/usr/bin/env bash
set -u
REPO_ROOT="${CLAUDE_PROJECT_DIR}"
LOG="${REPO_ROOT}/.cleargate/hook-log/gate-check.log"
mkdir -p "$(dirname "$LOG")"
FILE=$(jq -r '.tool_input.file_path' 2>/dev/null || echo "")
[ -z "$FILE" ] && exit 0
case "$FILE" in *.cleargate/delivery/*) : ;; *) exit 0 ;; esac
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Ordered chain — stamp MUST precede gate (gate may read draft_tokens)
node "${REPO_ROOT}/cleargate-cli/dist/cli.js" stamp-tokens "$FILE" >>"$LOG" 2>&1
SR1=$?
node "${REPO_ROOT}/cleargate-cli/dist/cli.js" gate check "$FILE" >>"$LOG" 2>&1
SR2=$?
node "${REPO_ROOT}/cleargate-cli/dist/cli.js" wiki ingest "$FILE" >>"$LOG" 2>&1
SR3=$?
echo "[$TS] stamp=$SR1 gate=$SR2 ingest=$SR3 file=$FILE" >>"$LOG"
exit 0   # ALWAYS 0 — severity enforcement is at wiki lint, not hook
