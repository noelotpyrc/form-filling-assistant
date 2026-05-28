import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { startServer, type ManagedServer } from './helpers/server-manager.js';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DATA_DIR = path.join(os.tmpdir(), `persist-server-${Date.now()}`);
const PORT = 4030;

let server: ManagedServer;
let baseUrl: string;

beforeAll(async () => {
  server = await startServer('persistence-server', PORT, { PERSIST_DATA_DIR: DATA_DIR });
  baseUrl = server.baseUrl;
});

afterAll(() => {
  server?.kill();
  fs.rmSync(DATA_DIR, { recursive: true, force: true });
});

async function post<T>(endpoint: string, body: unknown): Promise<{ status: number; body: T }> {
  const res = await fetch(`${baseUrl}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = (await res.json()) as T;
  return { status: res.status, body: data };
}

async function get<T>(endpoint: string): Promise<{ status: number; body: T }> {
  const res = await fetch(`${baseUrl}${endpoint}`);
  const data = (await res.json()) as T;
  return { status: res.status, body: data };
}

describe('Persistence Server', () => {
  describe('POST /api/drafts', () => {
    it('saves a draft and returns draft_id', async () => {
      const { status, body } = await post<{ draft_id: string; email: string; updated_at: string }>('/api/drafts', {
        email: 'test@example.com',
        form_id: 'masters-northfield',
        data: { personal: { full_name: 'John Smith' } },
      });

      expect(status).toBe(200);
      expect(body.draft_id).toMatch(/^draft_/);
      expect(body.email).toBe('test@example.com');
      expect(body.updated_at).toBeDefined();
    });

    it('upserts existing draft (same email)', async () => {
      const first = await post<{ draft_id: string }>('/api/drafts', {
        email: 'upsert@example.com',
        form_id: 'test-form',
        data: { name: 'First' },
      });

      const second = await post<{ draft_id: string }>('/api/drafts', {
        email: 'upsert@example.com',
        form_id: 'test-form',
        data: { name: 'Updated' },
      });

      // Same draft_id is reused
      expect(second.body.draft_id).toBe(first.body.draft_id);
    });

    it('returns 400 when email is missing', async () => {
      const { status } = await post<{ error: string }>('/api/drafts', {
        form_id: 'test',
        data: {},
      });
      expect(status).toBe(400);
    });

    it('returns 400 when form_id is missing', async () => {
      const { status } = await post<{ error: string }>('/api/drafts', {
        email: 'test@test.com',
        data: {},
      });
      expect(status).toBe(400);
    });

    it('returns 400 when data is missing', async () => {
      const { status } = await post<{ error: string }>('/api/drafts', {
        email: 'test@test.com',
        form_id: 'test',
      });
      expect(status).toBe(400);
    });
  });

  describe('GET /api/drafts/:email', () => {
    it('returns saved draft by email', async () => {
      // Save a draft first
      await post('/api/drafts', {
        email: 'get-test@example.com',
        form_id: 'masters-northfield',
        data: { personal: { full_name: 'Get Test' } },
      });

      const { status, body } = await get<{
        draft_id: string;
        form_id: string;
        data: { personal: { full_name: string } };
      }>('/api/drafts/get-test@example.com');

      expect(status).toBe(200);
      expect(body.draft_id).toMatch(/^draft_/);
      expect(body.form_id).toBe('masters-northfield');
      expect(body.data.personal.full_name).toBe('Get Test');
    });

    it('returns 404 for unknown email', async () => {
      const { status } = await get<{ error: string }>('/api/drafts/nobody@example.com');
      expect(status).toBe(404);
    });
  });

  describe('POST /api/submissions', () => {
    it('saves a submission and returns reference number', async () => {
      const { status, body } = await post<{
        submission_id: string;
        reference_number: string;
        submitted_at: string;
      }>('/api/submissions', {
        email: 'submit@example.com',
        form_id: 'masters-northfield',
        data: {
          personal: { full_name: 'Submit Test', email: 'submit@example.com' },
          program: { program: 'cs', start_term: 'fall_2026' },
        },
      });

      expect(status).toBe(200);
      expect(body.submission_id).toMatch(/^sub_/);
      expect(body.reference_number).toMatch(/^APP-\d{4}-\d{5}$/);
      expect(body.submitted_at).toBeDefined();
    });

    it('returns 400 when required fields are missing', async () => {
      const { status } = await post<{ error: string }>('/api/submissions', {
        email: 'test@test.com',
        // missing form_id and data
      });
      expect(status).toBe(400);
    });
  });

  describe('JSON file persistence', () => {
    it('creates drafts.json in data directory', () => {
      const draftsPath = path.join(DATA_DIR, 'drafts.json');
      expect(fs.existsSync(draftsPath)).toBe(true);

      const drafts = JSON.parse(fs.readFileSync(draftsPath, 'utf-8'));
      expect(Object.keys(drafts).length).toBeGreaterThanOrEqual(1);
    });

    it('creates submissions.json in data directory', () => {
      const subsPath = path.join(DATA_DIR, 'submissions.json');
      expect(fs.existsSync(subsPath)).toBe(true);

      const subs = JSON.parse(fs.readFileSync(subsPath, 'utf-8'));
      expect(Object.keys(subs).length).toBeGreaterThanOrEqual(1);
    });
  });
});
