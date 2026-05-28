/**
 * NDJSON (Newline-Delimited JSON) stream parser.
 *
 * Reads a Node.js Readable stream and yields parsed JSON objects,
 * handling line buffering for incomplete chunks.
 */

import type { Readable } from 'node:stream';

/**
 * Parse a Readable stream of NDJSON (one JSON object per line).
 *
 * Handles:
 * - Buffering incomplete lines across data chunks
 * - Skipping empty lines
 * - Skipping unparseable lines (debug output from the CLI)
 *
 * @param stream - A readable stream (typically process.stdout)
 * @yields Parsed JSON objects, one per line
 */
export async function* parseNdjsonStream(stream: Readable): AsyncGenerator<unknown> {
  let buffer = '';

  for await (const chunk of stream) {
    buffer += (chunk as Buffer).toString();

    // Split on newlines, keeping the last (possibly incomplete) segment in buffer
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;

      try {
        yield JSON.parse(trimmed);
      } catch {
        // Skip unparseable lines (e.g. debug output, warnings)
      }
    }
  }

  // Process any remaining data in the buffer after stream ends
  const remaining = buffer.trim();
  if (remaining) {
    try {
      yield JSON.parse(remaining);
    } catch {
      // ignore
    }
  }
}
