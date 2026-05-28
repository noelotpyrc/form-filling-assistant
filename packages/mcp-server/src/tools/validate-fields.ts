import type { ValidateResponse } from '@form-filling-assistant/shared';
import { getSession } from '../session-manager.js';
import { authenticatedFetch } from '../http-client.js';

export const validateFieldsDefinition = {
  name: 'validate_fields',
  description:
    'Validates one or more field values against the website\'s form constraints. ' +
    'Use this to check field values before submitting a draft.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      fields: {
        type: 'array',
        description: 'Array of field values to validate.',
        items: {
          type: 'object',
          properties: {
            field_id: {
              type: 'string',
              description: 'The field identifier from the form schema.',
            },
            value: {
              description: 'The value to validate for this field.',
            },
          },
          required: ['field_id', 'value'],
        },
      },
    },
    required: ['session_id', 'fields'],
  },
};

export async function handleValidateFields(args: {
  session_id: string;
  fields: Array<{ field_id: string; value: unknown }>;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, fields } = args;

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

  const url = `${session.base_url}/validate`;

  try {
    const result = await authenticatedFetch(session_id, url, {
      method: 'POST',
      body: JSON.stringify({
        form_id: session.form_id,
        fields,
      }),
    });

    if (!result.ok) {
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              error: `Validation request failed with status ${result.status}`,
              details: result.data,
            }),
          },
        ],
      };
    }

    const response = result.data as ValidateResponse;
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
