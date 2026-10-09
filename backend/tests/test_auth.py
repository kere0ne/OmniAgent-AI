import time
from tests.conftest import *

def test_register_login_me(client):
    uname = f"u{time.time_ns()%10**9}"
    r = client.post("/api/auth/register", json={"username": uname, "password": "longpassword1"})
    assert r.status_code == 200
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).json()["username"] == uname
    assert client.post("/api/auth/login", json={"username": uname, "password": "longpassword1"}).status_code == 200
    assert client.post("/api/auth/login", json={"username": uname, "password": "wrongpass99"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401

def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"username": "x", "password": "short"})
    assert r.status_code == 400
