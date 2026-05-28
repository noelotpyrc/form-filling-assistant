#!/usr/bin/env python3
"""
Mutate real SFT extractor examples with a cheap LLM to generate diverse GRPO training data.

Takes the 578 real data_extractor examples (natural user messages, real conversation
history, real form states) and asks the configured LLM to rewrite them with new user
profiles while keeping the same field_ids and structure.

Usage:
    cd python
    uv run python ../tuning/rl/mutate_extractor_data.py --count 3000
    uv run python ../tuning/rl/mutate_extractor_data.py --preview 5  # dry run

The model used to generate the current `grpo_extractor_mutated.jsonl` dataset is
configured by the `model=` argument inside `call_haiku` below. Change it there if
you want to regenerate with a different LLM — the model choice is an implementation
detail of data generation and is not expected to be stable across regenerations.

Legacy naming: internal names (`call_haiku`, `parse_haiku_response`, and the
`source="haiku_mutation"` label on output rows) predate the current implementation
and are kept for backward compatibility with existing rows in
`grpo_extractor_mutated.jsonl`. They are not an accurate description of the
provider actually called.
"""

import json
from datetime import datetime
import random
import argparse
import asyncio
import sys
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "tuning" / "sft"))

from gen_format_data import DataExtractorSignature
from dspy.adapters.chat_adapter import ChatAdapter

# Import value generators from gen_grpo_data
from gen_grpo_data import (
    random_name, random_full_name, random_email, random_phone,
    random_date, format_date_iso, format_date_human, random_address,
    random_gpa, random_gre_score, random_english_score,
    FIRST_NAMES, LAST_NAMES, INSTITUTIONS, EMPLOYERS, JOB_TITLES,
    FIELDS_OF_STUDY, HOW_HEARD_LABELS,
)

adapter = ChatAdapter()

# ══════════════════════════════════════════════════════════════════════
# Load real extractor examples from SFT data
# ══════════════════════════════════════════════════════════════════════

def load_real_examples(sft_path: str) -> list[dict]:
    """Load data_extractor examples from SFT training data."""
    examples = []
    with open(sft_path) as f:
        for line in f:
            d = json.loads(line)
            if d.get("module") != "data_extractor":
                continue

            user_content = d["messages"][1]["content"]
            asst_content = d["messages"][2]["content"]

            # Parse out the parts
            if "[[ ## user_message ## ]]" not in user_content:
                continue

            ctx_part, msg_part = user_content.split("[[ ## user_message ## ]]", 1)

            # Extract user message (before "Respond with...")
            user_msg = msg_part.split("Respond with the corresponding")[0].strip()

            # Extract filled fields
            filled_fields = {}
            if "Filled fields: " in ctx_part:
                filled_str = ctx_part.split("Filled fields: ")[1].split("\n\n")[0].strip()
                try:
                    filled_fields = json.loads(filled_str)
                except json.JSONDecodeError:
                    pass

            # Extract conversation history
            conv_history = ""
            if "Recent conversation:" in ctx_part:
                conv_history = ctx_part.split("Recent conversation:\n")[1].strip()

            # Parse assistant output for field_ids and field_values
            field_ids = []
            field_values = []
            if "[[ ## field_ids ## ]]" in asst_content and "[[ ## field_values ## ]]" in asst_content:
                ids_part = asst_content.split("[[ ## field_ids ## ]]")[1].split("[[ ## field_values ## ]]")[0].strip()
                vals_part = asst_content.split("[[ ## field_values ## ]]")[1].split("[[ ## completed ## ]]")[0].strip()
                try:
                    field_ids = json.loads(ids_part)
                    field_values = json.loads(vals_part)
                except json.JSONDecodeError:
                    continue

            if not field_ids:
                continue

            # Classify the example type
            if user_msg.startswith("[File:"):
                msg_type = "file_upload"
            elif user_msg.startswith("[system] User selected option:"):
                msg_type = "system_option"
            else:
                msg_type = "natural"

            examples.append({
                "user_message": user_msg,
                "filled_fields": filled_fields,
                "conversation_history": conv_history,
                "field_ids": field_ids,
                "field_values": field_values,
                "system_message": d["messages"][0]["content"],
                "full_context_prefix": ctx_part,
                "msg_type": msg_type,
            })

    return examples


# ══════════════════════════════════════════════════════════════════════
# Generate synthetic user profiles
# ══════════════════════════════════════════════════════════════════════

def generate_user_profile() -> dict:
    """Generate a complete synthetic user profile with all possible field values."""
    first, last = random_name()
    full_name = f"{first} {last}"
    dob = random_date(1980, 2004)
    email = random_email(first, last)

    # Generate degree info
    deg_inst = random.choice(INSTITUTIONS)
    deg_type = random.choice(["bachelor", "master", "doctorate", "associate"])
    deg_type_human = {"bachelor": "Bachelor's", "master": "Master's", "doctorate": "PhD", "associate": "Associate's"}[deg_type]
    deg_field = random.choice(FIELDS_OF_STUDY)
    deg_gpa = random_gpa()
    deg_scale = random.choice(["4.0", "5.0"])
    deg_start = random.randint(2010, 2021)
    deg_end = deg_start + random.randint(2, 6)

    # Job info
    job_employer = random.choice(EMPLOYERS)
    job_title = random.choice(JOB_TITLES)
    job_start_year = random.randint(2016, 2023)
    job_end_year = job_start_year + random.randint(1, 4)

    # Recommender info
    rec_first, rec_last = random_name()
    rec_prefix = random.choice(["Prof.", "Dr.", ""])
    rec_name = f"{rec_prefix} {rec_first} {rec_last}".strip()
    rec_email = random_email(rec_first, rec_last)
    rec_rel = random.choice(["professor", "employer", "advisor", "mentor"])
    rec_inst = random.choice(INSTITUTIONS + EMPLOYERS[:10])

    program_map = {
        "cs": "Computer Science",
        "data_science": "Data Science",
        "mba": "Business Administration",
        "education": "Education",
        "public_health": "Public Health",
        "engineering": "Engineering",
    }
    program_val = random.choice(list(program_map.keys()))

    country_map = {
        "US": "American", "CA": "Canadian", "UK": "British",
        "IN": "Indian", "CN": "Chinese", "KR": "Korean",
        "JP": "Japanese", "DE": "German", "FR": "French",
        "BR": "Brazilian", "MX": "Mexican", "NG": "Nigerian",
        "AU": "Australian", "NZ": "from New Zealand",
    }
    country_val = random.choice(list(country_map.keys()))

    how_heard_val = random.choice(list(HOW_HEARD_LABELS.keys()))

    gre_verbal = random_gre_score("verbal")
    gre_quant = random_gre_score("quant")
    gre_writing = random_gre_score("writing")
    gre_date = random_date(2023, 2026)

    return {
        "first_name": first,
        "last_name": last,
        "full_name": full_name,
        "preferred_name": random.choice([first, first[:3], f"{first}y"]),
        "dob_iso": format_date_iso(dob),
        "dob_human": format_date_human(dob),
        "email": email,
        "phone": random_phone(),
        "address": random_address(),
        "gender": random.choice(["male", "female", "non_binary", "prefer_not_to_say"]),
        "country": country_val,
        "country_human": country_map[country_val],
        "program": program_val,
        "program_human": program_map[program_val],
        "start_term": random.choice(["fall_2026", "spring_2027"]),
        "enrollment": random.choice(["full_time", "part_time"]),
        "degree_institution": deg_inst,
        "degree_type": deg_type,
        "degree_type_human": deg_type_human,
        "degree_field": deg_field,
        "degree_gpa": str(deg_gpa),
        "degree_scale": deg_scale,
        "degree_start": str(deg_start),
        "degree_end": str(deg_end),
        "job_employer": job_employer,
        "job_title": job_title,
        "job_start": str(job_start_year),
        "job_end": str(job_end_year),
        "recommender_name": rec_name,
        "recommender_email": rec_email,
        "recommender_relationship": rec_rel,
        "recommender_institution": rec_inst,
        "how_heard": how_heard_val,
        "how_heard_human": random.choice(HOW_HEARD_LABELS[how_heard_val]),
        "gre_verbal": str(gre_verbal),
        "gre_quant": str(gre_quant),
        "gre_writing": str(gre_writing),
        "gre_date_iso": format_date_iso(gre_date),
        "gre_date_human": format_date_human(gre_date),
        "funding_types": random.sample(
            ["teaching_assistantship", "research_assistantship", "fellowship", "scholarship"],
            k=random.randint(1, 3),
        ),
    }


# ══════════════════════════════════════════════════════════════════════
# Haiku mutation prompt
# ══════════════════════════════════════════════════════════════════════

MUTATION_SYSTEM = """You are a data mutation assistant. You rewrite form-filling conversation examples with new user information while preserving the exact same structure and field mappings.

Rules:
1. Keep the SAME field_ids — do not add or remove any
2. Replace values in the user message with values from the new profile
3. Vary the wording slightly — don't just do find-and-replace, make it sound natural
4. Update the conversation history to be coherent with the new values
5. Update filled_fields JSON to use new profile values where applicable
6. Output valid JSON only — no markdown, no explanation"""


def build_mutation_prompt(example: dict, profile: dict) -> str:
    """Build the Haiku prompt to mutate one example."""

    # Determine which profile fields are relevant based on field_ids
    relevant_profile_keys = []
    for fid in example["field_ids"]:
        # Map field_ids to profile keys
        if "full_name" in fid:
            relevant_profile_keys.extend(["full_name", "first_name", "last_name"])
        elif "preferred_name" in fid:
            relevant_profile_keys.append("preferred_name")
        elif "dob" in fid:
            relevant_profile_keys.extend(["dob_iso", "dob_human"])
        elif "email" in fid and "recommender" not in fid:
            relevant_profile_keys.append("email")
        elif "phone" in fid:
            relevant_profile_keys.append("phone")
        elif "mailing_address" in fid:
            relevant_profile_keys.append("address")
        elif "gender" in fid:
            relevant_profile_keys.append("gender")
        elif "country" in fid:
            relevant_profile_keys.extend(["country", "country_human"])
        elif "program" in fid:
            relevant_profile_keys.extend(["program", "program_human"])
        elif "start_term" in fid:
            relevant_profile_keys.append("start_term")
        elif "enrollment" in fid:
            relevant_profile_keys.append("enrollment")
        elif "institution" in fid and "recommender" not in fid:
            relevant_profile_keys.append("degree_institution")
        elif "degree_type" in fid:
            relevant_profile_keys.extend(["degree_type", "degree_type_human"])
        elif "field_of_study" in fid:
            relevant_profile_keys.append("degree_field")
        elif "gpa" in fid and "scale" not in fid:
            relevant_profile_keys.append("degree_gpa")
        elif "gpa_scale" in fid:
            relevant_profile_keys.append("degree_scale")
        elif fid.endswith("start_date") and "job" not in fid:
            relevant_profile_keys.append("degree_start")
        elif fid.endswith("end_date") and "job" not in fid:
            relevant_profile_keys.append("degree_end")
        elif "employer" in fid:
            relevant_profile_keys.append("job_employer")
        elif "title" in fid:
            relevant_profile_keys.append("job_title")
        elif fid.startswith("jobs") and "start" in fid:
            relevant_profile_keys.append("job_start")
        elif fid.startswith("jobs") and "end" in fid:
            relevant_profile_keys.append("job_end")
        elif "recommender" in fid and "name" in fid:
            relevant_profile_keys.append("recommender_name")
        elif "recommender" in fid and "email" in fid:
            relevant_profile_keys.append("recommender_email")
        elif "recommender" in fid and "relationship" in fid:
            relevant_profile_keys.append("recommender_relationship")
        elif "recommender" in fid and "institution" in fid:
            relevant_profile_keys.append("recommender_institution")
        elif "how_heard" in fid:
            relevant_profile_keys.extend(["how_heard", "how_heard_human"])
        elif "gre_verbal" in fid:
            relevant_profile_keys.append("gre_verbal")
        elif "gre_quant" in fid:
            relevant_profile_keys.append("gre_quant")
        elif "gre_writing" in fid:
            relevant_profile_keys.append("gre_writing")
        elif "gre_date" in fid:
            relevant_profile_keys.extend(["gre_date_iso", "gre_date_human"])
        elif "funding_type" in fid:
            relevant_profile_keys.append("funding_types")
        elif "prior_application" in fid:
            pass  # boolean, no profile value needed
        elif "has_work_experience" in fid:
            pass
        elif "gre_taken" in fid:
            pass
        elif "disability" in fid:
            pass
        elif "toefl_required" in fid:
            pass
        elif "funding_interest" in fid:
            pass
        elif "anything_else" in fid:
            pass
        elif "english_test" in fid:
            pass

    # Build relevant profile subset
    relevant_profile = {k: profile[k] for k in set(relevant_profile_keys) if k in profile}

    # Always include identity for filled_fields mutation
    relevant_profile["full_name"] = profile["full_name"]
    relevant_profile["email"] = profile["email"]

    return f"""Rewrite this form-filling example with the new user profile below.

ORIGINAL EXAMPLE:
- User message: {json.dumps(example["user_message"])}
- field_ids (DO NOT CHANGE): {json.dumps(example["field_ids"])}
- field_values (old): {json.dumps(example["field_values"])}
- Filled fields context: {json.dumps(example["filled_fields"])}
- Conversation history: {json.dumps(example["conversation_history"][:500] if example["conversation_history"] else "")}

NEW USER PROFILE:
{json.dumps(relevant_profile, indent=2)}

Output a JSON object with exactly these keys:
- "user_message": the rewritten user message with new values and slightly varied wording
- "field_values": updated values matching the new profile (same order as field_ids)
- "filled_fields": updated filled fields dict with new profile values swapped in where relevant
- "conversation_history": rewritten conversation history (keep it brief, coherent with new values)

Important:
- field_ids stays EXACTLY the same: {json.dumps(example["field_ids"])}
- For boolean fields (prior_application, has_work_experience, etc.), keep the same True/False value
- For select fields, use the schema value (e.g., "cs" not "Computer Science", "US" not "American")
- Dates in field_values must be ISO format (YYYY-MM-DD or YYYY-MM)
- Keep the same conversational tone and length as the original"""


# ══════════════════════════════════════════════════════════════════════
# Programmatic mutation: system option selections
# ══════════════════════════════════════════════════════════════════════

# Map field_id to all possible (option_label, schema_value) pairs
OPTION_MAP = {
    "program": [
        ("Computer Science (MS)", "cs"), ("Data Science (MS)", "data_science"),
        ("Business Administration (MBA)", "mba"), ("Education (MEd)", "education"),
        ("Public Health (MPH)", "public_health"), ("Engineering (MS)", "engineering"),
    ],
    "start_term": [("Fall 2026", "fall_2026"), ("Spring 2027", "spring_2027")],
    "enrollment_type": [("Full-time", "full_time"), ("Part-time", "part_time")],
    "prior_application": [("Yes", "True"), ("No", "False")],
    "has_work_experience": [("Yes", "True"), ("Yes, I have work experience", "True"),
                            ("No", "False"), ("No, skip this section", "False")],
    "gre_taken": [("Yes", "True"), ("Not yet", "False"), ("No", "False")],
    "funding_interest": [("Yes", "True"), ("Yes, I'm interested", "True"),
                         ("Yes, I'm interested!", "True"), ("Yes, I'd like to be considered", "True"),
                         ("No", "False"), ("No, not at this time", "False")],
    "funding_type": [
        ("Research Assistantship", "['research_assistantship']"),
        ("Teaching Assistantship", "['teaching_assistantship']"),
        ("Fellowship", "['fellowship']"),
        ("Scholarship", "['scholarship']"),
        ("All of the above!", "['teaching_assistantship', 'research_assistantship', 'fellowship', 'scholarship']"),
        ("All of them!", "['teaching_assistantship', 'research_assistantship', 'fellowship', 'scholarship']"),
    ],
    "gender": [("Male", "male"), ("Female", "female"), ("Non-binary", "non_binary"),
               ("Prefer not to say", "prefer_not_to_say")],
    "how_heard": [("Web Search", "web_search"), ("Social Media", "social_media"),
                  ("Referral", "referral"), ("Education Fair", "education_fair"),
                  ("Alumni", "alumni")],
    "toefl_required": [("Yes", "True"), ("No", "False")],
    "english_test_type": [("TOEFL", "toefl"), ("IELTS", "ielts")],
    "disability_accommodation": [("Yes", "True"), ("No", "False")],
}


def mutate_system_option(example: dict, profile: dict) -> dict | None:
    """Programmatically mutate a [system] User selected option example.

    For pure option clicks: swap to a different option.
    For option + natural language follow-up: use Haiku (return None to signal that).
    """
    user_msg = example["user_message"]
    field_ids = example["field_ids"]
    field_values = example["field_values"]

    # Check if there's natural language after the system option line
    lines = user_msg.split("\n", 1)
    has_followup = len(lines) > 1 and lines[1].strip() != ""

    # If multiple field_ids or natural language follow-up, fall back to Haiku
    if has_followup or len(field_ids) > 1:
        return None  # Signal: use Haiku for this one

    # Pure single-field option click — mutate programmatically
    field_id = field_ids[0]

    if field_id not in OPTION_MAP:
        return None  # Unknown field, fall back to Haiku

    # Pick a different option than current
    current_val = field_values[0]
    candidates = [(label, val) for label, val in OPTION_MAP[field_id] if val != current_val]
    if not candidates:
        candidates = OPTION_MAP[field_id]  # fallback: allow same value

    new_label, new_val = random.choice(candidates)
    new_user_msg = f'[system] User selected option: "{new_label}"'

    # Mutate filled fields — swap identity values from profile
    new_filled = mutate_filled_fields(example["filled_fields"], profile)

    return {
        "user_message": new_user_msg,
        "field_values": [new_val],
        "filled_fields": new_filled,
        "conversation_history": example["conversation_history"],
    }


# ══════════════════════════════════════════════════════════════════════
# Programmatic mutation: file uploads
# ══════════════════════════════════════════════════════════════════════

TRANSCRIPT_TEMPLATES = [
    {
        "institution": "Stanford University",
        "student": None,  # filled from profile
        "student_id": None,  # random
        "degree": "Bachelor of Science in {field}",
        "conferred": "{end_year}",
        "courses": [
            ("{field} 101 Introduction (A)", "{field} 201 Advanced Topics (A-)"),
            ("Research Methods (A)", "Statistics (B+)"),
            ("Senior Thesis (A)", "Capstone Project (A-)"),
        ],
        "gpa": None,  # from profile
    },
    {
        "institution": "University of California, Berkeley",
        "student": None,
        "student_id": None,
        "degree": "Bachelor of Arts in {field}",
        "conferred": "{end_year}",
        "courses": [
            ("Intro to {field} (A-)", "Intermediate {field} (B+)"),
            ("Advanced Seminar (A)", "Lab Research (A)"),
            ("Independent Study (A-)", "Thesis Writing (A)"),
        ],
        "gpa": None,
    },
]


def mutate_file_upload(example: dict, profile: dict) -> dict | None:
    """Mutate a file upload example with new student info."""
    user_msg = example["user_message"]
    field_ids = example["field_ids"]
    field_values = example["field_values"]

    # Generate new transcript content
    inst = profile["degree_institution"]
    student_name = profile["full_name"]
    student_id = str(random.randint(100000000, 999999999))
    field_of_study = profile["degree_field"]
    degree_type = profile["degree_type_human"]
    gpa = profile["degree_gpa"]
    gpa_scale = profile["degree_scale"]
    end_year = profile["degree_end"]
    start_year = profile["degree_start"]

    # Generate a realistic filename
    name_part = profile["full_name"].lower().replace(" ", "-")
    filename = random.choice([
        f"{name_part}-transcript.pdf",
        f"transcript-{name_part}.pdf",
        f"{profile['last_name'].lower()}_transcript.pdf",
        f"official-transcript-{name_part}.pdf",
        f"{profile['first_name'].lower()}_transcript.pdf",
    ])

    # Build transcript content
    transcript = f"""[File: {filename}]
UNOFFICIAL TRANSCRIPT
{inst}

Student: {student_name}
Student ID: {student_id}
Degree: {degree_type} in {field_of_study}
Conferred: May {end_year}

Course History:
Fall {start_year}: Introduction to {field_of_study} (A), General Education (B+), Research Methods (A-)
Spring {int(start_year)+1}: Advanced {field_of_study} (A), Statistics (A-), Lab Techniques (B+)
Fall {int(start_year)+1}: {field_of_study} Seminar (A-), Data Analysis (A), Elective (A)
Spring {int(start_year)+2}: Independent Research (A), Senior Seminar (A-), Capstone (A)

Cumulative GPA: {gpa} / {gpa_scale}
Dean's List: Fall {start_year} - Spring {end_year}
[End of {filename}]"""

    # Add optional follow-up text (from original if present)
    lines = user_msg.split("[End of")
    if len(lines) > 1:
        after_file = lines[-1].split("]", 1)
        if len(after_file) > 1 and after_file[1].strip():
            transcript += "\n" + after_file[1].strip()
    else:
        # Add a simple follow-up sometimes
        if random.random() < 0.5:
            followups = [
                f"\nHere's my transcript from {inst}!",
                f"\nUploading my {inst} transcript now.",
                f"\nYep, here it is! That's my only degree.",
                f"\nHere you go — let me know if you need anything else.",
            ]
            transcript += random.choice(followups)

    # Update field_values
    new_values = []
    for fid, old_val in zip(field_ids, field_values):
        if "transcript" in fid:
            new_values.append(filename)
        elif "institution" in fid:
            new_values.append(inst)
        elif "degree_type" in fid:
            new_values.append(profile["degree_type"])
        elif "field_of_study" in fid:
            new_values.append(field_of_study)
        elif fid.endswith(".gpa") and "scale" not in fid:
            new_values.append(gpa)
        elif "gpa_scale" in fid:
            new_values.append(gpa_scale)
        elif "start_date" in fid:
            new_values.append(f"{start_year}-09")
        elif "end_date" in fid:
            new_values.append(f"{end_year}-05")
        else:
            new_values.append(old_val)

    new_filled = mutate_filled_fields(example["filled_fields"], profile)

    return {
        "user_message": transcript,
        "field_values": new_values,
        "filled_fields": new_filled,
        "conversation_history": example["conversation_history"],
    }


# ══════════════════════════════════════════════════════════════════════
# Shared: mutate filled fields with new profile identity
# ══════════════════════════════════════════════════════════════════════

def mutate_filled_fields(filled: dict, profile: dict) -> dict:
    """Swap identity-related values in filled fields with profile values."""
    new_filled = dict(filled)

    # Map of filled field keys to profile values
    swap_map = {
        "full_name": profile["full_name"],
        "preferred_name": profile["preferred_name"],
        "email": profile["email"],
        "phone": profile["phone"],
        "mailing_address": profile["address"],
        "dob": profile["dob_iso"],
        "gender": profile["gender"],
        "country_citizenship": profile["country"],
        "country_residence": profile["country"],
        "program": profile["program"],
        "start_term": profile["start_term"],
        "enrollment_type": profile["enrollment"],
    }

    for key, new_val in swap_map.items():
        if key in new_filled:
            new_filled[key] = new_val

    return new_filled


# ══════════════════════════════════════════════════════════════════════
# Call Haiku via cla
# ══════════════════════════════════════════════════════════════════════

_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        import openai
        _openai_client = openai.AsyncOpenAI()
    return _openai_client


async def call_haiku(system: str, user: str, semaphore: asyncio.Semaphore, retries: int = 3) -> str | None:
    """Call GPT-4o-mini via OpenAI API with rate limiting and retries."""
    async with semaphore:
        for attempt in range(retries):
            try:
                client = get_openai_client()
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=2000,
                    temperature=0.7,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "rate" in err_str.lower() or "429" in err_str:
                    wait = (attempt + 1) * 5
                    print(f"  Rate limited, waiting {wait}s (attempt {attempt+1}/{retries})", file=sys.stderr)
                    await asyncio.sleep(wait)
                    continue
                print(f"  OpenAI error: {err_str[:200]}", file=sys.stderr)
                return None
        print(f"  Failed after {retries} retries", file=sys.stderr)
        return None


def validate_value_in_message(field_id: str, field_value: str, user_message: str) -> bool:
    """Check that a field value is grounded in the user message.

    For each field type, verify the value (or a recognizable form of it)
    actually appears in what the user said.
    """
    msg_lower = user_message.lower()
    val_lower = field_value.lower().strip()

    # Boolean fields — check sentiment, not literal "True"/"False"
    if val_lower in ("true", "false"):
        # These are fine as long as the message expresses yes/no sentiment
        # Too many ways to express booleans, so we allow these
        return True

    # List fields (funding_type) — stored as string repr of list
    if val_lower.startswith("[") and val_lower.endswith("]"):
        return True  # Hard to validate list values in natural text

    # File fields — check filename appears
    if field_id.endswith("transcript") or field_id in ("resume", "statement_of_purpose", "additional_docs"):
        # Filename should appear in [File: ...] tag or be mentioned
        return field_value.lower() in msg_lower or "[file:" in msg_lower

    # Select fields — check label or value appears in message
    select_labels = {
        "cs": ["computer science", "cs", "comp sci"],
        "data_science": ["data science", "ds"],
        "mba": ["mba", "business"],
        "education": ["education", "med"],
        "public_health": ["public health", "mph"],
        "engineering": ["engineering"],
        "fall_2026": ["fall 2026", "fall '26", "this fall", "coming fall"],
        "spring_2027": ["spring 2027", "spring '27", "next spring"],
        "full_time": ["full-time", "full time", "fulltime"],
        "part_time": ["part-time", "part time", "parttime"],
        "male": ["male", "man", " m "],
        "female": ["female", "woman", " f "],
        "non_binary": ["non-binary", "non binary", "nonbinary", "nb", "enby"],
        "prefer_not_to_say": ["prefer not", "rather not", "skip", "don't want to"],
        "professor": ["professor", "prof"],
        "employer": ["employer", "boss", "manager", "supervisor"],
        "advisor": ["advisor", "adviser"],
        "mentor": ["mentor"],
        "web_search": ["web search", "google", "searched", "online"],
        "social_media": ["social media", "instagram", "twitter", "linkedin", "reddit"],
        "referral": ["referral", "friend", "colleague", "recommended", "someone"],
        "education_fair": ["fair", "expo", "event"],
        "alumni": ["alumni", "alumnus", "graduate"],
        "toefl": ["toefl"],
        "ielts": ["ielts"],
        "bachelor": ["bachelor", "bs", "ba", "b.s.", "b.a.", "undergrad"],
        "master": ["master", "ms", "ma", "m.s.", "m.a."],
        "doctorate": ["phd", "doctorate", "doctoral", "ph.d"],
        "associate": ["associate"],
    }

    if val_lower in select_labels:
        return any(label in msg_lower for label in select_labels[val_lower])

    # Text/number fields — the value itself (or a close form) should appear in the message
    # Allow partial match for longer values (addresses, descriptions)
    if len(val_lower) > 50:
        # For long values (descriptions, addresses), check key parts
        # At least some significant words should appear
        words = [w for w in val_lower.split() if len(w) > 3]
        if not words:
            return True
        matches = sum(1 for w in words if w in msg_lower)
        return matches >= len(words) * 0.3  # at least 30% of words present

    # For names, emails, phones, short text — check the value appears
    if val_lower in msg_lower:
        return True

    # Check individual parts (e.g., "Jane Smith" — check "Jane" and "Smith")
    parts = val_lower.split()
    if len(parts) >= 2 and all(p in msg_lower for p in parts):
        return True

    # Date normalization: "1995-11-20" should match "November 20, 1995" etc.
    # Just check year appears for date fields
    if "-" in val_lower and len(val_lower) in (7, 10):  # YYYY-MM or YYYY-MM-DD
        year = val_lower[:4]
        return year in msg_lower

    return False


def parse_haiku_response(response_text: str, original: dict) -> dict | None:
    """Parse and validate Haiku's JSON response with strict quality checks."""
    if not response_text:
        return None

    # Try to extract JSON from response
    text = response_text.strip()
    # Remove markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return None

    # Validate required keys
    required = ["user_message", "field_values", "filled_fields"]
    if not all(k in result for k in required):
        return None

    # Validate field_values length matches field_ids
    if len(result["field_values"]) != len(original["field_ids"]):
        return None

    # Ensure all field_values are strings
    result["field_values"] = [str(v) for v in result["field_values"]]

    # Reject if any field_value is empty (Haiku dropped a value)
    if any(v.strip() == "" for v in result["field_values"]):
        return None

    # Strict check: every field_value must be grounded in the user message
    user_msg = result["user_message"]
    for fid, fval in zip(original["field_ids"], result["field_values"]):
        if not validate_value_in_message(fid, fval, user_msg):
            return None

    # Reject if user_message is too short (Haiku collapsed the message)
    if len(result["user_message"].strip()) < 10:
        return None

    # Reject if user_message is identical to original (no mutation happened)
    if result["user_message"].strip() == original["user_message"].strip():
        return None

    return result


# ══════════════════════════════════════════════════════════════════════
# Assemble into GRPO format
# ══════════════════════════════════════════════════════════════════════

FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"

def load_form_context() -> str:
    """Build form context string — same as gen_format_data.py."""
    form = json.load(open(FORM_SCHEMA_PATH))
    parts = [f"Form: {form['name']}", ""]
    for section in form["schema"]["sections"]:
        fields_desc = []
        for f in section["fields"]:
            req = " (required)" if f.get("required") else ""
            ftype = f["type"]
            if ftype == "group":
                sub_fields = [sf["field_id"] for sf in f.get("fields", [])]
                fields_desc.append(f"  {f['field_id']} (group: {', '.join(sub_fields)}){req}")
            elif ftype == "select" and f.get("options"):
                opts = [o.get("label", o.get("value", "")) if isinstance(o, dict) else str(o) for o in f["options"][:5]]
                fields_desc.append(f"  {f['field_id']} (select: {', '.join(opts)}){req}")
            else:
                fields_desc.append(f"  {f['field_id']} ({ftype}){req}")
        parts.append(f"{section['title']}:")
        parts.extend(fields_desc)
    return "\n".join(parts)


FORM_CONTEXT = load_form_context()


def build_grpo_example(original: dict, mutated: dict) -> dict:
    """Assemble a GRPO training example from original + mutated data."""
    # Build context
    ctx = FORM_CONTEXT

    filled = mutated.get("filled_fields", {})
    if filled:
        ctx += f"\n\nFilled fields: {json.dumps(filled)}"

    conv = mutated.get("conversation_history", "")
    if conv:
        ctx += f"\n\nRecent conversation:\n{conv}"

    # Format with DSPy ChatAdapter
    messages = adapter.format(
        signature=DataExtractorSignature,
        demos=[],
        inputs={"context": ctx, "user_message": mutated["user_message"]},
    )

    return {
        "prompt": messages,
        "ground_truth_ids": original["field_ids"],
        "ground_truth_values": mutated["field_values"],
        "source": "haiku_mutation",
    }


# ══════════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════════

async def main_async(args):
    sft_path = str(PROJECT_ROOT / "tuning" / "sft" / "format_train.jsonl")
    real_examples = load_real_examples(sft_path)

    # Split by type
    by_type = {"natural": [], "system_option": [], "file_upload": []}
    for ex in real_examples:
        by_type[ex["msg_type"]].append(ex)

    print(f"Loaded {len(real_examples)} real extractor examples:")
    for t, exs in by_type.items():
        print(f"  {t}: {len(exs)}")

    # Distribute count across types proportionally (but ensure all types get some)
    total = len(real_examples)
    counts_by_type = {
        "natural": int(args.count * len(by_type["natural"]) / total),
        "system_option": int(args.count * len(by_type["system_option"]) / total),
        "file_upload": max(int(args.count * len(by_type["file_upload"]) / total), min(len(by_type["file_upload"]) * 5, args.count // 20)),
    }
    # Give remainder to natural
    counts_by_type["natural"] += args.count - sum(counts_by_type.values())

    print(f"\nTarget counts: {counts_by_type}")

    # ── Phase 1: Programmatic mutations (instant) ──
    results = []
    source_counts = Counter()

    # System option mutations
    print(f"\n--- Phase 1a: System option mutations ({counts_by_type['system_option']}) ---")
    haiku_fallback = []  # option examples that need Haiku (multi-field or has followup)
    for i in range(counts_by_type["system_option"]):
        example = random.choice(by_type["system_option"])
        profile = generate_user_profile()
        mutated = mutate_system_option(example, profile)
        if mutated is None:
            # Falls back to Haiku (has natural language followup)
            haiku_fallback.append((example, profile))
            continue
        grpo_ex = build_grpo_example(example, mutated)
        grpo_ex["source"] = "programmatic_option"
        results.append(grpo_ex)
        source_counts["programmatic_option"] += 1

    print(f"  Generated {source_counts['programmatic_option']} programmatic, "
          f"{len(haiku_fallback)} need Haiku fallback")

    # File upload mutations
    print(f"\n--- Phase 1b: File upload mutations ({counts_by_type['file_upload']}) ---")
    file_errors = 0
    for i in range(counts_by_type["file_upload"]):
        example = random.choice(by_type["file_upload"])
        profile = generate_user_profile()
        mutated = mutate_file_upload(example, profile)
        if mutated is None:
            file_errors += 1
            continue
        # Validate: each field_value grounded in message
        valid = True
        for fid, fval in zip(example["field_ids"], mutated["field_values"]):
            if not validate_value_in_message(fid, fval, mutated["user_message"]):
                valid = False
                break
        if not valid:
            file_errors += 1
            continue
        grpo_ex = build_grpo_example(example, mutated)
        grpo_ex["source"] = "programmatic_file"
        results.append(grpo_ex)
        source_counts["programmatic_file"] += 1

    print(f"  Generated {source_counts['programmatic_file']} file upload mutations "
          f"({file_errors} rejected)")

    # ── Phase 2: Haiku mutations (natural language + option fallbacks) ──
    haiku_tasks = []
    for i in range(counts_by_type["natural"]):
        example = random.choice(by_type["natural"])
        profile = generate_user_profile()
        haiku_tasks.append((example, profile))

    # Add option fallbacks
    haiku_tasks.extend(haiku_fallback)

    print(f"\n--- Phase 2: Haiku mutations ({len(haiku_tasks)}) ---")

    if args.preview > 0:
        print(f"\nPreview of {args.preview} Haiku mutation prompts:")
        for example, profile in haiku_tasks[:args.preview]:
            prompt = build_mutation_prompt(example, profile)
            print(f"\n  Type: {example['msg_type']}")
            print(f"  Original: {example['user_message'][:100]}")
            print(f"  Profile: {profile['full_name']}, {profile['email']}")
            print(f"  Prompt length: {len(prompt)} chars")
        return

    # Open output file for incremental writing
    output_path = args.output or str(Path(__file__).parent / "grpo_extractor_mutated.jsonl")
    outfile = open(output_path, "w")

    # Write programmatic results immediately
    for ex in results:
        outfile.write(json.dumps(ex) + "\n")
    outfile.flush()
    print(f"  Wrote {len(results)} programmatic examples to {output_path}")

    semaphore = asyncio.Semaphore(args.concurrency)
    errors = 0
    error_types = Counter()
    haiku_start_time = datetime.now()
    # Rough cost estimate: gpt-4o-mini ~$0.00015/1K input, $0.0006/1K output
    # Average ~2K input + 0.5K output per call ≈ $0.0006/call
    COST_PER_CALL = 0.0006

    async def process_haiku(idx, example, profile):
        nonlocal errors
        prompt = build_mutation_prompt(example, profile)
        response = await call_haiku(MUTATION_SYSTEM, prompt, semaphore)

        if response is None:
            errors += 1
            error_types["api_error"] += 1
            return None

        mutated = parse_haiku_response(response, example)
        if mutated is None:
            errors += 1
            error_types["validation_failed"] += 1
            return None

        grpo_ex = build_grpo_example(example, mutated)
        grpo_ex["source"] = "haiku_mutation"
        return grpo_ex

    # Process Haiku calls in batches with incremental saving
    batch_size = 100
    total_batches = (len(haiku_tasks) - 1) // batch_size + 1
    for batch_start in range(0, len(haiku_tasks), batch_size):
        batch = haiku_tasks[batch_start:batch_start + batch_size]
        batch_t0 = datetime.now()
        try:
            batch_results = await asyncio.gather(*[
                process_haiku(batch_start + i, ex, prof)
                for i, (ex, prof) in enumerate(batch)
            ])
        except KeyboardInterrupt:
            print(f"\n  [{datetime.now():%H:%M:%S}] Interrupted! Saving progress...", file=sys.stderr)
            break
        except Exception as e:
            print(f"\n  [{datetime.now():%H:%M:%S}] Batch error: {e}. Continuing...", file=sys.stderr)
            continue

        batch_elapsed = (datetime.now() - batch_t0).total_seconds()
        valid = [r for r in batch_results if r is not None]
        results.extend(valid)
        source_counts["haiku_mutation"] += len(valid)

        # Write this batch incrementally
        for ex in valid:
            outfile.write(json.dumps(ex) + "\n")
        outfile.flush()

        batch_num = batch_start // batch_size + 1
        total_elapsed = (datetime.now() - haiku_start_time).total_seconds()
        calls_done = batch_start + len(batch)
        calls_remaining = len(haiku_tasks) - calls_done
        avg_per_call = total_elapsed / calls_done if calls_done else 0
        eta_sec = calls_remaining * avg_per_call
        est_cost = calls_done * COST_PER_CALL
        success_rate = (1 - errors / calls_done) * 100 if calls_done else 0

        print(f"  [{datetime.now():%H:%M:%S}] Batch {batch_num}/{total_batches}: "
              f"{len(valid)}/{len(batch)} valid ({batch_elapsed:.1f}s) | "
              f"Total: {len(results)} examples, {errors} errors "
              f"(api:{error_types['api_error']} val:{error_types['validation_failed']}) | "
              f"Rate: {success_rate:.0f}% | "
              f"Cost: ~${est_cost:.2f} | "
              f"ETA: {eta_sec/60:.0f}min")

    outfile.close()

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"Generated {len(results)} total examples")
    for src, cnt in source_counts.most_common():
        print(f"  {src}: {cnt}")
    print(f"  errors: {errors} (api: {error_types['api_error']}, validation: {error_types['validation_failed']})")
    print(f"\nWrote to {output_path}")

    # Field stats
    field_counts = Counter()
    for ex in results:
        for fid in ex["ground_truth_ids"]:
            parts = fid.split(".")
            if len(parts) == 3 and parts[1].isdigit():
                fid = f"{parts[0]}.*.{parts[2]}"
            field_counts[fid] += 1

    print(f"\nTop 20 fields:")
    for fid, c in field_counts.most_common(20):
        print(f"  {fid}: {c}")


def main():
    parser = argparse.ArgumentParser(description="Mutate extractor examples with Haiku")
    parser.add_argument("--count", type=int, default=30000, help="Number of examples to generate")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL path")
    parser.add_argument("--preview", type=int, default=0, help="Preview N mutation prompts (dry run)")
    parser.add_argument("--concurrency", type=int, default=20, help="Max concurrent Haiku calls")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    random.seed(args.seed)
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
