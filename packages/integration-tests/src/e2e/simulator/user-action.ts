/**
 * U→A Adapter: User Action Converter
 *
 * Converts LLM U's structured UserAction output into the per-turn
 * dynamic input that LLM A expects:
 *   - userMessage: the text/system-event string to send
 *   - formState: the updated form state snapshot (with any field edits applied)
 *   - stop: whether to end the session
 *
 * The loop controller is responsible for the static parts (system prompt
 * template, session management). This adapter only produces what changes
 * per turn.
 *
 * Action mapping:
 *   - message      → user message string (with optional [File:] wrapping)
 *   - select_choice → [system] User selected option: "..."
 *   - fill_fields   → no message, field edits applied to formState
 *   - click_button  → no message (loop controller handles button injection)
 *   - stop          → end session
 */

// ── Types ──

export interface FileAttachment {
  /** Display filename (e.g. "Resume.pdf") */
  filename: string;
  /** Pre-extracted text content of the file */
  content: string;
}

export interface UserAction {
  action: 'message' | 'select_choice' | 'fill_fields' | 'click_button' | 'stop';
  /** Free text message from the user */
  text?: string;
  /** File to attach — content already resolved, no persona lookup needed */
  file?: FileAttachment;
  /** Label of the selected choice (for select_choice) */
  label?: string;
  /** Field edits to apply silently (for fill_fields) */
  fields?: Record<string, unknown>;
}

export interface ConvertedAction {
  /** Message to send to LLM A (user message or system event). Null if no message. */
  userMessage: string | null;
  /** Updated form state snapshot (with any field edits applied). */
  formState: Record<string, unknown>;
  /** Whether to end the session. */
  stop: boolean;
}

// ── Converter ──

/**
 * Convert a UserAction from LLM U into the per-turn input for LLM A.
 *
 * @param userAction - Structured output from LLM U
 * @param formState  - Current form state snapshot (will not be mutated)
 * @returns The user message, updated form state, and stop flag
 */
export function convertUserActionToAppInput(
  userAction: UserAction,
  formState: Record<string, unknown>,
): ConvertedAction {
  switch (userAction.action) {
    case 'message': {
      let message = userAction.text || '';

      // If file attached, wrap content in the [File:...] format the app expects
      if (userAction.file) {
        const { filename, content } = userAction.file;
        message = `[File: ${filename}]\n${content}\n[End of ${filename}]\n\n${message}`;
      }

      return { userMessage: message, formState, stop: false };
    }

    case 'select_choice':
      return {
        userMessage: `[system] User selected option: "${userAction.label}"`,
        formState,
        stop: false,
      };

    case 'fill_fields': {
      if (!userAction.fields) {
        return { userMessage: null, formState, stop: false };
      }
      // Apply field edits to a copy of form state
      const updatedState = { ...formState, ...userAction.fields };
      return { userMessage: null, formState: updatedState, stop: false };
    }

    case 'click_button':
      // The loop controller handles the actual click event injection.
      // We just signal that it's a button click — no direct message or field edit.
      return { userMessage: null, formState, stop: false };

    case 'stop':
      return { userMessage: null, formState, stop: true };

    default:
      return { userMessage: null, formState, stop: false };
  }
}
