# Doc 4: Scenario — Master's Degree Application

## 1. Overview

Mock form for a graduate school application at "Northfield University." The form covers personal information, academic background, standardized test scores, program selection, essays, recommendation letters, and additional information.

Mock server runs on `http://localhost:3001`.

## 2. Form Schema

### Section: personal

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `full_name` | Full Legal Name | text | yes | max 200 chars |
| `preferred_name` | Preferred Name | text | no | max 100 chars |
| `dob` | Date of Birth | date | yes | format: YYYY-MM-DD |
| `gender` | Gender | select | no | options: male, female, non_binary, prefer_not_to_say |
| `country_citizenship` | Country of Citizenship | select | yes | ISO country codes |
| `country_residence` | Country of Residence | select | yes | ISO country codes |
| `email` | Email Address | email | yes | — |
| `phone` | Phone Number | phone | yes | require country code |
| `mailing_address` | Mailing Address | textarea | yes | max 500 chars |

### Section: program

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `program` | Program of Interest | select | yes | options: see below |
| `start_term` | Intended Start Term | select | yes | options: fall_2026, spring_2027 |
| `enrollment_type` | Enrollment Type | select | yes | options: full_time, part_time |
| `prior_application` | Have you previously applied to Northfield? | boolean | yes | — |
| `prior_application_year` | If yes, which year? | number | conditional | condition: prior_application == true; min: 2000, max: 2025 |

**Program options:**
- `cs` — Computer Science (MS)
- `data_science` — Data Science (MS)
- `mba` — Business Administration (MBA)
- `education` — Education (MEd)
- `public_health` — Public Health (MPH)
- `engineering` — Mechanical Engineering (MS)

### Section: education

Repeatable group — applicant may have multiple degrees.

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `degrees` | Academic Degrees | group | yes | min 1, max 5 |
| `degrees.institution` | Institution Name | text | yes | max 200 chars |
| `degrees.degree_type` | Degree Type | select | yes | options: bachelor, master, doctorate, associate, other |
| `degrees.field_of_study` | Field of Study / Major | text | yes | max 200 chars |
| `degrees.gpa` | GPA | number | yes | min 0, max 4.0, decimal places: 2 |
| `degrees.gpa_scale` | GPA Scale | select | yes | options: 4.0, 5.0, 10.0, percentage, other |
| `degrees.start_date` | Start Date | date | yes | format: YYYY-MM |
| `degrees.end_date` | End Date (or expected) | date | yes | format: YYYY-MM |
| `degrees.transcript` | Official Transcript | file | yes | accepted: pdf; max 10MB |

### Section: test_scores

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `gre_taken` | Have you taken the GRE? | boolean | conditional | condition: program not_in [cs, data_science] → required; otherwise optional |
| `gre_verbal` | GRE Verbal Score | number | conditional | condition: gre_taken == true; min: 130, max: 170 |
| `gre_quant` | GRE Quantitative Score | number | conditional | condition: gre_taken == true; min: 130, max: 170 |
| `gre_writing` | GRE Analytical Writing Score | number | conditional | condition: gre_taken == true; min: 0, max: 6, decimal: 1 |
| `gre_date` | GRE Test Date | date | conditional | condition: gre_taken == true |
| `toefl_required` | Is TOEFL/IELTS required? | boolean | auto | condition: country_citizenship not_in [US, CA, UK, AU, NZ] → true |
| `english_test_type` | English Proficiency Test | select | conditional | condition: toefl_required == true; options: toefl, ielts |
| `english_test_score` | Score | number | conditional | condition: toefl_required == true; TOEFL: 0-120, IELTS: 0-9 |
| `english_test_date` | Test Date | date | conditional | condition: toefl_required == true |

### Section: work_experience

Repeatable group — optional.

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `has_work_experience` | Do you have relevant work experience? | boolean | yes | — |
| `jobs` | Work Experience | group | conditional | condition: has_work_experience == true; min 1, max 10 |
| `jobs.employer` | Employer | text | yes | max 200 chars |
| `jobs.title` | Job Title | text | yes | max 200 chars |
| `jobs.start_date` | Start Date | date | yes | format: YYYY-MM |
| `jobs.end_date` | End Date | date | no | format: YYYY-MM; blank = current |
| `jobs.description` | Description of Role | textarea | no | max 500 chars |

### Section: documents

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `statement_of_purpose` | Statement of Purpose | file | yes | accepted: pdf, docx; max 5MB |
| `resume` | Resume / CV | file | yes | accepted: pdf, docx; max 5MB |
| `additional_docs` | Additional Supporting Documents | file | no | accepted: pdf, docx, jpg, png; max 10MB each; max 3 files |

### Section: references

Repeatable group — recommendation letters.

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `recommenders` | Recommenders | group | yes | min 2, max 4 |
| `recommenders.name` | Recommender Name | text | yes | max 200 chars |
| `recommenders.email` | Recommender Email | email | yes | — |
| `recommenders.relationship` | Relationship | select | yes | options: professor, employer, advisor, mentor, other |
| `recommenders.institution` | Institution / Organization | text | yes | max 200 chars |

Note: Recommendation letters are requested via email from recommenders — the applicant provides contact info only.

### Section: additional

| field_id | label | type | required | constraints |
|---|---|---|---|---|
| `funding_interest` | Interested in funding/assistantships? | boolean | yes | — |
| `funding_type` | Preferred funding type | multi_select | conditional | condition: funding_interest == true; options: teaching_assistantship, research_assistantship, fellowship, scholarship |
| `disability_accommodation` | Do you require disability accommodations? | boolean | no | — |
| `how_heard` | How did you hear about Northfield? | select | no | options: web_search, social_media, referral, education_fair, alumni, other |
| `anything_else` | Anything else you'd like us to know? | textarea | no | max 1000 chars |

## 3. Instruction Context

```json
{
  "greeting": "This is the graduate application portal for Northfield University. The applicant needs to provide personal details, academic history, test scores, supporting documents, and recommender information. The full application typically takes 20-30 minutes to complete with all materials ready.",

  "section_order": [
    "program",
    "personal",
    "education",
    "test_scores",
    "work_experience",
    "documents",
    "references",
    "additional"
  ],

  "section_guidance": {
    "program": {
      "intro": "Start by asking what program the applicant is interested in and their intended start term. This determines which fields are required later (e.g., GRE requirements vary by program).",
      "notes": "CS and Data Science programs have waived the GRE requirement. All other programs still require it."
    },
    "personal": {
      "intro": "Collect basic personal and contact information.",
      "notes": "For international applicants, remind them to use their name exactly as it appears on their passport. Phone number must include country code."
    },
    "education": {
      "intro": "Ask about the applicant's academic background. They must list at least one degree. If they upload a transcript, try to extract GPA and dates from it.",
      "notes": "If GPA is on a non-4.0 scale, ask them to specify the scale. Transcripts must be PDF format."
    },
    "test_scores": {
      "intro": "Handle standardized test scores. GRE and English proficiency vary by situation.",
      "notes": "GRE is required for MBA, Education, Public Health, and Engineering programs. It's optional for CS and Data Science. TOEFL/IELTS is required for applicants whose country of citizenship is not US, CA, UK, AU, or NZ. Let the applicant know which tests apply to them based on their earlier answers."
    },
    "work_experience": {
      "intro": "Ask if the applicant has relevant work experience. This section is optional but recommended, especially for MBA applicants.",
      "notes": "For MBA applicants, mention that work experience is strongly valued. For other programs, frame it as optional but helpful."
    },
    "documents": {
      "intro": "The applicant needs to upload a statement of purpose and resume. They can also upload additional supporting documents.",
      "notes": "Statement of purpose should be 500-1000 words. If the applicant hasn't written one yet, offer to move on and come back to this section. Resume should be up-to-date."
    },
    "references": {
      "intro": "Collect contact information for 2-4 recommenders. Recommendation letters will be requested directly from them via email.",
      "notes": "Recommenders should be people who can speak to the applicant's academic or professional abilities. At least one should be an academic reference if possible. Reassure the applicant that recommenders will receive an email with instructions — the applicant does not need to upload letters themselves."
    },
    "additional": {
      "intro": "Wrap up with funding interests and optional information.",
      "notes": "Funding is competitive — being interested doesn't guarantee it but applicants should indicate interest if they want to be considered. This is also a good place to mention anything that doesn't fit elsewhere."
    }
  },

  "general_notes": [
    "Program selection should come first because it affects conditional requirements throughout the rest of the form.",
    "Be encouraging and supportive — grad school applications are stressful.",
    "If the applicant seems uncertain about any field, explain what it is and why it matters for their application.",
    "The application can be saved as draft at any point. Remind the applicant of this if they need to gather documents or check on information.",
    "If the applicant uploads a resume or transcript, proactively extract any relevant data (employment history, GPA, graduation dates) to reduce manual entry.",
    "When asking for recommender information, suggest the applicant check with their recommenders before submitting to ensure they're willing to write a letter."
  ]
}
```

## 4. Mock Server Behavior Notes

- The `/discover` endpoint always returns the full schema above with a 1-hour temp token.
- The `/validate` endpoint checks types, ranges, and required fields. It also checks conditional dependencies.
- The `/submit-draft` endpoint accepts partial data and returns a preview with warnings for missing required fields.
- The `/upload-file` endpoint accepts any file matching the type/size constraints and returns a mock `file_id`.
- The `/submit-final` endpoint rejects if any required field is missing or invalid. On success, returns a mock confirmation with reference number.
- Recommender emails are not actually sent — the mock server just logs them.
