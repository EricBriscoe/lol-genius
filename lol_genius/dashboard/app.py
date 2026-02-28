from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lol_genius.db.queries import MatchDB

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    dsn = os.environ.get(
        "DATABASE_URL",
        "postgresql://lol_genius:lol_genius_dev@localhost:5432/lol_genius",
    )
    proxy_url = os.environ.get("PROXY_URL", "http://localhost:8080")
    model_dir = os.environ.get("MODEL_DIR", "data/models")
    ddragon_cache = os.environ.get("DDRAGON_CACHE", "data/ddragon")

    db = MatchDB(dsn)
    app.state.db = db
    app.state.dsn = dsn
    app.state.proxy_url = proxy_url
    app.state.model_dir = model_dir
    app.state.ddragon_cache = ddragon_cache

    log.info(f"Dashboard API started: db connected, proxy={proxy_url}")
    yield
    db.close()
    log.info("Dashboard API shut down")


app = FastAPI(title="lol-genius dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from lol_genius.dashboard.api import router  # noqa: E402

app.include_router(router, prefix="/api/v1")
