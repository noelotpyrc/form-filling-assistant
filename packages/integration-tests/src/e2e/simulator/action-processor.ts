/**
 * Action Processor — TypeScript port of processActions() and buildLlmAMessage()
 * from packages/web-app/public/js/sim-adapters.js
 *
 * Pure functions that convert LLM U's ranked candidate actions into an
 * execution plan the simulation loop can apply in a single pass.
 */

import { FileAttachment } from './user-action.js';

// ── Types ──

export interface LlmUAction {
  action: 'message' | 'select_choice' | 'fill_fields' | 'click_button' | 'stop';
  text?: string;
  label?: string;
  file?: string | FileAttachment;
  fields?: Record<string, unknown>;
}

export interface PlanMessage {
  text: string;
  isSystem?: boolean;
  fileKey?: string;
  resolvedFile?: FileAttachment;
}

export interface ActionPlan {
  stop: boolean;
  fieldEdits: Record<string, unknown>;
  messages: PlanMessage[];
  clickButton: string | null;
}

// ── Processor ──

/**
 * Process all actions from a selected LLM U candidate into a single execution plan.
 *
 * Rules:
 *   - stop → short-circuits, returns immediately
 *   - fill_fields → accumulates field edits (multiple fill_fields merge)
 *   - message → appends to messages list (with optional file key)
 *   - select_choice → appends system message
 *   - click_button → sets clickButton if a button was shown by LLM A
 *
 * @param actions - All actions from the selected candidate
 * @param formState - Current form values (not mutated)
 * @param availableButton - Button type from LLM A's show_button action ('save_draft'|'submit'|null)
 */
export function processActions(
  actions: LlmUAction[],
  formState: Record<string, unknown>,
  availableButton: string | null,
): ActionPlan {
  const plan: ActionPlan = {
    stop: false,
    fieldEdits: {},
    messages: [],
    clickButton: null,
  };

  if (!actions || actions.length === 0) return plan;

  for (const a of actions) {
    switch (a.action) {
      case 'stop':
        plan.stop = true;
        return plan;

      case 'fill_fields':
        if (a.fields) Object.assign(plan.fieldEdits, a.fields);
        break;

      case 'message': {
        const entry: PlanMessage = { text: a.text || '' };
        if (typeof a.file === 'string') entry.fileKey = a.file;
        plan.messages.push(entry);
        break;
      }

      case 'select_choice':
        plan.messages.push({
          text: `[system] User selected option: "${a.label || ''}"`,
          isSystem: true,
        });
        break;

      case 'click_button':
        if (availableButton) plan.clickButton = availableButton;
        break;
    }
  }

  return plan;
}

/**
 * Build the combined message string for LLM A from processed message entries.
 * Call AFTER resolving file keys — set msg.resolvedFile = { filename, content }.
 *
 * @param messages - From processActions().messages, with resolvedFile populated
 * @returns Combined message to send to LLM A
 */
export function buildLlmAMessage(messages: PlanMessage[]): string {
  const parts: string[] = [];
  for (const m of messages) {
    let text = m.text;
    if (m.resolvedFile && m.resolvedFile.filename) {
      const f = m.resolvedFile;
      text = `[File: ${f.filename}]\n${f.content}\n[End of ${f.filename}]\n\n${text}`;
    }
    parts.push(text);
  }
  return parts.join('\n');
}
