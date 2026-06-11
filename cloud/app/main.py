"""FastAPI application entry point.

Wires the routers and (in development) creates tables on startup so the app runs
with zero setup. In production, schema changes go through Alembic migrations
(added before deploy) rather than create_all — but create_all is a safe no-op
when the tables already exist.

Run locally:
    uvicorn cloud.app.main:app --reload
Interactive docs at /docs.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .routers import auth, dashboard, health, ingest, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: ensure tables exist. Harmless if they already do.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VisionMetrics Cloud", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
