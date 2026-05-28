import type { FormSchema } from '@form-filling-assistant/shared';

/**
 * Westbrook Institute — Research MS in Artificial Intelligence
 *
 * 5 sections:
 *   1. personal     — same fields as Program A (reusable from vault)
 *   2. education    — same degrees group (reusable from vault)
 *   3. work_experience — same structure (reusable from vault)
 *   4. research     — NEW: research background unique to this program
 *   5. technical    — NEW: technical skills unique to this program
 */
export const mastersBSchema: FormSchema = {
  sections: [
    // ── Section 1: Personal (matches Program A) ──────────────────────
    {
      section_id: 'personal',
      title: 'Personal Information',
      fields: [
        {
          field_id: 'full_name',
          label: 'Full Legal Name',
          type: 'text',
          required: true,
          max_length: 200,
        },
        {
          field_id: 'dob',
          label: 'Date of Birth',
          type: 'date',
          required: true,
          format: 'YYYY-MM-DD',
        },
        {
          field_id: 'country_citizenship',
          label: 'Country of Citizenship',
          type: 'select',
          required: true,
          options: ['US', 'CA', 'UK', 'AU', 'NZ', 'IN', 'CN', 'KR', 'JP', 'DE', 'FR', 'BR', 'MX', 'NG', 'OTHER'],
        },
        {
          field_id: 'email',
          label: 'Email Address',
          type: 'email',
          required: true,
        },
        {
          field_id: 'phone',
          label: 'Phone Number',
          type: 'phone',
          required: true,
          require_country_code: true,
        },
        {
          field_id: 'mailing_address',
          label: 'Mailing Address',
          type: 'textarea',
          required: true,
          max_length: 500,
        },
      ],
    },

    // ── Section 2: Education (matches Program A) ─────────────────────
    {
      section_id: 'education',
      title: 'Academic Background',
      fields: [
        {
          field_id: 'degrees',
          label: 'Academic Degrees',
          type: 'group',
          required: true,
          min_items: 1,
          max_items: 5,
          fields: [
            {
              field_id: 'institution',
              label: 'Institution Name',
              type: 'text',
              required: true,
              max_length: 200,
            },
            {
              field_id: 'degree_type',
              label: 'Degree Type',
              type: 'select',
              required: true,
              options: [
                { value: 'bachelor', label: 'Bachelor\'s' },
                { value: 'master', label: 'Master\'s' },
                { value: 'doctorate', label: 'Doctorate' },
                { value: 'associate', label: 'Associate' },
                { value: 'other', label: 'Other' },
              ],
            },
            {
              field_id: 'field_of_study',
              label: 'Field of Study / Major',
              type: 'text',
              required: true,
              max_length: 200,
            },
            {
              field_id: 'gpa',
              label: 'GPA',
              type: 'number',
              required: true,
              min: 0,
              max: 4.0,
              decimal_places: 2,
            },
            {
              field_id: 'gpa_scale',
              label: 'GPA Scale',
              type: 'select',
              required: true,
              options: [
                { value: '4.0', label: '4.0 Scale' },
                { value: '5.0', label: '5.0 Scale' },
                { value: '10.0', label: '10.0 Scale' },
                { value: 'percentage', label: 'Percentage' },
                { value: 'other', label: 'Other' },
              ],
            },
            {
              field_id: 'start_date',
              label: 'Start Date',
              type: 'date',
              required: true,
              format: 'YYYY-MM',
            },
            {
              field_id: 'end_date',
              label: 'End Date (or expected)',
              type: 'date',
              required: true,
              format: 'YYYY-MM',
            },
          ],
        },
      ],
    },

    // ── Section 3: Work Experience (matches Program A) ───────────────
    {
      section_id: 'work_experience',
      title: 'Work Experience',
      fields: [
        {
          field_id: 'has_work_experience',
          label: 'Do you have relevant work experience?',
          type: 'boolean',
          required: true,
        },
        {
          field_id: 'jobs',
          label: 'Work Experience',
          type: 'group',
          required: false,
          min_items: 1,
          max_items: 10,
          condition: {
            field_id: 'has_work_experience',
            operator: 'equals',
            value: true,
          },
          fields: [
            {
              field_id: 'employer',
              label: 'Employer',
              type: 'text',
              required: true,
              max_length: 200,
            },
            {
              field_id: 'title',
              label: 'Job Title',
              type: 'text',
              required: true,
              max_length: 200,
            },
            {
              field_id: 'start_date',
              label: 'Start Date',
              type: 'date',
              required: true,
              format: 'YYYY-MM',
            },
            {
              field_id: 'end_date',
              label: 'End Date',
              type: 'date',
              required: false,
              format: 'YYYY-MM',
              hint: 'Leave blank if current position',
            },
            {
              field_id: 'description',
              label: 'Description of Role',
              type: 'textarea',
              required: false,
              max_length: 500,
            },
          ],
        },
      ],
    },

    // ── Section 4: Research Experience (NEW — unique to Program B) ────
    {
      section_id: 'research',
      title: 'Research Experience',
      fields: [
        {
          field_id: 'publications_count',
          label: 'Number of publications (papers, posters, preprints)',
          type: 'number',
          required: true,
          min: 0,
          max: 100,
        },
        {
          field_id: 'research_interests',
          label: 'Research Interests',
          type: 'textarea',
          required: true,
          max_length: 1000,
          hint: 'Describe the AI/ML research areas you are interested in pursuing.',
        },
        {
          field_id: 'advisor_preference',
          label: 'Preferred Faculty Advisor(s)',
          type: 'text',
          required: false,
          max_length: 300,
          hint: 'If you have a preference, list faculty names.',
        },
      ],
    },

    // ── Section 5: Technical Skills (NEW — unique to Program B) ──────
    {
      section_id: 'technical',
      title: 'Technical Skills',
      fields: [
        {
          field_id: 'programming_languages',
          label: 'Programming Languages',
          type: 'multi_select',
          required: true,
          options: [
            { value: 'python', label: 'Python' },
            { value: 'cpp', label: 'C/C++' },
            { value: 'java', label: 'Java' },
            { value: 'javascript', label: 'JavaScript/TypeScript' },
            { value: 'rust', label: 'Rust' },
            { value: 'julia', label: 'Julia' },
            { value: 'r', label: 'R' },
            { value: 'other', label: 'Other' },
          ],
          max_selections: 5,
        },
        {
          field_id: 'technical_statement',
          label: 'Technical Background Statement',
          type: 'textarea',
          required: true,
          max_length: 500,
          hint: 'Briefly describe your technical background, frameworks, and tools you are proficient with.',
        },
      ],
    },
  ],
};
