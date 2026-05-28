import { Router } from 'express';
import { v4 as uuidv4 } from 'uuid';
import type { SubmitFinalRequest, SubmitFinalResponse } from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { validateField, checkConditionalRequirements } from '../data/validation-rules.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';

const ALWAYS_REQUIRED = [
  'full_name', 'dob', 'sex_at_birth', 'email', 'phone', 'address',
  'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
  'has_insurance', 'visit_reason', 'conditions', 'allergies_exist',
  'takes_medications', 'takes_supplements', 'immunization_status',
  'tobacco_use', 'alcohol_use', 'recreational_drugs', 'exercise_frequency',
  'consent_treatment', 'consent_privacy', 'signature_name', 'signature_date',
];

function getFieldValue(fieldId: string, data: Record<string, unknown>): unknown {
  for (const sectionKey of Object.keys(data)) {
    const sectionData = data[sectionKey];
    if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      const val = (sectionData as Record<string, unknown>)[fieldId];
      if (val !== undefined) return val;
    }
  }
  return undefined;
}

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

  const errors: Array<{ field_id: string; message: string }> = [];

  // Check always-required fields
  for (const fieldId of ALWAYS_REQUIRED) {
    const value = getFieldValue(fieldId, draft.data);
    if (value === undefined || value === null || value === '') {
      errors.push({ field_id: fieldId, message: `${fieldId} is required.` });
    }
  }

  // Check conditional requirements
  const condWarnings = checkConditionalRequirements(draft.data);
  for (const w of condWarnings) {
    errors.push({ field_id: w.field_id, message: w.message });
  }

  // Validate consent fields
  const consentFields = ['consent_treatment', 'consent_privacy', 'consent_billing', 'signature_name', 'signature_date'];
  for (const fieldId of consentFields) {
    const value = getFieldValue(fieldId, draft.data);
    if (value !== undefined && value !== null && value !== '') {
      const result = validateField(fieldId, value, draft.data);
      if (!result.valid) {
        // Only add if not already in errors
        if (!errors.some((e) => e.field_id === fieldId)) {
          errors.push({ field_id: fieldId, message: result.error || `${fieldId} validation failed.` });
        }
      }
    }
  }

  if (errors.length > 0) {
    const response: SubmitFinalResponse = {
      submission_id: '',
      status: 'rejected',
      errors,
    };
    res.status(422).json(response);
    return;
  }

  const submissionId = `sub_${new Date().toISOString().slice(0, 10).replace(/-/g, '')}_${uuidv4().slice(0, 6)}`;
  const refNumber = `PTI-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 99999)).padStart(5, '0')}`;

  const response: SubmitFinalResponse = {
    submission_id: submissionId,
    status: 'submitted',
    confirmation: {
      message: 'Your patient intake form for Riverside Family Medical has been submitted successfully.',
      reference_number: refNumber,
      next_steps: [
        'You will receive a confirmation email shortly.',
        'Please arrive 15 minutes before your scheduled appointment.',
        'Bring a photo ID and your insurance card (if applicable).',
        `Your intake reference number is ${refNumber}.`,
      ],
    },
  };

  store.saveSubmission(submissionId, draft.form_id, draft.data, refNumber);
  console.log(`[submit-final] Submission ${submissionId} accepted. Reference: ${refNumber}`);
  res.json(response);
});

export default router;
