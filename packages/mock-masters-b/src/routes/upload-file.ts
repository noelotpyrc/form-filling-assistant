import { Router } from 'express';
import multer from 'multer';
import type { UploadFileResponse } from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { mastersBSchema } from '../data/schema.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';
import type { FormField } from '@form-filling-assistant/shared';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
});

const router = Router();

function findFileField(fieldId: string): FormField | null {
  for (const section of mastersBSchema.sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId && field.type === 'file') {
        return field;
      }
      if (field.type === 'group' && field.fields) {
        for (const subField of field.fields) {
          if (subField.field_id === fieldId && subField.type === 'file') {
            return subField;
          }
        }
      }
    }
  }
  return null;
}

router.post('/upload-file', authMiddleware, upload.single('file'), (req, res) => {
  const formId = req.body.form_id as string;
  const fieldId = req.body.field_id as string;

  if (!formId) {
    res.status(400).json({ error: { code: ErrorCode.FORM_NOT_FOUND, message: 'form_id is required.' } });
    return;
  }
  if (!fieldId) {
    res.status(400).json({ error: { code: ErrorCode.VALIDATION_FAILED, message: 'field_id is required.' } });
    return;
  }
  if (!req.file) {
    res.status(400).json({ error: { code: ErrorCode.VALIDATION_FAILED, message: 'No file provided.' } });
    return;
  }

  const fieldDef = findFileField(fieldId);
  if (!fieldDef) {
    res.status(400).json({ error: { code: ErrorCode.VALIDATION_FAILED, message: `Unknown file field: ${fieldId}` } });
    return;
  }

  const filename = req.file.originalname;
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  if (fieldDef.accepted_types && !fieldDef.accepted_types.includes(ext)) {
    res.status(400).json({
      error: {
        code: ErrorCode.UNSUPPORTED_FILE_TYPE,
        message: `File type ".${ext}" is not accepted for ${fieldDef.label}. Accepted: ${fieldDef.accepted_types.join(', ')}.`,
      },
    });
    return;
  }

  const maxBytes = (fieldDef.max_size_mb || 10) * 1024 * 1024;
  if (req.file.size > maxBytes) {
    res.status(400).json({
      error: {
        code: ErrorCode.FILE_TOO_LARGE,
        message: `File size exceeds the ${fieldDef.max_size_mb}MB limit for ${fieldDef.label}.`,
      },
    });
    return;
  }

  const fileId = store.saveFile(fieldId, filename, req.file.size);

  const response: UploadFileResponse = {
    file_id: fileId,
    field_id: fieldId,
    filename,
    size_bytes: req.file.size,
    status: 'accepted',
  };

  console.log(`[upload-file] Accepted ${filename} for field ${fieldId}`);
  res.json(response);
});

export default router;
