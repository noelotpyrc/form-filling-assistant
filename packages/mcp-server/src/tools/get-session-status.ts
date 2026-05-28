import { getSession } from '../session-manager.js';

export const getSessionStatusDefinition = {
  name: 'get_session_status',
  description:
    'Returns the current state of a form-filling session. ' +
    'Useful for resuming work or checking where things stand.',
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

export async function handleGetSessionStatus(args: {
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
            error: `Session not found: ${session_id}. It may have expired or been deleted.`,
          }),
        },
      ],
    };
  }

  const result = {
    session_id: session.session_id,
    form_id: session.form_id,
    status: session.status,
    current_draft_id: session.current_draft_id,
    token_expires_at: session.token_expires_at,
  };

  return {
    content: [{ type: 'text', text: JSON.stringify(result) }],
  };
}
