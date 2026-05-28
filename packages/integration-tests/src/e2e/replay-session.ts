/**
 * Session Log Replay Tool
 *
 * Reads a session log (.jsonl), extracts user inputs, replays them against
 * the live API with reconstructed system prompts, and logs original vs replay
 * side-by-side for manual comparison.
 *
 * Usage:
 *   npm run replay -- <session-log.jsonl> [--form <form-json>]
 *
 * The form JSON is auto-detected from the session content when possible,
 * or can be specified manually.
 *
 * Output:
 *   Console: side-by-side comparison per turn
 *   JSON:    e2e-logs/replay-<session-id>-<timestamp>.json
 */

import { JSDOM } from 'jsdom';
import { readFileSync, writeFileSync, appendFileSync, mkdirSync } from 'fs';
import { resolve } from 'path';
import { startServer, type ManagedServer } from '../helpers/server-manager.js';

// ── Paths ──

const ROOT = resolve(import.meta.dirname, '..', '..', '..', '..');
const WEB_APP_PORT = 3004;
const WEB_APP_URL = `http://localhost:${WEB_APP_PORT}`;

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

interface SessionLogEntry {
  type: 'user_message' | 'model_input' | 'model_output' | 'form_state_update';
  session_id: string;
  ts: string;
  // user_message
  message?: string;
  role?: 'user' | 'system';
  // model_input
  user_message?: string;
  full_prompt_length?: number;
  // model_output
  raw_text?: string;
  parsed_actions?: Array<{ type: string; [key: string]: unknown }>;
  duration_ms?: number;
  cost_usd?: number;
  // form_state_update
  field_updates?: Record<string, unknown>;
  source?: string;
}

interface TurnPair {
  turn: number;
  userMessage: string;
  role: 'user' | 'system';
  original: {
    text: string;
    actions: Array<{ type: string; [key: string]: unknown }>;
    durationMs: number;
    costUsd: number;
  };
  replay: {
    text: string;
    actions: Array<{ type: string; [key: string]: unknown }>;
    durationMs: number;
    costUsd: number;
  };
  formStateBeforeTurn: Record<string, unknown>;
}

// ── Parse session log ──

function parseSessionLog(filePath: string): SessionLogEntry[] {
  const content = readFileSync(filePath, 'utf-8').trim();
  if (!content) return [];
  return content.split('\n').map((line) => JSON.parse(line));
}

/**
 * Extract turn pairs from a session log.
 * Each turn = one model_input + one model_output.
 */
function extractTurns(entries: SessionLogEntry[]): Array<{
  userMessage: string;
  role: 'user' | 'system';
  originalOutput: SessionLogEntry;
  formStateUpdates: SessionLogEntry[];
}> {
  const turns: Array<{
    userMessage: string;
    role: 'user' | 'system';
    originalOutput: SessionLogEntry;
    formStateUpdates: SessionLogEntry[];
  }> = [];

  let i = 0;
  while (i < entries.length) {
    const entry = entries[i];

    if (entry.type === 'model_input') {
      const userMessage = entry.user_message || '';
      const role = userMessage.startsWith('[system]') ? 'system' as const : 'user' as const;

      // Find the corresponding model_output
      let output: SessionLogEntry | null = null;
      const stateUpdates: SessionLogEntry[] = [];
      let j = i + 1;
      while (j < entries.length) {
        if (entries[j].type === 'model_output') {
          output = entries[j];
          // Collect form_state_updates after this output
          let k = j + 1;
          while (k < entries.length && entries[k].type === 'form_state_update') {
            stateUpdates.push(entries[k]);
            k++;
          }
          break;
        }
        j++;
      }

      if (output) {
        turns.push({
          userMessage,
          role,
          originalOutput: output,
          formStateUpdates: stateUpdates,
        });
        i = j + 1 + stateUpdates.length;
        continue;
      }
    }

    i++;
  }

  return turns;
}

// ── Auto-detect form from session content ──

function detectFormFile(entries: SessionLogEntry[]): string | null {
  const firstMessage = entries.find((e) => e.type === 'user_message')?.message?.toLowerCase() || '';
  if (firstMessage.includes('northfield')) return 'masters-northfield.json';
  if (firstMessage.includes('westbrook')) return 'masters-westbrook.json';
  if (firstMessage.includes('patient') || firstMessage.includes('checkup')) return 'patient-riverside.json';

  // Also check all messages
  for (const e of entries) {
    const text = (e.message || e.user_message || '').toLowerCase();
    if (text.includes('northfield')) return 'masters-northfield.json';
    if (text.includes('westbrook')) return 'masters-westbrook.json';
    if (text.includes('patient') || text.includes('checkup')) return 'patient-riverside.json';
  }

  return null;
}

// ── SSE Client (same as run-scenario.ts) ──

async function doGenerate(fullPrompt: string, sessionId: string | null): Promise<{
  text: string;
  sessionId: string;
  durationMs: number;
  costUsd: number;
}> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);

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
              process.stdout.write('.');
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

// ── Form state helpers (same as run-scenario.ts) ──

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

function applyFieldUpdates(
  updates: Record<string, unknown>,
  formValues: Record<string, unknown>,
): void {
  for (const [key, value] of Object.entries(updates)) {
    formValues[key] = value;
  }
}

// ── Session log writer (matches dev interface format) ──

function appendSessionEntry(logPath: string, entry: Record<string, unknown>): void {
  appendFileSync(logPath, JSON.stringify(entry) + '\n');
}

// ── Comparison helpers ──

function summarizeActions(actions: Array<{ type: string; [key: string]: unknown }>): string {
  if (actions.length === 0) return '(none)';
  return actions.map((a) => {
    if (a.type === 'set_fields' && Array.isArray(a.fields)) {
      const fieldIds = (a.fields as Array<{ field_id: string }>).map((f) => f.field_id);
      return `set_fields(${fieldIds.join(', ')})`;
    }
    if (a.type === 'ask_choice') return `ask_choice("${a.question || ''}")`;
    if (a.type === 'show_fields') return `show_fields`;
    if (a.type === 'show_preview') return `show_preview`;
    if (a.type === 'show_button') return `show_button(${a.button})`;
    return a.type;
  }).join(' + ');
}

// ══════════════════════════════════════════════════════════════════════
// MAIN
// ══════════════════════════════════════════════════════════════════════

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  // Parse args
  let logFile: string | null = null;
  let formFile: string | null = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--form' && args[i + 1]) {
      formFile = args[++i];
    } else if (!logFile) {
      logFile = args[i];
    }
  }

  if (!logFile) {
    console.error('Usage: npm run replay -- <session-log.jsonl> [--form <form-json>]');
    process.exit(1);
  }

  // Parse session log
  const entries = parseSessionLog(logFile);
  if (entries.length === 0) {
    console.error('Empty session log');
    process.exit(1);
  }

  const sessionId = entries[0].session_id;
  console.log(`\nSession: ${sessionId}`);
  console.log(`Entries: ${entries.length}`);

  // Detect or use form
  if (!formFile) {
    formFile = detectFormFile(entries);
    if (!formFile) {
      console.error('Could not auto-detect form. Use --form <form-json>');
      process.exit(1);
    }
    console.log(`Auto-detected form: ${formFile}`);
  }

  const formMeta = JSON.parse(
    readFileSync(
      resolve(ROOT, 'packages/web-app/public/forms', formFile),
      'utf-8',
    ),
  );

  // Extract turns
  const turns = extractTurns(entries);
  console.log(`Turns to replay: ${turns.length}`);

  console.log(`\n╔${'═'.repeat(68)}╗`);
  console.log(`║  Session Replay: ${sessionId}`.padEnd(69) + '║');
  console.log(`║  Form: ${formMeta.name}`.padEnd(69) + '║');
  console.log(`║  Turns: ${turns.length}`.padEnd(69) + '║');
  console.log(`╚${'═'.repeat(68)}╝\n`);

  // Start server
  let server: ManagedServer | null = null;
  try {
    console.log('Starting web-app server...');
    server = await startServer('web-app', WEB_APP_PORT);
    console.log(`  ✓ web-app on port ${WEB_APP_PORT}\n`);
  } catch (err) {
    console.error('Failed to start web-app server:', (err as Error).message);
    process.exit(1);
  }

  // Prepare session JSONL output
  const logDir = resolve(ROOT, 'packages', 'integration-tests', 'e2e-logs');
  mkdirSync(logDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const replayId = `replay-${sessionId}`;
  const sessionLogPath = resolve(logDir, `${replayId}-${timestamp}.jsonl`);
  const comparisonLogPath = resolve(logDir, `${replayId}-${timestamp}.json`);

  // Write session_start
  appendSessionEntry(sessionLogPath, {
    form_id: formFile!.replace('.json', ''),
    form_name: formMeta.name,
    session_id: replayId,
    type: 'session_start',
    ts: new Date().toISOString(),
  });

  const results: TurnPair[] = [];
  const formValues: Record<string, unknown> = {};
  let replaySessionId: string | null = null;
  let totalReplayCost = 0;
  let totalOriginalCost = 0;

  try {
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
      const turnNum = i + 1;

      console.log(`${'─'.repeat(70)}`);
      console.log(`  Turn ${turnNum} (${turn.role})`);
      console.log(`  IN: ${turn.userMessage.slice(0, 120)}${turn.userMessage.length > 120 ? '...' : ''}`);

      // Build system prompt with current form state
      const systemPrompt = SystemPrompt.build(formMeta, '', formValues);
      const fullPrompt = systemPrompt + '\n\n---\n\nUser message: ' + turn.userMessage;

      // Replay: call the API
      process.stdout.write('  Replay: ');
      let replayResult;
      try {
        replayResult = await doGenerate(fullPrompt, replaySessionId);
      } catch (err) {
        console.error(`\n  REPLAY ERROR: ${(err as Error).message}`);
        continue;
      }
      console.log(); // end progress dots

      replaySessionId = replayResult.sessionId;
      totalReplayCost += replayResult.costUsd;
      totalOriginalCost += turn.originalOutput.cost_usd || 0;

      const replayText = ActionParser.extractText(replayResult.text);
      const replayActions = ActionParser.parseActions(replayResult.text);

      // Original
      const originalText = ActionParser.extractText(turn.originalOutput.raw_text || '');
      const originalActions = turn.originalOutput.parsed_actions || [];

      const now = new Date().toISOString();

      // Emit session-format JSONL entries for replay
      appendSessionEntry(sessionLogPath, {
        message: turn.userMessage,
        role: turn.role,
        session_id: replayId,
        type: 'user_message',
        ts: now,
      });

      appendSessionEntry(sessionLogPath, {
        full_prompt_length: fullPrompt.length,
        prompt_hash: null,
        user_message: turn.userMessage,
        form_state_snapshot: { ...formValues },
        session_id: replayId,
        type: 'model_input',
        ts: now,
      });

      appendSessionEntry(sessionLogPath, {
        raw_text: replayResult.text,
        parsed_actions: replayActions,
        duration_ms: replayResult.durationMs,
        cost_usd: replayResult.costUsd,
        claude_session_id: replayResult.sessionId,
        session_id: replayId,
        type: 'model_output',
        ts: now,
      });

      // Apply original form state updates (to keep state in sync with original session)
      for (const su of turn.formStateUpdates) {
        if (su.field_updates) {
          applyFieldUpdates(su.field_updates, formValues);
        }
      }

      // Also apply set_fields from original actions (for state updates not captured in form_state_update)
      for (const action of originalActions) {
        if (action.type === 'set_fields' && Array.isArray(action.fields)) {
          const delta = applySetFields(
            action.fields as Array<{ field_id: string; value: unknown }>,
            formValues,
          );
          // Emit form_state_update for each set_fields
          appendSessionEntry(sessionLogPath, {
            field_updates: delta,
            source: 'model',
            session_id: replayId,
            type: 'form_state_update',
            ts: now,
          });
        }
      }

      // Log comparison
      console.log();
      console.log(`  ORIGINAL (${turn.originalOutput.duration_ms}ms, $${(turn.originalOutput.cost_usd || 0).toFixed(4)}):`);
      console.log(`    Text: ${originalText.slice(0, 150)}${originalText.length > 150 ? '...' : ''}`);
      console.log(`    Actions: ${summarizeActions(originalActions)}`);
      console.log();
      console.log(`  REPLAY (${replayResult.durationMs}ms, $${replayResult.costUsd.toFixed(4)}):`);
      console.log(`    Text: ${replayText.slice(0, 150)}${replayText.length > 150 ? '...' : ''}`);
      console.log(`    Actions: ${summarizeActions(replayActions)}`);

      // Quick structural match check
      const origTypes = originalActions.map((a) => a.type).sort().join(',');
      const replayTypes = replayActions.map((a) => a.type).sort().join(',');
      const match = origTypes === replayTypes ? '✓ MATCH' : '✗ DIFFER';
      console.log(`\n  Action types: ${match} (original: [${origTypes}] | replay: [${replayTypes}])`);

      results.push({
        turn: turnNum,
        userMessage: turn.userMessage,
        role: turn.role,
        original: {
          text: originalText,
          actions: originalActions,
          durationMs: turn.originalOutput.duration_ms || 0,
          costUsd: turn.originalOutput.cost_usd || 0,
        },
        replay: {
          text: replayText,
          actions: replayActions,
          durationMs: replayResult.durationMs,
          costUsd: replayResult.costUsd,
        },
        formStateBeforeTurn: { ...formValues },
      });

      console.log();
    }

    // Summary
    const actionMatches = results.filter((r) => {
      const origTypes = r.original.actions.map((a) => a.type).sort().join(',');
      const replayTypes = r.replay.actions.map((a) => a.type).sort().join(',');
      return origTypes === replayTypes;
    }).length;

    console.log(`\n╔${'═'.repeat(68)}╗`);
    console.log(`║  REPLAY COMPLETE`.padEnd(69) + '║');
    console.log(`║  Turns: ${results.length}  |  Action type match: ${actionMatches}/${results.length}`.padEnd(69) + '║');
    console.log(`║  Original cost: $${totalOriginalCost.toFixed(4)}  |  Replay cost: $${totalReplayCost.toFixed(4)}`.padEnd(69) + '║');
    console.log(`╚${'═'.repeat(68)}╝`);

    // Write comparison log
    writeFileSync(comparisonLogPath, JSON.stringify({
      sessionId,
      form: formMeta.name,
      timestamp: new Date().toISOString(),
      totalTurns: results.length,
      actionTypeMatchRate: `${actionMatches}/${results.length}`,
      totalOriginalCost: totalOriginalCost,
      totalReplayCost: totalReplayCost,
      turns: results,
    }, null, 2));

    console.log(`\n  Comparison: ${comparisonLogPath}`);
    console.log(`  Session log: ${sessionLogPath}\n`);
  } finally {
    if (server) {
      server.kill();
      console.log('  Server stopped.\n');
    }
  }
}

main().catch((err) => {
  console.error('\nReplay failed:', err);
  process.exit(1);
});
