import type { SubmitDraftResponse } from '@form-filling-assistant/shared';
import { getSession, updateSession } from '../session-manager.js';
import { authenticatedFetch } from '../http-client.js';

export const submitDraftDefinition = {
  name: 'submit_draft',
  description:
    'Submits collected form data as a draft and returns a preview for user review. ' +
    'Can be called multiple times as the user makes edits.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      data: {
        type: 'object',
        description:
          'Form data organized by section (e.g., { personal: { ... }, education: { ... } }).',
      },
    },
    required: ['session_id', 'data'],
  },
};

export async function handleSubmitDraft(args: {
  session_id: string;
  data: Record<string, unknown>;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, data } = args;

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

  const url = `${session.base_url}/submit-draft`;

  try {
    const result = await authenticatedFetch(session_id, url, {
      method: 'POST',
      body: JSON.stringify({
        form_id: session.form_id,
        data,
      }),
    });

    if (!result.ok) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: `Draft submission failed with status ${result.status}`,
              details: result.data,
            }),
          },
        ],
      };
    }

    const response = result.data as SubmitDraftResponse;

    // Store the draft_id in the session
    updateSession(session_id, {
      current_draft_id: response.draft_id,
    });

    const draftResult = {
      draft_id: response.draft_id,
      preview: response.preview,
      warnings: response.warnings,
      completeness: response.completeness,
    };

    return {
      content: [{ type: 'text', text: JSON.stringify(draftResult) }],
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
