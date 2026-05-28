/**
 * Tests for the A→U and U→A adapter layers in the scenario simulator.
 *
 * A→U: view-renderer.ts (renderScreenView)
 *   - Takes LLM A output + form state → renders text "screen view" for LLM U
 *
 * U→A: user-action.ts (convertUserActionToAppInput)
 *   - Takes LLM U's structured UserAction → format LLM A expects
 */

import { describe, it, expect } from 'vitest';
import { renderScreenView, type ParsedAction, type FormMeta } from './e2e/simulator/view-renderer.js';
import { convertUserActionToAppInput, type UserAction } from './e2e/simulator/user-action.js';

// ══════════════════════════════════════════════════════════════════════
// TEST FIXTURES
// ══════════════════════════════════════════════════════════════════════

/** Minimal 2-section form schema for testing */
const testFormMeta: FormMeta = {
  name: 'Test Application',
  schema: {
    sections: [
      {
        section_id: 'personal',
        title: 'Personal Information',
        fields: [
          { field_id: 'full_name', label: 'Full Name', type: 'text', required: true },
          { field_id: 'email', label: 'Email', type: 'email', required: true },
          { field_id: 'phone', label: 'Phone', type: 'phone', required: false },
        ],
      },
      {
        section_id: 'education',
        title: 'Education',
        fields: [
          {
            field_id: 'degrees',
            label: 'Degrees',
            type: 'group',
            required: true,
            min_items: 1,
            fields: [
              { field_id: 'institution', label: 'Institution', type: 'text', required: true },
              { field_id: 'gpa', label: 'GPA', type: 'number', required: true },
              { field_id: 'notes', label: 'Notes', type: 'text', required: false },
            ],
          },
        ],
      },
    ],
  },
};

/** Form with conditional fields for testing condition evaluation */
const conditionalFormMeta: FormMeta = {
  name: 'Conditional Test Form',
  schema: {
    sections: [
      {
        section_id: 'main',
        title: 'Main Section',
        fields: [
          { field_id: 'has_work', label: 'Has Work Experience?', type: 'boolean', required: true },
          {
            field_id: 'employer',
            label: 'Employer',
            type: 'text',
            required: true,
            condition: { field_id: 'has_work', operator: 'equals', value: true },
          },
          {
            field_id: 'country',
            label: 'Country',
            type: 'select',
            required: true,
            options: ['US', 'CA', 'UK', 'OTHER'],
          },
          {
            field_id: 'visa_type',
            label: 'Visa Type',
            type: 'text',
            required: true,
            condition: { field_id: 'country', operator: 'not_in', value: ['US', 'CA'] },
          },
        ],
      },
    ],
  },
};

/** Minimal test persona */
const testFormState: Record<string, unknown> = {
  email: 'test@example.com',
  full_name: 'Test User',
};

const testTranscriptFile = {
  filename: 'transcript.pdf',
  content: 'TRANSCRIPT\nStudent: Test User\nGPA: 3.9',
};

// ══════════════════════════════════════════════════════════════════════
// A→U ADAPTER: renderScreenView
// ══════════════════════════════════════════════════════════════════════

describe('A→U Adapter: renderScreenView', () => {
  describe('assistant message rendering', () => {
    it('renders assistant text in the screen view', () => {
      const view = renderScreenView(
        'Hello! Welcome to the application.',
        [],
        testFormMeta,
        {},
      );

      expect(view).toContain('## Assistant Message');
      expect(view).toContain('Hello! Welcome to the application.');
    });

    it('trims whitespace from assistant text', () => {
      const view = renderScreenView(
        '  \n  Hello!  \n  ',
        [],
        testFormMeta,
        {},
      );

      expect(view).toContain('Hello!');
      // Should not start with extra whitespace after the header
      const lines = view.split('\n');
      const msgIdx = lines.indexOf('## Assistant Message');
      expect(lines[msgIdx + 1]).toBe('Hello!');
    });
  });

  describe('form panel progress', () => {
    it('shows 0 progress when form is empty', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {});

      expect(view).toContain('## Form Panel');
      expect(view).toContain('Overall progress: 0/');
      expect(view).toContain('(0%)');
      expect(view).toContain('- Personal Information: 0/2');
      // Education group: 1 required entry with 2 required sub-fields (institution, gpa)
      // But 0 entries exist, so we count min_items=1 worth of required sub-fields
      expect(view).toContain('- Education: 0/2');
    });

    it('counts filled top-level fields', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {
        full_name: 'Jane Smith',
        email: 'jane@email.com',
      });

      expect(view).toContain('- Personal Information: 2/2 ✓');
    });

    it('counts filled group entry sub-fields', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {
        'degrees-0-institution': 'MIT',
        'degrees-0-gpa': 3.85,
      });

      expect(view).toContain('- Education: 2/2 ✓');
    });

    it('counts multiple group entries separately', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {
        'degrees-0-institution': 'MIT',
        'degrees-0-gpa': 3.85,
        'degrees-1-institution': 'Stanford',
        // degrees-1-gpa missing
      });

      // 2 entries × 2 required sub-fields = 4 required; 3 filled
      expect(view).toContain('- Education: 3/4');
    });

    it('computes overall percentage', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {
        full_name: 'Jane',
        email: 'jane@email.com',
        'degrees-0-institution': 'MIT',
        'degrees-0-gpa': 3.85,
      });

      // 4 filled / 4 required = 100%
      expect(view).toContain('Overall progress: 4/4 required fields (100%)');
    });

    it('does not count optional fields as required', () => {
      const view = renderScreenView('Hi', [], testFormMeta, {
        phone: '+1-555-0123', // optional — should not affect required count
      });

      // Still 0/4 because phone is not required
      expect(view).toContain('Overall progress: 0/');
    });
  });

  describe('conditional field progress', () => {
    it('skips conditional fields when condition not met', () => {
      // has_work = false, so employer is not required
      const view = renderScreenView('Hi', [], conditionalFormMeta, {
        has_work: false,
        country: 'US',
      });

      // has_work (required) + country (required) = 2 required
      // employer skipped (condition not met), visa_type skipped (US is in exclusion list)
      expect(view).toContain('- Main Section: 2/2 ✓');
    });

    it('includes conditional fields when condition is met', () => {
      // has_work = true, so employer becomes required
      const view = renderScreenView('Hi', [], conditionalFormMeta, {
        has_work: true,
        country: 'US',
      });

      // has_work + country + employer = 3 required; 2 filled (missing employer)
      expect(view).toContain('- Main Section: 2/3');
    });

    it('handles not_in condition correctly', () => {
      // country = UK → visa_type becomes required
      const view = renderScreenView('Hi', [], conditionalFormMeta, {
        has_work: false,
        country: 'UK',
      });

      // has_work + country + visa_type = 3 required; 2 filled
      expect(view).toContain('- Main Section: 2/3');
    });
  });

  describe('interactive element rendering', () => {
    it('renders ask_choice options', () => {
      const actions: ParsedAction[] = [
        {
          type: 'ask_choice',
          question: 'Which program?',
          options: [
            { label: 'Computer Science (MS)', value: 'cs' },
            { label: 'Data Science (MS)', value: 'ds' },
          ],
        },
      ];

      const view = renderScreenView('Choose a program:', actions, testFormMeta, {});

      expect(view).toContain('Choice buttons: ["Computer Science (MS)", "Data Science (MS)"]');
    });

    it('renders show_button save_draft', () => {
      const actions: ParsedAction[] = [{ type: 'show_button', button: 'save_draft' }];
      const view = renderScreenView('Ready to save?', actions, testFormMeta, {});

      expect(view).toContain('Button available: "Save Draft"');
    });

    it('renders show_button submit', () => {
      const actions: ParsedAction[] = [{ type: 'show_button', button: 'submit' }];
      const view = renderScreenView('Ready to submit?', actions, testFormMeta, {});

      expect(view).toContain('Button available: "Submit Application"');
    });

    it('renders show_fields section expansion', () => {
      const actions: ParsedAction[] = [{ type: 'show_fields', section: 'Personal Information' }];
      const view = renderScreenView('Let\'s start with your info.', actions, testFormMeta, {});

      expect(view).toContain('Form section "Personal Information" is open with fields: Full Name, Email, Phone');
    });

    it('resolves show_fields by section_id', () => {
      const actions: ParsedAction[] = [{ type: 'show_fields', section: 'education' }];
      const view = renderScreenView('Education next.', actions, testFormMeta, {});

      expect(view).toContain('Form section "Education" is open with fields: Institution, GPA, Notes');
    });

    it('renders show_preview summary card', () => {
      const actions: ParsedAction[] = [
        {
          type: 'show_preview',
          title: 'Summary',
          sections: [
            {
              title: 'Personal',
              fields: [
                { label: 'Name', value: 'Jane Smith' },
                { label: 'Email', value: 'jane@email.com' },
              ],
            },
          ],
        },
      ];

      const view = renderScreenView('Here is your summary.', actions, testFormMeta, {});

      expect(view).toContain('Preview card: Personal — Name: Jane Smith, Email: jane@email.com');
    });

    it('does not add extra text for set_fields actions', () => {
      const actions: ParsedAction[] = [
        {
          type: 'set_fields',
          fields: [{ field_id: 'full_name', value: 'Jane Smith' }],
        },
      ];

      const view = renderScreenView('Saved your name.', actions, testFormMeta, {
        full_name: 'Jane Smith',
      });

      // set_fields should not generate any additional text beyond progress
      expect(view).not.toContain('set_fields');
      expect(view).not.toContain('field_id');
    });

    it('renders multiple actions in one turn', () => {
      const actions: ParsedAction[] = [
        {
          type: 'set_fields',
          fields: [{ field_id: 'full_name', value: 'Jane' }],
        },
        {
          type: 'ask_choice',
          question: 'Program?',
          options: [{ label: 'CS', value: 'cs' }],
        },
        { type: 'show_button', button: 'save_draft' },
      ];

      const view = renderScreenView('Done! What next?', actions, testFormMeta, {
        full_name: 'Jane',
      });

      expect(view).toContain('Choice buttons: ["CS"]');
      expect(view).toContain('Button available: "Save Draft"');
    });
  });

  describe('full screen view structure', () => {
    it('produces a complete screen view with all sections', () => {
      const actions: ParsedAction[] = [
        {
          type: 'ask_choice',
          options: [{ label: 'Yes', value: 'yes' }, { label: 'No', value: 'no' }],
        },
      ];

      const view = renderScreenView(
        'Do you have work experience?',
        actions,
        testFormMeta,
        { full_name: 'Jane', email: 'jane@email.com' },
      );

      // Verify overall structure
      const lines = view.split('\n');
      expect(lines[0]).toBe('## Assistant Message');
      expect(lines[1]).toBe('Do you have work experience?');
      expect(lines[2]).toBe('');
      expect(lines[3]).toBe('## Form Panel');
      expect(lines[4]).toMatch(/^Overall progress:/);

      // Choice buttons appear after the form panel
      expect(view).toContain('Choice buttons: ["Yes", "No"]');
    });
  });
});

// ══════════════════════════════════════════════════════════════════════
// U→A ADAPTER: convertUserActionToAppInput
// ══════════════════════════════════════════════════════════════════════

describe('U→A Adapter: convertUserActionToAppInput', () => {
  describe('message action', () => {
    it('converts plain text message', () => {
      const action: UserAction = { action: 'message', text: "Hi, I'm Jane Smith." };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBe("Hi, I'm Jane Smith.");
      expect(result.formState).toEqual(testFormState);
      expect(result.stop).toBe(false);
    });

    it('wraps file content in [File:] markers', () => {
      const action: UserAction = {
        action: 'message',
        text: "Here's my transcript.",
        file: testTranscriptFile,
      };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toContain('[File: transcript.pdf]');
      expect(result.userMessage).toContain('TRANSCRIPT\nStudent: Test User\nGPA: 3.9');
      expect(result.userMessage).toContain('[End of transcript.pdf]');
      expect(result.userMessage).toContain("Here's my transcript.");
    });

    it('file content comes before user text', () => {
      const action: UserAction = {
        action: 'message',
        text: 'See above.',
        file: testTranscriptFile,
      };
      const result = convertUserActionToAppInput(action, testFormState);

      const fileIdx = result.userMessage!.indexOf('[File:');
      const textIdx = result.userMessage!.indexOf('See above.');
      expect(fileIdx).toBeLessThan(textIdx);
    });

    it('handles message with no file', () => {
      const action: UserAction = {
        action: 'message',
        text: 'Hello',
      };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBe('Hello');
      expect(result.userMessage).not.toContain('[File:');
    });

    it('handles empty text', () => {
      const action: UserAction = { action: 'message', text: '' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBe('');
    });

    it('handles missing text property', () => {
      const action: UserAction = { action: 'message' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBe('');
    });

    it('does not mutate input form state', () => {
      const state = { email: 'test@example.com' };
      const action: UserAction = { action: 'message', text: 'Hi' };
      const result = convertUserActionToAppInput(action, state);

      expect(result.formState).toEqual(state);
      expect(result.formState).toBe(state); // same reference (no mutation needed)
    });
  });

  describe('select_choice action', () => {
    it('converts to system event format', () => {
      const action: UserAction = { action: 'select_choice', label: 'Computer Science (MS)' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBe('[system] User selected option: "Computer Science (MS)"');
      expect(result.formState).toEqual(testFormState);
      expect(result.stop).toBe(false);
    });
  });

  describe('fill_fields action', () => {
    it('applies field edits to form state with no message', () => {
      const action: UserAction = {
        action: 'fill_fields',
        fields: { phone: '+1-555-0199', email: 'new@email.com' },
      };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBeNull();
      expect(result.formState).toEqual({
        email: 'new@email.com',
        full_name: 'Test User',
        phone: '+1-555-0199',
      });
      expect(result.stop).toBe(false);
    });

    it('does not mutate input form state', () => {
      const state = { email: 'original@example.com' };
      const action: UserAction = {
        action: 'fill_fields',
        fields: { email: 'changed@example.com' },
      };
      const result = convertUserActionToAppInput(action, state);

      expect(state.email).toBe('original@example.com'); // original unchanged
      expect(result.formState).toEqual({ email: 'changed@example.com' }); // copy updated
    });

    it('handles missing fields property', () => {
      const action: UserAction = { action: 'fill_fields' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBeNull();
      expect(result.formState).toEqual(testFormState);
    });
  });

  describe('click_button action', () => {
    it('returns no message (handled by loop controller)', () => {
      const action: UserAction = { action: 'click_button' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBeNull();
      expect(result.formState).toEqual(testFormState);
      expect(result.stop).toBe(false);
    });
  });

  describe('stop action', () => {
    it('returns stop=true', () => {
      const action: UserAction = { action: 'stop' };
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBeNull();
      expect(result.formState).toEqual(testFormState);
      expect(result.stop).toBe(true);
    });
  });

  describe('unknown action', () => {
    it('returns no-op for unknown action type', () => {
      const action = { action: 'unknown_thing' } as unknown as UserAction;
      const result = convertUserActionToAppInput(action, testFormState);

      expect(result.userMessage).toBeNull();
      expect(result.formState).toEqual(testFormState);
      expect(result.stop).toBe(false);
    });
  });
});
