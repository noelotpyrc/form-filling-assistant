# Doc 5: Scenario — Patient Intake Form

## 1. Overview

Mock form for a new patient intake at "Riverside Family Medical." The form covers personal demographics, insurance, medical history, current medications, family history, lifestyle, and reason for visit.

Mock server runs on `http://localhost:3002`.

## 2. Form Schema

### Section: personal

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `full_name` | Full Legal Name | text | yes | max 200 chars |
| `preferred_name` | Preferred Name | text | no | max 100 chars |
| `dob` | Date of Birth | date | yes | format: YYYY-MM-DD |
| `sex_at_birth` | Sex Assigned at Birth | select | yes | options: male, female, intersex |
| `gender_identity` | Gender Identity | select | no | options: man, woman, non_binary, transgender_man, transgender_woman, other, prefer_not_to_say |
| `pronouns` | Pronouns | select | no | options: he_him, she_her, they_them, other |
| `marital_status` | Marital Status | select | no | options: single, married, divorced, widowed, domestic_partnership |
| `email` | Email Address | email | yes | — |
| `phone` | Phone Number | phone | yes | — |
| `address` | Home Address | textarea | yes | max 500 chars |
| `emergency_contact_name` | Emergency Contact Name | text | yes | max 200 chars |
| `emergency_contact_phone` | Emergency Contact Phone | phone | yes | — |
| `emergency_contact_relationship` | Emergency Contact Relationship | text | yes | max 100 chars |

### Section: insurance

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `has_insurance` | Do you have health insurance? | boolean | yes | — |
| `insurance_provider` | Insurance Provider | text | conditional | condition: has_insurance == true; max 200 chars |
| `insurance_plan` | Plan Name | text | conditional | condition: has_insurance == true; max 200 chars |
| `insurance_member_id` | Member ID | text | conditional | condition: has_insurance == true; max 50 chars |
| `insurance_group_number` | Group Number | text | conditional | condition: has_insurance == true; max 50 chars |
| `insurance_phone` | Insurance Phone Number | phone | conditional | condition: has_insurance == true |
| `insurance_card` | Insurance Card (front and back) | file | conditional | condition: has_insurance == true; accepted: jpg, png, pdf; max 5MB each; max 2 files |
| `self_pay` | Self-Pay Acknowledgment | boolean | conditional | condition: has_insurance == false |

### Section: medical_history

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `conditions` | Have you been diagnosed with any of the following? | multi_select | yes | options: see below |
| `conditions_other` | Other conditions not listed | textarea | no | max 500 chars |
| `surgeries` | Past Surgeries | group | no | min 0, max 20 |
| `surgeries.procedure` | Procedure | text | yes | max 200 chars |
| `surgeries.year` | Approximate Year | number | yes | min: 1940, max: 2026 |
| `surgeries.notes` | Notes | text | no | max 300 chars |
| `allergies_exist` | Do you have any known allergies? | boolean | yes | — |
| `allergies` | Allergies | group | conditional | condition: allergies_exist == true; min 1, max 20 |
| `allergies.substance` | Substance | text | yes | max 200 chars |
| `allergies.reaction` | Reaction | text | yes | max 200 chars |
| `allergies.severity` | Severity | select | yes | options: mild, moderate, severe, life_threatening |
| `immunization_status` | Are your immunizations up to date? | select | yes | options: yes, no, unsure |
| `last_physical_date` | Date of Last Physical Exam | date | no | format: YYYY-MM |

**Condition options for `conditions`:**
diabetes_type1, diabetes_type2, hypertension, heart_disease, asthma, copd, cancer, arthritis, depression, anxiety, thyroid_disorder, kidney_disease, liver_disease, stroke, seizure_disorder, autoimmune_disorder, none

### Section: medications

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `takes_medications` | Are you currently taking any medications? | boolean | yes | — |
| `medications` | Current Medications | group | conditional | condition: takes_medications == true; min 1, max 30 |
| `medications.name` | Medication Name | text | yes | max 200 chars |
| `medications.dosage` | Dosage | text | yes | max 100 chars (e.g., "10mg", "500mg twice daily") |
| `medications.reason` | Reason for Taking | text | yes | max 200 chars |
| `medications.prescriber` | Prescribing Doctor | text | no | max 200 chars |
| `takes_supplements` | Do you take any vitamins or supplements? | boolean | yes | — |
| `supplements` | Vitamins / Supplements | group | conditional | condition: takes_supplements == true; min 1, max 20 |
| `supplements.name` | Name | text | yes | max 200 chars |
| `supplements.dosage` | Dosage | text | no | max 100 chars |

### Section: family_history

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `family_conditions` | Do any immediate family members have the following conditions? | group | yes | fixed items, one per condition |
| `family_conditions.condition` | Condition | select | — | options: heart_disease, diabetes, cancer, stroke, hypertension, mental_illness, substance_abuse, none |
| `family_conditions.relationship` | Who? | multi_select | conditional | condition: selected; options: mother, father, sister, brother, maternal_grandmother, maternal_grandfather, paternal_grandmother, paternal_grandfather |
| `family_conditions.notes` | Details | text | no | max 300 chars (e.g., "Father — diagnosed at age 50, colon cancer") |
| `family_history_unknown` | Family medical history is unknown | boolean | no | If true, skip rest of section |

### Section: lifestyle

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `tobacco_use` | Do you use tobacco products? | select | yes | options: never, former, current |
| `tobacco_type` | Type of tobacco | multi_select | conditional | condition: tobacco_use == current; options: cigarettes, cigars, pipe, chewing, vaping |
| `tobacco_frequency` | How often? | text | conditional | condition: tobacco_use == current; max 100 chars |
| `tobacco_quit_date` | When did you quit? | date | conditional | condition: tobacco_use == former; format: YYYY-MM |
| `alcohol_use` | Do you consume alcohol? | select | yes | options: never, occasionally, moderately, heavily |
| `alcohol_frequency` | How many drinks per week? | number | conditional | condition: alcohol_use in [occasionally, moderately, heavily]; min: 0, max: 100 |
| `recreational_drugs` | Do you use recreational drugs? | select | yes | options: never, former, current |
| `drug_details` | If current or former, please describe | textarea | conditional | condition: recreational_drugs in [former, current]; max 500 chars |
| `exercise_frequency` | How often do you exercise? | select | yes | options: none, 1_2_weekly, 3_4_weekly, 5_plus_weekly, daily |
| `diet_description` | Describe your typical diet | textarea | no | max 300 chars |
| `sleep_hours` | Average hours of sleep per night | number | no | min: 0, max: 24, decimal: 1 |

### Section: reason_for_visit

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `visit_reason` | Primary Reason for Visit | select | yes | options: new_patient_checkup, specific_concern, ongoing_condition, referral, second_opinion |
| `chief_complaint` | Describe your main concern or symptoms | textarea | conditional | condition: visit_reason in [specific_concern, ongoing_condition]; max 1000 chars |
| `symptom_duration` | How long have you experienced this? | text | conditional | condition: visit_reason in [specific_concern, ongoing_condition]; max 100 chars |
| `symptom_severity` | Severity (1-10) | number | conditional | condition: visit_reason in [specific_concern, ongoing_condition]; min: 1, max: 10 |
| `referring_doctor` | Referring Physician Name | text | conditional | condition: visit_reason == referral; max 200 chars |
| `referral_reason` | Reason for Referral | textarea | conditional | condition: visit_reason == referral; max 500 chars |
| `preferred_provider` | Do you have a preferred provider at our practice? | text | no | max 200 chars |
| `preferred_appointment` | Preferred appointment time | select | no | options: morning, afternoon, no_preference |

### Section: consent

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `consent_treatment` | I consent to examination and treatment | boolean | yes | must be true |
| `consent_privacy` | I acknowledge the privacy practices notice | boolean | yes | must be true |
| `consent_billing` | I authorize billing to my insurance | boolean | conditional | condition: has_insurance == true; must be true |
| `signature_name` | Typed Signature (Full Legal Name) | text | yes | must match full_name |
| `signature_date` | Date | date | yes | must be today's date |

## 3. Instruction Context

```json
{
  "greeting": "This is the new patient intake form for Riverside Family Medical. The patient needs to provide personal information, insurance details, medical history, current medications, family medical history, lifestyle information, and their reason for visiting. The form typically takes 10-15 minutes.",

  "section_order": [
    "personal",
    "insurance",
    "reason_for_visit",
    "medical_history",
    "medications",
    "family_history",
    "lifestyle",
    "consent"
  ],

  "section_guidance": {
    "personal": {
      "intro": "Collect the patient's personal and contact information, including an emergency contact.",
      "notes": "Sex at birth is a medical question needed for health screening — frame it clinically. Gender identity and pronouns are optional and should be offered respectfully. Emergency contact is required."
    },
    "insurance": {
      "intro": "Ask about health insurance coverage.",
      "notes": "If the patient has insurance, they'll need their member ID and group number — suggest they check their insurance card. Offer to let them upload a photo of their card. If they don't have insurance, note the self-pay option. Do NOT collect the actual insurance card numbers yourself — have them provide it or upload the card."
    },
    "reason_for_visit": {
      "intro": "Understand why the patient is coming in. This helps us prepare for their appointment.",
      "notes": "If it's a new patient checkup, this section is simple. If they have a specific concern, gently ask for details about symptoms — duration, severity. Don't push too hard on specifics — the doctor will explore further in person."
    },
    "medical_history": {
      "intro": "Walk through past medical conditions, surgeries, allergies, and immunization status.",
      "notes": "Present the conditions list conversationally — don't just dump a checklist. Group them: 'Do you have any heart or cardiovascular conditions? What about diabetes or metabolic conditions?' etc. For allergies, make sure to capture the reaction and severity — this is clinically important. If the patient is unsure about something, note 'unsure' rather than skipping."
    },
    "medications": {
      "intro": "Collect current medications and supplements.",
      "notes": "Patients often forget medications or get dosages wrong. Encourage them to check their medication bottles if possible. Separate prescription medications from over-the-counter supplements. If they upload a medication list from another provider, extract data from it."
    },
    "family_history": {
      "intro": "Ask about family medical history for immediate relatives.",
      "notes": "Some patients may not know their family history (adoption, estrangement). If so, mark it as unknown and move on — don't push. When asking, group by condition rather than by family member: 'Has anyone in your family had heart disease? Diabetes?' etc."
    },
    "lifestyle": {
      "intro": "Ask about tobacco, alcohol, drug use, exercise, and sleep.",
      "notes": "These are sensitive topics. Be matter-of-fact and non-judgmental. Frame these as 'routine questions we ask all patients.' For substance use, the patient's honesty matters for their care — reassure them that answers are confidential and used only for medical purposes."
    },
    "consent": {
      "intro": "The patient needs to consent to treatment, acknowledge privacy practices, and authorize billing.",
      "notes": "Present the consent items clearly. The typed signature must match the legal name provided earlier. If the patient has questions about privacy or consent, explain that this is standard practice and they can request a copy of the full privacy notice."
    }
  },

  "general_notes": [
    "Medical forms can be intimidating. Keep the tone warm, patient, and reassuring.",
    "If the patient seems unsure about a medical term, explain it simply. E.g., 'Hypertension is the medical term for high blood pressure.'",
    "For sensitive questions (substance use, mental health history), normalize the questions: 'These are routine questions we ask everyone.'",
    "If the patient doesn't have information handy (e.g., insurance card, medication list), offer to save the draft and come back to those sections.",
    "Be careful with medical data — confirm values like medication dosages and allergy reactions to make sure they're accurate.",
    "If a patient mentions symptoms that sound urgent (chest pain, difficulty breathing, suicidal thoughts), note this prominently and advise them to seek immediate care rather than waiting for their appointment.",
    "The patient may upload a medication list, previous medical records, or insurance card photos — extract relevant data from these when possible."
  ]
}
```

## 4. Mock Server Behavior Notes

- The `/discover` endpoint returns the full schema above with a 1-hour temp token.
- The `/validate` endpoint checks types, ranges, required fields, conditional dependencies, and consent constraints (must be true, signature must match name).
- The `/submit-draft` endpoint accepts partial data. Returns warnings for missing required fields. Flags potentially urgent symptoms in a separate `alerts` field.
- The `/upload-file` endpoint accepts insurance card images and any document files within constraints.
- The `/submit-final` endpoint requires all required fields filled, all consents accepted, and signature matching full_name. On success, returns a confirmation with appointment scheduling information.
- No actual medical data is stored — mock server logs submissions to console only.
