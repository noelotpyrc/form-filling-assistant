/**
 * @form-filling-assistant/claude-agent
 *
 * Thin wrapper around Claude Code CLI headless mode.
 * Use Claude as an LLM/agent backbone for any application.
 *
 * @example
 * ```typescript
 * import { ClaudeAgent, PRESETS } from '@form-filling-assistant/claude-agent';
 *
 * // One-shot question
 * const agent = new ClaudeAgent({ ...PRESETS.readonly, cwd: '/my/project' });
 * const answer = await agent.ask('What does this project do?');
 *
 * // Streaming events
 * for await (const event of agent.run('Explain the auth flow')) {
 *   if (event.type === 'text') process.stdout.write(event.text);
 * }
 *
 * // Structured output
 * const data = await agent.askJson<{ name: string }>(
 *   'What is the project name?',
 *   { type: 'object', properties: { name: { type: 'string' } }, required: ['name'] },
 * );
 * ```
 */

// ── Main class ──
export { ClaudeAgent } from './agent.js';

// ── Session types ──
export type { AgentSession, InteractiveSession } from './agent.js';

// ── Option & event types ──
export type {
  AgentOptions,
  AgentDefinition,
  ContentBlock,
  TextContent,
  ImageContent,
  AgentEvent,
  InitEvent,
  TextEvent,
  TextDeltaEvent,
  ToolInputDeltaEvent,
  ToolUseEvent,
  ToolResultEvent,
  UserMessageEvent,
  ResultEvent,
  ModelUsage,
  ErrorEvent,
  RawEvent,
} from './types.js';

// ── Presets ──
export { PRESETS } from './defaults.js';

// ── Low-level utilities (for advanced consumers) ──
export { EventNormalizer } from './events.js';
export { parseNdjsonStream } from './stream-parser.js';
export { buildArgs, buildInteractiveArgs, buildJsonArgs } from './args.js';
