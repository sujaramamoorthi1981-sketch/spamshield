import os

os.environ["DATABASE_URL"] = "sqlite:///./spamtest.db"

import pytest
from fastapi.testclient import TestClient

from app.database.session import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    r = client.post("/api/auth/register", json={"name": "Test", "email": "t@example.com", "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['data']['token']}"}
