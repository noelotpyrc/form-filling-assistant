import { v4 as uuidv4 } from 'uuid';
import path from 'node:path';
import { JsonStore } from '@form-filling-assistant/shared';

export interface TokenEntry {
  form_id: string;
  expires_at: Date;
}

export interface DraftEntry {
  form_id: string;
  data: Record<string, unknown>;
}

export interface FileEntry {
  field_id: string;
  filename: string;
  size_bytes: number;
}

const dataDir =
  process.env.MOCK_DATA_DIR || path.join(__dirname, '..', 'data');
const jsonStore = new JsonStore(dataDir);

class Store {
  tokens: Map<string, TokenEntry> = new Map();
  drafts: Map<string, DraftEntry> = new Map();
  files: Map<string, FileEntry> = new Map();

  createToken(formId: string): { token: string; expiresAt: Date } {
    const token = uuidv4();
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000); // 1 hour
    this.tokens.set(token, { form_id: formId, expires_at: expiresAt });
    return { token, expiresAt };
  }

  validateToken(token: string): TokenEntry | null {
    const entry = this.tokens.get(token);
    if (!entry) return null;
    if (new Date() > entry.expires_at) {
      this.tokens.delete(token);
      return null;
    }
    return entry;
  }

  saveDraft(formId: string, data: Record<string, unknown>): string {
    // Check for existing draft for this form
    for (const [draftId, draft] of this.drafts.entries()) {
      if (draft.form_id === formId) {
        // Merge data (deep merge section by section)
        for (const key of Object.keys(data)) {
          if (typeof data[key] === 'object' && !Array.isArray(data[key]) && data[key] !== null) {
            draft.data[key] = {
              ...(draft.data[key] as Record<string, unknown> || {}),
              ...(data[key] as Record<string, unknown>),
            };
          } else {
            draft.data[key] = data[key];
          }
        }
        // Persist to JSON
        const email = jsonStore.extractEmail(draft.data);
        if (email) {
          jsonStore.saveDraftToFile(email, {
            draft_id: draftId,
            form_id: formId,
            data: draft.data,
            updated_at: new Date().toISOString(),
          });
        }
        return draftId;
      }
    }
    // Create new draft
    const draftId = `draft_${uuidv4().slice(0, 8)}`;
    this.drafts.set(draftId, { form_id: formId, data });
    // Persist to JSON
    const email = jsonStore.extractEmail(data);
    if (email) {
      jsonStore.saveDraftToFile(email, {
        draft_id: draftId,
        form_id: formId,
        data,
        updated_at: new Date().toISOString(),
      });
    }
    return draftId;
  }

  getDraft(draftId: string): DraftEntry | null {
    return this.drafts.get(draftId) || null;
  }

  getDraftByFormId(formId: string): { draftId: string; draft: DraftEntry } | null {
    for (const [draftId, draft] of this.drafts.entries()) {
      if (draft.form_id === formId) {
        return { draftId, draft };
      }
    }
    return null;
  }

  saveSubmission(
    submissionId: string,
    formId: string,
    data: Record<string, unknown>,
    refNumber: string,
  ): void {
    const email = jsonStore.extractEmail(data);
    if (email) {
      jsonStore.saveSubmissionToFile(email, {
        submission_id: submissionId,
        form_id: formId,
        data,
        ref_number: refNumber,
        submitted_at: new Date().toISOString(),
      });
    }
  }

  saveFile(fieldId: string, filename: string, sizeBytes: number): string {
    const fileId = `file_${uuidv4().slice(0, 8)}`;
    this.files.set(fileId, { field_id: fieldId, filename, size_bytes: sizeBytes });
    return fileId;
  }

  get persistence(): JsonStore {
    return jsonStore;
  }
}

export const store = new Store();
