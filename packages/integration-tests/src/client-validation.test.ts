import { describe, it, expect } from 'vitest';

// Import validation functions by requiring the module (dual-export CJS/browser)
// eslint-disable-next-line @typescript-eslint/no-require-imports
const validation = await import('../../web-app/public/js/validation.js' as string) as {
  validateFieldValue: (field: Record<string, unknown>, value: unknown) => { valid: boolean; error?: string };
  validateField: (schema: Record<string, unknown>, fieldId: string, value: unknown, allData: Record<string, unknown>) => { field_id: string; valid: boolean; error?: string };
  getRequiredFields: (schema: Record<string, unknown>, allData: Record<string, unknown>) => string[];
  validateAllFields: (schema: Record<string, unknown>, allData: Record<string, unknown>) => Array<{ field_id: string; valid: boolean; error?: string }>;
  buildPreview: (schema: Record<string, unknown>, data: Record<string, unknown>) => Array<{ title: string; fields: Array<{ label: string; value: string }> }>;
  formatValue: (field: Record<string, unknown>, value: unknown) => string;
  findFieldDef: (schema: Record<string, unknown>, fieldId: string) => { field: Record<string, unknown>; section: Record<string, unknown> } | null;
  isConditionMet: (condFieldId: string, operator: string, condValue: unknown, allData: Record<string, unknown>) => boolean;
};

const { validateFieldValue, findFieldDef, isConditionMet, getRequiredFields, validateAllFields, buildPreview, formatValue } = validation;

// Simple test schema
const testSchema = {
  sections: [
    {
      section_id: 'personal',
      title: 'Personal Information',
      fields: [
        { field_id: 'full_name', label: 'Full Name', type: 'text', required: true, max_length: 100 },
        { field_id: 'email', label: 'Email', type: 'email', required: true },
        { field_id: 'phone', label: 'Phone', type: 'phone', required: false, require_country_code: true },
        { field_id: 'age', label: 'Age', type: 'number', required: false, min: 0, max: 150 },
        { field_id: 'dob', label: 'Date of Birth', type: 'date', required: true, format: 'YYYY-MM-DD' },
        {
          field_id: 'gender', label: 'Gender', type: 'select', required: false,
          options: [
            { value: 'male', label: 'Male' },
            { value: 'female', label: 'Female' },
          ],
        },
      ],
    },
    {
      section_id: 'program',
      title: 'Program',
      fields: [
        { field_id: 'applied_before', label: 'Applied before?', type: 'boolean', required: true },
        {
          field_id: 'prev_year', label: 'Previous year', type: 'number', required: true,
          min: 2000, max: 2025,
          condition: { field_id: 'applied_before', operator: 'equals', value: true },
        },
        {
          field_id: 'interests', label: 'Research Interests', type: 'multi_select', required: false,
          options: [
            { value: 'ai', label: 'AI' },
            { value: 'ml', label: 'ML' },
            { value: 'nlp', label: 'NLP' },
          ],
          max_selections: 2,
        },
      ],
    },
    {
      section_id: 'education',
      title: 'Education',
      fields: [
        {
          field_id: 'degrees', label: 'Degrees', type: 'group', required: true,
          min_items: 1, max_items: 3,
          fields: [
            { field_id: 'institution', label: 'Institution', type: 'text', required: true },
            { field_id: 'gpa', label: 'GPA', type: 'number', required: true, min: 0, max: 4.0, decimal_places: 2 },
          ],
        },
      ],
    },
  ],
};

describe('Client-side Validation', () => {
  describe('validateFieldValue', () => {
    it('validates required text field — empty string fails', () => {
      const field = { label: 'Name', type: 'text', required: true };
      expect(validateFieldValue(field, '')).toEqual({ valid: false, error: 'Name is required.' });
    });

    it('validates required text field — null fails', () => {
      const field = { label: 'Name', type: 'text', required: true };
      expect(validateFieldValue(field, null)).toEqual({ valid: false, error: 'Name is required.' });
    });

    it('validates optional text field — empty is OK', () => {
      const field = { label: 'Name', type: 'text', required: false };
      expect(validateFieldValue(field, '')).toEqual({ valid: true });
    });

    it('validates text max_length', () => {
      const field = { label: 'Name', type: 'text', max_length: 5 };
      expect(validateFieldValue(field, 'John Smith')).toEqual({
        valid: false,
        error: 'Name must be at most 5 characters.',
      });
    });

    it('validates text min_length', () => {
      const field = { label: 'Bio', type: 'textarea', min_length: 10 };
      expect(validateFieldValue(field, 'Hi')).toEqual({
        valid: false,
        error: 'Bio must be at least 10 characters.',
      });
    });

    it('validates valid email', () => {
      const field = { label: 'Email', type: 'email' };
      expect(validateFieldValue(field, 'john@example.com')).toEqual({ valid: true });
    });

    it('rejects invalid email', () => {
      const field = { label: 'Email', type: 'email' };
      expect(validateFieldValue(field, 'not-an-email')).toEqual({
        valid: false,
        error: 'Email is not a valid email address.',
      });
    });

    it('validates phone with country code', () => {
      const field = { label: 'Phone', type: 'phone', require_country_code: true };
      expect(validateFieldValue(field, '+1-555-123-4567')).toEqual({ valid: true });
    });

    it('rejects phone without country code when required', () => {
      const field = { label: 'Phone', type: 'phone', require_country_code: true };
      expect(validateFieldValue(field, '555-123-4567')).toEqual({
        valid: false,
        error: 'Phone must include a country code (e.g., +1-555-0123).',
      });
    });

    it('validates number in range', () => {
      const field = { label: 'GPA', type: 'number', min: 0, max: 4.0 };
      expect(validateFieldValue(field, 3.5)).toEqual({ valid: true });
    });

    it('rejects number below min', () => {
      const field = { label: 'GPA', type: 'number', min: 0, max: 4.0 };
      expect(validateFieldValue(field, -1)).toEqual({
        valid: false,
        error: 'GPA must be at least 0.',
      });
    });

    it('rejects number above max', () => {
      const field = { label: 'GPA', type: 'number', min: 0, max: 4.0 };
      expect(validateFieldValue(field, 5.0)).toEqual({
        valid: false,
        error: 'GPA must be at most 4.',
      });
    });

    it('rejects number with too many decimal places', () => {
      const field = { label: 'GPA', type: 'number', min: 0, max: 4.0, decimal_places: 1 };
      expect(validateFieldValue(field, 3.555)).toEqual({
        valid: false,
        error: 'GPA allows at most 1 decimal places.',
      });
    });

    it('rejects NaN for number type', () => {
      const field = { label: 'Score', type: 'number' };
      expect(validateFieldValue(field, 'not-a-number')).toEqual({
        valid: false,
        error: 'Score must be a valid number.',
      });
    });

    it('validates date in YYYY-MM-DD format', () => {
      const field = { label: 'DOB', type: 'date', format: 'YYYY-MM-DD' };
      expect(validateFieldValue(field, '1990-01-15')).toEqual({ valid: true });
    });

    it('rejects invalid date format', () => {
      const field = { label: 'DOB', type: 'date', format: 'YYYY-MM-DD' };
      expect(validateFieldValue(field, '01/15/1990')).toEqual({
        valid: false,
        error: 'DOB must be in YYYY-MM-DD format.',
      });
    });

    it('validates date in YYYY-MM format', () => {
      const field = { label: 'Start', type: 'date', format: 'YYYY-MM' };
      expect(validateFieldValue(field, '2020-09')).toEqual({ valid: true });
    });

    it('validates select with valid option', () => {
      const field = {
        label: 'Gender', type: 'select',
        options: [{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }],
      };
      expect(validateFieldValue(field, 'male')).toEqual({ valid: true });
    });

    it('rejects select with invalid option', () => {
      const field = {
        label: 'Gender', type: 'select',
        options: [{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }],
      };
      const result = validateFieldValue(field, 'unknown');
      expect(result.valid).toBe(false);
    });

    it('validates multi_select', () => {
      const field = {
        label: 'Languages', type: 'multi_select', max_selections: 2,
        options: [{ value: 'py', label: 'Python' }, { value: 'js', label: 'JS' }, { value: 'go', label: 'Go' }],
      };
      expect(validateFieldValue(field, ['py', 'js'])).toEqual({ valid: true });
    });

    it('rejects multi_select exceeding max_selections', () => {
      const field = {
        label: 'Languages', type: 'multi_select', max_selections: 2,
        options: [{ value: 'py', label: 'Python' }, { value: 'js', label: 'JS' }, { value: 'go', label: 'Go' }],
      };
      expect(validateFieldValue(field, ['py', 'js', 'go'])).toEqual({
        valid: false,
        error: 'Languages allows at most 2 selections.',
      });
    });

    it('validates boolean type', () => {
      const field = { label: 'Agree', type: 'boolean' };
      expect(validateFieldValue(field, true)).toEqual({ valid: true });
      expect(validateFieldValue(field, false)).toEqual({ valid: true });
    });

    it('rejects non-boolean for boolean type', () => {
      const field = { label: 'Agree', type: 'boolean' };
      expect(validateFieldValue(field, 'yes')).toEqual({
        valid: false,
        error: 'Agree must be true or false.',
      });
    });
  });

  describe('findFieldDef', () => {
    it('finds top-level field', () => {
      const result = findFieldDef(testSchema, 'full_name');
      expect(result).not.toBeNull();
      expect(result!.field.label).toBe('Full Name');
    });

    it('finds group sub-field by qualified name', () => {
      const result = findFieldDef(testSchema, 'degrees.institution');
      expect(result).not.toBeNull();
      expect(result!.field.label).toBe('Institution');
    });

    it('finds group sub-field by bare name', () => {
      const result = findFieldDef(testSchema, 'institution');
      expect(result).not.toBeNull();
      expect(result!.field.label).toBe('Institution');
    });

    it('returns null for unknown field', () => {
      expect(findFieldDef(testSchema, 'nonexistent')).toBeNull();
    });
  });

  describe('isConditionMet', () => {
    it('equals operator — true when matched', () => {
      expect(isConditionMet('applied_before', 'equals', true, { applied_before: true })).toBe(true);
    });

    it('equals operator — false when not matched', () => {
      expect(isConditionMet('applied_before', 'equals', true, { applied_before: false })).toBe(false);
    });

    it('not_equals operator', () => {
      expect(isConditionMet('status', 'not_equals', 'draft', { status: 'submitted' })).toBe(true);
    });

    it('in operator', () => {
      expect(isConditionMet('program', 'in', ['cs', 'ds'], { program: 'cs' })).toBe(true);
      expect(isConditionMet('program', 'in', ['cs', 'ds'], { program: 'mba' })).toBe(false);
    });

    it('not_in operator', () => {
      expect(isConditionMet('program', 'not_in', ['cs', 'ds'], { program: 'mba' })).toBe(true);
    });

    it('works with section-keyed data', () => {
      expect(isConditionMet('applied_before', 'equals', true, { program: { applied_before: true } })).toBe(true);
    });
  });

  describe('getRequiredFields', () => {
    it('returns required fields without conditions', () => {
      const required = getRequiredFields(testSchema, {});
      expect(required).toContain('full_name');
      expect(required).toContain('email');
      expect(required).toContain('dob');
      expect(required).toContain('applied_before');
      expect(required).toContain('degrees');
    });

    it('includes conditional field when condition is met', () => {
      const required = getRequiredFields(testSchema, { applied_before: true });
      expect(required).toContain('prev_year');
    });

    it('excludes conditional field when condition is not met', () => {
      const required = getRequiredFields(testSchema, { applied_before: false });
      expect(required).not.toContain('prev_year');
    });
  });

  describe('validateAllFields', () => {
    it('returns errors for missing required fields', () => {
      const errors = validateAllFields(testSchema, {});
      expect(errors.length).toBeGreaterThan(0);
      const fieldIds = errors.map((e: { field_id: string }) => e.field_id);
      expect(fieldIds).toContain('full_name');
      expect(fieldIds).toContain('email');
    });

    it('validates group sub-fields', () => {
      const data = {
        full_name: 'John',
        email: 'john@test.com',
        dob: '1990-01-01',
        applied_before: false,
        degrees: [{ institution: '', gpa: 5.0 }], // institution empty, gpa out of range
      };
      const errors = validateAllFields(testSchema, data);
      const fieldIds = errors.map((e: { field_id: string }) => e.field_id);
      // Should have errors for empty institution and gpa > 4.0
      expect(fieldIds.some((id: string) => id.includes('institution'))).toBe(true);
      expect(fieldIds.some((id: string) => id.includes('gpa'))).toBe(true);
    });

    it('returns empty array when all required fields are valid', () => {
      const data = {
        full_name: 'John Smith',
        email: 'john@test.com',
        dob: '1990-01-01',
        applied_before: false,
        degrees: [{ institution: 'MIT', gpa: 3.8 }],
      };
      const errors = validateAllFields(testSchema, data);
      expect(errors).toHaveLength(0);
    });
  });

  describe('buildPreview', () => {
    it('builds preview sections from data', () => {
      const data = {
        personal: { full_name: 'John Smith', email: 'john@test.com' },
        program: { applied_before: false },
      };
      const preview = buildPreview(testSchema, data);
      expect(preview.length).toBeGreaterThanOrEqual(1);
      expect(preview[0].title).toBe('Personal Information');
      expect(preview[0].fields.some((f: { label: string }) => f.label === 'Full Name')).toBe(true);
    });

    it('skips sections with no data', () => {
      const data = { personal: { full_name: 'John' } };
      const preview = buildPreview(testSchema, data);
      // Should only have personal section
      const titles = preview.map((s: { title: string }) => s.title);
      expect(titles).not.toContain('Education');
    });
  });

  describe('formatValue', () => {
    it('formats boolean as Yes/No', () => {
      expect(formatValue({ type: 'boolean' }, true)).toBe('Yes');
      expect(formatValue({ type: 'boolean' }, false)).toBe('No');
    });

    it('formats select option label', () => {
      const field = {
        type: 'select',
        options: [{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }],
      };
      expect(formatValue(field, 'male')).toBe('Male');
    });

    it('returns (not provided) for empty values', () => {
      expect(formatValue({ type: 'text' }, undefined)).toBe('(not provided)');
      expect(formatValue({ type: 'text' }, null)).toBe('(not provided)');
      expect(formatValue({ type: 'text' }, '')).toBe('(not provided)');
    });

    it('formats multi_select as comma-separated labels', () => {
      const field = {
        type: 'multi_select',
        options: [{ value: 'ai', label: 'AI' }, { value: 'ml', label: 'ML' }],
      };
      expect(formatValue(field, ['ai', 'ml'])).toBe('AI, ML');
    });
  });
});
