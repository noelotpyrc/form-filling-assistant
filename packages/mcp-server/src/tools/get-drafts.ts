import { getSession } from '../session-manager.js';

export const getDraftsDefinition = {
  name: 'get_drafts',
  description:
    'Retrieve saved drafts from the website. ' +
    'If an email is provided, returns the draft for that specific user. ' +
    'If no email is provided, returns all saved drafts. ' +
    'Useful for resuming a previously started form or checking if a user already has a draft on file.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      email: {
        type: 'string',
        description:
          'Optional email address to look up a specific draft. If omitted, returns all drafts.',
      },
    },
    required: ['session_id'],
  },
};

export async function handleGetDrafts(args: {
  session_id: string;
  email?: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, email } = args;

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

  const queryParam = email ? `?email=${encodeURIComponent(email)}` : '';
  const url = `${session.base_url}/drafts${queryParam}`;

  try {
    const res = await fetch(url);
    const body = await res.json();

    if (!res.ok) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              found: false,
              ...(email && { email }),
              message: (body as { error?: string }).error || `No draft found (HTTP ${res.status}).`,
            }),
          },
        ],
      };
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            found: true,
            ...(email && { email }),
            ...body,
          }),
        },
      ],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to fetch drafts: ${message}`,
          }),
        },
      ],
    };
  }
}
