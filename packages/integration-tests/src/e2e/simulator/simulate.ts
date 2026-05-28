/**
 * Scenario Simulator — Loop Controller
 *
 * Wires together:
 *   - LLM A (form-filling assistant) via ClaudeAgent.runInteractive()
 *   - LLM U (user simulator) via ClaudeAgent.runInteractive()
 *   - A→U adapter (view-renderer.ts) — renders what the user sees
 *   - U→A adapter (from run-scenario.ts patterns) — converts user actions to app format
 *
 * Both LLM A and LLM U use persistent interactive sessions (single CLI process
 * per simulation) to avoid re-spawning overhead on every turn. No web-app server needed.
 *
 * Produces session JSONL logs directly usable as training data.
 *
 * Usage:
 *   npm run e2e:sim -- --form northfield --persona jane --profile thorough
 *   npm run e2e:sim -- --runs 3
 *   npm run e2e:sim -- --form northfield --persona jane --profile impatient --seed 42
 *   npm run e2e:sim -- --form northfield --persona jane --profile thorough --sampling weighted --effort low
 *   npm run e2e:sim -- --form northfield --persona jane --profile thorough --split-prompt
 */

import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';
import { ClaudeAgent } from '@form-filling-assistant/claude-agent';
import { renderScreenView, type ParsedAction, type FormMeta, type ScreenViewOptions } from './view-renderer.js';
import { type UserAction } from './user-action.js';
import { buildLlmUSystemPrompt as buildLlmUPrompt } from './llm-u-prompt.js';
import { PERSONAS } from './personas.js';
import { SessionLogger } from './session-log.js';
import { processActions, buildLlmAMessage } from './action-processor.js';
import { generatePartialDraft, countFilledFields, draftSummary } from './draft-generator.js';

// ── Paths & constants ──

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..', '..');
const MAX_TURNS = 30;

// ── Forms ──

const FORMS: Record<string, string> = {
  northfield: 'masters-northfield.json',
  westbrook: 'masters-westbrook.json',
  patient: 'patient-riverside.json',
};

// ── Profiles ──

const PROFILES = ['thorough', 'impatient', 'confused', 'corrector', 'returning'];

// ── Load browser modules via JSDOM (same as run-scenario.ts) ──

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
  buildStatic: (formMeta: unknown) => string;
  buildDynamic: (formState: Record<string, unknown>) => string;
};

const ActionParser = loadBrowserModule('packages/web-app/public/js/action-parser.js').ActionParser as {
  parseActions: (response: string) => ParsedAction[];
  extractText: (response: string) => string;
};

// ── Types ──

type SamplingMode = 'greedy' | 'weighted' | 'uniform';

interface SimConfig {
  form: string;
  persona: string;
  profile: string;
  seed?: number;
  llmUModel?: string;
  sampling?: SamplingMode;
  effort?: string;
  splitPrompt?: boolean;
}

/**
 * Sample a candidate from LLM U's ranked list.
 * - greedy: always pick rank 1
 * - weighted: 40/35/25 distribution across top 3
 * - uniform: random pick
 */
function sampleCandidate(candidates: Array<{ intent: string }>, mode: SamplingMode): number {
  const n = candidates.length;
  if (n === 0) return -1;
  if (n === 1 || mode === 'greedy') return 0;

  if (mode === 'uniform') {
    return Math.floor(Math.random() * n);
  }

  // Weighted: 40/35/25 for rank 1/2/3 (normalized if fewer candidates)
  const weights = [0.4, 0.35, 0.25];
  const w = weights.slice(0, n);
  const sum = w.reduce((a, b) => a + b, 0);
  const r = Math.random() * sum;
  let cumulative = 0;
  for (let i = 0; i < w.length; i++) {
    cumulative += w[i];
    if (r <= cumulative) return i;
  }
  return 0; // fallback
}

// ══════════════════════════════════════════════════════════════════════
// LLM A: Form-filling assistant (via runInteractive — persistent process)
// ══════════════════════════════════════════════════════════════════════
//
// Previously went through the web-app server (/api/generate → SSE).
// Now uses a persistent interactive session directly, same as LLM U,
// to avoid re-spawning the CLI on every turn. The web-app server is
// no longer needed for simulation.

// ══════════════════════════════════════════════════════════════════════
// LLM U: User simulator (via ClaudeAgent.run — streaming with resume)
// ══════════════════════════════════════════════════════════════════════

/** LLM U candidate response types */
interface LlmUCandidate {
  rank: number;
  intent: string;
  reasoning: string;
  actions: UserAction[];
}

interface LlmUResponse {
  candidates: LlmUCandidate[];
}

/**
 * JSON schema for LLM U candidate output.
 * Used by sim.html's structured mode (/api/generate-json) and kept here as the
 * canonical reference for what the system prompt asks LLM U to produce.
 * The CLI simulator now uses streaming mode and parses JSON from text directly.
 */
const _CANDIDATES_SCHEMA = {
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

// ══════════════════════════════════════════════════════════════════════
// FORM STATE HELPERS (duplicated from run-scenario.ts)
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
// MAIN SIMULATION LOOP
// ══════════════════════════════════════════════════════════════════════

async function runSimulation(config: SimConfig): Promise<{
  turns: number;
  llmACostUsd: number;
  llmUCostUsd: number;
  logPath: string;
}> {
  const formFile = FORMS[config.form];
  if (!formFile) throw new Error(`Unknown form: ${config.form}`);

  const persona = PERSONAS[config.persona];
  if (!persona) throw new Error(`Unknown persona: ${config.persona}`);

  if (!PROFILES.includes(config.profile)) {
    throw new Error(`Unknown profile: ${config.profile}`);
  }

  // Load form metadata
  const formMeta = JSON.parse(
    readFileSync(resolve(ROOT, 'packages/web-app/public/forms', formFile), 'utf-8'),
  );
  const formMetaForRenderer: FormMeta = {
    name: formMeta.name,
    schema: formMeta.schema,
  };

  console.log(`\n${'='.repeat(70)}`);
  console.log(`  Simulation: ${config.form} × ${config.persona} × ${config.profile}`);
  console.log(`  Form: ${formMeta.name}`);
  console.log(`  Persona: ${persona.name}`);
  console.log(`  Profile: ${config.profile}`);
  console.log(`${'='.repeat(70)}\n`);

  // Initialize state — for "returning" profile, pre-populate with a partial draft
  const isReturning = config.profile === 'returning';
  const formValues: Record<string, unknown> = isReturning
    ? generatePartialDraft(persona, formMeta.schema, 0.5, config.seed)
    : {};
  if (isReturning) {
    const filled = countFilledFields(formValues);
    console.log(`  [returning] Pre-populated draft: ${filled} fields`);
    console.log(`  [returning] ${draftSummary(formValues, formMeta.schema)}`);
  }
  let turnNumber = 0;
  let llmACost = 0;
  let llmUCost = 0;
  const llmUModel = config.llmUModel || 'sonnet';
  const splitPrompt = config.splitPrompt || false;
  const logger = new SessionLogger();

  // Log state_init — full session context for replay
  logger.log({
    type: 'state_init',
    form_id: formMeta.form_id,
    form_name: formMeta.name,
    form_schema: formMeta.schema,
    initial_form_values: { ...formValues },
    persona: config.persona,
    persona_data: persona.data,
    profile: config.profile,
    session_config: {
      llm_a_model: 'sonnet', // LLM A always uses the server's default model
      llm_u_model: llmUModel,
      seed: config.seed,
      sampling: config.sampling || 'greedy',
      effort: config.effort || undefined,
      splitPrompt: splitPrompt,
    },
  });

  // Create LLM A as a persistent interactive session (single CLI process).
  // In split-prompt mode: static instructions go on the constructor (set once),
  // only dynamic state + user message sent per turn via send().
  // In default mode: everything sent as user message each turn (backward compat).
  const llmAStaticPrompt = splitPrompt ? SystemPrompt.buildStatic(formMeta) : undefined;
  if (splitPrompt) {
    console.log(`  [split-prompt] Static system prompt: ${llmAStaticPrompt!.length} chars (set once)`);
  }
  const llmAAgent = new ClaudeAgent({
    cwd: ROOT,
    dangerouslySkipPermissions: true,
    tools: '',       // LLM A outputs text+actions, no MCP tool calls
    maxTurns: 1,
    ...(llmAStaticPrompt ? { systemPrompt: llmAStaticPrompt } : {}),
  });
  const llmASession = llmAAgent.runInteractive();
  const llmAEvents = llmASession[Symbol.asyncIterator]();

  /** Send a prompt to LLM A and collect the response until the next `result` event. */
  async function callLlmA(fullPrompt: string): Promise<{
    text: string;
    durationMs: number;
    costUsd: number;
  }> {
    llmASession.send(fullPrompt);

    let text = '';
    let durationMs = 0;
    let costUsd = 0;

    while (true) {
      const { value: event, done } = await llmAEvents.next();
      if (done) throw new Error('LLM A session ended unexpectedly');

      if (event.type === 'text') {
        text += event.text;
      } else if (event.type === 'result') {
        durationMs = event.durationMs;
        costUsd = event.costUsd;
        break;
      }
    }

    return { text, durationMs, costUsd };
  }

  // Create LLM U as a persistent interactive session (single CLI process for
  // the entire simulation). This avoids re-spawning the CLI on every turn.
  const llmUSystemPrompt = buildLlmUPrompt({ persona, profileName: config.profile });
  const llmUAgent = new ClaudeAgent({
    model: llmUModel,
    systemPrompt: llmUSystemPrompt,
    dangerouslySkipPermissions: true,
    tools: '',       // No external tools — LLM U only produces JSON candidates
    maxTurns: 1,     // Single response per turn (no agentic loops)
    ...(config.effort ? { effort: config.effort as 'low' | 'medium' | 'high' } : {}),
  });
  const llmUSession = llmUAgent.runInteractive();

  // Event iterator — we consume from a single long-lived stream across all turns
  const llmUEvents = llmUSession[Symbol.asyncIterator]();

  /** Send a prompt to LLM U and collect the response until the next `result` event. */
  async function callLlmU(prompt: string): Promise<{
    text: string;
    durationMs: number;
    costUsd: number;
  }> {
    llmUSession.send(prompt);

    let text = '';
    let durationMs = 0;
    let costUsd = 0;

    while (true) {
      const { value: event, done } = await llmUEvents.next();
      if (done) throw new Error('LLM U session ended unexpectedly');

      if (event.type === 'text') {
        text += event.text;
      } else if (event.type === 'result') {
        durationMs = event.durationMs;
        costUsd = event.costUsd;
        break;
      }
    }

    return { text, durationMs, costUsd };
  }

  // ── Turn 0: LLM A greeting ──
  const greetingMessage = isReturning
    ? `[system] Draft restored. ${countFilledFields(formValues)} fields previously filled.\n\nI'm back to finish my application.`
    : `Help me fill out this form.`;
  let fullInitialPrompt: string;
  if (splitPrompt) {
    // In split mode, turn 0 sends dynamic state (if returning) + user message
    const dynamicState = SystemPrompt.buildDynamic(formValues);
    fullInitialPrompt = (dynamicState ? dynamicState + '\n\n---\n\n' : '') + 'User message: ' + greetingMessage;
  } else {
    const initialPrompt = SystemPrompt.build(formMeta, '', formValues);
    fullInitialPrompt = initialPrompt + '\n\n---\n\nUser message: ' + greetingMessage;
  }

  console.log('── Turn 0 (initial greeting) ──');
  console.log('  Sending initial message to LLM A...');

  logger.log({
    type: 'llm_a_input',
    turn: turnNumber,
    system_prompt_length: fullInitialPrompt.length,
    user_message: greetingMessage,
    resume_session_id: null,
  });

  let llmAResult = await callLlmA(fullInitialPrompt);
  llmACost += llmAResult.costUsd;

  const greetingText = ActionParser.extractText(llmAResult.text);
  const greetingActions = ActionParser.parseActions(llmAResult.text) as ParsedAction[];

  console.log(`  LLM A: ${greetingText.slice(0, 150)}...`);
  console.log(`  Actions: ${greetingActions.length === 0 ? 'none' : greetingActions.map((a) => a.type).join(', ')}`);
  console.log(`  (${llmAResult.durationMs}ms, $${llmAResult.costUsd.toFixed(4)})\n`);

  logger.log({
    type: 'llm_a_output',
    turn: turnNumber,
    raw_text: llmAResult.text,
    parsed_actions: greetingActions,
    session_id: llmASession.sessionId || '',
    cost_usd: llmAResult.costUsd,
    duration_ms: llmAResult.durationMs,
    form_state_snapshot: { ...formValues },
  });

  // Apply any set_fields from greeting
  for (const action of greetingActions) {
    if (action.type === 'set_fields' && Array.isArray(action.fields)) {
      const delta = applySetFields(action.fields as Array<{ field_id: string; value: unknown }>, formValues);
      if (Object.keys(delta).length > 0) {
        logger.log({
          type: 'state_update',
          turn: turnNumber,
          source: 'llm_a',
          delta,
          form_values: { ...formValues },
        });
      }
    }
  }

  turnNumber++;

  // ── Main loop ──

  // Pending button responses to inject (2-turn button flow)
  let pendingButtonResponse: string | null = null;

  // Repetition detection — if LLM U picks the same intent AND the screen hasn't changed,
  // it's truly stuck (e.g. saying "uploading" without actually uploading).
  const STUCK_THRESHOLD = 3;
  let lastIntent = '';
  let lastScreenHash = '';
  let intentRepeatCount = 0;

  /** Helper: call LLM A and log llm_a_input + llm_a_output + state_update */
  async function callAndLogLlmA(
    userMessage: string,
    source: 'llm_a' | 'button',
  ): Promise<void> {
    let fullPrompt: string;
    if (splitPrompt) {
      // Static instructions already on the constructor systemPrompt.
      // Only send dynamic state + user message per turn.
      const dynamicState = SystemPrompt.buildDynamic(formValues);
      fullPrompt = (dynamicState ? dynamicState + '\n\n---\n\n' : '') + 'User message: ' + userMessage;
    } else {
      // Default: full system prompt + user message each turn (backward compat)
      const sysPrompt = SystemPrompt.build(formMeta, '', formValues);
      fullPrompt = sysPrompt + '\n\n---\n\nUser message: ' + userMessage;
    }

    logger.log({
      type: 'llm_a_input',
      turn: turnNumber,
      system_prompt_length: fullPrompt.length,
      user_message: userMessage,
      resume_session_id: null,
    });

    llmAResult = await callLlmA(fullPrompt);
    llmACost += llmAResult.costUsd;

    const newActions = ActionParser.parseActions(llmAResult.text) as ParsedAction[];

    logger.log({
      type: 'llm_a_output',
      turn: turnNumber,
      raw_text: llmAResult.text,
      parsed_actions: newActions,
      session_id: llmASession.sessionId || '',
      cost_usd: llmAResult.costUsd,
      duration_ms: llmAResult.durationMs,
      form_state_snapshot: { ...formValues },
    });

    // Apply set_fields and log state_update
    for (const action of newActions) {
      if (action.type === 'set_fields' && Array.isArray(action.fields)) {
        const delta = applySetFields(
          action.fields as Array<{ field_id: string; value: unknown }>,
          formValues,
        );
        if (Object.keys(delta).length > 0) {
          logger.log({
            type: 'state_update',
            turn: turnNumber,
            source,
            delta,
            form_values: { ...formValues },
          });
        }
      }
    }

    const respText = ActionParser.extractText(llmAResult.text);
    console.log(`  LLM A: ${respText.slice(0, 120)}...`);
    console.log(`  Actions: ${newActions.length === 0 ? 'none' : newActions.map((a) => a.type).join(', ')}`);
    console.log(`  (${llmAResult.durationMs}ms, $${llmAResult.costUsd.toFixed(4)})\n`);
  }

  /** Helper: log session_end with summary */
  function logSessionEnd(reason: 'user_stop' | 'stuck_loop' | 'max_turns' | 'error'): void {
    logger.log({
      type: 'session_end',
      turn: turnNumber,
      reason,
      total_llm_a_cost: llmACost,
      total_llm_u_cost: llmUCost,
      fields_filled: Object.keys(formValues).length,
    });
  }

  while (turnNumber < MAX_TURNS) {
    // Render what the user sees
    const lastText = ActionParser.extractText(llmAResult.text);
    const lastActions = ActionParser.parseActions(llmAResult.text) as ParsedAction[];
    // Build state-aware nudge context
    const screenViewOpts: ScreenViewOptions = {
      turn: turnNumber,
      personaHasFiles: persona.files && Object.keys(persona.files).length > 0,
    };
    const screenView = renderScreenView(lastText, lastActions, formMetaForRenderer, formValues, screenViewOpts);

    // Detect available button from LLM A's last response
    const buttonAction = lastActions.find((a) => a.type === 'show_button');
    const availableButton = buttonAction ? (buttonAction.button as string) : null;

    // ── Pending button response injection (2-turn button flow) ──
    if (pendingButtonResponse) {
      console.log(`── Turn ${turnNumber} (system: button response) ──`);
      console.log(`  ${pendingButtonResponse}`);

      await callAndLogLlmA(pendingButtonResponse, 'button');
      pendingButtonResponse = null;
      turnNumber++;
      continue;
    }

    // ── LLM U decision ──
    console.log(`── Turn ${turnNumber} (LLM U deciding) ──`);

    // Log what LLM U will see
    logger.log({
      type: 'llm_u_input',
      turn: turnNumber,
      screen_view: screenView,
    });

    let llmUResponse: LlmUResponse;
    try {
      const llmUPrompt = `Here is what you see on your screen right now:\n\n${screenView}`;
      const llmUResult = await callLlmU(llmUPrompt);
      const llmUDurationMs = llmUResult.durationMs;
      const llmUCostTurn = llmUResult.costUsd;
      llmUCost += llmUCostTurn;

      // Parse JSON from streamed text (strip markdown fences if present)
      let jsonText = llmUResult.text.trim();
      const fenceMatch = jsonText.match(/```(?:json)?\s*([\s\S]*?)```/);
      if (fenceMatch) jsonText = fenceMatch[1].trim();

      try {
        llmUResponse = JSON.parse(jsonText) as LlmUResponse;
      } catch (parseErr) {
        console.error(`  LLM U returned invalid JSON (${(parseErr as Error).message})`);
        console.error(`  Raw response (first 300 chars): ${jsonText.slice(0, 300)}`);
        // Retry once with the same prompt — model may produce valid JSON on second attempt
        console.log('  Retrying LLM U (same prompt)...');
        const retryResult = await callLlmU(llmUPrompt);
        llmUCost += retryResult.costUsd;
        let retryJson = retryResult.text.trim();
        const retryFence = retryJson.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (retryFence) retryJson = retryFence[1].trim();
        try {
          llmUResponse = JSON.parse(retryJson) as LlmUResponse;
        } catch {
          console.error(`  LLM U retry also failed. Ending session.`);
          console.error(`  Retry response (first 300 chars): ${retryJson.slice(0, 300)}`);
          logSessionEnd('error');
          break;
        }
      }

      // Guard: LLM U may return valid JSON without candidates
      if (!llmUResponse.candidates || !Array.isArray(llmUResponse.candidates)) {
        console.error(`  LLM U returned JSON without candidates array. Keys: ${Object.keys(llmUResponse).join(', ')}`);
        console.error(`  Raw response (first 500 chars): ${jsonText.slice(0, 500)}`);
        logSessionEnd('error');
        break;
      }

      // Log all candidates to console
      const samplingMode: SamplingMode = config.sampling || 'greedy';
      const selectedIndex = sampleCandidate(llmUResponse.candidates, samplingMode);
      for (let ci = 0; ci < llmUResponse.candidates.length; ci++) {
        const c = llmUResponse.candidates[ci];
        const actionSummary = c.actions.map(a => a.action).join('+');
        const marker = ci === selectedIndex ? ' ★' : '';
        console.log(`  [${c.rank}] ${c.intent} (${actionSummary}): ${c.reasoning}${marker}`);
      }
      if (samplingMode !== 'greedy') {
        console.log(`  (${samplingMode} sampling → picked rank ${selectedIndex + 1})`);
      }

      const selected = llmUResponse.candidates[selectedIndex];
      if (!selected || selected.actions.length === 0) {
        console.error('  LLM U produced no actionable candidates. Ending.');
        logSessionEnd('error');
        break;
      }

      // Log LLM U output with all candidates
      logger.log({
        type: 'llm_u_output',
        turn: turnNumber,
        candidates: llmUResponse.candidates,
        selected_index: selectedIndex,
        selected_intent: selected.intent,
        sampling_mode: samplingMode,
        cost_usd: llmUCostTurn,
        duration_ms: llmUDurationMs,
      });

      // ── Process all actions from selected candidate via processActions() ──
      const plan = processActions(selected.actions, formValues, availableButton);

      // Log the execution plan
      logger.log({
        type: 'action_plan',
        turn: turnNumber,
        stop: plan.stop,
        field_edits: plan.fieldEdits,
        messages: plan.messages.map(m => ({
          text: m.text,
          ...(m.isSystem ? { isSystem: true } : {}),
          ...(m.fileKey ? { fileKey: m.fileKey } : {}),
        })),
        click_button: plan.clickButton,
      });

      console.log(`  (${llmUDurationMs}ms, $${llmUCostTurn.toFixed(4)})`);
      console.log(`  → Plan: stop=${plan.stop}, edits=${Object.keys(plan.fieldEdits).length}, msgs=${plan.messages.length}, button=${plan.clickButton}`);

      // ── Execute the plan ──

      // 1. Stop?
      if (plan.stop) {
        console.log('  → LLM U requested stop. Ending session.\n');
        logSessionEnd('user_stop');
        break;
      }

      // 2. Apply field edits silently
      if (Object.keys(plan.fieldEdits).length > 0) {
        Object.assign(formValues, plan.fieldEdits);
        logger.log({
          type: 'state_update',
          turn: turnNumber,
          source: 'llm_u',
          delta: { ...plan.fieldEdits },
          form_values: { ...formValues },
        });
        console.log(`  → field_edit: ${Object.keys(plan.fieldEdits).join(', ')}`);
      }

      // 3. Resolve file references in messages
      for (const msg of plan.messages) {
        if (msg.fileKey) {
          const personaFile = persona.files[msg.fileKey];
          if (personaFile) {
            msg.resolvedFile = {
              filename: personaFile.path.split('/').pop() || msg.fileKey,
              content: personaFile.content,
            };
            console.log(`  → Resolved file: ${msg.fileKey} → ${msg.resolvedFile.filename}`);
          } else {
            console.log(`  ⚠ Unknown file key: ${msg.fileKey}`);
          }
        }
      }

      // 4. Send combined message to LLM A (if any messages exist)
      if (plan.messages.length > 0) {
        const combinedMessage = buildLlmAMessage(plan.messages);
        const role = combinedMessage.startsWith('[system]') ? 'system' : 'user';
        console.log(`  → ${role} message to LLM A`);

        await callAndLogLlmA(combinedMessage, 'llm_a');
      }

      // 5. Handle button click (queues a system response for next iteration)
      if (plan.clickButton) {
        const buttonType = plan.clickButton;
        const clickMessage =
          buttonType === 'save_draft'
            ? '[system] User clicked: Save Draft'
            : '[system] User clicked: Submit';

        console.log(`  → button click: ${buttonType}`);
        await callAndLogLlmA(clickMessage, 'llm_a');

        // Queue the system response for next iteration
        if (buttonType === 'save_draft') {
          pendingButtonResponse = '[system] Draft saved successfully.';
        } else {
          const ref = `APP-2026-${String(Math.floor(Math.random() * 100000)).padStart(5, '0')}`;
          pendingButtonResponse = `[system] Submission saved. Reference: ${ref}`;
        }
      }

      // Repetition detection
      const screenHash = screenView.slice(0, 200);
      if (selected.intent === lastIntent && screenHash === lastScreenHash) {
        intentRepeatCount++;
        if (intentRepeatCount >= STUCK_THRESHOLD) {
          console.log(`  ⚠ LLM U stuck: "${selected.intent}" repeated ${intentRepeatCount} times with same screen. Forcing stop.\n`);
          logSessionEnd('stuck_loop');
          break;
        }
      } else {
        lastIntent = selected.intent;
        lastScreenHash = screenHash;
        intentRepeatCount = 1;
      }
    } catch (err) {
      const errMsg = (err as Error).message || String(err);
      console.error(`  LLM U error: ${errMsg}`);
      console.error(`  Stack: ${(err as Error).stack?.split('\n').slice(0, 3).join('\n  ')}`);
      logSessionEnd('error');
      break;
    }

    turnNumber++;
    console.log();
  }

  if (turnNumber >= MAX_TURNS) {
    console.log(`⚠ Hit max turn limit (${MAX_TURNS})\n`);
    logSessionEnd('max_turns');
  }

  // Clean up persistent processes
  llmASession.abort();
  llmUSession.abort();

  // Summary
  console.log(`${'─'.repeat(70)}`);
  console.log(`  Simulation DONE`);
  console.log(`  Turns: ${turnNumber}  |  LLM A cost: $${llmACost.toFixed(4)}  |  LLM U cost: $${llmUCost.toFixed(4)}`);
  console.log(`  Form fields filled: ${Object.keys(formValues).length}`);
  console.log(`${'─'.repeat(70)}\n`);

  // Write log
  const logDir = resolve(ROOT, 'sims');
  mkdirSync(logDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const logPath = resolve(
    logDir,
    `sim-${config.form}-${config.persona}-${config.profile}-${timestamp}.jsonl`,
  );
  writeFileSync(logPath, logger.toJsonl());
  console.log(`  Log: ${logPath}`);

  return { turns: turnNumber, llmACostUsd: llmACost, llmUCostUsd: llmUCost, logPath };
}

// ══════════════════════════════════════════════════════════════════════
// CLI
// ══════════════════════════════════════════════════════════════════════

function parseArgs(): SimConfig[] {
  const args = process.argv.slice(2);
  const configs: SimConfig[] = [];

  let form: string | undefined;
  let persona: string | undefined;
  let profile: string | undefined;
  let seed: number | undefined;
  let runs: number | undefined;
  let llmUModel: string | undefined;
  let sampling: SamplingMode | undefined;
  let effort: string | undefined;
  let splitPrompt = false;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--form':
        form = args[++i];
        break;
      case '--persona':
        persona = args[++i];
        break;
      case '--profile':
        profile = args[++i];
        break;
      case '--seed':
        seed = parseInt(args[++i], 10);
        break;
      case '--runs':
        runs = parseInt(args[++i], 10);
        break;
      case '--llm-u-model':
        llmUModel = args[++i];
        break;
      case '--sampling':
        sampling = args[++i] as SamplingMode;
        break;
      case '--effort':
        effort = args[++i];
        break;
      case '--split-prompt':
        splitPrompt = true;
        break;
    }
  }

  // If all specified, single run
  if (form && persona && profile) {
    configs.push({ form, persona, profile, seed, llmUModel, sampling, effort, splitPrompt });
    return configs;
  }

  // If --runs specified, generate all combinations
  const formKeys = form ? [form] : Object.keys(FORMS);
  const personaKeys = persona ? [persona] : Object.keys(PERSONAS);
  const profileKeys = profile ? [profile] : PROFILES;
  const numRuns = runs || 1;

  for (let r = 0; r < numRuns; r++) {
    for (const f of formKeys) {
      for (const p of personaKeys) {
        for (const pr of profileKeys) {
          configs.push({
            form: f,
            persona: p,
            profile: pr,
            seed: seed !== undefined ? seed + r : undefined,
            llmUModel,
            sampling,
            effort,
            splitPrompt,
          });
        }
      }
    }
  }

  return configs;
}

async function main(): Promise<void> {
  const configs = parseArgs();

  if (configs.length === 0) {
    console.error('Usage:');
    console.error('  npm run e2e:sim -- --form northfield --persona jane --profile thorough');
    console.error('  npm run e2e:sim -- --runs 3');
    console.error('  npm run e2e:sim -- --form northfield --persona jane --profile impatient --sampling weighted --effort low');
    console.error(`\nForms: ${Object.keys(FORMS).join(', ')}`);
    console.error(`Personas: ${Object.keys(PERSONAS).join(', ')}`);
    console.error(`Profiles: ${PROFILES.join(', ')}`);
    console.error(`Sampling: greedy, weighted, uniform (default: greedy)`);
    console.error(`Effort: low, medium, high (default: model default)`);
    process.exit(1);
  }

  console.log(`\n╔${'═'.repeat(68)}╗`);
  console.log(`║  Simulator — ${configs.length} session(s)`.padEnd(69) + '║');
  console.log(`║  Max turns per session: ${MAX_TURNS}`.padEnd(69) + '║');
  console.log(`╚${'═'.repeat(68)}╝\n`);

  const results: Array<{
    config: SimConfig;
    turns: number;
    llmACostUsd: number;
    llmUCostUsd: number;
    logPath: string;
  }> = [];

  for (const config of configs) {
    const result = await runSimulation(config);
    results.push({ config, ...result });
  }

  // Grand summary
  const totalLlmACost = results.reduce((sum, r) => sum + r.llmACostUsd, 0);
  const totalLlmUCost = results.reduce((sum, r) => sum + r.llmUCostUsd, 0);
  const totalTurns = results.reduce((sum, r) => sum + r.turns, 0);

  console.log(`\n╔${'═'.repeat(68)}╗`);
  console.log(`║  ALL DONE`.padEnd(69) + '║');
  console.log(
    `║  Sessions: ${results.length}  |  Turns: ${totalTurns}  |  LLM A: $${totalLlmACost.toFixed(4)}  |  LLM U: $${totalLlmUCost.toFixed(4)}`.padEnd(69) + '║',
  );
  console.log(`╚${'═'.repeat(68)}╝`);

  for (const r of results) {
    console.log(`  ${r.config.form}×${r.config.persona}×${r.config.profile}: ${r.logPath}`);
  }
  console.log();
}

main().catch((err) => {
  console.error('\nSimulator failed:', err);
  process.exit(1);
});
