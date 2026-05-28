/**
 * A→U Adapter: View Renderer
 *
 * Converts LLM A's raw output (text + parsed actions) and current form state
 * into a text representation of what the user sees on their screen.
 *
 * This is the ONLY input LLM U receives each turn — it sees what a human
 * would see in the web app's split-panel interface.
 */

import type { FormSchema, FormSection, FormField } from '@form-filling-assistant/shared';

// ── Types ──

/** Parsed action from LLM A's response (output of ActionParser.parseActions) */
export interface ParsedAction {
  type: string;
  [key: string]: unknown;
}

/** Minimal form metadata needed for rendering */
export interface FormMeta {
  name: string;
  schema: FormSchema;
}

// ── Section progress computation ──

interface SectionProgress {
  title: string;
  filled: number;
  required: number;
  complete: boolean;
}

/**
 * Count required fields in a section, respecting conditionals.
 * For group fields, counts based on entries present in formValues.
 */
function countSectionProgress(
  section: FormSection,
  formValues: Record<string, unknown>,
): SectionProgress {
  let required = 0;
  let filled = 0;

  for (const field of section.fields) {
    if (field.type === 'group' && field.fields) {
      const subFields: FormField[] = field.fields;
      // Count group entries present in formValues
      const entryCount = countGroupEntries(field.field_id, formValues);
      const minItems = field.min_items ?? (field.required ? 1 : 0);

      if (minItems > 0 && entryCount === 0) {
        // Need at least one entry but have none — count required sub-fields once
        for (const subField of subFields) {
          if (subField.required) required++;
        }
      } else {
        // Count each existing entry's sub-fields
        for (let i = 0; i < entryCount; i++) {
          for (const sf of subFields) {
            if (!sf.required) continue;
            if (!isConditionMet(sf, formValues)) continue;
            required++;
            const compositeId = `${field.field_id}-${i}-${sf.field_id}`;
            if (hasValue(formValues[compositeId])) filled++;
          }
        }
      }
    } else {
      if (!field.required) continue;
      if (!isConditionMet(field, formValues)) continue;
      required++;
      if (hasValue(formValues[field.field_id])) filled++;
    }
  }

  return {
    title: section.title,
    filled,
    required,
    complete: required > 0 && filled >= required,
  };
}

function countGroupEntries(groupId: string, formValues: Record<string, unknown>): number {
  const prefix = `${groupId}-`;
  let maxIndex = -1;
  for (const key of Object.keys(formValues)) {
    if (key.startsWith(prefix)) {
      const parts = key.slice(prefix.length).split('-');
      const idx = parseInt(parts[0], 10);
      if (!isNaN(idx) && idx > maxIndex) maxIndex = idx;
    }
  }
  return maxIndex + 1;
}

function isConditionMet(field: FormField, formValues: Record<string, unknown>): boolean {
  if (!field.condition) return true;
  const { field_id, operator, value: condValue } = field.condition;
  const actual = formValues[field_id];

  switch (operator) {
    case 'equals':
      return actual === condValue;
    case 'not_equals':
      return actual !== condValue;
    case 'in':
      return Array.isArray(condValue) && condValue.includes(actual as string);
    case 'not_in':
      return Array.isArray(condValue) && !condValue.includes(actual as string);
    default:
      return true;
  }
}

function hasValue(v: unknown): boolean {
  return v !== undefined && v !== null && v !== '';
}

// ── Main renderer ──

/** State context for generating turn-specific nudges */
export interface ScreenViewOptions {
  /** Current turn number */
  turn?: number;
  /** Whether the persona has file attachments available */
  personaHasFiles?: boolean;
  /** Number of completed sections so far */
  completedSections?: number;
  /** Total number of sections */
  totalSections?: number;
  /** Number of consecutive turns with the same intent (for stuck detection) */
  sameIntentStreak?: number;
}

/**
 * Render the user's screen view for a single turn.
 *
 * @param assistantText - The conversational text from LLM A (before ---actions---)
 * @param actions - Parsed actions from LLM A's response
 * @param formMeta - Form name + schema
 * @param formValues - Current form field values (after applying this turn's set_fields)
 * @param options - Optional hints (e.g. available files)
 * @returns Text representation of what the user sees
 */
export function renderScreenView(
  assistantText: string,
  actions: ParsedAction[],
  formMeta: FormMeta,
  formValues: Record<string, unknown>,
  options?: ScreenViewOptions,
): string {
  const parts: string[] = [];

  // ── Always visible: Assistant message ──
  parts.push('## Assistant Message');
  parts.push(assistantText.trim());

  // ── Always visible: Form panel with progress ──
  parts.push('');
  parts.push('## Form Panel');

  const sectionProgress = formMeta.schema.sections.map((s) =>
    countSectionProgress(s, formValues),
  );
  const totalFilled = sectionProgress.reduce((sum, s) => sum + s.filled, 0);
  const totalRequired = sectionProgress.reduce((sum, s) => sum + s.required, 0);
  const pct = totalRequired > 0 ? Math.round((totalFilled / totalRequired) * 100) : 0;

  parts.push(`Overall progress: ${totalFilled}/${totalRequired} required fields (${pct}%)`);
  for (const sp of sectionProgress) {
    const check = sp.complete ? ' ✓' : '';
    parts.push(`- ${sp.title}: ${sp.filled}/${sp.required}${check}`);
  }

  // ── Conditionally visible: interactive elements from actions ──
  for (const action of actions) {
    switch (action.type) {
      case 'ask_choice': {
        const options = action.options as Array<{ label: string }>;
        if (options?.length) {
          parts.push('');
          const labels = options.map((o) => `"${o.label}"`).join(', ');
          parts.push(`Choice buttons: [${labels}]`);
        }
        break;
      }

      case 'show_fields': {
        // Section expanded with fields visible
        const sectionRef = (action.section as string) || '';
        const section = formMeta.schema.sections.find(
          (s) =>
            s.title.toLowerCase() === sectionRef.toLowerCase() ||
            s.section_id.toLowerCase() === sectionRef.toLowerCase(),
        );
        if (section) {
          const fieldLabels = flattenFieldLabels(section.fields);
          parts.push('');
          parts.push(
            `Form section "${section.title}" is open with fields: ${fieldLabels.join(', ')}`,
          );
        }
        break;
      }

      case 'show_button': {
        const button = action.button as string;
        if (button === 'save_draft') {
          parts.push('');
          parts.push('Button available: "Save Draft"');
        } else if (button === 'submit') {
          parts.push('');
          parts.push('Button available: "Submit Application"');
        }
        break;
      }

      case 'show_preview': {
        const sections = action.sections as Array<{
          title: string;
          fields: Array<{ label: string; value: string }>;
        }>;
        if (sections?.length) {
          parts.push('');
          const summaryParts = sections.map((s) => {
            const fieldStrs = s.fields.map((f) => `${f.label}: ${f.value}`).join(', ');
            return `${s.title} — ${fieldStrs}`;
          });
          parts.push(`Preview card: ${summaryParts.join('; ')}`);
        }
        break;
      }

      // set_fields: user sees the effect via progress counters (already reflected above)
      // No additional rendering needed
    }
  }

  // ── Turn-specific nudges ──
  // State-aware hints injected by the middleman based on current progress.
  // These mimic contextual tips a real app would show at specific moments.
  const nudges = generateNudges(formMeta, formValues, sectionProgress, options);
  if (nudges.length > 0) {
    parts.push('');
    parts.push('## 💡 Tip');
    for (const nudge of nudges) {
      parts.push(nudge);
    }
  }

  return parts.join('\n');
}

// ── Nudge generator ──

/**
 * Generate turn-specific nudges based on current form state and progress.
 * Returns at most 1 nudge per turn to avoid overloading the screen view.
 * Nudges are prioritized: file upload > section review > progress check.
 */
function generateNudges(
  formMeta: FormMeta,
  formValues: Record<string, unknown>,
  sectionProgress: SectionProgress[],
  options?: ScreenViewOptions,
): string[] {
  const turn = options?.turn ?? 0;
  const completedSections = sectionProgress.filter((s) => s.complete).length;

  // Don't show nudges on turn 0 (greeting) or turn 1 (first real interaction)
  if (turn < 2) return [];

  // Nudge 1: File upload reminder — show after turn 3 if form has unfilled file fields
  // Generic: the app doesn't know what files the user has
  if (turn >= 3) {
    const fileFields = formMeta.schema.sections
      .flatMap((s) => s.fields)
      .filter((f) => f.type === 'file');
    const hasUnfilledFileFields = fileFields.some((f) => !hasValue(formValues[f.field_id]));
    if (hasUnfilledFileFields) {
      // Only show this once every ~5 turns to avoid nagging
      if (turn === 3 || turn % 5 === 0) {
        return ['You can upload documents (resume, transcript, etc.) anytime — the assistant can extract information from them automatically.'];
      }
    }
  }

  // Nudge 2: Section review — show when a section was just completed
  // (completedSections changed since last turn, which we approximate by checking
  // if any section is exactly at 100% with all fields just filled)
  if (completedSections > 0 && completedSections < sectionProgress.length) {
    const justCompleted = sectionProgress.find(
      (s) => s.complete && s.filled === s.required && s.required > 0,
    );
    if (justCompleted) {
      // Show review nudge at section completion boundaries
      const totalFilled = sectionProgress.reduce((sum, s) => sum + s.filled, 0);
      const totalRequired = sectionProgress.reduce((sum, s) => sum + s.required, 0);
      const pct = totalRequired > 0 ? Math.round((totalFilled / totalRequired) * 100) : 0;
      if (pct > 20 && pct < 90) {
        return [`You've completed the "${justCompleted.title}" section. You can ask to review what's been filled so far.`];
      }
    }
  }

  // Nudge 3: Progress check — show around the halfway point
  if (turn >= 8 && turn % 8 === 0) {
    const totalFilled = sectionProgress.reduce((sum, s) => sum + s.filled, 0);
    const totalRequired = sectionProgress.reduce((sum, s) => sum + s.required, 0);
    const pct = totalRequired > 0 ? Math.round((totalFilled / totalRequired) * 100) : 0;
    if (pct >= 30 && pct <= 80) {
      return [`You're ${pct}% through the form. You can ask the assistant to show a summary of what's been filled.`];
    }
  }

  return [];
}

/** Flatten field labels, handling group sub-fields */
function flattenFieldLabels(fields: FormField[]): string[] {
  const labels: string[] = [];
  for (const f of fields) {
    if (f.type === 'group' && f.fields) {
      for (const sub of f.fields) {
        labels.push(sub.label);
      }
    } else {
      labels.push(f.label);
    }
  }
  return labels;
}
