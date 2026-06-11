"""FastAPI application entry point.

Wires the routers. The database schema is managed by Alembic migrations
(`alembic -c cloud/alembic.ini upgrade head`) — both locally and in production —
so the app itself never creates tables. The Docker image runs the migration on
start before launching uvicorn.

Run locally:
    alembic -c cloud/alembic.ini upgrade head     # once / after schema changes
    uvicorn cloud.app.main:app --reload
Interactive docs at /docs.
"""

from __future__ import annotations

from fastapi import FastAPI

from .routers import auth, dashboard, health, ingest, users

app = FastAPI(title="VisionMetrics Cloud", version="0.1.0")

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
