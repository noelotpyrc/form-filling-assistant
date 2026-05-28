/**
 * Tests for the TypeScript action-processor module
 * (packages/integration-tests/src/e2e/simulator/action-processor.ts)
 *
 * These mirror the sim-action-processor.test.ts tests (which test the browser JS version)
 * to ensure the TS port is functionally identical.
 */

import { describe, it, expect } from 'vitest';
import { processActions, buildLlmAMessage } from './e2e/simulator/action-processor.js';

// ══════════════════════════════════════════════════════════════════════
// processActions
// ══════════════════════════════════════════════════════════════════════

describe('processActions (TS)', () => {
  const emptyForm = {};

  // ── Basic single actions ──

  it('returns empty plan for empty actions array', () => {
    const plan = processActions([], emptyForm, null);
    expect(plan.stop).toBe(false);
    expect(plan.fieldEdits).toEqual({});
    expect(plan.messages).toEqual([]);
    expect(plan.clickButton).toBeNull();
  });

  it('returns empty plan for null/undefined actions', () => {
    expect(processActions(null as any, emptyForm, null).messages).toEqual([]);
    expect(processActions(undefined as any, emptyForm, null).messages).toEqual([]);
  });

  it('handles single message action', () => {
    const plan = processActions(
      [{ action: 'message', text: 'Hello, I want to apply' }],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].text).toBe('Hello, I want to apply');
    expect(plan.messages[0].isSystem).toBeUndefined();
    expect(plan.stop).toBe(false);
  });

  it('handles single select_choice action', () => {
    const plan = processActions(
      [{ action: 'select_choice', label: 'Computer Science (MS)' }],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].text).toBe('[system] User selected option: "Computer Science (MS)"');
    expect(plan.messages[0].isSystem).toBe(true);
  });

  it('handles single fill_fields action', () => {
    const plan = processActions(
      [{ action: 'fill_fields', fields: { full_name: 'Jane Smith', email: 'jane@email.com' } }],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({ full_name: 'Jane Smith', email: 'jane@email.com' });
    expect(plan.messages).toHaveLength(0);
  });

  it('handles single click_button with available button', () => {
    const plan = processActions(
      [{ action: 'click_button' }],
      emptyForm,
      'save_draft',
    );
    expect(plan.clickButton).toBe('save_draft');
    expect(plan.messages).toHaveLength(0);
  });

  it('ignores click_button when no button available', () => {
    const plan = processActions(
      [{ action: 'click_button' }],
      emptyForm,
      null,
    );
    expect(plan.clickButton).toBeNull();
  });

  it('handles stop action', () => {
    const plan = processActions(
      [{ action: 'stop' }],
      emptyForm,
      null,
    );
    expect(plan.stop).toBe(true);
  });

  // ── Message with file ──

  it('captures file key on message action', () => {
    const plan = processActions(
      [{ action: 'message', text: 'Here is my transcript', file: 'transcript' }],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].fileKey).toBe('transcript');
    expect(plan.messages[0].text).toBe('Here is my transcript');
  });

  it('ignores non-string file references (already resolved)', () => {
    const plan = processActions(
      [{ action: 'message', text: 'Here is my transcript', file: { filename: 'transcript.pdf', content: '...' } as any }],
      emptyForm,
      null,
    );
    expect(plan.messages[0].fileKey).toBeUndefined();
  });

  // ── Multi-action combos ──

  it('select_choice + message: produces two messages', () => {
    const plan = processActions(
      [
        { action: 'select_choice', label: 'Computer Science (MS)' },
        { action: 'message', text: 'I have a strong background in ML' },
      ],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(2);
    expect(plan.messages[0].text).toBe('[system] User selected option: "Computer Science (MS)"');
    expect(plan.messages[0].isSystem).toBe(true);
    expect(plan.messages[1].text).toBe('I have a strong background in ML');
    expect(plan.messages[1].isSystem).toBeUndefined();
  });

  it('fill_fields + message: accumulates edits and message', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { gpa: '3.85' } },
        { action: 'message', text: 'I updated my GPA' },
      ],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({ gpa: '3.85' });
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].text).toBe('I updated my GPA');
  });

  it('multiple fill_fields: edits are accumulated', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { full_name: 'Jane Smith' } },
        { action: 'fill_fields', fields: { email: 'jane@email.com' } },
      ],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({ full_name: 'Jane Smith', email: 'jane@email.com' });
    expect(plan.messages).toHaveLength(0);
  });

  it('fill_fields with overlapping keys: last wins', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { gpa: '3.5' } },
        { action: 'fill_fields', fields: { gpa: '3.85' } },
      ],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({ gpa: '3.85' });
  });

  // ── Stop interrupts processing ──

  it('stop after other actions: stop takes precedence, prior actions preserved', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { gpa: '3.85' } },
        { action: 'stop' },
        { action: 'message', text: 'this should not appear' },
      ],
      emptyForm,
      null,
    );
    expect(plan.stop).toBe(true);
    expect(plan.fieldEdits).toEqual({ gpa: '3.85' });
    expect(plan.messages).toHaveLength(0);
  });

  // ── Does not mutate input ──

  it('does not mutate the input formState', () => {
    const formState = { full_name: 'Original' };
    const formStateCopy = { ...formState };
    processActions(
      [{ action: 'fill_fields', fields: { full_name: 'Changed', email: 'new@email.com' } }],
      formState,
      null,
    );
    expect(formState).toEqual(formStateCopy);
  });

  // ── Edge cases ──

  it('handles unknown action types gracefully', () => {
    const plan = processActions(
      [
        { action: 'unknown_type' as any, text: 'wat' },
        { action: 'message', text: 'after unknown' },
      ],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].text).toBe('after unknown');
  });

  it('handles fill_fields with no fields property', () => {
    const plan = processActions(
      [{ action: 'fill_fields' }],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({});
  });

  it('handles message with empty text', () => {
    const plan = processActions(
      [{ action: 'message' }],
      emptyForm,
      null,
    );
    expect(plan.messages).toHaveLength(1);
    expect(plan.messages[0].text).toBe('');
  });

  it('handles select_choice with no label', () => {
    const plan = processActions(
      [{ action: 'select_choice' }],
      emptyForm,
      null,
    );
    expect(plan.messages[0].text).toBe('[system] User selected option: ""');
  });

  // ── Complex real-world combos ──

  it('fill_fields + select_choice + message: all three handled', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { full_name: 'Jane Smith' } },
        { action: 'select_choice', label: 'Computer Science (MS)' },
        { action: 'message', text: 'I am applying for CS' },
      ],
      emptyForm,
      null,
    );
    expect(plan.fieldEdits).toEqual({ full_name: 'Jane Smith' });
    expect(plan.messages).toHaveLength(2);
    expect(plan.messages[0].isSystem).toBe(true);
    expect(plan.messages[1].text).toBe('I am applying for CS');
  });
});

// ══════════════════════════════════════════════════════════════════════
// buildLlmAMessage
// ══════════════════════════════════════════════════════════════════════

describe('buildLlmAMessage (TS)', () => {
  it('returns empty string for empty messages', () => {
    expect(buildLlmAMessage([])).toBe('');
  });

  it('returns single message text', () => {
    expect(buildLlmAMessage([{ text: 'Hello' }])).toBe('Hello');
  });

  it('joins multiple messages with newline', () => {
    const result = buildLlmAMessage([
      { text: '[system] User selected option: "CS (MS)"' },
      { text: 'I have a strong background in ML' },
    ]);
    expect(result).toBe('[system] User selected option: "CS (MS)"\nI have a strong background in ML');
  });

  it('prepends file content to message text', () => {
    const result = buildLlmAMessage([
      {
        text: 'Here is my transcript',
        resolvedFile: { filename: 'Transcript.pdf', content: 'GPA: 3.85\nDegree: CS' },
      },
    ]);
    expect(result).toBe(
      '[File: Transcript.pdf]\nGPA: 3.85\nDegree: CS\n[End of Transcript.pdf]\n\nHere is my transcript',
    );
  });

  it('ignores resolvedFile with no filename', () => {
    const result = buildLlmAMessage([
      { text: 'Hello', resolvedFile: { filename: '', content: 'stuff' } },
    ]);
    expect(result).toBe('Hello');
  });

  it('handles multiple messages with files', () => {
    const result = buildLlmAMessage([
      {
        text: 'My resume',
        resolvedFile: { filename: 'Resume.pdf', content: 'Work at Google' },
      },
      {
        text: 'My transcript',
        resolvedFile: { filename: 'Transcript.pdf', content: 'GPA: 3.85' },
      },
    ]);
    expect(result).toContain('[File: Resume.pdf]');
    expect(result).toContain('[File: Transcript.pdf]');
    expect(result).toContain('My resume');
    expect(result).toContain('My transcript');
  });
});

// ══════════════════════════════════════════════════════════════════════
// Integration: processActions → buildLlmAMessage
// ══════════════════════════════════════════════════════════════════════

describe('processActions → buildLlmAMessage integration (TS)', () => {
  it('select_choice + message produces correct combined LLM A input', () => {
    const plan = processActions(
      [
        { action: 'select_choice', label: 'Computer Science (MS)' },
        { action: 'message', text: 'I have a strong background in ML' },
      ],
      {},
      null,
    );
    const msg = buildLlmAMessage(plan.messages);
    expect(msg).toBe(
      '[system] User selected option: "Computer Science (MS)"\nI have a strong background in ML',
    );
  });

  it('fill_fields + message: only message reaches LLM A', () => {
    const plan = processActions(
      [
        { action: 'fill_fields', fields: { gpa: '3.85' } },
        { action: 'message', text: 'I updated my GPA' },
      ],
      {},
      null,
    );
    expect(plan.fieldEdits).toEqual({ gpa: '3.85' });
    const msg = buildLlmAMessage(plan.messages);
    expect(msg).toBe('I updated my GPA');
  });

  it('select_choice + message with resolved file', () => {
    const plan = processActions(
      [
        { action: 'select_choice', label: "Bachelor's" },
        { action: 'message', text: 'Here is my transcript', file: 'transcript' },
      ],
      {},
      null,
    );
    plan.messages[1].resolvedFile = { filename: 'Transcript.pdf', content: 'GPA: 3.85' };

    const msg = buildLlmAMessage(plan.messages);
    expect(msg).toContain('[system] User selected option: "Bachelor\'s"');
    expect(msg).toContain('[File: Transcript.pdf]');
    expect(msg).toContain('Here is my transcript');
  });

  it('fill_fields only: no message for LLM A', () => {
    const plan = processActions(
      [{ action: 'fill_fields', fields: { full_name: 'Jane' } }],
      {},
      null,
    );
    const msg = buildLlmAMessage(plan.messages);
    expect(msg).toBe('');
  });
});
