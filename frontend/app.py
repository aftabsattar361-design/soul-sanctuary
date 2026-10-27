"""Entry point: page config, global CSS, top navigation and auth guard.  Run: streamlit run app.py"""
import streamlit as st

st.set_page_config(page_title="Soul Sanctuary | Research & Data Management", page_icon="\U0001F9EC", layout="wide",
                   initial_sidebar_state="collapsed")

import api_client  # noqa: E402
import components  # noqa: E402
import utils  # noqa: E402

utils.inject_css()

ZW = "\u200b"  # zero-width label for icon-only popovers


def logout() -> None:
    """Clear the session and return to the login page."""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def render_topbar(pages: list, user: dict) -> None:
    """Logo | nav links | search + bell | user menu."""
    try:
        alerts = api_client.notifications()
    except api_client.ApiError:
        alerts = []
    with st.container(key="topbar"):
        c_logo, c_nav, c_icons, c_user = st.columns([3.1, 5.2, 1.1, 2.7], vertical_alignment="center")
        with c_logo:
            st.html(components.brand())
        with c_nav:
            for col, page in zip(st.columns(len(pages)), pages):
                with col:
                    st.page_link(page, label=page.title)
        with c_icons:
            s_col, b_col = st.columns(2)
            with s_col, st.container(key="search_pop"):
                with st.popover(ZW, icon=":material/search:"):
                    q = st.text_input("Search surveys and projects", key="global_search")
                    if q and len(q.strip()) >= 2:
                        try:
                            res = api_client.search(q.strip())
                            if not res["surveys"] and not res["projects"]:
                                st.caption("No matches.")
                            for s in res["surveys"]:
                                st.markdown(f"**Survey** - {s['title']} ({s['status']})")
                            for p in res["projects"]:
                                st.markdown(f"**Project** - {p['name']} ({p['status'].replace('_', ' ')})")
                        except api_client.ApiError as err:
                            utils.show_error(err)
            with b_col, st.container(key="bell_dot" if alerts else "bell_plain"):
                with st.popover(ZW, icon=":material/notifications:"):
                    if alerts:
                        for a in alerts:
                            st.markdown(f"- {a}")
                    else:
                        st.caption("You're all caught up.")
        with c_user:
            u_html, u_menu = st.columns([5, 1.2], vertical_alignment="center")
            with u_html:
                st.html(components.user_chip(user["name"], user["role"], user.get("avatar_url")))
            with u_menu, st.container(key="user_pop"):
                with st.popover(ZW, icon=":material/keyboard_arrow_down:"):
                    st.markdown(f"**{user['name']}**  \n{user['email']}")
                    if st.button("Log out", key="logout_btn", icon=":material/logout:"):
                        logout()


authed = bool(st.session_state.get("token")) and bool(st.session_state.get("user"))
if not authed:
    login_page = st.Page("pages/Login_Register.py", title="Login / Register", url_path="login", default=True)
    st.navigation([login_page], position="hidden").run()
else:
    pages = [
        st.Page("pages/Dashboard.py", title="Dashboard", url_path="dashboard", default=True),
        st.Page("pages/Surveys.py", title="Surveys", url_path="surveys"),
        st.Page("pages/Data.py", title="Data", url_path="data"),
        st.Page("pages/Analytics.py", title="Analytics", url_path="analytics"),
        st.Page("pages/Social_Media.py", title="Social Media", url_path="social-media"),
    ]
    nav = st.navigation(pages, position="hidden")
    render_topbar(pages, st.session_state["user"])
    nav.run()
