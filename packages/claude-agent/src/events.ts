/**
 * Event normalization: maps raw NDJSON events from the Claude CLI
 * into typed AgentEvent objects.
 *
 * This module handles the translation between the CLI's stream protocol
 * and our clean, typed event interface.
 */

import type {
  AgentEvent,
  InitEvent,
  TextEvent,
  TextDeltaEvent,
  ToolInputDeltaEvent,
  ToolUseEvent,
  ToolResultEvent,
  UserMessageEvent,
  ResultEvent,
  ErrorEvent,
  RawEvent,
} from './types.js';

/**
 * Stateful event normalizer.
 * Tracks tool_use IDs to match tool_results back to their tool names.
 */
export class EventNormalizer {
  /** Maps tool_use block IDs to tool names */
  private toolUseNames = new Map<string, string>();

  /** Maps content_block index to tool name (for streaming tool input deltas) */
  private streamingToolNames = new Map<number, string>();

  /**
   * Normalize a raw NDJSON event into zero or more AgentEvents.
   *
   * A single raw event can produce multiple AgentEvents
   * (e.g., an assistant message with text + tool_use + tool_result blocks).
   */
  *normalize(raw: unknown): Generator<AgentEvent> {
    const event = raw as Record<string, unknown>;
    const eventType = event.type as string;

    switch (eventType) {
      case 'system':
        yield* this.normalizeSystem(event);
        break;

      case 'assistant':
        yield* this.normalizeAssistant(event);
        break;

      case 'user':
        yield* this.normalizeUser(event);
        break;

      case 'stream_event':
        yield* this.normalizeStreamEvent(event);
        break;

      case 'result':
        yield* this.normalizeResult(event);
        break;

      case 'tool_use_summary':
        // Informational — pass through as raw
        yield this.raw(eventType, event);
        break;

      default:
        yield this.raw(eventType, event);
        break;
    }
  }

  // ── System Events ──

  private *normalizeSystem(event: Record<string, unknown>): Generator<AgentEvent> {
    const subtype = event.subtype as string;

    if (subtype === 'init') {
      const init: InitEvent = {
        type: 'init',
        sessionId: event.session_id as string,
        model: event.model as string,
        tools: (event.tools as string[]) ?? [],
        mcpServers: (event.mcp_servers as Array<{ name: string; status: string }>) ?? [],
        permissionMode: (event.permissionMode as string) ?? 'default',
        claudeCodeVersion: event.claude_code_version as string | undefined,
        agents: event.agents as string[] | undefined,
        skills: event.skills as string[] | undefined,
        raw: event,
      };
      yield init;
    } else {
      // compact_boundary, etc.
      yield this.raw('system/' + subtype, event);
    }
  }

  // ── Assistant Messages ──

  private *normalizeAssistant(event: Record<string, unknown>): Generator<AgentEvent> {
    const message = event.message as Record<string, unknown> | undefined;
    const content = message?.content as Array<Record<string, unknown>> | undefined;
    const parentToolUseId = event.parent_tool_use_id as string | null | undefined;

    if (!Array.isArray(content)) return;

    for (const block of content) {
      const blockType = block.type as string;

      switch (blockType) {
        case 'text': {
          const text = block.text as string;
          if (text) {
            const textEvent: TextEvent = { type: 'text', text, raw: event };
            yield textEvent;
          }
          break;
        }

        case 'tool_use': {
          const toolUseId = block.id as string;
          const name = block.name as string;
          this.toolUseNames.set(toolUseId, name);

          const toolUseEvent: ToolUseEvent = {
            type: 'tool_use',
            toolUseId,
            name,
            input: block.input,
            parentToolUseId: parentToolUseId ?? null,
            raw: event,
          };
          yield toolUseEvent;
          break;
        }

        case 'tool_result': {
          const toolUseId = block.tool_use_id as string;
          const name = this.toolUseNames.get(toolUseId) ?? 'unknown';

          const toolResultEvent: ToolResultEvent = {
            type: 'tool_result',
            toolUseId,
            name,
            content: typeof block.content === 'string'
              ? block.content
              : JSON.stringify(block.content),
            raw: event,
          };
          yield toolResultEvent;
          break;
        }

        default:
          // Unknown content block type
          yield this.raw('assistant/' + blockType, event);
          break;
      }
    }
  }

  // ── User Messages ──

  private *normalizeUser(event: Record<string, unknown>): Generator<AgentEvent> {
    const message = event.message as Record<string, unknown> | undefined;
    const content = message?.content;
    const isSynthetic = event.isSynthetic as boolean | undefined;

    // Check if this is a tool_result user message (e.g., from structured output flow)
    if (Array.isArray(content)) {
      for (const block of content as Array<Record<string, unknown>>) {
        if (block.type === 'tool_result') {
          const toolUseId = block.tool_use_id as string;
          const name = this.toolUseNames.get(toolUseId) ?? 'unknown';
          const toolResultEvent: ToolResultEvent = {
            type: 'tool_result',
            toolUseId,
            name,
            content: typeof block.content === 'string'
              ? block.content
              : JSON.stringify(block.content),
            raw: event,
          };
          yield toolResultEvent;
          return;
        }
      }
    }

    const userEvent: UserMessageEvent = {
      type: 'user_message',
      content,
      isSynthetic: isSynthetic ?? false,
      raw: event,
    };
    yield userEvent;
  }

  // ── Stream Events (partial messages) ──

  private *normalizeStreamEvent(event: Record<string, unknown>): Generator<AgentEvent> {
    const innerEvent = event.event as Record<string, unknown> | undefined;
    if (!innerEvent) return;

    const innerType = innerEvent.type as string;

    switch (innerType) {
      case 'content_block_start': {
        // Track tool names for streaming tool input deltas
        const contentBlock = innerEvent.content_block as Record<string, unknown> | undefined;
        const index = innerEvent.index as number | undefined;
        if (contentBlock?.type === 'tool_use' && index !== undefined) {
          this.streamingToolNames.set(index, contentBlock.name as string);
        }
        break;
      }

      case 'content_block_delta': {
        const delta = innerEvent.delta as Record<string, unknown> | undefined;
        if (!delta) break;

        const deltaType = delta.type as string;
        if (deltaType === 'text_delta') {
          const text = delta.text as string;
          if (text) {
            const textDelta: TextDeltaEvent = { type: 'text_delta', text, raw: event };
            yield textDelta;
          }
        } else if (deltaType === 'input_json_delta') {
          const partialJson = delta.partial_json as string;
          const index = innerEvent.index as number | undefined;
          if (partialJson) {
            const toolDelta: ToolInputDeltaEvent = {
              type: 'tool_input_delta',
              toolUseId: undefined,
              name: index !== undefined ? this.streamingToolNames.get(index) : undefined,
              partialJson,
              raw: event,
            };
            yield toolDelta;
          }
        }
        break;
      }

      case 'content_block_stop': {
        // Clean up streaming tool name tracking
        const index = innerEvent.index as number | undefined;
        if (index !== undefined) {
          this.streamingToolNames.delete(index);
        }
        break;
      }

      // message_start, message_delta, message_stop — pass through as raw
      default:
        yield this.raw('stream_event/' + innerType, event);
        break;
    }
  }

  // ── Result ──

  private *normalizeResult(event: Record<string, unknown>): Generator<AgentEvent> {
    const result: ResultEvent = {
      type: 'result',
      subtype: (event.subtype as ResultEvent['subtype']) ?? 'success',
      sessionId: event.session_id as string,
      isError: (event.is_error as boolean) ?? false,
      result: (event.result as string) ?? '',
      durationMs: (event.duration_ms as number) ?? 0,
      durationApiMs: (event.duration_api_ms as number) ?? 0,
      costUsd: (event.total_cost_usd as number) ?? 0,
      numTurns: (event.num_turns as number) ?? 0,
      usage: (event.usage as Record<string, unknown>) ?? {},
      modelUsage: (event.modelUsage as Record<string, ResultEvent['modelUsage'][string]>) ?? {},
      structuredOutput: event.structured_output,
      errors: event.errors as string[] | undefined,
      raw: event,
    };
    yield result;
  }

  // ── Helpers ──

  private raw(eventType: string, data: unknown): RawEvent {
    return { type: 'raw', eventType, data };
  }

  /**
   * Create an ErrorEvent (used by the process layer, not from NDJSON).
   */
  static error(message: string, raw?: unknown): ErrorEvent {
    return { type: 'error', message, raw };
  }
}
