#!/usr/bin/env node

import {
  listEntries,
  loadDumps,
  saveDump,
  deleteDumps,
  clearVault,
} from '../vault/vault-manager.js';

// ── Seed data (matches vault-cross-site.test.ts constants) ────────────

const PERSONAL_DATA = {
  full_name: 'Jane Smith',
  dob: '1995-06-15',
  country_citizenship: 'US',
  email: 'jane@example.com',
  phone: '+15559876543',
  mailing_address: '456 Oak Ave, Springfield, IL 62704',
};

const EDUCATION_DATA = {
  degrees: [
    {
      institution: 'State University',
      degree_type: 'bachelor',
      field_of_study: 'Computer Science',
      gpa: 3.85,
      gpa_scale: '4.0',
      start_date: '2013-08',
      end_date: '2017-05',
    },
  ],
};

const WORK_DATA = {
  has_work_experience: true,
  jobs: [
    {
      employer: 'Tech Corp',
      title: 'Software Engineer',
      start_date: '2017-06',
      end_date: '2024-12',
      description: 'Full-stack development and ML infrastructure',
    },
  ],
};

const RESEARCH_DATA = {
  publications_count: 2,
  research_interests:
    'Interested in large language models, reinforcement learning from human feedback, and AI safety.',
  advisor_preference: 'Dr. Sarah Chen, Dr. Michael Torres',
};

const TECHNICAL_DATA = {
  programming_languages: ['python', 'cpp', 'rust'],
  technical_statement:
    'Proficient in PyTorch, JAX, and distributed training. Built ML pipeline serving 10M requests/day.',
};

// ── Commands ──────────────────────────────────────────────────────────

function cmdList(): void {
  const entries = listEntries();
  if (entries.length === 0) {
    console.log('No entries in vault.');
    return;
  }
  console.log(`${entries.length} entries:\n`);
  for (const e of entries) {
    console.log(`  ${e.id}`);
    console.log(`    ${e.description}`);
    console.log(
      `    status=${e.status}  source=${e.source_url}  created=${e.created_at}`,
    );
    console.log(`    data: ${e.data_summary.join(', ')}`);
    console.log();
  }
}

function cmdShow(id: string): void {
  try {
    const [dump] = loadDumps([id]);
    console.log(`Entry: ${dump.id}`);
    console.log(`Description: ${dump.description}\n`);
    console.log(JSON.stringify(dump.data, null, 2));
  } catch (err) {
    console.error((err as Error).message);
    process.exit(1);
  }
}

function cmdDelete(ids: string[]): void {
  const result = deleteDumps(ids);
  if (result.deleted.length > 0) {
    console.log(`Deleted ${result.deleted.length} entries:`);
    for (const id of result.deleted) {
      console.log(`  - ${id}`);
    }
  }
  if (result.not_found.length > 0) {
    console.log(`Not found (${result.not_found.length}):`);
    for (const id of result.not_found) {
      console.log(`  - ${id}`);
    }
  }
}

function cmdClear(): void {
  const count = clearVault();
  console.log(`Cleared ${count} entries from vault.`);
}

function cmdSeed(): void {
  // Program A — Northfield CS Masters
  const a = saveDump({
    description:
      'Masters CS application to Northfield University for Jane Smith, Fall 2026',
    data_summary: [
      'personal info',
      'education',
      'work experience',
      'program selection',
      'funding',
    ],
    source_url: 'http://localhost:3001',
    form_id: 'seed_masters_a',
    status: 'submitted',
    data: {
      personal: PERSONAL_DATA,
      education: EDUCATION_DATA,
      work_experience: WORK_DATA,
      program: { program: 'cs', start_term: 'fall_2026' },
      additional: { funding_interest: true, how_heard: 'website' },
    },
  });

  // Program B — Westbrook Research MS in AI
  const b = saveDump({
    description:
      'Research MS in AI application to Westbrook Institute for Jane Smith',
    data_summary: [
      'personal info',
      'education',
      'work experience',
      'research experience',
      'technical skills',
    ],
    source_url: 'http://localhost:3003',
    form_id: 'seed_masters_b',
    status: 'submitted',
    data: {
      personal: PERSONAL_DATA,
      education: EDUCATION_DATA,
      work_experience: WORK_DATA,
      research: RESEARCH_DATA,
      technical: TECHNICAL_DATA,
    },
  });

  console.log('Seeded 2 entries:');
  console.log(`  1. ${a.id}`);
  console.log(`     Northfield CS Masters (personal, education, work, program, funding)`);
  console.log(`  2. ${b.id}`);
  console.log(`     Westbrook AI Research MS (personal, education, work, research, technical)`);
}

function printUsage(): void {
  console.log(`Usage: npm run vault -- <command> [args]

Commands:
  list                    List all vault entries
  show <id>               Show full data for an entry
  delete <id> [<id>...]   Delete one or more entries
  clear                   Delete ALL entries
  seed                    Create sample entries for testing

Environment:
  FORM_FILLING_VAULT_DIR  Override vault directory (default: ~/.form-filling-assistant)`);
}

// ── Main ──────────────────────────────────────────────────────────────

const [command, ...args] = process.argv.slice(2);

switch (command) {
  case 'list':
    cmdList();
    break;
  case 'show':
    if (!args[0]) {
      console.error('Usage: vault show <id>');
      process.exit(1);
    }
    cmdShow(args[0]);
    break;
  case 'delete':
    if (args.length === 0) {
      console.error('Usage: vault delete <id> [<id>...]');
      process.exit(1);
    }
    cmdDelete(args);
    break;
  case 'clear':
    cmdClear();
    break;
  case 'seed':
    cmdSeed();
    break;
  default:
    printUsage();
    break;
}
