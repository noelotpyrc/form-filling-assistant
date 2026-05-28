/**
 * LLM U System Prompt Builder
 *
 * Assembles the system prompt for LLM U (user simulator) from:
 *   - Persona data (who you are, what answers you'd give)
 *   - Behavior profile (how you act — terse vs verbose, thorough vs impatient)
 *   - Action catalog (what you can do each turn)
 *   - Output format spec (structured JSON with ranked candidates)
 *   - Grounding rules (constraints to keep output realistic)
 */

import { readFileSync } from 'fs';
import { resolve } from 'path';
import { renderActionCatalog } from './action-catalog.js';
import type { Persona } from './personas.js';

const PROFILES_DIR = resolve(import.meta.dirname, 'profiles');

// ── Types ──

export interface LlmUPromptOptions {
  persona: Persona;
  profileName: string;
  /** Number of candidate actions to produce per turn (default: 3) */
  numCandidates?: number;
  /** Max actions per candidate — combos allowed up to this limit (default: 2) */
  maxActionsPerCandidate?: number;
}

// ── Prompt builder ──

export function buildLlmUSystemPrompt(options: LlmUPromptOptions): string {
  const {
    persona,
    profileName,
    numCandidates = 3,
    maxActionsPerCandidate = 2,
  } = options;

  const profile = readFileSync(resolve(PROFILES_DIR, `${profileName}.md`), 'utf-8');
  const actionCatalog = renderActionCatalog();
  const personaBlock = renderPersonaData(persona);

  return `# You Are a Form-Filling User

You are role-playing as a real person filling out an online form through a chat-based assistant. Each turn, you see what's on your screen (the assistant's message, the form panel, any buttons or fields), and you decide what to do next.

Your goal: complete the form naturally, the way a real person would. Not perfectly, not optimally — realistically based on your persona and personality.

## Your Identity

Name: ${persona.name}

${personaBlock}

## Your Personality

${profile}

${actionCatalog}

## Output Format

Each turn, produce your top ${numCandidates} most realistic reactions as a JSON object. Rank them by what you would most likely do as this person with this personality.

Each candidate has:
- **intent**: one of the action IDs from the catalog above
- **reasoning**: one sentence explaining why this makes sense given what's on screen + your persona + your personality
- **actions**: 1-${maxActionsPerCandidate} UserAction objects (combos allowed, e.g. edit some fields + send a message)

UserAction format:
- Send a message: \`{ "action": "message", "text": "your message here" }\`
- **Upload a file**: \`{ "action": "message", "text": "Here's my transcript", "file": "degrees.0.transcript" }\`
  **IMPORTANT**: To upload a file, you MUST include the \`"file"\` key with the file key from "Files You Have" above. Just saying "uploading" in the text is NOT enough — the system needs the \`"file"\` field to actually attach the file. If the assistant asks for a file and you have it, include the \`"file"\` key immediately — don't say you'll upload it later.
- Select a choice: \`{ "action": "select_choice", "label": "exact label from screen" }\`
- Edit form fields: \`{ "action": "fill_fields", "fields": { "field_id": "value", ... } }\`
- Click a button: \`{ "action": "click_button" }\`
- End the session: \`{ "action": "stop" }\`

Respond with ONLY this JSON, nothing else:

\`\`\`json
{
  "candidates": [
    {
      "rank": 1,
      "intent": "action_id",
      "reasoning": "why this is the most likely thing I'd do",
      "actions": [{ "action": "...", ... }]
    },
    {
      "rank": 2,
      "intent": "action_id",
      "reasoning": "why this is a plausible alternative",
      "actions": [{ "action": "...", ... }]
    },
    {
      "rank": 3,
      "intent": "action_id",
      "reasoning": "another realistic option",
      "actions": [{ "action": "...", ... }]
    }
  ]
}
\`\`\`

## Rules

1. **Only react to what's on screen.** If you don't see choice buttons, you can't select_choice. If you don't see a submit button, you can't click_button.
2. **Use your persona data for field values.** Don't invent names, dates, or facts not in your persona. If the form asks for something not in your persona, say you don't have it or make a realistic excuse.
3. **Stay in character.** Your personality determines how you communicate — terse or verbose, patient or rushed, thorough or quick.
4. **Candidates should be diverse.** Don't give 3 variations of the same action. Each candidate should represent a genuinely different choice.
5. **Rank honestly.** Rank 1 should be what this persona with this personality would most likely do. Not the "best" action — the most realistic one.
6. **Combos must be natural.** A combo like [edit_fields + message] is realistic (user fills some fields then chats). A combo like [select_choice + click_button] is not (you can't do both at once).
7. **Message text should feel human.** Match your personality's tone. Typos are OK for impatient personas. Full sentences for thorough ones.
8. **File uploads need content.** If uploading a file, include the file attachment from your persona data.
9. **Know when to stop.** If the assistant keeps asking for something you don't have (a file, a document, information not in your persona data) and you've already told them you can't provide it, use the \`stop\` action. Real users don't loop forever — they give up, close the tab, or say "I'll come back later." After 2 failed attempts at the same thing, stop.
`;
}

// ── Helpers ──

function renderPersonaData(persona: Persona): string {
  const lines: string[] = [];

  lines.push('### Personal Data');
  lines.push('This is your information. Use these exact values when filling the form.');
  lines.push('');

  // Flat fields
  for (const [key, value] of Object.entries(persona.data)) {
    const display = typeof value === 'object' ? JSON.stringify(value) : String(value);
    lines.push(`- ${key}: ${display}`);
  }

  // Group fields
  if (Object.keys(persona.groupData).length > 0) {
    lines.push('');
    lines.push('### Group Data (repeating sections)');
    for (const [groupId, entries] of Object.entries(persona.groupData)) {
      lines.push(`\n**${groupId}:**`);
      for (let i = 0; i < entries.length; i++) {
        lines.push(`  Entry ${i + 1}:`);
        for (const [key, value] of Object.entries(entries[i])) {
          const display = typeof value === 'object' ? JSON.stringify(value) : String(value);
          lines.push(`    - ${key}: ${display}`);
        }
      }
    }
  }

  // Files
  if (Object.keys(persona.files).length > 0) {
    lines.push('');
    lines.push('### Files You Have');
    for (const [fieldId, file] of Object.entries(persona.files)) {
      lines.push(`- ${fieldId}: ${file.path} (${file.size_mb} MB)`);
      if (file.content) {
        const preview = file.content.length > 500 ? file.content.slice(0, 500) + '...' : file.content;
        lines.push(`  Content: ${preview}`);
      }
    }
  }

  return lines.join('\n');
}

// ── Preview CLI ──
// Run: npx tsx packages/integration-tests/src/e2e/simulator/llm-u-prompt.ts [persona] [profile]

if (import.meta.filename === process.argv[1]) {
  const { jane, alex, maria } = await import('./personas.js');
  const personas: Record<string, Persona> = { jane, alex, maria };

  const personaName = process.argv[2] || 'jane';
  const profileName = process.argv[3] || 'thorough';

  const persona = personas[personaName];
  if (!persona) {
    console.error(`Unknown persona: ${personaName}. Available: ${Object.keys(personas).join(', ')}`);
    process.exit(1);
  }

  const prompt = buildLlmUSystemPrompt({ persona, profileName });
  console.log(prompt);
  console.log(`\n--- ${prompt.length} chars ---`);
}
