import {
  saveProfile,
  setActiveProfileId,
  getActiveProfileId,
} from '../vault/vault-manager.js';

export const vaultSetProfileDefinition = {
  name: 'vault_set_profile',
  description:
    'Build, activate, or clear the active vault profile. A profile is a unified personal data record ' +
    'synthesized from multiple vault entries across different websites. When active, the AI automatically ' +
    'uses profile data for new forms.\n\n' +
    'Usage modes:\n' +
    '1. BUILD: Provide source_ids, data, and description to create a new profile from existing vault entries. ' +
    'The AI should first vault_load the source entries, intelligently merge/reconcile the data, then call ' +
    'this tool with the synthesized result.\n' +
    '2. ACTIVATE: Provide just id to set an existing profile entry as active.\n' +
    '3. CLEAR: Omit id (or pass null) to deactivate the current profile.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      id: {
        type: 'string',
        description:
          'For ACTIVATE mode: vault entry ID of an existing profile to set as active. ' +
          'Omit or null to CLEAR the active profile. ' +
          'Ignored when source_ids + data are provided (BUILD mode).',
      },
      source_ids: {
        type: 'array',
        items: { type: 'string' },
        description:
          'For BUILD mode: vault entry IDs that were used to synthesize this profile. ' +
          'Stored as metadata for provenance tracking.',
      },
      data: {
        type: 'object',
        description:
          'For BUILD mode: the synthesized profile data object. Should contain normalized ' +
          'categories like personal, education, work_experience, etc.',
      },
      description: {
        type: 'string',
        description:
          'For BUILD mode: natural-language description of the profile. ' +
          'E.g. "Unified profile for Jane Smith — personal info, education, work experience"',
      },
    },
  },
};

export async function handleVaultSetProfile(args: {
  id?: string;
  source_ids?: string[];
  data?: Record<string, unknown>;
  description?: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  try {
    const { id, source_ids, data, description } = args;

    // BUILD mode: source_ids + data + description provided
    if (source_ids && data && description) {
      const dataSummary = Object.keys(data).map((k) =>
        k.replace(/_/g, ' '),
      );
      const result = saveProfile({
        source_ids,
        data,
        description,
        data_summary: dataSummary,
      });
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              id: result.id,
              file: result.file,
              source_ids,
              active: true,
              message: 'Profile created and set as active.',
            }),
          },
        ],
      };
    }

    // ACTIVATE mode: just id provided
    if (id) {
      setActiveProfileId(id);
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              id,
              active: true,
              message: `Profile ${id} is now active.`,
            }),
          },
        ],
      };
    }

    // CLEAR mode: no args or id is null/undefined
    const previousId = getActiveProfileId();
    setActiveProfileId(null);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            active: false,
            previous_id: previousId,
            message: previousId
              ? 'Active profile cleared.'
              : 'No active profile to clear.',
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
            error: `Failed to set profile: ${(err as Error).message}`,
          }),
        },
      ],
    };
  }
}
