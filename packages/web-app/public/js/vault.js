/**
 * IndexedDB-based vault for storing and reusing form data across sessions.
 *
 * Database: "form-filling-vault"
 * Object store: "entries" (keyPath: "id")
 * Indexes: source_url, form_id, is_profile
 */

const VAULT_DB_NAME = 'form-filling-vault';
const VAULT_DB_VERSION = 1;
const VAULT_STORE_NAME = 'entries';

// ── Database initialization ─────────────────────────────────────────────────

/**
 * Open (or create) the vault database.
 * @returns {Promise<IDBDatabase>}
 */
function openVaultDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(VAULT_DB_NAME, VAULT_DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(VAULT_STORE_NAME)) {
        const store = db.createObjectStore(VAULT_STORE_NAME, { keyPath: 'id' });
        store.createIndex('source_url', 'source_url', { unique: false });
        store.createIndex('form_id', 'form_id', { unique: false });
        store.createIndex('is_profile', 'is_profile', { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Generate a unique ID for vault entries.
 */
function generateVaultId() {
  return 'vault_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
}

// ── CRUD operations ─────────────────────────────────────────────────────────

/**
 * List all vault entries (metadata only, no full data).
 * @returns {Promise<Array<{ id, description, data_summary, source_url, form_id, status, is_profile, created_at, updated_at }>>}
 */
async function vaultList() {
  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE_NAME, 'readonly');
    const store = tx.objectStore(VAULT_STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => {
      const entries = request.result.map((entry) => ({
        id: entry.id,
        description: entry.description,
        data_summary: entry.data_summary,
        source_url: entry.source_url,
        form_id: entry.form_id,
        status: entry.status,
        is_profile: entry.is_profile || false,
        created_at: entry.created_at,
        updated_at: entry.updated_at,
      }));
      resolve(entries);
    };
    request.onerror = () => reject(request.error);
  });
}

/**
 * Load one or more vault entries by ID (full data).
 * @param {string[]} ids
 * @returns {Promise<object[]>}
 */
async function vaultLoad(ids) {
  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE_NAME, 'readonly');
    const store = tx.objectStore(VAULT_STORE_NAME);
    const results = [];
    let completed = 0;

    for (const id of ids) {
      const request = store.get(id);
      request.onsuccess = () => {
        if (request.result) results.push(request.result);
        completed++;
        if (completed === ids.length) resolve(results);
      };
      request.onerror = () => {
        completed++;
        if (completed === ids.length) resolve(results);
      };
    }

    if (ids.length === 0) resolve([]);
  });
}

/**
 * Save a new vault entry.
 * @param {object} entry - { description, data_summary, source_url, form_id, status, data, is_profile? }
 * @returns {Promise<object>} The saved entry with generated id and timestamps.
 */
async function vaultSave(entry) {
  const db = await openVaultDB();
  const now = new Date().toISOString();
  const record = {
    id: generateVaultId(),
    description: entry.description || '',
    data_summary: entry.data_summary || [],
    source_url: entry.source_url || '',
    form_id: entry.form_id || '',
    status: entry.status || 'draft',
    is_profile: entry.is_profile || false,
    data: entry.data || {},
    created_at: now,
    updated_at: now,
  };

  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE_NAME, 'readwrite');
    const store = tx.objectStore(VAULT_STORE_NAME);
    const request = store.put(record);

    request.onsuccess = () => resolve(record);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Delete one or more vault entries by ID.
 * @param {string[]} ids
 * @returns {Promise<void>}
 */
async function vaultDelete(ids) {
  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE_NAME, 'readwrite');
    const store = tx.objectStore(VAULT_STORE_NAME);
    let completed = 0;

    for (const id of ids) {
      const request = store.delete(id);
      request.onsuccess = () => {
        completed++;
        if (completed === ids.length) resolve();
      };
      request.onerror = () => {
        completed++;
        if (completed === ids.length) resolve();
      };
    }

    if (ids.length === 0) resolve();
  });
}

// ── Profile management ──────────────────────────────────────────────────────

/**
 * Build/activate/clear a vault profile.
 *
 * - BUILD: Pass { data, description, source_ids } to create a new profile.
 * - ACTIVATE: Pass { id } to set an existing entry as the active profile.
 * - CLEAR: Pass no args (or { id: null }) to deactivate the current profile.
 *
 * Only one profile can be active at a time.
 *
 * @param {object} opts - { id?, data?, description?, source_ids? }
 * @returns {Promise<object|null>} The active profile entry, or null if cleared.
 */
async function vaultSetProfile(opts = {}) {
  const db = await openVaultDB();

  // First, deactivate all current profiles
  const allEntries = await vaultList();
  const currentProfiles = allEntries.filter((e) => e.is_profile);

  if (currentProfiles.length > 0) {
    const tx = db.transaction(VAULT_STORE_NAME, 'readwrite');
    const store = tx.objectStore(VAULT_STORE_NAME);
    for (const p of currentProfiles) {
      const getReq = store.get(p.id);
      getReq.onsuccess = () => {
        if (getReq.result) {
          getReq.result.is_profile = false;
          store.put(getReq.result);
        }
      };
    }
    await new Promise((resolve) => { tx.oncomplete = resolve; });
  }

  // CLEAR mode
  if (!opts.id && !opts.data) {
    return null;
  }

  // ACTIVATE mode: set an existing entry as profile
  if (opts.id && !opts.data) {
    const entries = await vaultLoad([opts.id]);
    if (entries.length === 0) return null;

    const entry = entries[0];
    entry.is_profile = true;
    entry.updated_at = new Date().toISOString();

    const tx2 = db.transaction(VAULT_STORE_NAME, 'readwrite');
    tx2.objectStore(VAULT_STORE_NAME).put(entry);
    await new Promise((resolve) => { tx2.oncomplete = resolve; });
    return entry;
  }

  // BUILD mode: create a new profile entry
  if (opts.data) {
    const profile = await vaultSave({
      description: opts.description || 'Unified profile',
      data_summary: opts.data_summary || ['profile'],
      source_url: 'profile',
      form_id: 'profile',
      status: 'submitted',
      is_profile: true,
      data: opts.data,
    });
    return profile;
  }

  return null;
}

/**
 * Get the currently active profile, if any.
 * @returns {Promise<object|null>}
 */
async function vaultGetActiveProfile() {
  const db = await openVaultDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(VAULT_STORE_NAME, 'readonly');
    const store = tx.objectStore(VAULT_STORE_NAME);
    const index = store.index('is_profile');
    const request = index.getAll(true);

    request.onsuccess = () => {
      const profiles = request.result;
      resolve(profiles.length > 0 ? profiles[0] : null);
    };
    request.onerror = () => reject(request.error);
  });
}

/**
 * Build a summary of all vault entries for injection into model context.
 * @returns {Promise<string>}
 */
async function vaultBuildSummary() {
  const entries = await vaultList();
  if (entries.length === 0) {
    return 'No saved vault entries.';
  }

  const lines = entries.map((e) => {
    const profileTag = e.is_profile ? ' [ACTIVE PROFILE]' : '';
    return `- ${e.id}: ${e.description} (${e.form_id}, ${e.status})${profileTag} — data: ${(e.data_summary || []).join(', ')}`;
  });

  return `Vault entries (${entries.length}):\n${lines.join('\n')}`;
}

// ── Exports ─────────────────────────────────────────────────────────────────

if (typeof window !== 'undefined') {
  window.Vault = {
    list: vaultList,
    load: vaultLoad,
    save: vaultSave,
    delete: vaultDelete,
    setProfile: vaultSetProfile,
    getActiveProfile: vaultGetActiveProfile,
    buildSummary: vaultBuildSummary,
  };
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    vaultList,
    vaultLoad,
    vaultSave,
    vaultDelete,
    vaultSetProfile,
    vaultGetActiveProfile,
    vaultBuildSummary,
  };
}
