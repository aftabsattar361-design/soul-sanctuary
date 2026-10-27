"""Idempotent seeding: survey (from the PDF), admin user, social rows and optional demo data.

Run manually:  python seed.py            (admin + survey + demo if SEED_DEMO_DATA=true)
               python seed.py --remove-demo   (delete all demo data)
"""
import logging
import math
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session

from auth import hash_password
from database import SessionLocal
from model import (Project, SocialStat, Survey, SurveyAnswer, SurveyOption, SurveyQuestion,
                   SurveyResponse, SurveySection, User)

logger = logging.getLogger("soul.seed")

# --------------------------------------------------------------------------------------
# SURVEY CONTENT: taken verbatim from Questionnaire PDF (wording, order, sections, options)
# --------------------------------------------------------------------------------------
SURVEY_TITLE = "Art of Living Participation and Community Well-Being: A Quantitative Sociological Study in Pakistan"
SURVEY_DESCRIPTION = ("Please select one answer for each question unless otherwise stated. There are no right or wrong "
                      "answers. Your responses will be used only for academic research.")
FREQ = ["Never", "Rarely", "Sometimes", "Often", "Very often"]
LIKERT = ["Strongly Disagree", "Disagree", "Neither Agree nor Disagree", "Agree", "Strongly Agree"]
EXAMPLES = ("Examples of activities: meditation, breathing practices, yoga, workshops/courses, group activities, "
            "and service/community activities.")

SURVEY_SECTIONS = [
    {
        "title": "Section A: Art of Living Participation",
        "description": ("Purpose: These questions measure the respondent's level and pattern of participation in "
                        "Art of Living activities."),
        "type": "single_choice",
        "questions": [
            (1, "How frequently do you attend Art of Living sessions or programs?",
             ["Never", "Rarely", "1–2 times per month", "1–2 times per week", "3 or more times per week"], None),
            (2, "How frequently do you participate in Art of Living meditation practices?", FREQ, None),
            (3, "How frequently do you practice Art of Living breathing techniques?", FREQ, None),
            (4, "How frequently do you participate in Art of Living yoga or physical practice sessions?", FREQ, None),
            (5, "How frequently do you attend Art of Living workshops, courses, or training programs?", FREQ, None),
            (6, "How frequently do you participate in group activities organized by Art of Living?", FREQ, None),
            (7, "How frequently do you participate in Art of Living community or service activities?", FREQ, None),
            (8, "For how long have you been participating in Art of Living activities?",
             ["Less than 6 months", "6 months to 1 year", "More than 1 year to 3 years",
              "More than 3 years to 5 years", "More than 5 years"], None),
            (9, "How regularly do you continue participating in Art of Living activities after completing a course or program?",
             FREQ, None),
            (10, "In how many different types of Art of Living activities have you participated?",
             ["1 type", "2 types", "3 types", "4 types", "5 or more types"], EXAMPLES),
        ],
    },
    {
        "title": "Section B: Community Well-Being",
        "description": ("Purpose: These questions measure the respondent's perceived community well-being, including "
                        "belonging, social connectedness, relationships, trust, mutual support, cooperation, and "
                        "satisfaction. For Questions 11–25, select one answer."),
        "type": "rating",
        "questions": [
            (11, "I feel that I belong to the community in which I live.", LIKERT, None),
            (12, "I feel socially connected to people in my community.", LIKERT, None),
            (13, "I have positive and meaningful relationships with people in my community.", LIKERT, None),
            (14, "I feel comfortable interacting with people from different backgrounds in my community.", LIKERT, None),
            (15, "I can rely on people in my community when I need social support.", LIKERT, None),
            (16, "I believe that people in my community generally trust one another.", LIKERT, None),
            (17, "People in my community are willing to help one another when needed.", LIKERT, None),
            (18, "People in my community cooperate to address common problems.", LIKERT, None),
            (19, "I am willing to work with other people to improve my community.", LIKERT, None),
            (20, "I participate in activities that contribute positively to my community.", LIKERT, None),
            (21, "I feel that my contribution to the community is valued by others.", LIKERT, None),
            (22, "I feel a sense of responsibility toward other members of my community.", LIKERT, None),
            (23, "People in my community respect and support one another.", LIKERT, None),
            (24, "I am satisfied with my social and community life.", LIKERT, None),
            (25, "Overall, I believe that my community provides a positive environment for social well-being.", LIKERT, None),
        ],
    },
]

# --------------------------------------------------------------------------------------
# DEMO DATA TARGETS (match the dashboard screenshot)
# --------------------------------------------------------------------------------------
TOTAL_USERS = 12_847
MONTHLY_NEW_USERS = [400, 1000, 700, 800, 1450, 950, 1500, 1700, 1500, 1900, 1900, 1900]
AGE_SPLIT = [("18-24", 28), ("25-34", 42), ("35-44", 20), ("45+", 10)]
TOTAL_COMPLETED = 3_209
TOTAL_ENTRIES = 89_432
SURVEY_PERIOD_WEIGHTS = [37, 61, 45, 66, 45, 36]
ACTIVE_SURVEYS_TARGET = 24
DEMO_PASSWORD = "DemoPass123"

NAMED_SURVEYS = [  # title, status, responses, days ago created
    ("Customer Feedback Q4", "completed", 156, 3),
    ("Product Experience Survey", "active", 89, 5),
    ("Employee Satisfaction Survey", "completed", 203, 9),
    ("Market Research Survey", "draft", 42, 11),
]
NAMED_PROJECTS = [  # name, entries, days ago updated, owner, status
    ("Clinical Trial Dataset", 12_340, 1, "Dr. Sarah Kim", "processed"),
    ("Environmental Survey Data", 8_932, 2, "James Lee", "active"),
    ("Consumer Behavior Study", 5_421, 4, "Maria Gonzalez", "processed"),
    ("Public Health Survey", 4_102, 7, "Alex Chen", "pending_review"),
]
OTHER_PROJECTS = ["Urban Mobility Panel", "Nutrition Intake Log", "Education Outcomes Tracker", "Water Quality Readings",
                  "Community Wellness Index", "Climate Perception Poll", "Hospital Wait-Time Audit", "Youth Skills Census",
                  "Rural Livelihood Survey", "Mental Health Screening Data", "Air Quality Sensors", "Household Energy Use",
                  "Vaccination Coverage Records", "Sleep Habits Study", "Volunteer Engagement Data", "Public Transit Feedback"]
OTHER_OWNERS = ["Ayesha Khan", "Omar Farooq", "Hina Malik", "Bilal Ahmed", "Sana Riaz", "Usman Tariq"]
OTHER_TOPICS = ["Community Pulse", "Wellness Check-in", "Volunteer Feedback", "Event Satisfaction", "Learning Needs",
                "Neighbourhood Safety", "Digital Access", "Health Habits", "Workplace Culture", "Public Services",
                "Local Business", "Youth Voices", "Family Support", "Mobility & Transport", "Green Spaces", "Food Security",
                "Cultural Activities", "Mentoring Programs", "Housing Needs", "Newsletter Readers", "Training Review",
                "Service Quality"]
FIRST = ["Ali", "Fatima", "Hassan", "Zainab", "Ahmed", "Ayesha", "Bilal", "Maryam", "Usman", "Hira", "Omar", "Sana",
         "Hamza", "Noor", "Imran", "Amna", "Faisal", "Iqra", "Saad", "Laiba"]
LAST = ["Khan", "Ahmed", "Malik", "Sheikh", "Raza", "Siddiqui", "Hussain", "Qureshi", "Butt", "Mirza", "Iqbal", "Ansari"]
CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Faisalabad", "Multan", "Peshawar", "Quetta", "Hyderabad", "Sialkot"]
GENDERS = ["Male", "Female", "Other", "Prefer not to say"]


def survey_counts() -> tuple[int, int]:
    """Return (sections, questions) defined in SURVEY_SECTIONS."""
    return len(SURVEY_SECTIONS), sum(len(s["questions"]) for s in SURVEY_SECTIONS)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def seed_admin(db: Session) -> None:
    """Create the admin user from ADMIN_EMAIL / ADMIN_PASSWORD if missing."""
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    if not email or not password:
        raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set before the API can start.")
    if len(password.encode()) > 72:
        raise RuntimeError("ADMIN_PASSWORD must be no more than 72 bytes for bcrypt.")
    if db.scalar(select(User).where(User.email == email)):
        return
    db.add(User(name="Alex Morgan", email=email, password_hash=hash_password(password), role="admin",
                age=35, gender="Other", city="Karachi"))
    db.commit()
    logger.info("Seeded admin user %s", email)
    print(f"Seeded admin user: {email}", flush=True)


def seed_survey(db: Session) -> Survey:
    """Insert the questionnaire from the PDF once. Prints section/question counts."""
    survey = db.scalar(select(Survey).where(Survey.title == SURVEY_TITLE))
    if survey is None:
        admin = db.scalar(select(User).where(User.role == "admin"))
        survey = Survey(title=SURVEY_TITLE, description=SURVEY_DESCRIPTION, status="active",
                        created_by=admin.id if admin else None, activated_at=_now())
        db.add(survey)
        db.flush()  # survey.id is needed by sections and questions
        order = 0
        for s_idx, sec in enumerate(SURVEY_SECTIONS, start=1):
            section = SurveySection(survey_id=survey.id, title=sec["title"], description=sec["description"], order=s_idx)
            for number, text, options, help_text in sec["questions"]:
                order += 1
                q = SurveyQuestion(survey_id=survey.id, number=number, text=text, help_text=help_text,
                                   type=sec["type"], required=True, order=order)
                q.options = [SurveyOption(label=lab, value=i, order=i) for i, lab in enumerate(options, start=1)]
                section.questions.append(q)
            db.add(section)
        db.commit()
        print("Seeded survey from PDF.", flush=True)
    n_sec = db.scalar(select(func.count()).select_from(SurveySection).where(SurveySection.survey_id == survey.id))
    n_q = db.scalar(select(func.count()).select_from(SurveyQuestion).where(SurveyQuestion.survey_id == survey.id))
    msg = f"Survey in DB: {n_sec} sections, {n_q} questions (PDF: {survey_counts()[0]} sections, {survey_counts()[1]} questions)"
    logger.info(msg)
    print(msg, flush=True)
    return survey


def seed_social(db: Session) -> None:
    """Ensure one social_stats row per platform exists."""
    for platform in ("instagram", "facebook"):
        if not db.scalar(select(SocialStat).where(SocialStat.platform == platform)):
            db.add(SocialStat(platform=platform))
    db.commit()


# --------------------------------------------------------------------------------------
# DEMO DATA
# --------------------------------------------------------------------------------------
def _chunks(rows: list, size: int = 2000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def _rand_dt(rng: random.Random, start: datetime, end: datetime) -> datetime:
    span = max(int((end - start).total_seconds()), 1)
    return start + timedelta(seconds=rng.randint(0, span))


def _demo_users(db: Session, rng: random.Random, now: datetime) -> list[int]:
    existing = db.scalar(select(func.count()).select_from(User)) or 0
    n_demo = max(TOTAL_USERS - existing, 0)
    month = now.month
    shape = MONTHLY_NEW_USERS[:month]
    in_year = min(sum(shape), n_demo)
    prior = n_demo - in_year
    # creation timestamps
    stamps: list[datetime] = []
    for m, count in enumerate(shape, start=1):
        start = datetime(now.year, m, 1, tzinfo=timezone.utc)
        end = min(datetime(now.year + (m == 12), (m % 12) + 1, 1, tzinfo=timezone.utc) - timedelta(seconds=1), now)
        stamps += [_rand_dt(rng, start, end) for _ in range(count)]
    stamps = stamps[:in_year]
    stamps += [datetime(now.year - 1, rng.randint(1, 12), rng.randint(1, 28), tzinfo=timezone.utc) for _ in range(prior)]
    # age groups
    buckets: list[str] = []
    for name, pct in AGE_SPLIT:
        buckets += [name] * round(n_demo * pct / 100)
    buckets = (buckets + ["25-34"] * n_demo)[:n_demo]
    rng.shuffle(buckets)
    ranges = {"18-24": (18, 24), "25-34": (25, 34), "35-44": (35, 44), "45+": (45, 70)}
    pw_hash = hash_password(DEMO_PASSWORD)  # ONE hash shared by all demo users
    rows = []
    for i in range(n_demo):
        age = rng.randint(*ranges[buckets[i]])
        rows.append(dict(name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", email=f"demo{i + 1}@demo.local",
                         password_hash=pw_hash, role="user", age=age,
                         date_of_birth=date(now.year - age, rng.randint(1, 12), rng.randint(1, 28)),
                         gender=rng.choice(GENDERS), city=rng.choice(CITIES), is_demo=True, created_at=stamps[i]))
    for chunk in _chunks(rows):
        db.execute(insert(User), chunk)
    db.commit()
    return list(db.scalars(select(User.id).where(User.is_demo.is_(True)).order_by(User.id)).all())


def _unique_users(user_ids: list[int], count: int, offset: int) -> list[int]:
    """Pick `count` distinct user ids, deterministic and spread out."""
    n = len(user_ids)
    step = 7
    while math.gcd(step, n) != 1:
        step += 2
    count = min(count, n)
    return [user_ids[(offset + j * step) % n] for j in range(count)]


def _insert_responses(db: Session, survey_id: int, users: list[int], times: list[datetime]) -> None:
    rows = [dict(user_id=u, survey_id=survey_id, submitted_at=t, is_complete=True) for u, t in zip(users, times)]
    for chunk in _chunks(rows):
        db.execute(insert(SurveyResponse), chunk)


def _demo_surveys_and_responses(db: Session, rng: random.Random, now: datetime, user_ids: list[int],
                                primary: Survey) -> None:
    admin = db.scalar(select(User).where(User.role == "admin"))
    admin_id = admin.id if admin else None
    # push the PDF survey back in time so the 4 named surveys are the latest rows in the table
    old = now - timedelta(days=60)
    db.execute(update(Survey).where(Survey.id == primary.id).values(created_at=old, activated_at=old))

    offset = 0
    named_ids = []
    for title, status, count, days in NAMED_SURVEYS:
        created = now - timedelta(days=days)
        s = Survey(title=title, description="Demo survey", status=status, created_by=admin_id, is_demo=True,
                   created_at=created, activated_at=created if status == "active" else None)
        db.add(s)
        db.flush()
        named_ids.append((s.id, count, created))
    # 22 other active surveys (Product Experience Survey + PDF survey make it 24); 2 of them are "new" (<30 days)
    n_other = ACTIVE_SURVEYS_TARGET - 2
    other_ids = []
    for i in range(n_other):
        days = 15 + i * 7 if i < 2 else 40 + (i - 2) * 9
        created = now - timedelta(days=days)
        s = Survey(title=f"{OTHER_TOPICS[i % len(OTHER_TOPICS)]} Survey", description="Demo survey", status="active",
                   created_by=admin_id, is_demo=True, created_at=created, activated_at=created)
        db.add(s)
        db.flush()
        other_ids.append((s.id, created))
    db.commit()

    for sid, count, created in named_ids:
        users = _unique_users(user_ids, count, offset)
        offset += 1013
        end = min(created + timedelta(days=3), now)
        _insert_responses(db, sid, users, [_rand_dt(rng, created, end) for _ in users])

    primary_total = sum(SURVEY_PERIOD_WEIGHTS)
    named_total = sum(c for _, c, _ in named_ids)
    remaining = max(TOTAL_COMPLETED - named_total - primary_total, 0)
    base, extra = divmod(remaining, len(other_ids))
    for i, (sid, created) in enumerate(other_ids):
        count = base + (1 if i < extra else 0)
        users = _unique_users(user_ids, count, offset)
        offset += 1013
        _insert_responses(db, sid, users, [_rand_dt(rng, created, now) for _ in users])
    db.commit()

    # --- the PDF survey: 6 equal periods Jan 1 -> now, with real answers ---
    year_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    width = (now - year_start) / 6
    users_all = _unique_users(user_ids, primary_total, offset)
    times: list[datetime] = []
    for p, weight in enumerate(SURVEY_PERIOD_WEIGHTS):
        lo = year_start + width * p
        hi = year_start + width * (p + 1) - timedelta(seconds=1)
        times += [_rand_dt(rng, lo, hi) for _ in range(weight)]
    _insert_responses(db, primary.id, users_all, times)
    db.commit()
    _demo_answers(db, rng, primary.id)


def _demo_answers(db: Session, rng: random.Random, survey_id: int) -> None:
    """Correlated demo answers: more participation -> higher community well-being."""
    questions = db.scalars(select(SurveyQuestion).where(SurveyQuestion.survey_id == survey_id)
                           .order_by(SurveyQuestion.order)).all()
    opt_ids = {q.id: [o.id for o in sorted(q.options, key=lambda o: o.order)] for q in questions}
    section_type = {q.id: q.type for q in questions}
    responses = db.execute(select(SurveyResponse.id).where(SurveyResponse.survey_id == survey_id)
                           .join(User, User.id == SurveyResponse.user_id).where(User.is_demo.is_(True))).all()
    rows = []
    clamp = lambda v: max(0, min(4, int(round(v))))
    for (rid,) in responses:
        p = rng.betavariate(2, 2)
        for q in questions:
            if section_type[q.id] == "single_choice":
                idx = clamp(p * 4 + rng.gauss(0, 0.8))
            else:
                idx = clamp((0.3 + 0.5 * p) * 4 + rng.gauss(0, 0.8))
            rows.append(dict(response_id=rid, question_id=q.id, option_id=opt_ids[q.id][idx]))
    for chunk in _chunks(rows, 5000):
        db.execute(insert(SurveyAnswer), chunk)
    db.commit()


def _demo_projects(db: Session, rng: random.Random, now: datetime) -> None:
    existing_entries = db.scalar(select(func.coalesce(func.sum(Project.entries_count), 0))) or 0
    named_total = sum(p[1] for p in NAMED_PROJECTS)
    remainder = max(TOTAL_ENTRIES - existing_entries - named_total, 0)
    weights = [rng.uniform(0.5, 1.5) for _ in OTHER_PROJECTS]
    sizes = [int(remainder * w / sum(weights)) for w in weights]
    sizes[-1] += remainder - sum(sizes)
    statuses = ["processed", "active", "active", "pending_review"]
    rows = []
    for name, entries, days, owner, status in NAMED_PROJECTS:
        updated = now - timedelta(days=days, hours=rng.randint(0, 5))
        rows.append(Project(name=name, entries_count=entries, last_updated=updated, owner_name=owner, status=status,
                            is_demo=True, created_at=updated - timedelta(days=rng.randint(5, 120))))
    for i, name in enumerate(OTHER_PROJECTS):
        updated = now - timedelta(days=rng.randint(9, 150))
        rows.append(Project(name=name, entries_count=sizes[i], last_updated=updated, owner_name=rng.choice(OTHER_OWNERS),
                            status=rng.choice(statuses), is_demo=True,
                            created_at=max(updated - timedelta(days=rng.randint(0, 90)), now - timedelta(days=300))))
    db.add_all(rows)
    db.commit()


def _demo_social(db: Session) -> None:
    values = {
        "instagram": dict(likes=28_400, shares=1_400, comments=3_200, followers=45_600,
                          likes_delta=1_200, shares_delta=210, comments_delta=340, followers_delta=890),
        "facebook": dict(likes=18_300, shares=0, comments=0, followers=0,
                         likes_delta=980, shares_delta=0, comments_delta=0, followers_delta=0),
    }
    for platform, vals in values.items():
        row = db.scalar(select(SocialStat).where(SocialStat.platform == platform))
        if row is None:
            row = SocialStat(platform=platform)
            db.add(row)
        for k, v in vals.items():
            setattr(row, k, v)
        row.updated_at = _now()
    db.commit()


def seed_demo(db: Session, primary: Survey) -> None:
    """Bulk-create demo users, surveys, responses, projects and social stats (idempotent)."""
    if db.scalar(select(func.count()).select_from(User).where(User.is_demo.is_(True))):
        print("Demo data already present; skipping.", flush=True)
        return
    print("Seeding demo data (this takes a few seconds)...", flush=True)
    rng = random.Random(42)
    now = _now()
    user_ids = _demo_users(db, rng, now)
    _demo_surveys_and_responses(db, rng, now, user_ids, primary)
    _demo_projects(db, rng, now)
    _demo_social(db)
    print(f"Demo data ready: {len(user_ids)} demo users (@demo.local).", flush=True)


def remove_demo(db: Session) -> None:
    """Delete every demo row (users @demo.local, demo surveys/projects and their responses)."""
    demo_users = select(User.id).where(User.is_demo.is_(True))
    demo_surveys = select(Survey.id).where(Survey.is_demo.is_(True))
    resp_ids = select(SurveyResponse.id).where(
        SurveyResponse.user_id.in_(demo_users) | SurveyResponse.survey_id.in_(demo_surveys))
    db.execute(delete(SurveyAnswer).where(SurveyAnswer.response_id.in_(resp_ids)))
    db.execute(delete(SurveyResponse).where(
        SurveyResponse.user_id.in_(demo_users) | SurveyResponse.survey_id.in_(demo_surveys)))
    db.execute(delete(Survey).where(Survey.is_demo.is_(True)))
    db.execute(delete(Project).where(Project.is_demo.is_(True)))
    db.execute(delete(User).where(User.is_demo.is_(True)))
    db.commit()
    print("Demo data removed.", flush=True)


def run_seed() -> None:
    """Seed admin, survey, social rows and (optionally) demo data."""
    with SessionLocal() as db:
        seed_admin(db)
        primary = seed_survey(db)
        seed_social(db)
        if os.getenv("SEED_DEMO_DATA", "false").strip().lower() in ("1", "true", "yes"):
            seed_demo(db, primary)


if __name__ == "__main__":
    from database import Base, check_connection, engine
    import model  # noqa: F401
    check_connection()
    Base.metadata.create_all(engine)
    if "--remove-demo" in sys.argv:
        with SessionLocal() as session:
            remove_demo(session)
    else:
        run_seed()
