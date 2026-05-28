/**
 * Browser-side structured logger for the form-filling assistant.
 *
 * Writes JSONL-style log entries to IndexedDB for debugging and
 * model training data collection. Works entirely in the browser —
 * no server dependency.
 *
 * IndexedDB store: "form-filling-logs"
 *   Object store: "entries" (autoIncrement key)
 *   Indexes: session_id, type, ts
 *
 * Log entry types:
 *   session_start  — form selected
 *   user_message   — user sends a message
 *   model_input    — before calling chat provider
 *   model_output   — after response complete
 *   error          — any error
 *   form_state_update — fields changed
 *
 * Exported via window.Logger
 */
(function () {
  'use strict';

  var DB_NAME = 'form-filling-logs';
  var STORE_NAME = 'entries';
  var DB_VERSION = 1;

  /** @type {IDBDatabase|null} */
  var db = null;

  /** @type {Promise<IDBDatabase>} */
  var dbReady = openDB();

  /**
   * Open (or create) the IndexedDB database.
   * @returns {Promise<IDBDatabase>}
   */
  function openDB() {
    return new Promise(function (resolve, reject) {
      var request = indexedDB.open(DB_NAME, DB_VERSION);

      request.onupgradeneeded = function (event) {
        var database = event.target.result;
        if (!database.objectStoreNames.contains(STORE_NAME)) {
          var store = database.createObjectStore(STORE_NAME, {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('session_id', 'session_id', { unique: false });
          store.createIndex('type', 'type', { unique: false });
          store.createIndex('ts', 'ts', { unique: false });
        }
      };

      request.onsuccess = function (event) {
        db = event.target.result;
        resolve(db);
      };

      request.onerror = function (event) {
        console.error('[logger] Failed to open IndexedDB:', event.target.error);
        reject(event.target.error);
      };
    });
  }

  /**
   * Write a log entry to IndexedDB.
   *
   * @param {string} sessionId - The current session ID
   * @param {string} type - Log entry type
   * @param {object} data - Additional fields for this entry
   * @returns {Promise<number>} The auto-generated entry ID
   */
  function log(sessionId, type, data) {
    var entry = Object.assign({}, data, {
      session_id: sessionId,
      type: type,
      ts: new Date().toISOString(),
    });

    return dbReady.then(function (database) {
      return new Promise(function (resolve, reject) {
        var tx = database.transaction(STORE_NAME, 'readwrite');
        var store = tx.objectStore(STORE_NAME);
        var request = store.add(entry);

        request.onsuccess = function () {
          resolve(request.result);
        };

        request.onerror = function (event) {
          console.error('[logger] Failed to write log entry:', event.target.error);
          reject(event.target.error);
        };
      });
    });
  }

  // ── Convenience methods ──

  function sessionStart(sessionId, formId, formName) {
    return log(sessionId, 'session_start', {
      form_id: formId,
      form_name: formName,
    });
  }

  function userMessage(sessionId, message, role) {
    return log(sessionId, 'user_message', {
      message: message,
      role: role || 'user',
    });
  }

  function modelInput(sessionId, data) {
    return log(sessionId, 'model_input', {
      full_prompt_length: data.fullPromptLength,
      prompt_hash: data.promptHash || null,
      user_message: data.userMessage,
      form_state_snapshot: data.formStateSnapshot || null,
    });
  }

  function modelOutput(sessionId, data) {
    return log(sessionId, 'model_output', {
      raw_text: data.rawText,
      parsed_actions: data.parsedActions,
      duration_ms: data.durationMs,
      cost_usd: data.costUsd,
      claude_session_id: data.claudeSessionId || null,
    });
  }

  function error(sessionId, message, context) {
    return log(sessionId, 'error', {
      message: message,
      context: context || null,
    });
  }

  function formStateUpdate(sessionId, fieldUpdates, source) {
    return log(sessionId, 'form_state_update', {
      field_updates: fieldUpdates,
      source: source || 'model',
    });
  }

  // ── Query / Export ──

  /**
   * Get all log entries for a given session, ordered by timestamp.
   *
   * @param {string} sessionId
   * @returns {Promise<Array<object>>}
   */
  function getSession(sessionId) {
    return dbReady.then(function (database) {
      return new Promise(function (resolve, reject) {
        var tx = database.transaction(STORE_NAME, 'readonly');
        var store = tx.objectStore(STORE_NAME);
        var index = store.index('session_id');
        var request = index.getAll(sessionId);

        request.onsuccess = function () {
          var entries = request.result || [];
          entries.sort(function (a, b) {
            return a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0;
          });
          resolve(entries);
        };

        request.onerror = function (event) {
          reject(event.target.error);
        };
      });
    });
  }

  /**
   * Export a session's log entries as a JSONL string (one JSON object per line).
   * Useful for downloading as training data.
   *
   * @param {string} sessionId
   * @returns {Promise<string>} JSONL string
   */
  function exportSession(sessionId) {
    return getSession(sessionId).then(function (entries) {
      return entries
        .map(function (entry) {
          // Remove the auto-increment id for clean export
          var clean = Object.assign({}, entry);
          delete clean.id;
          return JSON.stringify(clean);
        })
        .join('\n');
    });
  }

  /**
   * List all unique session IDs in the log store.
   *
   * @returns {Promise<Array<string>>}
   */
  function listSessions() {
    return dbReady.then(function (database) {
      return new Promise(function (resolve, reject) {
        var tx = database.transaction(STORE_NAME, 'readonly');
        var store = tx.objectStore(STORE_NAME);
        var index = store.index('session_id');
        var request = index.openKeyCursor(null, 'nextunique');
        var sessionIds = [];

        request.onsuccess = function (event) {
          var cursor = event.target.result;
          if (cursor) {
            sessionIds.push(cursor.key);
            cursor.continue();
          } else {
            resolve(sessionIds);
          }
        };

        request.onerror = function (event) {
          reject(event.target.error);
        };
      });
    });
  }

  /**
   * Delete all log entries for a specific session.
   *
   * @param {string} sessionId
   * @returns {Promise<void>}
   */
  function deleteSession(sessionId) {
    return getSession(sessionId).then(function (entries) {
      return dbReady.then(function (database) {
        return new Promise(function (resolve, reject) {
          var tx = database.transaction(STORE_NAME, 'readwrite');
          var store = tx.objectStore(STORE_NAME);
          entries.forEach(function (e) {
            store.delete(e.id);
          });
          tx.oncomplete = function () { resolve(); };
          tx.onerror = function (event) { reject(event.target.error); };
        });
      });
    });
  }

  /**
   * Clear all log entries (for development/testing).
   *
   * @returns {Promise<void>}
   */
  function clearAll() {
    return dbReady.then(function (database) {
      return new Promise(function (resolve, reject) {
        var tx = database.transaction(STORE_NAME, 'readwrite');
        var store = tx.objectStore(STORE_NAME);
        var request = store.clear();

        request.onsuccess = function () {
          resolve();
        };

        request.onerror = function (event) {
          reject(event.target.error);
        };
      });
    });
  }

  // ── Export ──
  window.Logger = {
    log: log,
    sessionStart: sessionStart,
    userMessage: userMessage,
    modelInput: modelInput,
    modelOutput: modelOutput,
    error: error,
    formStateUpdate: formStateUpdate,
    getSession: getSession,
    exportSession: exportSession,
    listSessions: listSessions,
    deleteSession: deleteSession,
    clearAll: clearAll,
  };
})();
