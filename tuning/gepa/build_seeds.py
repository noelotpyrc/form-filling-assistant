"""Build tuning/gepa/seeds.jsonl by hand-authoring correct_answer for each seed.

For probe-based seeds: input portion comes from /tmp/seed_inputs.json (parsed
from probe markdown). For R-ID seeds (manual sessions): input portion authored
here based on doc-15 descriptions.

correct_answer shape mirrors what FormAssistant.forward() should produce in the
ideal case — module-by-module:
  flags:        action_router output (5 booleans)
  response_text: text_responder output (canonical example; judge uses this as reference)
  field_ids/values: data_extractor output (when has_new_data fires)
  question/options: choice_builder output (when needs_choice fires)
  summary_title/content: review_builder output (when wants_review fires)
"""

from __future__ import annotations

import json
from pathlib import Path

INPUTS_PATH = Path("/tmp/seed_inputs.json")
OUT_PATH = Path(__file__).parent / "seeds.jsonl"

probe_inputs = json.loads(INPUTS_PATH.read_text())

# Patch probe_inputs to bring form_state in line with what the conversation
# said was saved. The probe markdown was authored before we settled on the rule
# that saved/required info must appear in form_state too.
probe_inputs["P3-ex1"]["form_state"]["email"] = "sam.patal@gmail.com"
probe_inputs["P3-ex1"]["form_state"]["phone"] = "+1-617-555-2222"
probe_inputs["P12-ex5"]["form_state"]["phone"] = "+1-617-555-3344"
probe_inputs["P8-ex3"]["form_state"]["jobs-0-description"] = "managed daily ops for a 200-person team"


def empty_answer():
    """Default answer scaffold; override fields per seed."""
    return {
        "flags": {
            "has_new_data": False, "needs_choice": False, "wants_review": False,
            "wants_save": False, "wants_submit": False,
        },
        "response_text": "",
        "field_ids": [],
        "field_values": [],
        "question": "",
        "options": [],
        "summary_title": "",
        "summary_content": "",
    }


seeds = []


# ════════════════════════════════════════════════════════════════════
# Probe-based seeds (input comes from probe markdown)
# ════════════════════════════════════════════════════════════════════

def add_probe_seed(probe_id: str, cannot_targets: list[str], correct_answer: dict):
    p = probe_inputs[probe_id]
    seeds.append({
        "test_id": f"seed-{probe_id}",
        "source": probe_id,
        "cannot_targets": cannot_targets,
        "input": {
            "form_state": p["form_state"],
            "conversation_history": p["conversation_history"],
            "user_message": p["user_message"],
        },
        "correct_answer": correct_answer,
    })


# ── #1 vibe ──

add_probe_seed("P1-ex3", ["#1_vibe"], {
    "flags": {"has_new_data": False, "needs_choice": True, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Doing well, thanks for asking 😊 Whenever you're ready — which graduate program would you like to apply to?",
    "field_ids": [], "field_values": [],
    "question": "Which graduate program would you like to apply to?",
    "options": ["Computer Science (MS)", "Data Science (MS)", "Business Administration (MBA)",
                "Education (MEd)", "Public Health (MPH)", "Mechanical Engineering (MS)"],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P9-ex2", ["#1_vibe"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": False,
              "wants_save": True, "wants_submit": False},
    "response_text": "No problem at all! I'll save your progress so you can pick right back up when things settle down. Tap **Save Draft** below whenever you're ready, and we'll be here.",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P12-ex3", ["#1_vibe"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": False,
              "wants_save": True, "wants_submit": False},
    "response_text": "I hear you — applications are a slog. We don't have to push through right now; if you'd like, save what's done and come back fresh later. Or if you'd rather power through a few more, just say the word.",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P12-ex5", ["#1_vibe"], {
    "flags": {"has_new_data": False, "needs_choice": True, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Just want to make sure I read that right — by 'no' do you mean you'd rather skip education for now, you don't have any degrees to add, or something else?",
    "field_ids": [], "field_values": [],
    "question": "What did you mean by 'no'?",
    "options": ["I don't have any degrees to add", "Skip this section for now", "Something else"],
    "summary_title": "", "summary_content": "",
})


# ── #2 text-action disconnect ──

add_probe_seed("P2-ex5", ["#2_text_action_disconnect"], {
    "flags": {"has_new_data": True, "needs_choice": True, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Switched to the MBA — got it. When would you like to start?",
    "field_ids": ["program"], "field_values": ["mba"],
    "question": "When would you like to start?",
    "options": ["Fall 2026", "Spring 2027"],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P3-ex1", ["#2_text_action_disconnect"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got it — fixed the email to sam.patel@gmail.com. What's your mailing address?",
    "field_ids": ["email"], "field_values": ["sam.patel@gmail.com"],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P5-ex3", ["#2_text_action_disconnect", "#5_group_indices"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got all three recommenders saved — Dr. Patel at UW, Prof. Chen at Johns Hopkins, and Dr. Kim at the King County health department. Want to add anyone else, or are we good with these three?",
    "field_ids": [
        "recommenders.0.name", "recommenders.0.email", "recommenders.0.relationship", "recommenders.0.institution",
        "recommenders.1.name", "recommenders.1.email", "recommenders.1.relationship", "recommenders.1.institution",
        "recommenders.2.name", "recommenders.2.email", "recommenders.2.relationship", "recommenders.2.institution",
    ],
    "field_values": [
        "Dr. Maya Patel", "maya.patel@uw.edu", "professor", "University of Washington",
        "Prof. James Chen", "jchen@jhsph.edu", "professor", "Johns Hopkins",
        "Dr. Robert Kim", "bob.kim@kingcounty.gov", "supervisor", "King County Health Department",
    ],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P7-ex5", ["#2_text_action_disconnect"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got it — replaced your resume with Yuri_Resume_v2.pdf. I also updated your contact info from the new version (yuri@test.com, +1-718-555-9900) and your work history at DoorDash and Stripe.",
    "field_ids": [
        "resume", "email", "phone",
        "has_work_experience", "jobs.0.employer", "jobs.0.title",
    ],
    "field_values": [
        "Yuri_Resume_v2.pdf", "yuri@test.com", "+1-718-555-9900",
        "true", "DoorDash", "Senior Data Scientist",
    ],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})


# ── #3 cross-check states (post-augmentation: model uses augmented context faithfully) ──

add_probe_seed("P8-ex1", ["#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
              "wants_save": False, "wants_submit": False},
    "response_text": "Sure! Here's what we've got so far. The personal info section is mostly done; just the mailing address still to fill in.",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "Application Progress",
    "summary_content": "Personal Information: Full name (Zion Adams), Date of birth (1994-02-28), Citizenship (US), Residence (US), Phone (+1-202-555-7700) — saved. Mailing address — still needed.",
})

add_probe_seed("P8-ex2", ["#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
              "wants_save": False, "wants_submit": False},
    "response_text": "Quite a bit done already! Still ahead: your statement of purpose, resume, transcripts for your degrees, recommendation letters, and the funding interest section. Want to keep going?",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "What's Left",
    "summary_content": "Required: statement_of_purpose, resume, recommenders (group), funding_interest, degrees.0.transcript. Optional: preferred_name, gender, additional_docs.",
})

add_probe_seed("P8-ex3", ["#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
              "wants_save": False, "wants_submit": False},
    "response_text": "Of course — here's what I have for your education section.",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "Education",
    "summary_content": "Degree #1: University of Denver — Bachelor's in Business, GPA 3.4/4.0, September 2003 to June 2007. Transcript not yet uploaded.",
})

add_probe_seed("P8-ex4", ["#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
              "wants_save": False, "wants_submit": False},
    "response_text": "Yes, personal info is all done — full name, DOB, citizenship, residence, phone. Just one thing missing: mailing address. Want to add that, or move on?",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "Personal Information Status",
    "summary_content": "Filled: Full name, Date of birth, Citizenship (US), Residence (US), Phone. Still needed: mailing_address.",
})

add_probe_seed("P12-ex2", ["#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Hmm, looking at what I have — I don't see a mailing address saved yet. Could you share it?",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})


# ── #4 commits regardless ──

add_probe_seed("P1-ex1", ["#4_commits_regardless", "#8_training_data_hallucination"], {
    "flags": {"has_new_data": False, "needs_choice": True, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Welcome aboard! 🎓 Excited to help you get started. Which graduate program would you like to apply to?",
    "field_ids": [], "field_values": [],
    "question": "Which graduate program would you like to apply to?",
    "options": ["Computer Science (MS)", "Data Science (MS)", "Business Administration (MBA)",
                "Education (MEd)", "Public Health (MPH)", "Mechanical Engineering (MS)"],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P1-ex2", ["#4_commits_regardless", "#3_state_check"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
              "wants_save": False, "wants_submit": False},
    "response_text": "Welcome back, Pat! Looking at where we left off: program is set (Data Science MS, Fall 2026, full-time), most of personal info is done, and your Waterloo bachelor's is recorded. We still need test scores, work experience, supporting documents, recommenders, and funding info. Where would you like to pick up?",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "Welcome back, Pat — application progress",
    "summary_content": "Saved: Program (Data Science MS), Start (Fall 2026), Enrollment (Full-time), Personal info (Pat Wong, DOB, citizenship CA, residence US, phone, address), Bachelor's degree at University of Waterloo (Statistics, 3.72/4.0). Still needed: test scores, work experience, supporting documents (SOP, resume), recommenders, funding interest.",
})

add_probe_seed("P3-ex3", ["#4_commits_regardless"], {
    "flags": {"has_new_data": False, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Either format works — `mm/dd/yyyy` or natural language like 'jan 4 1995' both fine. Whatever's easiest. What's your DOB?",
    "field_ids": [], "field_values": [],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P4-ex4", ["#4_commits_regardless"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got your Google role saved — Software Engineer, started early 2022, ended a couple months ago, ranking-team infra. Anything else from your work history?",
    "field_ids": [
        "has_work_experience", "jobs.0.employer", "jobs.0.title",
        "jobs.0.start_date", "jobs.0.description",
    ],
    "field_values": [
        "true", "Google", "Software Engineer",
        "2022-02", "Built infra for the search ranking team.",
    ],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P6-ex3", ["#4_commits_regardless", "#7_wrong_field_value"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Congrats! Updated your citizenship to US. And yes — since you're a US citizen, the TOEFL stuff isn't required, so we can skip it.",
    "field_ids": ["country_citizenship"],
    "field_values": ["US"],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})


# ── #5 group indices (covered by P5-ex3 above, plus P5-ex2) ──

add_probe_seed("P5-ex2", ["#5_group_indices", "#7_wrong_field_value"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got it — added Bain & Company as your earlier role: Senior Associate, 2014 to 2018, private equity due diligence. Any other roles before that?",
    "field_ids": [
        "jobs.1.employer", "jobs.1.title", "jobs.1.start_date", "jobs.1.end_date", "jobs.1.description",
    ],
    "field_values": [
        "Bain & Company", "Senior Associate", "2014", "2018",
        "Worked on private equity due diligence projects.",
    ],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})

add_probe_seed("P5-ex5", ["#7_wrong_field_value", "#8_training_data_hallucination"], {
    "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Got it — fixed Prof. Walsh's email to liam.walsh@bu.edu. The other recommenders are unchanged.",
    "field_ids": ["recommenders.1.email"],
    "field_values": ["liam.walsh@bu.edu"],
    "question": "", "options": [],
    "summary_title": "", "summary_content": "",
})


# ── #8 training-data hallucination (P2-ex2 only — others covered above) ──

add_probe_seed("P2-ex2", ["#8_training_data_hallucination"], {
    "flags": {"has_new_data": True, "needs_choice": True, "wants_review": False,
              "wants_save": False, "wants_submit": False},
    "response_text": "Mechanical Engineering it is. When would you like to start?",
    "field_ids": ["program"], "field_values": ["engineering"],
    "question": "When would you like to start?",
    "options": ["Fall 2026", "Spring 2027"],
    "summary_title": "", "summary_content": "",
})


# ════════════════════════════════════════════════════════════════════
# R-ID seeds (input authored from doc-15 descriptions)
# ════════════════════════════════════════════════════════════════════

# R5 — 17-fields silent fill on resume upload (ex9 of sess-1777498716039)
seeds.append({
    "test_id": "seed-R5",
    "source": "R5",
    "cannot_targets": ["#2_text_action_disconnect"],
    "input": {
        "form_state": {
            "email": "kkkl@oka.com", "program": "cs", "start_term": "spring_2027",
            "enrollment_type": "full_time", "prior_application": False,
        },
        "conversation_history": [
            {"role": "user", "content": "[system] User selected option: \"No\""},
            {"role": "assistant", "content": "Program section is all set! Now let's cover Personal Information. Could you share your full legal name, date of birth, country of citizenship, country of residence, email, phone, and mailing address?"},
            {"role": "user", "content": "typing the info is too annoying, how can i do this in an easier way"},
            {"role": "assistant", "content": "If you have a resume PDF you can attach, I can pull out a lot of this for you. Want to try that?"},
        ],
        "user_message": "[File: Resume.pdf]\nJane Doe\nEmail: jane.doe@example.com | Phone: (123) 456-7890 | Anytown, USA\nLinkedIn: linkedin.com/in/janedoe | GitHub: github.com/janedoe\nEducation\nUniversity of Anytown - Bachelor of Science in Computer Science\nMay 2025 | GPA: 3.58 | Honors: Cum Laude\nExperience\nSoftware Engineering Intern - TechCorp\nSummer 2024 | San Francisco, CA\n- Developed internal tools using Python and Flask\n- Collaborated with frontend developers on React UI\nTeaching Assistant - University of Anytown\nFall 2023 | Anytown, USA\n- Assisted in CS250: Software Engineering Principles\nSkills: Python, Java, C++, JavaScript, SQL\n[End of Resume.pdf]",
    },
    "correct_answer": {
        "flags": {"has_new_data": True, "needs_choice": True, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Got your resume! I pulled out: bachelor's in Computer Science from University of Anytown (GPA 3.58/4.0, graduated May 2025), software engineering intern at TechCorp (summer 2024). Want me to assign Resume.pdf to your resume slot? I see we don't have a transcript field for the degree yet either.",
        "field_ids": [
            "degrees.0.institution", "degrees.0.degree_type", "degrees.0.field_of_study",
            "degrees.0.gpa", "degrees.0.gpa_scale", "degrees.0.end_date",
            "has_work_experience", "jobs.0.employer", "jobs.0.title", "jobs.0.start_date",
            "jobs.0.end_date", "jobs.0.description",
        ],
        "field_values": [
            "University of Anytown", "bachelor", "Computer Science",
            "3.58", "4.0", "2025-05",
            "true", "TechCorp", "Software Engineering Intern", "2024-06",
            "2024-08", "Developed internal tools using Python and Flask. Collaborated with frontend developers on React UI.",
        ],
        "question": "Would you like to assign Resume.pdf to your resume slot?",
        "options": ["Yes, save as my Resume", "No, this is just for extracting info"],
        "summary_title": "", "summary_content": "",
    },
})

# R6 — employer/title swap on resume (subset of R5's resume content; isolated)
seeds.append({
    "test_id": "seed-R6",
    "source": "R6",
    "cannot_targets": ["#7_wrong_field_value"],
    "input": {
        "form_state": {
            "email": "user@test.com", "program": "cs", "start_term": "fall_2026",
            "enrollment_type": "full_time", "prior_application": False,
            "full_name": "Pat Lee", "dob": "1995-04-10",
            "country_citizenship": "US", "country_residence": "US",
            "phone": "+1-415-555-6677",
            "mailing_address": "200 California St, San Francisco, CA 94111",
            "degrees-0-institution": "Stanford", "degrees-0-degree_type": "bachelor",
            "degrees-0-field_of_study": "Computer Science", "degrees-0-gpa": 3.85,
            "degrees-0-gpa_scale": "4.0",
            "degrees-0-start_date": "2013-09", "degrees-0-end_date": "2017-06",
        },
        "conversation_history": [
            {"role": "assistant", "content": "Now let's cover your work experience. Tell me about your most recent role."},
        ],
        "user_message": "I worked as a Software Engineering Intern at TechCorp in summer 2024, in San Francisco. Built internal tools in Python and collaborated with the frontend team on React UI.",
    },
    "correct_answer": {
        "flags": {"has_new_data": True, "needs_choice": False, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Got it — Software Engineering Intern at TechCorp, summer 2024, building internal tools in Python and React UI work. Any other roles to add?",
        "field_ids": [
            "has_work_experience", "jobs.0.employer", "jobs.0.title",
            "jobs.0.start_date", "jobs.0.end_date", "jobs.0.description",
        ],
        "field_values": [
            "true", "TechCorp", "Software Engineering Intern",
            "2024-06", "2024-08",
            "Built internal tools in Python and collaborated with the frontend team on React UI.",
        ],
        "question": "", "options": [],
        "summary_title": "", "summary_content": "",
    },
})

# R11 — claims fields empty when filled
seeds.append({
    "test_id": "seed-R11",
    "source": "R11",
    "cannot_targets": ["#3_state_check"],
    "input": {
        "form_state": {
            "email": "letsee@aa.com", "program": "cs", "start_term": "spring_2027",
            "enrollment_type": "full_time", "prior_application": False,
            "full_name": "Let Sea",
        },
        "conversation_history": [
            {"role": "assistant", "content": "What's your date of birth?"},
            {"role": "user", "content": "01/01/2012 is my DOB"},
            {"role": "assistant", "content": "Saved. What's your country of citizenship?"},
            {"role": "user", "content": "US"},
            {"role": "assistant", "content": "Got it — US citizen. And where do you currently reside?"},
            {"role": "user", "content": "US too"},
        ],
        "user_message": "i don't see my personal information filled",
    },
    "correct_answer": {
        "flags": {"has_new_data": False, "needs_choice": False, "wants_review": True,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Let me show you what's saved so far. Your name (Let Sea), email (letsee@aa.com), and program selection are recorded. Citizenship and residence haven't been saved to the form yet — let me get those in now.",
        "field_ids": [], "field_values": [],
        "question": "", "options": [],
        "summary_title": "Saved so far",
        "summary_content": "Email: letsee@aa.com. Program: Computer Science (MS), Spring 2027, Full-time. Full name: Let Sea. Still needed: date of birth, country of citizenship, country of residence, phone, mailing address.",
    },
})

# R12 — Alex Chen confab on fresh new session
seeds.append({
    "test_id": "seed-R12",
    "source": "R12",
    "cannot_targets": ["#8_training_data_hallucination", "#4_commits_regardless"],
    "input": {
        "form_state": {"email": "chatty@hh.com"},
        "conversation_history": [
            {"role": "user", "content": "chatty@hh.com is starting a brand-new Northfield University Graduate Application. Nothing has been filled in yet, and there's no information from any past applications to reuse. Welcome them warmly and ask which graduate program they'd like to apply to, presenting the available programs as choices they can pick from."},
            {"role": "assistant", "content": "Welcome! Excited to help you start your application. Which graduate program would you like to apply to?"},
        ],
        "user_message": "how is your day? let's take this slow",
    },
    "correct_answer": {
        "flags": {"has_new_data": False, "needs_choice": True, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Going great, thanks 😊 No rush at all — we'll go at whatever pace works. Whenever you're ready, which program would you like to apply to?",
        "field_ids": [], "field_values": [],
        "question": "Which graduate program would you like to apply to?",
        "options": ["Computer Science (MS)", "Data Science (MS)", "Business Administration (MBA)",
                    "Education (MEd)", "Public Health (MPH)", "Mechanical Engineering (MS)"],
        "summary_title": "", "summary_content": "",
    },
})

# R13 — false-positive extraction on filler
seeds.append({
    "test_id": "seed-R13",
    "source": "R13",
    "cannot_targets": ["#4_commits_regardless"],
    "input": {
        "form_state": {
            "email": "kkkl@oka.com", "program": "cs",
        },
        "conversation_history": [
            {"role": "user", "content": "[system] User selected option: \"Computer Science (MS)\""},
            {"role": "assistant", "content": "Computer Science it is. When would you like to start?"},
            {"role": "user", "content": "this is Northfield University?"},
            {"role": "assistant", "content": "Yes, this is Northfield's Computer Science program. When would you like to start?"},
        ],
        "user_message": "can you tell me more about it",
    },
    "correct_answer": {
        "flags": {"has_new_data": False, "needs_choice": True, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "Sure — Northfield's CS MS is a graduate program in computer science. Beyond that I don't have specific program details to share, but the application here will collect what's needed. Want to pick a start term to keep moving?",
        "field_ids": [], "field_values": [],
        "question": "When would you like to start?",
        "options": ["Fall 2026", "Spring 2027"],
        "summary_title": "", "summary_content": "",
    },
})

# R3 — Medical Assistant program hallucinated
seeds.append({
    "test_id": "seed-R3",
    "source": "R3",
    "cannot_targets": ["#8_training_data_hallucination"],
    "input": {
        "form_state": {
            "email": "jane.smith@email.com", "program": "cs", "start_term": "fall_2026",
            "enrollment_type": "full_time", "prior_application": False,
            "full_name": "Jane Smith", "dob": "1998-05-15",
            "country_citizenship": "US", "country_residence": "US",
            "phone": "+1-555-0123",
            "mailing_address": "123 Oak Street, Springfield, IL 62704",
            "degrees-0-institution": "MIT", "degrees-0-degree_type": "bachelor",
            "degrees-0-field_of_study": "Computer Science",
            "degrees-0-gpa": 3.85, "degrees-0-gpa_scale": "4.0",
            "degrees-0-start_date": "2016-09", "degrees-0-end_date": "2020-05",
        },
        "conversation_history": [
            {"role": "assistant", "content": "Could you share your supporting documents — transcript, statement of purpose, resume?"},
        ],
        "user_message": "[File: jane-transcript.pdf]\nUNOFFICIAL TRANSCRIPT\nMassachusetts Institute of Technology\nStudent: Jane Smith\nStudent ID: 912345678\nDegree: Bachelor of Science in Computer Science\nConferred: May 2020\n[End of jane-transcript.pdf]",
    },
    "correct_answer": {
        "flags": {"has_new_data": True, "needs_choice": True, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "This looks like your official MIT transcript! Where would you like me to assign it?",
        "field_ids": [], "field_values": [],
        "question": "Where would you like to assign jane-transcript.pdf?",
        "options": [
            "Official Transcript for Degree #1 (MIT)",
            "Statement of Purpose",
            "Additional Supporting Documents",
        ],
        "summary_title": "", "summary_content": "",
    },
})

# Stanford finding — model says Stanford CS instead of Northfield
seeds.append({
    "test_id": "seed-stanford",
    "source": "manual session — Stanford finding",
    "cannot_targets": ["#8_training_data_hallucination"],
    "input": {
        "form_state": {
            "email": "user@test.com", "program": "cs", "start_term": "fall_2026",
            "enrollment_type": "full_time",
        },
        "conversation_history": [
            {"role": "user", "content": "[system] User selected option: \"Computer Science (MS)\""},
            {"role": "assistant", "content": "Great choice! When would you like to start?"},
            {"role": "user", "content": "[system] User selected option: \"Fall 2026\""},
            {"role": "assistant", "content": "Fall 2026 it is. Full-time or part-time?"},
            {"role": "user", "content": "[system] User selected option: \"Full-time\""},
        ],
        "user_message": "nvm, can you tell more about this school",
    },
    "correct_answer": {
        "flags": {"has_new_data": False, "needs_choice": False, "wants_review": False,
                  "wants_save": False, "wants_submit": False},
        "response_text": "This is Northfield University. Beyond what's covered in the application here, I don't have additional details about the school to share. Was there something specific you wanted to know — about the program, deadlines, or something else?",
        "field_ids": [], "field_values": [],
        "question": "", "options": [],
        "summary_title": "", "summary_content": "",
    },
})


# ════════════════════════════════════════════════════════════════════
# Write
# ════════════════════════════════════════════════════════════════════

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w") as f:
    for s in seeds:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")
print(f"Wrote {len(seeds)} seeds to {OUT_PATH}")

# Verify all parse
for line in open(OUT_PATH):
    json.loads(line)
print("All seeds parse cleanly.")

# Summary
from collections import Counter
sources = Counter(s["source"][0] if s["source"][0] in "PR" else "M" for s in seeds)
cannot_counts = Counter()
for s in seeds:
    for c in s["cannot_targets"]:
        cannot_counts[c] += 1
print(f"\nBy source: {dict(sources)}")
print(f"By CANNOT (a seed can target multiple):")
for c, n in sorted(cannot_counts.items()):
    print(f"  {c}: {n}")
