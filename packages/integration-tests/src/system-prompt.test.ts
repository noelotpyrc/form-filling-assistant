import { describe, it, expect } from 'vitest';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { JSDOM } from 'jsdom';

// Load browser-side system-prompt.js via JSDOM (same pattern as action-parser.test.ts)
const promptPath = resolve(__dirname, '../../web-app/public/js/system-prompt.js');
const promptCode = readFileSync(promptPath, 'utf-8');

const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>', {
  runScripts: 'dangerously',
});
dom.window.eval(promptCode);

const SystemPrompt = (dom.window as unknown as {
  SystemPrompt: {
    build: (
      formMeta: unknown | null,
      vaultSummary: string,
      formState: Record<string, unknown>,
    ) => string;
  };
}).SystemPrompt;

// Load Northfield form metadata as fixture
const formMeta = JSON.parse(
  readFileSync(
    resolve(__dirname, '../../web-app/public/forms/masters-northfield.json'),
    'utf-8',
  ),
);

describe('System Prompt Builder (from browser JS)', () => {
  it('contains "No Form Selected" when formMeta is null', () => {
    const result = SystemPrompt.build(null, '', {});
    expect(result).toContain('No Form Selected');
  });

  it('contains form name when formMeta is provided', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('Northfield University Graduate Application');
  });

  it('includes form schema as JSON', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('"field_id": "full_name"');
    expect(result).toContain('"field_id": "email"');
  });

  it('includes section order joined by arrow', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    // section_order: ["program", "personal", "education", ...]
    expect(result).toContain('program');
    expect(result).toContain(' → ');
    expect(result).toContain('personal');
  });

  it('includes section guidance for each section', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('Start by asking what program');
    expect(result).toContain('Collect basic personal and contact information');
    expect(result).toContain("Ask about the applicant's academic background");
  });

  it('includes general notes', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('Program selection should come first');
    expect(result).toContain('Be encouraging and supportive');
  });

  it('does not include vault section in prompt (vault disabled)', () => {
    const result = SystemPrompt.build(formMeta, 'Vault has 2 entries: personal info, education.', {});
    expect(result).not.toContain('Vault');
    expect(result).not.toContain('vault');
  });

  it('does NOT include "Current Form State" when formState is empty', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).not.toContain('Current Form State');
  });

  it('includes formState values as JSON when populated', () => {
    const result = SystemPrompt.build(formMeta, '', {
      full_name: 'John Smith',
      email: 'john@test.com',
    });
    expect(result).toContain('Current Form State');
    expect(result).toContain('"full_name": "John Smith"');
    expect(result).toContain('"email": "john@test.com"');
  });

  it('includes action format specification with all 5 action types', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('---actions---');
    expect(result).toContain('set_fields');
    expect(result).toContain('show_fields');
    expect(result).toContain('ask_choice');
    expect(result).toContain('show_preview');
    expect(result).toContain('show_button');
  });

  it('includes behavior guidelines with interruption handling', () => {
    const result = SystemPrompt.build(formMeta, '', {});
    expect(result).toContain('Handle interruptions gracefully');
    expect(result).toContain('Be conversational');
    expect(result).toContain('Don\'t control the form panel');
  });
});
