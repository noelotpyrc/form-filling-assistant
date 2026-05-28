/**
 * Persona definitions for the scenario simulator.
 *
 * A persona is a flat data blob keyed by field_id containing all the "answers"
 * a fake user would give. One persona can be used across multiple forms —
 * shared fields (full_name, email, dob) get reused automatically.
 *
 * Group fields use dot notation: "degrees.0.institution", "jobs.0.employer"
 */

export interface PersonaFile {
  path: string;
  content: string; // pre-extracted text content
  size_mb: number;
}

export interface Persona {
  name: string;
  /** Flat field values keyed by field_id (top-level fields) */
  data: Record<string, unknown>;
  /** Group field entries keyed by group field_id */
  groupData: Record<string, Record<string, unknown>[]>;
  /** File attachments keyed by field_id */
  files: Record<string, PersonaFile>;
}

// ══════════════════════════════════════════════════════════════════════
// PERSONA: Jane Smith — US grad school applicant
// ══════════════════════════════════════════════════════════════════════

export const jane: Persona = {
  name: 'Jane Smith',
  data: {
    // Shared across forms
    full_name: 'Jane Smith',
    preferred_name: 'Jane',
    dob: '1998-05-15',
    date_of_birth: '1998-05-15',
    gender: 'female',
    country_citizenship: 'US',
    country_residence: 'US',
    email: 'jane.smith@email.com',
    phone: '+1-555-0123',
    mailing_address: '123 Oak Street, Springfield, IL 62704',

    // Northfield program selection
    program: 'cs',
    start_term: 'fall_2026',
    enrollment_type: 'full_time',
    prior_application: false,

    // Work experience
    has_work_experience: true,

    // Test scores (CS waives GRE, US citizen skips TOEFL)

    // Additional
    funding_interest: true,
    funding_type: ['research_assistantship', 'fellowship'],
    disability_accommodation: false,
    how_heard: 'referral',
    anything_else: '',

    // Westbrook-specific
    publications_count: 1,
    research_interests:
      'Natural language processing, specifically in-context learning and instruction tuning for large language models.',
    advisor_preference: 'Dr. Emily Chen',
    programming_languages: ['python', 'cpp', 'javascript'],
    technical_statement:
      'Proficient in PyTorch and Hugging Face Transformers. Built an NLP pipeline for text classification at Google serving 5M requests/day. Experience with distributed training on TPU pods.',
  },
  groupData: {
    degrees: [
      {
        institution: 'MIT',
        degree_type: 'bachelor',
        field_of_study: 'Computer Science',
        gpa: 3.85,
        gpa_scale: '4.0',
        start_date: '2016-09',
        end_date: '2020-05',
      },
    ],
    jobs: [
      {
        employer: 'Google',
        title: 'Software Engineer',
        start_date: '2020-06',
        end_date: '2024-01',
        description:
          'Developed backend microservices for Google Cloud Platform. Built ML infrastructure for text classification serving 5M daily requests.',
      },
    ],
    recommenders: [
      {
        name: 'Prof. Alan Turing',
        email: 'turing@mit.edu',
        relationship: 'professor',
        institution: 'MIT',
      },
      {
        name: 'Dr. Sarah Connor',
        email: 'sconnor@google.com',
        relationship: 'employer',
        institution: 'Google',
      },
    ],
  },
  files: {
    'degrees.0.transcript': {
      path: 'fixtures/jane-transcript.pdf',
      content: `UNOFFICIAL TRANSCRIPT
Massachusetts Institute of Technology

Student: Jane Smith
Student ID: 912345678
Degree: Bachelor of Science in Computer Science
Conferred: May 2020

Course History:
Fall 2016: 6.001 Intro to CS (A), 18.01 Calculus I (A-), 8.01 Physics I (B+)
Spring 2017: 6.002 Circuits (A), 18.02 Calculus II (A), 6.006 Algorithms (A)
Fall 2017: 6.004 Computation Structures (A-), 6.036 Machine Learning (A), 18.06 Linear Algebra (A)
Spring 2018: 6.033 Computer Systems (A), 6.046 Design of Algorithms (A-), 6.034 AI (B+)
Fall 2018: 6.824 Distributed Systems (A), 6.828 Operating Systems (A), 6.172 Performance Engineering (A-)
Spring 2019: 6.858 Computer Security (A), 6.S081 OS Engineering (A), 6.854 Advanced Algorithms (B+)
Fall 2019: 6.857 Network Security (A-), 6.867 Machine Learning (A), Thesis Research (A)
Spring 2020: Thesis: Distributed Consensus in Heterogeneous Networks (A)

Cumulative GPA: 3.85 / 4.0
Dean's List: Fall 2016 - Spring 2020`,
      size_mb: 0.8,
    },
  },
};

// ══════════════════════════════════════════════════════════════════════
// PERSONA: Alex Chen — International AI researcher
// ══════════════════════════════════════════════════════════════════════

export const alex: Persona = {
  name: 'Alex Chen',
  data: {
    // Shared
    full_name: 'Alex Chen',
    dob: '1995-11-20',
    date_of_birth: '1995-11-20',
    country_citizenship: 'US',
    country_residence: 'US',
    email: 'alex.chen@email.com',
    phone: '+1-555-0456',
    mailing_address: '456 Elm Ave, San Jose, CA 95112',

    // Work experience
    has_work_experience: true,

    // Westbrook-specific
    publications_count: 3,
    research_interests:
      'Reinforcement learning, multi-agent systems, and robotics. Specifically interested in sim-to-real transfer and safe exploration in RL.',
    advisor_preference: 'Dr. Sarah Martinez',
    programming_languages: ['python', 'cpp', 'rust'],
    technical_statement:
      'Proficient in PyTorch, JAX, and TensorFlow. Built distributed training pipelines for RL at scale. Experience with ROS for robotics applications. Published at NeurIPS workshops on multi-agent coordination.',

    // Northfield-specific (if Alex applies there too)
    program: 'cs',
    start_term: 'fall_2026',
    enrollment_type: 'full_time',
    prior_application: false,
    funding_interest: true,
    funding_type: ['research_assistantship'],
    disability_accommodation: false,
  },
  groupData: {
    degrees: [
      {
        institution: 'Stanford University',
        degree_type: 'bachelor',
        field_of_study: 'Computer Science',
        gpa: 3.72,
        gpa_scale: '4.0',
        start_date: '2013-09',
        end_date: '2017-06',
      },
    ],
    jobs: [
      {
        employer: 'DeepMind',
        title: 'Research Engineer',
        start_date: '2017-07',
        end_date: '', // current position
        description:
          'Reinforcement learning systems for robotics. Published two NeurIPS workshop papers and one arXiv preprint on multi-agent coordination.',
      },
    ],
    recommenders: [
      {
        name: 'Prof. Fei-Fei Li',
        email: 'fli@stanford.edu',
        relationship: 'professor',
        institution: 'Stanford University',
      },
      {
        name: 'Dr. David Silver',
        email: 'silver@deepmind.com',
        relationship: 'employer',
        institution: 'DeepMind',
      },
    ],
  },
  files: {},
};

// ══════════════════════════════════════════════════════════════════════
// PERSONA: Maria Garcia — Medical patient
// ══════════════════════════════════════════════════════════════════════

export const maria: Persona = {
  name: 'Maria Garcia',
  data: {
    // Personal
    full_name: 'Maria Garcia',
    preferred_name: 'Maria',
    dob: '1982-03-22',
    date_of_birth: '1982-03-22',
    sex_at_birth: 'female',
    gender_identity: 'woman',
    pronouns: 'she_her',
    marital_status: 'married',
    email: 'maria.garcia@email.com',
    phone: '555-0789',
    address: '789 Pine St, Riverside, CA 92501',
    mailing_address: '789 Pine St, Riverside, CA 92501',
    emergency_contact_name: 'Carlos Garcia',
    emergency_contact_phone: '555-0790',
    emergency_contact_relationship: 'spouse',

    // Insurance
    has_insurance: true,
    insurance_provider: 'Blue Cross Blue Shield',
    insurance_plan: 'PPO Gold',
    insurance_member_id: 'BCB123456789',
    insurance_group_number: 'GRP-5678',
    insurance_phone: '800-555-1234',

    // Reason for visit
    visit_reason: 'new_patient_checkup',
    preferred_appointment: 'morning',

    // Medical history
    conditions: ['hypertension', 'anxiety'],
    allergies_exist: true,
    immunization_status: 'yes',
    last_physical_date: '2023-06',

    // Medications
    takes_medications: true,
    takes_supplements: true,

    // Family history
    family_history_unknown: false,

    // Lifestyle
    tobacco_use: 'never',
    alcohol_use: 'occasionally',
    alcohol_frequency: 2,
    recreational_drugs: 'never',
    exercise_frequency: '3_4_weekly',
    diet_description: 'Mostly Mediterranean diet with plenty of vegetables, olive oil, and fish.',
    sleep_hours: 7,

    // Consent
    consent_treatment: true,
    consent_privacy: true,
    consent_billing: true,
    signature_name: 'Maria Garcia',
    signature_date: '2026-03-11',
  },
  groupData: {
    allergies: [
      {
        substance: 'Penicillin',
        reaction: 'Skin rash',
        severity: 'moderate',
      },
    ],
    medications: [
      {
        name: 'Lisinopril',
        dosage: '10mg daily',
        reason: 'High blood pressure',
        prescriber: 'Dr. Johnson',
      },
    ],
    supplements: [
      { name: 'Daily Multivitamin', dosage: '1 tablet daily' },
      { name: 'Vitamin D', dosage: '2000 IU daily' },
    ],
    family_conditions: [
      {
        condition: 'heart_disease',
        relationship: ['father'],
        notes: 'Father diagnosed with coronary artery disease at age 55',
      },
      {
        condition: 'hypertension',
        relationship: ['father'],
        notes: 'Father on blood pressure medication',
      },
      {
        condition: 'diabetes',
        relationship: ['mother'],
        notes: 'Mother has type 2 diabetes, diagnosed at age 60',
      },
    ],
  },
  files: {},
};

// ── Registry ──

export const PERSONAS: Record<string, Persona> = {
  jane,
  alex,
  maria,
};
