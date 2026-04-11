#!/usr/bin/env node

/**
 * Golden-file test for .vbounce/scripts/complete_story.mjs
 *
 * Runs complete_story.mjs against a fixture sprint plan and asserts the
 * output matches the expected golden file EXACTLY. If this test passes,
 * the script is NOT corrupting adjacent tables, NOT eating column headers,
 * and NOT appending duplicate execution log rows — the three failure modes
 * that produced 5 consecutive hand-patches during S-04.
 *
 * Run with:
 *   node .vbounce/scripts/__tests__/complete_story.test.mjs
 *
 * Exit 0 = pass. Exit 1 = fail (diff printed to stderr).
 *
 * To regenerate the expected file from scratch if the script's output
 * format legitimately changes:
 *   1. Edit sprint-test-expected.md by hand to match the new desired output
 *   2. Re-run this test; it should pass
 *   DO NOT just copy the script's current output to the expected file
 *   without reviewing it — that defeats the whole point of a golden test.
 */

import fs from 'fs';
import path from 'path';
import os from 'os';
import { fileURLToPath } from 'url';
import { spawnSync } from 'child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '../../..');
const SCRIPT = path.join(ROOT, '.vbounce', 'scripts', 'complete_story.mjs');
const INPUT_FIXTURE = path.join(__dirname, '..', '__fixtures__', 'sprint-test-input.md');
const EXPECTED_FIXTURE = path.join(__dirname, '..', '__fixtures__', 'sprint-test-expected.md');

function fail(msg) {
  console.error(`✗ FAIL: ${msg}`);
  process.exit(1);
}

function pass(msg) {
  console.log(`✓ PASS: ${msg}`);
}

// 1. Build a throwaway sandbox that mimics the repo layout expected by the script.
const sandbox = fs.mkdtempSync(path.join(os.tmpdir(), 'vbounce-complete-story-test-'));
try {
  // Layout: sandbox/.vbounce/state.json, sandbox/product_plans/sprints/sprint-test/sprint-test.md
  fs.mkdirSync(path.join(sandbox, '.vbounce'), { recursive: true });
  fs.mkdirSync(path.join(sandbox, '.vbounce', 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(sandbox, 'product_plans', 'sprints', 'sprint-test'), { recursive: true });

  // Minimal state.json with the test story IDs
  const state = {
    sprint_id: 'S-test',
    stories: {
      'STORY-TEST-01': { state: 'Bouncing', qa_bounces: 0, arch_bounces: 0, worktree: null },
      'STORY-TEST-02': { state: 'Draft', qa_bounces: 0, arch_bounces: 0, worktree: null },
      'STORY-TEST-03': { state: 'Draft', qa_bounces: 0, arch_bounces: 0, worktree: null },
    },
    phase: 'Phase 3',
    last_action: 'test setup',
    updated_at: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(sandbox, '.vbounce', 'state.json'), JSON.stringify(state, null, 2));

  // Copy the sprint plan fixture into the sandbox
  const sprintPlanPath = path.join(sandbox, 'product_plans', 'sprints', 'sprint-test', 'sprint-test.md');
  fs.copyFileSync(INPUT_FIXTURE, sprintPlanPath);

  // Copy the script into the sandbox's .vbounce/scripts/ so it resolves ROOT correctly
  // (the script computes ROOT from its own __dirname).
  fs.copyFileSync(SCRIPT, path.join(sandbox, '.vbounce', 'scripts', 'complete_story.mjs'));

  // 2. Run the script in the sandbox
  const result = spawnSync(
    process.execPath,
    [
      path.join(sandbox, '.vbounce', 'scripts', 'complete_story.mjs'),
      'STORY-TEST-01',
      '--qa-bounces', '0',
      '--arch-bounces', '0',
      '--correction-tax', '5',
      '--notes', 'Fast Track. 3/3 target tests.',
    ],
    { stdio: 'pipe', cwd: sandbox, encoding: 'utf8' }
  );

  if (result.status !== 0) {
    fail(`Script exited with status ${result.status}. stderr:\n${result.stderr}`);
  }

  // 3. Compare actual vs expected
  const actual = fs.readFileSync(sprintPlanPath, 'utf8');
  const expected = fs.readFileSync(EXPECTED_FIXTURE, 'utf8');

  if (actual !== expected) {
    // Find the first differing line for a quick diff
    const actualLines = actual.split('\n');
    const expectedLines = expected.split('\n');
    const maxLen = Math.max(actualLines.length, expectedLines.length);
    const diff = [];
    for (let i = 0; i < maxLen; i++) {
      if (actualLines[i] !== expectedLines[i]) {
        diff.push(`  line ${i + 1}:`);
        diff.push(`    expected: ${JSON.stringify(expectedLines[i] ?? '<EOF>')}`);
        diff.push(`    actual  : ${JSON.stringify(actualLines[i] ?? '<EOF>')}`);
        if (diff.length >= 30) break; // cap at ~10 diffs
      }
    }
    console.error('✗ FAIL: actual output does not match expected golden file');
    console.error(`  fixture: ${INPUT_FIXTURE}`);
    console.error(`  expected: ${EXPECTED_FIXTURE}`);
    console.error(`  sandbox output: ${sprintPlanPath}`);
    console.error('  first differences:');
    console.error(diff.join('\n'));
    process.exit(1);
  }

  pass('complete_story.mjs STORY-TEST-01 output matches golden file — no cross-row corruption, no column-header eating, no duplicate row append');

  // 4. Bonus: verify state.json in the sandbox was also updated correctly
  const sandboxState = JSON.parse(fs.readFileSync(path.join(sandbox, '.vbounce', 'state.json'), 'utf8'));
  if (sandboxState.stories['STORY-TEST-01'].state !== 'Done') {
    fail(`state.json STORY-TEST-01 not set to Done (got "${sandboxState.stories['STORY-TEST-01'].state}")`);
  }
  pass('state.json STORY-TEST-01 updated to Done');

  // 5. Verify OTHER stories were NOT touched in state.json
  if (sandboxState.stories['STORY-TEST-02'].state !== 'Draft' || sandboxState.stories['STORY-TEST-03'].state !== 'Draft') {
    fail('state.json incorrectly mutated unrelated stories');
  }
  pass('state.json unrelated stories untouched');
} finally {
  // Cleanup sandbox
  fs.rmSync(sandbox, { recursive: true, force: true });
}

console.log('\n✓ All golden-file assertions passed.');
process.exit(0);
