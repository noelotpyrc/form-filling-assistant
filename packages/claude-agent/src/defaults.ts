/**
 * Preset option sets for common agent patterns.
 *
 * Use with spread syntax:
 *   new ClaudeAgent({ ...PRESETS.readonly, cwd: '/my/project' })
 */

import type { AgentOptions } from './types.js';

export const PRESETS = {
  /** Read-only agent — can analyze but not modify anything */
  readonly: {
    allowedTools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },

  /** Coding agent — can read, write, and execute */
  coding: {
    allowedTools: ['Read', 'Edit', 'Write', 'Bash', 'Glob', 'Grep'],
  },

  /** Full agent — all tools, no permission prompts */
  full: {
    dangerouslySkipPermissions: true,
  },

  /** Planning agent — can explore but enters plan mode */
  planning: {
    permissionMode: 'plan' as const,
    allowedTools: ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch'],
  },

  /** CI agent — no session persistence, budget-limited */
  ci: {
    dangerouslySkipPermissions: true,
    noSessionPersistence: true,
    maxBudgetUsd: 5.0,
  },
} as const satisfies Record<string, AgentOptions>;
