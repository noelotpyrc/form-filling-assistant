import fs from 'node:fs';
import path from 'node:path';

// ── Types ──────────────────────────────────────────────────────────────

export interface PersistedDraft {
  draft_id: string;
  form_id: string;
  data: Record<string, unknown>;
  updated_at: string;
}

export interface PersistedSubmission {
  submission_id: string;
  form_id: string;
  data: Record<string, unknown>;
  ref_number: string;
  submitted_at: string;
}

// ── JsonStore ──────────────────────────────────────────────────────────

/**
 * Simple JSON-file persistence for mock server drafts and submissions.
 * Each file is keyed by user email.
 *
 * Storage layout:
 *   <dataDir>/drafts.json       — { [email]: PersistedDraft }
 *   <dataDir>/submissions.json  — { [email]: PersistedSubmission }
 */
export class JsonStore {
  private draftsPath: string;
  private submissionsPath: string;

  constructor(private dataDir: string) {
    this.draftsPath = path.join(dataDir, 'drafts.json');
    this.submissionsPath = path.join(dataDir, 'submissions.json');
    this.ensureDir();
  }

  // ── Email extraction ───────────────────────────────────────────────

  /**
   * Search nested form data for an `email` field in any section.
   * Returns the first email string found, or null.
   */
  extractEmail(data: Record<string, unknown>): string | null {
    for (const section of Object.values(data)) {
      if (section && typeof section === 'object' && !Array.isArray(section)) {
        const sectionObj = section as Record<string, unknown>;
        if (typeof sectionObj.email === 'string' && sectionObj.email) {
          return sectionObj.email;
        }
      }
    }
    // Also check top-level (in case data isn't nested by section)
    if (typeof (data as Record<string, unknown>).email === 'string') {
      return (data as Record<string, unknown>).email as string;
    }
    return null;
  }

  // ── Draft persistence ──────────────────────────────────────────────

  saveDraftToFile(email: string, draft: PersistedDraft): void {
    const all = this.readJson<PersistedDraft>(this.draftsPath);
    all[email] = draft;
    this.writeJson(this.draftsPath, all);
  }

  getDraftByEmail(email: string): PersistedDraft | null {
    const all = this.readJson<PersistedDraft>(this.draftsPath);
    return all[email] || null;
  }

  listDrafts(): Record<string, PersistedDraft> {
    return this.readJson<PersistedDraft>(this.draftsPath);
  }

  // ── Submission persistence ─────────────────────────────────────────

  saveSubmissionToFile(email: string, sub: PersistedSubmission): void {
    const all = this.readJson<PersistedSubmission>(this.submissionsPath);
    all[email] = sub;
    this.writeJson(this.submissionsPath, all);
  }

  getSubmissionByEmail(email: string): PersistedSubmission | null {
    const all = this.readJson<PersistedSubmission>(this.submissionsPath);
    return all[email] || null;
  }

  listSubmissions(): Record<string, PersistedSubmission> {
    return this.readJson<PersistedSubmission>(this.submissionsPath);
  }

  // ── Helpers ────────────────────────────────────────────────────────

  private ensureDir(): void {
    if (!fs.existsSync(this.dataDir)) {
      fs.mkdirSync(this.dataDir, { recursive: true });
    }
  }

  private readJson<T>(filePath: string): Record<string, T> {
    if (!fs.existsSync(filePath)) return {};
    try {
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch {
      return {};
    }
  }

  private writeJson(filePath: string, data: Record<string, unknown>): void {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
  }
}
