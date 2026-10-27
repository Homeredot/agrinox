import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["GEMINI_API_KEY"] = ""
os.environ["PLANET_CLIENT_ID"] = ""
os.environ["PLANET_CLIENT_SECRET"] = ""
os.environ["EMAIL_ENABLED"] = "false"
os.environ["EMAIL_VERIFICATION_REQUIRED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.models import Cell, District, Province, Sector, Village
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal.begin() as db:
        db.add(Province(code=4, name="NORTH"))
        db.flush()
        db.add(District(code=403, province_code=4, name="Musanze"))
        db.flush()
        db.add(Sector(code="040310", district_code=403, name="Muhoza"))
        db.flush()
        db.add(Cell(code=4031001, sector_code="040310", name="Ruhengeri"))
        db.flush()
        db.add(Village(code=403100101, cell_code=4031001, name="User confirmed"))
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()
    TEST_DB.unlink(missing_ok=True)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth(client):
    response = client.post("/api/v1/auth/register", json={"email": "farmer@example.com", "full_name": "Test Farmer", "password": "securepass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

