"""Analytics: per-question charts built from real survey answers."""
from html import escape

import streamlit as st

import api_client
import components as C
import utils

st.html(C.page_title("Analytics", "Answer distribution for every survey question."))

try:
    surveys = [s for s in api_client.list_surveys() if s["question_count"] > 0]
except api_client.ApiError as err:
    utils.show_error(err)
    st.stop()
if not surveys:
    st.info("No survey with questions exists yet.")
    st.stop()

titles = [s["title"] for s in surveys]
chosen = surveys[titles.index(st.selectbox("Survey", titles, key="an_survey"))]
try:
    stats = api_client.question_stats(chosen["id"])
except api_client.ApiError as err:
    utils.show_error(err)
    st.stop()

mini = "".join(f'<div class="mini-kpi"><b>{v}</b><span>{escape(k)}</span></div>' for k, v in
               [("Completed responses", utils.fmt_int(stats["total_responses"]))] +
               [(f"Average score: {s['title'].split(':')[0]}", f"{s['mean']:.2f} / 5" if s["mean"] is not None else "-")
                for s in stats["sections"]])
st.html(f'<div class="chip-row">{mini}</div>')
if not stats["total_responses"]:
    st.info("No responses yet. Charts will appear after the first submission.")

for sec in stats["sections"]:
    st.html(C.section_title(sec["title"]))
    cols = st.columns(2)
    for i, q in enumerate(sec["questions"]):
        with cols[i % 2], st.container(border=True):
            st.markdown(f"**Q{q['number']}.** {q['text']}")
            if q["options"]:
                st.plotly_chart(C.option_bar([o["label"] for o in q["options"]], [o["count"] for o in q["options"]]),
                                config=C.CHART_CONFIG, key=f"an_{q['id']}")
                note = f"{q['answered']} answered"
                if q["mean"] is not None:
                    note += f" \u2022 average option position {q['mean']:.2f} of {len(q['options'])}"
                st.caption(note)
            else:
                st.caption(f"{q['answered']} answered" + (f" \u2022 average {q['mean']}" if q["mean"] is not None else ""))
