export type FieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'date'
  | 'select'
  | 'multi_select'
  | 'boolean'
  | 'email'
  | 'phone'
  | 'file'
  | 'group';

export type ConditionOperator =
  | 'equals'
  | 'not_equals'
  | 'in'
  | 'not_in'
  | 'greater_than'
  | 'less_than';

export interface FieldCondition {
  field_id: string;
  operator: ConditionOperator;
  value: string | number | boolean | string[];
}

export interface FormField {
  field_id: string;
  label: string;
  type: FieldType;
  required: boolean;
  hint?: string;
  condition?: FieldCondition;

  // text / textarea
  max_length?: number;
  min_length?: number;
  pattern?: string;
  word_limit?: number;

  // number
  min?: number;
  max?: number;
  decimal_places?: number;

  // date
  format?: string;
  min_date?: string;
  max_date?: string;

  // select / multi_select
  options?: string[] | Array<{ value: string; label: string }>;
  max_selections?: number;

  // phone
  require_country_code?: boolean;

  // file
  accepted_types?: string[];
  max_size_mb?: number;
  max_files?: number;

  // group (repeatable)
  fields?: FormField[];
  min_items?: number;
  max_items?: number;
}

export interface FormSection {
  section_id: string;
  title: string;
  fields: FormField[];
}

export interface FormSchema {
  sections: FormSection[];
}
