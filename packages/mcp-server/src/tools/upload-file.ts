import fs from 'node:fs';
import path from 'node:path';
import type { UploadFileResponse } from '@form-filling-assistant/shared';
import { getSession } from '../session-manager.js';

export const uploadFileDefinition = {
  name: 'upload_file',
  description:
    'Uploads a file from the local filesystem to the website for a specific form field. ' +
    'The user provides the file path through the chat.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      field_id: {
        type: 'string',
        description: 'The form field this file is for (e.g., "transcript").',
      },
      file_path: {
        type: 'string',
        description: 'Local filesystem path to the file to upload.',
      },
    },
    required: ['session_id', 'field_id', 'file_path'],
  },
};

export async function handleUploadFile(args: {
  session_id: string;
  field_id: string;
  file_path: string;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, field_id, file_path } = args;

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

  // Check if file exists
  if (!fs.existsSync(file_path)) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `File not found: ${file_path}. Please check the file path and try again.`,
          }),
        },
      ],
    };
  }

  const url = `${session.base_url}/upload-file`;

  try {
    // Build multipart form data using native FormData (Node 18+)
    const fileBuffer = fs.readFileSync(file_path);
    const blob = new Blob([fileBuffer]);
    const form = new FormData();
    form.append('form_id', session.form_id);
    form.append('field_id', field_id);
    form.append('file', blob, path.basename(file_path));

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${session.auth_token}`,
      },
      body: form,
    });

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
              error: `File upload failed with status ${response.status}`,
              details: errorBody,
            }),
          },
        ],
      };
    }

    const data = (await response.json()) as UploadFileResponse;

    const result = {
      file_id: data.file_id,
      field_id: data.field_id,
      filename: data.filename,
      status: data.status,
    };

    return {
      content: [{ type: 'text', text: JSON.stringify(result) }],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error';
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `File upload error: ${message}`,
          }),
        },
      ],
    };
  }
}
