/**
 * LLM U Action Catalog
 *
 * Defines the complete set of atomic actions/reactions LLM U can take.
 * Used as context in LLM U's prompt so it picks from a known action space.
 *
 * Two categories:
 *   - REACTIVE: responding to something visible on screen (choice buttons,
 *     form fields, a button, a preview card, or a question in the chat)
 *   - PROACTIVE: user-initiated, not directly prompted by what's on screen
 *
 * Descriptions are written from the user's perspective — what they see on
 * screen, not LLM A's internal action types. LLM U never sees raw action
 * types like ask_choice or show_fields; it sees rendered text like
 * "Choice buttons: [...]" or "Form section 'Education' is open with fields: ...".
 *
 * Each action maps to one or more UserAction outputs via the U→A adapter.
 */

// ── Reactive actions ──
// These respond to something visible on the current screen.

export const REACTIVE_ACTIONS = {
  /** Screen shows choice buttons → user picks one */
  select_choice: {
    description: 'Pick one of the choice buttons shown on screen',
    outputs: 'select_choice',
  },

  /** Screen shows a form section with input fields → user fills them in */
  fill_presented_fields: {
    description: 'Fill in the form fields that are currently open on screen',
    outputs: 'fill_fields',
  },

  /** Screen shows a save/submit button → user clicks it */
  click_button: {
    description: 'Click the save draft or submit button shown on screen',
    outputs: 'click_button',
  },

  /** Screen shows a preview card → user confirms it looks correct */
  confirm_preview: {
    description: 'Confirm the preview summary shown on screen looks correct',
    outputs: 'message',
  },

  /** Screen shows a preview card → user spots an error */
  reject_preview: {
    description: 'Point out an error in the preview shown on screen and ask to fix it',
    outputs: 'message',
  },

  /** Assistant asked a question in the chat → user answers */
  answer_question: {
    description: 'Answer a question the assistant asked in the chat',
    outputs: 'message',
  },

  /** User agrees with what the assistant said or did */
  confirm: {
    description: 'Simple agreement or confirmation ("yes", "correct", "go ahead", "sounds good")',
    outputs: 'message',
  },

  /** User disagrees or wants to pause */
  deny: {
    description: 'Simple disagreement or pause ("no", "wait", "not yet", "hold on")',
    outputs: 'message',
  },

  /** User didn't understand the assistant's message */
  request_clarification: {
    description: 'Ask the assistant to rephrase or explain what it just said',
    outputs: 'message',
  },

  /** Assistant mentioned needing a document → user uploads it */
  upload_file: {
    description: 'Upload a document the assistant mentioned (resume, transcript, etc.)',
    outputs: 'message + file',
  },

  /** Assistant mentioned needing a document → user declines */
  decline_file: {
    description: "Decline to upload a file (don't have it, will do later, etc.)",
    outputs: 'message',
  },
} as const;

// ── Proactive actions ──
// User-initiated. Can happen at any point in the conversation.

export const PROACTIVE_ACTIONS = {
  /** User volunteers personal info without being asked */
  provide_info: {
    description: 'Proactively share personal information (name, education, work history, etc.)',
    outputs: 'message',
  },

  /** User edits form fields directly in the form panel */
  edit_fields: {
    description: 'Directly edit form fields in the panel (without going through chat)',
    outputs: 'fill_fields',
  },

  /** User asks about a field, requirement, or process */
  ask_question: {
    description: 'Ask a question about the form, a field, or the process',
    outputs: 'message',
  },

  /** User notices the assistant filled something wrong */
  correct_mistake: {
    description: 'Point out a mistake the assistant made and provide the correct value',
    outputs: 'message',
  },

  /** User wants to revisit a previous section */
  revisit_section: {
    description: 'Go back to a previous section to review or change answers',
    outputs: 'message',
  },

  /** User wants to see what's been filled or what's left */
  review_progress: {
    description: 'Ask to see a summary of what has been filled so far, or check what fields remain',
    outputs: 'message',
  },

  /** User wants to see a specific section's fields */
  inspect_section: {
    description: 'Ask the assistant to show or expand a specific form section (e.g. "show me the Education section")',
    outputs: 'message',
  },

  /** User wants to skip something */
  skip: {
    description: 'Ask to skip a section, optional field, or move on',
    outputs: 'message',
  },

  /** User wants to save progress */
  request_save: {
    description: 'Ask the assistant to save the current draft',
    outputs: 'message',
  },

  /** User says something off-topic */
  small_talk: {
    description: 'Off-topic message, greeting, or social comment',
    outputs: 'message',
  },

  /** User wants to end the session */
  stop: {
    description: 'End the session (done, leaving, will come back later)',
    outputs: 'stop',
  },
} as const;

// ── Combined catalog ──

export const ACTION_CATALOG = {
  reactive: REACTIVE_ACTIONS,
  proactive: PROACTIVE_ACTIONS,
} as const;

// ── Types ──

export type ReactiveActionId = keyof typeof REACTIVE_ACTIONS;
export type ProactiveActionId = keyof typeof PROACTIVE_ACTIONS;
export type ActionId = ReactiveActionId | ProactiveActionId;

// ── Prompt rendering ──

/**
 * Render the action catalog as a text block for inclusion in LLM U's prompt.
 * Groups by reactive/proactive and numbers them for easy reference.
 */
export function renderActionCatalog(): string {
  const lines: string[] = [];

  lines.push('## Available Actions');
  lines.push('');
  lines.push('### Reactive (responding to what you see on screen)');
  let i = 1;
  for (const [id, action] of Object.entries(REACTIVE_ACTIONS)) {
    lines.push(`  ${i}. ${id}: ${action.description}`);
    i++;
  }

  lines.push('');
  lines.push('### Proactive (you initiate)');
  for (const [id, action] of Object.entries(PROACTIVE_ACTIONS)) {
    lines.push(`  ${i}. ${id}: ${action.description}`);
    i++;
  }

  return lines.join('\n');
}
