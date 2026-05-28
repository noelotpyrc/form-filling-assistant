import { deleteDumps } from '../vault/vault-manager.js';

export const vaultDeleteDefinition = {
  name: 'vault_delete',
  description:
    'Delete one or more saved form submissions from the local vault.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      ids: {
        type: 'array',
        items: { type: 'string' },
        description: 'Vault entry IDs to delete.',
      },
    },
    required: ['ids'],
  },
};

export async function handleVaultDelete(args: {
  ids: string[];
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  try {
    const result = deleteDumps(args.ids);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result),
        },
      ],
    };
  } catch (err) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to delete from vault: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
