import { Router } from 'express';
import multer from 'multer';
import type { UploadFileResponse } from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { mastersSchema } from '../data/schema.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';
import type { FormField } from '@form-filling-assistant/shared';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 }, // 10MB max
});

const router = Router();

/**
 * Find the file field definition from schema, including within group sub-fields.
 */
function findFileField(fieldId: string): FormField | null {
  for (const section of mastersSchema.sections) {
    for (const field of section.fields) {
      if (field.field_id === fieldId && field.type === 'file') {
        return field;
      }
      // Check within group sub-fields
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
    res.status(400).json({
      error: {
        code: ErrorCode.FORM_NOT_FOUND,
        message: 'form_id is required.',
      },
    });
    return;
  }

  if (!fieldId) {
    res.status(400).json({
      error: {
        code: ErrorCode.VALIDATION_FAILED,
        message: 'field_id is required.',
      },
    });
    return;
  }

  if (!req.file) {
    res.status(400).json({
      error: {
        code: ErrorCode.VALIDATION_FAILED,
        message: 'No file provided. Use multipart/form-data with a "file" field.',
      },
    });
    return;
  }

  const fieldDef = findFileField(fieldId);
  if (!fieldDef) {
    res.status(400).json({
      error: {
        code: ErrorCode.VALIDATION_FAILED,
        message: `Unknown file field: ${fieldId}`,
      },
    });
    return;
  }

  // Validate file type
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

  // Validate file size
  const maxBytes = (fieldDef.max_size_mb || 10) * 1024 * 1024;
  if (req.file.size > maxBytes) {
    res.status(400).json({
      error: {
        code: ErrorCode.FILE_TOO_LARGE,
        message: `File size (${(req.file.size / (1024 * 1024)).toFixed(1)}MB) exceeds the ${fieldDef.max_size_mb}MB limit for ${fieldDef.label}.`,
      },
    });
    return;
  }

  // Store file metadata (discard binary)
  const fileId = store.saveFile(fieldId, filename, req.file.size);

  const response: UploadFileResponse = {
    file_id: fileId,
    field_id: fieldId,
    filename,
    size_bytes: req.file.size,
    status: 'accepted',
  };

  console.log(`[upload-file] Accepted ${filename} (${req.file.size} bytes) for field ${fieldId}`);
  res.json(response);
});

export default router;
