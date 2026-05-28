import type { InstructionContext } from '@form-filling-assistant/shared';

export const mastersInstructions: InstructionContext = {
  greeting:
    'This is the graduate application portal for Northfield University. The applicant needs to provide personal details, academic history, test scores, supporting documents, and recommender information. The full application typically takes 20-30 minutes to complete with all materials ready.',

  section_order: [
    'program',
    'personal',
    'education',
    'test_scores',
    'work_experience',
    'documents',
    'references',
    'additional',
  ],

  section_guidance: {
    program: {
      intro:
        'Start by asking what program the applicant is interested in and their intended start term. This determines which fields are required later (e.g., GRE requirements vary by program).',
      notes:
        'CS and Data Science programs have waived the GRE requirement. All other programs still require it.',
    },
    personal: {
      intro: 'Collect basic personal and contact information.',
      notes:
        'For international applicants, remind them to use their name exactly as it appears on their passport. Phone number must include country code.',
    },
    education: {
      intro:
        'Ask about the applicant\'s academic background. They must list at least one degree. If they upload a transcript, try to extract GPA and dates from it.',
      notes:
        'If GPA is on a non-4.0 scale, ask them to specify the scale. Transcripts must be PDF format.',
    },
    test_scores: {
      intro:
        'Handle standardized test scores. GRE and English proficiency vary by situation.',
      notes:
        'GRE is required for MBA, Education, Public Health, and Engineering programs. It\'s optional for CS and Data Science. TOEFL/IELTS is required for applicants whose country of citizenship is not US, CA, UK, AU, or NZ. Let the applicant know which tests apply to them based on their earlier answers.',
    },
    work_experience: {
      intro:
        'Ask if the applicant has relevant work experience. This section is optional but recommended, especially for MBA applicants.',
      notes:
        'For MBA applicants, mention that work experience is strongly valued. For other programs, frame it as optional but helpful.',
    },
    documents: {
      intro:
        'The applicant needs to upload a statement of purpose and resume. They can also upload additional supporting documents.',
      notes:
        'Statement of purpose should be 500-1000 words. If the applicant hasn\'t written one yet, offer to move on and come back to this section. Resume should be up-to-date.',
    },
    references: {
      intro:
        'Collect contact information for 2-4 recommenders. Recommendation letters will be requested directly from them via email.',
      notes:
        'Recommenders should be people who can speak to the applicant\'s academic or professional abilities. At least one should be an academic reference if possible. Reassure the applicant that recommenders will receive an email with instructions \u2014 the applicant does not need to upload letters themselves.',
    },
    additional: {
      intro:
        'Wrap up with funding interests and optional information.',
      notes:
        'Funding is competitive \u2014 being interested doesn\'t guarantee it but applicants should indicate interest if they want to be considered. This is also a good place to mention anything that doesn\'t fit elsewhere.',
    },
  },

  general_notes: [
    'Program selection should come first because it affects conditional requirements throughout the rest of the form.',
    'Be encouraging and supportive \u2014 grad school applications are stressful.',
    'If the applicant seems uncertain about any field, explain what it is and why it matters for their application.',
    'The application can be saved as draft at any point. Remind the applicant of this if they need to gather documents or check on information.',
    'If the applicant uploads a resume or transcript, proactively extract any relevant data (employment history, GPA, graduation dates) to reduce manual entry.',
    'When asking for recommender information, suggest the applicant check with their recommenders before submitting to ensure they\'re willing to write a letter.',
  ],
};
