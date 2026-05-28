import { Router } from 'express';
import { v4 as uuidv4 } from 'uuid';
import type { SubmitFinalRequest, SubmitFinalResponse } from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { validateAllFields } from '../data/validation-rules.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';

const router = Router();

router.post('/submit-final', authMiddleware, (req, res) => {
  const body = req.body as SubmitFinalRequest;

  if (!body.form_id) {
    res.status(400).json({
      error: { code: ErrorCode.FORM_NOT_FOUND, message: 'form_id is required.' },
    });
    return;
  }

  if (!body.draft_id) {
    res.status(400).json({
      error: { code: ErrorCode.INCOMPLETE_SUBMISSION, message: 'draft_id is required. Please submit a draft first.' },
    });
    return;
  }

  const draft = store.getDraft(body.draft_id);
  if (!draft) {
    res.status(404).json({
      error: { code: ErrorCode.FORM_NOT_FOUND, message: `Draft not found: ${body.draft_id}.` },
    });
    return;
  }

  if (draft.form_id !== body.form_id) {
    res.status(400).json({
      error: { code: ErrorCode.FORM_NOT_FOUND, message: 'draft_id does not match form_id.' },
    });
    return;
  }

  const errors = validateAllFields(draft.data);

  if (errors.length > 0) {
    const response: SubmitFinalResponse = {
      submission_id: '',
      status: 'rejected',
      errors: errors.map((e) => ({
        field_id: e.field_id,
        message: e.error || `${e.field_id} is invalid.`,
      })),
    };
    res.status(422).json(response);
    return;
  }

  const submissionId = `sub_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${uuidv4().slice(0, 6)}`;
  const refNumber = `WBI-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 99999)).padStart(5, '0')}`;

  const response: SubmitFinalResponse = {
    submission_id: submissionId,
    status: 'submitted',
    confirmation: {
      message: 'Your application to Westbrook Institute Research MS in AI has been submitted successfully.',
      reference_number: refNumber,
      next_steps: [
        'You will receive a confirmation email within 24 hours.',
        'Application review takes 6-8 weeks.',
        `Track your status at https://apply.westbrook.edu/status/${refNumber}`,
      ],
    },
  };

  store.saveSubmission(submissionId, draft.form_id, draft.data, refNumber);
  console.log(`[submit-final] Submission ${submissionId} accepted. Reference: ${refNumber}`);
  res.json(response);
});

export default router;
