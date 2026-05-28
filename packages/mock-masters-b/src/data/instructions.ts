import type { InstructionContext } from '@form-filling-assistant/shared';

export const mastersBInstructions: InstructionContext = {
  greeting:
    'This is the application portal for Westbrook Institute\'s Research MS in Artificial Intelligence. ' +
    'The applicant needs to provide personal details, academic history, work experience, research background, ' +
    'and technical skills. GRE is not required for this program.',

  section_order: [
    'personal',
    'education',
    'work_experience',
    'research',
    'technical',
  ],

  section_guidance: {
    personal: {
      intro: 'Collect basic personal and contact information.',
      notes:
        'Phone number must include country code. ' +
        'If the applicant has previously filled this info for another application, it can be reused.',
    },
    education: {
      intro:
        'Ask about the applicant\'s academic background. They must list at least one degree.',
      notes:
        'GPA must be on a 4.0 scale. If using a different scale, select the appropriate option. ' +
        'No transcript upload is required at this stage — only degree information.',
    },
    work_experience: {
      intro:
        'Ask if the applicant has relevant work experience. Industry or research experience is valued.',
      notes:
        'Work experience is optional but strongly recommended for applicants with industry backgrounds.',
    },
    research: {
      intro:
        'This section is critical for the research-focused MS. Ask about publications, research interests, ' +
        'and preferred advisors.',
      notes:
        'Even zero publications is fine — just be honest. Research interests should mention specific AI/ML subfields. ' +
        'Faculty advisor preference is optional but shows engagement with the program.',
    },
    technical: {
      intro:
        'Collect technical skills. This program requires proficiency in at least one programming language.',
      notes:
        'Python is expected for AI/ML research. The technical statement should highlight relevant frameworks ' +
        '(e.g., PyTorch, TensorFlow, JAX) and any significant projects or contributions.',
    },
  },

  general_notes: [
    'This is a research-focused program — emphasize research experience and interests.',
    'GRE scores are NOT required and there is no test scores section.',
    'No document uploads are required for this application (handled separately).',
    'If the applicant has existing saved data from other applications, suggest reusing personal info and education.',
    'The application can be saved as draft at any point.',
  ],
};
