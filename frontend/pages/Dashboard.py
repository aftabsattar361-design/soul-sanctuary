"""Dashboard Overview: KPIs, analytics charts, social media + tables, all from the backend."""
from datetime import datetime

import streamlit as st

import api_client
import components as C
import utils

user = st.session_state["user"]
is_admin = user["role"] == "admin"


@st.dialog("Create new survey", width="large")
def new_survey_dialog() -> None:
    """Admin-only dialog that POSTs /surveys; the dashboard reloads afterwards."""
    if C.new_survey_form("dash_ns"):
        st.rerun()


# ---- refresh controls (outside the fragment so the interval can change) ----
with st.container(key="refresh_row"):
    _, c_auto, c_refresh = st.columns([7, 2.2, 1.4], vertical_alignment="center")
    auto = c_auto.toggle("Auto-refresh (60s)", key="dash_auto")
    if c_refresh.button("Refresh", icon=":material/refresh:", key="dash_refresh"):
        st.rerun()


def render_dashboard() -> None:
    """Fetch /dashboard/overview once and draw every section."""
    placeholder = st.empty()
    placeholder.html(C.skeleton())
    try:
        data = api_client.get_overview()
    except api_client.ApiError as err:
        placeholder.empty()
        if err.status == 401:
            st.rerun(scope="app")
        utils.show_error(err)
        st.info("Make sure the backend is running, then press Refresh.")
        return
    placeholder.empty()

    s = data["summary"]
    # ---- title row ----
    c_title, c_export, c_new = st.columns([6.2, 1.5, 1.6], vertical_alignment="center")
    c_title.html(C.page_title("Dashboard Overview",
                              f"Real-time insights for research and data management \u2014 updated {utils.fmt_date(s['updated_at'])}"))
    if is_admin:
        with c_export, st.container(key="btn_export"):
            try:
                csv_bytes = api_client.export_report()
                st.download_button("Export Report", data=csv_bytes, mime="text/csv", icon=":material/download:",
                                   file_name=f"soul-sanctuary-report-{datetime.now():%Y%m%d}.csv", key="dash_export")
            except api_client.ApiError as err:
                utils.show_error(err)
        with c_new, st.container(key="btn_new"):
            if st.button("+ New Survey", key="dash_new_survey"):
                new_survey_dialog()

    # ---- KPI cards ----
    st.html(C.kpi_row(s))

    # ---- analytics ----
    sr, rg, dm = data["survey_responses"], data["registration_growth"], data["demographics"]
    with st.container(key="analytics_box"):
        st.html(C.section_title("Analytics Overview"))
        c1, c2, c3 = st.columns(3)
        with c1:
            st.html(C.chart_title("Survey Responses"))
            st.plotly_chart(C.bar_chart(sr["labels"], sr["values"]), config=C.CHART_CONFIG, key="ch_resp")
            st.html(C.caption(f"Total: {utils.fmt_int(sr['total'])} Responses"))
        with c2:
            st.html(C.chart_title("User Registration Growth"))
            st.plotly_chart(C.line_chart(rg["months"], rg["values"]), config=C.CHART_CONFIG, key="ch_reg")
            st.html(C.caption(f"YTD: +{utils.fmt_int(rg['ytd_total'])} users"))
        with c3:
            st.html(C.chart_title("Demographics"))
            st.plotly_chart(C.pie_chart(dm["groups"]), config=C.CHART_CONFIG, key="ch_demo")
            st.html(C.caption(f"{utils.fmt_int(dm['total'])} users with age on file"))

    # ---- social media integration ----
    st.html(C.section_title("Social Media Integration"))
    left, right = st.columns(2)
    left.html(C.social_card_instagram(data["social"]["instagram"], data["surveys_table"]))
    right.html(C.social_card_facebook(data["social"]["facebook"], data["projects_table"]))


st.fragment(run_every=60 if auto else None)(render_dashboard)()
