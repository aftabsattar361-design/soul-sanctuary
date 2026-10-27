"""Login / Register page (the only page visible without a token)."""
from datetime import date

import streamlit as st

import api_client
import components
import utils

st.html(f'<div class="login-brand">{components.brand()}</div>')
st.html('<div class="login-note">Sign in to continue to the research platform</div>')

if st.session_state.get("flash_error"):
    st.warning(st.session_state.pop("flash_error"))


def _start_session(result: dict) -> None:
    st.session_state["token"] = result["access_token"]
    st.session_state["user"] = result["user"]
    st.rerun()


with st.container(key="login_card"):
    st.markdown("### 🚀 Quick Demo Access")
    col_admin, col_member = st.columns(2)
    with col_admin:
        if st.button("⚡ Admin Login (one click)", type="primary", use_container_width=True,
                     help="Logs in as Alex Morgan – Admin"):
            try:
                _start_session(api_client.login("admin@soulsanctuary.local", "Admin@12345"))
            except api_client.ApiError as err:
                utils.show_error(err)
    with col_member:
        if st.button("⚡ Member Login (one click)", use_container_width=True,
                     help="Logs in as a verified demo member"):
            try:
                _start_session(api_client.login("demo1@demo.local", "DemoPass123"))
            except api_client.ApiError as err:
                utils.show_error(err)

    st.divider()

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", value="admin@soulsanctuary.local", key="login_email")
            password = st.text_input("Password", value="Admin@12345", type="password", key="login_password")
            go = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if go:
            if not email or not password:
                st.error("Enter your email and password.")
            else:
                try:
                    _start_session(api_client.login(email, password))
                except api_client.ApiError as err:
                    utils.show_error(err)

    with tab_register:
        with st.form("register_form"):
            name = st.text_input("Full name")
            email_r = st.text_input("Email", key="reg_email")
            c1, c2 = st.columns(2)
            pw = c1.text_input("Password", type="password", key="reg_pw", help="8+ characters with upper, lower case and a digit")
            pw2 = c2.text_input("Confirm password", type="password", key="reg_pw2")
            c3, c4 = st.columns(2)
            dob = c3.date_input("Date of birth (18+)", value=None, min_value=date(1920, 1, 1), max_value=date(date.today().year - 18, date.today().month, min(date.today().day, 28)), format="YYYY-MM-DD")
            gender = c4.selectbox("Gender", ["Male", "Female", "Other", "Prefer not to say"], index=None, placeholder="Select")
            city = st.text_input("City")
            submitted = st.form_submit_button("Create account", type="primary")
        if submitted:
            problems = []
            if len(name.strip()) < 2:
                problems.append("Enter your full name.")
            if not email_r:
                problems.append("Enter your email.")
            if dob is None:
                problems.append("Select your date of birth.")
            if gender is None:
                problems.append("Select your gender.")
            if not city.strip():
                problems.append("Enter your city.")
            if pw != pw2:
                problems.append("Passwords do not match.")
            if problems:
                for p in problems:
                    st.error(p)
            else:
                try:
                    _start_session(api_client.register({
                        "name": name.strip(), "email": email_r, "password": pw, "confirm_password": pw2,
                        "date_of_birth": dob.isoformat(), "gender": gender, "city": city.strip()}))
                except api_client.ApiError as err:
                    utils.show_error(err)
