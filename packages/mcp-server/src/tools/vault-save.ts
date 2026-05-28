import { saveDump } from '../vault/vault-manager.js';

export const vaultSaveDefinition = {
  name: 'vault_save',
  description:
    'Save form data as a new local vault entry for future reuse across different websites. ' +
    'Call this after the user confirms they want to save their submission. ' +
    'The description and data_summary should be written in natural language by the AI.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      description: {
        type: 'string',
        description:
          'Natural-language description of what this submission contains and its purpose. ' +
          'E.g. "Masters application to Northfield University for Jane Smith, CS program, Fall 2026."',
      },
      data_summary: {
        type: 'array',
        items: { type: 'string' },
        description:
          'List of data categories present in this submission. ' +
          'E.g. ["personal info", "education", "work experience", "test scores"]',
      },
      source_url: {
        type: 'string',
        description: 'The URL of the website where this form was submitted.',
      },
      form_id: {
        type: 'string',
        description: 'The form ID returned by discover_form.',
      },
      status: {
        type: 'string',
        enum: ['draft', 'submitted'],
        description: 'Whether this was a draft or a final submission.',
      },
      data: {
        type: 'object',
        description: 'The raw form data object to save.',
      },
    },
    required: ['description', 'data_summary', 'source_url', 'form_id', 'status', 'data'],
  },
};

export async function handleVaultSave(args: {
  description: string;
  data_summary: string[];
  source_url: string;
  form_id: string;
  status: 'draft' | 'submitted';
  data: Record<string, unknown>;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  try {
    const result = saveDump(args);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            id: result.id,
            file: result.file,
            message: 'Form data saved to vault successfully.',
          }),
        },
      ],
    };
  } catch (err) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to save to vault: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
