import { Router } from 'express';
import type {
  SubmitDraftRequest,
  SubmitDraftResponse,
  PreviewSection,
  DraftWarning,
  Completeness,
  DraftAlert,
  FormField,
} from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { patientIntakeSchema } from '../data/schema.js';
import { checkForUrgentSymptoms, checkConditionalRequirements } from '../data/validation-rules.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';

const router = Router();

// Top-level required fields (always required regardless of conditions)
const ALWAYS_REQUIRED = [
  'full_name', 'dob', 'sex_at_birth', 'email', 'phone', 'address',
  'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
  'has_insurance', 'visit_reason', 'conditions', 'allergies_exist',
  'takes_medications', 'takes_supplements', 'immunization_status',
  'tobacco_use', 'alcohol_use', 'recreational_drugs', 'exercise_frequency',
  'consent_treatment', 'consent_privacy', 'signature_name', 'signature_date',
];

function getFieldValue(fieldId: string, data: Record<string, unknown>): unknown {
  for (const sectionKey of Object.keys(data)) {
    const sectionData = data[sectionKey];
    if (sectionData && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      const val = (sectionData as Record<string, unknown>)[fieldId];
      if (val !== undefined) return val;
    }
  }
  return undefined;
}

function formatValue(field: FormField, value: unknown): string {
  if (value === undefined || value === null || value === '') return '(not provided)';
  switch (field.type) {
    case 'boolean': return value === true ? 'Yes' : 'No';
    case 'select': {
      if (field.options) {
        const opt = field.options.find((o) => typeof o === 'string' ? o === value : o.value === value);
        if (opt) return typeof opt === 'string' ? opt : opt.label;
      }
      return String(value);
    }
    case 'multi_select': {
      if (Array.isArray(value)) return value.join(', ');
      return String(value);
    }
    case 'group': {
      if (Array.isArray(value)) return `${value.length} item(s)`;
      return String(value);
    }
    case 'file': {
      if (typeof value === 'object' && value !== null && 'filename' in value) {
        return (value as { filename: string }).filename;
      }
      return String(value);
    }
    default: return String(value);
  }
}

function buildPreview(data: Record<string, unknown>): PreviewSection[] {
  const sections: PreviewSection[] = [];

  for (const section of patientIntakeSchema.sections) {
    const sectionData = data[section.section_id] as Record<string, unknown> | undefined;
    if (!sectionData) continue;

    const fields: Array<{ label: string; value: string }> = [];

    for (const field of section.fields) {
      if (field.type === 'group') {
        const groupVal = sectionData[field.field_id];
        if (Array.isArray(groupVal)) {
          for (let i = 0; i < groupVal.length; i++) {
            const item = groupVal[i] as Record<string, unknown>;
            if (field.fields) {
              for (const subField of field.fields) {
                const subVal = item[subField.field_id];
                if (subVal !== undefined && subVal !== null && subVal !== '') {
                  fields.push({
                    label: `${field.label} #${i + 1} - ${subField.label}`,
                    value: formatValue(subField, subVal),
                  });
                }
              }
            }
          }
        }
      } else {
        const val = sectionData[field.field_id];
        if (val !== undefined && val !== null && val !== '') {
          fields.push({ label: field.label, value: formatValue(field, val) });
        }
      }
    }

    if (fields.length > 0) {
      sections.push({ title: section.title, fields });
    }
  }

  return sections;
}

router.post('/submit-draft', authMiddleware, (req, res) => {
  const body = req.body as SubmitDraftRequest;

  if (!body.form_id) {
    res.status(400).json({
      error: { code: ErrorCode.FORM_NOT_FOUND, message: 'form_id is required.' },
    });
    return;
  }

  if (!body.data || typeof body.data !== 'object') {
    res.status(400).json({
      error: { code: ErrorCode.VALIDATION_FAILED, message: 'data must be an object with section keys.' },
    });
    return;
  }

  const draftId = store.saveDraft(body.form_id, body.data as Record<string, unknown>);
  const draft = store.getDraft(draftId);
  const allData = draft?.data ?? body.data;

  const preview = buildPreview(allData as Record<string, unknown>);

  // Compute completeness from always-required fields
  let filledCount = 0;
  const warnings: DraftWarning[] = [];

  for (const fieldId of ALWAYS_REQUIRED) {
    const value = getFieldValue(fieldId, allData as Record<string, unknown>);
    if (value !== undefined && value !== null && value !== '') {
      filledCount++;
    } else {
      let label = fieldId;
      for (const section of patientIntakeSchema.sections) {
        for (const field of section.fields) {
          if (field.field_id === fieldId) { label = field.label; break; }
        }
      }
      warnings.push({ field_id: fieldId, message: `${label} is required but not yet provided.` });
    }
  }

  // Add conditional requirement warnings
  const conditionalWarnings = checkConditionalRequirements(allData as Record<string, unknown>);
  for (const w of conditionalWarnings) {
    warnings.push({ field_id: w.field_id, message: w.message });
  }

  const totalRequired = ALWAYS_REQUIRED.length + conditionalWarnings.length;
  const completeness: Completeness = {
    required_filled: filledCount,
    required_total: totalRequired,
    percentage: totalRequired > 0 ? Math.round((filledCount / totalRequired) * 100) : 100,
  };

  // Check for urgent symptoms
  const urgentAlerts = checkForUrgentSymptoms(allData as Record<string, unknown>);
  const alerts: DraftAlert[] = urgentAlerts.map((a) => ({
    severity: a.severity,
    message: a.message,
    field_id: a.field_id,
  }));

  const response: SubmitDraftResponse = {
    draft_id: draftId,
    status: 'draft',
    preview: { sections: preview },
    warnings,
    completeness,
    ...(alerts.length > 0 ? { alerts } : {}),
  };

  console.log(`[submit-draft] Draft ${draftId} saved. Completeness: ${completeness.percentage}%`);
  if (alerts.length > 0) {
    console.log(`[submit-draft] ⚠️  ${alerts.length} urgent alert(s) detected!`);
  }
  res.json(response);
});

export default router;
