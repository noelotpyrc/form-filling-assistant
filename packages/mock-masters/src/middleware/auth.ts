import type { Request, Response, NextFunction } from 'express';
import { ErrorCode } from '@form-filling-assistant/shared';
import { store } from '../store.js';

export function authMiddleware(req: Request, res: Response, next: NextFunction): void {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    res.status(401).json({
      error: {
        code: ErrorCode.TOKEN_EXPIRED,
        message: 'Missing or invalid Authorization header. Use: Authorization: Bearer <token>',
      },
    });
    return;
  }

  const token = authHeader.slice(7); // Remove 'Bearer '
  const entry = store.validateToken(token);

  if (!entry) {
    res.status(401).json({
      error: {
        code: ErrorCode.TOKEN_EXPIRED,
        message: 'Token is invalid or expired. Please call /discover to get a new token.',
      },
    });
    return;
  }

  // Attach form_id to request for downstream use
  (req as Request & { formId?: string }).formId = entry.form_id;
  next();
}
