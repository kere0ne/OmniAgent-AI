import time, threading
from app.db import SessionLocal
from app.models import AgentTask

def _mk_wid(client, auth):
    pid = client.post("/api/projects", json={"name": f"a{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    return client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]

def _uid(auth):
    from app.security import verify_token
    return verify_token(auth["Authorization"].split()[1])

def test_agent_mock_writes_file(client, auth):
    from app.services import agent as agent_svc
    wid = _mk_wid(client, auth)
    script = [
        {"tool": "write_file", "args": {"path": "calc.py", "content": "def add(a, b):\n    return a + b\n"}},
        {"tool": "run_command", "args": {"command": "python3 -c 'import calc; print(calc.add(2,3))'"}},
        {"tool": "finish", "args": {"summary": "Wrote calc.py with add(); verified 2+3=5 by running it.", "unfinished": ""}},
    ]
    db = SessionLocal()
    t = AgentTask(user_id=_uid(auth), workspace_id=wid, goal="create calc.py and verify add works", role="engineer")
    db.add(t); db.commit(); tid = t.id; db.close()
    th = threading.Thread(target=agent_svc._run, args=(tid, script), daemon=True)
    th.start(); th.join(timeout=30)
    task = client.get(f"/api/agents/{tid}", headers=auth).json()
    assert task["status"] == "complete", task
    assert any(e["type"] == "tool" and e["tool"] == "write_file" for e in task["events"])
    f = client.get(f"/api/workspaces/{wid}/file", params={"path": "calc.py"}, headers=auth).json()
    assert "def add" in f["content"]
    tool_events = [e for e in task["events"] if e["type"] == "tool" and e["tool"] == "run_command"]
    assert tool_events and "5" in tool_events[0]["result"].get("stdout", "")

def test_agent_no_model_fails_usefully(client, auth):
    pid = client.post("/api/projects", json={"name": f"a{time.time_ns()%10**9}"}, headers=auth).json()["id"]
    wid = client.post(f"/api/projects/{pid}/workspaces", json={"name": "main"}, headers=auth).json()["id"]
    r = client.post("/api/agents/run", json={"goal": "do something"}, headers=auth)
    assert r.status_code == 200
    tid = r.json()["id"]
    task = {}
    for _ in range(25):
        task = client.get(f"/api/agents/{tid}", headers=auth).json()
        if task["status"] == "failed": break
        time.sleep(0.2)
    assert task["status"] == "failed"
    assert "No AI model configured" in task["result"]

def test_agent_cancel(client, auth):
    from app.services import agent as agent_svc
    wid = _mk_wid(client, auth)
    db = SessionLocal()
    t = AgentTask(user_id=_uid(auth), workspace_id=wid, goal="x", role="engineer", status="running")
    db.add(t); db.commit(); tid = t.id; db.close()
    r = client.post(f"/api/agents/{tid}/cancel", headers=auth)
    assert r.json()["status"] == "cancelled"
    # another user cannot touch it
    other = {"Authorization": "Bearer " + client.post("/api/auth/register", json={"username": f"c{time.time_ns()%10**9}", "password": "longpassword1"}).json()["token"]}
    assert client.get(f"/api/agents/{tid}", headers=other).status_code == 404

def test_tool_catalog(client, auth):
    tools = client.get("/api/agents/tools/catalog", headers=auth).json()
    names = {t["name"] for t in tools}
    assert {"list_files", "read_file", "write_file", "run_command", "search_files", "finish"} <= names
