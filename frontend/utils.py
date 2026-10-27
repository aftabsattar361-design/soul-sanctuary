"""CSS loader, formatters and share-link builders."""
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
load_dotenv()


def inject_css() -> None:
    """Inject styles.css (global styles, Inter font, Bootstrap Icons) into the page."""
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def fmt_int(n: int | float | None) -> str:
    """12847 -> '12,847'."""
    return f"{int(n or 0):,}"


def fmt_compact(n: int | float | None) -> str:
    """45600 -> '45.6K', 1400 -> '1.4K', 850 -> '850', 2_300_000 -> '2.3M'."""
    n = float(n or 0)
    for limit, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(n) >= limit:
            v = n / limit
            return f"{v:.1f}".rstrip("0").rstrip(".") + suffix if v < 100 else f"{v:.0f}{suffix}"
    return f"{int(n)}"


def fmt_delta(n: int | float | None, lowercase_k: bool = False) -> str:
    """1200 -> '+1.2k' (lowercase_k) or '+1.2K'; 210 -> '+210'; negatives keep their minus."""
    n = float(n or 0)
    sign = "+" if n >= 0 else "-"
    text = fmt_compact(abs(n))
    return sign + (text.replace("K", "k") if lowercase_k else text)


def parse_dt(value: str | datetime | None) -> datetime | None:
    """Parse an ISO timestamp from the backend."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fmt_date(value: str | datetime | None) -> str:
    """'2026-10-05T..' -> 'Oct 5, 2026'."""
    d = parse_dt(value)
    return f"{d.strftime('%b')} {d.day}, {d.year}" if d else "-"


def initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p and p.lower() != "dr"]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


# ---- links from .env ----
def public_url() -> str:
    url = os.getenv("PUBLIC_APP_URL", "http://localhost:8501").rstrip("/")
    return url if "://" in url else f"https://{url}"


def profile_links() -> dict[str, str]:
    return {"Instagram": os.getenv("INSTAGRAM_URL", "https://www.instagram.com/"),
            "Facebook": os.getenv("FACEBOOK_URL", "https://www.facebook.com/"),
            "YouTube": os.getenv("YOUTUBE_URL", "https://www.youtube.com/")}


def share_links(url: str, text: str) -> dict[str, str]:
    """Share URLs for WhatsApp, Facebook, X and LinkedIn."""
    u, t = quote(url, safe=""), quote(text, safe="")
    return {"WhatsApp": f"https://wa.me/?text={quote(text + ' ' + url, safe='')}",
            "Facebook": f"https://www.facebook.com/sharer/sharer.php?u={u}",
            "X": f"https://twitter.com/intent/tweet?text={t}&url={u}",
            "LinkedIn": f"https://www.linkedin.com/sharing/share-offsite/?url={u}"}


def show_error(err: Exception) -> None:
    """Render a backend error consistently."""
    status = getattr(err, "status", None)
    detail = getattr(err, "detail", str(err))
    if status == 0:
        st.error(f"Backend unavailable. {detail}")
    else:
        st.error(detail)
