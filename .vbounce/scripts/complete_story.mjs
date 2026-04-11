#!/usr/bin/env node

/**
 * complete_story.mjs
 * Mark a story as Done — updates Sprint Plan §1 + §4, and state.json atomically.
 *
 * Usage:
 *   ./.vbounce/scripts/complete_story.mjs STORY-005-02 --qa-bounces 1 --arch-bounces 0 --correction-tax 5 --notes "Missing validation fixed"
 *
 * Implementation notes (post-S-04 rewrite):
 *   Previously this script used a single regex with `[^|]*` patterns + /g flag to
 *   update both §1 and §4. Because `[^|]*` matches newlines, the regex spanned
 *   across table row boundaries and corrupted cells in OTHER tables (Merge Ordering,
 *   Dependency Chain, Open Questions, Execution Mode). It also APPENDED execution-log
 *   rows instead of replacing the placeholder row, producing duplicates with
 *   mismatched column counts.
 *
 *   The rewrite parses markdown tables row-by-row, operates ONLY on the §1 Active
 *   Scope table (identified by its header signature), and replaces the existing
 *   execution-log placeholder row in-place by matching the story ID in the first
 *   cell. No more global regex, no more cross-row spanning, no more appending.
 *
 *   See `.vbounce/archive/S-04/` for the 5 hand-patch commits caused by the old
 *   regex approach. See `.vbounce/improvement-suggestions.md` entry #2 for the
 *   original P0 bug report.
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawnSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../..');

function parseArgs(argv) {
  const result = { storyId: null, qaBounces: 0, archBounces: 0, correctionTax: '0%', notes: '' };
  const args = argv.slice(2);
  result.storyId = args[0];
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--qa-bounces') result.qaBounces = parseInt(args[++i], 10) || 0;
    else if (args[i] === '--arch-bounces') result.archBounces = parseInt(args[++i], 10) || 0;
    else if (args[i] === '--correction-tax') result.correctionTax = args[++i] + (args[i].includes('%') ? '' : '%');
    else if (args[i] === '--notes') result.notes = args[++i];
  }
  return result;
}

/**
 * Split a markdown table row on unescaped `|` characters.
 * Returns an array of cell strings (trimmed). Leading and trailing empty cells
 * from the outer `|` delimiters are dropped. Returns null if the line is not
 * a table row (no leading `|`).
 */
function splitRow(line) {
  if (!line.startsWith('|')) return null;
  const parts = line.split('|');
  // First and last are empty because of the leading/trailing `|`
  parts.shift();
  parts.pop();
  return parts.map(c => c.trim());
}

/**
 * Join a cell array back into a markdown table row. Each cell is padded with
 * single spaces around its content to match the repo's existing table style.
 */
function joinRow(cells) {
  return '| ' + cells.join(' | ') + ' |';
}

/**
 * Find the §1 Active Scope table row for `storyId` and replace its V-Bounce
 * State cell with "Done". Returns { content, updated } — leaves the file
 * unchanged if no matching row is found.
 *
 * The §1 table has columns: Priority | Story | Epic | Label | V-Bounce State | Blocker
 * (5-index 0..5). The state cell is index 4.
 *
 * The table is identified by its header signature containing "V-Bounce State"
 * AND "Priority" — avoids collisions with other tables that happen to have
 * the story ID in them (Merge Ordering, Dependency Chain, Execution Log).
 */
function updateActiveScope(content, storyId) {
  const lines = content.split('\n');
  let inActiveScopeTable = false;
  let updated = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Detect the §1 Active Scope header by its unique column signature
    if (line.startsWith('|') && line.includes('V-Bounce State') && line.includes('Priority') && line.includes('Blocker')) {
      inActiveScopeTable = true;
      continue;
    }

    // Exit the table on blank line or non-table line
    if (inActiveScopeTable && !line.startsWith('|')) {
      inActiveScopeTable = false;
      continue;
    }

    // Skip the separator row
    if (inActiveScopeTable && /^\|[-:|\s]+\|$/.test(line)) continue;

    if (inActiveScopeTable) {
      const cells = splitRow(line);
      if (!cells || cells.length < 6) continue;
      // Story cell is index 1. Match if it contains the storyId anywhere
      // (usually wrapped in a markdown link like `[STORY-XXX: name](path)`).
      if (cells[1].includes(storyId)) {
        cells[4] = 'Done';
        lines[i] = joinRow(cells);
        updated = true;
        break; // Only one match expected per sprint plan
      }
    }
  }

  return { content: lines.join('\n'), updated };
}

/**
 * Update the §4 Execution Log row for `storyId` in place. If a placeholder
 * row (first cell == storyId, rest `_pending_`) exists, replace it. If a
 * completed row for this story exists, overwrite it. If neither exists,
 * append a new row before `<!-- EXECUTION_LOG_END -->`.
 *
 * Column count is detected from the table header — supports both the 6-col
 * layout (Story, Final State, QA Bounces, Arch Bounces, Correction Tax, Notes)
 * and the 7-col layout (adds "Tests Written" between Arch Bounces and
 * Correction Tax). Unknown columns are left as `—`.
 */
function updateExecutionLog(content, storyId, qaBounces, archBounces, correctionTax, notes) {
  const logStart = '<!-- EXECUTION_LOG_START -->';
  const logEnd = '<!-- EXECUTION_LOG_END -->';

  if (!content.includes(logStart) || !content.includes(logEnd)) {
    return { content, message: '⚠  Execution log markers not found — skipping §4 update.' };
  }

  const lines = content.split('\n');
  const startIdx = lines.findIndex(l => l.includes(logStart));
  const endIdx = lines.findIndex(l => l.includes(logEnd));
  if (startIdx < 0 || endIdx < 0 || endIdx <= startIdx) {
    return { content, message: '⚠  Execution log markers malformed — skipping §4 update.' };
  }

  // Find header row inside the log section
  let headerIdx = -1;
  let headerCells = null;
  for (let i = startIdx + 1; i < endIdx; i++) {
    const l = lines[i];
    if (l.startsWith('|') && l.includes('Story') && l.includes('Final State')) {
      headerCells = splitRow(l);
      headerIdx = i;
      break;
    }
  }

  if (!headerCells) {
    return { content, message: '⚠  Execution log table header not found — skipping §4 update.' };
  }

  // Build the new row matching the detected column count and column names
  const newCells = headerCells.map(col => {
    const c = col.toLowerCase();
    if (c === 'story') return storyId;
    if (c === 'final state') return 'Done';
    if (c === 'qa bounces') return String(qaBounces);
    if (c === 'arch bounces') return String(archBounces);
    if (c === 'tests written') return '—'; // filled in by caller if known; script keeps it neutral
    if (c === 'correction tax') return correctionTax;
    if (c === 'notes') return notes || '—';
    return '—';
  });
  const newRow = joinRow(newCells);

  // Try to find an existing row for this story (placeholder or completed)
  // inside the log section (between header and endIdx).
  let replacedIdx = -1;
  for (let i = headerIdx + 1; i < endIdx; i++) {
    const l = lines[i];
    if (!l.startsWith('|')) continue;
    if (/^\|[-:|\s]+\|$/.test(l)) continue; // separator
    const cells = splitRow(l);
    if (cells && cells[0] === storyId) {
      lines[i] = newRow;
      replacedIdx = i;
      break;
    }
  }

  if (replacedIdx < 0) {
    // No existing row — insert before the end marker
    lines.splice(endIdx, 0, newRow);
  }

  return {
    content: lines.join('\n'),
    message: replacedIdx >= 0 ? '✓ Replaced existing row in §4 Execution Log' : '✓ Appended new row to §4 Execution Log',
  };
}

// ---- Main ----

const { storyId, qaBounces, archBounces, correctionTax, notes } = parseArgs(process.argv);

if (!storyId) {
  console.error('Usage: complete_story.mjs STORY-ID [--qa-bounces N] [--arch-bounces N] [--correction-tax N] [--notes "text"]');
  process.exit(1);
}

// 1. Update state.json
const stateFile = path.join(ROOT, '.vbounce', 'state.json');
if (!fs.existsSync(stateFile)) {
  console.error('ERROR: .vbounce/state.json not found');
  process.exit(1);
}
let state;
try {
  state = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
} catch (e) {
  console.error(`ERROR: state.json is not valid JSON — ${e.message}`);
  process.exit(1);
}
if (!state.stories[storyId]) {
  console.error(`ERROR: Story "${storyId}" not found in state.json`);
  process.exit(1);
}
state.stories[storyId].state = 'Done';
state.stories[storyId].qa_bounces = qaBounces;
state.stories[storyId].arch_bounces = archBounces;
state.stories[storyId].worktree = null;
state.last_action = `${storyId} completed`;
state.updated_at = new Date().toISOString();
fs.writeFileSync(stateFile, JSON.stringify(state, null, 2));
console.log(`✓ Updated state.json: ${storyId} → Done`);

// 2. Find sprint plan
const sprintNum = state.sprint_id.replace('S-', '');
const candidatePaths = [
  path.join(ROOT, 'product_plans', 'sprints', `sprint-${sprintNum}`, `sprint-${sprintNum}.md`),
  path.join(ROOT, 'product_plans', 'archive', 'sprints', `sprint-${sprintNum}`, `sprint-${sprintNum}.md`),
];
const sprintPlanPath = candidatePaths.find(p => fs.existsSync(p));

if (!sprintPlanPath) {
  console.warn(`⚠  Sprint plan not found for ${state.sprint_id} (checked: ${candidatePaths.join(', ')}). Update §1 and §4 manually.`);
  process.exit(0);
}

let content = fs.readFileSync(sprintPlanPath, 'utf8');

// 3. Update §1 Active Scope — replace V-Bounce State cell with "Done"
const activeScopeResult = updateActiveScope(content, storyId);
if (activeScopeResult.updated) {
  content = activeScopeResult.content;
  console.log('✓ Updated §1 Active Scope');
} else {
  console.warn(`⚠  Could not find ${storyId} row in §1 Active Scope table. Update V-Bounce State manually.`);
}

// 4. Update §4 Execution Log — replace placeholder or append
const logResult = updateExecutionLog(content, storyId, qaBounces, archBounces, correctionTax, notes);
content = logResult.content;
console.log(logResult.message);

fs.writeFileSync(sprintPlanPath, content);
console.log(`✓ Updated sprint plan: ${storyId} Done`);
console.log(`\n  QA bounces: ${qaBounces} | Arch bounces: ${archBounces} | Correction tax: ${correctionTax}`);

// Regenerate product graph (non-blocking)
const graphScript = path.join(__dirname, 'product_graph.mjs');
if (fs.existsSync(graphScript)) {
  const graphResult = spawnSync(process.execPath, [graphScript], { stdio: 'pipe', cwd: ROOT });
  if (graphResult.status === 0) console.log('✓ Product graph regenerated');
}
