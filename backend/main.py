"""FastAPI application: CORS, startup (DB check, create_all, seed), routers and /health."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")

import model  # noqa: E402,F401  (registers tables)
from database import Base, SessionLocal, check_connection, engine  # noqa: E402
from route import auth_routes, dashboard_routes, data_routes, social_routes, survey_routes  # noqa: E402
from seed import run_seed  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect, create tables, seed, start optional Meta sync."""
    check_connection()
    Base.metadata.create_all(bind=engine)
    print("Tables ready (create_all).", flush=True)
    run_seed()
    social_routes.start_meta_sync_thread()
    yield


app = FastAPI(title="Soul Sanctuary API", version="1.0.0", lifespan=lifespan)

_cors_env = os.getenv("CORS_ORIGINS", "").strip()
if not _cors_env or _cors_env == "*":
    # Production: allow all origins (Streamlit Cloud uses varying subdomains)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    _origins = []
    for _o in _cors_env.split(","):
        _o = _o.strip().rstrip("/")
        if _o and "://" not in _o:
            _scheme = "http" if _o.startswith(("localhost", "127.0.0.1")) else "https"
            _o = f"{_scheme}://{_o}"
        if _o:
            _origins.append(_o)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

for r in (auth_routes.router, survey_routes.router, dashboard_routes.router, data_routes.router, social_routes.router):
    app.include_router(r)


@app.get("/", tags=["system"])
def root() -> dict:
    """Root / status endpoint."""
    return {"title": "Soul Sanctuary API", "status": "online", "docs": "/docs"}


@app.get("/health", tags=["system"])
def health() -> dict:
    """Liveness + database check."""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
