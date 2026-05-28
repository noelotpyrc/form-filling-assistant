/**
 * E2E Scenario Runner — Live Mode
 *
 * Replicates the browser's multi-turn chat loop in Node.js:
 *   build system prompt → POST /api/generate → parse SSE → parse actions → update form state → next turn
 *
 * No assertions — just generates structured logs for analysis.
 *
 * Usage:
 *   npm run build
 *   npm run e2e                          # run all 3 scenarios
 *   npm run e2e -- northfield            # run just Northfield CS
 *   npm run e2e -- westbrook             # run just Westbrook AI
 *   npm run e2e -- patient               # run just Patient Intake
 *   npm run e2e -- northfield westbrook  # run two
 *
 * Output:
 *   Console: human-readable turn-by-turn summary
 *   JSON:    packages/integration-tests/e2e-logs/<scenario>-<timestamp>.json
 */

import { JSDOM } from 'jsdom';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { startServer, type ManagedServer } from '../helpers/server-manager.js';

// ── Paths ──

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..');
const WEB_APP_PORT = 3004;
const WEB_APP_URL = `http://localhost:${WEB_APP_PORT}`;
const MAX_TURNS = 20; // safety limit per scenario

// ── Load browser modules via JSDOM ──

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function loadBrowserModule(relativePath: string): any {
  const code = readFileSync(resolve(ROOT, relativePath), 'utf-8');
  const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
    runScripts: 'dangerously',
  });
  dom.window.eval(code);
  return dom.window;
}

const SystemPrompt = loadBrowserModule('packages/web-app/public/js/system-prompt.js').SystemPrompt as {
  build: (formMeta: unknown, vaultSummary: string, formState: Record<string, unknown>) => string;
};

const ActionParser = loadBrowserModule('packages/web-app/public/js/action-parser.js').ActionParser as {
  parseActions: (response: string) => Array<{ type: string; [key: string]: unknown }>;
  extractText: (response: string) => string;
};

// ── Types ──

type FieldEdit = { type: 'field_edit'; fields: Record<string, unknown> };
type QueuedAction = string | FieldEdit;

interface Scenario {
  name: string;
  formJsonFile: string; // relative to packages/web-app/public/forms/
  preferredValues: Set<string>; // for auto-selecting ask_choice options
  actions: QueuedAction[];
  email?: string;
  initialFormValues?: Record<string, unknown>;
}

interface TurnLog {
  turn: number;
  role: 'user' | 'system' | 'field_edit';
  input: string;
  rawResponse: string;
  parsedText: string;
  parsedActions: unknown[];
  formStateDelta: Record<string, unknown>;
  formStateSnapshot: Record<string, unknown>;
  sessionId: string | null;
  durationMs: number;
  costUsd: number;
}

interface GenerateResult {
  text: string;
  sessionId: string;
  durationMs: number;
  costUsd: number;
}

// ══════════════════════════════════════════════════════════════════════
// SCENARIOS
// ══════════════════════════════════════════════════════════════════════

const SCENARIOS: Record<string, Scenario> = {
  northfield: {
    name: 'northfield-cs-fulltime',
    formJsonFile: 'masters-northfield.json',
    preferredValues: new Set(['cs', 'fall_2026', 'full_time']),
    actions: [
      // Program selection + enrollment
      "Hi, I'd like to apply for the Computer Science masters program, full-time, starting Fall 2026. I haven't applied to Northfield before.",

      // Personal information (all at once)
      'My name is Jane Smith, preferred name Jane. Born 1998-05-15, female. US citizen living in the US. Email: jane.smith@email.com, phone: +1-555-0123. Mailing address: 123 Oak Street, Springfield, IL 62704.',

      // Education
      "I have a Bachelor's in Computer Science from MIT. GPA was 3.85 on a 4.0 scale. I studied from 2016-09 to 2020-05. I don't have my transcript ready to upload yet.",

      // Test scores (CS waives GRE, US citizen skips TOEFL)
      "No GRE needed since CS waived it, and I'm a US citizen so no TOEFL either.",

      // Work experience
      'Yes, I have work experience. I worked at Google as a Software Engineer from 2020-06 to 2024-01. I developed backend microservices for Google Cloud Platform.',

      // Request draft save
      "I don't have my statement of purpose or resume ready yet. Can we save this as a draft and come back to finish later?",
    ],
  },

  'northfield-returning': {
    name: 'northfield-cs-returning',
    formJsonFile: 'masters-northfield.json',
    preferredValues: new Set(['cs', 'fall_2026', 'full_time']),
    email: 'jane.smith@email.com',
    initialFormValues: {
      'program': 'cs',
      'start_term': 'fall_2026',
      'enrollment_type': 'full_time',
      'previous_applicant': 'no',
      'full_name': 'Jane Smith',
      'preferred_name': 'Jane',
      'date_of_birth': '1998-05-15',
      'gender': 'female',
      'citizenship': 'us_citizen',
      'country_of_residence': 'US',
      'email': 'jane.smith@email.com',
      'phone': '+1-555-0123',
      'mailing_address': '123 Oak Street, Springfield, IL 62704',
      'degrees-0-institution': 'MIT',
      'degrees-0-degree_type': 'bachelors',
      'degrees-0-field_of_study': 'Computer Science',
      'degrees-0-gpa': '3.85',
      'degrees-0-gpa_scale': '4.0',
      'degrees-0-start_date': '2016-09',
      'degrees-0-end_date': '2020-05',
    },
    actions: [
      // Returning user — model sees pre-filled formValues and this message
      'The user has returned to continue the Masters Application - Northfield University form. Their email is jane.smith@email.com. Their saved draft has been restored. Show them an overview of what\'s been filled and what\'s still missing, then ask where they\'d like to pick up.',

      // Upload transcript (file attachment)
      '[File: Transcript.pdf]\nUNOFFICIAL TRANSCRIPT\nMassachusetts Institute of Technology\n\nStudent: Jane Smith\nStudent ID: 912345678\nDegree: Bachelor of Science in Computer Science\nConferred: May 2020\n\nCourse History:\nFall 2016: 6.001 Intro to CS (A), 18.01 Calculus I (A-), 8.01 Physics I (B+)\nSpring 2017: 6.002 Circuits (A), 18.02 Calculus II (A), 6.006 Algorithms (A)\nFall 2017: 6.004 Computation Structures (A-), 6.036 Machine Learning (A), 18.06 Linear Algebra (A)\nSpring 2018: 6.033 Computer Systems (A), 6.046 Design of Algorithms (A-), 6.034 AI (B+)\nFall 2018: 6.824 Distributed Systems (A), 6.828 Operating Systems (A), 6.172 Performance Engineering (A-)\nSpring 2019: 6.858 Computer Security (A), 6.S081 OS Engineering (A), 6.854 Advanced Algorithms (B+)\nFall 2019: 6.857 Network Security (A-), 6.867 Machine Learning (A), Thesis Research (A)\nSpring 2020: Thesis: Distributed Consensus in Heterogeneous Networks (A)\n\nCumulative GPA: 3.85 / 4.0\nDean\'s List: Fall 2016 - Spring 2020\n[End of Transcript.pdf]\n\nHere\'s my transcript from MIT.',

      // Work experience
      'Yes, I have work experience. I worked at Google as a Software Engineer from 2020-06 to 2024-01. I developed backend microservices for Google Cloud Platform.',

      // User directly edits a field in the form panel (corrects phone number)
      { type: 'field_edit' as const, fields: { phone: '+1-555-0199' } },

      // Then mentions it in chat
      'By the way, I updated my phone number in the form. Also, I still need to write my statement of purpose. Can we save this as a draft?',
    ],
  },

  westbrook: {
    name: 'westbrook-ai-research',
    formJsonFile: 'masters-westbrook.json',
    preferredValues: new Set([]),
    actions: [
      // Personal info
      "Hi, I'm Alex Chen. Born 1995-11-20. I'm a US citizen. Email: alex.chen@email.com, phone: +1-555-0456. Address: 456 Elm Ave, San Jose, CA 95112.",

      // Education
      "I have a Bachelor's in Computer Science from Stanford, GPA 3.72 on a 4.0 scale, from 2013-09 to 2017-06.",

      // Work experience
      "Yes, I have work experience. I've been working at DeepMind as a Research Engineer from 2017-07 to present. I work on reinforcement learning systems for robotics.",

      // Research
      "I have 3 publications — two workshop papers at NeurIPS and one preprint on arXiv. My research interests are in reinforcement learning, multi-agent systems, and robotics. I'd be interested in working with Dr. Sarah Martinez if she's available.",

      // Technical skills
      "I'm proficient in Python and C++. My technical background includes extensive work with PyTorch, JAX, and TensorFlow. I've built distributed training pipelines and have experience with ROS for robotics applications.",
    ],
  },

  patient: {
    name: 'patient-checkup',
    formJsonFile: 'patient-riverside.json',
    preferredValues: new Set(['new_patient_checkup']),
    actions: [
      // Personal info + emergency contact
      "Hi, I'm Maria Garcia, prefer to go by Maria. Born 1982-03-22, female. She/her pronouns. Married. Email: maria.garcia@email.com, phone: 555-0789. I live at 789 Pine St, Riverside, CA 92501. Emergency contact is my husband Carlos Garcia, phone 555-0790, he's my spouse.",

      // Insurance
      "Yes, I have insurance through Blue Cross Blue Shield, plan is PPO Gold. Member ID is BCB123456789, group number GRP-5678. Insurance phone is 800-555-1234. I don't have my card handy to upload right now.",

      // Reason for visit
      "I'm here for a new patient checkup. No specific concerns, just haven't had a physical in a while. Morning appointments work best for me.",

      // Medical history
      "I've been diagnosed with hypertension and anxiety. No surgeries. I'm allergic to penicillin — I get a rash, it's moderate severity. My immunizations are up to date. Last physical was about 2023-06.",

      // Medications + supplements
      'I take Lisinopril 10mg daily for blood pressure, prescribed by Dr. Johnson. I also take a daily multivitamin and vitamin D 2000IU supplement.',

      // Family history + lifestyle + consent
      "My father had heart disease and hypertension. My mother has diabetes type 2. No recreational drugs, never used tobacco. I drink occasionally, maybe 2 drinks a week. I exercise 3-4 times a week, mostly Mediterranean diet, about 7 hours of sleep. Yes, I consent to treatment and acknowledge the privacy notice. I authorize billing to my insurance. Typed signature: Maria Garcia, date is 2026-03-11.",
    ],
  },
};

// ══════════════════════════════════════════════════════════════════════
// SSE CLIENT
// ══════════════════════════════════════════════════════════════════════

async function doGenerate(fullPrompt: string, sessionId: string | null): Promise<GenerateResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000); // 2 min per turn

  try {
    const res = await fetch(`${WEB_APP_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: fullPrompt, resume: sessionId || undefined }),
      signal: controller.signal,
    });

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${await res.text()}`);
    }

    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullText = '';
    let eventType: string | null = null;
    let resultSessionId = '';
    let durationMs = 0;
    let costUsd = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop()!;

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith('data: ') && eventType) {
          let data: Record<string, unknown>;
          try {
            data = JSON.parse(line.slice(6));
          } catch {
            eventType = null;
            continue;
          }
          switch (eventType) {
            case 'text':
              fullText += data.text as string;
              process.stdout.write('.'); // progress dots
              break;
            case 'done':
              resultSessionId = data.session_id as string;
              durationMs = data.duration_ms as number;
              costUsd = data.cost_usd as number;
              break;
            case 'error':
              throw new Error(`SSE error: ${data.message}`);
          }
          eventType = null;
        }
      }
    }

    return { text: fullText, sessionId: resultSessionId, durationMs, costUsd };
  } finally {
    clearTimeout(timeout);
  }
}

// ══════════════════════════════════════════════════════════════════════
// FORM STATE HELPERS
// ══════════════════════════════════════════════════════════════════════

function makeCompositeId(groupId: string, entryIndex: number, subFieldId: string): string {
  return `${groupId}-${entryIndex}-${subFieldId}`;
}

function applySetFields(
  fields: Array<{ field_id: string; value: unknown }>,
  formValues: Record<string, unknown>,
): Record<string, unknown> {
  const delta: Record<string, unknown> = {};
  for (const { field_id, value } of fields) {
    const dotMatch = field_id.match(/^(.+)\.(\d+)\.(.+)$/);
    const compositeId = dotMatch
      ? makeCompositeId(dotMatch[1], parseInt(dotMatch[2]), dotMatch[3])
      : field_id;
    formValues[compositeId] = value;
    delta[compositeId] = value;
  }
  return delta;
}

// ══════════════════════════════════════════════════════════════════════
// SCENARIO RUNNER
// ══════════════════════════════════════════════════════════════════════

async function runScenario(scenario: Scenario): Promise<{
  totalTurns: number;
  totalDurationMs: number;
  totalCostUsd: number;
  logPath: string;
}> {
  // Load form metadata
  const formMeta = JSON.parse(
    readFileSync(
      resolve(ROOT, 'packages/web-app/public/forms', scenario.formJsonFile),
      'utf-8',
    ),
  );

  console.log(`\n${'='.repeat(70)}`);
  console.log(`  Scenario: ${scenario.name}`);
  console.log(`  Form: ${formMeta.name}`);
  console.log(`  Scripted actions: ${scenario.actions.length}`);
  console.log(`${'='.repeat(70)}\n`);

  const formValues: Record<string, unknown> = { ...(scenario.initialFormValues ?? {}) };
  let sessionId: string | null = null;
  const turns: TurnLog[] = [];
  const pendingActions: QueuedAction[] = [...scenario.actions];
  let turnNumber = 0;
  let totalCost = 0;
  let totalDuration = 0;

  while (pendingActions.length > 0 && turnNumber < MAX_TURNS) {
    const action = pendingActions.shift()!;

    // Handle field_edit: apply state change, no model call
    if (typeof action !== 'string') {
      turnNumber++;
      const editFields = Object.entries(action.fields).map(([field_id, value]) => ({ field_id, value }));
      const delta = applySetFields(editFields, formValues);
      console.log(`── Turn ${turnNumber} (field_edit) ──`);
      console.log(`  Fields: ${Object.keys(delta).join(', ')}`);
      turns.push({
        turn: turnNumber,
        role: 'field_edit',
        input: JSON.stringify(action.fields),
        rawResponse: '',
        parsedText: '',
        parsedActions: [],
        formStateDelta: delta,
        formStateSnapshot: { ...formValues },
        sessionId,
        durationMs: 0,
        costUsd: 0,
      });
      console.log();
      continue;
    }

    const message = action;
    turnNumber++;

    const role = message.startsWith('[system]') ? 'system' : 'user';
    console.log(`── Turn ${turnNumber} (${role}) ──`);
    console.log(
      `  IN:  ${message.slice(0, 120)}${message.length > 120 ? '...' : ''}`,
    );

    // Build system prompt (same as browser does each turn)
    const systemPrompt = SystemPrompt.build(formMeta, '', formValues);
    const fullPrompt = systemPrompt + '\n\n---\n\nUser message: ' + message;

    // Call Claude via web-app proxy
    process.stdout.write('  ');
    let result: GenerateResult;
    try {
      result = await doGenerate(fullPrompt, sessionId);
    } catch (err) {
      console.error(`\n  ERROR: ${(err as Error).message}`);
      turns.push({
        turn: turnNumber,
        role,
        input: message,
        rawResponse: `ERROR: ${(err as Error).message}`,
        parsedText: '',
        parsedActions: [],
        formStateDelta: {},
        formStateSnapshot: { ...formValues },
        sessionId,
        durationMs: 0,
        costUsd: 0,
      });
      continue;
    }
    console.log(); // end progress dots line

    sessionId = result.sessionId;
    totalCost += result.costUsd;
    totalDuration += result.durationMs;

    // Parse response
    const parsedText = ActionParser.extractText(result.text);
    const parsedActions = ActionParser.parseActions(result.text);

    console.log(`  OUT: ${parsedText.slice(0, 150)}${parsedText.length > 150 ? '...' : ''}`);
    console.log(
      `  Actions: ${parsedActions.length === 0 ? 'none' : parsedActions.map((a) => a.type).join(', ')}`,
    );
    console.log(`  (${result.durationMs}ms, $${result.costUsd.toFixed(4)})`);

    // Apply actions to form state
    let delta: Record<string, unknown> = {};
    for (const action of parsedActions) {
      if (action.type === 'set_fields' && Array.isArray(action.fields)) {
        delta = {
          ...delta,
          ...applySetFields(
            action.fields as Array<{ field_id: string; value: unknown }>,
            formValues,
          ),
        };
      }

      // Auto-respond to ask_choice
      if (action.type === 'ask_choice' && Array.isArray(action.options)) {
        const options = action.options as Array<{ label: string; value: string }>;
        const preferred = options.find((o) => scenario.preferredValues.has(o.value));
        const selected = preferred || options[0];
        const systemEvent = `[system] User selected option: "${selected.label}"`;
        pendingActions.unshift(systemEvent);
        console.log(`  → ask_choice auto-select: "${selected.label}"`);
      }

      // Auto-respond to show_button (inject click event + API response event)
      if (action.type === 'show_button' && action.button) {
        if (action.button === 'save_draft') {
          pendingActions.unshift(`[system] Draft saved successfully.`);
          pendingActions.unshift(`[system] User clicked: Save Draft`);
          console.log(`  → show_button auto-click: Save Draft`);
        } else {
          const ref = `APP-2026-${String(Math.floor(Math.random() * 100000)).padStart(5, '0')}`;
          pendingActions.unshift(`[system] Submission saved. Reference: ${ref}`);
          pendingActions.unshift(`[system] User clicked: Submit`);
          console.log(`  → show_button auto-click: Submit`);
        }
      }
    }

    if (Object.keys(delta).length > 0) {
      console.log(`  State delta: +${Object.keys(delta).length} fields`);
    }

    // Log turn
    turns.push({
      turn: turnNumber,
      role,
      input: message,
      rawResponse: result.text,
      parsedText,
      parsedActions,
      formStateDelta: delta,
      formStateSnapshot: { ...formValues },
      sessionId: result.sessionId,
      durationMs: result.durationMs,
      costUsd: result.costUsd,
    });

    console.log();
  }

  if (turnNumber >= MAX_TURNS) {
    console.log(`⚠ Hit max turn limit (${MAX_TURNS})\n`);
  }

  // Summary
  console.log(`${'─'.repeat(70)}`);
  console.log(`  ${scenario.name} DONE`);
  console.log(`  Turns: ${turnNumber}  |  Duration: ${(totalDuration / 1000).toFixed(1)}s  |  Cost: $${totalCost.toFixed(4)}`);
  console.log(`  Form fields filled: ${Object.keys(formValues).length}`);
  console.log(`${'─'.repeat(70)}\n`);

  // Write log file
  const logDir = resolve(ROOT, 'packages', 'integration-tests', 'e2e-logs');
  mkdirSync(logDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logPath = resolve(logDir, `${scenario.name}-${timestamp}.json`);

  const logData = {
    scenario: scenario.name,
    form: formMeta.name,
    timestamp: new Date().toISOString(),
    totalTurns: turnNumber,
    totalDurationMs: totalDuration,
    totalCostUsd: totalCost,
    finalFormState: formValues,
    turns,
  };

  writeFileSync(logPath, JSON.stringify(logData, null, 2));
  console.log(`  Log: ${logPath}`);

  return { totalTurns: turnNumber, totalDurationMs: totalDuration, totalCostUsd: totalCost, logPath };
}

// ══════════════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════════════

async function main(): Promise<void> {
  // Parse CLI args to select scenarios
  const args = process.argv.slice(2);
  const selectedKeys = args.length > 0
    ? args.filter((a) => a in SCENARIOS)
    : Object.keys(SCENARIOS);

  if (selectedKeys.length === 0) {
    console.error(`Unknown scenario(s): ${args.join(', ')}`);
    console.error(`Available: ${Object.keys(SCENARIOS).join(', ')}`);
    process.exit(1);
  }

  console.log(`\n╔${'═'.repeat(68)}╗`);
  console.log(`║  E2E Runner — ${selectedKeys.length} scenario(s): ${selectedKeys.join(', ')}`.padEnd(69) + '║');
  console.log(`║  Max turns per scenario: ${MAX_TURNS}`.padEnd(69) + '║');
  console.log(`╚${'═'.repeat(68)}╝\n`);

  // Start server
  let server: ManagedServer | null = null;
  try {
    console.log('Starting web-app server...');
    server = await startServer('web-app', WEB_APP_PORT);
    console.log(`  ✓ web-app on port ${WEB_APP_PORT}\n`);
  } catch (err) {
    console.error('Failed to start web-app server:', (err as Error).message);
    console.error('Make sure to run `npm run build` first.');
    process.exit(1);
  }

  const results: Array<{ scenario: string; turns: number; durationMs: number; costUsd: number; logPath: string }> = [];

  try {
    for (const key of selectedKeys) {
      const result = await runScenario(SCENARIOS[key]);
      results.push({
        scenario: key,
        turns: result.totalTurns,
        durationMs: result.totalDurationMs,
        costUsd: result.totalCostUsd,
        logPath: result.logPath,
      });
    }

    // Grand summary
    const totalCost = results.reduce((sum, r) => sum + r.costUsd, 0);
    const totalDuration = results.reduce((sum, r) => sum + r.durationMs, 0);
    const totalTurns = results.reduce((sum, r) => sum + r.turns, 0);

    console.log(`\n╔${'═'.repeat(68)}╗`);
    console.log(`║  ALL DONE`.padEnd(69) + '║');
    console.log(`║  Scenarios: ${results.length}  |  Turns: ${totalTurns}  |  Duration: ${(totalDuration / 1000).toFixed(1)}s  |  Cost: $${totalCost.toFixed(4)}`.padEnd(69) + '║');
    console.log(`╚${'═'.repeat(68)}╝`);

    for (const r of results) {
      console.log(`  ${r.scenario}: ${r.logPath}`);
    }
    console.log();
  } finally {
    if (server) {
      server.kill();
      console.log('  Server stopped.\n');
    }
  }
}

main().catch((err) => {
  console.error('\nE2E runner failed:', err);
  process.exit(1);
});
