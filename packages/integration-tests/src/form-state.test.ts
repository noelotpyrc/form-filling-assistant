import { describe, it, expect } from 'vitest';

/**
 * Pure functions extracted from index.html's IIFE.
 * These are the exact implementations from the browser code.
 */

// Composite ID for group sub-fields: "degrees-0-institution"
function makeCompositeId(groupId: string, entryIndex: number, subFieldId: string): string {
  return `${groupId}-${entryIndex}-${subFieldId}`;
}

function parseCompositeId(compositeId: string): { groupId: string; entryIndex: number; subFieldId: string } | null {
  const match = compositeId.match(/^(.+)-(\d+)-(.+)$/);
  if (match) return { groupId: match[1], entryIndex: parseInt(match[2]), subFieldId: match[3] };
  return null;
}

/**
 * Replicates handleSetFields dot-notation conversion from index.html.
 * Takes an array of { field_id, value } and applies them to a formValues object.
 */
function applySetFields(
  fields: Array<{ field_id: string; value: unknown }>,
  formValues: Record<string, unknown>,
): void {
  for (const { field_id, value } of fields) {
    // Parse dot-notation for group sub-fields (same regex as index.html)
    const dotMatch = field_id.match(/^(.+)\.(\d+)\.(.+)$/);
    const compositeId = dotMatch
      ? makeCompositeId(dotMatch[1], parseInt(dotMatch[2]), dotMatch[3])
      : field_id;

    formValues[compositeId] = value;
  }
}

describe('Form State: makeCompositeId', () => {
  it('creates composite ID for degrees entry 0', () => {
    expect(makeCompositeId('degrees', 0, 'institution')).toBe('degrees-0-institution');
  });

  it('creates composite ID for degrees entry 1', () => {
    expect(makeCompositeId('degrees', 1, 'gpa')).toBe('degrees-1-gpa');
  });

  it('creates composite ID for jobs group', () => {
    expect(makeCompositeId('jobs', 1, 'employer')).toBe('jobs-1-employer');
  });
});

describe('Form State: parseCompositeId', () => {
  it('parses a valid composite ID', () => {
    expect(parseCompositeId('degrees-0-institution')).toEqual({
      groupId: 'degrees',
      entryIndex: 0,
      subFieldId: 'institution',
    });
  });

  it('parses composite ID with higher entry index', () => {
    expect(parseCompositeId('jobs-2-employer')).toEqual({
      groupId: 'jobs',
      entryIndex: 2,
      subFieldId: 'employer',
    });
  });

  it('returns null for non-group field ID', () => {
    expect(parseCompositeId('full_name')).toBeNull();
  });

  it('returns null for simple hyphenated field', () => {
    // "some-field" doesn't match the pattern (needs group-N-sub)
    expect(parseCompositeId('some-field')).toBeNull();
  });
});

describe('Form State: applySetFields (dot-notation)', () => {
  it('sets a top-level field', () => {
    const formValues: Record<string, unknown> = {};
    applySetFields([{ field_id: 'full_name', value: 'John Smith' }], formValues);
    expect(formValues['full_name']).toBe('John Smith');
  });

  it('converts dot-notation to composite ID for group sub-field', () => {
    const formValues: Record<string, unknown> = {};
    applySetFields([{ field_id: 'degrees.0.institution', value: 'MIT' }], formValues);
    expect(formValues['degrees-0-institution']).toBe('MIT');
    expect(formValues['degrees.0.institution']).toBeUndefined(); // NOT stored with dots
  });

  it('handles numeric group values', () => {
    const formValues: Record<string, unknown> = {};
    applySetFields([{ field_id: 'degrees.0.gpa', value: 3.8 }], formValues);
    expect(formValues['degrees-0-gpa']).toBe(3.8);
  });

  it('sets multiple fields at once', () => {
    const formValues: Record<string, unknown> = {};
    applySetFields([
      { field_id: 'full_name', value: 'Jane Doe' },
      { field_id: 'email', value: 'jane@test.com' },
      { field_id: 'phone', value: '+1-555-0199' },
    ], formValues);
    expect(Object.keys(formValues)).toHaveLength(3);
    expect(formValues['full_name']).toBe('Jane Doe');
    expect(formValues['email']).toBe('jane@test.com');
    expect(formValues['phone']).toBe('+1-555-0199');
  });

  it('overwrites existing value', () => {
    const formValues: Record<string, unknown> = { full_name: 'John Smith' };
    applySetFields([{ field_id: 'full_name', value: 'John Smythe' }], formValues);
    expect(formValues['full_name']).toBe('John Smythe');
  });

  it('handles mixed top-level and group fields in same call', () => {
    const formValues: Record<string, unknown> = {};
    applySetFields([
      { field_id: 'full_name', value: 'Alice' },
      { field_id: 'degrees.0.institution', value: 'Stanford' },
      { field_id: 'degrees.0.gpa', value: 3.9 },
      { field_id: 'degrees.1.institution', value: 'MIT' },
    ], formValues);
    expect(formValues['full_name']).toBe('Alice');
    expect(formValues['degrees-0-institution']).toBe('Stanford');
    expect(formValues['degrees-0-gpa']).toBe(3.9);
    expect(formValues['degrees-1-institution']).toBe('MIT');
  });
});
