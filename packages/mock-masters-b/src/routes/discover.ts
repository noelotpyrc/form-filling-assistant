import { Router } from 'express';
import { v4 as uuidv4 } from 'uuid';
import type { DiscoverRequest, DiscoverResponse } from '@form-filling-assistant/shared';
import { mastersBSchema } from '../data/schema.js';
import { mastersBInstructions } from '../data/instructions.js';
import { store } from '../store.js';

const router = Router();

router.post('/discover', (req, res) => {
  const body = req.body as DiscoverRequest;

  if (body.agent_id) {
    console.log(`[discover] Agent connected: ${body.agent_id}`);
  }

  const formId = `form_${uuidv4().slice(0, 12)}`;
  const { token, expiresAt } = store.createToken(formId);

  const response: DiscoverResponse = {
    form_id: formId,
    auth_token: token,
    token_expires_at: expiresAt.toISOString(),
    schema: mastersBSchema,
    instructions: mastersBInstructions,
  };

  console.log(`[discover] Created form ${formId}, token expires at ${expiresAt.toISOString()}`);
  res.json(response);
});

export default router;
