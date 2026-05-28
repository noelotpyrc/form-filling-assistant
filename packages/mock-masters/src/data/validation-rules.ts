import type { FormField, FormSection, ValidationResult } from '@form-filling-assistant/shared';
import { mastersSchema } from './schema.js';

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const DATE_FULL_REGEX = /^\d{4}-\d{2}-\d{2}$/;
const DATE_MONTH_REGEX = /^\d{4}-\d{2}$/;
const PHONE_REGEX = /^\+\d{1,4}[\s\-]?\d[\d\s\-]{5,}$/;

const NON_TOEFL_COUNTRIES = ['US', 'CA', 'UK', 'AU', 'NZ'];
const GRE_OPTIONAL_PROGRAMS = ['cs', 'data_science'];

/**
 * Find a field definition across the schema, including group sub-fields.
 * Returns the field definition and its parent section.
 */
function findFieldDef(fieldId: string): { field: FormField; section: FormSection } | null {
  for (const section of mastersSchema.sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId) {
        return { field, section };
      }
      // Check group sub-fields (e.g., degrees.institution)
      if (field.type === 'group' && field.fields) {
        for (const subField of field.fields) {
          // Match either "group.subfield" or just "subfield" within known groups
          if (subField.field_id === fieldId || `${field.field_id}.${subField.field_id}` === fieldId) {
            return { field: subField, section };
          }
        }
      }
    }
  }
  return null;
}

/**
 * Check if a condition is met given current form data.
 */
function isConditionMet(
  conditionFieldId: string,
  operator: string,
  conditionValue: unknown,
  allData: Record<string, unknown>,
): boolean {
  const actualValue = getFieldValue(conditionFieldId, allData);

  switch (operator) {
    case 'equals':
      return actualValue === conditionValue;
    case 'not_equals':
      return actualValue !== conditionValue;
    case 'in':
      if (Array.isArray(conditionValue)) {
        return conditionValue.includes(actualValue as string);
      }
      return false;
    case 'not_in':
      if (Array.isArray(conditionValue)) {
        return !conditionValue.includes(actualValue as string);
      }
      return false;
    case 'greater_than':
      return typeof actualValue === 'number' && typeof conditionValue === 'number' && actualValue > conditionValue;
    case 'less_than':
      return typeof actualValue === 'number' && typeof conditionValue === 'number' && actualValue < conditionValue;
    default:
      return true;
  }
}

/**
 * Retrieve a field value from the nested data structure.
 */
function getFieldValue(fieldId: string, allData: Record<string, unknown>): unknown {
  // Check top-level across all sections
  for (const sectionKey of Object.keys(allData)) {
    const sectionData = allData[sectionKey];
    if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      const val = (sectionData as Record<string, unknown>)[fieldId];
      if (val !== undefined) return val;
    }
  }
  // Check direct top-level
  if (allData[fieldId] !== undefined) return allData[fieldId];
  return undefined;
}

/**
 * Validate a single field value.
 */
export function validateField(
  fieldId: string,
  value: unknown,
  allData: Record<string, unknown>,
): ValidationResult {
  const result: ValidationResult = { field_id: fieldId, valid: true };
  const found = findFieldDef(fieldId);

  if (!found) {
    return { field_id: fieldId, valid: false, error: `Unknown field: ${fieldId}` };
  }

  const { field } = found;

  // Check if field condition is met (if conditional, check if it applies)
  if (field.condition) {
    const conditionMet = isConditionMet(
      field.condition.field_id,
      field.condition.operator,
      field.condition.value,
      allData,
    );
    if (!conditionMet) {
      // Condition not met, field is not applicable -- skip validation
      return { field_id: fieldId, valid: true };
    }
  }

  // Check required
  if (field.required && (value === undefined || value === null || value === '')) {
    return {
      field_id: fieldId,
      valid: false,
      error: `${field.label} is required.`,
    };
  }

  // If no value provided and not required, it's valid
  if (value === undefined || value === null || value === '') {
    return result;
  }

  // Type-specific validation
  switch (field.type) {
    case 'text':
    case 'textarea': {
      const strVal = String(value);
      if (field.max_length && strVal.length > field.max_length) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be at most ${field.max_length} characters.`,
        };
      }
      if (field.min_length && strVal.length < field.min_length) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be at least ${field.min_length} characters.`,
        };
      }
      break;
    }

    case 'number': {
      const numVal = typeof value === 'number' ? value : parseFloat(String(value));
      if (isNaN(numVal)) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be a valid number.`,
        };
      }
      if (field.min !== undefined && numVal < field.min) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be at least ${field.min}.`,
          suggestion: field.field_id === 'gpa'
            ? "If your institution uses a different scale, select 'Other' for gpa_scale and provide the original value."
            : undefined,
        };
      }
      if (field.max !== undefined && numVal > field.max) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be at most ${field.max}.`,
          suggestion: field.field_id === 'gpa'
            ? "If your institution uses a different scale, select 'Other' for gpa_scale and provide the original value."
            : undefined,
        };
      }
      break;
    }

    case 'email': {
      if (!EMAIL_REGEX.test(String(value))) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be a valid email address.`,
        };
      }
      break;
    }

    case 'phone': {
      if (!PHONE_REGEX.test(String(value))) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must include a country code (e.g., +1-555-0123).`,
        };
      }
      break;
    }

    case 'date': {
      const dateStr = String(value);
      const expectMonthOnly = field.format === 'YYYY-MM';
      if (expectMonthOnly) {
        if (!DATE_MONTH_REGEX.test(dateStr)) {
          return {
            field_id: fieldId,
            valid: false,
            error: `${field.label} must be in YYYY-MM format.`,
          };
        }
      } else {
        if (!DATE_FULL_REGEX.test(dateStr) && !DATE_MONTH_REGEX.test(dateStr)) {
          return {
            field_id: fieldId,
            valid: false,
            error: `${field.label} must be in YYYY-MM-DD format.`,
          };
        }
      }
      break;
    }

    case 'select': {
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((o) =>
          typeof o === 'string' ? o : o.value,
        );
        if (!validValues.includes(String(value))) {
          return {
            field_id: fieldId,
            valid: false,
            error: `${field.label} must be one of: ${validValues.join(', ')}.`,
          };
        }
      }
      break;
    }

    case 'multi_select': {
      if (!Array.isArray(value)) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be an array of selections.`,
        };
      }
      if (field.options && field.options.length > 0) {
        const validValues = field.options.map((o) =>
          typeof o === 'string' ? o : o.value,
        );
        for (const v of value) {
          if (!validValues.includes(String(v))) {
            return {
              field_id: fieldId,
              valid: false,
              error: `Invalid selection "${v}" for ${field.label}.`,
            };
          }
        }
      }
      if (field.max_selections && value.length > field.max_selections) {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} allows at most ${field.max_selections} selections.`,
        };
      }
      break;
    }

    case 'boolean': {
      if (typeof value !== 'boolean') {
        return {
          field_id: fieldId,
          valid: false,
          error: `${field.label} must be true or false.`,
        };
      }
      break;
    }

    case 'file': {
      // File validation is handled by the upload-file endpoint
      break;
    }
  }

  return result;
}

/**
 * Determine which fields are required given the current form data,
 * accounting for conditional logic.
 */
export function getRequiredFields(allData: Record<string, unknown>): string[] {
  const required: string[] = [];

  for (const section of mastersSchema.sections) {
    for (const field of section.fields) {
      if (field.type === 'group') {
        // Group fields: check if the group itself is required / conditional
        let groupApplies = true;
        if (field.condition) {
          groupApplies = isConditionMet(
            field.condition.field_id,
            field.condition.operator,
            field.condition.value,
            allData,
          );
        }
        if (field.required && groupApplies) {
          required.push(field.field_id);
        }
        continue;
      }

      // Check if field condition is met
      let applies = true;
      if (field.condition) {
        applies = isConditionMet(
          field.condition.field_id,
          field.condition.operator,
          field.condition.value,
          allData,
        );
      }

      // Special handling for gre_taken: it becomes required when program is not cs/data_science
      if (field.field_id === 'gre_taken') {
        const program = getFieldValue('program', allData);
        if (program && !GRE_OPTIONAL_PROGRAMS.includes(String(program))) {
          required.push(field.field_id);
        }
        continue;
      }

      // Special handling for toefl_required
      if (field.field_id === 'toefl_required') {
        const citizenship = getFieldValue('country_citizenship', allData);
        if (citizenship && !NON_TOEFL_COUNTRIES.includes(String(citizenship))) {
          required.push(field.field_id);
        }
        continue;
      }

      // Special handling: GRE score fields are required if gre_taken is true
      if (['gre_verbal', 'gre_quant', 'gre_writing', 'gre_date'].includes(field.field_id)) {
        const greTaken = getFieldValue('gre_taken', allData);
        if (greTaken === true) {
          required.push(field.field_id);
        }
        continue;
      }

      // Special handling: English test fields are required if toefl_required is true
      if (['english_test_type', 'english_test_score', 'english_test_date'].includes(field.field_id)) {
        const toeflRequired = getFieldValue('toefl_required', allData);
        if (toeflRequired === true) {
          required.push(field.field_id);
        }
        continue;
      }

      // Special handling: prior_application_year conditional
      if (field.field_id === 'prior_application_year') {
        const priorApp = getFieldValue('prior_application', allData);
        if (priorApp === true) {
          required.push(field.field_id);
        }
        continue;
      }

      // Special handling: funding_type conditional
      if (field.field_id === 'funding_type') {
        const fundingInterest = getFieldValue('funding_interest', allData);
        if (fundingInterest === true) {
          required.push(field.field_id);
        }
        continue;
      }

      if (field.required && applies) {
        required.push(field.field_id);
      }
    }
  }

  return required;
}

/**
 * Validate all fields in the submitted data.
 */
export function validateAllFields(
  allData: Record<string, unknown>,
): ValidationResult[] {
  const errors: ValidationResult[] = [];
  const requiredFields = getRequiredFields(allData);

  for (const fieldId of requiredFields) {
    const value = getFieldValue(fieldId, allData);

    // For group fields, check the array
    if (fieldId === 'degrees' || fieldId === 'recommenders' || fieldId === 'jobs') {
      const found = findFieldDef(fieldId);
      if (!found) continue;
      const { field } = found;

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

      // Validate sub-fields of each item
      if (field.fields) {
        for (let i = 0; i < value.length; i++) {
          const item = value[i] as Record<string, unknown>;
          for (const subField of field.fields) {
            if (subField.required) {
              const subVal = item[subField.field_id];
              const subResult = validateField(subField.field_id, subVal, allData);
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

    const result = validateField(fieldId, value, allData);
    if (!result.valid) {
      errors.push(result);
    } else if (value === undefined || value === null || value === '') {
      errors.push({
        field_id: fieldId,
        valid: false,
        error: `${findFieldDef(fieldId)?.field.label || fieldId} is required.`,
      });
    }
  }

  return errors;
}
