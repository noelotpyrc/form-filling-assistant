/**
 * Browser-side action parser for the form-filling assistant.
 *
 * Parses the actions block from the model's streamed text response.
 * The model outputs text + an optional ---actions--- delimiter followed
 * by a JSON array of action objects.
 *
 * Exported via window.ActionParser
 */
(function () {
  'use strict';

  var ACTIONS_DELIMITER = '---actions---';

  /**
   * Parse the actions block from a model response string.
   *
   * Expected format:
   *   Some conversational text here...
   *
   *   ---actions---
   *   ```json
   *   [{ "type": "set_fields", "fields": [...] }]
   *   ```
   *
   * @param {string} response - The full model response text
   * @returns {Array<{type: string}>} Parsed action objects
   */
  function parseActions(response) {
    var delimiterIndex = response.indexOf(ACTIONS_DELIMITER);
    if (delimiterIndex === -1) return [];

    var actionsBlock = response.slice(delimiterIndex + ACTIONS_DELIMITER.length).trim();

    // Try to extract JSON from the actions block
    var jsonStr = actionsBlock;

    // Remove markdown code fences if present
    var jsonFenceMatch = jsonStr.match(/```(?:json)?\s*\n?([\s\S]*?)```/);
    if (jsonFenceMatch) {
      jsonStr = jsonFenceMatch[1].trim();
    }

    // Also try just stripping leading/trailing backticks
    jsonStr = jsonStr.replace(/^```(?:json)?/gm, '').replace(/```$/gm, '').trim();

    try {
      var parsed = JSON.parse(jsonStr);
      if (Array.isArray(parsed)) {
        return parsed.filter(function (a) {
          return a && typeof a === 'object' && typeof a.type === 'string';
        });
      }
      // Single action object
      if (parsed && typeof parsed === 'object' && typeof parsed.type === 'string') {
        return [parsed];
      }
      return [];
    } catch (e) {
      console.warn('[action-parser] Failed to parse actions JSON:', jsonStr.slice(0, 200));
      return [];
    }
  }

  /**
   * Extract just the text portion (before the actions delimiter) from a response.
   *
   * @param {string} response - The full model response text
   * @returns {string} The conversational text only
   */
  function extractText(response) {
    var delimiterIndex = response.indexOf(ACTIONS_DELIMITER);
    if (delimiterIndex === -1) return response;
    return response.slice(0, delimiterIndex).trim();
  }

  /**
   * Check if text contains the actions delimiter.
   * Used during streaming to know when to stop sending text to the UI.
   *
   * @param {string} text - Text to check
   * @returns {boolean}
   */
  function containsActionsDelimiter(text) {
    return text.includes(ACTIONS_DELIMITER);
  }

  // ── Export ──
  window.ActionParser = {
    parseActions: parseActions,
    extractText: extractText,
    containsActionsDelimiter: containsActionsDelimiter,
  };
})();
