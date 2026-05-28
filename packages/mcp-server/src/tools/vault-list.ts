import { listEntries, getActiveProfileId } from '../vault/vault-manager.js';

export const vaultListDefinition = {
  name: 'vault_list',
  description:
    'List all saved form submissions in the local vault. ' +
    'Returns metadata (description, data categories, source URL, date) for each entry — not the actual data. ' +
    'Call this after discover_form to check if any past submissions contain data relevant to the current form.',
  inputSchema: {
    type: 'object' as const,
    properties: {},
  },
};

export async function handleVaultList(): Promise<{
  content: Array<{ type: 'text'; text: string }>;
}> {
  try {
    const entries = listEntries();
    const activeProfileId = getActiveProfileId();
    const activeEntry = activeProfileId
      ? entries.find((e) => e.id === activeProfileId) ?? null
      : null;

    const result = {
      entries: entries.map((e) => ({
        id: e.id,
        description: e.description,
        data_summary: e.data_summary,
        created_at: e.created_at,
        status: e.status,
        source_url: e.source_url,
        is_merged: !!e.is_merged,
        is_profile: !!e.is_profile,
      })),
      active_profile: activeEntry
        ? {
            id: activeEntry.id,
            description: activeEntry.description,
            data_summary: activeEntry.data_summary,
          }
        : null,
    };

    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
    };
  } catch (err) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `Failed to list vault entries: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
