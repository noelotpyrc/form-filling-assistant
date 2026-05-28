import type { SubmitFinalResponse } from '@form-filling-assistant/shared';
import { getSession, updateSession } from '../session-manager.js';
import { authenticatedFetch } from '../http-client.js';

export const submitFinalDefinition = {
  name: 'submit_final',
  description:
    'Commits the final form submission. Requires a draft to have been submitted first via submit_draft. ' +
    'Only call this after the user has reviewed and confirmed the draft preview.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
    },
    required: ['session_id'],
  },
};

export async function handleSubmitFinal(args: {
  session_id: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id } = args;

  const session = getSession(session_id);
  if (!session) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Session not found: ${session_id}. Please call discover_form first.`,
          }),
        },
      ],
    };
  }

  if (!session.current_draft_id) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error:
              'No draft exists for this session. Please call submit_draft first to create a draft.',
          }),
        },
      ],
    };
  }

  const url = `${session.base_url}/submit-final`;

  try {
    const result = await authenticatedFetch(session_id, url, {
      method: 'POST',
      body: JSON.stringify({
        form_id: session.form_id,
        draft_id: session.current_draft_id,
      }),
    });

    if (!result.ok) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: `Final submission failed with status ${result.status}`,
              details: result.data,
            }),
          },
        ],
      };
    }

    const response = result.data as SubmitFinalResponse;

    // Mark session as submitted
    updateSession(session_id, {
      status: 'submitted',
    });

    return {
      content: [{ type: 'text', text: JSON.stringify(response) }],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ error: message }),
        },
      ],
    };
  }
}
