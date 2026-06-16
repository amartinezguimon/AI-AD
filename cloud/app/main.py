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
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import admin, auth, dashboard, health, ingest, users

app = FastAPI(title="VisionMetrics Cloud", version="0.1.0")

# The dashboard SPA calls this API from the browser. Auth is a Bearer token (not
# cookies), so allowing all origins is safe; lock it down in prod via VM_CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(admin.router)
