/**
 * Claude CLI process spawning and lifecycle management.
 *
 * Handles spawning `claude`, piping stdin/stdout, and cleanup.
 */

import { spawn, type ChildProcess } from 'node:child_process';
import type { AgentOptions, ContentBlock } from './types.js';
import type { AgentEvent } from './types.js';
import { buildArgs, buildInteractiveArgs, buildJsonArgs } from './args.js';
import { parseNdjsonStream } from './stream-parser.js';
import { EventNormalizer } from './events.js';

/** Claude CLI binary name (assumes it's on PATH) */
const CLAUDE_BIN = 'claude';

// ── Single-message streaming mode ──

/**
 * Spawn claude in single-message streaming mode and yield normalized events.
 *
 * @param prompt - User message
 * @param opts - Merged agent options
 * @param abort - Callback to receive the abort function
 */
export async function* runStreaming(
  prompt: string,
  opts: AgentOptions,
  abort: { fn?: () => void },
): AsyncGenerator<AgentEvent> {
  const args = buildArgs(prompt, opts);
  const proc = spawnClaude(args, opts);
  abort.fn = () => proc.kill('SIGTERM');

  yield* pipeProcess(proc, opts);
}

// ── Interactive streaming mode ──

export interface InteractiveHandle {
  /** Send a user message via stdin */
  send(message: string | ContentBlock[]): void;
  /** Send a control message via stdin */
  sendControl(control: Record<string, unknown>): void;
  /** Abort the CLI process */
  abort(): void;
  /** Async generator of events from stdout */
  events: AsyncGenerator<AgentEvent>;
}

/**
 * Spawn claude in interactive streaming mode (bidirectional stdin/stdout).
 */
export function runInteractiveProcess(opts: AgentOptions): InteractiveHandle {
  const args = buildInteractiveArgs(opts);
  const proc = spawnClaude(args, opts, true /* needsStdin */);

  const send = (message: string | ContentBlock[]): void => {
    const content = typeof message === 'string' ? message : message;
    const payload = JSON.stringify({
      type: 'user',
      message: { role: 'user', content },
    });
    proc.stdin?.write(payload + '\n');
  };

  const sendControl = (control: Record<string, unknown>): void => {
    const payload = JSON.stringify({ type: 'control', ...control });
    proc.stdin?.write(payload + '\n');
  };

  const abort = (): void => {
    proc.stdin?.end();
    proc.kill('SIGTERM');
  };

  return {
    send,
    sendControl,
    abort,
    events: pipeProcess(proc, opts),
  };
}

// ── Non-streaming JSON mode (for ask()) ──

/**
 * Result from a non-streaming JSON invocation.
 */
export interface JsonResult {
  result: string;
  sessionId: string;
  isError: boolean;
  costUsd: number;
  durationMs: number;
  numTurns: number;
  structuredOutput?: unknown;
  raw: unknown;
}

/**
 * Spawn claude in JSON output mode and return the parsed result.
 */
export async function runJson(prompt: string, opts: AgentOptions): Promise<JsonResult> {
  const args = buildJsonArgs(prompt, opts);
  const proc = spawnClaude(args, opts);

  return new Promise<JsonResult>((resolve, reject) => {
    let stdout = '';
    let stderr = '';

    proc.stdout?.on('data', (data: Buffer) => {
      stdout += data.toString();
    });

    proc.stderr?.on('data', (data: Buffer) => {
      stderr += data.toString();
      opts.onStderr?.(data.toString());
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn Claude CLI: ${err.message}`));
    });

    proc.on('close', (code) => {
      if (code !== 0 && code !== null) {
        reject(new Error(`Claude CLI exited with code ${code}${stderr ? ': ' + stderr.trim() : ''}`));
        return;
      }

      try {
        const parsed = JSON.parse(stdout.trim()) as Record<string, unknown>;
        resolve({
          result: (parsed.result as string) ?? '',
          sessionId: (parsed.session_id as string) ?? '',
          isError: (parsed.is_error as boolean) ?? false,
          costUsd: (parsed.total_cost_usd as number) ?? 0,
          durationMs: (parsed.duration_ms as number) ?? 0,
          numTurns: (parsed.num_turns as number) ?? 0,
          structuredOutput: parsed.structured_output,
          raw: parsed,
        });
      } catch (err) {
        reject(new Error(`Failed to parse Claude CLI JSON output: ${(err as Error).message}`));
      }
    });
  });
}

// ── Internal helpers ──

function spawnClaude(
  args: string[],
  opts: AgentOptions,
  needsStdin = false,
): ChildProcess {
  const proc = spawn(CLAUDE_BIN, args, {
    cwd: opts.cwd ?? process.cwd(),
    env: opts.env ? { ...process.env, ...opts.env } : { ...process.env },
    stdio: [needsStdin ? 'pipe' : 'ignore', 'pipe', 'pipe'],
  });

  return proc;
}

async function* pipeProcess(
  proc: ChildProcess,
  opts: AgentOptions,
): AsyncGenerator<AgentEvent> {
  const normalizer = new EventNormalizer();

  // Capture stderr for debugging
  proc.stderr?.on('data', (data: Buffer) => {
    opts.onStderr?.(data.toString());
  });

  // Set up error handling
  let processError: Error | undefined;

  proc.on('error', (err) => {
    processError = err;
  });

  // Parse stdout as NDJSON and normalize events
  if (proc.stdout) {
    try {
      for await (const rawEvent of parseNdjsonStream(proc.stdout)) {
        for (const event of normalizer.normalize(rawEvent)) {
          yield event;
        }
      }
    } catch (err) {
      yield EventNormalizer.error(`Stream error: ${(err as Error).message}`);
    }
  }

  // Wait for process to fully exit
  const exitCode = await new Promise<number | null>((resolve) => {
    if (proc.exitCode !== null) {
      resolve(proc.exitCode);
    } else {
      proc.on('close', (code) => resolve(code));
    }
  });

  // Emit error if process failed
  if (processError) {
    yield EventNormalizer.error(`Failed to spawn Claude CLI: ${processError.message}`);
  } else if (exitCode !== 0 && exitCode !== null) {
    yield EventNormalizer.error(`Claude CLI exited with code ${exitCode}`);
  }
}
