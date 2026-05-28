import { loadDumps } from '../vault/vault-manager.js';

export const vaultLoadDefinition = {
  name: 'vault_load',
  description:
    'Load one or more saved form submissions by ID. ' +
    'Returns the full raw data for each requested entry so the AI can map it onto the current form fields. ' +
    'Call vault_list first to find relevant entry IDs.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      ids: {
        type: 'array',
        items: { type: 'string' },
        description: 'One or more vault entry IDs to load.',
      },
    },
    required: ['ids'],
  },
};

export async function handleVaultLoad(args: {
  ids: string[];
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { ids } = args;

  if (!ids || ids.length === 0) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({ error: 'No IDs provided. Pass at least one vault entry ID.' }),
        },
      ],
    };
  }

  try {
    const dumps = loadDumps(ids);

    return {
      content: [{ type: 'text', text: JSON.stringify({ dumps }) }],
    };
  } catch (err) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to load vault entries: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
