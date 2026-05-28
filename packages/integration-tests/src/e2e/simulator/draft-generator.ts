/**
 * Generate a realistic partial draft for "returning user" simulations.
 *
 * Fills complete sections using persona data, leaving some sections empty.
 * The draft looks like a real user who started, filled some sections, and left.
 *
 * Rules:
 * - Fill by section (complete or empty, rarely partial)
 * - Always fill "Program Selection" (users pick this first)
 * - Always leave at least one section empty (otherwise there's nothing to do)
 * - File fields are always empty (files don't persist in drafts)
 * - Group fields use dot notation: "degrees.0.institution", "jobs.0.employer"
 * - Respect conditional fields (only fill if condition is met)
 */

import type { Persona } from './personas.js';

interface FormField {
  field_id: string;
  type: string;
  required?: boolean;
  fields?: FormField[]; // group sub-fields
  condition?: { field_id: string; operator: string; value: unknown };
}

interface FormSection {
  section_id: string;
  title: string;
  fields: FormField[];
}

interface FormSchema {
  sections: FormSection[];
}

/**
 * Generate a partial draft from persona data.
 *
 * @param persona - The persona whose data to use
 * @param schema - The form schema (from form JSON's .schema)
 * @param fillRatio - Target fraction of sections to fill (0.4–0.7). Default 0.5.
 * @param seed - Optional seed for deterministic randomness
 * @returns Partial formValues object
 */
export function generatePartialDraft(
  persona: Persona,
  schema: FormSchema,
  fillRatio = 0.5,
  seed?: number,
): Record<string, unknown> {
  const formValues: Record<string, unknown> = {};

  // Simple seeded random (mulberry32)
  let rngState = seed ?? Date.now();
  function random(): number {
    rngState |= 0;
    rngState = (rngState + 0x6d2b79f5) | 0;
    let t = Math.imul(rngState ^ (rngState >>> 15), 1 | rngState);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  const sections = schema.sections;

  // Decide which sections to fill
  // Always fill "program" section (users pick this first)
  // Never fill "documents" section (files don't persist)
  // Randomly fill others based on fillRatio
  const sectionDecisions: Map<string, boolean> = new Map();
  let filledCount = 0;

  for (const section of sections) {
    if (section.section_id === 'program') {
      sectionDecisions.set(section.section_id, true);
      filledCount++;
    } else if (section.section_id === 'documents') {
      sectionDecisions.set(section.section_id, false);
    } else {
      const fill = random() < fillRatio;
      sectionDecisions.set(section.section_id, fill);
      if (fill) filledCount++;
    }
  }

  // Ensure at least one non-program section is empty
  if (filledCount >= sections.length - 1) {
    // Too many filled — randomly unfill one (not program, not documents)
    const candidates = sections.filter(
      (s) => s.section_id !== 'program' && s.section_id !== 'documents' && sectionDecisions.get(s.section_id),
    );
    if (candidates.length > 0) {
      const idx = Math.floor(random() * candidates.length);
      sectionDecisions.set(candidates[idx].section_id, false);
    }
  }

  // Ensure at least one non-program section IS filled (otherwise draft is too empty)
  const filledNonProgram = sections.filter(
    (s) => s.section_id !== 'program' && sectionDecisions.get(s.section_id),
  );
  if (filledNonProgram.length === 0) {
    // Force-fill "personal" if it exists, otherwise pick randomly
    const personal = sections.find((s) => s.section_id === 'personal');
    if (personal) {
      sectionDecisions.set('personal', true);
    } else {
      const candidates = sections.filter(
        (s) => s.section_id !== 'program' && s.section_id !== 'documents',
      );
      if (candidates.length > 0) {
        const idx = Math.floor(random() * candidates.length);
        sectionDecisions.set(candidates[idx].section_id, true);
      }
    }
  }

  // Fill sections
  for (const section of sections) {
    if (!sectionDecisions.get(section.section_id)) continue;

    for (const field of section.fields) {
      fillField(field, '', persona, formValues, random);
    }
  }

  return formValues;
}

/**
 * Fill a single field from persona data.
 */
function fillField(
  field: FormField,
  prefix: string,
  persona: Persona,
  formValues: Record<string, unknown>,
  random: () => number,
): void {
  const fieldId = prefix ? `${prefix}.${field.field_id}` : field.field_id;

  // Skip file fields (don't persist in drafts)
  if (field.type === 'file') return;

  // Handle group fields
  if (field.type === 'group') {
    const groupEntries = persona.groupData[field.field_id];
    if (!groupEntries || groupEntries.length === 0) return;

    const subFields = field.fields || [];
    for (let i = 0; i < groupEntries.length; i++) {
      const entryData = groupEntries[i];
      for (const subField of subFields) {
        const subKey = `${field.field_id}.${i}.${subField.field_id}`;
        const value = entryData[subField.field_id];
        if (value !== undefined && subField.type !== 'file') {
          formValues[subKey] = value;
        }
      }
    }
    return;
  }

  // Handle conditional fields — check if condition is met
  if (field.condition) {
    const condField = field.condition.field_id;
    const condValue = formValues[condField];
    if (field.condition.operator === 'equals' && condValue !== field.condition.value) {
      return; // Condition not met, skip
    }
  }

  // Regular field — look up in persona data
  const value = persona.data[field.field_id];
  if (value !== undefined) {
    formValues[fieldId] = value;
  }
}

/**
 * Count filled fields in a formValues object.
 */
export function countFilledFields(formValues: Record<string, unknown>): number {
  return Object.keys(formValues).length;
}

/**
 * Get a human-readable summary of which sections are filled.
 */
export function draftSummary(
  formValues: Record<string, unknown>,
  schema: FormSchema,
): string {
  const parts: string[] = [];
  for (const section of schema.sections) {
    const sectionFields = getSectionFieldIds(section);
    const filled = sectionFields.filter((fid) => formValues[fid] !== undefined).length;
    if (filled > 0) {
      parts.push(`${section.title}: ${filled}/${sectionFields.length} fields`);
    }
  }
  return parts.join(', ');
}

function getSectionFieldIds(section: FormSection): string[] {
  const ids: string[] = [];
  for (const field of section.fields) {
    if (field.type === 'group') {
      // Just count the group field itself
      ids.push(field.field_id);
    } else {
      ids.push(field.field_id);
    }
  }
  return ids;
}
