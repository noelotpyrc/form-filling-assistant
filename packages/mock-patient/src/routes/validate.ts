import { Router } from 'express';
import type { ValidateRequest, ValidateResponse, ValidationResult } from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { validateField } from '../data/validation-rules.js';
import { authMiddleware } from '../middleware/auth.js';

const router = Router();

router.post('/validate', authMiddleware, (req, res) => {
  const body = req.body as ValidateRequest;

  if (!body.form_id) {
    res.status(400).json({
      error: {
        code: ErrorCode.FORM_NOT_FOUND,
        message: 'form_id is required.',
      },
    });
    return;
  }

  if (!body.fields || !Array.isArray(body.fields)) {
    res.status(400).json({
      error: {
        code: ErrorCode.VALIDATION_FAILED,
        message: 'fields must be an array of { field_id, value } objects.',
      },
    });
    return;
  }

  const results: ValidationResult[] = [];
  for (const f of body.fields) {
    const result = validateField(f.field_id, f.value);
    results.push(result);
  }

  const response: ValidateResponse = { results };
  res.json(response);
});

export default router;
