import type { FormSchema } from './schema.js';
import type { InstructionContext } from './api.js';

export type SessionStatus = 'active' | 'submitted' | 'expired';

export interface Session {
  session_id: string;
  form_id: string;
  base_url: string;
  auth_token: string;
  token_expires_at: string;
  schema: FormSchema;
  instructions: InstructionContext;
  current_draft_id: string | null;
  status: SessionStatus;
}
