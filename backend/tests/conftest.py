"""Test setup. Tests run against a real PostgreSQL database (never production).

Set TEST_DATABASE_URL to point at an empty throw-away database.
"""
import os

# These must be set BEFORE the app is imported, because config.py reads them at import time
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql://postgres@localhost:5433/stockpilot_test"
)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-chars-long"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def register(client, email="a@example.com", name="User A", password="password123"):
    response = client.post(
        "/auth/register", json={"email": email, "full_name": name, "password": password}
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}
