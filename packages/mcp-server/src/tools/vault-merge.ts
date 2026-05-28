import { mergeDumps } from '../vault/vault-manager.js';

export const vaultMergeDefinition = {
  name: 'vault_merge',
  description:
    'Merge multiple vault entries from the same website into a single consolidated entry. ' +
    'Useful for combining partial drafts or successive submissions to the same site. ' +
    'All entries must share the same source_url. Later entries override earlier ones on conflicts.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      ids: {
        type: 'array',
        items: { type: 'string' },
        description: 'Vault entry IDs to merge (minimum 2). Order matters — later IDs override earlier.',
      },
      description: {
        type: 'string',
        description: 'Description for the merged entry.',
      },
    },
    required: ['ids', 'description'],
  },
};

export async function handleVaultMerge(args: {
  ids: string[];
  description: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  try {
    const result = mergeDumps(args.ids, args.description);

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            id: result.id,
            file: result.file,
            merged_from: result.merged_from,
            message: 'Vault entries merged successfully.',
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
            error: `Failed to merge vault entries: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
