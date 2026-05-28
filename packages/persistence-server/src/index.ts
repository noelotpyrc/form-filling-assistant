import express from 'express';
import cors from 'cors';
import path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { JsonStore } from '@form-filling-assistant/shared';

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3005;

// Persistence
const dataDir = process.env.PERSIST_DATA_DIR || path.join(__dirname, '..', 'data');
const store = new JsonStore(dataDir);

app.use(cors());
app.use(express.json());

// ── Health check ──
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' });
});

// ── POST /api/drafts — Upsert a draft ──

app.post('/api/drafts', (req, res) => {
  const { email, form_id, data } = req.body as {
    email?: string;
    form_id?: string;
    data?: Record<string, unknown>;
  };

  if (!email || !form_id || !data) {
    res.status(400).json({ error: 'email, form_id, and data are required' });
    return;
  }

  const existing = store.getDraftByEmail(email);
  const draft_id = existing?.draft_id ?? `draft_${uuidv4().slice(0, 8)}`;
  const updated_at = new Date().toISOString();

  store.saveDraftToFile(email, { draft_id, form_id, data, updated_at });

  res.json({ draft_id, email, updated_at });
});

// ── GET /api/drafts/:email — Get a saved draft ──

app.get('/api/drafts/:email', (req, res) => {
  const { email } = req.params;
  const draft = store.getDraftByEmail(email);

  if (!draft) {
    res.status(404).json({ error: 'No draft found' });
    return;
  }

  res.json(draft);
});

// ── POST /api/submissions — Save a submission ──

app.post('/api/submissions', (req, res) => {
  const { email, form_id, data } = req.body as {
    email?: string;
    form_id?: string;
    data?: Record<string, unknown>;
  };

  if (!email || !form_id || !data) {
    res.status(400).json({ error: 'email, form_id, and data are required' });
    return;
  }

  const submission_id = `sub_${uuidv4().slice(0, 8)}`;
  const ref_number = `APP-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 100000)).padStart(5, '0')}`;
  const submitted_at = new Date().toISOString();

  store.saveSubmissionToFile(email, {
    submission_id,
    form_id,
    data,
    ref_number,
    submitted_at,
  });

  res.json({ submission_id, reference_number: ref_number, submitted_at });
});

// ── Start ──

app.listen(PORT, () => {
  console.log(`\n📦 Persistence Server`);
  console.log(`   http://localhost:${PORT}\n`);
  console.log(`   POST /api/drafts          — save draft`);
  console.log(`   GET  /api/drafts/:email   — get draft`);
  console.log(`   POST /api/submissions     — save submission\n`);
});
