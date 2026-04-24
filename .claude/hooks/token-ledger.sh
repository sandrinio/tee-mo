#!/usr/bin/env bash
# SubagentStop hook: append one JSONL row per subagent completion to the active sprint's token ledger.
#
# Input: JSON on stdin from Claude Code with fields session_id, transcript_path, cwd, hook_event_name.
# Output: appends to .cleargate/sprint-runs/<sprint-id>/token-ledger.jsonl
# Cost computation is deferred to the Reporter agent (prices change; keep raw).
#
# Active sprint detection (FIXED 2026-04-19):
#   Primary  : .cleargate/sprint-runs/.active sentinel file (one line: "SPRINT-NN")
#              Orchestrator writes this at sprint kickoff, removes/updates at close.
#   Fallback : .cleargate/sprint-runs/_off-sprint/token-ledger.jsonl
#              When no .active sentinel exists, writes still get captured but
#              tagged off-sprint instead of misrouting to a stale sprint dir.
#   (Removed): the old `ls -td sprint-runs/*/ | head -1` mtime heuristic — it
#              misrouted SPRINT-04 firings to SPRINT-03 because ledger appends
#              themselves bumped SPRINT-03's mtime. See REPORT.md SPRINT-04.
#
# Work-item ID detection (GENERALIZED 2026-04-19 STORY-008-04):
#   Primary  : first user message in the transcript — that's the orchestrator's
#              dispatch prompt, which by agent convention starts with
#              `STORY=NNN-NN`, `PROPOSAL-NNN`, `EPIC-NNN`, `CR-NNN`, or `BUG-NNN`.
#   Pattern  : (STORY|PROPOSAL|EPIC|CR|BUG)[-=]?[0-9]+(-[0-9]+)?
#   Fallback : grep first match anywhere in the transcript.
#   story_id : populated only when the match is a STORY-* (backward compat).
#   work_item_id: always populated when detection succeeds; equals story_id for STORY items.
#   (Removed): grep-first-anywhere as PRIMARY — it picked up SPRINT-05 mentions
#              from architect plans being read by the subagent and mistagged
#              every SPRINT-04 firing as STORY-006-01.
#
# Robustness: never exits non-zero on parse failure (never block a subagent stop). Errors go to a
# sibling hook.log so you can diagnose without fighting the runtime.

set -u

REPO_ROOT="/Users/ssuladze/Documents/Dev/ClearGate"
LOG_DIR="${REPO_ROOT}/.cleargate/hook-log"
mkdir -p "${LOG_DIR}"
HOOK_LOG="${LOG_DIR}/token-ledger.log"
ACTIVE_SENTINEL="${REPO_ROOT}/.cleargate/sprint-runs/.active"

{
  INPUT="$(cat)"

  # --- parse hook payload ---
  TRANSCRIPT_PATH="$(printf '%s' "${INPUT}" | jq -r '.transcript_path // empty')"
  SESSION_ID="$(printf '%s' "${INPUT}" | jq -r '.session_id // empty')"

  if [[ -z "${TRANSCRIPT_PATH}" || ! -f "${TRANSCRIPT_PATH}" ]]; then
    printf '[%s] no transcript_path (session=%s)\n' "$(date -u +%FT%TZ)" "${SESSION_ID}" >> "${HOOK_LOG}"
    exit 0
  fi

  # --- determine active sprint via sentinel ---
  SPRINT_ID=""
  if [[ -f "${ACTIVE_SENTINEL}" ]]; then
    SPRINT_ID="$(tr -d '[:space:]' < "${ACTIVE_SENTINEL}")"
  fi

  if [[ -n "${SPRINT_ID}" ]]; then
    SPRINT_DIR="${REPO_ROOT}/.cleargate/sprint-runs/${SPRINT_ID}"
    mkdir -p "${SPRINT_DIR}"
    printf '[%s] routing to sprint=%s (sentinel)\n' "$(date -u +%FT%TZ)" "${SPRINT_ID}" >> "${HOOK_LOG}"
  else
    # No active sprint: capture the row in an off-sprint ledger so we don't lose data.
    SPRINT_ID="_off-sprint"
    SPRINT_DIR="${REPO_ROOT}/.cleargate/sprint-runs/_off-sprint"
    mkdir -p "${SPRINT_DIR}"
    printf '[%s] no .active sentinel — bucketing as _off-sprint\n' "$(date -u +%FT%TZ)" >> "${HOOK_LOG}"
  fi
  LEDGER="${SPRINT_DIR}/token-ledger.jsonl"

  # --- walk transcript, sum usage across all assistant turns in this subagent run ---
  USAGE_JSON="$(jq -cs '
    map(select(.type == "assistant" and .message.usage))
    | (map(.message.usage.input_tokens // 0)                     | add) as $in
    | (map(.message.usage.output_tokens // 0)                    | add) as $out
    | (map(.message.usage.cache_creation_input_tokens // 0)      | add) as $cc
    | (map(.message.usage.cache_read_input_tokens // 0)          | add) as $cr
    | (map(.message.model) | unique | map(select(. != null)) | join(","))     as $models
    | (length)                                                   as $turns
    | {input: $in, output: $out, cache_creation: $cc, cache_read: $cr, model: $models, turns: $turns}
  ' "${TRANSCRIPT_PATH}" 2>/dev/null)"

  if [[ -z "${USAGE_JSON}" || "${USAGE_JSON}" == "null" ]]; then
    printf '[%s] could not parse usage from %s\n' "$(date -u +%FT%TZ)" "${TRANSCRIPT_PATH}" >> "${HOOK_LOG}"
    exit 0
  fi

  # --- detect agent_type ---
  # Subagent transcripts contain `subagent_type` in the parent's tool invocation.
  # Best-effort extraction; falls back to grepping role markers in the transcript body.
  AGENT_TYPE="$(jq -rs '
    [.[] | select(.type == "user") | .message.content]
    | tostring
    | capture("subagent_type[\"\\s:=]+(?<t>[a-zA-Z0-9_-]+)"; "g")?.t
    // "unknown"
  ' "${TRANSCRIPT_PATH}" 2>/dev/null)"
  [[ -z "${AGENT_TYPE}" || "${AGENT_TYPE}" == "null" ]] && AGENT_TYPE="unknown"

  if [[ "${AGENT_TYPE}" == "unknown" ]]; then
    for role in architect developer qa reporter; do
      if grep -qiE "\\b${role}\\b agent|role: ${role}|you are the ${role}" "${TRANSCRIPT_PATH}" 2>/dev/null; then
        AGENT_TYPE="${role}"
        break
      fi
    done
  fi

  # --- detect work_item_id (PRIMARY: first user message; FALLBACK: anywhere-grep) ---
  # Orchestrator convention (.claude/agents/developer.md): the first line of the
  # dispatch prompt is `STORY=NNN-NN`. The first user message in the transcript
  # is that prompt. Look there first to avoid picking up work-item mentions inside
  # the subagent's later reads of plans, sprint files, etc.
  #
  # Pattern covers: STORY-NNN-NN, PROPOSAL-NNN, EPIC-NNN, CR-NNN, BUG-NNN
  # (and = separator variants like STORY=008-04)
  WORK_ITEM_RAW="$(jq -rs '
    [.[] | select(.type == "user")] | .[0].message.content
    | if type == "array" then map(.text? // "") | join(" ") else (. // "") end
    | tostring
    | scan("(STORY|PROPOSAL|EPIC|CR|BUG)[-=]?([0-9]+(-[0-9]+)?)") | .[0:2] | join("-")
  ' "${TRANSCRIPT_PATH}" 2>/dev/null | head -1)"

  if [[ -n "${WORK_ITEM_RAW}" && "${WORK_ITEM_RAW}" != "null" && "${WORK_ITEM_RAW}" != "-" ]]; then
    # Normalize: replace any = separator with - in the result
    WORK_ITEM_ID="$(printf '%s' "${WORK_ITEM_RAW}" | sed 's/=/-/g')"
  else
    # Fallback: grep anywhere in the transcript
    WORK_ITEM_ID="$(grep -oE '(STORY|PROPOSAL|EPIC|CR|BUG)[-=]?[0-9]+(-[0-9]+)?' "${TRANSCRIPT_PATH}" 2>/dev/null \
      | head -1 \
      | sed 's/=/-/g')"
    if [[ -n "${WORK_ITEM_ID}" ]]; then
      printf '[%s] work_item_id fallback grep: %s\n' "$(date -u +%FT%TZ)" "${WORK_ITEM_ID}" >> "${HOOK_LOG}"
    fi
  fi
  [[ -z "${WORK_ITEM_ID}" ]] && WORK_ITEM_ID=""

  # story_id is populated only when the work item is a STORY-* (backward compat)
  STORY_ID=""
  if [[ "${WORK_ITEM_ID}" == STORY-* ]]; then
    STORY_ID="${WORK_ITEM_ID}"
  fi

  # Legacy fallback: if no work_item_id found at all, fall back to old grep for story_id only
  if [[ -z "${WORK_ITEM_ID}" ]]; then
    STORY_ID="$(grep -oE 'STORY[-=]?[0-9]{3}-[0-9]{2}' "${TRANSCRIPT_PATH}" 2>/dev/null \
      | head -1 \
      | sed -E 's/STORY[-=]?([0-9]{3}-[0-9]{2})/STORY-\1/')"
    [[ -z "${STORY_ID}" ]] && STORY_ID="none"
    WORK_ITEM_ID="${STORY_ID}"
  fi

  # --- assemble ledger row ---
  TS="$(date -u +%FT%TZ)"
  ROW="$(jq -cn \
    --arg ts "${TS}" \
    --arg agent "${AGENT_TYPE}" \
    --arg story "${STORY_ID}" \
    --arg work_item "${WORK_ITEM_ID}" \
    --arg session "${SESSION_ID}" \
    --arg transcript "${TRANSCRIPT_PATH}" \
    --arg sprint "${SPRINT_ID}" \
    --argjson usage "${USAGE_JSON}" \
    '{ts: $ts, sprint_id: $sprint, agent_type: $agent, story_id: $story, work_item_id: $work_item, session_id: $session, transcript: $transcript} + $usage')"

  printf '%s\n' "${ROW}" >> "${LEDGER}"
  printf '[%s] wrote row: sprint=%s agent=%s work_item=%s story=%s tokens=in:%s/out:%s\n' \
    "${TS}" "${SPRINT_ID}" "${AGENT_TYPE}" "${WORK_ITEM_ID}" "${STORY_ID}" \
    "$(printf '%s' "${USAGE_JSON}" | jq -r '.input')" \
    "$(printf '%s' "${USAGE_JSON}" | jq -r '.output')" \
    >> "${HOOK_LOG}"
} 2>> "${HOOK_LOG}"

exit 0
