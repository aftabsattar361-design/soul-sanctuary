"""Surveys: take an active survey (multi-section form), browse all surveys, admin creates new ones."""
from html import escape

import streamlit as st

import api_client
import components as C
import utils

user = st.session_state["user"]
is_admin = user["role"] == "admin"
st.html(C.page_title("Surveys", "Take a survey, review all surveys, or create a new one."))

tabs = st.tabs(["Take a survey", "All surveys"] + (["Create survey"] if is_admin else []))


# ---------------------------------------------------------------- helpers
def _label_map(q: dict) -> dict[str, int]:
    return {o["label"]: o["id"] for o in q["options"]}


def _saved_label(q: dict, saved: dict | None) -> str | None:
    if not saved or saved.get("option_id") is None:
        return None
    return next((o["label"] for o in q["options"] if o["id"] == saved["option_id"]), None)


def question_widget(q: dict, saved: dict | None) -> dict | None:
    """Render the right widget for the question type; return the normalized answer or None."""
    label = f"Q{q['number']}. {q['text']}" + ("" if q["required"] else " (optional)")
    key = f"w_{q['id']}"
    kind = q["type"]
    answer: dict | None = None
    if kind in ("single_choice", "rating"):
        labels = [o["label"] for o in q["options"]]
        cur = _saved_label(q, saved)
        pick = st.radio(label, labels, index=labels.index(cur) if cur in labels else None, key=key,
                        horizontal=(kind == "rating"))
        if pick:
            answer = {"question_id": q["id"], "option_id": _label_map(q)[pick]}
    elif kind == "dropdown":
        labels = [o["label"] for o in q["options"]]
        cur = _saved_label(q, saved)
        pick = st.selectbox(label, labels, index=labels.index(cur) if cur in labels else None, key=key, placeholder="Select an option")
        if pick:
            answer = {"question_id": q["id"], "option_id": _label_map(q)[pick]}
    elif kind == "multi_choice":
        labels = [o["label"] for o in q["options"]]
        ids = (saved or {}).get("option_ids", [])
        default = [o["label"] for o in q["options"] if o["id"] in ids]
        picks = st.multiselect(label, labels, default=default, key=key)
        if picks:
            answer = {"question_id": q["id"], "option_ids": [_label_map(q)[p] for p in picks]}
    elif kind == "text":
        txt = st.text_area(label, value=(saved or {}).get("text_value", ""), key=key)
        if txt.strip():
            answer = {"question_id": q["id"], "text_value": txt.strip()}
    elif kind == "number":
        num = st.number_input(label, value=(saved or {}).get("number_value"), key=key, step=1.0, format="%g")
        if num is not None:
            answer = {"question_id": q["id"], "number_value": float(num)}
    if q.get("help_text"):
        st.html(f'<div class="sv-help">{escape(q["help_text"])}</div>')
    return answer


def thank_you(submitted_at: str | None = None, again: bool = False) -> None:
    when = f" on {utils.fmt_date(submitted_at)}" if submitted_at else ""
    title = "You have already taken this survey" if again else "Thank you!"
    body = f"Your response was recorded{when}. It will appear in the dashboard and analytics." if not again else \
        f"Your response was recorded{when}. Each person can submit a survey only once."
    st.html(f'<div class="thanks"><i class="bi bi-check-circle-fill"></i><h2>{title}</h2><p>{escape(body)}</p></div>')


def missing_required(survey: dict, answers: dict[int, dict], section_idx: int | None = None) -> list[int]:
    """Question numbers of unanswered required questions (one section or the whole survey)."""
    secs = survey["sections"] if section_idx is None else [survey["sections"][section_idx]]
    return [q["number"] for s in secs for q in s["questions"] if q["required"] and q["id"] not in answers]


def take_survey(summary: dict) -> None:
    sid = summary["id"]
    try:
        mine = api_client.my_response(sid)
    except api_client.ApiError as err:
        utils.show_error(err)
        return
    if mine["submitted"]:
        thank_you(mine.get("submitted_at"), again=not st.session_state.get(f"sv_{sid}_done"))
        return
    try:
        survey = api_client.survey_detail(sid)
    except api_client.ApiError as err:
        utils.show_error(err)
        return
    sections = survey["sections"]
    total_q = sum(len(s["questions"]) for s in sections)
    answers: dict[int, dict] = st.session_state.setdefault(f"sv_{sid}_answers", {})
    step = min(st.session_state.get(f"sv_{sid}_step", 0), len(sections) - 1)

    with st.container(key="survey_card"):
        st.html(f'<div class="sv-title">{escape(survey["title"])}</div>')
        if survey.get("description"):
            st.caption(survey["description"])
        st.progress(len(answers) / total_q if total_q else 0.0,
                    text=f"Section {step + 1} of {len(sections)} \u2022 {len(answers)} of {total_q} questions answered")
        sec = sections[step]
        st.html(f'<div class="sv-section">{escape(sec["title"])}</div>')
        if sec.get("description"):
            st.html(f'<div class="sv-purpose">{escape(sec["description"])}</div>')
        last = step == len(sections) - 1
        with st.form(f"sv_form_{sid}_{step}"):
            current = {q["id"]: question_widget(q, answers.get(q["id"])) for q in sec["questions"]}
            b1, b2, _ = st.columns([1, 1.4, 4])
            back = b1.form_submit_button("Back", disabled=step == 0)
            nxt = b2.form_submit_button("Submit survey" if last else "Next section", type="primary")
        if back or nxt:
            for qid, ans in current.items():
                if ans is None:
                    answers.pop(qid, None)
                else:
                    answers[qid] = ans
            if back:
                st.session_state[f"sv_{sid}_step"] = step - 1
                st.rerun()
            miss = missing_required(survey, answers, step)
            if miss:
                st.error("Please answer the required question(s): " + ", ".join(f"Q{n}" for n in miss))
            elif not last:
                st.session_state[f"sv_{sid}_step"] = step + 1
                st.rerun()
            else:
                all_miss = missing_required(survey, answers)
                if all_miss:
                    st.error("Some earlier questions are unanswered: " + ", ".join(f"Q{n}" for n in all_miss))
                    return
                try:
                    api_client.submit_survey(sid, list(answers.values()))
                except api_client.ApiError as err:
                    if err.status == 409:
                        st.warning(err.detail)
                    else:
                        utils.show_error(err)
                        return
                st.session_state[f"sv_{sid}_done"] = True
                st.session_state.pop(f"sv_{sid}_answers", None)
                st.session_state.pop(f"sv_{sid}_step", None)
                st.rerun()


# ---------------------------------------------------------------- tab: take
with tabs[0]:
    try:
        active = api_client.active_surveys()
    except api_client.ApiError as err:
        utils.show_error(err)
        active = []
    else:
        if not active:
            st.info("There is no active survey to take right now.")
        else:
            idx = 0
            if len(active) > 1:
                titles = [s["title"] for s in active]
                idx = titles.index(st.selectbox("Choose a survey", titles, key="sv_choice"))
            take_survey(active[idx])

# ---------------------------------------------------------------- tab: all
with tabs[1]:
    try:
        rows = api_client.list_surveys()
    except api_client.ApiError as err:
        utils.show_error(err)
        rows = []
    status_filter = st.selectbox("Status", ["All", "active", "draft", "completed"], key="sv_filter")
    shown = [r for r in rows if status_filter == "All" or r["status"] == status_filter]
    st.caption(f"{len(shown)} survey(s)")
    table_rows = [[escape(r["title"]), utils.fmt_int(r["question_count"]), utils.fmt_int(r["response_count"]),
                   C.status_pill(r["status"]), utils.fmt_date(r["created_at"])] for r in shown[:200]]
    st.html(C.data_table(["Survey", "Questions", "Responses", "Status", "Created"], table_rows,
                         empty_text="No surveys match this filter."))
    if len(shown) > 200:
        st.caption("Showing the latest 200 surveys.")

# ---------------------------------------------------------------- tab: create (admin)
if is_admin:
    with tabs[2]:
        if C.new_survey_form("sv_new"):
            st.rerun()
