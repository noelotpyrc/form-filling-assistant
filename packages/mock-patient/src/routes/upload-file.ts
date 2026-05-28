import { Router } from 'express';
import multer from 'multer';
import { ErrorCode } from '@form-filling-assistant/shared';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 5 * 1024 * 1024 }, // 5MB
});

const ACCEPTED_TYPES: Record<string, string[]> = {
  insurance_card: ['jpg', 'jpeg', 'png', 'pdf'],
};

const router = Router();

router.post('/upload-file', authMiddleware, upload.single('file'), (req, res) => {
  const fieldId = req.body?.field_id as string | undefined;
  const formId = req.body?.form_id as string | undefined;

  if (!formId) {
    res.status(400).json({
      error: { code: ErrorCode.FORM_NOT_FOUND, message: 'form_id is required.' },
    });
    return;
  }

  if (!fieldId) {
    res.status(400).json({
      error: { code: ErrorCode.VALIDATION_FAILED, message: 'field_id is required.' },
    });
    return;
  }

  if (!req.file) {
    res.status(400).json({
      error: { code: ErrorCode.VALIDATION_FAILED, message: 'No file provided.' },
    });
    return;
  }

  // Check file type
  const ext = req.file.originalname.split('.').pop()?.toLowerCase() ?? '';
  const allowed = ACCEPTED_TYPES[fieldId] ?? ['jpg', 'jpeg', 'png', 'pdf'];
  if (!allowed.includes(ext)) {
    res.status(400).json({
      error: {
        code: ErrorCode.UNSUPPORTED_FILE_TYPE,
        message: `Unsupported file type ".${ext}". Accepted: ${allowed.join(', ')}.`,
      },
    });
    return;
  }

  // Check file size
  if (req.file.size > 5 * 1024 * 1024) {
    res.status(400).json({
      error: {
        code: ErrorCode.FILE_TOO_LARGE,
        message: 'File exceeds maximum size of 5MB.',
      },
    });
    return;
  }

  const fileId = store.saveFile(fieldId, req.file.originalname, req.file.size);

  console.log(`[upload-file] Saved file ${fileId}: ${req.file.originalname} (${req.file.size} bytes) for field ${fieldId}`);
  res.json({
    file_id: fileId,
    field_id: fieldId,
    filename: req.file.originalname,
    size_bytes: req.file.size,
    status: 'accepted',
  });
});

export default router;
