import zipfile, io, time

def _mk_project(client, auth, name=None):
    name = name or f"proj{time.time_ns()%10**9}"
    r = client.post("/api/projects", json={"name": name}, headers=auth)
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth)
    return pid, r.json()["id"]

def test_project_isolation(client):
    ua = f"iso_a{time.time_ns()%10**9}"; ub = f"iso_b{time.time_ns()%10**9}"
    ha = {"Authorization": "Bearer " + client.post("/api/auth/register", json={"username": ua, "password": "longpassword1"}).json()["token"]}
    hb = {"Authorization": "Bearer " + client.post("/api/auth/register", json={"username": ub, "password": "longpassword1"}).json()["token"]}
    pid, wid = _mk_project(client, ha)
    client.put(f"/api/workspaces/{wid}/file", json={"path": "secret.txt", "content": "user a data"}, headers=ha)
    # user b cannot read user a's workspace or list it
    assert client.get(f"/api/workspaces/{wid}/file", params={"path": "secret.txt"}, headers=hb).status_code == 404
    assert client.get(f"/api/workspaces/{wid}/files", headers=hb).status_code == 404
    assert client.post(f"/api/workspaces/{wid}/exec", json={"command": "ls"}, headers=hb).status_code == 404
    # anon cannot either
    assert client.get(f"/api/workspaces/{wid}/files").status_code == 401

def test_crud_and_files(client, auth):
    pid, wid = _mk_project(client, auth)
    assert client.get("/api/projects", headers=auth).json()[0]["id"] == pid
    r = client.put(f"/api/workspaces/{wid}/file", json={"path": "src/app.py", "content": "print('hi')\n"}, headers=auth)
    assert r.status_code == 200
    r = client.get(f"/api/workspaces/{wid}/file", params={"path": "src/app.py"}, headers=auth)
    assert r.json()["content"] == "print('hi')\n"
    files = client.get(f"/api/workspaces/{wid}/files", headers=auth).json()["entries"]
    assert {"path": "src/app.py", "type": "file"} in [{**e, **{}} for e in files] or any(f["path"] == "src/app.py" for f in files)
    # rename + delete
    assert client.post(f"/api/workspaces/{wid}/rename", json={"from_path": "src/app.py", "to_path": "src/main.py"}, headers=auth).status_code == 200
    assert client.delete(f"/api/workspaces/{wid}/file", params={"path": "src/main.py"}, headers=auth).status_code == 200

def test_path_traversal_blocked(client, auth):
    pid, wid = _mk_project(client, auth)
    for evil in ["../../etc/passwd", "/etc/passwd", "a/../../b", "..%2f"]:
        r = client.get(f"/api/workspaces/{wid}/file", params={"path": evil}, headers=auth)
        assert r.status_code in (400, 404), (evil, r.status_code)

def test_zip_upload_extract(client, auth):
    pid, wid = _mk_project(client, auth)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("proj/main.py", "x = 1\n")
        z.writestr("proj/README.md", "hi\n")
    r = client.post(f"/api/workspaces/{wid}/upload", files={"file": ("proj.zip", buf.getvalue(), "application/zip")}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["extracted"] is True

def test_zip_traversal_rejected(client, auth):
    pid, wid = _mk_project(client, auth)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../evil.txt", "boom")
    r = client.post(f"/api/workspaces/{wid}/upload", files={"file": ("evil.zip", buf.getvalue(), "application/zip")}, headers=auth)
    assert r.status_code == 400
