/**
 * Client-side validation for form fields.
 *
 * Schema-generic — works with any form JSON loaded from /forms/*.json.
 * No hardcoded field IDs; all conditional logic uses the schema's `condition` property.
 */

// ── Regex patterns ──────────────────────────────────────────────────────────
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DATE_FULL_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const DATE_MONTH_REGEX = /^\d{4}-\d{2}$/;
const PHONE_REGEX = /^\+\d{1,4}[\s\-]?\d[\d\s\-]{5,}$/;

// ── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Find a field definition in the schema, including group sub-fields.
 * @param {object} schema - The form schema ({ sections: [...] })
 * @param {string} fieldId - Top-level field_id or group sub-field id
 * @returns {{ field: object, section: object } | null}
 */
function findFieldDef(schema, fieldId) {
  for (const section of schema.sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId) {
        return { field, section };
      }
      if (field.type === 'group' && field.fields) {
        for (const subField of field.fields) {
          if (
            subField.field_id === fieldId ||
            `${field.field_id}.${subField.field_id}` === fieldId
          ) {
            return { field: subField, section };
          }
        }
      }
    }
  }
  return null;
}

/**
 * Get a field value from the data object.
 * Data can be flat ({ full_name: "..." }) or section-keyed ({ personal: { full_name: "..." } }).
 */
function getFieldValue(fieldId, allData) {
  // Check section-keyed data
  for (const key of Object.keys(allData)) {
    const sectionData = allData[key];
    if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      const val = sectionData[fieldId];
      if (val !== undefined) return val;
    }
  }
  // Check flat
  if (allData[fieldId] !== undefined) return allData[fieldId];
  return undefined;
}

/**
 * Check if a schema condition is met.
 */
function isConditionMet(conditionFieldId, operator, conditionValue, allData) {
  const actual = getFieldValue(conditionFieldId, allData);

  switch (operator) {
    case 'equals':
      return actual === conditionValue;
    case 'not_equals':
      return actual !== conditionValue;
    case 'in':
      return Array.isArray(conditionValue) && conditionValue.includes(actual);
    case 'not_in':
      return Array.isArray(conditionValue) && !conditionValue.includes(actual);
    case 'greater_than':
      return typeof actual === 'number' && typeof conditionValue === 'number' && actual > conditionValue;
    case 'less_than':
      return typeof actual === 'number' && typeof conditionValue === 'number' && actual < conditionValue;
    default:
      return true;
  }
}

// ── Single-field validation ─────────────────────────────────────────────────

/**
 * Validate a single field value against its schema definition.
 * @param {object} field - The field definition from the schema
 * @param {*} value - The value to validate
 * @returns {{ valid: boolean, error?: string }}
 */
function validateFieldValue(field, value) {
  // Empty check
  if (value === null || value === undefined || value === '') {
    if (field.required) {
      return { valid: false, error: `${field.label} is required.` };
    }
    return { valid: true };
  }

  switch (field.type) {
    case 'text':
    case 'textarea': {
      const str = String(value);
      if (field.max_length && str.length > field.max_length) {
        return { valid: false, error: `${field.label} must be at most ${field.max_length} characters.` };
      }
      if (field.min_length && str.length < field.min_length) {
        return { valid: false, error: `${field.label} must be at least ${field.min_length} characters.` };
      }
      return { valid: true };
    }

    case 'email': {
      if (!EMAIL_REGEX.test(String(value))) {
        return { valid: false, error: `${field.label} is not a valid email address.` };
      }
      return { valid: true };
    }

    case 'phone': {
      const phoneStr = String(value);
      if (field.require_country_code && !PHONE_REGEX.test(phoneStr)) {
        return { valid: false, error: `${field.label} must include a country code (e.g., +1-555-0123).` };
      }
      return { valid: true };
    }

    case 'number': {
      const num = typeof value === 'number' ? value : Number(value);
      if (isNaN(num)) {
        return { valid: false, error: `${field.label} must be a valid number.` };
      }
      if (field.min !== undefined && num < field.min) {
        return { valid: false, error: `${field.label} must be at least ${field.min}.` };
      }
      if (field.max !== undefined && num > field.max) {
        return { valid: false, error: `${field.label} must be at most ${field.max}.` };
      }
      if (field.decimal_places !== undefined) {
        const parts = String(num).split('.');
        if (parts[1] && parts[1].length > field.decimal_places) {
          return { valid: false, error: `${field.label} allows at most ${field.decimal_places} decimal places.` };
        }
      }
      return { valid: true };
    }

    case 'date': {
      const dateStr = String(value);
      const fmt = field.format || 'YYYY-MM-DD';
      if (fmt === 'YYYY-MM' && !DATE_MONTH_REGEX.test(dateStr)) {
        return { valid: false, error: `${field.label} must be in YYYY-MM format.` };
      }
      if (fmt === 'YYYY-MM-DD' && !DATE_FULL_REGEX.test(dateStr)) {
        return { valid: false, error: `${field.label} must be in YYYY-MM-DD format.` };
      }
      return { valid: true };
    }

    case 'select': {
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((o) => (typeof o === 'string' ? o : o.value));
        if (!validValues.includes(String(value))) {
          return { valid: false, error: `${field.label}: "${value}" is not a valid option. Valid: ${validValues.join(', ')}.` };
        }
      }
      return { valid: true };
    }

    case 'multi_select': {
      if (!Array.isArray(value)) {
        return { valid: false, error: `${field.label} must be an array of values.` };
      }
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((o) => (typeof o === 'string' ? o : o.value));
        for (const v of value) {
          if (!validValues.includes(String(v))) {
            return { valid: false, error: `${field.label}: "${v}" is not a valid option.` };
          }
        }
      }
      if (field.max_selections && value.length > field.max_selections) {
        return { valid: false, error: `${field.label} allows at most ${field.max_selections} selections.` };
      }
      return { valid: true };
    }

    case 'boolean': {
      if (typeof value !== 'boolean') {
        return { valid: false, error: `${field.label} must be true or false.` };
      }
      return { valid: true };
    }

    case 'file': {
      // File uploads are handled by the frontend separately
      return { valid: true };
    }

    case 'group': {
      // Groups are validated via their sub-fields — not directly
      return { valid: true };
    }

    default:
      return { valid: true };
  }
}

// ── Schema-aware validation ─────────────────────────────────────────────────

/**
 * Validate a single field by ID within a schema, respecting conditions.
 * @param {object} schema - Form schema
 * @param {string} fieldId - The field_id to validate
 * @param {*} value - The value
 * @param {object} allData - All current form data
 * @returns {{ field_id: string, valid: boolean, error?: string }}
 */
function validateField(schema, fieldId, value, allData) {
  const found = findFieldDef(schema, fieldId);
  if (!found) {
    return { field_id: fieldId, valid: false, error: `Unknown field: ${fieldId}` };
  }

  const { field } = found;

  // If field has a condition, check if it applies
  if (field.condition) {
    const met = isConditionMet(field.condition.field_id, field.condition.operator, field.condition.value, allData);
    if (!met) {
      return { field_id: fieldId, valid: true }; // Condition not met, skip validation
    }
  }

  const result = validateFieldValue(field, value);
  return { field_id: fieldId, ...result };
}

/**
 * Get all required fields given the current form data and schema conditions.
 * Uses only the schema's `condition` property — no hardcoded field IDs.
 * @param {object} schema - Form schema
 * @param {object} allData - Current form data
 * @returns {string[]} Array of required field_ids
 */
function getRequiredFields(schema, allData) {
  const required = [];

  for (const section of schema.sections) {
    for (const field of section.fields) {
      // Check if field's condition is met
      let applies = true;
      if (field.condition) {
        applies = isConditionMet(
          field.condition.field_id,
          field.condition.operator,
          field.condition.value,
          allData,
        );
      }

      if (!applies) continue;

      if (field.type === 'group') {
        if (field.required) {
          required.push(field.field_id);
        }
        // Don't enumerate sub-fields here — they're validated with the group
        continue;
      }

      if (field.required) {
        required.push(field.field_id);
      }
    }
  }

  return required;
}

/**
 * Validate all form data against the schema.
 * @param {object} schema - Form schema
 * @param {object} allData - All form data
 * @returns {{ field_id: string, valid: boolean, error?: string }[]}
 */
function validateAllFields(schema, allData) {
  const errors = [];
  const requiredFields = getRequiredFields(schema, allData);

  for (const fieldId of requiredFields) {
    const value = getFieldValue(fieldId, allData);
    const found = findFieldDef(schema, fieldId);
    if (!found) continue;

    const { field } = found;

    // Group field validation
    if (field.type === 'group') {
      if (!Array.isArray(value) || value.length === 0) {
        if (field.min_items && field.min_items > 0) {
          errors.push({
            field_id: fieldId,
            valid: false,
            error: `At least ${field.min_items} ${field.label} required.`,
          });
        }
        continue;
      }

      if (field.min_items && value.length < field.min_items) {
        errors.push({
          field_id: fieldId,
          valid: false,
          error: `At least ${field.min_items} ${field.label} required.`,
        });
      }
      if (field.max_items && value.length > field.max_items) {
        errors.push({
          field_id: fieldId,
          valid: false,
          error: `At most ${field.max_items} ${field.label} allowed.`,
        });
      }

      // Validate sub-fields of each entry
      if (field.fields) {
        for (let i = 0; i < value.length; i++) {
          const item = value[i];
          for (const subField of field.fields) {
            if (subField.required) {
              const subVal = item ? item[subField.field_id] : undefined;
              const subResult = validateFieldValue(subField, subVal);
              if (!subResult.valid) {
                errors.push({
                  field_id: `${fieldId}[${i}].${subField.field_id}`,
                  valid: false,
                  error: subResult.error || `${subField.label} is required in ${field.label} #${i + 1}.`,
                });
              }
            }
          }
        }
      }
      continue;
    }

    // Scalar field validation
    const result = validateFieldValue(field, value);
    if (!result.valid) {
      errors.push({ field_id: fieldId, ...result });
    } else if (value === undefined || value === null || value === '') {
      errors.push({
        field_id: fieldId,
        valid: false,
        error: `${field.label} is required.`,
      });
    }
  }

  return errors;
}

// ── Preview builder ─────────────────────────────────────────────────────────

/**
 * Format a field value for human-readable display.
 */
function formatValue(field, value) {
  if (value === undefined || value === null || value === '') return '(not provided)';

  switch (field.type) {
    case 'boolean':
      return value === true ? 'Yes' : 'No';
    case 'select': {
      if (field.options) {
        const opt = field.options.find((o) => (typeof o === 'string' ? o === value : o.value === value));
        if (opt) return typeof opt === 'string' ? opt : opt.label;
      }
      return String(value);
    }
    case 'multi_select': {
      if (Array.isArray(value) && field.options) {
        return value
          .map((v) => {
            const opt = field.options.find((o) => (typeof o === 'string' ? o === v : o.value === v));
            return opt ? (typeof opt === 'string' ? opt : opt.label) : String(v);
          })
          .join(', ');
      }
      return String(value);
    }
    case 'file': {
      if (typeof value === 'object' && value !== null && value.filename) {
        return value.filename;
      }
      return String(value);
    }
    case 'group': {
      if (Array.isArray(value)) return `${value.length} item(s)`;
      return String(value);
    }
    default:
      return String(value);
  }
}

/**
 * Build a preview of the form data, organized by sections.
 * @param {object} schema - Form schema
 * @param {object} data - Form data (section-keyed)
 * @returns {{ title: string, fields: { label: string, value: string }[] }[]}
 */
function buildPreview(schema, data) {
  const sections = [];

  for (const section of schema.sections) {
    const sectionData = data[section.section_id];
    if (!sectionData) continue;

    const fields = [];

    for (const field of section.fields) {
      if (field.type === 'group') {
        const groupVal = sectionData[field.field_id];
        if (Array.isArray(groupVal)) {
          for (let i = 0; i < groupVal.length; i++) {
            const item = groupVal[i];
            if (field.fields) {
              for (const subField of field.fields) {
                const subVal = item[subField.field_id];
                if (subVal !== undefined && subVal !== null && subVal !== '') {
                  fields.push({
                    label: `${field.label} #${i + 1} – ${subField.label}`,
                    value: formatValue(subField, subVal),
                  });
                }
              }
            }
          }
        }
      } else {
        const val = sectionData[field.field_id];
        if (val !== undefined && val !== null && val !== '') {
          fields.push({
            label: field.label,
            value: formatValue(field, val),
          });
        }
      }
    }

    if (fields.length > 0) {
      sections.push({ title: section.title, fields });
    }
  }

  return sections;
}

// ── Exports (global for browser, or module) ─────────────────────────────────

if (typeof window !== 'undefined') {
  window.FormValidation = {
    validateFieldValue,
    validateField,
    getRequiredFields,
    validateAllFields,
    buildPreview,
    formatValue,
    findFieldDef,
    getFieldValue,
    isConditionMet,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    validateFieldValue,
    validateField,
    getRequiredFields,
    validateAllFields,
    buildPreview,
    formatValue,
    findFieldDef,
    getFieldValue,
    isConditionMet,
  };
}
