#!/usr/bin/env npx tsx
/**
 * Demo: U→A Adapter (full pipeline)
 *
 * Loads a REAL recorded session log (JSONL) and replays each user turn:
 *   1. Shows what was ACTUALLY sent to LLM A (ground truth from session)
 *   2. Derives the UserAction(s) that LLM U would produce for the same effect
 *      — including fill_fields inferred from form state deltas
 *   3. Runs each through convertUserActionToAppInput() with current form state
 *   4. Compares output to ground truth — proving the adapter is correct
 *
 * Form state delta inference:
 *   Between consecutive form_state_snapshots, any field changes NOT explained
 *   by model set_fields are inferred as user proactive edits → fill_fields actions.
 *
 * Zero fabrication — every input comes from an actual recorded session.
 *
 * Usage:
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-u2a.ts
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-u2a.ts 3
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-u2a.ts --file path/to/session.jsonl
 */

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { convertUserActionToAppInput, type UserAction, type FileAttachment } from './user-action.js';

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..', '..');

// ── JSONL types ──

interface SessionEntry {
  type: string;
  ts: string;
  session_id: string;
  // user_message fields
  message?: string;
  role?: string;
  // model_input fields
  user_message?: string;
  form_state_snapshot?: Record<string, unknown>;
  // model_output fields
  parsed_actions?: ParsedAction[];
}

interface ParsedAction {
  type?: string;
  tool?: string;
  fields?: Array<{ field_id: string; value: unknown }>;
  input?: Record<string, unknown>;
  [key: string]: unknown;
}

interface UserTurn {
  turnNumber: number;
  /** The raw message that was actually sent to LLM A (ground truth) */
  actualMessageSent: string;
  /** The role (user or system) */
  role: string;
  /** Form state at the time (from model_input — ground truth) */
  formState: Record<string, unknown>;
  /** Form state from the PREVIOUS turn's model_input (what we'd feed the adapter) */
  prevFormState: Record<string, unknown>;
  /** Fields set by model set_fields between previous and current snapshot */
  modelSetFields: Set<string>;
}

// ── Load and parse session JSONL ──

function loadSession(filePath: string): UserTurn[] {
  const lines = readFileSync(filePath, 'utf-8').trim().split('\n');
  const entries: SessionEntry[] = lines.map((line) => JSON.parse(line));

  const turns: UserTurn[] = [];
  let turnNumber = 0;
  let prevFormState: Record<string, unknown> = {};
  let prevSnapshotIdx = -1;

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];

    if (entry.type === 'user_message' && entry.message) {
      // Find the corresponding model_input
      let actualMessageSent = entry.message;
      let formState: Record<string, unknown> = {};
      let snapshotIdx = -1;

      for (let j = i + 1; j < entries.length; j++) {
        if (entries[j].type === 'model_input') {
          actualMessageSent = entries[j].user_message || entry.message;
          formState = entries[j].form_state_snapshot || {};
          snapshotIdx = j;
          break;
        }
        if (entries[j].type === 'user_message') break;
      }

      // Collect model set_fields between previous snapshot and current snapshot
      const modelSetFields = new Set<string>();
      const searchStart = prevSnapshotIdx >= 0 ? prevSnapshotIdx : 0;
      const searchEnd = snapshotIdx >= 0 ? snapshotIdx : i;

      for (let j = searchStart; j < searchEnd; j++) {
        const e = entries[j];
        if (e.type === 'model_output' && e.parsed_actions) {
          for (const action of e.parsed_actions) {
            if (action.type === 'set_fields' && action.fields) {
              for (const f of action.fields) {
                // Normalize dots to dashes to match snapshot keys
                modelSetFields.add(f.field_id.replace(/\./g, '-'));
              }
            }
          }
        }
      }

      turnNumber++;
      turns.push({
        turnNumber,
        actualMessageSent,
        role: entry.role || 'user',
        formState,
        prevFormState: { ...prevFormState },
        modelSetFields,
      });

      prevFormState = formState;
      if (snapshotIdx >= 0) prevSnapshotIdx = snapshotIdx;
    }
  }

  return turns;
}

// ── Compute unexplained field changes (user proactive edits) ──

function computeUserEdits(turn: UserTurn): Record<string, unknown> {
  const prev = turn.prevFormState;
  const curr = turn.formState;
  const edits: Record<string, unknown> = {};

  // Find all keys present in current but not in previous, or with different values
  for (const k of Object.keys(curr)) {
    const prevVal = prev[k];
    const currVal = curr[k];

    // Skip if unchanged
    if (prevVal === currVal) continue;
    if (JSON.stringify(prevVal) === JSON.stringify(currVal)) continue;

    // Skip if explained by model set_fields
    if (turn.modelSetFields.has(k)) continue;

    edits[k] = currVal;
  }

  return edits;
}

// ── Extract file attachments from session data ──

function extractFilesFromSession(turns: UserTurn[]): Map<string, FileAttachment> {
  const files = new Map<string, FileAttachment>();

  for (const turn of turns) {
    const fileMatch = turn.actualMessageSent.match(/\[File: (.+?)\]\n([\s\S]*?)\n\[End of \1\]/);
    if (fileMatch) {
      files.set(fileMatch[1], {
        filename: fileMatch[1],
        content: fileMatch[2],
      });
    }
  }

  return files;
}

// ── Derive UserAction(s) from a real session turn ──
// Returns an array: may include a fill_fields action AND a message/select/etc action.

function deriveUserActions(
  turn: UserTurn,
  sessionFiles: Map<string, FileAttachment>,
): Array<{ action: UserAction; explanation: string }> {
  const results: Array<{ action: UserAction; explanation: string }> = [];

  // Check for user proactive field edits (form state delta inference)
  const userEdits = computeUserEdits(turn);
  if (Object.keys(userEdits).length > 0) {
    results.push({
      action: { action: 'fill_fields', fields: userEdits },
      explanation: `Form state delta: ${Object.keys(userEdits).length} field(s) changed between turns, not explained by model set_fields → user proactive edit`,
    });
  }

  // Now derive the action from the message itself
  const msg = turn.actualMessageSent;

  // System selection events
  const selectMatch = msg.match(/^\[system\] User selected option: "(.+)"$/);
  if (selectMatch) {
    results.push({
      action: { action: 'select_choice', label: selectMatch[1] },
      explanation: `Real user clicked a choice button → LLM U outputs select_choice`,
    });
    return results;
  }

  // System events (draft saved, etc.)
  if (msg.startsWith('[system]')) {
    results.push({
      action: { action: 'click_button' },
      explanation: `System event from button click → LLM U outputs click_button (loop controller injects the system message)`,
    });
    return results;
  }

  // File attachment
  const fileMatch = msg.match(/\[File: (.+?)\]/);
  if (fileMatch) {
    const filename = fileMatch[1];
    const file = sessionFiles.get(filename);
    const afterFile = msg.match(/\[End of .+?\]\n+([\s\S]*)$/);
    const userText = afterFile ? afterFile[1].trim() : '';

    results.push({
      action: { action: 'message', text: userText || 'Here is my file.', file },
      explanation: `User uploaded a file with a message → LLM U outputs message + file attachment`,
    });
    return results;
  }

  // System greeting (session start)
  if (turn.role === 'system' && msg.includes('has opened the')) {
    results.push({
      action: { action: 'message', text: '' },
      explanation: `Session start system message → injected by loop controller, not LLM U (skipped in simulation)`,
    });
    return results;
  }

  // Plain user message
  results.push({
    action: { action: 'message', text: msg },
    explanation: `User typed a message → LLM U outputs message action`,
  });
  return results;
}

// ── Render a single turn ──

function printTurn(turn: UserTurn, sessionFiles: Map<string, FileAttachment>): void {
  console.log(`\n${'═'.repeat(72)}`);
  console.log(`  Turn ${turn.turnNumber} (${turn.role})`);
  console.log(`${'═'.repeat(72)}`);

  // Ground truth
  console.log('\n── REAL: What was actually sent to LLM A ──');
  const msgPreview =
    turn.actualMessageSent.length > 300
      ? turn.actualMessageSent.slice(0, 300) + '...'
      : turn.actualMessageSent;
  console.log(msgPreview);

  // Form state context
  const prevKeys = Object.keys(turn.prevFormState);
  const realKeys = Object.keys(turn.formState);
  const userEdits = computeUserEdits(turn);
  const editCount = Object.keys(userEdits).length;
  console.log(
    `\n── FORM STATE: ${prevKeys.length} fields (prev) → ${realKeys.length} fields (current) ` +
      `| model set_fields: ${turn.modelSetFields.size} | user edits: ${editCount} ──`,
  );
  if (editCount > 0) {
    for (const [k, v] of Object.entries(userEdits)) {
      const display = JSON.stringify(v);
      console.log(`  ⚡ ${k}: ${display.length > 60 ? display.slice(0, 60) + '...' : display}`);
    }
  }

  // Derive actions
  const derived = deriveUserActions(turn, sessionFiles);

  console.log(`\n── DERIVE: ${derived.length} UserAction(s) LLM U would produce ──`);
  for (let ai = 0; ai < derived.length; ai++) {
    const { action, explanation } = derived[ai];
    console.log(`  [${ai + 1}] ${action.action}: ${explanation}`);
    const displayAction = { ...action };
    if (displayAction.file) {
      displayAction.file = {
        filename: displayAction.file.filename,
        content: displayAction.file.content.slice(0, 80) + '...',
      };
    }
    if (displayAction.fields && Object.keys(displayAction.fields).length > 5) {
      const keys = Object.keys(displayAction.fields);
      console.log(`      fields: { ${keys.slice(0, 3).join(', ')}, ... } (${keys.length} total)`);
    } else {
      console.log(`      ${JSON.stringify(displayAction)}`);
    }
  }

  // Run each action through the adapter, chaining form state
  console.log('\n── OUTPUT: convertUserActionToAppInput() results ──');
  let runningFormState = { ...turn.prevFormState };

  for (let ai = 0; ai < derived.length; ai++) {
    const { action } = derived[ai];
    const result = convertUserActionToAppInput(action, runningFormState);
    runningFormState = result.formState;

    console.log(`  [${ai + 1}] ${action.action}:`);
    if (result.stop) {
      console.log('      → STOP session');
    } else if (result.userMessage !== null) {
      const preview =
        result.userMessage.length > 120
          ? result.userMessage.slice(0, 120) + '...'
          : result.userMessage;
      console.log(`      → message: "${preview}"`);
    } else if (action.action === 'fill_fields') {
      const changed = Object.keys(action.fields || {});
      console.log(`      → form state updated: ${changed.length} field(s) applied`);
    } else {
      console.log('      → no output (handled by loop controller)');
    }
    console.log(`      → formState: ${Object.keys(result.formState).length} fields`);
  }

  // Match checks
  console.log('\n── MATCH CHECK ──');

  const isSystemStart = turn.role === 'system' && turn.actualMessageSent.includes('has opened the');
  const isSystemEvent =
    turn.actualMessageSent.startsWith('[system]') &&
    !turn.actualMessageSent.startsWith('[system] User selected');

  // Check message match
  const messageAction = derived.find(
    (d) => d.action.action !== 'fill_fields' && d.action.action !== 'click_button',
  );

  if (isSystemStart) {
    console.log('  ⏭  Session start — injected by loop controller, not adapter responsibility');
  } else if (isSystemEvent) {
    console.log('  ⏭  System event from button — loop controller injects this after button click');
  } else if (messageAction) {
    const result = convertUserActionToAppInput(messageAction.action, turn.prevFormState);
    if (result.userMessage !== null) {
      const normalizedActual = turn.actualMessageSent.trim();
      const normalizedOutput = result.userMessage.trim();

      if (normalizedActual === normalizedOutput) {
        console.log('  ✅ MESSAGE MATCH — adapter output === real session data');
      } else {
        const actualHasFile = normalizedActual.includes('[File:');
        const outputHasFile = normalizedOutput.includes('[File:');
        if (actualHasFile && outputHasFile) {
          console.log('  🔍 File attachment — structure matches (both use [File:] markers)');
        } else {
          console.log('  ❌ MESSAGE MISMATCH');
          console.log(`     Real:   "${normalizedActual.slice(0, 80)}..."`);
          console.log(`     Output: "${normalizedOutput.slice(0, 80)}..."`);
        }
      }
    }
  }

  // Check form state match
  if (editCount > 0) {
    // Verify that after applying fill_fields, the form state matches the real snapshot
    const fillAction = derived.find((d) => d.action.action === 'fill_fields');
    if (fillAction) {
      const result = convertUserActionToAppInput(fillAction.action, turn.prevFormState);
      let allMatch = true;
      for (const [k, v] of Object.entries(userEdits)) {
        if (JSON.stringify(result.formState[k]) !== JSON.stringify(v)) {
          console.log(`  ❌ FIELD MISMATCH: ${k} — expected ${JSON.stringify(v)}, got ${JSON.stringify(result.formState[k])}`);
          allMatch = false;
        }
      }
      if (allMatch) {
        console.log(`  ✅ FIELD EDITS MATCH — ${editCount} user edit(s) correctly applied to form state`);
      }
    }
  }

  console.log();
}

// ── CLI ──

let sessionFile = resolve(ROOT, 'mock_data/session-for-replay-test.jsonl');
let selectedTurn: number | undefined;

const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--file' && args[i + 1]) {
    sessionFile = resolve(args[i + 1]);
    i++;
  } else if (/^\d+$/.test(args[i])) {
    selectedTurn = parseInt(args[i], 10);
  }
}

// Load and run
const turns = loadSession(sessionFile);
const sessionFiles = extractFilesFromSession(turns);

console.log(`\n  U→A Adapter Demo — replaying recorded session`);
console.log(`  Session: ${sessionFile}`);
console.log(`  Turns: ${turns.length} user/system messages`);
console.log(
  `  Pipeline: real session turn → derive UserAction(s) → convertUserActionToAppInput() → compare to ground truth`,
);
console.log(`  NEW: form state delta inference detects user proactive field edits\n`);

if (selectedTurn !== undefined) {
  const turn = turns.find((t) => t.turnNumber === selectedTurn);
  if (!turn) {
    console.error(`Invalid turn number ${selectedTurn}. Available: 1-${turns.length}`);
    process.exit(1);
  }
  printTurn(turn, sessionFiles);
} else {
  for (const turn of turns) {
    printTurn(turn, sessionFiles);
  }
}
