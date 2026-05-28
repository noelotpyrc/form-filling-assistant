/**
 * ClaudeAgent — the main entry point for the claude-agent wrapper.
 *
 * Provides three API levels:
 *   - agent.ask(prompt)      — one-shot, returns string result
 *   - agent.askJson(prompt)  — one-shot, returns typed structured output
 *   - agent.run(prompt)      — full streaming with for-await
 *   - agent.runInteractive() — multi-turn bidirectional streaming
 */

import type { AgentOptions, AgentEvent, ContentBlock } from './types.js';
import { runStreaming, runJson, runInteractiveProcess } from './process.js';

/**
 * A streaming session from agent.run(). Implements AsyncIterable<AgentEvent>.
 */
export interface AgentSession extends AsyncIterable<AgentEvent> {
  /** The Claude CLI session ID. Available after the first InitEvent is received. */
  readonly sessionId: string | undefined;
  /** Abort the CLI process (sends SIGTERM). */
  abort(): void;
}

/**
 * An interactive session from agent.runInteractive().
 * Supports sending follow-up messages and control commands via stdin.
 */
export interface InteractiveSession extends AgentSession {
  /** Send a follow-up user message. Can be plain text or content blocks (with images). */
  send(message: string | ContentBlock[]): void;
  /** Send a control command via stdin. */
  sendControl(control: Record<string, unknown>): void;
}

/**
 * Main agent class. Create an instance with default options,
 * then call run/ask/askJson with per-call overrides.
 *
 * @example
 * ```typescript
 * const agent = new ClaudeAgent({
 *   cwd: '/path/to/project',
 *   appendSystemPrompt: 'You are a helpful assistant.',
 *   dangerouslySkipPermissions: true,
 * });
 *
 * // One-shot
 * const answer = await agent.ask('What does this project do?');
 *
 * // Streaming
 * for await (const event of agent.run('Explain the auth module')) {
 *   if (event.type === 'text') process.stdout.write(event.text);
 * }
 *
 * // Structured output
 * const data = await agent.askJson<{ functions: string[] }>(
 *   'List function names in auth.py',
 *   { type: 'object', properties: { functions: { type: 'array', items: { type: 'string' } } }, required: ['functions'] }
 * );
 * ```
 */
export class ClaudeAgent {
  private defaults: AgentOptions;

  constructor(defaults?: AgentOptions) {
    this.defaults = defaults ?? {};
  }

  /**
   * Full streaming mode: sends a single prompt and streams all events.
   *
   * Use `for await (const event of session)` to consume events.
   * Call `session.abort()` to cancel.
   * Read `session.sessionId` after the first event for the CLI session ID.
   *
   * @param prompt - The user message to send
   * @param opts - Per-call option overrides (merged with constructor defaults)
   * @returns An AgentSession (AsyncIterable<AgentEvent> + abort + sessionId)
   */
  run(prompt: string, opts?: AgentOptions): AgentSession {
    const merged = this.merge(opts);
    const abortHandle: { fn?: () => void } = {};

    let capturedSessionId: string | undefined;
    const gen = runStreaming(prompt, merged, abortHandle);

    // Wrap the generator to capture sessionId from InitEvent
    const wrappedGen = async function* (): AsyncGenerator<AgentEvent> {
      for await (const event of gen) {
        if (event.type === 'init') {
          capturedSessionId = event.sessionId;
        }
        yield event;
      }
    };

    const iterable = wrappedGen();

    return {
      get sessionId() {
        return capturedSessionId;
      },
      abort() {
        abortHandle.fn?.();
      },
      [Symbol.asyncIterator]() {
        return iterable[Symbol.asyncIterator]();
      },
    };
  }

  /**
   * Interactive multi-turn mode: spawns a long-lived CLI process with
   * bidirectional streaming via stdin/stdout.
   *
   * Send follow-up messages with `session.send()`.
   * Read events with `for await (const event of session)`.
   *
   * @param opts - Per-call option overrides
   * @returns An InteractiveSession
   */
  runInteractive(opts?: AgentOptions): InteractiveSession {
    const merged = this.merge(opts);
    const handle = runInteractiveProcess(merged);

    let capturedSessionId: string | undefined;

    const wrappedEvents = async function* (): AsyncGenerator<AgentEvent> {
      for await (const event of handle.events) {
        if (event.type === 'init') {
          capturedSessionId = event.sessionId;
        }
        yield event;
      }
    };

    const iterable = wrappedEvents();

    return {
      get sessionId() {
        return capturedSessionId;
      },
      abort() {
        handle.abort();
      },
      send(message: string | ContentBlock[]) {
        handle.send(message);
      },
      sendControl(control: Record<string, unknown>) {
        handle.sendControl(control);
      },
      [Symbol.asyncIterator]() {
        return iterable[Symbol.asyncIterator]();
      },
    };
  }

  /**
   * One-shot mode: sends a prompt and returns the final result text.
   *
   * Uses `--output-format json` for a single JSON response (not streaming).
   * Simpler but no intermediate events.
   *
   * @param prompt - The user message
   * @param opts - Per-call option overrides
   * @returns The result text
   * @throws Error if the CLI fails
   */
  async ask(prompt: string, opts?: AgentOptions): Promise<string> {
    const merged = this.merge(opts);
    const result = await runJson(prompt, merged);
    if (result.isError) {
      throw new Error(`Claude CLI returned an error: ${result.result}`);
    }
    return result.result;
  }

  /**
   * Structured output mode: sends a prompt with a JSON schema
   * and returns the validated, parsed result.
   *
   * Uses `--output-format json` + `--json-schema`.
   *
   * @param prompt - The user message
   * @param schema - JSON Schema object for the desired output structure
   * @param opts - Per-call option overrides
   * @returns The parsed structured output
   * @throws Error if the CLI fails or output doesn't match schema
   */
  async askJson<T = unknown>(
    prompt: string,
    schema: Record<string, unknown>,
    opts?: AgentOptions,
  ): Promise<T> {
    const full = await this.askJsonFull<T>(prompt, schema, opts);
    return full.data;
  }

  /**
   * Like askJson but also returns session metadata (sessionId, cost, duration).
   * Useful when you need to resume the session on subsequent calls.
   *
   * @param prompt - The user message
   * @param schema - JSON Schema object for the desired output structure
   * @param opts - Per-call option overrides
   * @returns Object with { data, sessionId, costUsd, durationMs }
   */
  async askJsonFull<T = unknown>(
    prompt: string,
    schema: Record<string, unknown>,
    opts?: AgentOptions,
  ): Promise<{ data: T; sessionId: string; costUsd: number; durationMs: number }> {
    const merged = this.merge({ ...opts, jsonSchema: schema });
    const result = await runJson(prompt, merged);

    if (result.isError) {
      throw new Error(`Claude CLI returned an error: ${result.result}`);
    }

    let data: T;
    if (result.structuredOutput !== undefined) {
      data = result.structuredOutput as T;
    } else {
      // Fallback: the model may output JSON as plain text (especially on resumed
      // sessions where it skips the StructuredOutput tool). Try parsing directly,
      // then try stripping markdown code fences.
      data = parseJsonText<T>(result.result);
    }

    return {
      data,
      sessionId: result.sessionId,
      costUsd: result.costUsd,
      durationMs: result.durationMs,
    };
  }

  // ── Internal ──

  /**
   * Merge per-call options with constructor defaults.
   * Per-call values override defaults. Arrays are replaced, not merged.
   */
  private merge(opts?: AgentOptions): AgentOptions {
    if (!opts) return { ...this.defaults };
    return { ...this.defaults, ...opts };
  }
}

/**
 * Parse JSON from model text output, handling markdown code fences.
 * On resumed sessions the model may skip the StructuredOutput tool and
 * return raw JSON wrapped in ```json ... ``` fences.
 */
function parseJsonText<T>(raw: string): T {
  const text = raw.trim();
  // Try raw text first
  try {
    return JSON.parse(text) as T;
  } catch {
    // Try stripping markdown fences: ```json\n...\n``` or ```\n...\n```
    const fenceMatch = text.match(/^```\w*\n([\s\S]*?)\n```$/);
    if (fenceMatch) {
      try {
        return JSON.parse(fenceMatch[1]) as T;
      } catch {
        // fall through
      }
    }
    throw new Error(
      'Claude CLI did not return structured output and result text is not valid JSON',
    );
  }
}
