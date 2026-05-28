import type { DiscoverResponse } from '@form-filling-assistant/shared';
import { createSession } from '../session-manager.js';

export const discoverFormDefinition = {
  name: 'discover_form',
  description:
    'Connects to a website and retrieves the form schema and instructions for AI-assisted form filling. ' +
    'Call this first to start a new form-filling session.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      url: {
        type: 'string',
        description:
          'Base URL of the website (e.g., http://localhost:3001). The /ai-agent/v1/discover endpoint will be called automatically.',
      },
      form_type: {
        type: 'string',
        description:
          'Optional. Specific form to request if the site hosts multiple forms.',
      },
    },
    required: ['url'],
  },
};

export async function handleDiscoverForm(args: {
  url: string;
  form_type?: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { url, form_type } = args;

  // Normalize the base URL: strip trailing slashes
  const baseUrl = url.replace(/\/+$/, '');
  const discoverUrl = `${baseUrl}/ai-agent/v1/discover`;

  const requestBody: Record<string, string> = {
    agent_id: 'claude-form-filler-1.0',
  };
  if (form_type) {
    requestBody.form_type = form_type;
  }

  let response: Response;
  try {
    response = await fetch(discoverUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to connect to ${discoverUrl}: ${message}. Please check that the website is running and the URL is correct.`,
          }),
        },
      ],
    };
  }

  if (!response.ok) {
    let errorBody: unknown;
    try {
      errorBody = await response.json();
    } catch {
      errorBody = { raw: await response.text() };
    }
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Discovery failed with status ${response.status}`,
            details: errorBody,
          }),
        },
      ],
    };
  }

  const data = (await response.json()) as DiscoverResponse;

  // Store the full response (including auth_token) in a new session
  const apiBaseUrl = `${baseUrl}/ai-agent/v1`;
  const session = createSession({
    form_id: data.form_id,
    base_url: apiBaseUrl,
    auth_token: data.auth_token,
    token_expires_at: data.token_expires_at,
    schema: data.schema,
    instructions: data.instructions,
  });

  // Return schema and instructions to Claude, but strip auth_token
  const result = {
    session_id: session.session_id,
    form_id: data.form_id,
    schema: data.schema,
    instructions: data.instructions,
  };

  return {
    content: [{ type: 'text', text: JSON.stringify(result) }],
  };
}
