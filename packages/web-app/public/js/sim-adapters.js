/**
 * Simulation Adapters — Browser-side ports of view-renderer.ts and user-action.ts
 * Used by sim.html for the simulation demo page.
 */
var SimAdapters = (function () {

  // ── A→U: View Renderer ──

  function countGroupEntries(groupId, formValues) {
    var prefix = groupId + '-';
    var maxIndex = -1;
    for (var key of Object.keys(formValues)) {
      if (key.startsWith(prefix)) {
        var parts = key.slice(prefix.length).split('-');
        var idx = parseInt(parts[0], 10);
        if (!isNaN(idx) && idx > maxIndex) maxIndex = idx;
      }
    }
    return maxIndex + 1;
  }

  function isConditionMet(field, formValues) {
    if (!field.condition) return true;
    var cond = field.condition;
    var actual = formValues[cond.field_id];
    switch (cond.operator) {
      case 'equals': return actual === cond.value;
      case 'not_equals': return actual !== cond.value;
      case 'in': return Array.isArray(cond.value) && cond.value.includes(actual);
      case 'not_in': return Array.isArray(cond.value) && !cond.value.includes(actual);
      default: return true;
    }
  }

  function hasValue(v) {
    return v !== undefined && v !== null && v !== '';
  }

  function countSectionProgress(section, formValues) {
    var required = 0, filled = 0;
    for (var field of section.fields) {
      if (field.type === 'group' && field.fields) {
        var entryCount = countGroupEntries(field.field_id, formValues);
        var minItems = field.min_items != null ? field.min_items : (field.required ? 1 : 0);
        if (minItems > 0 && entryCount === 0) {
          for (var sf of field.fields) {
            if (sf.required) required++;
          }
        } else {
          for (var i = 0; i < entryCount; i++) {
            for (var sf of field.fields) {
              if (!sf.required) continue;
              if (!isConditionMet(sf, formValues)) continue;
              required++;
              var compositeId = field.field_id + '-' + i + '-' + sf.field_id;
              if (hasValue(formValues[compositeId])) filled++;
            }
          }
        }
      } else {
        if (!field.required) continue;
        if (!isConditionMet(field, formValues)) continue;
        required++;
        if (hasValue(formValues[field.field_id])) filled++;
      }
    }
    return { title: section.title, filled: filled, required: required, complete: required > 0 && filled >= required };
  }

  function flattenFieldLabels(fields) {
    var labels = [];
    for (var f of fields) {
      if (f.type === 'group' && f.fields) {
        for (var sub of f.fields) labels.push(sub.label);
      } else {
        labels.push(f.label);
      }
    }
    return labels;
  }

  /**
   * Render the user's screen view for a single turn.
   * @param {string} assistantText
   * @param {Array} actions - Parsed actions from ActionParser.parseActions()
   * @param {Object} formMeta - { name, schema }
   * @param {Object} formValues
   * @returns {string}
   */
  function renderScreenView(assistantText, actions, formMeta, formValues) {
    var parts = [];

    parts.push('## Assistant Message');
    parts.push((assistantText || '').trim());

    parts.push('');
    parts.push('## Form Panel');

    var sectionProgress = formMeta.schema.sections.map(function (s) {
      return countSectionProgress(s, formValues);
    });
    var totalFilled = sectionProgress.reduce(function (sum, s) { return sum + s.filled; }, 0);
    var totalRequired = sectionProgress.reduce(function (sum, s) { return sum + s.required; }, 0);
    var pct = totalRequired > 0 ? Math.round((totalFilled / totalRequired) * 100) : 0;

    parts.push('Overall progress: ' + totalFilled + '/' + totalRequired + ' required fields (' + pct + '%)');
    for (var sp of sectionProgress) {
      var check = sp.complete ? ' ✓' : '';
      parts.push('- ' + sp.title + ': ' + sp.filled + '/' + sp.required + check);
    }

    for (var action of actions) {
      switch (action.type) {
        case 'ask_choice': {
          var options = action.options;
          if (options && options.length) {
            parts.push('');
            var labels = options.map(function (o) { return '"' + o.label + '"'; }).join(', ');
            parts.push('Choice buttons: [' + labels + ']');
          }
          break;
        }
        case 'show_fields': {
          var sectionRef = action.section || '';
          var section = formMeta.schema.sections.find(function (s) {
            return s.title.toLowerCase() === sectionRef.toLowerCase() ||
              s.section_id.toLowerCase() === sectionRef.toLowerCase();
          });
          if (section) {
            var fieldLabels = flattenFieldLabels(section.fields);
            parts.push('');
            parts.push('Form section "' + section.title + '" is open with fields: ' + fieldLabels.join(', '));
          }
          break;
        }
        case 'show_button': {
          var button = action.button;
          if (button === 'save_draft') {
            parts.push('');
            parts.push('Button available: "Save Draft"');
          } else if (button === 'submit') {
            parts.push('');
            parts.push('Button available: "Submit Application"');
          }
          break;
        }
        case 'show_preview': {
          var sections = action.sections;
          if (sections && sections.length) {
            parts.push('');
            var summaryParts = sections.map(function (s) {
              var fieldStrs = s.fields.map(function (f) { return f.label + ': ' + f.value; }).join(', ');
              return s.title + ' — ' + fieldStrs;
            });
            parts.push('Preview card: ' + summaryParts.join('; '));
          }
          break;
        }
      }
    }

    return parts.join('\n');
  }

  // ── U→A: Action Converter ──

  /**
   * Convert a UserAction from LLM U into the per-turn input for LLM A.
   * @param {Object} userAction - { action, text?, file?, label?, fields? }
   * @param {Object} formState - Current form state (not mutated)
   * @returns {{ userMessage: string|null, formState: Object, stop: boolean }}
   */
  function convertUserAction(userAction, formState) {
    switch (userAction.action) {
      case 'message': {
        var message = userAction.text || '';
        if (userAction.file && userAction.file.filename) {
          var f = userAction.file;
          message = '[File: ' + f.filename + ']\n' + f.content + '\n[End of ' + f.filename + ']\n\n' + message;
        }
        return { userMessage: message, formState: formState, stop: false };
      }
      case 'select_choice':
        return { userMessage: '[system] User selected option: "' + userAction.label + '"', formState: formState, stop: false };
      case 'fill_fields': {
        if (!userAction.fields) return { userMessage: null, formState: formState, stop: false };
        var updated = Object.assign({}, formState, userAction.fields);
        return { userMessage: null, formState: updated, stop: false };
      }
      case 'click_button':
        return { userMessage: null, formState: formState, stop: false };
      case 'stop':
        return { userMessage: null, formState: formState, stop: true };
      default:
        return { userMessage: null, formState: formState, stop: false };
    }
  }

  // ── Multi-action processor ──

  /**
   * Process ALL actions from an LLM U candidate into an execution plan.
   * Pure function — no side effects, no async, no UI updates.
   *
   * Replaces the old "primary + secondary" logic with a single pass that
   * handles every action type and accumulates results.
   *
   * @param {Array} actions - LLM U actions array (from selected candidate)
   * @param {Object} formState - Current form state snapshot (not mutated)
   * @param {string|null} availableButton - Button type from LLM A ('save_draft'|'submit'|null)
   * @returns {{ stop: boolean, fieldEdits: Object, messages: Array, clickButton: string|null }}
   */
  function processActions(actions, formState, availableButton) {
    var plan = {
      stop: false,
      fieldEdits: {},
      messages: [],       // { text: string, isSystem?: boolean, fileKey?: string }
      clickButton: null,  // 'save_draft' | 'submit' | null
    };

    if (!actions || actions.length === 0) return plan;

    for (var i = 0; i < actions.length; i++) {
      var a = actions[i];
      switch (a.action) {
        case 'stop':
          plan.stop = true;
          return plan;

        case 'fill_fields':
          if (a.fields) Object.assign(plan.fieldEdits, a.fields);
          break;

        case 'message': {
          var entry = { text: a.text || '' };
          if (typeof a.file === 'string') entry.fileKey = a.file;
          plan.messages.push(entry);
          break;
        }

        case 'select_choice':
          plan.messages.push({
            text: '[system] User selected option: "' + (a.label || '') + '"',
            isSystem: true,
          });
          break;

        case 'click_button':
          if (availableButton) plan.clickButton = availableButton;
          break;
      }
    }

    return plan;
  }

  /**
   * Build the combined message string for LLM A from processed message entries.
   * Call AFTER resolving file keys — set msg.resolvedFile = { filename, content }.
   *
   * @param {Array} messages - From processActions().messages, with resolvedFile populated
   * @returns {string} Combined message to send to LLM A
   */
  function buildLlmAMessage(messages) {
    var parts = [];
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i];
      var text = m.text;
      if (m.resolvedFile && m.resolvedFile.filename) {
        var f = m.resolvedFile;
        text = '[File: ' + f.filename + ']\n' + f.content + '\n[End of ' + f.filename + ']\n\n' + text;
      }
      parts.push(text);
    }
    return parts.join('\n');
  }

  return {
    renderScreenView: renderScreenView,
    convertUserAction: convertUserAction,
    processActions: processActions,
    buildLlmAMessage: buildLlmAMessage,
  };

})();

// Node.js export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SimAdapters;
}
