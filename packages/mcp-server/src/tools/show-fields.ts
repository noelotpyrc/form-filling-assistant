import { getSession } from '../session-manager.js';
import type { FormField, FormSection } from '@form-filling-assistant/shared';

export const showFieldsDefinition = {
  name: 'show_fields',
  description:
    'Show specific form fields in the user\'s form panel. The panel starts empty — ' +
    'use this tool to progressively reveal fields as the conversation progresses. ' +
    'For group fields (repeatable entries like degrees or jobs), specify entry_index to show ' +
    'sub-fields for a specific entry (e.g., entry_index 0 for "Degree #1"). ' +
    'Fields already shown will not be duplicated. Previously completed fields remain visible as compact summaries.',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      fields: {
        type: 'array',
        description: 'Array of fields to show in the form panel.',
        items: {
          type: 'object',
          properties: {
            field_id: {
              type: 'string',
              description:
                'The field identifier from the form schema. For top-level fields, use the field_id directly ' +
                '(e.g., "full_name", "email"). For group fields, use the group field_id (e.g., "degrees", "jobs").',
            },
            entry_index: {
              type: 'number',
              description:
                'For group fields only. The 0-based index of the entry to show ' +
                '(e.g., 0 for "Degree #1", 1 for "Degree #2"). Omit for non-group fields.',
            },
            sub_fields: {
              type: 'array',
              items: { type: 'string' },
              description:
                'For group fields only. Which sub-fields to show for this entry. ' +
                'If omitted, all sub-fields of the group are shown. E.g., ["institution", "degree_type", "gpa"].',
            },
          },
          required: ['field_id'],
        },
      },
    },
    required: ['session_id', 'fields'],
  },
};

interface ShowFieldRequest {
  field_id: string;
  entry_index?: number;
  sub_fields?: string[];
}

interface ShownFieldResult {
  field_id: string;
  entry_index?: number;
  label: string;
  type: string;
  sub_fields_shown?: string[];
}

/**
 * Find a field definition by its field_id across all sections.
 */
function findFieldInSchema(
  sections: FormSection[],
  fieldId: string,
): { field: FormField; section: FormSection } | undefined {
  for (const section of sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId) return { field, section };
    }
  }
  return undefined;
}

export async function handleShowFields(args: {
  session_id: string;
  fields: ShowFieldRequest[];
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, fields } = args;

  const session = getSession(session_id);

  // If session is missing (e.g., MCP server restarted between turns),
  // still return success — the frontend handles the actual UI rendering
  // by intercepting the tool_use SSE event directly.
  if (!session || !session.schema || !session.schema.sections) {
    const shown: ShownFieldResult[] = fields.map((req) => ({
      field_id: req.field_id,
      entry_index: req.entry_index,
      label: req.field_id,
      type: 'unknown',
    }));
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            shown,
            note: 'Fields pushed to form panel (schema validation skipped — session was recycled).',
          }),
        },
      ],
    };
  }

  const shown: ShownFieldResult[] = [];
  const errors: Array<{ field_id: string; message: string }> = [];

  for (const req of fields) {
    const result = findFieldInSchema(session.schema.sections, req.field_id);

    if (!result) {
      errors.push({
        field_id: req.field_id,
        message: `Field "${req.field_id}" not found in form schema.`,
      });
      continue;
    }

    const { field } = result;

    if (field.type === 'group') {
      // Validate entry_index
      const entryIndex = req.entry_index ?? 0;
      if (field.max_items && entryIndex >= field.max_items) {
        errors.push({
          field_id: req.field_id,
          message: `Entry index ${entryIndex} exceeds max_items (${field.max_items}) for "${field.label}".`,
        });
        continue;
      }

      // Validate sub_fields if specified
      const groupSubFields = field.fields || [];
      let subFieldsToShow: string[];

      if (req.sub_fields && req.sub_fields.length > 0) {
        const validSubFieldIds = groupSubFields.map((f) => f.field_id);
        const invalidSubs = req.sub_fields.filter(
          (sf) => !validSubFieldIds.includes(sf),
        );
        if (invalidSubs.length > 0) {
          errors.push({
            field_id: req.field_id,
            message: `Unknown sub-fields: ${invalidSubs.join(', ')}. Valid: ${validSubFieldIds.join(', ')}.`,
          });
          continue;
        }
        subFieldsToShow = req.sub_fields;
      } else {
        // Show all non-file sub-fields by default
        subFieldsToShow = groupSubFields
          .filter((f) => f.type !== 'file')
          .map((f) => f.field_id);
      }

      shown.push({
        field_id: req.field_id,
        entry_index: entryIndex,
        label: `${field.label} #${entryIndex + 1}`,
        type: 'group',
        sub_fields_shown: subFieldsToShow,
      });
    } else if (field.type === 'file') {
      // File fields are handled via chat upload, but we can still show them as informational
      shown.push({
        field_id: req.field_id,
        label: field.label,
        type: 'file',
      });
    } else {
      // Regular field
      shown.push({
        field_id: req.field_id,
        label: field.label,
        type: field.type,
      });
    }
  }

  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify({
          shown,
          errors: errors.length > 0 ? errors : undefined,
        }),
      },
    ],
  };
}
