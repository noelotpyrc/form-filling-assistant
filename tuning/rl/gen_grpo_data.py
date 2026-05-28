#!/usr/bin/env python3
"""
Generate synthetic GRPO training data for DataExtractor RL training.

Creates diverse (prompt, ground_truth) pairs where:
- prompt = DSPy ChatAdapter formatted system+user messages (form context + user message)
- ground_truth = expected field_ids + field_values

Variations:
- Random form states (0-80% fields filled with diverse realistic values)
- Random user messages with varied phrasings per field type
- Single-field and multi-field extractions (1-5 fields per message)
- Edge cases: negations, corrections, embedded questions, file uploads
- Random conversation histories coherent with form state

Usage:
    cd python
    uv run python ../tuning/rl/gen_grpo_data.py --count 3000
    uv run python ../tuning/rl/gen_grpo_data.py --stats  # preview distribution
"""

import json
import random
import argparse
import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent.parent
FORM_SCHEMA_PATH = PROJECT_ROOT / "packages/web-app/public/forms/masters-northfield.json"
sys.path.insert(0, str(PROJECT_ROOT))

import dspy
from dspy.adapters.chat_adapter import ChatAdapter

# Reuse signatures from gen_format_data
sys.path.insert(0, str(PROJECT_ROOT / "tuning" / "sft"))
from gen_format_data import (
    DataExtractorSignature,
    load_form_context,
    FORM_CONTEXT,
)

adapter = ChatAdapter()

# ══════════════════════════════════════════════════════════════════════
# Value generators — realistic, diverse values per field type
# ══════════════════════════════════════════════════════════════════════

FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda",
    "David", "Elizabeth", "Wei", "Yuki", "Priya", "Mohammed", "Fatima", "Carlos",
    "María", "Hiroshi", "Aisha", "Oluwaseun", "Seo-yeon", "Raj", "Chen", "Yuto",
    "Amara", "Diego", "Sofia", "Kenji", "Anya", "Omar", "Liam", "Emma", "Noah",
    "Olivia", "Ethan", "Ava", "Lucas", "Mia", "Alex", "Sam", "Jordan", "Taylor",
    "Deepak", "Sunita", "Kwame", "Ngozi", "Pierre", "Ingrid", "Sven", "Mei-Lin",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "García", "Miller", "Davis",
    "Rodriguez", "Martinez", "Kim", "Lee", "Chen", "Wang", "Patel", "Singh",
    "Nakamura", "Tanaka", "Okafor", "Adeyemi", "Mueller", "Johansson", "O'Brien",
    "van der Berg", "Fernández", "López", "Nguyen", "Trần", "Park", "Suzuki",
    "Ali", "Hassan", "Kowalski", "Petrov", "Ivanova", "Santos", "Oliveira",
    "Schmidt", "Fischer", "Dubois", "Moreau", "Rossi", "Romano", "Thompson",
]

INSTITUTIONS = [
    "MIT", "Stanford University", "UC Berkeley", "Harvard University",
    "University of Michigan", "Georgia Tech", "Carnegie Mellon University",
    "University of Toronto", "Oxford University", "ETH Zurich",
    "National University of Singapore", "Tsinghua University", "IIT Bombay",
    "University of Tokyo", "Seoul National University", "TU Munich",
    "University of São Paulo", "University of Cape Town", "McGill University",
    "University of Melbourne", "Imperial College London", "Caltech",
    "University of Washington", "Cornell University", "Princeton University",
    "Columbia University", "Yale University", "UCLA", "NYU", "Duke University",
    "University of Illinois", "Penn State", "Ohio State University",
    "University of Texas at Austin", "University of Florida",
    "Arizona State University", "University of Wisconsin-Madison",
    "Boston University", "Northeastern University", "Purdue University",
]

EMPLOYERS = [
    "Google", "Microsoft", "Amazon", "Apple", "Meta", "Netflix", "Spotify",
    "Salesforce", "Adobe", "IBM", "Oracle", "Intel", "NVIDIA", "Tesla",
    "SpaceX", "Stripe", "Airbnb", "Uber", "Lyft", "DoorDash",
    "McKinsey & Company", "Boston Consulting Group", "Deloitte", "PwC",
    "Goldman Sachs", "JP Morgan", "Morgan Stanley", "BlackRock",
    "Johns Hopkins Hospital", "Mayo Clinic", "WHO", "UNICEF",
    "World Bank", "United Nations", "Peace Corps", "Teach for America",
    "local startup", "a small consulting firm", "my family's business",
]

JOB_TITLES = [
    "Software Engineer", "Data Analyst", "Research Assistant", "Product Manager",
    "Marketing Coordinator", "Financial Analyst", "Teaching Assistant",
    "Lab Technician", "Project Coordinator", "Business Analyst",
    "UX Designer", "DevOps Engineer", "Machine Learning Engineer",
    "Consultant", "Account Manager", "Operations Associate",
    "Clinical Research Coordinator", "Public Health Analyst",
    "Curriculum Developer", "Program Manager", "Staff Engineer",
    "Senior Developer", "Junior Analyst", "Intern",
]

FIELDS_OF_STUDY = [
    "Computer Science", "Mathematics", "Physics", "Biology", "Chemistry",
    "Economics", "Psychology", "Electrical Engineering", "Mechanical Engineering",
    "Business Administration", "Public Health", "Education", "Data Science",
    "Statistics", "Philosophy", "English Literature", "Political Science",
    "Sociology", "Anthropology", "Environmental Science", "Neuroscience",
    "Biomedical Engineering", "Chemical Engineering", "Civil Engineering",
    "Information Systems", "Finance", "Accounting", "Marketing",
]

STREET_NAMES = [
    "Oak", "Maple", "Cedar", "Pine", "Elm", "Main", "Park", "Lake",
    "Hill", "River", "Spring", "Forest", "Meadow", "Valley", "Summit",
    "Broadway", "Washington", "Lincoln", "Jefferson", "Madison",
]

CITIES = [
    ("Springfield", "IL", "62704"), ("Portland", "OR", "97201"),
    ("Austin", "TX", "78701"), ("Denver", "CO", "80202"),
    ("Seattle", "WA", "98101"), ("Boston", "MA", "02101"),
    ("Chicago", "IL", "60601"), ("San Francisco", "CA", "94102"),
    ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"),
    ("Miami", "FL", "33101"), ("Atlanta", "GA", "30301"),
    ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
    ("Minneapolis", "MN", "55401"), ("Nashville", "TN", "37201"),
    ("Charlotte", "NC", "28201"), ("Columbus", "OH", "43201"),
    ("San Diego", "CA", "92101"), ("Detroit", "MI", "48201"),
]

HOW_HEARD_LABELS = {
    "web_search": ["Google", "web search", "googled it", "searched online", "found it online"],
    "social_media": ["Instagram", "Twitter", "social media", "LinkedIn", "saw it on social media", "Reddit"],
    "referral": ["a friend", "my professor", "someone recommended it", "a colleague", "word of mouth", "referral"],
    "education_fair": ["an education fair", "a college fair", "a grad school expo", "a recruitment event"],
    "alumni": ["an alumnus", "an alumni", "a graduate of the program", "someone who went here"],
    "other": ["other", "not sure", "I don't remember", "a flyer", "an email"],
}


def random_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def random_full_name():
    first, last = random_name()
    return f"{first} {last}"


def random_email(first, last):
    """Generate email from name with variations."""
    domain = random.choice([
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
        "protonmail.com", "mail.com", "aol.com", "zoho.com",
        f"{last.lower().replace(' ', '')}.com",
    ])
    formats = [
        f"{first.lower()}.{last.lower()}@{domain}",
        f"{first.lower()}{last.lower()}@{domain}",
        f"{first[0].lower()}{last.lower()}@{domain}",
        f"{first.lower()}_{last.lower()}@{domain}",
        f"{first.lower()}{random.randint(1, 99)}@{domain}",
        f"{first.lower()}.{last.lower()}{random.randint(1, 999)}@{domain}",
    ]
    return random.choice(formats)


def random_phone():
    """Generate US phone number with format variations."""
    area = random.randint(200, 999)
    mid = random.randint(200, 999)
    last = random.randint(1000, 9999)
    formats = [
        f"+1-{area}-{mid}-{last}",
        f"({area}) {mid}-{last}",
        f"{area}-{mid}-{last}",
        f"+1{area}{mid}{last}",
        f"{area}.{mid}.{last}",
        f"1-{area}-{mid}-{last}",
    ]
    return random.choice(formats)


def random_date(start_year=1970, end_year=2005):
    """Generate a random date."""
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    rand_date = start + timedelta(days=random.randint(0, delta.days))
    return rand_date


def format_date_iso(dt):
    """ISO format for field value."""
    return dt.strftime("%Y-%m-%d")


def format_date_human(dt):
    """Random human-readable date format for user messages."""
    formats = [
        dt.strftime("%B %d, %Y"),          # March 5, 1995
        dt.strftime("%b %d, %Y"),           # Mar 5, 1995
        dt.strftime("%m/%d/%Y"),            # 03/05/1995
        dt.strftime("%m/%d/%y"),            # 03/05/95
        dt.strftime("%d %B %Y"),            # 5 March 1995
        dt.strftime("%B %d %Y"),            # March 5 1995
        f"{dt.strftime('%B')} {dt.day}, {dt.year}",  # March 5, 1995 (no leading zero)
        dt.strftime("%Y-%m-%d"),            # 1995-03-05
    ]
    return random.choice(formats)


def random_address():
    """Generate a random US mailing address."""
    num = random.randint(1, 9999)
    street = random.choice(STREET_NAMES)
    suffix = random.choice(["St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Way", "Ct"])
    city, state, zip_code = random.choice(CITIES)
    apt = ""
    if random.random() < 0.3:
        apt = f", Apt {random.randint(1, 999)}"
    return f"{num} {street} {suffix}{apt}, {city}, {state} {zip_code}"


def random_gpa():
    """Random GPA on 4.0 scale."""
    return round(random.uniform(2.5, 4.0), 2)


def random_gre_score(section):
    if section == "verbal":
        return random.randint(130, 170)
    elif section == "quant":
        return random.randint(130, 170)
    elif section == "writing":
        return round(random.uniform(2.0, 6.0) * 2) / 2  # 0.5 increments


def random_english_score(test_type):
    if test_type == "toefl":
        return random.randint(60, 120)
    else:  # ielts
        return round(random.uniform(5.0, 9.0) * 2) / 2


# ══════════════════════════════════════════════════════════════════════
# Form state generator
# ══════════════════════════════════════════════════════════════════════

# All flat fields and their value generators
FIELD_GENERATORS = {
    # Personal Information
    "full_name": lambda ctx: ctx["full_name"],
    "preferred_name": lambda ctx: ctx["first_name"],
    "dob": lambda ctx: format_date_iso(ctx["dob"]),
    "gender": lambda _: random.choice(["male", "female", "non_binary", "prefer_not_to_say"]),
    "country_citizenship": lambda _: random.choice(["US", "CA", "UK", "AU", "NZ", "IN", "CN", "KR", "JP", "DE", "FR", "BR", "MX", "NG", "OTHER"]),
    "country_residence": lambda _: random.choice(["US", "CA", "UK", "AU", "NZ", "IN", "CN", "KR", "JP", "DE", "FR", "BR", "MX", "NG", "OTHER"]),
    "email": lambda ctx: ctx["email"],
    "phone": lambda _: random_phone(),
    "mailing_address": lambda _: random_address(),
    # Program Selection
    "program": lambda _: random.choice(["cs", "data_science", "mba", "education", "public_health", "engineering"]),
    "start_term": lambda _: random.choice(["fall_2026", "spring_2027"]),
    "enrollment_type": lambda _: random.choice(["full_time", "part_time"]),
    "prior_application": lambda _: random.choice([True, False]),
    "prior_application_year": lambda _: random.randint(2020, 2025),
    # Standardized Test Scores
    "gre_taken": lambda _: random.choice([True, False]),
    "gre_verbal": lambda _: random_gre_score("verbal"),
    "gre_quant": lambda _: random_gre_score("quant"),
    "gre_writing": lambda _: random_gre_score("writing"),
    "gre_date": lambda _: format_date_iso(random_date(2023, 2026)),
    "toefl_required": lambda _: random.choice([True, False]),
    "english_test_type": lambda _: random.choice(["toefl", "ielts"]),
    "english_test_score": lambda _: random.randint(80, 120),  # simplified
    "english_test_date": lambda _: format_date_iso(random_date(2023, 2026)),
    # Work Experience
    "has_work_experience": lambda _: random.choice([True, False]),
    # Additional Information
    "funding_interest": lambda _: random.choice([True, False]),
    "funding_type": lambda _: random.sample(
        ["teaching_assistantship", "research_assistantship", "fellowship", "scholarship"],
        k=random.randint(1, 3),
    ),
    "disability_accommodation": lambda _: random.choice([True, False]),
    "how_heard": lambda _: random.choice(["web_search", "social_media", "referral", "education_fair", "alumni", "other"]),
    "anything_else": lambda _: random.choice([
        "", "Looking forward to this program!",
        "I have a service dog.", "I need parking accommodations.",
        "Excited to join the research group on distributed systems.",
        "I'd love to connect with current students before the semester starts.",
    ]),
}

# Group field generators (degrees, jobs, recommenders)
def gen_degree(idx=0):
    """Generate one degree entry."""
    inst = random.choice(INSTITUTIONS)
    deg = random.choice(["bachelor", "master", "doctorate", "associate"])
    field = random.choice(FIELDS_OF_STUDY)
    gpa = random_gpa()
    scale = random.choice(["4.0", "5.0", "10.0", "percentage"])
    start_year = random.randint(2010, 2022)
    end_year = start_year + random.randint(2, 6)
    prefix = f"degrees.{idx}" if "." not in str(idx) else f"degrees-{idx}"
    # Use dot notation like the real data
    return {
        f"degrees.{idx}.institution": inst,
        f"degrees.{idx}.degree_type": deg,
        f"degrees.{idx}.field_of_study": field,
        f"degrees.{idx}.gpa": gpa,
        f"degrees.{idx}.gpa_scale": scale,
        f"degrees.{idx}.start_date": f"{start_year}-09",
        f"degrees.{idx}.end_date": f"{end_year}-05",
    }


def gen_job(idx=0):
    """Generate one job entry."""
    employer = random.choice(EMPLOYERS)
    title = random.choice(JOB_TITLES)
    start_year = random.randint(2016, 2024)
    end_year = start_year + random.randint(0, 4)
    return {
        f"jobs.{idx}.employer": employer,
        f"jobs.{idx}.title": title,
        f"jobs.{idx}.start_date": f"{start_year}-{random.randint(1,12):02d}",
        f"jobs.{idx}.end_date": f"{end_year}-{random.randint(1,12):02d}",
        f"jobs.{idx}.description": random.choice([
            f"Worked on {random.choice(['backend systems', 'data pipelines', 'ML models', 'frontend apps', 'research projects', 'client engagements'])}",
            f"Led a team of {random.randint(2, 10)} on {random.choice(['product development', 'analytics', 'operations', 'research'])}",
            f"Responsible for {random.choice(['data analysis', 'software development', 'project management', 'curriculum design', 'patient care coordination'])}",
        ]),
    }


def gen_recommender(idx=0):
    """Generate one recommender entry."""
    name_prefix = random.choice(["Prof.", "Dr.", ""])
    first, last = random_name()
    name = f"{name_prefix} {first} {last}".strip()
    rel = random.choice(["professor", "employer", "advisor", "mentor", "other"])
    inst = random.choice(INSTITUTIONS + EMPLOYERS[:15])
    return {
        f"recommenders.{idx}.name": name,
        f"recommenders.{idx}.email": random_email(first, last),
        f"recommenders.{idx}.relationship": rel,
        f"recommenders.{idx}.institution": inst,
    }


def generate_random_form_state(fill_pct=None):
    """Generate a random partial form state.

    Returns (form_state_dict, person_context) where person_context has
    the identity info used to generate values (for coherent user messages).
    """
    if fill_pct is None:
        fill_pct = random.uniform(0, 0.8)

    # Create a "person" for coherent values
    first, last = random_name()
    full_name = f"{first} {last}"
    dob = random_date(1980, 2004)
    email = random_email(first, last)

    person = {
        "first_name": first,
        "last_name": last,
        "full_name": full_name,
        "dob": dob,
        "email": email,
    }

    state = {}
    flat_fields = list(FIELD_GENERATORS.keys())

    # Randomly select which flat fields are filled
    n_flat = int(len(flat_fields) * fill_pct)
    filled_fields = random.sample(flat_fields, min(n_flat, len(flat_fields)))

    for fid in filled_fields:
        val = FIELD_GENERATORS[fid](person)
        state[fid] = val

    # Maybe add degree(s)
    if random.random() < fill_pct:
        n_degrees = random.choices([1, 2], weights=[0.7, 0.3])[0]
        for i in range(n_degrees):
            state.update(gen_degree(i))

    # Maybe add job(s)
    if random.random() < fill_pct and state.get("has_work_experience", False):
        n_jobs = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
        for i in range(n_jobs):
            state.update(gen_job(i))

    # Maybe add recommender(s)
    if random.random() < fill_pct:
        n_recs = random.choices([1, 2, 3], weights=[0.3, 0.5, 0.2])[0]
        for i in range(n_recs):
            state.update(gen_recommender(i))

    return state, person


# ══════════════════════════════════════════════════════════════════════
# User message generator — varied phrasings per field
# ══════════════════════════════════════════════════════════════════════

# Maps field_id -> list of (user_message_template, value_generator) pairs
# Templates use {value} for the generated value, {human_value} for human-readable form
# Some templates generate multiple fields at once

def _bool_phrases(positive, negative):
    """Generate boolean phrasing templates."""
    return {
        True: positive,
        False: negative,
    }

BOOL_PRIOR_APP = _bool_phrases(
    ["Yes, I applied before", "Yeah I've applied to Northfield before", "I applied back in {year}",
     "Yep, submitted an application previously", "I have, yes"],
    ["No, first time applying", "Nope, this is my first time", "This is my first application here",
     "Haven't applied before", "No, never applied", "First time!",
     "No I haven't applied to Northfield before"],
)

BOOL_GRE = _bool_phrases(
    ["Yes, I took the GRE", "I've taken the GRE already", "Yep, took it last year",
     "I have my GRE scores", "Yes I did take the GRE"],
    ["No, haven't taken the GRE", "I haven't taken the GRE yet", "Nope, no GRE",
     "I didn't take the GRE", "Haven't done the GRE", "No GRE scores"],
)

BOOL_WORK_EXP = _bool_phrases(
    ["Yes, I have work experience", "Yeah I've been working", "I do have work experience",
     "Yes, I've worked for a few years", "Yep, got some work experience"],
    ["No work experience", "I don't have any work experience", "No, I'm coming straight from undergrad",
     "Haven't worked yet", "Nope, no professional experience",
     "No, I went straight to grad school applications"],
)

BOOL_FUNDING = _bool_phrases(
    ["Yes, I'm interested in funding", "Definitely interested in financial aid",
     "Yes please, I'd love funding support", "I would like to be considered for funding",
     "Yes, funding would be great"],
    ["No, I don't need funding", "I'm self-funded", "No funding needed",
     "Nah, I've got it covered financially", "No thanks on the funding"],
)

BOOL_DISABILITY = _bool_phrases(
    ["Yes, I need disability accommodations", "I do need some accommodations",
     "Yes, I have a disability that requires accommodation"],
    ["No accommodations needed", "No, I don't need any accommodations", "Nope, all good",
     "No disability accommodations", "I'm fine, no accommodations needed"],
)

BOOL_TOEFL = _bool_phrases(
    ["Yes, I need to take an English proficiency test", "I do need the TOEFL/IELTS",
     "Yes, English isn't my first language so I took the TOEFL"],
    ["No, English is my first language", "I don't need to take the TOEFL",
     "No, I'm a native English speaker", "Nope, no English test needed"],
)


def gen_user_msg_single_field(field_id, person, form_state):
    """Generate a user message providing a single field value.
    Returns (user_message, field_id, field_value) or None.
    """
    first = person["first_name"]
    last = person["last_name"]

    if field_id == "full_name":
        name = random_full_name()
        templates = [
            f"My name is {name}",
            f"It's {name}",
            f"{name}",
            f"My full name is {name}",
            f"I'm {name}",
            f"You can put {name}",
            f"The name's {name}",
            f"Hi, I'm {name}. Let's get started!",
            f"Sure — {name}",
            f"Full name: {name}",
        ]
        return random.choice(templates), "full_name", name

    elif field_id == "preferred_name":
        pref = random.choice([first, first[:3], f"{first}y", random.choice(FIRST_NAMES)])
        templates = [
            f"I go by {pref}",
            f"Just call me {pref}",
            f"My preferred name is {pref}",
            f"People call me {pref}",
            f"You can put {pref} as my preferred name",
            f"{pref} is fine",
        ]
        return random.choice(templates), "preferred_name", pref

    elif field_id == "dob":
        dt = random_date(1980, 2004)
        human = format_date_human(dt)
        iso = format_date_iso(dt)
        templates = [
            f"My date of birth is {human}",
            f"I was born {human}",
            f"DOB: {human}",
            f"Birthday is {human}",
            f"Born on {human}",
            f"I was born on {human} — is that the right format?",
            f"My birthday is {human}",
            f"{human}",
            f"Date of birth — {human}",
            f"Sure, it's {human}",
        ]
        return random.choice(templates), "dob", iso

    elif field_id == "gender":
        val = random.choice(["male", "female", "non_binary", "prefer_not_to_say"])
        human_map = {
            "male": ["male", "I'm a man", "I'm male", "man", "Male", "M"],
            "female": ["female", "I'm a woman", "I'm female", "woman", "Female", "F"],
            "non_binary": ["non-binary", "I'm non-binary", "non binary", "NB", "enby"],
            "prefer_not_to_say": ["prefer not to say", "I'd rather not say", "skip that one",
                                  "I don't want to answer that", "rather not disclose"],
        }
        human = random.choice(human_map[val])
        templates = [
            f"Gender: {human}",
            f"I'm {human}" if not human.startswith("I") else human,
            f"For gender, {human}",
            f"{human}",
            f"Put me down as {human}",
        ]
        return random.choice(templates), "gender", val

    elif field_id in ("country_citizenship", "country_residence"):
        country_labels = {
            "US": ["US", "United States", "USA", "American", "the US", "the United States"],
            "CA": ["Canada", "Canadian", "CA"],
            "UK": ["UK", "United Kingdom", "British", "England", "the UK"],
            "AU": ["Australia", "Australian"],
            "NZ": ["New Zealand", "Kiwi"],
            "IN": ["India", "Indian"],
            "CN": ["China", "Chinese"],
            "KR": ["South Korea", "Korean"],
            "JP": ["Japan", "Japanese"],
            "DE": ["Germany", "German"],
            "FR": ["France", "French"],
            "BR": ["Brazil", "Brazilian"],
            "MX": ["Mexico", "Mexican"],
            "NG": ["Nigeria", "Nigerian"],
            "OTHER": ["other", "another country"],
        }
        val = random.choice(list(country_labels.keys()))
        human = random.choice(country_labels[val])
        label = "citizenship" if field_id == "country_citizenship" else "residence"
        templates = [
            f"I'm from {human}" if label == "citizenship" else f"I live in {human}",
            f"My {label} is {human}",
            f"{human}",
            f"I'm a {human} citizen" if label == "citizenship" else f"I currently reside in {human}",
            f"For {label}, {human}",
        ]
        return random.choice(templates), field_id, val

    elif field_id == "email":
        new_first, new_last = random_name()
        email = random_email(new_first, new_last)
        templates = [
            f"My email is {email}",
            f"Email: {email}",
            f"You can reach me at {email}",
            f"{email}",
            f"Best email is {email}",
            f"Contact me at {email}",
            f"My email address is {email}",
            f"Sure, it's {email}",
        ]
        return random.choice(templates), "email", email

    elif field_id == "phone":
        phone = random_phone()
        templates = [
            f"My phone number is {phone}",
            f"Phone: {phone}",
            f"You can call me at {phone}",
            f"{phone}",
            f"My cell is {phone}",
            f"Best number is {phone}",
            f"Reach me at {phone}",
        ]
        return random.choice(templates), "phone", phone

    elif field_id == "mailing_address":
        addr = random_address()
        templates = [
            f"My address is {addr}",
            f"Mailing address: {addr}",
            f"I live at {addr}",
            f"{addr}",
            f"Send mail to {addr}",
            f"My mailing address is {addr}",
        ]
        return random.choice(templates), "mailing_address", addr

    elif field_id == "program":
        program_labels = {
            "cs": ["Computer Science", "CS", "the CS program", "computer science", "the Computer Science MS", "comp sci"],
            "data_science": ["Data Science", "the data science program", "DS", "data science MS"],
            "mba": ["MBA", "the MBA program", "Business Administration", "business"],
            "education": ["Education", "MEd", "the education program", "Master of Education"],
            "public_health": ["Public Health", "MPH", "the public health program", "master of public health"],
            "engineering": ["Engineering", "the engineering program", "engineering MS"],
        }
        val = random.choice(list(program_labels.keys()))
        human = random.choice(program_labels[val])
        templates = [
            f"I'm applying for {human}",
            f"I want to study {human}",
            f"{human}",
            f"I'd like to apply to {human}",
            f"The {human} program",
            f"Interested in {human}",
            f"I'm looking at the {human} program" if not human.startswith("the") else f"I'm looking at {human}",
        ]
        return random.choice(templates), "program", val

    elif field_id == "start_term":
        val = random.choice(["fall_2026", "spring_2027"])
        human_map = {
            "fall_2026": ["Fall 2026", "fall 2026", "this coming fall", "Fall '26", "the fall semester"],
            "spring_2027": ["Spring 2027", "spring 2027", "next spring", "Spring '27", "the spring semester"],
        }
        human = random.choice(human_map[val])
        templates = [
            f"I want to start {human}",
            f"Starting {human}",
            f"{human}",
            f"I'm planning to start {human}",
            f"For start term, {human}",
            f"I'd like to begin in {human}",
        ]
        return random.choice(templates), "start_term", val

    elif field_id == "enrollment_type":
        val = random.choice(["full_time", "part_time"])
        human_map = {
            "full_time": ["full-time", "full time", "I'll be going full-time", "fulltime"],
            "part_time": ["part-time", "part time", "I'll be going part-time", "parttime", "I'm doing this while working"],
        }
        human = random.choice(human_map[val])
        templates = [
            f"I'll be {human}",
            f"{human}",
            f"I want to enroll {human}",
            f"Enrollment: {human}",
            f"Going {human}",
        ]
        return random.choice(templates), "enrollment_type", val

    elif field_id == "prior_application":
        val = random.choice([True, False])
        msg = random.choice(BOOL_PRIOR_APP[val])
        if val and "{year}" in msg:
            msg = msg.replace("{year}", str(random.randint(2020, 2025)))
        return msg, "prior_application", str(val)

    elif field_id == "prior_application_year":
        year = random.randint(2020, 2025)
        templates = [
            f"I applied in {year}",
            f"It was {year}",
            f"Back in {year}",
            f"That was in {year}",
            f"{year}",
        ]
        return random.choice(templates), "prior_application_year", str(year)

    elif field_id == "gre_taken":
        val = random.choice([True, False])
        return random.choice(BOOL_GRE[val]), "gre_taken", str(val)

    elif field_id == "has_work_experience":
        val = random.choice([True, False])
        return random.choice(BOOL_WORK_EXP[val]), "has_work_experience", str(val)

    elif field_id == "funding_interest":
        val = random.choice([True, False])
        return random.choice(BOOL_FUNDING[val]), "funding_interest", str(val)

    elif field_id == "disability_accommodation":
        val = random.choice([True, False])
        return random.choice(BOOL_DISABILITY[val]), "disability_accommodation", str(val)

    elif field_id == "toefl_required":
        val = random.choice([True, False])
        return random.choice(BOOL_TOEFL[val]), "toefl_required", str(val)

    elif field_id == "english_test_type":
        val = random.choice(["toefl", "ielts"])
        human_map = {"toefl": ["TOEFL", "the TOEFL"], "ielts": ["IELTS", "the IELTS"]}
        human = random.choice(human_map[val])
        templates = [
            f"I took {human}",
            f"I have {human} scores",
            f"{human}",
            f"I went with {human}",
        ]
        return random.choice(templates), "english_test_type", val

    elif field_id == "english_test_score":
        test_type = random.choice(["toefl", "ielts"])
        score = random_english_score(test_type)
        templates = [
            f"My score was {score}",
            f"I got a {score}",
            f"Score: {score}",
            f"{score}",
            f"I scored {score}",
        ]
        return random.choice(templates), "english_test_score", str(score)

    elif field_id in ("gre_verbal", "gre_quant", "gre_writing"):
        section = field_id.split("_")[1]
        score = random_gre_score(section)
        section_label = {"verbal": "verbal", "quant": "quant", "writing": "writing"}[section]
        templates = [
            f"My GRE {section_label} score was {score}",
            f"Got a {score} on {section_label}",
            f"{section_label}: {score}",
            f"I scored {score} on the {section_label} section",
        ]
        return random.choice(templates), field_id, str(score)

    elif field_id == "gre_date":
        dt = random_date(2023, 2026)
        human = format_date_human(dt)
        iso = format_date_iso(dt)
        templates = [
            f"I took the GRE on {human}",
            f"GRE date was {human}",
            f"Took it on {human}",
            f"The test was on {human}",
        ]
        return random.choice(templates), "gre_date", iso

    elif field_id == "english_test_date":
        dt = random_date(2023, 2026)
        human = format_date_human(dt)
        iso = format_date_iso(dt)
        templates = [
            f"I took the test on {human}",
            f"Test date was {human}",
            f"I took it {human}",
        ]
        return random.choice(templates), "english_test_date", iso

    elif field_id == "how_heard":
        val = random.choice(list(HOW_HEARD_LABELS.keys()))
        human = random.choice(HOW_HEARD_LABELS[val])
        templates = [
            f"I heard about the program through {human}",
            f"Found out about it from {human}",
            f"Through {human}",
            f"I found Northfield via {human}",
            f"{human}",
            f"A {human} told me about it" if val == "referral" else f"Through {human}",
        ]
        return random.choice(templates), "how_heard", val

    elif field_id == "anything_else":
        texts = [
            "Nothing else to add",
            "That's everything!",
            "I think that covers it",
            "I'm a first-generation college student",
            "I have a service dog that will need accommodation",
            "I'd love to connect with the professor working on NLP research",
            "I plan to focus my research on renewable energy policy",
            "No, I think we're good!",
            "Just that I'm really excited about this program!",
            "I was a student athlete — captain of the debate team",
        ]
        text = random.choice(texts)
        return text, "anything_else", text

    elif field_id == "funding_type":
        options = ["teaching_assistantship", "research_assistantship", "fellowship", "scholarship"]
        labels = {
            "teaching_assistantship": ["TA", "teaching assistantship", "a TA position"],
            "research_assistantship": ["RA", "research assistantship", "a research position"],
            "fellowship": ["fellowship", "a fellowship"],
            "scholarship": ["scholarship", "a scholarship"],
        }
        selected = random.sample(options, k=random.randint(1, 3))
        human_parts = [random.choice(labels[s]) for s in selected]
        joined = " and ".join(human_parts) if len(human_parts) <= 2 else ", ".join(human_parts[:-1]) + f", and {human_parts[-1]}"
        templates = [
            f"I'm interested in {joined}",
            f"I'd like to apply for {joined}",
            f"{joined}",
            f"Hoping to get {joined}",
        ]
        return random.choice(templates), "funding_type", json.dumps(selected)

    # File fields — simulate file upload messages
    elif field_id in ("statement_of_purpose", "resume", "additional_docs"):
        file_names = {
            "statement_of_purpose": ["statement_of_purpose.pdf", "SOP.pdf", "personal_statement.pdf", "my_statement.pdf"],
            "resume": ["resume.pdf", "CV.pdf", "my_resume.pdf", f"{first}_{last}_resume.pdf"],
            "additional_docs": ["supplemental.pdf", "portfolio.pdf", "writing_sample.pdf", "certificates.pdf"],
        }
        fname = random.choice(file_names[field_id])
        templates = [
            f"[File: {fname}]\nHere's my {field_id.replace('_', ' ')}",
            f"Uploading {fname} now",
            f"[File: {fname}]\nHere you go!",
            f"[File: {fname}]",
        ]
        return random.choice(templates), field_id, fname

    return None


# ══════════════════════════════════════════════════════════════════════
# Multi-field message generators
# ══════════════════════════════════════════════════════════════════════

def gen_multi_field_groups():
    """Define natural multi-field groupings (fields users commonly provide together)."""
    return [
        # Personal info combos
        ["full_name", "email"],
        ["full_name", "dob"],
        ["full_name", "email", "phone"],
        ["email", "phone"],
        ["country_citizenship", "country_residence"],
        ["full_name", "dob", "gender"],
        ["full_name", "preferred_name"],
        ["phone", "mailing_address"],
        # Program combos
        ["program", "start_term"],
        ["program", "start_term", "enrollment_type"],
        ["enrollment_type", "start_term"],
        ["program", "enrollment_type"],
        # Test score combos
        ["gre_verbal", "gre_quant", "gre_writing"],
        ["gre_verbal", "gre_quant"],
        ["gre_taken", "gre_verbal", "gre_quant", "gre_writing"],
        ["english_test_type", "english_test_score"],
        ["english_test_type", "english_test_score", "english_test_date"],
        # Additional
        ["funding_interest", "funding_type"],
        ["disability_accommodation", "how_heard"],
        ["how_heard", "anything_else"],
    ]


MULTI_FIELD_CONNECTORS = [
    "{a}. Also, {b}",
    "{a}, and {b}",
    "{a}. Oh, and {b}",
    "{a}. {b}",
    "Sure! {a}. {b}",
    "Let me give you a few things: {a}. {b}",
    "Here's my info: {a}, and {b}",
    "OK so {a}. And {b}",
    "Yeah — {a}. Also {b}",
    "{a}. For the other question, {b}",
]

MULTI_FIELD_CONNECTORS_3 = [
    "{a}. {b}. {c}",
    "{a}, {b}, and {c}",
    "Here's everything: {a}. {b}. And {c}",
    "OK so {a}. Also, {b}. Oh and {c}",
    "Let me give you all of that: {a}. {b}. {c}",
    "Sure! {a}. {b}. {c}.",
]


def gen_multi_field_message(field_ids, person, form_state):
    """Generate a message providing multiple field values at once.
    Returns (user_message, [(field_id, field_value), ...]) or None.
    """
    parts = []
    extractions = []

    for fid in field_ids:
        result = gen_user_msg_single_field(fid, person, form_state)
        if result is None:
            continue
        msg, actual_fid, val = result
        parts.append(msg)
        extractions.append((actual_fid, val))

    if len(parts) < 2:
        return None

    # Combine with connector templates
    if len(parts) == 2:
        template = random.choice(MULTI_FIELD_CONNECTORS)
        combined = template.format(a=parts[0], b=parts[1])
    elif len(parts) == 3:
        template = random.choice(MULTI_FIELD_CONNECTORS_3)
        combined = template.format(a=parts[0], b=parts[1], c=parts[2])
    else:
        combined = ". ".join(parts)

    return combined, extractions


# ══════════════════════════════════════════════════════════════════════
# Group field messages (degrees, jobs, recommenders)
# ══════════════════════════════════════════════════════════════════════

def gen_degree_message(idx=0):
    """Generate a user message providing degree info."""
    inst = random.choice(INSTITUTIONS)
    deg_type = random.choice(["bachelor", "master", "doctorate", "associate"])
    field = random.choice(FIELDS_OF_STUDY)
    gpa = random_gpa()
    gpa_scale = random.choice(["4.0", "5.0"])
    start_year = random.randint(2010, 2022)
    end_year = start_year + random.randint(2, 6)

    deg_labels = {"bachelor": "Bachelor's", "master": "Master's", "doctorate": "PhD", "associate": "Associate's"}
    deg_human = deg_labels.get(deg_type, deg_type)

    templates = [
        f"I got my {deg_human} in {field} from {inst}. GPA was {gpa}/{gpa_scale}. {start_year} to {end_year}.",
        f"{inst}, {deg_human} in {field}, {gpa} GPA on a {gpa_scale} scale. Started {start_year}, finished {end_year}.",
        f"I studied {field} at {inst} — got my {deg_human} degree. GPA: {gpa}/{gpa_scale}. I was there from {start_year} to {end_year}.",
        f"My degree is from {inst}. {deg_human} in {field}. GPA {gpa} out of {gpa_scale}. Attended {start_year}-{end_year}.",
        f"Sure! I went to {inst} for my {deg_human}. Majored in {field}. {gpa}/{gpa_scale} GPA, {start_year} through {end_year}.",
    ]

    extractions = [
        (f"degrees.{idx}.institution", inst),
        (f"degrees.{idx}.degree_type", deg_type),
        (f"degrees.{idx}.field_of_study", field),
        (f"degrees.{idx}.gpa", str(gpa)),
        (f"degrees.{idx}.gpa_scale", gpa_scale),
        (f"degrees.{idx}.start_date", f"{start_year}-09"),
        (f"degrees.{idx}.end_date", f"{end_year}-05"),
    ]

    return random.choice(templates), extractions


def gen_job_message(idx=0):
    """Generate a user message providing job info."""
    employer = random.choice(EMPLOYERS)
    title = random.choice(JOB_TITLES)
    start_year = random.randint(2016, 2024)
    start_month = random.randint(1, 12)
    end_year = start_year + random.randint(0, 4)
    end_month = random.randint(1, 12)
    desc = random.choice([
        f"worked on {random.choice(['backend systems', 'data pipelines', 'ML models', 'frontend', 'research'])}",
        f"led {random.choice(['product development', 'analytics', 'a small team'])}",
        f"was responsible for {random.choice(['data analysis', 'software dev', 'operations'])}",
    ])

    templates = [
        f"I worked at {employer} as a {title} from {start_month}/{start_year} to {end_month}/{end_year}. I {desc}.",
        f"{title} at {employer}, {start_year}-{end_year}. Mainly {desc}.",
        f"My job was at {employer} — {title}. Started {start_month}/{start_year}, ended {end_month}/{end_year}. I {desc}.",
        f"I was a {title} at {employer} ({start_year} to {end_year}). {desc.capitalize()}.",
    ]

    extractions = [
        (f"jobs.{idx}.employer", employer),
        (f"jobs.{idx}.title", title),
        (f"jobs.{idx}.start_date", f"{start_year}-{start_month:02d}"),
        (f"jobs.{idx}.end_date", f"{end_year}-{end_month:02d}"),
        (f"jobs.{idx}.description", desc),
    ]

    return random.choice(templates), extractions


def gen_recommender_message(idx=0):
    """Generate a user message providing recommender info."""
    prefix = random.choice(["Prof.", "Dr.", ""])
    r_first, r_last = random_name()
    name = f"{prefix} {r_first} {r_last}".strip()
    email = random_email(r_first, r_last)
    rel = random.choice(["professor", "employer", "advisor", "mentor", "other"])
    inst = random.choice(INSTITUTIONS + EMPLOYERS[:10])

    rel_human = {
        "professor": "my professor", "employer": "my boss/employer",
        "advisor": "my academic advisor", "mentor": "my mentor", "other": "a reference",
    }[rel]

    templates = [
        f"One of my recommenders is {name} ({email}). They were {rel_human} at {inst}.",
        f"{name}, email {email}. They're {rel_human} from {inst}.",
        f"For a recommendation, you can contact {name} at {email}. {rel_human.capitalize()} at {inst}.",
        f"My recommender is {name} — {rel_human} at {inst}. Email: {email}.",
    ]

    extractions = [
        (f"recommenders.{idx}.name", name),
        (f"recommenders.{idx}.email", email),
        (f"recommenders.{idx}.relationship", rel),
        (f"recommenders.{idx}.institution", inst),
    ]

    return random.choice(templates), extractions


# ══════════════════════════════════════════════════════════════════════
# Conversation history generator
# ══════════════════════════════════════════════════════════════════════

ASSISTANT_GREETINGS = [
    "Welcome! I'm here to help you with your Northfield University graduate application. Let's get started!",
    "Hi there! Ready to work on your graduate application?",
    "Hello! Let's work through your Northfield application together.",
    "Welcome to the Northfield graduate application assistant. How can I help?",
]

ASSISTANT_FOLLOWUPS = [
    "Got it! What's next?",
    "Thanks! Moving on — {}",
    "Perfect, I've saved that. {}",
    "Great, noted! {}",
    "OK, that's saved. {}",
    "Thanks for that info. {}",
    "Awesome! {}",
]

SECTION_PROMPTS = {
    "personal": "Can you tell me your full name?",
    "program": "Which program are you interested in?",
    "academic": "Tell me about your educational background.",
    "tests": "Have you taken the GRE?",
    "work": "Do you have any work experience?",
    "docs": "Do you have your statement of purpose ready?",
    "recs": "Let's set up your recommendation letters. Who's your first recommender?",
    "additional": "A few more questions — are you interested in funding?",
}


def gen_conversation_history(form_state, n_turns=None):
    """Generate a plausible conversation history given a form state.
    Returns list of {"role": "user"/"assistant", "content": "..."} dicts.
    """
    if n_turns is None:
        n_turns = random.randint(0, 6)

    if n_turns == 0:
        return []

    history = []

    # Opening turn
    history.append({"role": "assistant", "content": random.choice(ASSISTANT_GREETINGS)})

    # Simulate a few turns of back-and-forth based on what's filled
    filled = set(form_state.keys())
    sections_done = []
    if any(f in filled for f in ["full_name", "email", "phone"]):
        sections_done.append("personal")
    if any(f in filled for f in ["program", "start_term"]):
        sections_done.append("program")
    if any(f.startswith("degrees") for f in filled):
        sections_done.append("academic")

    for i in range(min(n_turns - 1, len(sections_done))):
        section = sections_done[i]
        prompt = SECTION_PROMPTS.get(section, "What else can you tell me?")

        # User responds with something related
        user_msgs = [
            "Sure, let me give you that info.",
            "OK, here goes...",
            "Yep, happy to provide that.",
            "Let me fill that in for you.",
        ]
        history.append({"role": "user", "content": random.choice(user_msgs)})

        followup = random.choice(ASSISTANT_FOLLOWUPS)
        next_section = ([s for s in SECTION_PROMPTS if s not in sections_done] or ["anything_else"])
        next_prompt = SECTION_PROMPTS.get(next_section[0], "Anything else to add?")
        history.append({"role": "assistant", "content": followup.format(next_prompt)})

    # Trim to requested size (keep last n_turns * 2 messages)
    if len(history) > n_turns * 2:
        history = history[-(n_turns * 2):]

    return history


# ══════════════════════════════════════════════════════════════════════
# Build context string (matches DSPy format exactly)
# ══════════════════════════════════════════════════════════════════════

def build_context(form_state, conversation_history):
    """Build context string matching optimize_prompt.py format."""
    ctx = FORM_CONTEXT

    if form_state:
        ctx += f"\n\nFilled fields: {json.dumps(form_state)}"

    if conversation_history:
        recent = conversation_history[-6:]
        ctx += "\n\nRecent conversation:\n"
        ctx += "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content'][:300]}"
            for h in recent
        )

    return ctx


# ══════════════════════════════════════════════════════════════════════
# Main example generator
# ══════════════════════════════════════════════════════════════════════

# All single fields that can be independently generated
SINGLE_FIELDS = [
    "full_name", "preferred_name", "dob", "gender",
    "country_citizenship", "country_residence", "email", "phone", "mailing_address",
    "program", "start_term", "enrollment_type", "prior_application",
    "prior_application_year",
    "gre_taken", "gre_verbal", "gre_quant", "gre_writing", "gre_date",
    "toefl_required", "english_test_type", "english_test_score", "english_test_date",
    "has_work_experience",
    "funding_interest", "funding_type", "disability_accommodation",
    "how_heard", "anything_else",
    "statement_of_purpose", "resume", "additional_docs",
]


def generate_one_example():
    """Generate one GRPO training example.

    Returns dict with:
    - messages: [system_msg, user_msg] (DSPy ChatAdapter format)
    - ground_truth_ids: list of field_ids
    - ground_truth_values: list of field_values
    - example_type: "single" | "multi" | "degree" | "job" | "recommender"
    """
    form_state, person = generate_random_form_state()
    history = gen_conversation_history(form_state)

    # Decide example type with weighted distribution
    # Bias toward types the model struggles with
    example_type = random.choices(
        ["single", "multi", "degree", "job", "recommender"],
        weights=[0.30, 0.30, 0.15, 0.10, 0.15],
    )[0]

    if example_type == "single":
        # Pick a field that's NOT already filled
        unfilled = [f for f in SINGLE_FIELDS if f not in form_state]
        if not unfilled:
            unfilled = SINGLE_FIELDS  # fallback: allow duplicates
        field_id = random.choice(unfilled)
        result = gen_user_msg_single_field(field_id, person, form_state)
        if result is None:
            # Fallback to a safe field
            result = gen_user_msg_single_field("full_name", person, form_state)
        user_msg, fid, fval = result
        field_ids = [fid]
        field_values = [fval]

    elif example_type == "multi":
        groups = gen_multi_field_groups()
        # Filter to groups where at least 2 fields are unfilled
        viable = [g for g in groups if len([f for f in g if f not in form_state]) >= 2]
        if not viable:
            viable = groups  # allow all
        group = random.choice(viable)
        # Only include unfilled fields from the group (min 2)
        fields_to_use = [f for f in group if f not in form_state]
        if len(fields_to_use) < 2:
            fields_to_use = group  # use full group as fallback
        result = gen_multi_field_message(fields_to_use, person, form_state)
        if result is None:
            # Fallback: pick 2-3 random unfilled single fields
            unfilled = [f for f in SINGLE_FIELDS if f not in form_state]
            if len(unfilled) < 2:
                unfilled = SINGLE_FIELDS
            pick = random.sample(unfilled, min(random.randint(2, 3), len(unfilled)))
            result = gen_multi_field_message(pick, person, form_state)
            if result is None:
                # Last resort single
                r = gen_user_msg_single_field("email", person, form_state)
                user_msg, fid, fval = r
                field_ids = [fid]
                field_values = [fval]
            else:
                user_msg, extractions = result
                field_ids = [e[0] for e in extractions]
                field_values = [e[1] for e in extractions]
        else:
            user_msg, extractions = result
            field_ids = [e[0] for e in extractions]
            field_values = [e[1] for e in extractions]

    elif example_type == "degree":
        # Find next degree index
        existing = [k for k in form_state if k.startswith("degrees.")]
        idx = len(set(k.split(".")[1] for k in existing)) if existing else 0
        user_msg, extractions = gen_degree_message(idx)
        field_ids = [e[0] for e in extractions]
        field_values = [e[1] for e in extractions]

    elif example_type == "job":
        existing = [k for k in form_state if k.startswith("jobs.")]
        idx = len(set(k.split(".")[1] for k in existing)) if existing else 0
        user_msg, extractions = gen_job_message(idx)
        field_ids = [e[0] for e in extractions]
        field_values = [e[1] for e in extractions]

    elif example_type == "recommender":
        existing = [k for k in form_state if k.startswith("recommenders.")]
        idx = len(set(k.split(".")[1] for k in existing)) if existing else 0
        user_msg, extractions = gen_recommender_message(idx)
        field_ids = [e[0] for e in extractions]
        field_values = [e[1] for e in extractions]

    # Build DSPy-formatted prompt
    context = build_context(form_state, history)
    messages = adapter.format(
        signature=DataExtractorSignature,
        demos=[],
        inputs={"context": context, "user_message": user_msg},
    )

    return {
        "messages": messages,  # [system_msg, user_msg]
        "ground_truth_ids": field_ids,
        "ground_truth_values": field_values,
        "example_type": example_type,
        "user_message": user_msg,  # for debugging/inspection
    }


# ══════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Generate GRPO training data for DataExtractor")
    parser.add_argument("--count", type=int, default=3000, help="Number of examples to generate")
    parser.add_argument("--output", type=str, default=None, help="Output JSONL path")
    parser.add_argument("--stats", action="store_true", help="Show stats only, don't write")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--preview", type=int, default=0, help="Print N example prompts")
    args = parser.parse_args()

    random.seed(args.seed)

    output_path = args.output or str(Path(__file__).parent / "grpo_extractor_data.jsonl")

    examples = []
    for i in range(args.count):
        ex = generate_one_example()
        examples.append(ex)

    # Stats
    type_counts = Counter(ex["example_type"] for ex in examples)
    field_counts = Counter()
    n_fields_dist = Counter()
    for ex in examples:
        n_fields_dist[len(ex["ground_truth_ids"])] += 1
        for fid in ex["ground_truth_ids"]:
            # Normalize group fields: degrees.0.institution -> degrees.*.institution
            parts = fid.split(".")
            if len(parts) == 3 and parts[1].isdigit():
                fid = f"{parts[0]}.*.{parts[2]}"
            field_counts[fid] += 1

    print(f"Generated {len(examples)} examples")
    print(f"\nType distribution:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c} ({c/len(examples)*100:.1f}%)")

    print(f"\nFields per example:")
    for n, c in sorted(n_fields_dist.items()):
        print(f"  {n} fields: {c} ({c/len(examples)*100:.1f}%)")

    print(f"\nTop 20 field_ids:")
    for fid, c in field_counts.most_common(20):
        print(f"  {fid}: {c}")

    if args.preview > 0:
        print(f"\n{'='*60}")
        print(f"Preview of {args.preview} examples:")
        print(f"{'='*60}")
        for ex in random.sample(examples, min(args.preview, len(examples))):
            print(f"\n--- Type: {ex['example_type']} ---")
            print(f"User msg: {ex['user_message']}")
            print(f"Field IDs: {ex['ground_truth_ids']}")
            print(f"Field values: {ex['ground_truth_values']}")

    if args.stats:
        return

    # Write JSONL
    with open(output_path, "w") as f:
        for ex in examples:
            # For GRPO: prompt (messages without assistant) + ground truth
            row = {
                "prompt": ex["messages"],  # system + user messages
                "ground_truth_ids": ex["ground_truth_ids"],
                "ground_truth_values": ex["ground_truth_values"],
                "example_type": ex["example_type"],
            }
            f.write(json.dumps(row) + "\n")

    print(f"\nWrote {len(examples)} examples to {output_path}")


if __name__ == "__main__":
    main()
