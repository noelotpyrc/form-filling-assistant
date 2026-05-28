#!/usr/bin/env npx tsx
/**
 * Demo: LLM U Candidate Generation
 *
 * Replays a recorded session's screen views through the LLM U prompt,
 * showing what candidates LLM U produces for each turn.
 *
 * For each turn:
 *   1. Renders the screen view (same as demo-a2u)
 *   2. Sends it to LLM U with the system prompt (persona + profile + action catalog)
 *   3. Prints LLM U's ranked candidate actions
 *   4. Shows what the real user actually did (ground truth from session)
 *
 * Usage:
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-llm-u.ts
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-llm-u.ts 3
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-llm-u.ts --persona jane --profile impatient
 *   npx tsx packages/integration-tests/src/e2e/simulator/demo-llm-u.ts --model haiku --turns 1-3
 */

import { readFileSync, readdirSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';
import { ClaudeAgent } from '@form-filling-assistant/claude-agent';
import { renderScreenView, type ParsedAction, type FormMeta } from './view-renderer.js';
import { buildLlmUSystemPrompt } from './llm-u-prompt.js';
import { jane, alex, maria, type Persona } from './personas.js';

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..', '..');

// ── Load ActionParser from browser JS ──

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

function loadFormSchema(formId: string): FormMeta {
  const formsDir = resolve(ROOT, 'packages/web-app/public/forms');
  for (const file of readdirSync(formsDir)) {
    if (!file.endsWith('.json')) continue;
    const form = JSON.parse(readFileSync(resolve(formsDir, file), 'utf-8'));
    if (form.form_id === formId || file.includes(formId.replace('masters-', ''))) {
      return { name: form.name, schema: form.schema };
    }
  }
  throw new Error(`Could not find form schema for: ${formId}`);
}

// ── JSONL types ──

interface SessionEntry {
  type: string;
  raw_text?: string;
  form_state_snapshot?: Record<string, unknown>;
  user_message?: string;
  form_id?: string;
  message?: string;
  role?: string;
}

interface Turn {
  turnNumber: number;
  userMessage: string;
  formState: Record<string, unknown>;
  rawText: string;
}

// ── Load session ──

function loadSession(filePath: string): { formId: string; turns: Turn[] } {
  const lines = readFileSync(filePath, 'utf-8').trim().split('\n');
  const entries: SessionEntry[] = lines.map(l => JSON.parse(l));

  const sessionStart = entries.find(e => e.type === 'session_start');
  const formId = sessionStart?.form_id || 'unknown';

  const turns: Turn[] = [];
  let turnNumber = 0;

  for (let i = 0; i < entries.length; i++) {
    if (entries[i].type === 'model_output' && entries[i].raw_text) {
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
      turns.push({ turnNumber, userMessage, formState, rawText: entries[i].raw_text! });
    }
  }

  return { formId, turns };
}

// ── Render screen view for a turn ──

function renderTurnScreen(turn: Turn, formMeta: FormMeta): string {
  const actions = ActionParser.parseActions(turn.rawText);
  const assistantText = ActionParser.extractText(turn.rawText);
  return renderScreenView(assistantText, actions, formMeta, turn.formState);
}

// ── LLM U candidate response type ──

interface Candidate {
  rank: number;
  intent: string;
  reasoning: string;
  actions: Array<{ action: string; text?: string; label?: string; fields?: Record<string, unknown>; file?: unknown }>;
}

interface LlmUResponse {
  candidates: Candidate[];
}

// ── JSON schema for structured output ──

const CANDIDATES_SCHEMA = {
  type: 'object',
  properties: {
    candidates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          rank: { type: 'number' },
          intent: { type: 'string' },
          reasoning: { type: 'string' },
          actions: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                action: { type: 'string', enum: ['message', 'select_choice', 'fill_fields', 'click_button', 'stop'] },
                text: { type: 'string' },
                file: { type: 'string' },
                label: { type: 'string' },
                fields: { type: 'object' },
              },
              required: ['action'],
            },
          },
        },
        required: ['rank', 'intent', 'reasoning', 'actions'],
      },
    },
  },
  required: ['candidates'],
};

// ── CLI args ──

const PERSONAS: Record<string, Persona> = { jane, alex, maria };

let sessionFile = resolve(ROOT, 'mock_data/session-for-replay-test.jsonl');
let personaName = 'jane';
let profileName = 'thorough';
let modelName = 'sonnet';
let selectedTurns: number[] | undefined;

const args = process.argv.slice(2);
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--file' && args[i + 1]) { sessionFile = resolve(args[i + 1]); i++; }
  else if (args[i] === '--persona' && args[i + 1]) { personaName = args[i + 1]; i++; }
  else if (args[i] === '--profile' && args[i + 1]) { profileName = args[i + 1]; i++; }
  else if (args[i] === '--model' && args[i + 1]) { modelName = args[i + 1]; i++; }
  else if (args[i] === '--turns' && args[i + 1]) {
    const range = args[i + 1];
    if (range.includes('-')) {
      const [start, end] = range.split('-').map(Number);
      selectedTurns = Array.from({ length: end - start + 1 }, (_, j) => start + j);
    } else {
      selectedTurns = range.split(',').map(Number);
    }
    i++;
  }
  else if (/^\d+$/.test(args[i])) { selectedTurns = [parseInt(args[i], 10)]; }
}

const persona = PERSONAS[personaName];
if (!persona) {
  console.error(`Unknown persona: ${personaName}. Available: ${Object.keys(PERSONAS).join(', ')}`);
  process.exit(1);
}

// ── Load session + form ──

const { formId, turns } = loadSession(sessionFile);
const formMeta = loadFormSchema(formId);

// ── Build LLM U agent ──

const systemPrompt = buildLlmUSystemPrompt({ persona, profileName });

const agent = new ClaudeAgent({
  model: modelName,
  systemPrompt,
  dangerouslySkipPermissions: true,
});

// ── Run ──

const turnsToRun = selectedTurns
  ? turns.filter(t => selectedTurns!.includes(t.turnNumber))
  : turns;

console.log(`\n  LLM U Demo — candidate generation from recorded session`);
console.log(`  Session: ${sessionFile}`);
console.log(`  Persona: ${persona.name} | Profile: ${profileName} | Model: ${modelName}`);
console.log(`  Turns: ${turnsToRun.length} of ${turns.length}`);
console.log(`  System prompt: ${systemPrompt.length} chars\n`);

for (const turn of turnsToRun) {
  console.log(`\n${'═'.repeat(72)}`);
  console.log(`  Turn ${turn.turnNumber}`);
  console.log(`${'═'.repeat(72)}`);

  // Render screen view
  const screenView = renderTurnScreen(turn, formMeta);

  console.log('\n── SCREEN VIEW (sent to LLM U) ──');
  console.log(screenView);

  // Call LLM U
  console.log('\n── LLM U CANDIDATES ──');
  console.log('  (calling LLM...)');

  try {
    const response = await agent.askJson<LlmUResponse>(
      `Here is what you see on your screen right now:\n\n${screenView}`,
      CANDIDATES_SCHEMA,
    );

    for (const candidate of response.candidates) {
      console.log(`\n  [${candidate.rank}] ${candidate.intent}`);
      console.log(`      Reasoning: ${candidate.reasoning}`);
      for (const action of candidate.actions) {
        const actionDisplay = { ...action };
        // Truncate long text
        if (actionDisplay.text && actionDisplay.text.length > 100) {
          actionDisplay.text = actionDisplay.text.slice(0, 100) + '...';
        }
        if (actionDisplay.fields) {
          const keys = Object.keys(actionDisplay.fields);
          if (keys.length > 3) {
            console.log(`      Action: { action: "${action.action}", fields: { ${keys.slice(0, 3).join(', ')}, ... } (${keys.length} total) }`);
            continue;
          }
        }
        console.log(`      Action: ${JSON.stringify(actionDisplay)}`);
      }
    }
  } catch (err) {
    console.error(`  ❌ LLM call failed: ${err}`);
  }

  console.log();
}
