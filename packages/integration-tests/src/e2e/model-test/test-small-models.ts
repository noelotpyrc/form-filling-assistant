#!/usr/bin/env npx tsx
/**
 * CLI script to test small models against our system prompt.
 *
 * Usage:
 *   npx tsx packages/integration-tests/src/e2e/model-test/test-small-models.ts
 *   npx tsx packages/integration-tests/src/e2e/model-test/test-small-models.ts --model qwen
 *   npx tsx packages/integration-tests/src/e2e/model-test/test-small-models.ts --model smollm --test greeting
 *   npx tsx packages/integration-tests/src/e2e/model-test/test-small-models.ts --model all --max-tokens 256
 */

import { pipeline, type TextGenerationPipeline } from '@huggingface/transformers';
import { readFileSync } from 'fs';
import path from 'path';

// ── Model configs ──
const MODELS: Record<string, { id: string; label: string; sizeNote: string }> = {
  'smollm-360': {
    id: 'HuggingFaceTB/SmolLM2-360M-Instruct',
    label: 'SmolLM2-360M-Instruct',
    sizeNote: '~250MB q4',
  },
  'qwen25': {
    id: 'onnx-community/Qwen2.5-0.5B-Instruct',
    label: 'Qwen2.5-0.5B-Instruct',
    sizeNote: '~350MB q4',
  },
  'qwen3': {
    id: 'onnx-community/Qwen3-0.6B-ONNX',
    label: 'Qwen3-0.6B',
    sizeNote: '~400MB q4',
  },
  'smollm-135': {
    id: 'HuggingFaceTB/SmolLM2-135M-Instruct',
    label: 'SmolLM2-135M-Instruct',
    sizeNote: '~100MB q4',
  },
};

// ── Test cases ──
const TEST_CASES: Record<string, { label: string; userMessage: string; description: string; expectActions: boolean }> = {
  greeting: {
    label: 'Greeting',
    userMessage: 'Hi, I want to start filling out this form.',
    description: 'Should produce text + ask_choice action',
    expectActions: true,
  },
  simple_answer: {
    label: 'Simple answer',
    userMessage: 'Jane Smith',
    description: 'Should produce set_fields with name',
    expectActions: true,
  },
  multi_info: {
    label: 'Multi-info batch',
    userMessage: 'Jane Smith, born May 15 1998, US citizen, jane.smith@email.com',
    description: 'Should produce set_fields with multiple fields',
    expectActions: true,
  },
  choice_select: {
    label: 'Choice selection',
    userMessage: 'Computer Science MS',
    description: 'Should produce set_fields with program',
    expectActions: true,
  },
  question: {
    label: 'User question',
    userMessage: 'What documents do I need to submit for this application?',
    description: 'Should answer without hallucinating actions',
    expectActions: false,
  },
};

// ── Action parser (port of browser action-parser.js) ──
const ACTIONS_DELIMITER = '---actions---';

function extractText(response: string): string {
  const idx = response.indexOf(ACTIONS_DELIMITER);
  return idx === -1 ? response : response.slice(0, idx).trim();
}

function parseActions(response: string): Array<{ type: string; [k: string]: unknown }> {
  const idx = response.indexOf(ACTIONS_DELIMITER);
  if (idx === -1) return [];
  let jsonStr = response.slice(idx + ACTIONS_DELIMITER.length).trim();
  const fenceMatch = jsonStr.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
  if (fenceMatch) jsonStr = fenceMatch[1].trim();
  jsonStr = jsonStr.replace(/^```(?:json)?/gm, '').replace(/```$/gm, '').trim();
  try {
    const parsed = JSON.parse(jsonStr);
    if (Array.isArray(parsed)) return parsed.filter(a => a && typeof a === 'object' && typeof a.type === 'string');
    if (parsed && typeof parsed.type === 'string') return [parsed];
    return [];
  } catch {
    return [];
  }
}

// ── System prompt builder (port of browser system-prompt.js) ──
function buildSystemPrompt(formMeta: any): string {
  const parts: string[] = [];

  parts.push(`You are a form-filling assistant that helps users complete forms through conversation. Users interact with you via a chat interface with a form panel on the right side.

You guide users through the form section by section, collecting their information conversationally. You control what appears in the form panel through structured actions.`);

  parts.push(`
## Output Format: Text + Actions

Every response you give has two parts:
1. **Text** — your conversational message to the user (always present)
2. **Actions** — structured commands that control the form panel (optional)

When you need to include actions, place them AFTER your text, separated by the delimiter \`---actions---\`, followed by a JSON array in a fenced code block:

\`\`\`
Your conversational text here...

---actions---
\`\`\`json
[
  { "type": "set_fields", "fields": [{ "field_id": "full_name", "value": "John Smith" }] }
]
\`\`\`
\`\`\`

If you have NO actions to emit, just write your text with no delimiter.

### Available Action Types

**set_fields** — Set form field values.
\`\`\`json
{ "type": "set_fields", "fields": [{ "field_id": "full_name", "value": "John Smith" }] }
\`\`\`

**ask_choice** — Render clickable option buttons in the chat.
\`\`\`json
{ "type": "ask_choice", "question": "Which program?", "options": [{ "label": "CS (MS)", "value": "cs" }] }
\`\`\`

You can emit multiple actions in one response as a JSON array.`);

  if (formMeta) {
    parts.push(`
## Current Form: ${formMeta.name}

### Form Instructions
${formMeta.instructions.greeting}

**Section order:** ${formMeta.instructions.section_order.join(' → ')}

### Form Schema
\`\`\`json
${JSON.stringify(formMeta.schema, null, 2)}
\`\`\``);
  }

  parts.push(`
## Behavior Guidelines
- Be conversational — this is a chat, not a form.
- Auto-fill when possible — when you know field values, fill them in automatically with set_fields.
- Don't force completion — users can send partial answers.`);

  return parts.join('\n');
}

// ── Scoring ──
interface Score { label: string; grade: 'pass' | 'partial' | 'fail' }

function scoreOutput(text: string, testId: string): Score[] {
  const scores: Score[] = [];
  const trimmed = text.trim();

  if (trimmed.length < 10) {
    scores.push({ label: 'Output too short', grade: 'fail' });
    return scores;
  }
  scores.push({ label: 'Has text output', grade: 'pass' });

  const hasDelimiter = text.includes(ACTIONS_DELIMITER);
  const expectActions = TEST_CASES[testId].expectActions;

  if (expectActions) {
    scores.push({
      label: hasDelimiter ? 'Has ---actions--- delimiter' : 'Missing ---actions--- delimiter',
      grade: hasDelimiter ? 'pass' : 'fail',
    });
  } else {
    scores.push({
      label: hasDelimiter ? 'Has actions (unexpected for question)' : 'No actions (correct for question)',
      grade: hasDelimiter ? 'partial' : 'pass',
    });
  }

  if (hasDelimiter) {
    const actions = parseActions(text);
    if (actions.length > 0) {
      scores.push({ label: `Valid JSON actions (${actions.length})`, grade: 'pass' });
      const validTypes = ['set_fields', 'ask_choice', 'show_fields', 'show_preview', 'show_button', 'ask_user'];
      const allValid = actions.every(a => validTypes.includes(a.type));
      scores.push({
        label: allValid ? 'All action types valid' : `Unknown types: ${actions.map(a => a.type).join(', ')}`,
        grade: allValid ? 'pass' : 'partial',
      });
    } else {
      scores.push({ label: 'Actions JSON parse failed', grade: 'fail' });
    }
  }

  const textPart = extractText(text);
  scores.push({
    label: textPart.length > 20 ? `Conversational text (${textPart.length} chars)` : `Text too short (${textPart.length} chars)`,
    grade: textPart.length > 20 ? 'pass' : 'partial',
  });

  return scores;
}

// ── CLI ──
async function main() {
  const args = process.argv.slice(2);
  const modelKey = getArg(args, '--model') || 'qwen';
  const testFilter = getArg(args, '--test');
  const maxTokens = parseInt(getArg(args, '--max-tokens') || '512');
  const dtype = getArg(args, '--dtype') || 'q4'; // q4f16 needs WebGPU; q4 works on WASM/Node

  const modelsToTest = modelKey === 'all' ? Object.keys(MODELS) : [modelKey];
  const testsToRun = testFilter ? [testFilter] : Object.keys(TEST_CASES);

  // Load form schema
  const formPath = path.resolve(
    import.meta.dirname, '..', '..', '..', '..', 'web-app', 'public', 'forms', 'masters-northfield.json',
  );
  const formMeta = JSON.parse(readFileSync(formPath, 'utf-8'));
  const systemPrompt = buildSystemPrompt(formMeta);

  console.log(`\n${'═'.repeat(70)}`);
  console.log(`  Small Model Test — Form-Filling Assistant`);
  console.log(`${'═'.repeat(70)}`);
  console.log(`  System prompt: ${systemPrompt.length} chars (~${Math.round(systemPrompt.length / 4)} tokens)`);
  console.log(`  Max tokens: ${maxTokens}  Dtype: ${dtype}`);
  console.log(`  Models: ${modelsToTest.join(', ')}`);
  console.log(`  Tests: ${testsToRun.join(', ')}`);
  console.log(`${'═'.repeat(70)}\n`);

  for (const mk of modelsToTest) {
    const modelConfig = MODELS[mk];
    if (!modelConfig) {
      console.error(`Unknown model: ${mk}. Options: ${Object.keys(MODELS).join(', ')}, all`);
      process.exit(1);
    }

    console.log(`\n${'─'.repeat(70)}`);
    console.log(`  Loading: ${modelConfig.label} (${modelConfig.sizeNote})`);
    console.log(`  ID: ${modelConfig.id}`);
    console.log(`${'─'.repeat(70)}`);

    const loadStart = Date.now();
    let generator: TextGenerationPipeline;
    try {
      generator = await pipeline('text-generation', modelConfig.id, {
        dtype: dtype as any,
        // Node.js: use 'q4' for WASM. 'q4f16' needs WebGPU (browser only).
        progress_callback: (progress: any) => {
          if (progress.status === 'progress' && progress.progress) {
            process.stdout.write(`\r  Loading: ${Math.round(progress.progress)}%   `);
          }
        },
      }) as TextGenerationPipeline;
    } catch (err: any) {
      console.error(`\n  ✗ Failed to load model: ${err.message}`);
      continue;
    }
    const loadTime = ((Date.now() - loadStart) / 1000).toFixed(1);
    console.log(`\r  ✓ Model loaded in ${loadTime}s\n`);

    // Run tests
    const results: Array<{ test: string; elapsed: number; scores: Score[]; output: string }> = [];

    for (const testId of testsToRun) {
      const test = TEST_CASES[testId];
      if (!test) {
        console.error(`  Unknown test: ${testId}`);
        continue;
      }

      process.stdout.write(`  ── ${test.label} ──\n`);
      process.stdout.write(`  User: "${test.userMessage}"\n`);
      process.stdout.write(`  Generating...`);

      const messages = [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: test.userMessage },
      ];

      const genStart = Date.now();
      let fullText = '';

      try {
        const output = await generator(messages, {
          max_new_tokens: maxTokens,
          do_sample: true,
          temperature: 0.7,
          return_full_text: false,
        });

        // Extract generated text
        if (output && (output as any)[0]) {
          const genText = (output as any)[0].generated_text;
          if (typeof genText === 'string') {
            fullText = genText;
          } else if (Array.isArray(genText)) {
            const last = genText[genText.length - 1];
            fullText = last?.content || JSON.stringify(genText);
          }
        }
      } catch (err: any) {
        fullText = `[ERROR] ${err.message}`;
      }

      const elapsed = Date.now() - genStart;
      const scores = scoreOutput(fullText, testId);
      results.push({ test: testId, elapsed, scores, output: fullText });

      // Print results
      console.log(`\r  Generated in ${(elapsed / 1000).toFixed(1)}s`);
      console.log(`  Output (${fullText.length} chars):`);
      console.log(`  ${'·'.repeat(60)}`);
      // Truncate for display
      const display = fullText.length > 800 ? fullText.slice(0, 800) + '\n  ... [truncated]' : fullText;
      display.split('\n').forEach(line => console.log(`  │ ${line}`));
      console.log(`  ${'·'.repeat(60)}`);

      // Scores
      console.log(`  Scores:`);
      scores.forEach(s => {
        const icon = s.grade === 'pass' ? '✓' : s.grade === 'partial' ? '~' : '✗';
        const color = s.grade === 'pass' ? '\x1b[32m' : s.grade === 'partial' ? '\x1b[33m' : '\x1b[31m';
        console.log(`    ${color}${icon}\x1b[0m ${s.label}`);
      });
      console.log('');
    }

    // Summary
    console.log(`  ${'═'.repeat(60)}`);
    console.log(`  Summary: ${modelConfig.label}`);
    console.log(`  ${'═'.repeat(60)}`);
    let totalPass = 0, totalPartial = 0, totalFail = 0;
    results.forEach(r => {
      r.scores.forEach(s => {
        if (s.grade === 'pass') totalPass++;
        else if (s.grade === 'partial') totalPartial++;
        else totalFail++;
      });
    });
    console.log(`  Pass: ${totalPass}  Partial: ${totalPartial}  Fail: ${totalFail}`);
    console.log(`  Total time: ${results.reduce((s, r) => s + r.elapsed, 0) / 1000}s`);
    console.log(`  Avg time/test: ${(results.reduce((s, r) => s + r.elapsed, 0) / results.length / 1000).toFixed(1)}s`);
    console.log('');
  }
}

function getArg(args: string[], flag: string): string | undefined {
  const idx = args.indexOf(flag);
  return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : undefined;
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
