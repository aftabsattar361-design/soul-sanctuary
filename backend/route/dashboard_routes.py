"""Dashboard endpoints: everything is computed from the database (no constants)."""
import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import get_db
from model import (Project, SocialStat, Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse, User)
from route.survey_routes import summaries

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
AGE_GROUPS = [("18-24", 18, 24), ("25-34", 25, 34), ("35-44", 35, 44), ("45+", 45, 200)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev = (this - timedelta(days=1)).replace(day=1)
    return prev, this


def _pct(cur: float, prev: float) -> float | None:
    if not prev:
        return None
    return round((cur - prev) / prev * 100, 1)


def _kpi(value: int, cur: float, prev: float) -> dict:
    return {"value": int(value), "delta_pct": _pct(cur, prev), "delta_text": None}


def _count_between(db: Session, col, start: datetime, end: datetime, *extra) -> int:
    return db.scalar(select(func.count()).select_from(col.class_).where(col >= start, col < end, *extra)) or 0


def build_summary(db: Session) -> dict:
    """The four KPI cards plus the 'updated at' timestamp."""
    now = _now()
    prev, this = _month_bounds(now)
    users_total = db.scalar(select(func.count()).select_from(User)) or 0
    done_total = db.scalar(select(func.count()).select_from(SurveyResponse).where(SurveyResponse.is_complete.is_(True))) or 0
    active = db.scalar(select(func.count()).select_from(Survey).where(Survey.status == "active")) or 0
    new_active = db.scalar(select(func.count()).select_from(Survey).where(
        Survey.status == "active", Survey.activated_at >= now - timedelta(days=30))) or 0
    entries = db.scalar(select(func.coalesce(func.sum(Project.entries_count), 0))) or 0

    def entries_between(a: datetime, b: datetime) -> int:
        return db.scalar(select(func.coalesce(func.sum(Project.entries_count), 0)).where(
            Project.created_at >= a, Project.created_at < b)) or 0

    return {
        "updated_at": now,
        "registrations": _kpi(users_total, _count_between(db, User.created_at, this, now + timedelta(days=1)),
                              _count_between(db, User.created_at, prev, this)),
        "completed_surveys": _kpi(done_total, _count_between(db, SurveyResponse.submitted_at, this, now + timedelta(days=1),
                                                             SurveyResponse.is_complete.is_(True)),
                                  _count_between(db, SurveyResponse.submitted_at, prev, this,
                                                 SurveyResponse.is_complete.is_(True))),
        "active_surveys": {"value": int(active), "delta_pct": None, "delta_text": f"{new_active} new"},
        "data_entries": _kpi(entries, entries_between(this, now + timedelta(days=1)), entries_between(prev, this)),
    }


def primary_survey_id(db: Session) -> int | None:
    """Survey shown in the 'Survey Responses' chart: the first survey that has questions."""
    return db.scalar(select(SurveyQuestion.survey_id).group_by(SurveyQuestion.survey_id)
                     .order_by(SurveyQuestion.survey_id).limit(1))


def build_survey_responses(db: Session, survey_id: int | None = None) -> dict:
    """Responses to the main questionnaire in 6 equal periods (Q1..Q6) from Jan 1 to now."""
    now = _now()
    sid = survey_id or primary_survey_id(db)
    start = datetime(now.year, 1, 1, tzinfo=timezone.utc)
    width = (now - start) / 6
    values = []
    for i in range(6):
        lo, hi = start + width * i, (start + width * (i + 1)) if i < 5 else now + timedelta(seconds=1)
        n = 0
        if sid:
            n = db.scalar(select(func.count()).select_from(SurveyResponse).where(
                SurveyResponse.survey_id == sid, SurveyResponse.submitted_at >= lo, SurveyResponse.submitted_at < hi)) or 0
        values.append(int(n))
    return {"labels": [f"Q{i}" for i in range(1, 7)], "values": values, "total": sum(values)}


def build_registration_growth(db: Session) -> dict:
    """New registrations per month, January to the current month."""
    now = _now()
    rows = db.execute(select(extract("month", User.created_at).label("m"), func.count())
                      .where(extract("year", User.created_at) == now.year).group_by("m")).all()
    by_month = {int(m): n for m, n in rows}
    months = MONTHS[:now.month]
    values = [int(by_month.get(i, 0)) for i in range(1, now.month + 1)]
    return {"months": months, "values": values, "ytd_total": sum(values)}


def build_demographics(db: Session) -> dict:
    """Users by age group with integer percentages that add up to 100."""
    counts = []
    for name, lo, hi in AGE_GROUPS:
        n = db.scalar(select(func.count()).select_from(User).where(User.age.is_not(None), User.age >= lo,
                                                                     User.age <= hi)) or 0
        counts.append((name, n))
    total = sum(n for _, n in counts)
    pcts = [0] * len(counts)
    if total:
        raw = [n * 100 / total for _, n in counts]
        pcts = [int(r) for r in raw]
        for i in sorted(range(len(raw)), key=lambda k: raw[k] - pcts[k], reverse=True)[:100 - sum(pcts)]:
            pcts[i] += 1
    return {"total": total, "groups": [{"label": n, "count": c, "percent": p} for (n, c), p in zip(counts, pcts)]}


def _social_dict(row: SocialStat | None, platform: str) -> dict:
    keys = ["likes", "shares", "comments", "followers"]
    out = {"platform": platform, "updated_at": row.updated_at if row else None}
    for k in keys:
        out[k] = getattr(row, k) if row else 0
        out[f"{k}_delta"] = getattr(row, f"{k}_delta") if row else 0
    return out


def build_social(db: Session) -> dict:
    """Instagram and Facebook stats from the social_stats table."""
    rows = {r.platform: r for r in db.scalars(select(SocialStat))}
    return {"instagram": _social_dict(rows.get("instagram"), "instagram"),
            "facebook": _social_dict(rows.get("facebook"), "facebook")}


def build_surveys_table(db: Session) -> list[dict]:
    """Latest 4 surveys."""
    return [{"title": s.title, "responses": s.response_count, "status": s.status, "date": s.created_at,
             "action": "Edit" if s.status == "draft" else "View"} for s in summaries(db, limit=4)]


def build_projects_table(db: Session) -> list[dict]:
    """Latest 4 projects by last_updated."""
    rows = db.scalars(select(Project).order_by(Project.last_updated.desc(), Project.id.desc()).limit(4)).all()
    return [{"name": p.name, "entries": p.entries_count, "last_updated": p.last_updated, "owner": p.owner_name,
             "status": p.status} for p in rows]


@router.get("/summary")
def summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """KPI cards."""
    return build_summary(db)


@router.get("/survey-responses")
def survey_responses(survey_id: int | None = None, db: Session = Depends(get_db),
                     _: User = Depends(get_current_user)) -> dict:
    """Survey responses chart data."""
    return build_survey_responses(db, survey_id)


@router.get("/registration-growth")
def registration_growth(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Registration growth chart data."""
    return build_registration_growth(db)


@router.get("/demographics")
def demographics(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Age-group split."""
    return build_demographics(db)


@router.get("/social")
def social(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Instagram and Facebook numbers."""
    return build_social(db)


@router.get("/surveys-table")
def surveys_table(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    """Latest 4 surveys."""
    return build_surveys_table(db)


@router.get("/projects-table")
def projects_table(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[dict]:
    """Latest 4 projects."""
    return build_projects_table(db)


@router.get("/overview")
def overview(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Everything the dashboard needs in one call."""
    return {"summary": build_summary(db), "survey_responses": build_survey_responses(db),
            "registration_growth": build_registration_growth(db), "demographics": build_demographics(db),
            "social": build_social(db), "surveys_table": build_surveys_table(db),
            "projects_table": build_projects_table(db)}


@router.get("/export")
def export_report(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Response:
    """CSV report with all KPIs and tables (admin only)."""
    data = overview(db, None)  # type: ignore[arg-type]
    buf = io.StringIO()
    w = csv.writer(buf)
    s = data["summary"]
    w.writerow(["Soul Sanctuary - Dashboard report"])
    w.writerow(["Generated at (UTC)", s["updated_at"].strftime("%Y-%m-%d %H:%M")])
    w.writerow([])
    w.writerow(["KPI", "Value", "Change"])
    for label, key in [("Total Registrations / Sign-ups", "registrations"), ("Completed Surveys", "completed_surveys"),
                       ("Active Surveys", "active_surveys"), ("Data Entries", "data_entries")]:
        k = s[key]
        change = k["delta_text"] or (f"{k['delta_pct']:+.1f}% vs last month" if k["delta_pct"] is not None else "n/a")
        w.writerow([label, k["value"], change])
    w.writerow([])
    w.writerow(["Survey responses by period", "Responses"])
    sr = data["survey_responses"]
    w.writerows(zip(sr["labels"], sr["values"]))
    w.writerow(["Total", sr["total"]])
    w.writerow([])
    w.writerow(["Registrations by month", "New users"])
    rg = data["registration_growth"]
    w.writerows(zip(rg["months"], rg["values"]))
    w.writerow(["YTD total", rg["ytd_total"]])
    w.writerow([])
    w.writerow(["Age group", "Users", "Percent"])
    for g in data["demographics"]["groups"]:
        w.writerow([g["label"], g["count"], g["percent"]])
    w.writerow([])
    w.writerow(["Platform", "Likes", "Shares", "Comments", "Followers", "Likes change", "Shares change",
                "Comments change", "Followers change"])
    for p in ("instagram", "facebook"):
        x = data["social"][p]
        w.writerow([p.title(), x["likes"], x["shares"], x["comments"], x["followers"], x["likes_delta"],
                    x["shares_delta"], x["comments_delta"], x["followers_delta"]])
    w.writerow([])
    w.writerow(["Survey", "Responses", "Status", "Date"])
    for r in data["surveys_table"]:
        w.writerow([r["title"], r["responses"], r["status"], r["date"].strftime("%b %d, %Y")])
    w.writerow([])
    w.writerow(["Project", "Data entries", "Last updated", "Owner", "Status"])
    for r in data["projects_table"]:
        w.writerow([r["name"], r["entries"], r["last_updated"].strftime("%b %d, %Y"), r["owner"], r["status"]])
    name = f"soul-sanctuary-report-{_now():%Y%m%d}.csv"
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/question-stats")
def question_stats(survey_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Per-question answer counts (for the Analytics page) from real answers."""
    survey = db.get(Survey, survey_id)
    if survey is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Survey not found")
    total = db.scalar(select(func.count()).select_from(SurveyResponse).where(
        SurveyResponse.survey_id == survey_id, SurveyResponse.is_complete.is_(True))) or 0
    counts = {(q, o): n for q, o, n in db.execute(
        select(SurveyAnswer.question_id, SurveyAnswer.option_id, func.count())
        .join(SurveyResponse, SurveyResponse.id == SurveyAnswer.response_id)
        .where(SurveyResponse.survey_id == survey_id, SurveyResponse.is_complete.is_(True))
        .group_by(SurveyAnswer.question_id, SurveyAnswer.option_id)).all()}
    numeric = {q: (n, avg) for q, n, avg in db.execute(
        select(SurveyAnswer.question_id, func.count(), func.avg(SurveyAnswer.number_value))
        .join(SurveyResponse, SurveyResponse.id == SurveyAnswer.response_id)
        .where(SurveyResponse.survey_id == survey_id, SurveyAnswer.number_value.is_not(None))
        .group_by(SurveyAnswer.question_id)).all()}
    texts = {q: n for q, n in db.execute(
        select(SurveyAnswer.question_id, func.count()).where(SurveyAnswer.text_value.is_not(None))
        .join(SurveyResponse, SurveyResponse.id == SurveyAnswer.response_id)
        .where(SurveyResponse.survey_id == survey_id).group_by(SurveyAnswer.question_id)).all()}
    sections = []
    for sec in survey.sections:
        qs = []
        for q in sec.questions:
            opts = [{"label": o.label, "value": o.value, "count": counts.get((q.id, o.id), 0)} for o in q.options]
            answered = sum(o["count"] for o in opts)
            mean = round(sum(o["value"] * o["count"] for o in opts) / answered, 2) if answered and q.type != "multi_choice" else None
            item = {"id": q.id, "number": q.number, "text": q.text, "type": q.type, "options": opts,
                    "answered": answered, "mean": mean}
            if q.type == "number" and q.id in numeric:
                item["answered"], item["mean"] = numeric[q.id][0], round(float(numeric[q.id][1]), 2)
            if q.type == "text":
                item["answered"] = texts.get(q.id, 0)
            qs.append(item)
        means = [x["mean"] for x in qs if x["mean"] is not None and x["type"] in ("single_choice", "rating", "dropdown")]
        sections.append({"title": sec.title, "questions": qs,
                         "mean": round(sum(means) / len(means), 2) if means else None})
    return {"survey_id": survey_id, "title": survey.title, "total_responses": total, "sections": sections}


@router.get("/search")
def search(q: str = Query(min_length=2), db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> dict:
    """Header search over surveys and projects."""
    like = f"%{q.strip()}%"
    surveys = db.scalars(select(Survey).where(Survey.title.ilike(like)).order_by(Survey.created_at.desc()).limit(5)).all()
    projects = db.scalars(select(Project).where(Project.name.ilike(like)).order_by(Project.last_updated.desc()).limit(5)).all()
    return {"surveys": [{"id": s.id, "title": s.title, "status": s.status} for s in surveys],
            "projects": [{"id": p.id, "name": p.name, "status": p.status} for p in projects]}


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[str]:
    """Short alerts for the bell icon."""
    out = []
    drafts = db.scalar(select(func.count()).select_from(Survey).where(Survey.status == "draft")) or 0
    pending = db.scalar(select(func.count()).select_from(Project).where(Project.status == "pending_review")) or 0
    day = db.scalar(select(func.count()).select_from(SurveyResponse).where(
        SurveyResponse.submitted_at >= _now() - timedelta(days=1))) or 0
    if day:
        out.append(f"{day} survey response(s) in the last 24 hours")
    if drafts:
        out.append(f"{drafts} draft survey(s) waiting to be published")
    if pending:
        out.append(f"{pending} project(s) pending review")
    return out
