"""Reusable HTML builders (header, KPI card, status pill, tables, social cards) and Plotly chart builders."""
from html import escape

import streamlit as st

import api_client
from utils import fmt_compact, fmt_date, fmt_delta, fmt_int, initials

TEAL, PURPLE, ORANGE, GREY = "#11a1a2", "#724abe", "#f2953a", "#cecece"


def _c(html: str) -> str:
    """Collapse multi-line HTML so Streamlit never treats indentation as a code block."""
    return "".join(line.strip() for line in html.strip().splitlines())


def icon(name: str, cls: str = "") -> str:
    """Bootstrap Icons glyph."""
    return f'<i class="bi bi-{name} {cls}"></i>'


# ------------------------------------------------------------------ header pieces
def brand() -> str:
    """Logo mark (teal molecule) + 'Research & Data Management' on two lines."""
    svg = ('<svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">'
           '<g stroke="#0f3d56" stroke-width="2.2" stroke-linecap="round">'
           '<path d="M20 20 L20 7"/><path d="M20 20 L31 26.5"/><path d="M20 20 L9 26.5"/><path d="M20 7 L31 13.5"/></g>'
           '<circle cx="20" cy="20" r="5.2" fill="#009a9f"/><circle cx="20" cy="6.5" r="4.2" fill="#009a9f"/>'
           '<circle cx="31.5" cy="26.8" r="4.2" fill="#0f3d56"/><circle cx="8.5" cy="26.8" r="4.2" fill="#009a9f"/>'
           '<circle cx="31.5" cy="13.2" r="3.2" fill="#009a9f"/></svg>')
    return _c(f'<div class="brand">{svg}<div class="brand-title">Research &amp; Data<br>Management</div></div>')


def user_chip(name: str, role: str, avatar_url: str | None = None) -> str:
    """Avatar + name with role underneath."""
    avatar = (f'<img class="avatar" src="{escape(avatar_url)}" alt="">' if avatar_url
              else f'<span class="avatar avatar-initials">{escape(initials(name))}</span>')
    return _c(f'<div class="user-chip">{avatar}<div class="user-meta"><div class="user-name">{escape(name)}</div>'
              f'<div class="user-role">{escape(role.title())}</div></div></div>')


def page_title(title: str, subtitle: str) -> str:
    """Large bold page title with a grey subtitle."""
    return _c(f'<div class="page-title"><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>')


def section_title(text: str) -> str:
    return f'<h2 class="section-title">{escape(text)}</h2>'


# ------------------------------------------------------------------ KPI cards
KPI_TONES = {"teal": "people-fill", "purple": "card-checklist", "blue": "bar-chart-fill", "orange": "database-fill"}


def delta_html(kpi: dict, arrow: bool = False) -> str:
    """Green (or red when negative) delta line under a KPI number."""
    if kpi.get("delta_text"):
        text, neg = kpi["delta_text"], False
    elif kpi.get("delta_pct") is None:
        return '<div class="kpi-delta muted">No data for last month</div>'
    else:
        pct = kpi["delta_pct"]
        neg = pct < 0
        text = f"{pct:+.1f}% vs last month"
    mark = ("\u2198 " if neg else "\u2197 ") if arrow else ""
    return f'<div class="kpi-delta{" neg" if neg else ""}">{mark}{escape(text)}</div>'


def kpi_card(label: str, value: int, delta: str, tone: str) -> str:
    """One KPI card: colored icon tile, label, big number, delta."""
    return _c(f'<div class="kpi-card"><div class="kpi-tile tone-{tone}">{icon(KPI_TONES[tone])}</div>'
              f'<div class="kpi-body"><div class="kpi-label">{escape(label)}</div>'
              f'<div class="kpi-value">{fmt_int(value)}</div>{delta}</div></div>')


def kpi_row(summary: dict) -> str:
    """The four KPI cards in one grid row."""
    cards = [
        kpi_card("Total Registrations / Sign-ups", summary["registrations"]["value"],
                 delta_html(summary["registrations"], arrow=True), "teal"),
        kpi_card("Completed Surveys", summary["completed_surveys"]["value"],
                 delta_html(summary["completed_surveys"]), "purple"),
        kpi_card("Active Surveys", summary["active_surveys"]["value"], delta_html(summary["active_surveys"], arrow=True), "blue"),
        kpi_card("Data Entries", summary["data_entries"]["value"], delta_html(summary["data_entries"]), "orange"),
    ]
    return f'<div class="kpi-grid">{"".join(cards)}</div>'


# ------------------------------------------------------------------ pills + tables
PILLS = {"completed": ("Completed", "green"), "processed": ("Processed", "green"), "active": ("Active", "indigo"),
         "draft": ("Draft", "amber"), "pending_review": ("Pending Review", "yellow")}


def status_pill(status: str) -> str:
    """Rounded solid pill: green/indigo/amber/yellow."""
    label, tone = PILLS.get(status, (status.replace("_", " ").title(), "indigo"))
    return f'<span class="pill pill-{tone}">{escape(label)}</span>'


def data_table(headers: list[str], rows: list[list[str]], numbered: bool = True, empty_text: str = "Nothing to show yet.",
               empty_hint: str = "") -> str:
    """HTML table. Cells are trusted HTML (callers escape user text). Shows an empty state when no rows."""
    head = ("<th class='num'></th>" if numbered else "") + "".join(f"<th>{escape(h)}</th>" for h in headers)
    cols = len(headers) + (1 if numbered else 0)
    if rows:
        body = "".join("<tr>" + (f"<td class='num'>{i}</td>" if numbered else "") +
                       "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for i, row in enumerate(rows, start=1))
    else:
        hint = f"<div class='empty-hint'>{escape(empty_hint)}</div>" if empty_hint else ""
        body = f"<tr><td colspan='{cols}' class='empty'>{escape(empty_text)}{hint}</td></tr>"
    return _c(f'<table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def owner_cell(name: str) -> str:
    return f'<span class="owner"><span class="avatar avatar-sm">{escape(initials(name))}</span>{escape(name)}</span>'


def surveys_table(rows: list[dict]) -> str:
    """Instagram card table: Survey | Responses | Status | Date | Action."""
    out = []
    for r in rows:
        out.append([escape(r["title"]), f'{fmt_int(r["responses"])} responses', status_pill(r["status"]),
                    fmt_date(r["date"]), f'<span class="action-link">{escape(r["action"])}</span>'])
    return data_table(["Survey", "Responses", "Status", "Date", "Action"], out, empty_text="No surveys yet.",
                      empty_hint="Use + New Survey to create the first one.")


def projects_table(rows: list[dict], numbered: bool = True) -> str:
    """Facebook card table: Project | Data Entries | Last Updated | Owner | Status."""
    out = []
    for r in rows:
        out.append([escape(r["name"]), f'{fmt_int(r["entries"])} entries', fmt_date(r["last_updated"]),
                    owner_cell(r["owner"]), status_pill(r["status"])])
    return data_table(["Project", "Data Entries", "Last Updated", "Owner", "Status"], out, numbered=numbered,
                      empty_text="No projects yet.")


# ------------------------------------------------------------------ social cards
def _stat(icon_name: str, value: str, label: str) -> str:
    return (f'<div class="soc-stat">{icon(icon_name, "soc-stat-icon")}<div><div class="soc-num">{value}</div>'
            f'<div class="soc-lbl">{escape(label)}</div></div></div>')


def social_card_instagram(ig: dict, survey_rows: list[dict]) -> str:
    """Instagram stats row + survey table."""
    head = _c(f'<div class="soc-head"><div class="soc-brand"><span class="ig-badge">{icon("instagram")}</span>'
              f'<div><div class="soc-name">Instagram</div><div class="soc-lbl">Likes ({fmt_delta(ig["likes_delta"], True)})</div></div></div>'
              + _stat("heart-fill", fmt_compact(ig["shares"]), f'Shares ({fmt_delta(ig["shares_delta"])})')
              + _stat("chat-fill", fmt_compact(ig["comments"]), f'Comments ({fmt_delta(ig["comments_delta"])})')
              + _stat("people-fill", fmt_compact(ig["followers"]), f'Followers ({fmt_delta(ig["followers_delta"])})')
              + '</div>')
    return f'<div class="social-card">{head}{surveys_table(survey_rows)}</div>'


def social_card_facebook(fb: dict, project_rows: list[dict]) -> str:
    """Facebook stats row + 'Research / Data Management' project table."""
    head = _c(f'<div class="soc-head"><div class="soc-brand"><span class="fb-badge">{icon("facebook")}</span>'
              f'<div class="soc-name">Facebook</div></div>'
              f'<div class="soc-stat">{icon("hand-thumbs-up-fill", "soc-stat-icon fb")}<div class="soc-num">{fmt_compact(fb["likes"])}</div></div>'
              f'<div class="soc-stat">{icon("share-fill", "soc-stat-icon")}<div class="soc-lbl">Likes ({fmt_delta(fb["likes_delta"])})</div></div></div>')
    sub = '<h3 class="soc-sub">Research / Data Management</h3>'
    return f'<div class="social-card">{head}{sub}{projects_table(project_rows)}</div>'


def skeleton() -> str:
    """Loading placeholder shown while the backend answers."""
    kpis = "".join('<div class="kpi-card"><div class="sk sk-tile"></div><div class="sk-col"><div class="sk sk-line"></div>'
                   '<div class="sk sk-big"></div><div class="sk sk-line short"></div></div></div>' for _ in range(4))
    return _c(f'<div class="skeleton"><div class="sk sk-title"></div><div class="kpi-grid">{kpis}</div>'
              '<div class="sk-charts"><div class="sk sk-chart"></div><div class="sk sk-chart"></div><div class="sk sk-chart"></div></div>'
              '<div class="sk-charts two"><div class="sk sk-chart"></div><div class="sk sk-chart"></div></div></div>')


def caption(text: str) -> str:
    return f'<div class="chart-caption">{escape(text)}</div>'


def chart_title(text: str) -> str:
    return f'<div class="chart-title">{escape(text)}</div>'


# ------------------------------------------------------------------ Plotly figures
def _step(ymax: int, base: int) -> int:
    """Gridline step: `base` for small ranges, a round number (<= ~8 lines) for big ones."""
    if ymax <= base * 8:
        return base
    raw = ymax / 8
    mag = 10 ** (len(str(int(raw))) - 1)
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return int(m * mag)
    return int(raw)


def _base_layout(fig, height: int = 240):
    fig.update_layout(height=height, margin=dict(l=34, r=8, t=8, b=26), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter, sans-serif", size=11, color="#6b7280"),
                      showlegend=False, hoverlabel=dict(font_size=12))
    return fig


def empty_figure(message: str):
    import plotly.graph_objects as go
    fig = _base_layout(go.Figure())
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.add_annotation(text=message, showarrow=False, font=dict(size=13, color="#9ca3af"))
    return fig


def bar_chart(labels: list[str], values: list[int]):
    """Teal vertical bars, y axis 0-80 (grows only if data needs it), step 10."""
    import plotly.graph_objects as go
    top = max([80] + [int(-(-v // 10) * 10) for v in values])
    fig = _base_layout(go.Figure(go.Bar(x=labels, y=values, marker_color=TEAL, width=0.5,
                                         hovertemplate="%{x}: %{y} responses<extra></extra>")))
    fig.update_yaxes(range=[0, top], dtick=_step(top, 10), gridcolor="#e8ecf1", zeroline=False, showline=False,
                     fixedrange=True, tickfont=dict(size=10))
    fig.update_xaxes(showgrid=False, showline=False, fixedrange=True, tickfont=dict(size=10))
    return fig


def line_chart(months: list[str], values: list[int]):
    """Purple line with circular markers, y axis 0-2000 step 500."""
    import plotly.graph_objects as go
    top = max([2000] + [int(-(-v // 500) * 500) for v in values])
    fig = _base_layout(go.Figure(go.Scatter(x=months, y=values, mode="lines+markers", line=dict(color=PURPLE, width=2),
                                             marker=dict(color=PURPLE, size=6, symbol="circle"),
                                             hovertemplate="%{x}: %{y:,} new users<extra></extra>")))
    fig.update_yaxes(range=[0, top], dtick=_step(top, 500), gridcolor="#e8ecf1", zeroline=False, showline=False,
                     fixedrange=True, tickfont=dict(size=10))
    fig.update_xaxes(showgrid=False, showline=False, fixedrange=True, tickfont=dict(size=10))
    return fig


def pie_chart(groups: list[dict]):
    """Demographics pie, legend on the right: '18-24 (28%)' ..."""
    import plotly.graph_objects as go
    if not sum(g["count"] for g in groups):
        return empty_figure("No age data yet")
    fig = go.Figure(go.Pie(labels=[f'{g["label"]} ({g["percent"]}%)' for g in groups], values=[g["count"] for g in groups],
                           marker=dict(colors=[TEAL, PURPLE, ORANGE, GREY], line=dict(width=0)), textinfo="none", sort=False,
                           direction="clockwise", rotation=40, hovertemplate="%{label}: %{value:,} users<extra></extra>"))
    _base_layout(fig)
    fig.update_layout(showlegend=True, margin=dict(l=0, r=0, t=8, b=26),
                      legend=dict(orientation="v", x=1.0, xanchor="right", y=0.5, yanchor="middle", font=dict(size=12, color="#374151")))
    return fig


def option_bar(labels: list[str], counts: list[int]):
    """Horizontal bars for one survey question (Analytics page)."""
    import plotly.graph_objects as go
    total = sum(counts) or 1
    fig = go.Figure(go.Bar(y=labels[::-1], x=counts[::-1], orientation="h", marker_color=TEAL,
                           text=[f"{c} ({c * 100 / total:.0f}%)" for c in counts[::-1]], textposition="outside",
                           hovertemplate="%{y}: %{x}<extra></extra>", cliponaxis=False))
    _base_layout(fig, height=60 + 34 * len(labels))
    fig.update_layout(margin=dict(l=8, r=60, t=4, b=8))
    fig.update_xaxes(showgrid=True, gridcolor="#e8ecf1", zeroline=False, fixedrange=True, tickfont=dict(size=10),
                     range=[0, max(counts + [1]) * 1.25])
    fig.update_yaxes(showgrid=False, fixedrange=True, automargin=True, tickfont=dict(size=11, color="#374151"))
    return fig


CHART_CONFIG = {"displayModeBar": False}


# ------------------------------------------------------------------ create-survey form (used by dashboard dialog + Surveys page)
def new_survey_form(prefix: str = "ns") -> bool:
    """Admin form that builds a survey and POSTs it. Returns True after a successful creation."""
    title = st.text_input("Survey title", key=f"{prefix}_title", placeholder="e.g. Community Feedback 2026")
    desc = st.text_area("Description (optional)", key=f"{prefix}_desc", height=80)
    c1, c2 = st.columns(2)
    status = c1.selectbox("Status", ["draft", "active", "completed"], key=f"{prefix}_status",
                          help="Only active surveys can be taken by users.")
    section = c2.text_input("Section title", value="Section 1", key=f"{prefix}_section")
    n = int(st.number_input("Number of questions", min_value=1, max_value=30, value=3, step=1, key=f"{prefix}_n"))
    types = ["single_choice", "multi_choice", "rating", "dropdown", "text", "number"]
    questions = []
    for i in range(1, n + 1):
        with st.container(border=True):
            text = st.text_input(f"Question {i}", key=f"{prefix}_q{i}_text")
            a, b = st.columns([2, 1])
            qtype = a.selectbox("Type", types, key=f"{prefix}_q{i}_type")
            required = b.checkbox("Required", value=True, key=f"{prefix}_q{i}_req")
            options = ""
            if qtype in ("single_choice", "multi_choice", "dropdown"):
                options = st.text_area("Options (one per line)", key=f"{prefix}_q{i}_opts", height=90)
            elif qtype == "rating":
                options = st.text_area("Rating labels (one per line, leave empty for Strongly Disagree ... Strongly Agree)",
                                       key=f"{prefix}_q{i}_opts", height=90)
            questions.append({"text": text.strip(), "type": qtype, "required": required,
                              "options": [o.strip() for o in options.splitlines() if o.strip()]})
    if st.button("Create survey", type="primary", key=f"{prefix}_submit"):
        if len(title.strip()) < 3:
            st.error("Enter a survey title (at least 3 characters).")
            return False
        empty = [i for i, q in enumerate(questions, 1) if len(q["text"]) < 3]
        if empty:
            st.error("Write the text of question(s): " + ", ".join(map(str, empty)))
            return False
        try:
            api_client.create_survey({"title": title.strip(), "description": desc.strip() or None, "status": status,
                                      "sections": [{"title": section.strip() or "Section 1", "questions": questions}]})
        except api_client.ApiError as err:
            st.error(err.detail)
            return False
        st.success("Survey created.")
        return True
    return False
