"""Social media stats, optional Meta Graph API sync, and the community feed."""
import logging
import os
import threading
import time

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import SessionLocal, get_db
from model import SocialPost, SocialStat, User
from schemas import PostIn, PostOut, SocialStatIn, SocialStatOut

logger = logging.getLogger("soul.social")
router = APIRouter(prefix="/social", tags=["social"])
GRAPH = "https://graph.facebook.com/v19.0"


def _row(db: Session, platform: str) -> SocialStat:
    row = db.scalar(select(SocialStat).where(SocialStat.platform == platform))
    if row is None:
        row = SocialStat(platform=platform)
        db.add(row)
        db.flush()
    return row


@router.get("/stats", response_model=list[SocialStatOut])
def get_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> list[SocialStat]:
    """Stored Instagram/Facebook numbers."""
    return list(db.scalars(select(SocialStat).order_by(SocialStat.platform)))


@router.put("/stats", response_model=SocialStatOut)
def update_stats(body: SocialStatIn, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> SocialStat:
    """Update stored numbers for one platform (admin only)."""
    row = _row(db, body.platform)
    for field, value in body.model_dump(exclude={"platform"}, exclude_none=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


def sync_meta_stats(db: Session) -> dict:
    """Pull follower/like counts from the Meta Graph API (needs META_ACCESS_TOKEN). Returns what was updated."""
    token = os.getenv("META_ACCESS_TOKEN", "").strip()
    if not token:
        return {"synced": False, "reason": "META_ACCESS_TOKEN is not set; using stored values."}
    updated: dict[str, str] = {}
    page_id, ig_id = os.getenv("META_FACEBOOK_PAGE_ID", "").strip(), os.getenv("META_INSTAGRAM_USER_ID", "").strip()
    try:
        if page_id:
            r = requests.get(f"{GRAPH}/{page_id}", params={"fields": "fan_count", "access_token": token}, timeout=15)
            r.raise_for_status()
            likes = int(r.json().get("fan_count", 0))
            row = _row(db, "facebook")
            row.likes_delta, row.likes = likes - row.likes, likes
            updated["facebook"] = "ok"
        if ig_id:
            r = requests.get(f"{GRAPH}/{ig_id}", params={"fields": "followers_count,media_count", "access_token": token},
                             timeout=15)
            r.raise_for_status()
            followers = int(r.json().get("followers_count", 0))
            row = _row(db, "instagram")
            row.followers_delta, row.followers = followers - row.followers, followers
            updated["instagram"] = "ok"
        db.commit()
    except (requests.RequestException, ValueError) as exc:
        db.rollback()
        logger.warning("Meta sync failed: %s", exc)
        return {"synced": False, "reason": f"Meta API error: {exc}"}
    if not updated:
        return {"synced": False, "reason": "Set META_FACEBOOK_PAGE_ID and/or META_INSTAGRAM_USER_ID in .env."}
    return {"synced": True, "updated": updated}


def start_meta_sync_thread() -> None:
    """Start the optional background sync (only when META_ACCESS_TOKEN is set)."""
    if not os.getenv("META_ACCESS_TOKEN", "").strip():
        return
    minutes = max(int(os.getenv("META_SYNC_MINUTES", "60")), 5)

    def loop() -> None:
        while True:
            with SessionLocal() as db:
                logger.info("Meta sync: %s", sync_meta_stats(db))
            time.sleep(minutes * 60)

    threading.Thread(target=loop, daemon=True, name="meta-sync").start()
    logger.info("Meta sync job started (every %s min)", minutes)


@router.post("/sync")
def sync_now(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> dict:
    """Run the Meta sync once (admin only)."""
    return sync_meta_stats(db)


@router.get("/posts", response_model=list[PostOut])
def list_posts(limit: int = 50, db: Session = Depends(get_db)) -> list[PostOut]:
    """Community feed (public)."""
    rows = db.execute(select(SocialPost, User.name).join(User, User.id == SocialPost.user_id)
                      .order_by(SocialPost.created_at.desc(), SocialPost.id.desc()).limit(min(max(limit, 1), 200))).all()
    return [PostOut(id=p.id, author=name, content=p.content, created_at=p.created_at) for p, name in rows]


@router.post("/posts", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(body: PostIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> PostOut:
    """Publish a post to the community feed (logged-in users)."""
    content = body.content.strip()
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Post cannot be empty")
    post = SocialPost(user_id=user.id, content=content)
    db.add(post)
    db.commit()
    return PostOut(id=post.id, author=user.name, content=post.content, created_at=post.created_at)
