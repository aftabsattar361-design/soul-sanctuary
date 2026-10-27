"""Database engine, session factory and startup connection check."""
import logging
import os
from pathlib import Path
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

logger = logging.getLogger("soul.db")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env (project root) and set "
        "DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/DBNAME"
    )
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base class for all models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _hint_for(error_text: str) -> str:
    low = error_text.lower()
    if "password authentication failed" in low:
        return "Wrong username/password. Check DATABASE_URL in .env against your pgAdmin server login."
    if "does not exist" in low and "database" in low:
        return "The database in DATABASE_URL does not exist. Create it in pgAdmin (Servers > Databases > Create) or use 'postgres'."
    if "connection refused" in low or "could not connect" in low or "timeout" in low:
        return "PostgreSQL is not reachable. Start the PostgreSQL service and confirm host/port (default localhost:5432)."
    return "Check DATABASE_URL in .env and that PostgreSQL is running."


def check_connection() -> None:
    """Test the connection; log 'Database connected' or a readable error with a fix hint."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError as exc:
        reason = str(getattr(exc, "orig", exc)).strip().splitlines()[0]
        msg = f"Database connection FAILED: {reason}\n  Fix: {_hint_for(str(exc))}"
        logger.error(msg)
        print(msg, flush=True)
        raise RuntimeError(msg) from exc
    logger.info("Database connected")
    print("Database connected", flush=True)
