/**
 * Web App Server — Dumb CLI Proxy
 *
 * This server has ONE job: proxy prompts to Claude Code CLI and stream
 * back raw text via SSE. It knows NOTHING about forms, actions, sessions,
 * vault, or the application domain. All that logic lives in the browser.
 *
 * Endpoint:
 *   POST /api/generate { prompt: string, resume?: string }
 *   → SSE stream:
 *       event: text   data: { text: "chunk" }
 *       event: done   data: { session_id: "...", duration_ms: N, cost_usd: N }
 *       event: error  data: { message: "..." }
 *
 * Static files are served from public/ (the browser app).
 */

import express from 'express';
import cors from 'cors';
import path from 'path';
import { readFileSync, readdirSync } from 'fs';
import { ClaudeAgent } from '@form-filling-assistant/claude-agent';

// ── Claude Agent instance ──
// Project root where .mcp.json lives (if any)
const PROJECT_ROOT = path.resolve(
  import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname),
  '..', '..', '..',
);

const agent = new ClaudeAgent({
  cwd: PROJECT_ROOT,
  model: process.env.LLM_MODEL ?? 'haiku',
  fallbackModel: process.env.LLM_FALLBACK ?? 'sonnet',
  dangerouslySkipPermissions: true,
});

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3004;

// ── CLI flags ──
const formFlagIdx = process.argv.indexOf('--form');
const preselectedForm = formFlagIdx !== -1 ? process.argv[formFlagIdx + 1] ?? null : null;

// ── Middleware ──

app.use(cors());
app.use(express.json({ limit: '1mb' }));

// ── Local SFT harness (Experiment 10, doc-12) ──
// When the browser uses ?backend=local, requests go to /api/generate-local
// which proxies to the Python harness. Default backend stays Claude.
const HARNESS_URL = process.env.HARNESS_URL ?? 'http://localhost:8200';

// Serve static files from public/
const publicDir = path.resolve(
  import.meta.dirname ?? path.dirname(new URL(import.meta.url).pathname),
  '..', 'public',
);
app.use(express.static(publicDir));

// ── Health check (for test infrastructure) ──

app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// ── App config (consumed by browser on init) ──

app.get('/api/config', (_req, res) => {
  res.json({ preselectedForm });
});

// ── Single endpoint: dumb proxy ──

/**
 * POST /api/generate — Forward a prompt to Claude CLI and stream back text.
 *
 * Body: { prompt: string, resume?: string, systemPrompt?: string, model?: string, effort?: string }
 * Response: SSE stream
 *
 * When systemPrompt/model/effort are provided, creates a one-off agent (used by
 * LLM U streaming mode). Otherwise uses the default app agent (LLM A).
 */
app.post('/api/generate', (req, res) => {
  const { prompt, resume, systemPrompt, model, effort } = req.body as {
    prompt?: string;
    resume?: string;
    systemPrompt?: string;
    model?: string;
    effort?: string;
  };

  if (!prompt) {
    res.status(400).json({ error: 'prompt is required' });
    return;
  }

  // Set up SSE headers
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  function sendSSE(event: string, data: unknown): void {
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  }

  // Use custom agent when systemPrompt/model/effort are provided (LLM U streaming),
  // otherwise use the default app agent (LLM A).
  const runAgent = (systemPrompt || model || effort)
    ? new ClaudeAgent({
        model: model || 'haiku',
        systemPrompt: systemPrompt || undefined,
        dangerouslySkipPermissions: true,
        effort: (effort as 'low' | 'medium' | 'high') || undefined,
      })
    : agent;

  const run = runAgent.run(prompt, {
    resume: resume || undefined,
  });

  let finished = false;

  // Process events
  (async () => {
    try {
      for await (const event of run) {
        if (finished) break;

        switch (event.type) {
          case 'text': {
            sendSSE('text', { text: event.text });
            break;
          }

          case 'result': {
            finished = true;
            sendSSE('done', {
              session_id: event.sessionId,
              duration_ms: event.durationMs,
              cost_usd: event.costUsd,
            });
            res.end();
            break;
          }

          case 'error': {
            finished = true;
            sendSSE('error', { message: event.message });
            res.end();
            break;
          }

          // tool_use, tool_result, init, etc. — not forwarded
          default:
            break;
        }
      }

      if (!finished) {
        finished = true;
        res.end();
      }
    } catch (err) {
      if (!finished) {
        finished = true;
        sendSSE('error', { message: `Stream error: ${(err as Error).message}` });
        res.end();
      }
    }
  })();

  res.on('close', () => {
    if (!finished) {
      console.log('[proxy] Client disconnected, aborting Claude CLI');
      finished = true;
      run.abort();
    }
  });
});

// ══════════════════════════════════════════════════════════════════════
// Simulation Demo Endpoints
// ══════════════════════════════════════════════════════════════════════

// Lazy-load simulator modules (only when sim endpoints are hit)
let simModulesLoaded = false;
let buildLlmUSystemPrompt: any;
let PERSONAS: any;
const PROFILES = ['thorough', 'impatient', 'confused', 'corrector', 'returning'];
const SIM_FORMS: Record<string, string> = {
  northfield: 'masters-northfield.json',
  westbrook: 'masters-westbrook.json',
  patient: 'patient-riverside.json',
};

async function loadSimModules() {
  if (simModulesLoaded) return;
  // Cross-package imports from integration-tests simulator
  const promptMod = await import(
    path.resolve(PROJECT_ROOT, 'packages/integration-tests/src/e2e/simulator/llm-u-prompt.js')
  );
  const personaMod = await import(
    path.resolve(PROJECT_ROOT, 'packages/integration-tests/src/e2e/simulator/personas.js')
  );
  buildLlmUSystemPrompt = promptMod.buildLlmUSystemPrompt;
  PERSONAS = personaMod.PERSONAS;
  simModulesLoaded = true;
}

/** JSON schema for LLM U structured output */
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

/**
 * POST /api/generate-local — Proxy to the local SFT harness (Experiment 10).
 *
 * Body: structured per-turn input
 *   { session_id, user_message, form_state, form_schema, conversation_history }
 *
 * Response: SSE stream (same shape as /api/generate). The harness composes
 * the model's 5-module pipeline output into the legacy text + ---actions---
 * format the browser already parses.
 */
app.post('/api/generate-local', async (req, res) => {
  const upstream = await fetch(`${HARNESS_URL}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req.body),
  });

  if (!upstream.ok || !upstream.body) {
    res.status(upstream.status).json({ error: `harness HTTP ${upstream.status}` });
    return;
  }

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const reader = upstream.body.getReader();
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      res.write(value);
    }
  } catch (err) {
    res.write(`event: error\ndata: ${JSON.stringify({ message: String(err) })}\n\n`);
  } finally {
    res.end();
  }
});

/**
 * GET /api/sim/config — Available personas, profiles, forms for the sim UI
 */
app.get('/api/sim/config', async (_req, res) => {
  try {
    await loadSimModules();
    const personaSummaries: Record<string, { name: string; files: string[] }> = {};
    for (const [key, p] of Object.entries(PERSONAS) as [string, any][]) {
      personaSummaries[key] = {
        name: p.name,
        files: Object.keys(p.files),
      };
    }
    res.json({
      personas: personaSummaries,
      profiles: PROFILES,
      forms: SIM_FORMS,
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

/**
 * POST /api/sim/llm-u-prompt — Build the LLM U system prompt
 * Body: { persona: string, profile: string }
 */
app.post('/api/sim/llm-u-prompt', async (req, res) => {
  try {
    await loadSimModules();
    const { persona: personaName, profile: profileName } = req.body;
    const persona = PERSONAS[personaName];
    if (!persona) {
      res.status(400).json({ error: `Unknown persona: ${personaName}` });
      return;
    }
    const systemPrompt = buildLlmUSystemPrompt({ persona, profileName });
    res.json({ systemPrompt });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

/**
 * POST /api/generate-json — Generate structured JSON output from a prompt.
 * Body: { prompt: string, systemPrompt?: string, model?: string, resume?: string, jsonSchema?: object }
 *
 * Counterpart to /api/generate (streaming text). This returns a single JSON response
 * validated against the provided schema.
 *
 * If no jsonSchema is provided, defaults to CANDIDATES_SCHEMA (sim LLM U format).
 * Pass `resume` with a session ID from a previous response to continue the same session.
 */
app.post('/api/generate-json', async (req, res) => {
  const { prompt, systemPrompt, model, resume, jsonSchema, effort } = req.body as {
    prompt?: string;
    systemPrompt?: string;
    model?: string;
    resume?: string;
    jsonSchema?: Record<string, unknown>;
    effort?: string;
  };

  if (!prompt) {
    res.status(400).json({ error: 'prompt is required' });
    return;
  }

  try {
    const agent = new ClaudeAgent({
      model: model || 'haiku',
      systemPrompt: systemPrompt || undefined,
      dangerouslySkipPermissions: true,
      resume: resume || undefined,
      effort: (effort as 'low' | 'medium' | 'high') || undefined,
    });

    const schema = jsonSchema || CANDIDATES_SCHEMA;
    const response = await agent.askJsonFull(prompt, schema);

    res.json({
      data: response.data,
      sessionId: response.sessionId,
      costUsd: response.costUsd,
      durationMs: response.durationMs,
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

/**
 * POST /api/sim/resolve-file — Resolve a file key from persona data
 * Body: { persona: string, fileKey: string }
 */
app.post('/api/sim/resolve-file', async (req, res) => {
  try {
    await loadSimModules();
    const { persona: personaName, fileKey } = req.body;
    const persona = PERSONAS[personaName];
    if (!persona) {
      res.status(400).json({ error: `Unknown persona: ${personaName}` });
      return;
    }
    const file = persona.files[fileKey];
    if (!file) {
      res.status(404).json({ error: `File not found: ${fileKey}` });
      return;
    }
    res.json({
      filename: file.path.split('/').pop() || fileKey,
      content: file.content,
    });
  } catch (err) {
    res.status(500).json({ error: (err as Error).message });
  }
});

// ── Start server ──

app.listen(PORT, () => {
  console.log(`\n  Form-Filling Assistant Web App`);
  console.log(`   http://localhost:${PORT}`);
  console.log(`   http://localhost:${PORT}/dev.html  — Session Inspector`);
  console.log(`   http://localhost:${PORT}/sim.html   — Simulation Demo`);
  if (preselectedForm) {
    console.log(`   --form ${preselectedForm}`);
  }
  console.log(`   POST /api/generate  — Claude CLI proxy (SSE stream)`);
  console.log(`   Static files: public/\n`);
});
