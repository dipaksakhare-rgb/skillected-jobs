"""Shared fixtures: isolated temp DB per session, app client, seeded demo data."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

_TMP = tempfile.mkdtemp(prefix="skillected-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["APP_SECRET"] = "test-secret"
os.environ["APP_ENV"] = "test"


@pytest.fixture(scope="session", autouse=True)
def _database():
    from scripts.apply_migrations import main as apply_migrations
    from app.db import seed_demo_data
    apply_migrations()
    seed_demo_data.seed()
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The limiter is process-global; tests share it across app instances."""
    from app.core.security import limiter
    limiter._hits.clear()
    yield
    limiter._hits.clear()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app import create_app
    return TestClient(create_app())


@pytest.fixture()
def admin_client(client):
    resp = client.post("/admin/login", data={
        "email": "admin@skillected.local", "password": "ChangeMe!Admin1"},
        follow_redirects=False)
    assert resp.status_code == 303, resp.text
    return client


@pytest.fixture()
def db_session():
    """Marker fixture: services tests just need the seeded session DB."""
    yield


@pytest.fixture()
def db_with_courses(db_session):
    from app.repositories import courses_repo
    courses_repo.ensure_courses()
    yield
