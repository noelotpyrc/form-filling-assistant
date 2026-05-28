import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';

// Load the browser-side action-parser.js and execute it in a simulated DOM
// so we test the actual shipped code, not a duplicate.
const parserPath = resolve(__dirname, '../../web-app/public/js/action-parser.js');
const parserCode = readFileSync(parserPath, 'utf-8');

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  runScripts: 'dangerously',
});
dom.window.eval(parserCode);

const ActionParser = (dom.window as unknown as { ActionParser: {
  parseActions: (response: string) => Array<{ type: string; [key: string]: unknown }>;
  extractText: (response: string) => string;
  containsActionsDelimiter: (text: string) => boolean;
} }).ActionParser;

const { parseActions, extractText, containsActionsDelimiter } = ActionParser;

describe('Action Parser (from browser JS)', () => {
  it('returns empty array when no actions delimiter', () => {
    const response = 'Hello! How can I help you today?';
    expect(parseActions(response)).toEqual([]);
  });

  it('extracts full text when no actions', () => {
    const response = 'Hello! How can I help you today?';
    expect(extractText(response)).toBe('Hello! How can I help you today?');
  });

  it('parses single action in fenced JSON block', () => {
    const response = `Let me show you the first fields.

---actions---
\`\`\`json
[{ "type": "show_fields", "fields": [{ "field_id": "full_name" }] }]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
    expect(actions[0].type).toBe('show_fields');
  });

  it('extracts text before actions delimiter', () => {
    const response = `Let me show you the first fields.

---actions---
\`\`\`json
[{ "type": "show_fields", "fields": [{ "field_id": "full_name" }] }]
\`\`\``;

    expect(extractText(response)).toBe('Let me show you the first fields.');
  });

  it('parses multiple actions', () => {
    const response = `Got it! I'll set your name and show more fields.

---actions---
\`\`\`json
[
  { "type": "set_fields", "fields": [{ "field_id": "full_name", "value": "John Smith" }] },
  { "type": "show_fields", "fields": [{ "field_id": "email" }, { "field_id": "phone" }] }
]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(2);
    expect(actions[0].type).toBe('set_fields');
    expect(actions[1].type).toBe('show_fields');
  });

  it('parses ask_choice action', () => {
    const response = `Which program are you interested in?

---actions---
\`\`\`json
[{
  "type": "ask_choice",
  "question": "Which program?",
  "options": [
    { "label": "CS", "value": "cs" },
    { "label": "MBA", "value": "mba" }
  ]
}]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
    expect(actions[0].type).toBe('ask_choice');
    expect((actions[0] as { options: unknown[] }).options).toHaveLength(2);
  });

  it('parses show_preview action', () => {
    const response = `Here's your application summary:

---actions---
\`\`\`json
[{
  "type": "show_preview",
  "title": "Summary",
  "sections": [{ "title": "Personal", "fields": [{ "label": "Name", "value": "John" }] }]
}]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
    expect(actions[0].type).toBe('show_preview');
  });

  it('parses show_button action', () => {
    const response = `Ready to save?

---actions---
\`\`\`json
[{ "type": "show_button", "button": "save_draft" }]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
    expect(actions[0].type).toBe('show_button');
    expect(actions[0].button).toBe('save_draft');
  });

  it('handles raw JSON without fences', () => {
    const response = `Text here.

---actions---
[{ "type": "show_fields", "fields": [] }]`;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
  });

  it('handles single action object (not array)', () => {
    const response = `Text.

---actions---
\`\`\`json
{ "type": "show_button", "button": "submit" }
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(1);
    expect(actions[0].button).toBe('submit');
  });

  it('returns empty array for malformed JSON', () => {
    const response = `Text.

---actions---
\`\`\`json
{ not valid json }
\`\`\``;

    expect(parseActions(response)).toEqual([]);
  });

  it('filters out non-action objects from array', () => {
    const response = `Text.

---actions---
\`\`\`json
[
  { "type": "show_fields", "fields": [] },
  { "not_an_action": true },
  null,
  { "type": "set_fields", "fields": [] }
]
\`\`\``;

    const actions = parseActions(response);
    expect(actions).toHaveLength(2);
  });

  it('containsActionsDelimiter returns true when delimiter present', () => {
    expect(containsActionsDelimiter('some text ---actions--- more')).toBe(true);
    expect(containsActionsDelimiter('no delimiter here')).toBe(false);
  });
});
