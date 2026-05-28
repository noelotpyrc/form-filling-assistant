import type { FormSchema } from './schema.js';

// -- Discover --

export interface DiscoverRequest {
  agent_id: string;
  form_type?: string;
}

export interface SectionGuidance {
  intro: string;
  notes: string;
}

export interface InstructionContext {
  greeting: string;
  section_order: string[];
  section_guidance: Record<string, SectionGuidance>;
  general_notes: string[];
}

export interface DiscoverResponse {
  form_id: string;
  auth_token: string;
  token_expires_at: string;
  schema: FormSchema;
  instructions: InstructionContext;
}

// -- Validate --

export interface FieldValidation {
  field_id: string;
  value: unknown;
}

export interface ValidateRequest {
  form_id: string;
  fields: FieldValidation[];
}

export interface ValidationResult {
  field_id: string;
  valid: boolean;
  error?: string;
  suggestion?: string;
}

export interface ValidateResponse {
  results: ValidationResult[];
}

// -- Upload File --

export interface UploadFileResponse {
  file_id: string;
  field_id: string;
  filename: string;
  size_bytes: number;
  status: 'accepted' | 'rejected';
}

// -- Submit Draft --

export interface SubmitDraftRequest {
  form_id: string;
  data: Record<string, unknown>;
}

export interface PreviewField {
  label: string;
  value: string;
}

export interface PreviewSection {
  title: string;
  fields: PreviewField[];
}

export interface DraftWarning {
  field_id: string;
  message: string;
}

export interface Completeness {
  required_filled: number;
  required_total: number;
  percentage: number;
}

export interface DraftAlert {
  severity: 'urgent' | 'warning';
  message: string;
  field_id: string;
}

export interface SubmitDraftResponse {
  draft_id: string;
  status: 'draft';
  preview: {
    sections: PreviewSection[];
  };
  warnings: DraftWarning[];
  completeness: Completeness;
  alerts?: DraftAlert[];
}

// -- Submit Final --

export interface SubmitFinalRequest {
  form_id: string;
  draft_id: string;
}

export interface SubmitFinalResponse {
  submission_id: string;
  status: 'submitted' | 'rejected';
  confirmation?: {
    message: string;
    reference_number: string;
    next_steps: string[];
  };
  errors?: Array<{
    field_id: string;
    message: string;
  }>;
}
