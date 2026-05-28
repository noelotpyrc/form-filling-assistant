#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  ListToolsRequestSchema,
  CallToolRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import {
  discoverFormDefinition,
  handleDiscoverForm,
} from './tools/discover-form.js';
import {
  validateFieldsDefinition,
  handleValidateFields,
} from './tools/validate-fields.js';
import {
  uploadFileDefinition,
  handleUploadFile,
} from './tools/upload-file.js';
import {
  submitDraftDefinition,
  handleSubmitDraft,
} from './tools/submit-draft.js';
import {
  submitFinalDefinition,
  handleSubmitFinal,
} from './tools/submit-final.js';
import {
  getSessionStatusDefinition,
  handleGetSessionStatus,
} from './tools/get-session-status.js';
import { vaultListDefinition, handleVaultList } from './tools/vault-list.js';
import { vaultLoadDefinition, handleVaultLoad } from './tools/vault-load.js';
import { vaultSaveDefinition, handleVaultSave } from './tools/vault-save.js';
import {
  vaultDeleteDefinition,
  handleVaultDelete,
} from './tools/vault-delete.js';
import {
  vaultMergeDefinition,
  handleVaultMerge,
} from './tools/vault-merge.js';
import {
  vaultSetProfileDefinition,
  handleVaultSetProfile,
} from './tools/vault-set-profile.js';
import { getDraftsDefinition, handleGetDrafts } from './tools/get-drafts.js';
import {
  getSubmissionsDefinition,
  handleGetSubmissions,
} from './tools/get-submissions.js';
import {
  setFieldsDefinition,
  handleSetFields,
} from './tools/set-fields.js';
import {
  showFieldsDefinition,
  handleShowFields,
} from './tools/show-fields.js';

// All tool definitions for listing
const toolDefinitions = [
  discoverFormDefinition,
  validateFieldsDefinition,
  uploadFileDefinition,
  submitDraftDefinition,
  submitFinalDefinition,
  getSessionStatusDefinition,
  // Vault tools
  vaultListDefinition,
  vaultLoadDefinition,
  vaultSaveDefinition,
  vaultDeleteDefinition,
  vaultMergeDefinition,
  vaultSetProfileDefinition,
  // Record retrieval tools
  getDraftsDefinition,
  getSubmissionsDefinition,
  // Form panel tools
  setFieldsDefinition,
  showFieldsDefinition,
];

// Create the MCP server
const server = new Server(
  {
    name: 'form-filling-assistant',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  },
);

// Register the list tools handler
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: toolDefinitions,
  };
});

// Register the call tool handler
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case 'discover_form':
      return handleDiscoverForm(args as { url: string; form_type?: string });

    case 'validate_fields':
      return handleValidateFields(
        args as {
          session_id: string;
          fields: Array<{ field_id: string; value: unknown }>;
        },
      );

    case 'upload_file':
      return handleUploadFile(
        args as {
          session_id: string;
          field_id: string;
          file_path: string;
        },
      );

    case 'submit_draft':
      return handleSubmitDraft(
        args as {
          session_id: string;
          data: Record<string, unknown>;
        },
      );

    case 'submit_final':
      return handleSubmitFinal(args as { session_id: string });

    case 'get_session_status':
      return handleGetSessionStatus(args as { session_id: string });

    // Vault tools
    case 'vault_list':
      return handleVaultList();

    case 'vault_load':
      return handleVaultLoad(args as { ids: string[] });

    case 'vault_save':
      return handleVaultSave(
        args as {
          description: string;
          data_summary: string[];
          source_url: string;
          form_id: string;
          status: 'draft' | 'submitted';
          data: Record<string, unknown>;
        },
      );

    case 'vault_delete':
      return handleVaultDelete(args as { ids: string[] });

    case 'vault_merge':
      return handleVaultMerge(
        args as { ids: string[]; description: string },
      );

    case 'vault_set_profile':
      return handleVaultSetProfile(
        args as {
          id?: string;
          source_ids?: string[];
          data?: Record<string, unknown>;
          description?: string;
        },
      );

    // Record retrieval tools
    case 'get_drafts':
      return handleGetDrafts(
        args as { session_id: string; email?: string },
      );

    case 'get_submissions':
      return handleGetSubmissions(
        args as { session_id: string; email?: string },
      );

    case 'set_fields':
      return handleSetFields(
        args as {
          session_id: string;
          fields: Array<{ field_id: string; value: unknown }>;
        },
      );

    case 'show_fields':
      return handleShowFields(
        args as {
          session_id: string;
          fields: Array<{
            field_id: string;
            entry_index?: number;
            sub_fields?: string[];
          }>;
        },
      );

    default:
      return {
        content: [
          {
            type: 'text' as const,
            text: JSON.stringify({
              error: `Unknown tool: ${name}`,
            }),
          },
        ],
      };
  }
});

// Start the server with stdio transport
async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // The server is now listening on stdin/stdout via the MCP protocol
}

main().catch((err) => {
  console.error('Fatal error starting MCP server:', err);
  process.exit(1);
});
