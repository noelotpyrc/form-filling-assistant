import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

// ── Types ──────────────────────────────────────────────────────────────

export interface VaultEntry {
  id: string;
  file: string;
  created_at: string;
  source_url: string;
  form_id: string;
  status: 'draft' | 'submitted';
  description: string;
  data_summary: string[];
  is_merged?: boolean;
  is_profile?: boolean;
}

interface VaultIndex {
  version: string;
  entries: VaultEntry[];
  active_profile_id: string | null;
}

export interface SaveDumpParams {
  description: string;
  data_summary: string[];
  source_url: string;
  form_id: string;
  status: 'draft' | 'submitted';
  data: Record<string, unknown>;
  is_merged?: boolean;
  is_profile?: boolean;
}

// ── Paths ──────────────────────────────────────────────────────────────
// Allow overriding via env var for testing
const VAULT_DIR =
  process.env.FORM_FILLING_VAULT_DIR ||
  path.join(os.homedir(), '.form-filling-assistant');
const INDEX_PATH = path.join(VAULT_DIR, 'index.json');
const DUMPS_DIR = path.join(VAULT_DIR, 'dumps');

// ── Helpers ────────────────────────────────────────────────────────────

/**
 * Turn a description like "Masters application to Northfield University"
 * into a short slug like "masters-application-to-northfield-university"
 * (max 50 chars, lowercase, alphanumeric + hyphens).
 */
function slugify(text: string, maxLen = 50): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, maxLen);
}

function readIndex(): VaultIndex {
  const raw = fs.readFileSync(INDEX_PATH, 'utf-8');
  const parsed = JSON.parse(raw) as VaultIndex;
  // Backward compat: older index files may lack active_profile_id
  if (parsed.active_profile_id === undefined) {
    parsed.active_profile_id = null;
  }
  return parsed;
}

function writeIndex(index: VaultIndex): void {
  fs.writeFileSync(INDEX_PATH, JSON.stringify(index, null, 2), 'utf-8');
}

// ── Public API ─────────────────────────────────────────────────────────

/**
 * Ensure the vault directory structure exists.
 * Safe to call multiple times — only creates what's missing.
 */
export function initVault(): void {
  fs.mkdirSync(DUMPS_DIR, { recursive: true });

  if (!fs.existsSync(INDEX_PATH)) {
    const empty: VaultIndex = { version: '1.0', entries: [], active_profile_id: null };
    writeIndex(empty);
  }
}

/**
 * Return all vault entries (metadata only — no dump data).
 */
export function listEntries(): VaultEntry[] {
  initVault();
  const index = readIndex();
  return index.entries;
}

/**
 * Load one or more dump files by their IDs.
 * Returns an array of { id, description, data } objects.
 * Throws if any ID is not found.
 */
export function loadDumps(
  ids: string[],
): Array<{ id: string; description: string; data: Record<string, unknown> }> {
  initVault();
  const index = readIndex();

  return ids.map((id) => {
    const entry = index.entries.find((e) => e.id === id);
    if (!entry) {
      throw new Error(`Vault entry not found: ${id}`);
    }
    const dumpPath = path.join(VAULT_DIR, entry.file);
    if (!fs.existsSync(dumpPath)) {
      throw new Error(`Dump file missing for entry ${id}: ${dumpPath}`);
    }
    const raw = fs.readFileSync(dumpPath, 'utf-8');
    const data = JSON.parse(raw) as Record<string, unknown>;
    return { id: entry.id, description: entry.description, data };
  });
}

/**
 * Save a new dump to the vault.
 * Returns { id, file } for the created entry.
 */
export function saveDump(params: SaveDumpParams): { id: string; file: string } {
  initVault();

  // Generate ID: ISO timestamp (file-safe) + purpose slug
  // Append a short random suffix to avoid collisions within the same second
  const now = new Date();
  const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19); // e.g. 2026-02-15T18-30-00
  const purpose = slugify(params.description);
  const suffix = crypto.randomUUID().slice(0, 4);
  const id = `${timestamp}_${purpose}-${suffix}`;
  const relFile = `dumps/${id}.json`;
  const absFile = path.join(VAULT_DIR, relFile);

  // Write the dump data
  fs.writeFileSync(absFile, JSON.stringify(params.data, null, 2), 'utf-8');

  // Append entry to index
  const index = readIndex();
  const entry: VaultEntry = {
    id,
    file: relFile,
    created_at: now.toISOString(),
    source_url: params.source_url,
    form_id: params.form_id,
    status: params.status,
    description: params.description,
    data_summary: params.data_summary,
    ...(params.is_merged && { is_merged: true }),
    ...(params.is_profile && { is_profile: true }),
  };
  index.entries.push(entry);
  writeIndex(index);

  return { id, file: relFile };
}

/**
 * Delete one or more vault entries by ID.
 * Removes both the dump file and the index entry.
 * Returns which IDs were deleted and which were not found.
 */
export function deleteDumps(
  ids: string[],
): { deleted: string[]; not_found: string[] } {
  initVault();
  const index = readIndex();
  const deleted: string[] = [];
  const not_found: string[] = [];

  for (const id of ids) {
    const idx = index.entries.findIndex((e) => e.id === id);
    if (idx === -1) {
      not_found.push(id);
      continue;
    }
    // Remove dump file
    const dumpPath = path.join(VAULT_DIR, index.entries[idx].file);
    if (fs.existsSync(dumpPath)) {
      fs.unlinkSync(dumpPath);
    }
    // Remove from index
    index.entries.splice(idx, 1);
    deleted.push(id);
  }

  // Clear active profile if it was deleted
  if (index.active_profile_id && deleted.includes(index.active_profile_id)) {
    index.active_profile_id = null;
  }

  writeIndex(index);
  return { deleted, not_found };
}

/**
 * Remove all vault entries and dump files.
 * Resets index.json to an empty state.
 */
export function clearVault(): number {
  initVault();
  const index = readIndex();
  const count = index.entries.length;

  // Delete all dump files
  for (const entry of index.entries) {
    const dumpPath = path.join(VAULT_DIR, entry.file);
    if (fs.existsSync(dumpPath)) {
      fs.unlinkSync(dumpPath);
    }
  }

  // Reset index
  writeIndex({ version: '1.0', entries: [], active_profile_id: null });
  return count;
}

// ── Profile API ───────────────────────────────────────────────────────

/**
 * Return the active profile entry ID, or null if none is set.
 */
export function getActiveProfileId(): string | null {
  initVault();
  const index = readIndex();
  return index.active_profile_id;
}

/**
 * Set or clear the active profile.
 * Validates the entry exists when setting (non-null).
 */
export function setActiveProfileId(id: string | null): void {
  initVault();
  const index = readIndex();
  if (id !== null) {
    const entry = index.entries.find((e) => e.id === id);
    if (!entry) {
      throw new Error(`Vault entry not found: ${id}`);
    }
  }
  index.active_profile_id = id;
  writeIndex(index);
}

/**
 * Save a synthesized profile as a new vault entry and set it as active.
 * Profiles use source_url: "profile" and form_id: "profile".
 */
export function saveProfile(params: {
  source_ids: string[];
  data: Record<string, unknown>;
  description: string;
  data_summary: string[];
}): { id: string; file: string } {
  const result = saveDump({
    description: params.description,
    data_summary: params.data_summary,
    source_url: 'profile',
    form_id: 'profile',
    status: 'submitted',
    data: params.data,
    is_profile: true,
  });
  setActiveProfileId(result.id);
  return result;
}

// ── Deep merge helper ─────────────────────────────────────────────────

/**
 * Recursively merge two objects. `b` wins on scalar conflicts.
 * Arrays are replaced (not concatenated) — later entry's array wins.
 */
function deepMerge(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...a };
  for (const key of Object.keys(b)) {
    const aVal = a[key];
    const bVal = b[key];
    if (
      bVal !== null &&
      typeof bVal === 'object' &&
      !Array.isArray(bVal) &&
      aVal !== null &&
      typeof aVal === 'object' &&
      !Array.isArray(aVal)
    ) {
      result[key] = deepMerge(
        aVal as Record<string, unknown>,
        bVal as Record<string, unknown>,
      );
    } else {
      result[key] = bVal;
    }
  }
  return result;
}

/**
 * Merge multiple vault entries from the **same website** into a single entry.
 * Entries are merged in order (later entries override earlier on conflicts).
 * Throws if entries come from different source_url values.
 * Returns the new merged entry's { id, file, merged_from }.
 */
export function mergeDumps(
  ids: string[],
  description: string,
): { id: string; file: string; merged_from: string[] } {
  if (ids.length < 2) {
    throw new Error('Merge requires at least 2 entry IDs.');
  }

  initVault();
  const index = readIndex();

  // Look up entries and validate same source_url
  const entries = ids.map((id) => {
    const entry = index.entries.find((e) => e.id === id);
    if (!entry) {
      throw new Error(`Vault entry not found: ${id}`);
    }
    return entry;
  });

  const sourceUrls = new Set(entries.map((e) => e.source_url));
  if (sourceUrls.size > 1) {
    throw new Error(
      'Cannot merge entries from different websites. ' +
        'All entries must share the same source_url. ' +
        `Found: ${[...sourceUrls].join(', ')}`,
    );
  }

  // Load dump data for each entry
  const dumps = loadDumps(ids);

  // Deep merge data in order (later wins)
  let mergedData: Record<string, unknown> = {};
  for (const dump of dumps) {
    mergedData = deepMerge(mergedData, dump.data);
  }

  // Union of data_summary arrays (deduplicated)
  const allSummaries = entries.flatMap((e) => e.data_summary);
  const mergedSummary = [...new Set(allSummaries)];

  // Save as new entry — use latest entry's form_id and source_url
  const latestEntry = entries[entries.length - 1];
  const result = saveDump({
    description,
    data_summary: mergedSummary,
    source_url: latestEntry.source_url,
    form_id: latestEntry.form_id,
    status: 'draft',
    data: mergedData,
    is_merged: true,
  });

  return { ...result, merged_from: ids };
}
