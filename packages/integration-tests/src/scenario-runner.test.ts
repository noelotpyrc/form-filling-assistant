/**
 * Tests for the scenario runner's queue-processing mechanics.
 *
 * These tests exercise the action queue logic (field_edit, show_button response events,
 * ask_choice auto-selection, initialFormValues) without making any API calls.
 * The logic is replicated from run-scenario.ts to keep the runner self-contained.
 */

import { describe, it, expect } from 'vitest';

// ── Types (same as run-scenario.ts) ──

type FieldEdit = { type: 'field_edit'; fields: Record<string, unknown> };
type QueuedAction = string | FieldEdit;

// ── Helpers (same as run-scenario.ts) ──

function makeCompositeId(groupId: string, entryIndex: number, subFieldId: string): string {
  return `${groupId}-${entryIndex}-${subFieldId}`;
}

function applySetFields(
  fields: Array<{ field_id: string; value: unknown }>,
  formValues: Record<string, unknown>,
): Record<string, unknown> {
  const delta: Record<string, unknown> = {};
  for (const { field_id, value } of fields) {
    const dotMatch = field_id.match(/^(.+)\.(\d+)\.(.+)$/);
    const compositeId = dotMatch
      ? makeCompositeId(dotMatch[1], parseInt(dotMatch[2]), dotMatch[3])
      : field_id;
    formValues[compositeId] = value;
    delta[compositeId] = value;
  }
  return delta;
}

/**
 * Simulates the runner's reactive action handler.
 * Given parsed model actions, returns system events to inject into the queue.
 */
function processModelActions(
  parsedActions: Array<{ type: string; [key: string]: unknown }>,
  formValues: Record<string, unknown>,
  preferredValues: Set<string>,
): { injectedEvents: string[]; delta: Record<string, unknown> } {
  const injectedEvents: string[] = [];
  let delta: Record<string, unknown> = {};

  for (const action of parsedActions) {
    // set_fields
    if (action.type === 'set_fields' && Array.isArray(action.fields)) {
      delta = {
        ...delta,
        ...applySetFields(
          action.fields as Array<{ field_id: string; value: unknown }>,
          formValues,
        ),
      };
    }

    // ask_choice → auto-select
    if (action.type === 'ask_choice' && Array.isArray(action.options)) {
      const options = action.options as Array<{ label: string; value: string }>;
      const preferred = options.find((o) => preferredValues.has(o.value));
      const selected = preferred || options[0];
      injectedEvents.push(`[system] User selected option: "${selected.label}"`);
    }

    // show_button → click + API response
    if (action.type === 'show_button' && action.button) {
      if (action.button === 'save_draft') {
        injectedEvents.push(`[system] User clicked: Save Draft`);
        injectedEvents.push(`[system] Draft saved successfully.`);
      } else {
        injectedEvents.push(`[system] User clicked: Submit`);
        injectedEvents.push(`[system] Submission saved. Reference: APP-2026-00001`);
      }
    }
  }

  return { injectedEvents, delta };
}

// ══════════════════════════════════════════════════════════════════════
// TESTS
// ══════════════════════════════════════════════════════════════════════

describe('Scenario Runner: QueuedAction type handling', () => {
  it('string actions are message turns', () => {
    const actions: QueuedAction[] = [
      'Hello, I want to apply',
      '[system] User selected option: "CS"',
    ];

    const messages: string[] = [];
    for (const action of actions) {
      if (typeof action === 'string') {
        messages.push(action);
      }
    }

    expect(messages).toHaveLength(2);
    expect(messages[0]).toBe('Hello, I want to apply');
    expect(messages[1].startsWith('[system]')).toBe(true);
  });

  it('field_edit actions mutate formValues without producing a message', () => {
    const formValues: Record<string, unknown> = { phone: '+1-555-0123' };
    const action: FieldEdit = { type: 'field_edit', fields: { phone: '+1-555-0199' } };

    const editFields = Object.entries(action.fields).map(([field_id, value]) => ({ field_id, value }));
    const delta = applySetFields(editFields, formValues);

    expect(formValues.phone).toBe('+1-555-0199');
    expect(delta).toEqual({ phone: '+1-555-0199' });
  });

  it('field_edit handles group fields with dot notation', () => {
    const formValues: Record<string, unknown> = {};
    const action: FieldEdit = {
      type: 'field_edit',
      fields: { 'degrees.0.gpa': '3.90' },
    };

    const editFields = Object.entries(action.fields).map(([field_id, value]) => ({ field_id, value }));
    applySetFields(editFields, formValues);

    expect(formValues['degrees-0-gpa']).toBe('3.90');
  });

  it('mixed queue processes in correct order', () => {
    const formValues: Record<string, unknown> = { email: 'test@test.com' };
    const actions: QueuedAction[] = [
      'Here is my info',
      { type: 'field_edit', fields: { phone: '555-1234' } },
      'I also updated my phone',
    ];

    const log: Array<{ type: string; value?: string }> = [];

    for (const action of actions) {
      if (typeof action !== 'string') {
        const editFields = Object.entries(action.fields).map(([field_id, value]) => ({ field_id, value }));
        applySetFields(editFields, formValues);
        log.push({ type: 'field_edit' });
      } else {
        log.push({ type: action.startsWith('[system]') ? 'system' : 'user', value: action });
      }
    }

    expect(log).toEqual([
      { type: 'user', value: 'Here is my info' },
      { type: 'field_edit' },
      { type: 'user', value: 'I also updated my phone' },
    ]);
    expect(formValues.phone).toBe('555-1234');
  });
});

describe('Scenario Runner: initialFormValues', () => {
  it('pre-loads form state from scenario', () => {
    const initialFormValues = {
      full_name: 'Jane Smith',
      email: 'jane@test.com',
      'degrees-0-institution': 'MIT',
    };
    const formValues: Record<string, unknown> = { ...initialFormValues };

    expect(formValues.full_name).toBe('Jane Smith');
    expect(formValues.email).toBe('jane@test.com');
    expect(formValues['degrees-0-institution']).toBe('MIT');
  });

  it('defaults to empty when no initialFormValues', () => {
    const formValues: Record<string, unknown> = { ...(undefined ?? {}) };
    expect(Object.keys(formValues)).toHaveLength(0);
  });
});

describe('Scenario Runner: show_button response events', () => {
  it('save_draft injects click + success events in order', () => {
    const formValues: Record<string, unknown> = {};
    const { injectedEvents } = processModelActions(
      [{ type: 'show_button', button: 'save_draft' }],
      formValues,
      new Set(),
    );

    expect(injectedEvents).toEqual([
      '[system] User clicked: Save Draft',
      '[system] Draft saved successfully.',
    ]);
  });

  it('submit injects click + reference events in order', () => {
    const formValues: Record<string, unknown> = {};
    const { injectedEvents } = processModelActions(
      [{ type: 'show_button', button: 'submit' }],
      formValues,
      new Set(),
    );

    expect(injectedEvents).toHaveLength(2);
    expect(injectedEvents[0]).toBe('[system] User clicked: Submit');
    expect(injectedEvents[1]).toMatch(/^\[system\] Submission saved\. Reference: APP-2026-/);
  });
});

describe('Scenario Runner: ask_choice auto-selection', () => {
  it('selects preferred option when available', () => {
    const formValues: Record<string, unknown> = {};
    const { injectedEvents } = processModelActions(
      [{
        type: 'ask_choice',
        options: [
          { label: 'Electrical Engineering', value: 'ee' },
          { label: 'Computer Science', value: 'cs' },
        ],
      }],
      formValues,
      new Set(['cs']),
    );

    expect(injectedEvents).toEqual(['[system] User selected option: "Computer Science"']);
  });

  it('falls back to first option when no preferred match', () => {
    const formValues: Record<string, unknown> = {};
    const { injectedEvents } = processModelActions(
      [{
        type: 'ask_choice',
        options: [
          { label: 'Spring 2026', value: 'spring_2026' },
          { label: 'Fall 2026', value: 'fall_2026' },
        ],
      }],
      formValues,
      new Set(['winter_2027']),
    );

    expect(injectedEvents).toEqual(['[system] User selected option: "Spring 2026"']);
  });
});

describe('Scenario Runner: set_fields from model', () => {
  it('applies set_fields to formValues and returns delta', () => {
    const formValues: Record<string, unknown> = {};
    const { delta } = processModelActions(
      [{
        type: 'set_fields',
        fields: [
          { field_id: 'full_name', value: 'Jane Smith' },
          { field_id: 'degrees.0.institution', value: 'MIT' },
        ],
      }],
      formValues,
      new Set(),
    );

    expect(formValues.full_name).toBe('Jane Smith');
    expect(formValues['degrees-0-institution']).toBe('MIT');
    expect(delta).toEqual({
      full_name: 'Jane Smith',
      'degrees-0-institution': 'MIT',
    });
  });
});

describe('Scenario Runner: combined model response', () => {
  it('handles set_fields + ask_choice + show_button in one response', () => {
    const formValues: Record<string, unknown> = {};
    const { injectedEvents, delta } = processModelActions(
      [
        {
          type: 'set_fields',
          fields: [{ field_id: 'email', value: 'jane@test.com' }],
        },
        {
          type: 'ask_choice',
          options: [
            { label: 'Full-time', value: 'full_time' },
            { label: 'Part-time', value: 'part_time' },
          ],
        },
        { type: 'show_button', button: 'save_draft' },
      ],
      formValues,
      new Set(['full_time']),
    );

    // set_fields applied
    expect(formValues.email).toBe('jane@test.com');
    expect(delta.email).toBe('jane@test.com');

    // ask_choice + show_button injected events in order
    expect(injectedEvents).toEqual([
      '[system] User selected option: "Full-time"',
      '[system] User clicked: Save Draft',
      '[system] Draft saved successfully.',
    ]);
  });
});

describe('Scenario Runner: file attachment format', () => {
  it('file content is just a string message matching [File:] format', () => {
    const fileMessage = '[File: Transcript.pdf]\nStudent: Jane Smith\nGPA: 3.85\n[End of Transcript.pdf]\n\nHere is my transcript.';

    // It's a regular string — no special handling needed
    expect(typeof fileMessage).toBe('string');
    expect(fileMessage.startsWith('[system]')).toBe(false);
    // Runner would treat this as a 'user' role message
    const role = fileMessage.startsWith('[system]') ? 'system' : 'user';
    expect(role).toBe('user');
  });
});
