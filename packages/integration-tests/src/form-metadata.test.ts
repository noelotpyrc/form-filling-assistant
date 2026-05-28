import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const FORMS_DIR = path.resolve(import.meta.dirname, '..', '..', 'web-app', 'public', 'forms');

interface FormField {
  field_id: string;
  label: string;
  type: string;
  required?: boolean;
  fields?: FormField[];
  condition?: { field_id: string; operator: string; value: unknown };
  options?: Array<string | { value: string; label: string }>;
  [key: string]: unknown;
}

interface FormSection {
  section_id: string;
  title: string;
  fields: FormField[];
}

interface FormMeta {
  form_id: string;
  name: string;
  schema: { sections: FormSection[] };
  instructions: {
    greeting: string;
    section_order: string[];
    section_guidance: Record<string, { intro: string; notes: string }>;
    general_notes: string[];
  };
}

const EXPECTED_FORMS = [
  'masters-northfield.json',
  'masters-westbrook.json',
  'patient-riverside.json',
];

const VALID_FIELD_TYPES = [
  'text', 'textarea', 'email', 'phone', 'number', 'date',
  'select', 'multi_select', 'boolean', 'file', 'group',
];

const VALID_OPERATORS = ['equals', 'not_equals', 'in', 'not_in', 'greater_than', 'less_than'];

describe('Form Metadata JSON files', () => {
  it('all expected form files exist', () => {
    for (const file of EXPECTED_FORMS) {
      const filePath = path.join(FORMS_DIR, file);
      expect(fs.existsSync(filePath), `Missing form file: ${file}`).toBe(true);
    }
  });

  for (const file of EXPECTED_FORMS) {
    describe(file, () => {
      let form: FormMeta;

      it('is valid JSON', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;
        expect(form).toBeDefined();
      });

      it('has required top-level fields', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        expect(form.form_id).toBeTypeOf('string');
        expect(form.form_id.length).toBeGreaterThan(0);
        expect(form.name).toBeTypeOf('string');
        expect(form.name.length).toBeGreaterThan(0);
        expect(form.schema).toBeDefined();
        expect(form.schema.sections).toBeInstanceOf(Array);
        expect(form.schema.sections.length).toBeGreaterThan(0);
        expect(form.instructions).toBeDefined();
      });

      it('has valid instructions structure', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        expect(form.instructions.greeting).toBeTypeOf('string');
        expect(form.instructions.section_order).toBeInstanceOf(Array);
        expect(form.instructions.section_order.length).toBeGreaterThan(0);
        expect(form.instructions.section_guidance).toBeTypeOf('object');
        expect(form.instructions.general_notes).toBeInstanceOf(Array);
      });

      it('section_order references valid section_ids', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        const sectionIds = form.schema.sections.map((s) => s.section_id);
        for (const orderedId of form.instructions.section_order) {
          expect(sectionIds, `section_order references unknown section: ${orderedId}`).toContain(orderedId);
        }
      });

      it('section_guidance has entries for all section_order items', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        for (const sectionId of form.instructions.section_order) {
          const guidance = form.instructions.section_guidance[sectionId];
          expect(guidance, `Missing guidance for section: ${sectionId}`).toBeDefined();
          expect(guidance.intro).toBeTypeOf('string');
          expect(guidance.notes).toBeTypeOf('string');
        }
      });

      it('all fields have valid types', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        function checkFields(fields: FormField[], parentPath: string) {
          for (const field of fields) {
            const fieldPath = `${parentPath}.${field.field_id}`;
            expect(VALID_FIELD_TYPES, `Invalid type "${field.type}" at ${fieldPath}`).toContain(field.type);

            if (field.type === 'group' && field.fields) {
              checkFields(field.fields, fieldPath);
            }
          }
        }

        for (const section of form.schema.sections) {
          checkFields(section.fields, section.section_id);
        }
      });

      it('all fields have field_id and label', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        function checkFields(fields: FormField[], parentPath: string) {
          for (const field of fields) {
            expect(field.field_id, `Missing field_id in ${parentPath}`).toBeTypeOf('string');
            expect(field.label, `Missing label for ${parentPath}.${field.field_id}`).toBeTypeOf('string');

            if (field.type === 'group' && field.fields) {
              checkFields(field.fields, `${parentPath}.${field.field_id}`);
            }
          }
        }

        for (const section of form.schema.sections) {
          checkFields(section.fields, section.section_id);
        }
      });

      it('condition operators are valid', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        function checkConditions(fields: FormField[], parentPath: string) {
          for (const field of fields) {
            if (field.condition) {
              const fieldPath = `${parentPath}.${field.field_id}`;
              expect(VALID_OPERATORS, `Invalid operator "${field.condition.operator}" at ${fieldPath}`)
                .toContain(field.condition.operator);
              expect(field.condition.field_id, `Missing condition.field_id at ${fieldPath}`).toBeTypeOf('string');
            }

            if (field.type === 'group' && field.fields) {
              checkConditions(field.fields, `${parentPath}.${field.field_id}`);
            }
          }
        }

        for (const section of form.schema.sections) {
          checkConditions(section.fields, section.section_id);
        }
      });

      it('select/multi_select fields have options', () => {
        const raw = fs.readFileSync(path.join(FORMS_DIR, file), 'utf-8');
        form = JSON.parse(raw) as FormMeta;

        function checkOptions(fields: FormField[], parentPath: string) {
          for (const field of fields) {
            if (field.type === 'select' || field.type === 'multi_select') {
              const fieldPath = `${parentPath}.${field.field_id}`;
              expect(field.options, `Missing options for ${fieldPath}`).toBeInstanceOf(Array);
              expect(field.options!.length, `Empty options for ${fieldPath}`).toBeGreaterThan(0);
            }

            if (field.type === 'group' && field.fields) {
              checkOptions(field.fields, `${parentPath}.${field.field_id}`);
            }
          }
        }

        for (const section of form.schema.sections) {
          checkOptions(section.fields, section.section_id);
        }
      });
    });
  }
});
