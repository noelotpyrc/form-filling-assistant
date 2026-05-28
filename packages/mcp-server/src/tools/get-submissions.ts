import { getSession } from '../session-manager.js';

export const getSubmissionsDefinition = {
  name: 'get_submissions',
  description:
    'Retrieve completed submissions from the website. ' +
    'If an email is provided, returns the submission for that specific user (including reference number and submission date). ' +
    'If no email is provided, returns all submissions. ' +
    'Useful for checking if a form was successfully submitted or looking up a confirmation reference number.',
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
          'Optional email address to look up a specific submission. If omitted, returns all submissions.',
      },
    },
    required: ['session_id'],
  },
};

export async function handleGetSubmissions(args: {
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
  const url = `${session.base_url}/submissions${queryParam}`;

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
              message: (body as { error?: string }).error || `No submission found (HTTP ${res.status}).`,
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
            error: `Failed to fetch submissions: ${message}`,
          }),
        },
      ],
    };
  }
}
