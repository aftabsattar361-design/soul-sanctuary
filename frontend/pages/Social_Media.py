"""Social Media: share buttons, profile links, admin stats editor and the community feed."""
from html import escape

import streamlit as st

import api_client
import components as C
import utils

user = st.session_state["user"]
is_admin = user["role"] == "admin"
st.html(C.page_title("Social Media", "Share the platform, follow our channels and join the community feed."))

base = utils.public_url()
LINKS = {"WhatsApp": ("wa", "whatsapp"), "Facebook": ("fb", "facebook"), "X": ("x", "twitter-x"), "LinkedIn": ("in", "linkedin")}


def share_row(url: str, text: str) -> str:
    links = utils.share_links(url, text)
    items = "".join(f'<a class="share-btn {LINKS[n][0]}" href="{escape(href)}" target="_blank" rel="noopener">{C.icon(LINKS[n][1])} {n}</a>'
                    for n, href in links.items())
    return f'<div class="share-row">{items}</div>'


left, right = st.columns(2)
with left, st.container(border=True):
    st.markdown("#### Share")
    st.html('<div class="share-label">Survey link</div>' + share_row(f"{base}/surveys", "Take part in our research survey"))
    st.html('<div class="share-label">Dashboard link</div>' + share_row(f"{base}/dashboard", "Explore the Soul Sanctuary research dashboard"))
    st.caption(f"Links use PUBLIC_APP_URL from .env ({base}).")
with right, st.container(border=True):
    st.markdown("#### Follow us")
    prof = utils.profile_links()
    cls = {"Instagram": ("ig", "instagram"), "Facebook": ("fb", "facebook"), "YouTube": ("yt", "youtube")}
    st.html('<div class="share-row">' + "".join(
        f'<a class="share-btn {cls[n][0]}" href="{escape(u)}" target="_blank" rel="noopener">{C.icon(cls[n][1])} {n}</a>'
        for n, u in prof.items()) + '</div>')
    stats: dict = {}
    try:
        stats = {s["platform"]: s for s in api_client.social_stats()}
        ig, fb = stats.get("instagram"), stats.get("facebook")
        st.caption(f"Instagram followers {utils.fmt_compact(ig['followers'] if ig else 0)} \u2022 "
                   f"Facebook likes {utils.fmt_compact(fb['likes'] if fb else 0)}")
    except api_client.ApiError as err:
        utils.show_error(err)

if is_admin:
    with st.expander("Admin: update social media numbers"):
        platform = st.selectbox("Platform", ["instagram", "facebook"], key="soc_platform")
        current = stats.get(platform) or {}
        with st.form("soc_form"):
            a, b = st.columns(2)
            likes = a.number_input("Likes", min_value=0, value=int(current.get("likes", 0)))
            likes_d = b.number_input("Likes change (+)", value=int(current.get("likes_delta", 0)))
            c, d = st.columns(2)
            shares = c.number_input("Shares", min_value=0, value=int(current.get("shares", 0)))
            shares_d = d.number_input("Shares change (+)", value=int(current.get("shares_delta", 0)))
            e, f = st.columns(2)
            comments = e.number_input("Comments", min_value=0, value=int(current.get("comments", 0)))
            comments_d = f.number_input("Comments change (+)", value=int(current.get("comments_delta", 0)))
            g, h = st.columns(2)
            followers = g.number_input("Followers", min_value=0, value=int(current.get("followers", 0)))
            followers_d = h.number_input("Followers change (+)", value=int(current.get("followers_delta", 0)))
            save = st.form_submit_button("Save numbers", type="primary")
        if save:
            try:
                api_client.update_social_stats({
                    "platform": platform, "likes": int(likes), "likes_delta": int(likes_d), "shares": int(shares),
                    "shares_delta": int(shares_d), "comments": int(comments), "comments_delta": int(comments_d),
                    "followers": int(followers), "followers_delta": int(followers_d)})
                st.success("Saved. The dashboard shows the new numbers on its next refresh.")
            except api_client.ApiError as err:
                utils.show_error(err)
        if st.button("Sync from Meta Graph API", key="soc_sync"):
            try:
                res = api_client.sync_social()
                (st.success if res.get("synced") else st.info)(res.get("reason") or f"Synced: {res.get('updated')}")
            except api_client.ApiError as err:
                utils.show_error(err)

st.html(C.section_title("Community feed"))
with st.form("post_form", clear_on_submit=True):
    content = st.text_area("Share something with the community", max_chars=1000, height=90)
    posted = st.form_submit_button("Post", type="primary")
if posted:
    if not content.strip():
        st.error("Write something before posting.")
    else:
        try:
            api_client.create_post(content.strip())
        except api_client.ApiError as err:
            utils.show_error(err)

try:
    posts = api_client.social_posts()
except api_client.ApiError as err:
    utils.show_error(err)
    posts = []
if not posts:
    st.info("No posts yet. Be the first to share something.")
for p in posts[:50]:
    st.html(f'<div class="post"><div class="post-head"><span class="avatar avatar-sm" style="margin:0">{escape(utils.initials(p["author"]))}</span>'
            f'<div><div class="post-author">{escape(p["author"])}</div><div class="post-time">{utils.fmt_date(p["created_at"])}</div></div></div>'
            f'<div class="post-body">{escape(p["content"])}</div></div>')
