/**
 * Converts AgentOptions into CLI argument arrays for spawning `claude`.
 *
 * This is a pure function with no side effects.
 */

import type { AgentOptions } from './types.js';

/**
 * Build the CLI args for a single-message `claude -p` invocation.
 *
 * @param prompt - The user message to send
 * @param opts - Agent options (merged defaults + per-call overrides)
 * @returns Array of CLI argument strings
 */
export function buildArgs(prompt: string, opts: AgentOptions): string[] {
  const args: string[] = [
    '-p', prompt,
    '--output-format', 'stream-json',
    '--verbose',
  ];

  addCommonArgs(args, opts);
  return args;
}

/**
 * Build the CLI args for interactive streaming mode (--input-format stream-json).
 * In this mode, the prompt is sent via stdin, not as a CLI argument.
 *
 * @param opts - Agent options
 * @returns Array of CLI argument strings
 */
export function buildInteractiveArgs(opts: AgentOptions): string[] {
  const args: string[] = [
    '-p',
    '--output-format', 'stream-json',
    '--verbose',
    '--input-format', 'stream-json',
  ];

  addCommonArgs(args, opts);
  return args;
}

/**
 * Build args for a non-streaming JSON response (used by ask()).
 *
 * @param prompt - The user message
 * @param opts - Agent options
 * @returns Array of CLI argument strings
 */
export function buildJsonArgs(prompt: string, opts: AgentOptions): string[] {
  const args: string[] = [
    '-p', prompt,
    '--output-format', 'json',
  ];

  addCommonArgs(args, opts);
  return args;
}

// ── Internal ──

function addCommonArgs(args: string[], opts: AgentOptions): void {
  // Model
  if (opts.model) {
    args.push('--model', opts.model);
  }
  if (opts.fallbackModel) {
    args.push('--fallback-model', opts.fallbackModel);
  }
  if (opts.effort) {
    args.push('--effort', opts.effort);
  }

  // System prompt (mutually exclusive: systemPrompt vs systemPromptFile)
  if (opts.systemPrompt) {
    args.push('--system-prompt', opts.systemPrompt);
  } else if (opts.systemPromptFile) {
    args.push('--system-prompt-file', opts.systemPromptFile);
  }
  if (opts.appendSystemPrompt) {
    args.push('--append-system-prompt', opts.appendSystemPrompt);
  }
  if (opts.appendSystemPromptFile) {
    args.push('--append-system-prompt-file', opts.appendSystemPromptFile);
  }

  // Session
  if (opts.resume) {
    args.push('--resume', opts.resume);
  }
  if (opts.continue) {
    args.push('--continue');
  }
  if (opts.forkSession) {
    args.push('--fork-session');
  }
  if (opts.sessionId) {
    args.push('--session-id', opts.sessionId);
  }
  if (opts.noSessionPersistence) {
    args.push('--no-session-persistence');
  }

  // Tools & Permissions
  if (opts.allowedTools && opts.allowedTools.length > 0) {
    args.push('--allowedTools', ...opts.allowedTools);
  }
  if (opts.disallowedTools && opts.disallowedTools.length > 0) {
    args.push('--disallowedTools', ...opts.disallowedTools);
  }
  if (opts.tools !== undefined) {
    if (opts.tools === '') {
      args.push('--tools', '');
    } else if (Array.isArray(opts.tools) && opts.tools.length > 0) {
      args.push('--tools', ...opts.tools);
    }
  }
  if (opts.permissionMode) {
    args.push('--permission-mode', opts.permissionMode);
  }
  if (opts.permissionPromptTool) {
    args.push('--permission-prompt-tool', opts.permissionPromptTool);
  }
  if (opts.dangerouslySkipPermissions) {
    args.push('--dangerously-skip-permissions');
  }
  if (opts.allowDangerouslySkipPermissions) {
    args.push('--allow-dangerously-skip-permissions');
  }

  // Limits
  if (opts.maxTurns !== undefined) {
    args.push('--max-turns', String(opts.maxTurns));
  }
  if (opts.maxBudgetUsd !== undefined) {
    args.push('--max-budget-usd', String(opts.maxBudgetUsd));
  }

  // MCP
  if (opts.mcpConfig) {
    const configs = Array.isArray(opts.mcpConfig) ? opts.mcpConfig : [opts.mcpConfig];
    args.push('--mcp-config', ...configs);
  }
  if (opts.strictMcpConfig) {
    args.push('--strict-mcp-config');
  }

  // Structured output
  if (opts.jsonSchema) {
    args.push('--json-schema', JSON.stringify(opts.jsonSchema));
  }

  // Streaming
  if (opts.includePartialMessages) {
    args.push('--include-partial-messages');
  }
  if (opts.replayUserMessages) {
    args.push('--replay-user-messages');
  }

  // Subagents
  if (opts.agents && Object.keys(opts.agents).length > 0) {
    args.push('--agents', JSON.stringify(opts.agents));
  }

  // Directories
  if (opts.addDirs && opts.addDirs.length > 0) {
    args.push('--add-dir', ...opts.addDirs);
  }

  // Settings
  if (opts.settings) {
    args.push('--settings', opts.settings);
  }
  if (opts.settingSources && opts.settingSources.length > 0) {
    args.push('--setting-sources', opts.settingSources.join(','));
  }
  if (opts.betas && opts.betas.length > 0) {
    args.push('--betas', ...opts.betas);
  }
  if (opts.disableSlashCommands) {
    args.push('--disable-slash-commands');
  }
  if (opts.chrome === true) {
    args.push('--chrome');
  } else if (opts.chrome === false) {
    args.push('--no-chrome');
  }

  // Debug
  if (opts.debug === true) {
    args.push('--debug');
  } else if (typeof opts.debug === 'string') {
    args.push('--debug', opts.debug);
  }
  if (opts.debugFile) {
    args.push('--debug-file', opts.debugFile);
  }
}
