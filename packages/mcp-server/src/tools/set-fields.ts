import { getSession } from '../session-manager.js';
import type { FormField, FormSection } from '@form-filling-assistant/shared';

export const setFieldsDefinition = {
  name: 'set_fields',
  description:
    'Set multiple form field values at once. Use this to fill form fields with data extracted ' +
    'from documents, vault entries, or user input. Values are validated against the form schema. ' +
    'The web UI form panel updates in real-time when this tool is called. ' +
    'For group sub-fields, use dot notation: "group_id.entry_index.sub_field_id" ' +
    '(e.g., "degrees.0.institution", "degrees.0.gpa", "jobs.1.employer").',
  inputSchema: {
    type: 'object' as const,
    properties: {
      session_id: {
        type: 'string',
        description: 'Active session ID returned from discover_form.',
      },
      fields: {
        type: 'array',
        description: 'Array of field values to set.',
        items: {
          type: 'object',
          properties: {
            field_id: {
              type: 'string',
              description:
                'The field identifier. For top-level fields: "full_name", "email". ' +
                'For group sub-fields use dot notation: "degrees.0.institution", "jobs.1.employer".',
            },
            value: {
              description: 'The value to set for this field.',
            },
          },
          required: ['field_id', 'value'],
        },
      },
    },
    required: ['session_id', 'fields'],
  },
};

interface SetFieldResult {
  field_id: string;
  value: unknown;
  valid: boolean;
  message?: string;
}

/**
 * Parse a dot-notation field_id like "degrees.0.institution"
 * Returns { groupId, entryIndex, subFieldId } or null if not dot-notation.
 */
function parseDotNotation(
  fieldId: string,
): { groupId: string; entryIndex: number; subFieldId: string } | null {
  const parts = fieldId.split('.');
  if (parts.length === 3) {
    const entryIndex = parseInt(parts[1], 10);
    if (!isNaN(entryIndex)) {
      return { groupId: parts[0], entryIndex, subFieldId: parts[2] };
    }
  }
  return null;
}

/**
 * Find a top-level field definition by its field_id across all sections.
 */
function findTopLevelField(
  sections: FormSection[],
  fieldId: string,
): FormField | undefined {
  for (const section of sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId) return field;
    }
  }
  return undefined;
}

/**
 * Find a field definition by its field_id across all sections.
 * Supports dot-notation for group sub-fields (e.g., "degrees.0.institution").
 * Also searches inside group fields (one level deep) for plain sub-field IDs.
 */
function findFieldInSchema(
  sections: FormSection[],
  fieldId: string,
): FormField | undefined {
  // Try dot-notation first
  const dotParsed = parseDotNotation(fieldId);
  if (dotParsed) {
    const groupField = findTopLevelField(sections, dotParsed.groupId);
    if (groupField?.type === 'group' && groupField.fields) {
      return groupField.fields.find((f) => f.field_id === dotParsed.subFieldId);
    }
    return undefined;
  }

  // Try top-level match
  const topLevel = findTopLevelField(sections, fieldId);
  if (topLevel) return topLevel;

  // Try searching inside group sub-fields (backward compat)
  for (const section of sections) {
    for (const field of section.fields) {
      if (field.type === 'group' && field.fields) {
        for (const subField of field.fields) {
          if (subField.field_id === fieldId) return subField;
        }
      }
    }
  }
  return undefined;
}

/**
 * Validate a single field value against its schema definition.
 */
function validateFieldValue(
  field: FormField,
  value: unknown,
): { valid: boolean; message?: string } {
  // Null/undefined/empty check
  if (value === null || value === undefined || value === '') {
    if (field.required) {
      return { valid: false, message: `${field.label} is required.` };
    }
    return { valid: true };
  }

  switch (field.type) {
    case 'text':
    case 'email':
    case 'phone':
    case 'textarea': {
      if (typeof value !== 'string') {
        return { valid: false, message: `${field.label} must be a string.` };
      }
      if (field.max_length && value.length > field.max_length) {
        return {
          valid: false,
          message: `${field.label} exceeds max length of ${field.max_length}.`,
        };
      }
      if (field.min_length && value.length < field.min_length) {
        return {
          valid: false,
          message: `${field.label} must be at least ${field.min_length} characters.`,
        };
      }
      if (field.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        return { valid: false, message: `${field.label} is not a valid email.` };
      }
      return { valid: true };
    }

    case 'number': {
      const num = typeof value === 'number' ? value : Number(value);
      if (isNaN(num)) {
        return { valid: false, message: `${field.label} must be a number.` };
      }
      if (field.min !== undefined && num < field.min) {
        return {
          valid: false,
          message: `${field.label} must be at least ${field.min}.`,
        };
      }
      if (field.max !== undefined && num > field.max) {
        return {
          valid: false,
          message: `${field.label} must be at most ${field.max}.`,
        };
      }
      if (field.decimal_places !== undefined) {
        const parts = String(num).split('.');
        if (parts[1] && parts[1].length > field.decimal_places) {
          return {
            valid: false,
            message: `${field.label} allows at most ${field.decimal_places} decimal places.`,
          };
        }
      }
      return { valid: true };
    }

    case 'date': {
      if (typeof value !== 'string') {
        return { valid: false, message: `${field.label} must be a date string.` };
      }
      const format = field.format || 'YYYY-MM-DD';
      if (format === 'YYYY-MM' && !/^\d{4}-\d{2}$/.test(value)) {
        return {
          valid: false,
          message: `${field.label} must be in YYYY-MM format.`,
        };
      }
      if (format === 'YYYY-MM-DD' && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        return {
          valid: false,
          message: `${field.label} must be in YYYY-MM-DD format.`,
        };
      }
      return { valid: true };
    }

    case 'select': {
      if (typeof value !== 'string') {
        return { valid: false, message: `${field.label} must be a string.` };
      }
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((opt) =>
          typeof opt === 'string' ? opt : opt.value,
        );
        if (!validValues.includes(value)) {
          return {
            valid: false,
            message: `${field.label}: "${value}" is not a valid option. Valid options: ${validValues.join(', ')}.`,
          };
        }
      }
      return { valid: true };
    }

    case 'multi_select': {
      if (!Array.isArray(value)) {
        return {
          valid: false,
          message: `${field.label} must be an array of values.`,
        };
      }
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((opt) =>
          typeof opt === 'string' ? opt : opt.value,
        );
        for (const v of value) {
          if (!validValues.includes(v as string)) {
            return {
              valid: false,
              message: `${field.label}: "${v}" is not a valid option.`,
            };
          }
        }
      }
      if (field.max_selections && value.length > field.max_selections) {
        return {
          valid: false,
          message: `${field.label} allows at most ${field.max_selections} selections.`,
        };
      }
      return { valid: true };
    }

    case 'boolean': {
      if (typeof value !== 'boolean') {
        return { valid: false, message: `${field.label} must be true or false.` };
      }
      return { valid: true };
    }

    case 'file': {
      return {
        valid: false,
        message: `${field.label} is a file field. Use upload_file instead.`,
      };
    }

    case 'group': {
      // If someone passes a group field_id directly (without dot notation),
      // guide them to use dot notation instead
      return {
        valid: false,
        message: `${field.label} is a group field. Use dot notation: "${field.field_id}.0.sub_field_id".`,
      };
    }

    default:
      return { valid: true };
  }
}

export async function handleSetFields(args: {
  session_id: string;
  fields: Array<{ field_id: string; value: unknown }>;
}): Promise<{ content: Array<{ type: 'text'; text: string }> }> {
  const { session_id, fields } = args;

  const session = getSession(session_id);

  // If session is missing (e.g., MCP server restarted between turns),
  // still return success — the frontend handles the actual UI update
  // by intercepting the tool_use SSE event directly.
  if (!session || !session.schema || !session.schema.sections) {
    const results: SetFieldResult[] = fields.map(({ field_id, value }) => ({
      field_id,
      value,
      valid: true,
      message: 'Pushed to form panel (schema validation skipped).',
    }));
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            summary: `Set ${fields.length} field(s) in the form panel (schema validation skipped — session was recycled).`,
            set: results,
          }),
        },
      ],
    };
  }

  const results: SetFieldResult[] = [];
  const errors: Array<{ field_id: string; message: string }> = [];

  for (const { field_id, value } of fields) {
    const fieldDef = findFieldInSchema(session.schema.sections, field_id);

    if (!fieldDef) {
      errors.push({
        field_id,
        message: `Field "${field_id}" not found in form schema.`,
      });
      results.push({ field_id, value, valid: false, message: `Unknown field.` });
      continue;
    }

    const validation = validateFieldValue(fieldDef, value);
    results.push({
      field_id,
      value,
      valid: validation.valid,
      message: validation.message,
    });

    if (!validation.valid) {
      errors.push({
        field_id,
        message: validation.message || 'Invalid value.',
      });
    }
  }

  const successCount = results.filter((r) => r.valid).length;
  const errorCount = errors.length;

  return {
    content: [
      {
        type: 'text',
        text: JSON.stringify({
          summary: `Set ${successCount} field(s) successfully${errorCount > 0 ? `, ${errorCount} error(s)` : ''}.`,
          set: results,
          errors: errors.length > 0 ? errors : undefined,
        }),
      },
    ],
  };
}
