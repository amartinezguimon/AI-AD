"""Test harness: a fresh in-memory SQLite DB per test, wired into the app.

No Docker, no Postgres needed to run the suite — the same models work on SQLite.
Each test gets an isolated database and a FastAPI TestClient whose get_session
dependency is overridden to use it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cloud.app.db import Base, get_session
from cloud.app.main import app


@pytest.fixture()
def db_session():
    # One shared in-memory DB for the test (StaticPool keeps it alive across connections).
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
