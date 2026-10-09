def test_real_command_execution(client, auth):
    import time
    pid = client.post("/api/projects", json={"name": f"e{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    wid = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]
    client.put(f"/api/workspaces/{wid}/file", json={"path": "hello.py", "content": "print('real output')\n"}, headers=auth)
    r = client.post(f"/api/workspaces/{wid}/exec", json={"command": "python3 hello.py"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exit_code"] == 0 and "real output" in body["stdout"]

def test_exit_codes_and_stderr(client, auth):
    import time
    pid = client.post("/api/projects", json={"name": f"e{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    wid = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]
    r = client.post(f"/api/workspaces/{wid}/exec", json={"command": "ls /definitely/not/here"}, headers=auth).json()
    assert r["exit_code"] != 0 and "stderr" in r
    r = client.post(f"/api/workspaces/{wid}/exec", json={"command": "exit 3"}, headers=auth).json()
    assert r["exit_code"] == 3

def test_dangerous_binaries_blocked(client, auth):
    import time
    pid = client.post("/api/projects", json={"name": f"e{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    wid = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]
    r = client.post(f"/api/workspaces/{wid}/exec", json={"command": "sudo rm -rf /"}, headers=auth).json()
    assert r["exit_code"] == 126 and "blocked" in r["stderr"]

def test_exec_isolation_no_server_env(client, auth):
    import time
    pid = client.post("/api/projects", json={"name": f"e{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    wid = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]
    r = client.post(f"/api/workspaces/{wid}/exec", json={"command": "echo ${OMNI_SECRET_KEY} ${HOME}"}, headers=auth).json()
    assert "dev-secret-change-me" not in r["stdout"]
