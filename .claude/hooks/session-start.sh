#!/usr/bin/env bash
set -u
REPO_ROOT="${CLAUDE_PROJECT_DIR}"
node "${REPO_ROOT}/cleargate-cli/dist/cli.js" doctor --session-start 2>/dev/null || true
