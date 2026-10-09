import os, sys, tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="omni-test-")
os.environ["OMNI_DATA_DIR"] = _tmp
os.environ["OMNI_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import init_db

@pytest.fixture(scope="session")
def client():
    init_db()
    with TestClient(app) as c:
        yield c

@pytest.fixture()
def auth(client):
    uname = f"tester{int(__import__('time').time()*1000)%10_000_000}"
    r = client.post("/api/auth/register", json={"username": uname, "password": "test-password-1"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}
