import { Router } from 'express';
import type {
  SubmitDraftRequest,
  SubmitDraftResponse,
  PreviewSection,
  DraftWarning,
  Completeness,
  FormField,
} from '@form-filling-assistant/shared';
import { ErrorCode } from '@form-filling-assistant/shared';
import { mastersBSchema } from '../data/schema.js';
import { getRequiredFields, getFieldValue } from '../data/validation-rules.js';
import { authMiddleware } from '../middleware/auth.js';
import { store } from '../store.js';

const router = Router();

function formatValue(field: FormField, value: unknown): string {
  if (value === undefined || value === null || value === '') return '(not provided)';

  switch (field.type) {
    case 'boolean':
      return value === true ? 'Yes' : 'No';
    case 'select': {
      if (field.options) {
        const opt = field.options.find((o) =>
          typeof o === 'string' ? o === value : o.value === value,
        );
        if (opt) return typeof opt === 'string' ? opt : opt.label;
      }
      return String(value);
    }
    case 'multi_select': {
      if (Array.isArray(value) && field.options) {
        return value
          .map((v) => {
            const opt = field.options!.find((o) =>
              typeof o === 'string' ? o === v : o.value === v,
            );
            return opt ? (typeof opt === 'string' ? opt : opt.label) : String(v);
          })
          .join(', ');
      }
      return String(value);
    }
    case 'group': {
      if (Array.isArray(value)) return `${value.length} item(s)`;
      return String(value);
    }
    default:
      return String(value);
  }
}

function buildPreview(data: Record<string, unknown>): PreviewSection[] {
  const sections: PreviewSection[] = [];

  for (const section of mastersBSchema.sections) {
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
          fields.push({
            label: field.label,
            value: formatValue(field, val),
          });
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

  const requiredFields = getRequiredFields(allData as Record<string, unknown>);
  let filledCount = 0;
  const warnings: DraftWarning[] = [];

  for (const fieldId of requiredFields) {
    const value = getFieldValue(fieldId, allData as Record<string, unknown>);

    if (fieldId === 'degrees' || fieldId === 'jobs') {
      if (Array.isArray(value) && value.length > 0) {
        filledCount++;
      } else if (fieldId === 'degrees') {
        warnings.push({ field_id: fieldId, message: 'At least 1 academic degree is required.' });
      }
      continue;
    }

    if (value !== undefined && value !== null && value !== '') {
      filledCount++;
    } else {
      let label = fieldId;
      for (const section of mastersBSchema.sections) {
        for (const field of section.fields) {
          if (field.field_id === fieldId) {
            label = field.label;
            break;
          }
        }
      }
      warnings.push({
        field_id: fieldId,
        message: `${label} is required but not yet provided.`,
      });
    }
  }

  const completeness: Completeness = {
    required_filled: filledCount,
    required_total: requiredFields.length,
    percentage: requiredFields.length > 0 ? Math.round((filledCount / requiredFields.length) * 100) : 100,
  };

  const response: SubmitDraftResponse = {
    draft_id: draftId,
    status: 'draft',
    preview: { sections: preview },
    warnings,
    completeness,
  };

  console.log(`[submit-draft] Draft ${draftId} saved. Completeness: ${completeness.percentage}%`);
  res.json(response);
});

export default router;
