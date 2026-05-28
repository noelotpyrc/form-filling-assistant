/**
 * Replayable Session Log Format
 *
 * Typed entry interfaces and logger for the three-actor simulation log:
 *   LLM U ↔ Middleman (state) ↔ LLM A
 *
 * Given just the JSONL, you can reconstruct the entire session — scrubbing
 * through a timeline of message exchanges and state changes across all three actors.
 *
 * Predictable per-turn sequence:
 *   state_init
 *   → [llm_a_input → llm_a_output → state_update]           (turn 0: greeting)
 *   → [llm_u_input → llm_u_output → action_plan
 *      → state_update → llm_a_input → llm_a_output
 *      → state_update]                                       (turns 1..N)
 *   → session_end
 */

// ── Entry Types ──

export interface StateInitEntry {
  type: 'state_init';
  form_id: string;
  form_name: string;
  form_schema: object;
  initial_form_values: Record<string, unknown>;
  persona: string;
  persona_data: Record<string, unknown>;
  profile: string;
  session_config: {
    llm_a_model: string;
    llm_u_model: string;
    seed?: number;
  };
}

export interface LlmAInputEntry {
  type: 'llm_a_input';
  turn: number;
  system_prompt_length: number;
  user_message: string;
  resume_session_id: string | null;
}

export interface LlmAOutputEntry {
  type: 'llm_a_output';
  turn: number;
  raw_text: string;
  parsed_actions: object[];
  session_id: string;
  cost_usd: number;
  duration_ms: number;
  form_state_snapshot: Record<string, unknown>;
}

export interface StateUpdateEntry {
  type: 'state_update';
  turn: number;
  source: 'llm_a' | 'llm_u' | 'button';
  delta: Record<string, unknown>;
  form_values: Record<string, unknown>;
}

export interface LlmUInputEntry {
  type: 'llm_u_input';
  turn: number;
  screen_view: string;
}

export interface LlmUOutputEntry {
  type: 'llm_u_output';
  turn: number;
  candidates: object[];
  selected_index: number;
  selected_intent: string;
  sampling_mode: string;
  cost_usd: number;
  duration_ms: number;
}

export interface ActionPlanEntry {
  type: 'action_plan';
  turn: number;
  stop: boolean;
  field_edits: Record<string, unknown>;
  messages: Array<{ text: string; isSystem?: boolean; fileKey?: string }>;
  click_button: string | null;
}

export interface SessionEndEntry {
  type: 'session_end';
  turn: number;
  reason: 'user_stop' | 'stuck_loop' | 'max_turns' | 'error';
  total_llm_a_cost: number;
  total_llm_u_cost: number;
  fields_filled: number;
}

export type SessionLogEntry =
  | StateInitEntry
  | LlmAInputEntry
  | LlmAOutputEntry
  | StateUpdateEntry
  | LlmUInputEntry
  | LlmUOutputEntry
  | ActionPlanEntry
  | SessionEndEntry;

export type TimestampedEntry = SessionLogEntry & { timestamp: string };

// ── Logger ──

export class SessionLogger {
  private entries: TimestampedEntry[] = [];

  log(entry: SessionLogEntry): void {
    this.entries.push({ ...entry, timestamp: new Date().toISOString() } as TimestampedEntry);
  }

  toJsonl(): string {
    return this.entries.map((e) => JSON.stringify(e)).join('\n') + '\n';
  }

  get length(): number {
    return this.entries.length;
  }
}
