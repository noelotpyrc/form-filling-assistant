import { Router } from 'express';
import { store } from '../store.js';

const router = Router();

router.get('/drafts', (req, res) => {
  const email = req.query.email as string | undefined;

  if (!email) {
    // List all drafts
    const all = store.persistence.listDrafts();
    res.json({ drafts: all });
    return;
  }

  const draft = store.persistence.getDraftByEmail(email);
  if (!draft) {
    res.status(404).json({ error: `No draft found for email: ${email}` });
    return;
  }

  res.json(draft);
});

router.get('/submissions', (req, res) => {
  const email = req.query.email as string | undefined;

  if (!email) {
    // List all submissions
    const all = store.persistence.listSubmissions();
    res.json({ submissions: all });
    return;
  }

  const submission = store.persistence.getSubmissionByEmail(email);
  if (!submission) {
    res.status(404).json({ error: `No submission found for email: ${email}` });
    return;
  }

  res.json(submission);
});

export default router;
