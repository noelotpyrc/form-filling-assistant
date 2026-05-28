/**
 * Browser-side chat provider abstraction for the form-filling assistant.
 *
 * Provides a pluggable interface for different LLM backends:
 *  - CLIProxyProvider (current) — proxies to a server that wraps Claude CLI
 *  - LocalModelProvider (future) — WASM/WebGPU model running in-browser
 *  - APIProvider (future) — direct Anthropic/OpenAI API calls
 *
 * Exported via window.ChatProvider
 */
(function () {
  'use strict';

  /**
   * CLIProxyProvider — sends prompts to a thin Express server that spawns
   * Claude Code CLI and streams back raw text via SSE.
   *
   * Usage:
   *   var provider = new ChatProvider.CLIProxyProvider('/api/generate');
   *   var ctrl = provider.generate(fullPrompt, resumeSessionId);
   *   ctrl.onText = function (chunk) { ... };
   *   ctrl.onDone = function (info) { ... };  // { sessionId, durationMs, costUsd }
   *   ctrl.onError = function (err) { ... };  // { message }
   *   // To cancel: ctrl.abort();
   *
   * @param {string} endpoint - The proxy endpoint URL (e.g. '/api/generate')
   */
  function CLIProxyProvider(endpoint) {
    this.endpoint = endpoint || '/api/generate';
  }

  /**
   * Send a prompt to the CLI proxy and stream back the response.
   *
   * @param {string} fullPrompt - The complete prompt (system + user message)
   * @param {string} [resumeSessionId] - Claude CLI session ID for multi-turn
   * @returns {{ onText, onDone, onError, abort }}
   */
  CLIProxyProvider.prototype.generate = function (fullPrompt, resumeSessionId) {
    var controller = new AbortController();

    var ctrl = {
      /** @type {function(string):void} Called with each text chunk */
      onText: null,
      /** @type {function({sessionId:string, durationMs:number, costUsd:number}):void} */
      onDone: null,
      /** @type {function({message:string}):void} */
      onError: null,
      /** Cancel the in-flight request */
      abort: function () {
        controller.abort();
      },
    };

    var body = { prompt: fullPrompt };
    if (resumeSessionId) body.resume = resumeSessionId;

    fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(function (response) {
        if (!response.ok) {
          return response.json().then(function (err) {
            throw new Error(err.error || 'HTTP ' + response.status);
          });
        }

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var eventType = null;

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) return;

            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ') && eventType) {
                var data;
                try {
                  data = JSON.parse(line.slice(6));
                } catch (e) {
                  eventType = null;
                  continue;
                }

                switch (eventType) {
                  case 'text':
                    if (ctrl.onText) ctrl.onText(data.text);
                    break;
                  case 'done':
                    if (ctrl.onDone)
                      ctrl.onDone({
                        sessionId: data.session_id,
                        durationMs: data.duration_ms,
                        costUsd: data.cost_usd,
                      });
                    break;
                  case 'error':
                    if (ctrl.onError) ctrl.onError({ message: data.message });
                    break;
                }
                eventType = null;
              }
            }

            return pump();
          });
        }

        return pump();
      })
      .catch(function (err) {
        if (err.name === 'AbortError') return; // user cancelled
        if (ctrl.onError) ctrl.onError({ message: err.message });
      });

    return ctrl;
  };

  // ─────────────────────────────────────────────────────────────────────
  // LocalSFTProvider — drives the local fine-tuned model via the Python
  // harness (tuning/harness/serve.py) running our 5-module DSPy pipeline.
  //
  // Unlike CLIProxyProvider, the harness is stateless: every turn must
  // include form_state, form_schema, and conversation_history. The caller
  // (doGenerate in index.html) supplies these via the third argument.
  //
  // SSE output format is identical, so the consumer is unchanged:
  //   ctrl.onText(chunk)   ctrl.onDone(info)   ctrl.onError(err)
  //
  // @param {string} endpoint - Harness endpoint (default '/api/generate-local')
  // ─────────────────────────────────────────────────────────────────────
  function LocalSFTProvider(endpoint) {
    this.endpoint = endpoint || '/api/generate-local';
  }

  /**
   * @param {string} fullPrompt - Ignored. The harness needs structured input.
   * @param {string} [resumeSessionId] - Ignored. Harness keys on session_id in ctx.
   * @param {object} structuredCtx - { session_id, user_message, form_state, form_schema, conversation_history }
   */
  LocalSFTProvider.prototype.generate = function (fullPrompt, resumeSessionId, structuredCtx) {
    var controller = new AbortController();
    var ctrl = {
      onText: null,
      onDone: null,
      onError: null,
      abort: function () { controller.abort(); },
    };

    if (!structuredCtx) {
      // Defensive — caller forgot to pass structured context.
      setTimeout(function () {
        if (ctrl.onError) ctrl.onError({ message: 'LocalSFTProvider: structuredCtx required' });
      }, 0);
      return ctrl;
    }

    fetch(this.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(structuredCtx),
      signal: controller.signal,
    })
      .then(function (response) {
        if (!response.ok) {
          return response.text().then(function (txt) {
            throw new Error('HTTP ' + response.status + ': ' + txt);
          });
        }

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = '';
        var eventType = null;

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) return;
            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split('\n');
            buffer = lines.pop();

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ') && eventType) {
                var data;
                try { data = JSON.parse(line.slice(6)); }
                catch (e) { eventType = null; continue; }

                switch (eventType) {
                  case 'text':
                    if (ctrl.onText) ctrl.onText(data.text);
                    break;
                  case 'done':
                    if (ctrl.onDone) ctrl.onDone({
                      sessionId: data.session_id,
                      durationMs: data.duration_ms,
                      costUsd: data.cost_usd || 0,
                    });
                    break;
                  case 'error':
                    if (ctrl.onError) ctrl.onError({ message: data.message });
                    break;
                }
                eventType = null;
              } else if (line === '') {
                eventType = null;
              }
            }

            return pump();
          });
        }
        return pump();
      })
      .catch(function (err) {
        if (err.name === 'AbortError') return;
        if (ctrl.onError) ctrl.onError({ message: err.message });
      });

    return ctrl;
  };

  // Mark provider so the caller knows to pass structuredCtx.
  LocalSFTProvider.prototype.requiresStructuredContext = true;

  // ── Export ──
  window.ChatProvider = {
    CLIProxyProvider: CLIProxyProvider,
    LocalSFTProvider: LocalSFTProvider,
  };
})();
