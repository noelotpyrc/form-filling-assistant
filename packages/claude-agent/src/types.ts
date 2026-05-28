/**
 * Type definitions for the Claude CLI Agent wrapper.
 *
 * AgentOptions maps 1:1 to Claude CLI headless flags.
 * AgentEvent types represent the normalized NDJSON stream events.
 */

// ── Agent Options ──────────────────────────────────────────────────────────

/**
 * Configuration options for the Claude CLI agent.
 * Each option corresponds to a CLI flag. See `args.ts` for the mapping.
 */
export interface AgentOptions {
  /** Working directory (where .mcp.json lives). Defaults to process.cwd(). */
  cwd?: string;

  // ── Model ──

  /** Model name or alias: 'sonnet', 'opus', 'haiku', or full name like 'claude-sonnet-4-5-20250929' */
  model?: string;
  /** Fallback model when primary is overloaded (print mode only) */
  fallbackModel?: string;
  /** Effort level for reasoning: 'low', 'medium', 'high' */
  effort?: 'low' | 'medium' | 'high';

  // ── System Prompt ──
  // systemPrompt and systemPromptFile are mutually exclusive.
  // append variants can be used with either.

  /** Replace the entire default system prompt */
  systemPrompt?: string;
  /** Append to the default system prompt */
  appendSystemPrompt?: string;
  /** Load system prompt from a file (replaces default) */
  systemPromptFile?: string;
  /** Append system prompt text from a file */
  appendSystemPromptFile?: string;

  // ── Session ──

  /** Resume a specific session by ID */
  resume?: string;
  /** Continue the most recent conversation in the cwd */
  continue?: boolean;
  /** Fork the session when resuming (creates new session ID) */
  forkSession?: boolean;
  /** Use a specific session UUID */
  sessionId?: string;
  /** Don't save sessions to disk (ephemeral) */
  noSessionPersistence?: boolean;

  // ── Tools & Permissions ──

  /** Tools that execute without permission prompts. Supports permission rule syntax. */
  allowedTools?: string[];
  /** Tools that are blocked entirely */
  disallowedTools?: string[];
  /** Restrict which built-in tools are available. Use '' to disable all, 'default' for all. */
  tools?: string[] | '';
  /** Permission mode for the session */
  permissionMode?: 'default' | 'acceptEdits' | 'bypassPermissions' | 'plan' | 'delegate' | 'dontAsk';
  /** MCP tool name to handle permission prompts in non-interactive mode */
  permissionPromptTool?: string;
  /** Skip all permission checks (use with caution) */
  dangerouslySkipPermissions?: boolean;
  /** Enable bypassing permissions as an option without activating it */
  allowDangerouslySkipPermissions?: boolean;

  // ── Limits ──

  /** Maximum number of agentic turns before stopping */
  maxTurns?: number;
  /** Maximum dollar amount to spend on API calls */
  maxBudgetUsd?: number;

  // ── MCP ──

  /** Load MCP servers from JSON files or strings */
  mcpConfig?: string | string[];
  /** Only use servers from --mcp-config, ignore all other MCP configs */
  strictMcpConfig?: boolean;

  // ── Structured Output ──

  /** JSON Schema for structured output validation */
  jsonSchema?: Record<string, unknown>;

  // ── Streaming ──

  /** Include partial streaming events (token-level deltas) */
  includePartialMessages?: boolean;
  /** Echo user messages back on stdout (for ack in stream-json input mode) */
  replayUserMessages?: boolean;

  // ── Subagents ──

  /** Custom subagent definitions */
  agents?: Record<string, AgentDefinition>;

  // ── Directories ──

  /** Additional directories to allow tool access to */
  addDirs?: string[];

  // ── Settings ──

  /** Path to a settings JSON file or a JSON string */
  settings?: string;
  /** Which setting sources to load: 'user', 'project', 'local' */
  settingSources?: string[];
  /** Beta headers to include in API requests */
  betas?: string[];
  /** Disable all skills / slash commands */
  disableSlashCommands?: boolean;
  /** Enable/disable Chrome browser integration */
  chrome?: boolean;
  /** Enable debug mode. Pass true for all, or a filter string like 'api,hooks' */
  debug?: string | boolean;
  /** Path to write debug logs to a file */
  debugFile?: string;

  // ── Environment ──

  /** Custom environment variables for the Claude process */
  env?: Record<string, string>;

  // ── Callbacks ──

  /** Called with raw stderr data (for debugging) */
  onStderr?: (data: string) => void;
}

/**
 * Custom subagent definition (maps to --agents JSON).
 */
export interface AgentDefinition {
  /** Natural language description of when this subagent should be invoked */
  description: string;
  /** System prompt for the subagent */
  prompt: string;
  /** Array of tool names the subagent can use. If omitted, inherits all tools. */
  tools?: string[];
  /** Tools to explicitly deny for this subagent */
  disallowedTools?: string[];
  /** Model override: 'sonnet', 'opus', 'haiku', 'inherit' */
  model?: 'sonnet' | 'opus' | 'haiku' | 'inherit';
  /** Skill names to preload into the subagent's context */
  skills?: string[];
  /** MCP servers for this subagent */
  mcpServers?: Array<string | Record<string, unknown>>;
  /** Maximum agentic turns for the subagent */
  maxTurns?: number;
}

// ── Content Block Types (for interactive stdin messages) ──

export interface TextContent {
  type: 'text';
  text: string;
}

export interface ImageContent {
  type: 'image';
  source: {
    type: 'base64';
    media_type: string;
    data: string;
  };
}

export type ContentBlock = TextContent | ImageContent;

// ── Normalized Agent Events ────────────────────────────────────────────────

/**
 * Emitted when the CLI process initializes and the session is ready.
 */
export interface InitEvent {
  type: 'init';
  sessionId: string;
  model: string;
  tools: string[];
  mcpServers: Array<{ name: string; status: string }>;
  permissionMode: string;
  claudeCodeVersion?: string;
  agents?: string[];
  skills?: string[];
  /** The raw NDJSON event for full access */
  raw: unknown;
}

/**
 * Emitted for each complete text block in an assistant message.
 */
export interface TextEvent {
  type: 'text';
  text: string;
  raw: unknown;
}

/**
 * Emitted for streaming text deltas (requires includePartialMessages: true).
 * These are incremental token chunks — accumulate them for the full text.
 */
export interface TextDeltaEvent {
  type: 'text_delta';
  text: string;
  raw: unknown;
}

/**
 * Emitted for streaming tool input deltas (requires includePartialMessages: true).
 */
export interface ToolInputDeltaEvent {
  type: 'tool_input_delta';
  toolUseId?: string;
  name?: string;
  partialJson: string;
  raw: unknown;
}

/**
 * Emitted when a tool invocation starts.
 */
export interface ToolUseEvent {
  type: 'tool_use';
  toolUseId: string;
  name: string;
  input: unknown;
  parentToolUseId?: string | null;
  raw: unknown;
}

/**
 * Emitted when a tool invocation completes with a result.
 */
export interface ToolResultEvent {
  type: 'tool_result';
  toolUseId: string;
  name: string;
  content: string;
  raw: unknown;
}

/**
 * Emitted for user messages in the stream (usually synthetic, injected by the CLI).
 */
export interface UserMessageEvent {
  type: 'user_message';
  content: unknown;
  isSynthetic?: boolean;
  raw: unknown;
}

/**
 * Emitted when the CLI finishes (successfully or with error).
 */
export interface ResultEvent {
  type: 'result';
  subtype:
    | 'success'
    | 'error'
    | 'error_max_turns'
    | 'error_max_budget_usd'
    | 'error_during_execution'
    | 'error_max_structured_output_retries';
  sessionId: string;
  isError: boolean;
  result: string;
  durationMs: number;
  durationApiMs: number;
  costUsd: number;
  numTurns: number;
  usage: Record<string, unknown>;
  modelUsage: Record<string, ModelUsage>;
  structuredOutput?: unknown;
  errors?: string[];
  raw: unknown;
}

/**
 * Per-model usage statistics from the result event.
 */
export interface ModelUsage {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
  webSearchRequests: number;
  costUSD: number;
  contextWindow: number;
  maxOutputTokens?: number;
}

/**
 * Emitted on CLI process errors (spawn failure, non-zero exit, etc.)
 */
export interface ErrorEvent {
  type: 'error';
  message: string;
  raw?: unknown;
}

/**
 * Passthrough for any NDJSON event we don't explicitly normalize.
 * Consumers can inspect `data` for the raw event.
 */
export interface RawEvent {
  type: 'raw';
  eventType: string;
  data: unknown;
}

/**
 * Union of all normalized events emitted by the agent.
 */
export type AgentEvent =
  | InitEvent
  | TextEvent
  | TextDeltaEvent
  | ToolInputDeltaEvent
  | ToolUseEvent
  | ToolResultEvent
  | UserMessageEvent
  | ResultEvent
  | ErrorEvent
  | RawEvent;
