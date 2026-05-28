import type { ValidationResult } from '@form-filling-assistant/shared';

/**
 * Validates a single field value. Returns a ValidationResult.
 * draftData is the full draft data for cross-field validation (e.g., signature matching).
 */
export function validateField(
  fieldId: string,
  value: unknown,
  draftData?: Record<string, unknown>
): ValidationResult {
  switch (fieldId) {
    // ---- consent fields ----
    case 'consent_treatment':
      if (value !== true) {
        return {
          field_id: fieldId,
          valid: false,
          error: 'You must consent to examination and treatment to proceed.',
        };
      }
      return { field_id: fieldId, valid: true };

    case 'consent_privacy':
      if (value !== true) {
        return {
          field_id: fieldId,
          valid: false,
          error:
            'You must acknowledge the privacy practices notice to proceed.',
        };
      }
      return { field_id: fieldId, valid: true };

    case 'consent_billing': {
      const insuranceData = draftData?.['insurance'] as
        | Record<string, unknown>
        | undefined;
      const hasInsurance = insuranceData?.['has_insurance'];
      if (hasInsurance === true && value !== true) {
        return {
          field_id: fieldId,
          valid: false,
          error:
            'You must authorize billing to your insurance since you indicated you have insurance.',
        };
      }
      return { field_id: fieldId, valid: true };
    }

    // ---- signature fields ----
    case 'signature_name': {
      if (!value || typeof value !== 'string' || value.trim().length === 0) {
        return {
          field_id: fieldId,
          valid: false,
          error: 'Signature is required.',
        };
      }
      const personalData = draftData?.['personal'] as
        | Record<string, unknown>
        | undefined;
      const fullName = personalData?.['full_name'];
      if (
        fullName &&
        typeof fullName === 'string' &&
        typeof value === 'string'
      ) {
        if (fullName.trim().toLowerCase() !== value.trim().toLowerCase()) {
          return {
            field_id: fieldId,
            valid: false,
            error:
              'Typed signature must match the full legal name provided in the personal section.',
            suggestion: `Expected "${fullName}".`,
          };
        }
      }
      return { field_id: fieldId, valid: true };
    }

    case 'signature_date': {
      const today = new Date().toISOString().split('T')[0];
      if (value !== today) {
        return {
          field_id: fieldId,
          valid: false,
          error: `Signature date must be today's date (${today}).`,
          suggestion: `Use ${today}.`,
        };
      }
      return { field_id: fieldId, valid: true };
    }

    // ---- personal fields ----
    case 'full_name':
      return validateText(fieldId, value, 'Full legal name', 200, true);

    case 'preferred_name':
      return validateText(fieldId, value, 'Preferred name', 100, false);

    case 'dob':
      return validateDate(fieldId, value, 'Date of birth', true);

    case 'sex_at_birth':
      return validateSelect(fieldId, value, ['male', 'female', 'intersex']);

    case 'gender_identity':
      return validateSelect(fieldId, value, [
        'man',
        'woman',
        'non_binary',
        'transgender_man',
        'transgender_woman',
        'other',
        'prefer_not_to_say',
      ]);

    case 'pronouns':
      return validateSelect(fieldId, value, [
        'he_him',
        'she_her',
        'they_them',
        'other',
      ]);

    case 'marital_status':
      return validateSelect(fieldId, value, [
        'single',
        'married',
        'divorced',
        'widowed',
        'domestic_partnership',
      ]);

    case 'email':
      return validateEmail(fieldId, value);

    case 'phone':
    case 'emergency_contact_phone':
    case 'insurance_phone':
      return validatePhone(fieldId, value);

    case 'address':
      return validateText(fieldId, value, 'Home address', 500, true);

    case 'emergency_contact_name':
      return validateText(
        fieldId,
        value,
        'Emergency contact name',
        200,
        true
      );

    case 'emergency_contact_relationship':
      return validateText(
        fieldId,
        value,
        'Emergency contact relationship',
        100,
        true
      );

    // ---- insurance fields ----
    case 'has_insurance':
    case 'self_pay':
    case 'allergies_exist':
    case 'takes_medications':
    case 'takes_supplements':
    case 'family_history_unknown':
      return validateBoolean(fieldId, value);

    case 'insurance_provider':
      return validateText(fieldId, value, 'Insurance provider', 200, false);

    case 'insurance_plan':
      return validateText(fieldId, value, 'Plan name', 200, false);

    case 'insurance_member_id':
      return validateText(fieldId, value, 'Member ID', 50, false);

    case 'insurance_group_number':
      return validateText(fieldId, value, 'Group number', 50, false);

    // ---- reason for visit ----
    case 'visit_reason':
      return validateSelect(fieldId, value, [
        'new_patient_checkup',
        'specific_concern',
        'ongoing_condition',
        'referral',
        'second_opinion',
      ]);

    case 'chief_complaint':
      return validateText(
        fieldId,
        value,
        'Chief complaint description',
        1000,
        false
      );

    case 'symptom_duration':
      return validateText(fieldId, value, 'Symptom duration', 100, false);

    case 'symptom_severity':
      return validateNumber(fieldId, value, 1, 10);

    case 'referring_doctor':
      return validateText(
        fieldId,
        value,
        'Referring physician name',
        200,
        false
      );

    case 'referral_reason':
      return validateText(fieldId, value, 'Referral reason', 500, false);

    case 'preferred_provider':
      return validateText(fieldId, value, 'Preferred provider', 200, false);

    case 'preferred_appointment':
      return validateSelect(fieldId, value, [
        'morning',
        'afternoon',
        'no_preference',
      ]);

    // ---- medical history ----
    case 'conditions':
      return validateMultiSelect(fieldId, value, [
        'diabetes_type1',
        'diabetes_type2',
        'hypertension',
        'heart_disease',
        'asthma',
        'copd',
        'cancer',
        'arthritis',
        'depression',
        'anxiety',
        'thyroid_disorder',
        'kidney_disease',
        'liver_disease',
        'stroke',
        'seizure_disorder',
        'autoimmune_disorder',
        'none',
      ]);

    case 'conditions_other':
      return validateText(fieldId, value, 'Other conditions', 500, false);

    case 'immunization_status':
      return validateSelect(fieldId, value, ['yes', 'no', 'unsure']);

    case 'last_physical_date':
      return validateDate(fieldId, value, 'Last physical date', false);

    // ---- lifestyle ----
    case 'tobacco_use':
      return validateSelect(fieldId, value, ['never', 'former', 'current']);

    case 'tobacco_type':
      return validateMultiSelect(fieldId, value, [
        'cigarettes',
        'cigars',
        'pipe',
        'chewing',
        'vaping',
      ]);

    case 'tobacco_frequency':
      return validateText(fieldId, value, 'Tobacco frequency', 100, false);

    case 'tobacco_quit_date':
      return validateDate(fieldId, value, 'Tobacco quit date', false);

    case 'alcohol_use':
      return validateSelect(fieldId, value, [
        'never',
        'occasionally',
        'moderately',
        'heavily',
      ]);

    case 'alcohol_frequency':
      return validateNumber(fieldId, value, 0, 100);

    case 'recreational_drugs':
      return validateSelect(fieldId, value, ['never', 'former', 'current']);

    case 'drug_details':
      return validateText(fieldId, value, 'Drug details', 500, false);

    case 'exercise_frequency':
      return validateSelect(fieldId, value, [
        'none',
        '1_2_weekly',
        '3_4_weekly',
        '5_plus_weekly',
        'daily',
      ]);

    case 'diet_description':
      return validateText(fieldId, value, 'Diet description', 300, false);

    case 'sleep_hours':
      return validateNumber(fieldId, value, 0, 24);

    default:
      return { field_id: fieldId, valid: true };
  }
}

// ---- helper validators ----

function validateText(
  fieldId: string,
  value: unknown,
  label: string,
  maxLength: number,
  required: boolean
): ValidationResult {
  if (value === undefined || value === null || value === '') {
    if (required) {
      return {
        field_id: fieldId,
        valid: false,
        error: `${label} is required.`,
      };
    }
    return { field_id: fieldId, valid: true };
  }
  if (typeof value !== 'string') {
    return {
      field_id: fieldId,
      valid: false,
      error: `${label} must be a string.`,
    };
  }
  if (value.length > maxLength) {
    return {
      field_id: fieldId,
      valid: false,
      error: `${label} must be at most ${maxLength} characters.`,
    };
  }
  return { field_id: fieldId, valid: true };
}

function validateEmail(fieldId: string, value: unknown): ValidationResult {
  if (!value || typeof value !== 'string') {
    return { field_id: fieldId, valid: false, error: 'Email is required.' };
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(value)) {
    return {
      field_id: fieldId,
      valid: false,
      error: 'Please provide a valid email address.',
    };
  }
  return { field_id: fieldId, valid: true };
}

function validatePhone(fieldId: string, value: unknown): ValidationResult {
  if (!value || typeof value !== 'string') {
    return { field_id: fieldId, valid: true };
  }
  const digitsOnly = value.replace(/\D/g, '');
  if (digitsOnly.length < 10 || digitsOnly.length > 15) {
    return {
      field_id: fieldId,
      valid: false,
      error: 'Phone number must be between 10 and 15 digits.',
    };
  }
  return { field_id: fieldId, valid: true };
}

function validateDate(
  fieldId: string,
  value: unknown,
  label: string,
  required: boolean
): ValidationResult {
  if (!value || typeof value !== 'string') {
    if (required) {
      return {
        field_id: fieldId,
        valid: false,
        error: `${label} is required.`,
      };
    }
    return { field_id: fieldId, valid: true };
  }
  // Accept YYYY-MM-DD or YYYY-MM formats
  const fullDateRegex = /^\d{4}-\d{2}-\d{2}$/;
  const monthDateRegex = /^\d{4}-\d{2}$/;
  if (!fullDateRegex.test(value) && !monthDateRegex.test(value)) {
    return {
      field_id: fieldId,
      valid: false,
      error: `${label} must be in YYYY-MM-DD or YYYY-MM format.`,
    };
  }
  return { field_id: fieldId, valid: true };
}

function validateNumber(
  fieldId: string,
  value: unknown,
  min: number,
  max: number
): ValidationResult {
  if (value === undefined || value === null || value === '') {
    return { field_id: fieldId, valid: true };
  }
  const num = typeof value === 'string' ? Number(value) : value;
  if (typeof num !== 'number' || isNaN(num)) {
    return {
      field_id: fieldId,
      valid: false,
      error: 'Must be a number.',
    };
  }
  if (num < min || num > max) {
    return {
      field_id: fieldId,
      valid: false,
      error: `Must be between ${min} and ${max}.`,
    };
  }
  return { field_id: fieldId, valid: true };
}

function validateSelect(
  fieldId: string,
  value: unknown,
  options: string[]
): ValidationResult {
  if (!value || typeof value !== 'string') {
    return { field_id: fieldId, valid: true };
  }
  if (!options.includes(value)) {
    return {
      field_id: fieldId,
      valid: false,
      error: `Invalid selection. Must be one of: ${options.join(', ')}.`,
    };
  }
  return { field_id: fieldId, valid: true };
}

function validateMultiSelect(
  fieldId: string,
  value: unknown,
  options: string[]
): ValidationResult {
  if (!value || !Array.isArray(value)) {
    return { field_id: fieldId, valid: true };
  }
  for (const item of value) {
    if (typeof item !== 'string' || !options.includes(item)) {
      return {
        field_id: fieldId,
        valid: false,
        error: `Invalid selection "${item}". Must be one of: ${options.join(', ')}.`,
      };
    }
  }
  return { field_id: fieldId, valid: true };
}

function validateBoolean(fieldId: string, value: unknown): ValidationResult {
  if (value !== true && value !== false) {
    return {
      field_id: fieldId,
      valid: false,
      error: 'Must be true or false.',
    };
  }
  return { field_id: fieldId, valid: true };
}

// ---- urgency detection ----

const URGENT_KEYWORDS = [
  'chest pain',
  'difficulty breathing',
  'suicidal',
  'severe bleeding',
  'shortness of breath',
  'loss of consciousness',
  'stroke symptoms',
  'allergic reaction',
  'anaphylaxis',
];

export interface UrgentAlert {
  severity: 'urgent' | 'warning';
  message: string;
  field_id: string;
}

export function checkForUrgentSymptoms(
  data: Record<string, unknown>
): UrgentAlert[] {
  const alerts: UrgentAlert[] = [];
  const reasonSection = data['reason_for_visit'] as
    | Record<string, unknown>
    | undefined;

  if (!reasonSection) return alerts;

  const chiefComplaint = reasonSection['chief_complaint'];
  if (chiefComplaint && typeof chiefComplaint === 'string') {
    const lower = chiefComplaint.toLowerCase();
    for (const keyword of URGENT_KEYWORDS) {
      if (lower.includes(keyword)) {
        alerts.push({
          severity: 'urgent',
          message: `Patient reports "${keyword}". Consider advising immediate medical attention if symptoms are active.`,
          field_id: 'chief_complaint',
        });
      }
    }
  }

  const severity = reasonSection['symptom_severity'];
  if (typeof severity === 'number' && severity >= 8) {
    alerts.push({
      severity: 'urgent',
      message: `Patient reports symptom severity of ${severity}/10. This may require urgent attention.`,
      field_id: 'symptom_severity',
    });
  }

  return alerts;
}

// ---- conditional requirement checks ----

export interface MissingFieldWarning {
  field_id: string;
  message: string;
}

export function checkConditionalRequirements(
  data: Record<string, unknown>
): MissingFieldWarning[] {
  const warnings: MissingFieldWarning[] = [];

  const insurance = data['insurance'] as Record<string, unknown> | undefined;
  if (insurance?.['has_insurance'] === true) {
    if (!insurance['insurance_provider']) {
      warnings.push({
        field_id: 'insurance_provider',
        message: 'Insurance provider is required when you have insurance.',
      });
    }
    if (!insurance['insurance_plan']) {
      warnings.push({
        field_id: 'insurance_plan',
        message: 'Plan name is required when you have insurance.',
      });
    }
    if (!insurance['insurance_member_id']) {
      warnings.push({
        field_id: 'insurance_member_id',
        message: 'Member ID is required when you have insurance.',
      });
    }
    if (!insurance['insurance_group_number']) {
      warnings.push({
        field_id: 'insurance_group_number',
        message: 'Group number is required when you have insurance.',
      });
    }
    if (!insurance['insurance_phone']) {
      warnings.push({
        field_id: 'insurance_phone',
        message: 'Insurance phone number is required when you have insurance.',
      });
    }
  }
  if (insurance?.['has_insurance'] === false) {
    if (insurance['self_pay'] !== true) {
      warnings.push({
        field_id: 'self_pay',
        message:
          'Self-pay acknowledgment is required when you do not have insurance.',
      });
    }
  }

  const reason = data['reason_for_visit'] as
    | Record<string, unknown>
    | undefined;
  const visitReason = reason?.['visit_reason'] as string | undefined;
  if (
    visitReason === 'specific_concern' ||
    visitReason === 'ongoing_condition'
  ) {
    if (!reason?.['chief_complaint']) {
      warnings.push({
        field_id: 'chief_complaint',
        message:
          'Please describe your main concern or symptoms.',
      });
    }
    if (!reason?.['symptom_duration']) {
      warnings.push({
        field_id: 'symptom_duration',
        message:
          'Please indicate how long you have experienced these symptoms.',
      });
    }
    if (reason?.['symptom_severity'] === undefined || reason?.['symptom_severity'] === null) {
      warnings.push({
        field_id: 'symptom_severity',
        message: 'Please rate the severity of your symptoms (1-10).',
      });
    }
  }
  if (visitReason === 'referral') {
    if (!reason?.['referring_doctor']) {
      warnings.push({
        field_id: 'referring_doctor',
        message: 'Referring physician name is required for referral visits.',
      });
    }
    if (!reason?.['referral_reason']) {
      warnings.push({
        field_id: 'referral_reason',
        message: 'Reason for referral is required.',
      });
    }
  }

  const meds = data['medications'] as Record<string, unknown> | undefined;
  if (meds?.['takes_medications'] === true) {
    const medsList = meds['medications'];
    if (!medsList || !Array.isArray(medsList) || medsList.length === 0) {
      warnings.push({
        field_id: 'medications',
        message:
          'Please list at least one medication since you indicated you take medications.',
      });
    }
  }
  if (meds?.['takes_supplements'] === true) {
    const suppList = meds['supplements'];
    if (!suppList || !Array.isArray(suppList) || suppList.length === 0) {
      warnings.push({
        field_id: 'supplements',
        message:
          'Please list at least one supplement since you indicated you take supplements.',
      });
    }
  }

  const medHist = data['medical_history'] as
    | Record<string, unknown>
    | undefined;
  if (medHist?.['allergies_exist'] === true) {
    const allergyList = medHist['allergies'];
    if (
      !allergyList ||
      !Array.isArray(allergyList) ||
      allergyList.length === 0
    ) {
      warnings.push({
        field_id: 'allergies',
        message:
          'Please list at least one allergy since you indicated you have allergies.',
      });
    }
  }

  const lifestyle = data['lifestyle'] as Record<string, unknown> | undefined;
  if (lifestyle?.['tobacco_use'] === 'current') {
    if (!lifestyle['tobacco_type']) {
      warnings.push({
        field_id: 'tobacco_type',
        message: 'Please specify the type of tobacco you use.',
      });
    }
    if (!lifestyle['tobacco_frequency']) {
      warnings.push({
        field_id: 'tobacco_frequency',
        message: 'Please specify how often you use tobacco.',
      });
    }
  }
  if (lifestyle?.['tobacco_use'] === 'former') {
    if (!lifestyle['tobacco_quit_date']) {
      warnings.push({
        field_id: 'tobacco_quit_date',
        message: 'Please indicate when you quit using tobacco.',
      });
    }
  }
  if (
    lifestyle?.['alcohol_use'] === 'occasionally' ||
    lifestyle?.['alcohol_use'] === 'moderately' ||
    lifestyle?.['alcohol_use'] === 'heavily'
  ) {
    if (
      lifestyle['alcohol_frequency'] === undefined ||
      lifestyle['alcohol_frequency'] === null
    ) {
      warnings.push({
        field_id: 'alcohol_frequency',
        message: 'Please indicate how many drinks per week you consume.',
      });
    }
  }
  if (
    lifestyle?.['recreational_drugs'] === 'former' ||
    lifestyle?.['recreational_drugs'] === 'current'
  ) {
    if (!lifestyle['drug_details']) {
      warnings.push({
        field_id: 'drug_details',
        message: 'Please describe your recreational drug use.',
      });
    }
  }

  return warnings;
}
