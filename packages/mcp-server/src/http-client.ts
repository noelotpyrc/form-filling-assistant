import type { ApiError, ErrorCode, DiscoverResponse } from '@form-filling-assistant/shared';
import { getSession, updateSession } from './session-manager.js';

interface RequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: BodyInit;
}

/**
 * Check whether the auth token for a session has expired by comparing
 * `token_expires_at` with the current time.
 */
export function isTokenExpired(token_expires_at: string): boolean {
  return new Date(token_expires_at) <= new Date();
}

/**
 * Re-discover a session: calls POST /discover on the original base_url to
 * obtain a fresh auth_token, then updates the session in-memory.
 * Returns true if re-discovery succeeded, false otherwise.
 */
async function reDiscover(session_id: string): Promise<boolean> {
  const session = getSession(session_id);
  if (!session) return false;

  // The base_url already points at e.g. http://localhost:3001/ai-agent/v1
  const discoverUrl = `${session.base_url}/discover`;

  try {
    const res = await fetch(discoverUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent_id: 'claude-form-filler-1.0' }),
    });

    if (!res.ok) return false;

    const data = (await res.json()) as DiscoverResponse;

    updateSession(session_id, {
      auth_token: data.auth_token,
      token_expires_at: data.token_expires_at,
      schema: data.schema,
      instructions: data.instructions,
    });

    return true;
  } catch {
    return false;
  }
}

/**
 * Determines whether an API response body is an ApiError with a given code.
 */
function isApiErrorWithCode(body: unknown, code: ErrorCode): boolean {
  if (
    typeof body === 'object' &&
    body !== null &&
    'error' in body
  ) {
    const err = body as ApiError;
    return err.error?.code === code;
  }
  return false;
}

/**
 * Authenticated fetch wrapper.
 *
 * - Adds `Authorization: Bearer {token}` from the session.
 * - Detects TOKEN_EXPIRED responses and triggers re-discovery, then retries once.
 * - Handles RATE_LIMITED with one retry after a 1-second wait.
 * - Wraps network errors with descriptive messages.
 */
export async function authenticatedFetch(
  session_id: string,
  url: string,
  options: RequestOptions = {},
): Promise<{ ok: boolean; status: number; data: unknown }> {
  const session = getSession(session_id);
  if (!session) {
    throw new Error(`Session not found: ${session_id}`);
  }

  // Check if the token has already expired before making the request
  if (isTokenExpired(session.token_expires_at)) {
    const refreshed = await reDiscover(session_id);
    if (!refreshed) {
      throw new Error(
        'Auth token has expired and re-discovery failed. Please discover the form again.',
      );
    }
  }

  // Build the actual request
  const makeRequest = async (): Promise<Response> => {
    const currentSession = getSession(session_id);
    if (!currentSession) {
      throw new Error(`Session not found: ${session_id}`);
    }

    const headers: Record<string, string> = {
      ...options.headers,
      Authorization: `Bearer ${currentSession.auth_token}`,
    };

    // Default to JSON content type for non-multipart requests
    if (!headers['Content-Type'] && typeof options.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }

    return fetch(url, {
      method: options.method ?? 'POST',
      headers,
      body: options.body,
    });
  };

  try {
    let response = await makeRequest();
    let body: unknown;

    // Try to parse the response as JSON
    const text = await response.text();
    try {
      body = JSON.parse(text);
    } catch {
      body = { raw: text };
    }

    // Handle TOKEN_EXPIRED: re-discover and retry once
    if (!response.ok && isApiErrorWithCode(body, 'TOKEN_EXPIRED' as ErrorCode)) {
      const refreshed = await reDiscover(session_id);
      if (!refreshed) {
        throw new Error(
          'Auth token expired and re-discovery failed. Please discover the form again.',
        );
      }
      response = await makeRequest();
      const retryText = await response.text();
      try {
        body = JSON.parse(retryText);
      } catch {
        body = { raw: retryText };
      }
    }

    // Handle RATE_LIMITED: wait 1s and retry once
    if (!response.ok && isApiErrorWithCode(body, 'RATE_LIMITED' as ErrorCode)) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      response = await makeRequest();
      const retryText = await response.text();
      try {
        body = JSON.parse(retryText);
      } catch {
        body = { raw: retryText };
      }
    }

    return {
      ok: response.ok,
      status: response.status,
      data: body,
    };
  } catch (err) {
    if (err instanceof Error && err.message.includes('Session not found')) {
      throw err;
    }
    if (err instanceof Error && (err.message.includes('re-discovery failed') || err.message.includes('expired'))) {
      throw err;
    }
    // Network / connection errors
    const message =
      err instanceof Error ? err.message : 'Unknown network error';
    throw new Error(
      `Network error while contacting the website API: ${message}. Please check that the website is running and try again.`,
    );
  }
}
