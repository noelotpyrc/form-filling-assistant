import { describe, it, expect } from 'vitest';

/**
 * SSE line-parsing logic extracted from chat-provider.js (lines 73-114).
 *
 * The actual code uses fetch + ReadableStream which can't run in Node/JSDOM.
 * This replicates the exact buffer/split/dispatch algorithm so we can test it
 * with raw string chunks.
 */
function createSSEParser() {
  let buffer = '';
  let eventType: string | null = null;

  const calls: {
    onText: string[];
    onDone: Array<{ sessionId: string; durationMs: number; costUsd: number }>;
    onError: Array<{ message: string }>;
  } = {
    onText: [],
    onDone: [],
    onError: [],
  };

  function feedChunk(chunk: string) {
    buffer += chunk;
    const lines = buffer.split('\n');
    buffer = lines.pop()!; // keep incomplete line

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith('data: ') && eventType) {
        let data: Record<string, unknown>;
        try {
          data = JSON.parse(line.slice(6));
        } catch {
          eventType = null;
          continue;
        }

        switch (eventType) {
          case 'text':
            calls.onText.push(data.text as string);
            break;
          case 'done':
            calls.onDone.push({
              sessionId: data.session_id as string,
              durationMs: data.duration_ms as number,
              costUsd: data.cost_usd as number,
            });
            break;
          case 'error':
            calls.onError.push({ message: data.message as string });
            break;
        }
        eventType = null;
      }
    }
  }

  return { feedChunk, calls, getBuffer: () => buffer };
}

describe('SSE Parser (extracted from chat-provider.js)', () => {
  it('parses a single text event', () => {
    const parser = createSSEParser();
    parser.feedChunk('event: text\ndata: {"text":"hello"}\n\n');
    expect(parser.calls.onText).toEqual(['hello']);
  });

  it('parses a done event with field name mapping', () => {
    const parser = createSSEParser();
    parser.feedChunk(
      'event: done\ndata: {"session_id":"s1","duration_ms":1234,"cost_usd":0.05}\n\n',
    );
    expect(parser.calls.onDone).toEqual([
      { sessionId: 's1', durationMs: 1234, costUsd: 0.05 },
    ]);
  });

  it('parses an error event', () => {
    const parser = createSSEParser();
    parser.feedChunk('event: error\ndata: {"message":"something broke"}\n\n');
    expect(parser.calls.onError).toEqual([{ message: 'something broke' }]);
  });

  it('parses multiple events in one chunk', () => {
    const parser = createSSEParser();
    parser.feedChunk(
      'event: text\ndata: {"text":"a"}\n\nevent: text\ndata: {"text":"b"}\n\n',
    );
    expect(parser.calls.onText).toEqual(['a', 'b']);
  });

  it('reassembles event split across two chunks', () => {
    const parser = createSSEParser();
    parser.feedChunk('event: text\nda');
    expect(parser.calls.onText).toEqual([]);
    parser.feedChunk('ta: {"text":"hi"}\n\n');
    expect(parser.calls.onText).toEqual(['hi']);
  });

  it('skips malformed JSON silently', () => {
    const parser = createSSEParser();
    parser.feedChunk('event: text\ndata: {bad json}\n\n');
    expect(parser.calls.onText).toEqual([]);
    expect(parser.calls.onError).toEqual([]);
  });

  it('skips data line without preceding event type', () => {
    const parser = createSSEParser();
    parser.feedChunk('data: {"text":"orphan"}\n\n');
    expect(parser.calls.onText).toEqual([]);
  });

  it('handles empty lines between events correctly', () => {
    const parser = createSSEParser();
    parser.feedChunk(
      'event: text\ndata: {"text":"first"}\n\nevent: text\ndata: {"text":"second"}\n\n',
    );
    expect(parser.calls.onText).toEqual(['first', 'second']);
  });

  it('keeps trailing incomplete line in buffer', () => {
    const parser = createSSEParser();
    parser.feedChunk('event: text\ndata: {"text":"part');
    expect(parser.calls.onText).toEqual([]);
    expect(parser.getBuffer()).toBe('data: {"text":"part');
  });

  it('maps done event snake_case fields to camelCase', () => {
    const parser = createSSEParser();
    parser.feedChunk(
      'event: done\ndata: {"session_id":"abc-123","duration_ms":5000,"cost_usd":0.12}\n\n',
    );
    const done = parser.calls.onDone[0];
    expect(done.sessionId).toBe('abc-123');
    expect(done.durationMs).toBe(5000);
    expect(done.costUsd).toBe(0.12);
  });
});
