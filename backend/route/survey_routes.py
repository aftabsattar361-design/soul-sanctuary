"""Survey listing, detail, submission and creation endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from auth import get_current_user, require_admin
from database import get_db
from model import (Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse, SurveySection, User)
from schemas import (MyResponseOut, SubmitIn, SubmitOut, SurveyCreate, SurveyDetail, SurveySummary)

router = APIRouter(prefix="/surveys", tags=["surveys"])
CHOICE_TYPES = {"single_choice", "dropdown", "rating"}
LIKERT = ["Strongly Disagree", "Disagree", "Neither Agree nor Disagree", "Agree", "Strongly Agree"]


def summaries(db: Session, where=None, limit: int | None = None, only_with_questions: bool = False) -> list[SurveySummary]:
    """Surveys with response and question counts, newest first."""
    resp = (select(SurveyResponse.survey_id, func.count().label("n")).group_by(SurveyResponse.survey_id).subquery())
    ques = (select(SurveyQuestion.survey_id, func.count().label("n")).group_by(SurveyQuestion.survey_id).subquery())
    stmt = (select(Survey, func.coalesce(resp.c.n, 0), func.coalesce(ques.c.n, 0))
            .outerjoin(resp, resp.c.survey_id == Survey.id).outerjoin(ques, ques.c.survey_id == Survey.id)
            .order_by(Survey.created_at.desc(), Survey.id.desc()))
    if where is not None:
        stmt = stmt.where(where)
    if only_with_questions:
        stmt = stmt.where(func.coalesce(ques.c.n, 0) > 0)
    if limit:
        stmt = stmt.limit(limit)
    return [SurveySummary(id=s.id, title=s.title, description=s.description, status=s.status, created_at=s.created_at,
                          response_count=r, question_count=q) for s, r, q in db.execute(stmt).all()]


@router.get("", response_model=list[SurveySummary])
def list_surveys(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SurveySummary]:
    """All surveys (for the Surveys page)."""
    return summaries(db)


@router.get("/active", response_model=list[SurveySummary])
def active_surveys(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SurveySummary]:
    """Active surveys that contain questions and can be taken."""
    return summaries(db, where=Survey.status == "active", only_with_questions=True)


@router.get("/my-response", response_model=MyResponseOut)
def my_response(survey_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MyResponseOut:
    """Whether the current user already submitted this survey."""
    r = db.scalar(select(SurveyResponse).where(SurveyResponse.user_id == user.id, SurveyResponse.survey_id == survey_id))
    if r is None:
        return MyResponseOut(submitted=False)
    return MyResponseOut(submitted=True, response_id=r.id, submitted_at=r.submitted_at)


@router.get("/{survey_id}", response_model=SurveyDetail)
def get_survey(survey_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> Survey:
    """Full survey with sections, questions and options."""
    survey = db.scalar(select(Survey).where(Survey.id == survey_id).options(
        selectinload(Survey.sections).selectinload(SurveySection.questions).selectinload(SurveyQuestion.options)))
    if survey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    return survey


@router.post("/submit", response_model=SubmitOut, status_code=status.HTTP_201_CREATED)
def submit(body: SubmitIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> SubmitOut:
    """Validate and store a user's answers (required questions enforced, one response per user)."""
    survey = db.get(Survey, body.survey_id)
    if survey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    if survey.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This survey is not accepting responses")
    if db.scalar(select(SurveyResponse.id).where(SurveyResponse.user_id == user.id,
                                                 SurveyResponse.survey_id == survey.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already submitted this survey")

    questions = {q.id: q for q in db.scalars(select(SurveyQuestion).where(SurveyQuestion.survey_id == survey.id)
                                              .options(selectinload(SurveyQuestion.options)))}
    seen: set[int] = set()
    rows: list[dict] = []
    for a in body.answers:
        q = questions.get(a.question_id)
        if q is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Question {a.question_id} is not in this survey")
        if a.question_id in seen:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Duplicate answer for Q{q.number}")
        valid = {o.id for o in q.options}
        if q.type in CHOICE_TYPES:
            if a.option_id is None:
                continue
            if a.option_id not in valid:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid option for Q{q.number}")
            rows.append(dict(question_id=q.id, option_id=a.option_id))
        elif q.type == "multi_choice":
            ids = list(dict.fromkeys(a.option_ids or []))
            if not ids:
                continue
            if any(i not in valid for i in ids):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid option for Q{q.number}")
            rows += [dict(question_id=q.id, option_id=i) for i in ids]
        elif q.type == "text":
            if not (a.text_value or "").strip():
                continue
            rows.append(dict(question_id=q.id, text_value=a.text_value.strip()))
        elif q.type == "number":
            if a.number_value is None:
                continue
            rows.append(dict(question_id=q.id, number_value=a.number_value))
        seen.add(q.id)
    missing = sorted(q.number for q in questions.values() if q.required and q.id not in seen)
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Please answer all required questions: " + ", ".join(f"Q{n}" for n in missing))

    response = SurveyResponse(user_id=user.id, survey_id=survey.id, is_complete=True,
                              submitted_at=datetime.now(timezone.utc))
    db.add(response)
    try:
        db.flush()
        db.add_all([SurveyAnswer(response_id=response.id, **r) for r in rows])
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You have already submitted this survey")
    return SubmitOut(response_id=response.id, submitted_at=response.submitted_at)


@router.post("", response_model=SurveyDetail, status_code=status.HTTP_201_CREATED)
def create_survey(body: SurveyCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)) -> Survey:
    """Create a survey with sections, questions and options (admin only)."""
    survey = Survey(title=body.title.strip(), description=body.description, status=body.status, created_by=admin.id,
                    activated_at=datetime.now(timezone.utc) if body.status == "active" else None)
    db.add(survey)
    db.flush()
    number = order = 0
    for s_idx, sec in enumerate(body.sections, start=1):
        section = SurveySection(survey_id=survey.id, title=sec.title.strip(), description=sec.description, order=s_idx)
        for qc in sec.questions:
            labels = [o.strip() for o in qc.options if o.strip()]
            if qc.type == "rating" and not labels:
                labels = LIKERT
            if qc.type in CHOICE_TYPES | {"multi_choice"} and len(labels) < 2:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                    f"Question '{qc.text[:40]}' needs at least two options")
            number += 1
            order += 1
            q = SurveyQuestion(survey_id=survey.id, number=number, text=qc.text.strip(), help_text=qc.help_text,
                               type=qc.type, required=qc.required, order=order)
            if qc.type in CHOICE_TYPES | {"multi_choice"}:
                q.options = [SurveyOption(label=lab, value=i, order=i) for i, lab in enumerate(labels, start=1)]
            section.questions.append(q)
        db.add(section)
    db.commit()
    return get_survey(survey.id, db, admin)
