#!/usr/bin/env npx tsx
/**
 * Demo: A→U Adapter (full pipeline)
 *
 * Loads a REAL recorded session log (JSONL) and replays each LLM A turn
 * through the FULL pipeline:
 *   real raw_text from session → ActionParser.extractText() + parseActions()
 *   real form_state_snapshot from session → renderScreenView()
 *
 * Zero fabrication — every input comes from an actual recorded session.
 *
 * Usage:
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-a2u.ts
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-a2u.ts 3
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-a2u.ts --file path/to/session.jsonl
 */

import { readFileSync, readdirSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';
import { renderScreenView, type ParsedAction, type FormMeta } from './view-renderer.js';

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..', '..');

// ── Load ActionParser from browser JS ──

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function loadBrowserModule(relativePath: string): any {
  const code = readFileSync(resolve(ROOT, relativePath), 'utf-8');
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    runScripts: 'dangerously',
  });
  dom.window.eval(code);
  return dom.window;
}

const ActionParser = loadBrowserModule('packages/web-app/public/js/action-parser.js').ActionParser as {
  parseActions: (response: string) => ParsedAction[];
  extractText: (response: string) => string;
};

// ── Load form schemas ──

const FORM_SCHEMAS: Record<string, FormMeta> = {};

function loadFormSchema(formId: string): FormMeta {
  if (FORM_SCHEMAS[formId]) return FORM_SCHEMAS[formId];

  // Try common form file patterns
  const candidates = [
    `packages/web-app/public/forms/${formId}.json`,
    `packages/web-app/public/forms/masters-northfield.json`,
    `packages/web-app/public/forms/patient-riverside.json`,
  ];

  for (const candidate of candidates) {
    try {
      const form = JSON.parse(readFileSync(resolve(ROOT, candidate), 'utf-8'));
      if (form.form_id === formId || candidate.includes(formId.replace('masters-', ''))) {
        FORM_SCHEMAS[formId] = { name: form.name, schema: form.schema };
        return FORM_SCHEMAS[formId];
      }
    } catch {
      // skip
    }
  }

  // Fallback: load all forms and match by form_id
  const formsDir = resolve(ROOT, 'packages/web-app/public/forms');
  try {
    for (const file of readdirSync(formsDir)) {
      if (!file.endsWith('.json')) continue;
      const form = JSON.parse(readFileSync(resolve(formsDir, file), 'utf-8'));
      if (form.form_id === formId) {
        FORM_SCHEMAS[formId] = { name: form.name, schema: form.schema };
        return FORM_SCHEMAS[formId];
      }
    }
  } catch {
    // skip
  }

  throw new Error(`Could not find form schema for form_id: ${formId}`);
}

// ── JSONL types ──

interface SessionEntry {
  type: string;
  ts: string;
  session_id: string;
  // model_output fields
  raw_text?: string;
  parsed_actions?: ParsedAction[];
  // model_input fields
  form_state_snapshot?: Record<string, unknown>;
  user_message?: string;
  // session_start fields
  form_id?: string;
  form_name?: string;
  // user_message fields
  message?: string;
  role?: string;
}

interface Turn {
  turnNumber: number;
  /** The user/system message that triggered this turn */
  userMessage: string;
  /** Form state at the time of model input */
  formState: Record<string, unknown>;
  /** Raw LLM A output (the actual text the model produced) */
  rawText: string;
}

// ── Load and parse session JSONL ──

function loadSession(filePath: string): { formId: string; formName: string; turns: Turn[] } {
  const lines = readFileSync(filePath, 'utf-8').trim().split('\n');
  const entries: SessionEntry[] = lines.map((line) => JSON.parse(line));

  // Find session metadata
  const sessionStart = entries.find((e) => e.type === 'session_start');
  const formId = sessionStart?.form_id || 'unknown';
  const formName = sessionStart?.form_name || 'Unknown Form';

  // Pair model_input + model_output entries into turns
  const turns: Turn[] = [];
  let turnNumber = 0;

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i];

    if (entry.type === 'model_output' && entry.raw_text) {
      // Look backward for the matching model_input
      let formState: Record<string, unknown> = {};
      let userMessage = '';

      for (let j = i - 1; j >= 0; j--) {
        if (entries[j].type === 'model_input') {
          formState = entries[j].form_state_snapshot || {};
          userMessage = entries[j].user_message || '';
          break;
        }
      }

      turnNumber++;
      turns.push({
        turnNumber,
        userMessage,
        formState,
        rawText: entry.raw_text,
      });
    }
  }

  return { formId, formName, turns };
}

// ── Form state helpers ──

function applySetFields(
  fields: Array<{ field_id: string; value: unknown }>,
  formValues: Record<string, unknown>,
): void {
  for (const { field_id, value } of fields) {
    const dotMatch = field_id.match(/^(.+)\.(\d+)\.(.+)$/);
    const compositeId = dotMatch
      ? `${dotMatch[1]}-${parseInt(dotMatch[2])}-${dotMatch[3]}`
      : field_id;
    formValues[compositeId] = value;
  }
}

// ── Render a single turn ──

function printTurn(turn: Turn, formMeta: FormMeta): void {
  console.log(`\n${'═'.repeat(72)}`);
  console.log(`  Turn ${turn.turnNumber}`);
  console.log(`${'═'.repeat(72)}`);

  // What triggered this turn
  console.log('\n── TRIGGER: User/System Message ──');
  const msgPreview = turn.userMessage.length > 200
    ? turn.userMessage.slice(0, 200) + '...'
    : turn.userMessage;
  console.log(msgPreview);

  // Form state at input time
  const stateKeys = Object.keys(turn.formState);
  console.log(`\n── FORM STATE: ${stateKeys.length} fields at input time ──`);
  if (stateKeys.length <= 10) {
    for (const key of stateKeys) {
      const val = turn.formState[key];
      const display = typeof val === 'object' ? JSON.stringify(val) : String(val);
      console.log(`  ${key}: ${display.length > 60 ? display.slice(0, 60) + '...' : display}`);
    }
  } else {
    // Show first 5 and last 5
    for (const key of stateKeys.slice(0, 5)) {
      const val = turn.formState[key];
      const display = typeof val === 'object' ? JSON.stringify(val) : String(val);
      console.log(`  ${key}: ${display.length > 60 ? display.slice(0, 60) + '...' : display}`);
    }
    console.log(`  ... (${stateKeys.length - 10} more) ...`);
    for (const key of stateKeys.slice(-5)) {
      const val = turn.formState[key];
      const display = typeof val === 'object' ? JSON.stringify(val) : String(val);
      console.log(`  ${key}: ${display.length > 60 ? display.slice(0, 60) + '...' : display}`);
    }
  }

  // Raw LLM A output
  console.log('\n── INPUT: Raw LLM A Output ──');
  console.log(turn.rawText);

  // Parse through ActionParser (the real pipeline)
  const parsedText = ActionParser.extractText(turn.rawText);
  const parsedActions = ActionParser.parseActions(turn.rawText) as ParsedAction[];

  console.log('\n── PARSE: ActionParser results ──');
  console.log(`  extractText(): "${parsedText.slice(0, 120)}${parsedText.length > 120 ? '...' : ''}"`);
  console.log(`  parseActions(): ${parsedActions.length} action(s)${parsedActions.length > 0 ? ' → ' + parsedActions.map((a) => a.type).join(', ') : ''}`);

  // Apply set_fields to get post-turn form state
  const formValues = { ...turn.formState };
  for (const action of parsedActions) {
    if (action.type === 'set_fields' && Array.isArray(action.fields)) {
      applySetFields(action.fields as Array<{ field_id: string; value: unknown }>, formValues);
    }
  }

  const newFields = Object.keys(formValues).length - stateKeys.length;
  if (newFields > 0) {
    console.log(`  set_fields applied: +${newFields} new fields in form state`);
  }

  // Render screen view (what LLM U sees)
  const view = renderScreenView(parsedText, parsedActions, formMeta, formValues);

  console.log('\n── OUTPUT: What LLM U Sees ──');
  console.log(view);
  console.log();
}

// ── CLI ──

// Parse args
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
const session = loadSession(sessionFile);
const formMeta = loadFormSchema(session.formId);

if (selectedTurn !== undefined) {
  const turn = session.turns.find((t) => t.turnNumber === selectedTurn);
  if (!turn) {
    console.error(`Invalid turn number ${selectedTurn}. Available: 1-${session.turns.length}`);
    process.exit(1);
  }
  printTurn(turn, formMeta);
} else {
  console.log(`\n  A→U Adapter Demo — replaying recorded session`);
  console.log(`  Session: ${sessionFile}`);
  console.log(`  Form: ${session.formName} (${session.formId})`);
  console.log(`  Turns: ${session.turns.length}`);
  console.log(`  Pipeline: real raw_text → ActionParser → renderScreenView → LLM U input\n`);

  for (const turn of session.turns) {
    printTurn(turn, formMeta);
  }
}
