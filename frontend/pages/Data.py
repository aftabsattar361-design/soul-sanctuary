"""Data: full projects table with search and status filter."""
from html import escape

import streamlit as st

import api_client
import components as C
import utils

is_admin = st.session_state["user"]["role"] == "admin"
st.html(C.page_title("Data", "All research projects and datasets."))

c1, c2, _ = st.columns([3, 2, 3])
search = c1.text_input("Search by project or owner", key="data_search", placeholder="Search...")
status_label = c2.selectbox("Status", ["All", "Processed", "Active", "Pending Review"], key="data_status")
status = {"All": "", "Processed": "processed", "Active": "active", "Pending Review": "pending_review"}[status_label]

try:
    result = api_client.projects(search.strip(), status)
except api_client.ApiError as err:
    utils.show_error(err)
    st.stop()

st.html(f'<div class="chip-row"><div class="mini-kpi"><b>{utils.fmt_int(result["total"])}</b><span>Projects</span></div>'
        f'<div class="mini-kpi"><b>{utils.fmt_int(result["total_entries"])}</b><span>Data entries</span></div></div>')
rows = [{"name": p["name"], "entries": p["entries_count"], "last_updated": p["last_updated"], "owner": p["owner_name"],
         "status": p["status"]} for p in result["items"]]
st.html(f'<div class="card">{C.projects_table(rows)}</div>')
if result["total"] > len(rows):
    st.caption(f"Showing the {len(rows)} most recently updated of {utils.fmt_int(result['total'])} projects. Refine the search to see others.")

if is_admin:
    with st.expander("Add a project"):
        with st.form("add_project"):
            name = st.text_input("Project name")
            a, b, d = st.columns(3)
            owner = a.text_input("Owner")
            entries = b.number_input("Data entries", min_value=0, value=0, step=100)
            st_label = d.selectbox("Status", ["Active", "Processed", "Pending Review"])
            ok = st.form_submit_button("Add project", type="primary")
        if ok:
            if len(name.strip()) < 2 or len(owner.strip()) < 2:
                st.error("Enter a project name and an owner.")
            else:
                try:
                    api_client.create_project({"name": name.strip(), "owner_name": owner.strip(), "entries_count": int(entries),
                                               "status": {"Active": "active", "Processed": "processed",
                                                          "Pending Review": "pending_review"}[st_label]})
                    st.success("Project added.")
                    st.rerun()
                except api_client.ApiError as err:
                    utils.show_error(err)
