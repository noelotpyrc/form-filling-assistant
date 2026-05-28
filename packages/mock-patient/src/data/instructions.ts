import type { InstructionContext } from '@form-filling-assistant/shared';

export const patientIntakeInstructions: InstructionContext = {
  greeting:
    'This is the new patient intake form for Riverside Family Medical. The patient needs to provide personal information, insurance details, medical history, current medications, family medical history, lifestyle information, and their reason for visiting. The form typically takes 10-15 minutes.',

  section_order: [
    'personal',
    'insurance',
    'reason_for_visit',
    'medical_history',
    'medications',
    'family_history',
    'lifestyle',
    'consent',
  ],

  section_guidance: {
    personal: {
      intro:
        "Collect the patient's personal and contact information, including an emergency contact.",
      notes:
        'Sex at birth is a medical question needed for health screening — frame it clinically. Gender identity and pronouns are optional and should be offered respectfully. Emergency contact is required.',
    },
    insurance: {
      intro: 'Ask about health insurance coverage.',
      notes:
        "If the patient has insurance, they'll need their member ID and group number — suggest they check their insurance card. Offer to let them upload a photo of their card. If they don't have insurance, note the self-pay option. Do NOT collect the actual insurance card numbers yourself — have them provide it or upload the card.",
    },
    reason_for_visit: {
      intro:
        'Understand why the patient is coming in. This helps us prepare for their appointment.',
      notes:
        "If it's a new patient checkup, this section is simple. If they have a specific concern, gently ask for details about symptoms — duration, severity. Don't push too hard on specifics — the doctor will explore further in person.",
    },
    medical_history: {
      intro:
        'Walk through past medical conditions, surgeries, allergies, and immunization status.',
      notes:
        "Present the conditions list conversationally — don't just dump a checklist. Group them: 'Do you have any heart or cardiovascular conditions? What about diabetes or metabolic conditions?' etc. For allergies, make sure to capture the reaction and severity — this is clinically important. If the patient is unsure about something, note 'unsure' rather than skipping.",
    },
    medications: {
      intro: 'Collect current medications and supplements.',
      notes:
        'Patients often forget medications or get dosages wrong. Encourage them to check their medication bottles if possible. Separate prescription medications from over-the-counter supplements. If they upload a medication list from another provider, extract data from it.',
    },
    family_history: {
      intro: 'Ask about family medical history for immediate relatives.',
      notes:
        "Some patients may not know their family history (adoption, estrangement). If so, mark it as unknown and move on — don't push. When asking, group by condition rather than by family member: 'Has anyone in your family had heart disease? Diabetes?' etc.",
    },
    lifestyle: {
      intro: 'Ask about tobacco, alcohol, drug use, exercise, and sleep.',
      notes:
        "These are sensitive topics. Be matter-of-fact and non-judgmental. Frame these as 'routine questions we ask all patients.' For substance use, the patient's honesty matters for their care — reassure them that answers are confidential and used only for medical purposes.",
    },
    consent: {
      intro:
        'The patient needs to consent to treatment, acknowledge privacy practices, and authorize billing.',
      notes:
        'Present the consent items clearly. The typed signature must match the legal name provided earlier. If the patient has questions about privacy or consent, explain that this is standard practice and they can request a copy of the full privacy notice.',
    },
  },

  general_notes: [
    'Medical forms can be intimidating. Keep the tone warm, patient, and reassuring.',
    "If the patient seems unsure about a medical term, explain it simply. E.g., 'Hypertension is the medical term for high blood pressure.'",
    "For sensitive questions (substance use, mental health history), normalize the questions: 'These are routine questions we ask everyone.'",
    "If the patient doesn't have information handy (e.g., insurance card, medication list), offer to save the draft and come back to those sections.",
    "Be careful with medical data — confirm values like medication dosages and allergy reactions to make sure they're accurate.",
    'If a patient mentions symptoms that sound urgent (chest pain, difficulty breathing, suicidal thoughts), note this prominently and advise them to seek immediate care rather than waiting for their appointment.',
    'The patient may upload a medication list, previous medical records, or insurance card photos — extract relevant data from these when possible.',
  ],
};
