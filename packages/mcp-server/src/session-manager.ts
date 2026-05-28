import crypto from 'node:crypto';
import type { Session, FormSchema, InstructionContext } from '@form-filling-assistant/shared';

export interface CreateSessionParams {
  form_id: string;
  base_url: string;
  auth_token: string;
  token_expires_at: string;
  schema: FormSchema;
  instructions: InstructionContext;
}

const sessions = new Map<string, Session>();

export function createSession(params: CreateSessionParams): Session {
  const session_id = crypto.randomUUID();
  const session: Session = {
    session_id,
    form_id: params.form_id,
    base_url: params.base_url,
    auth_token: params.auth_token,
    token_expires_at: params.token_expires_at,
    schema: params.schema,
    instructions: params.instructions,
    current_draft_id: null,
    status: 'active',
  };
  sessions.set(session_id, session);
  return session;
}

export function getSession(session_id: string): Session | undefined {
  return sessions.get(session_id);
}

export function updateSession(
  session_id: string,
  updates: Partial<Omit<Session, 'session_id'>>,
): Session {
  const session = sessions.get(session_id);
  if (!session) {
    throw new Error(`Session not found: ${session_id}`);
  }
  const updated = { ...session, ...updates };
  sessions.set(session_id, updated);
  return updated;
}

export function deleteSession(session_id: string): boolean {
  return sessions.delete(session_id);
}
