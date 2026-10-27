"""Every call to the FastAPI backend goes through this module (JWT header, errors, timeouts)."""
import os
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()


def _resolve_api_url() -> str:
    """Resolve API_BASE_URL from env, then Streamlit secrets, then fallback."""
    url = os.getenv("API_BASE_URL", "").strip()
    if not url:
        try:
            url = st.secrets.get("API_BASE_URL", "")
        except Exception:
            pass
    if not url:
        url = "http://localhost:8000"
    url = url.rstrip("/")
    if url and "://" not in url:
        url = f"https://{url}"
    return url


API_BASE_URL = _resolve_api_url()
DEFAULT_TIMEOUT = 20


class ApiError(Exception):
    """Raised for any failed backend call. status == 0 means the backend is unreachable."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _detail(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or resp.reason
    d = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(d, list):  # FastAPI validation errors
        parts = []
        for item in d:
            msg = str(item.get("msg", "")).replace("Value error, ", "")
            loc = [str(x) for x in item.get("loc", []) if x not in ("body", "query")]
            parts.append(f"{' > '.join(loc)}: {msg}" if loc else msg)
        return "; ".join(parts)
    return str(d)


def _request(method: str, path: str, *, params: dict | None = None, json: Any = None, auth: bool = True,
             timeout: int = DEFAULT_TIMEOUT, raw: bool = False) -> Any:
    headers = {}
    token = st.session_state.get("token")
    if auth and token:
        headers["Authorization"] = f"Bearer {token}"
    base = _resolve_api_url()
    try:
        resp = requests.request(method, f"{base}{path}", params=params, json=json, headers=headers, timeout=timeout)
    except requests.ConnectionError:
        raise ApiError(0, f"Cannot reach the backend at {base}. Make sure the backend service is running.")
    except requests.Timeout:
        raise ApiError(0, "The backend took too long to respond. Please try again.")
    if resp.status_code == 401 and auth and token:
        for k in ("token", "user"):
            st.session_state.pop(k, None)
        st.session_state["flash_error"] = "Your session expired. Please sign in again."
        raise ApiError(401, "Session expired")
    if not resp.ok:
        raise ApiError(resp.status_code, _detail(resp))
    if raw:
        return resp.content
    return resp.json() if resp.content else None


# ---- auth ----
def register(payload: dict) -> dict:
    return _request("POST", "/auth/register", json=payload, auth=False)


def login(email: str, password: str) -> dict:
    return _request("POST", "/auth/login", json={"email": email, "password": password}, auth=False)


def me() -> dict:
    return _request("GET", "/auth/me")


# ---- dashboard ----
def get_overview() -> dict:
    return _request("GET", "/dashboard/overview")


def export_report() -> bytes:
    return _request("GET", "/dashboard/export", raw=True)


def question_stats(survey_id: int) -> dict:
    return _request("GET", "/dashboard/question-stats", params={"survey_id": survey_id})


def search(q: str) -> dict:
    return _request("GET", "/dashboard/search", params={"q": q})


def notifications() -> list[str]:
    return _request("GET", "/dashboard/notifications", timeout=5)


# ---- surveys ----
def list_surveys() -> list[dict]:
    return _request("GET", "/surveys")


def active_surveys() -> list[dict]:
    return _request("GET", "/surveys/active")


def survey_detail(survey_id: int) -> dict:
    return _request("GET", f"/surveys/{survey_id}")


def my_response(survey_id: int) -> dict:
    return _request("GET", "/surveys/my-response", params={"survey_id": survey_id})


def submit_survey(survey_id: int, answers: list[dict]) -> dict:
    return _request("POST", "/surveys/submit", json={"survey_id": survey_id, "answers": answers})


def create_survey(payload: dict) -> dict:
    return _request("POST", "/surveys", json=payload)


# ---- projects ----
def projects(search_text: str = "", status: str = "") -> dict:
    params = {k: v for k, v in {"search": search_text, "status": status}.items() if v}
    return _request("GET", "/projects", params=params)


def create_project(payload: dict) -> dict:
    return _request("POST", "/projects", json=payload)


# ---- social ----
def social_stats() -> list[dict]:
    return _request("GET", "/social/stats")


def update_social_stats(payload: dict) -> dict:
    return _request("PUT", "/social/stats", json=payload)


def sync_social() -> dict:
    return _request("POST", "/social/sync", timeout=40)


def social_posts() -> list[dict]:
    return _request("GET", "/social/posts", auth=False)


def create_post(content: str) -> dict:
    return _request("POST", "/social/posts", json={"content": content})
