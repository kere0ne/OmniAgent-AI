import threading, time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
import httpx
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Workspace, AuditLog
from ..deps import current_user
from ..services import workspaces
from ..services.executor import run

router = APIRouter(prefix="/api/workspaces/{wid}/preview", tags=["preview"])

# in-memory registry: workspace_id -> {"proc", "port", "cmd", "started"}
SERVERS: dict[int, dict] = {}

def _own(db, user_id, wid):
    w = db.get(Workspace, wid)
    if not w: raise HTTPException(404, "workspace not found")
    from ..models import Project
    p = db.get(Project, w.project_id)
    if not p or p.user_id != user_id: raise HTTPException(404, "workspace not found")
    return workspaces.ensure_ws(user_id, wid)

@router.post("/start")
def start(wid: int, body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    root = _own(db, user.id, wid)
    cmd = (body.get("command") or "").strip()
    port = int(body.get("port") or 0)
    if not cmd: raise HTTPException(400, "command required, e.g. 'python3 -m http.server 8080'")
    if not (1024 <= port <= 65535): raise HTTPException(400, "port must be 1024-65535")
    stop(wid, user, db, silent=True)
    proc_holder = {}

    def spawn():
        import subprocess, os, resource
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(root), "PYTHONUNBUFFERED": "1"}
        def limits():
            mem = 512 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
            os.setsid()
        proc_holder["p"] = subprocess.Popen(["/bin/bash", "-c", cmd], cwd=str(root), env=env,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            preexec_fn=limits, start_new_session=True)
    spawn()
    time.sleep(1.5)
    if proc_holder.get("p") and proc_holder["p"].poll() is None:
        SERVERS[wid] = {"p": proc_holder["p"], "port": port, "cmd": cmd, "started": time.time()}
        db.add(AuditLog(user_id=user.id, action="preview.start", detail=f"{cmd} :{port}")); db.commit()
        return {"ok": True, "url": f"/api/workspaces/{wid}/preview/", "command": cmd}
    return {"ok": False, "error": "server exited immediately; check the command and its logs"}

@router.post("/stop")
def stop(wid: int, user=Depends(current_user), db: Session = Depends(get_db), silent: bool = False):
    s = SERVERS.pop(wid, None)
    if s:
        try:
            import os, signal
            os.killpg(os.getpgid(s["p"].pid), signal.SIGKILL)
        except Exception:
            try: s["p"].kill()
            except Exception: pass
        if not silent:
            db.add(AuditLog(user_id=user.id, action="preview.stop", detail="")); db.commit()
    return {"ok": True, "was_running": bool(s)}

@router.get("/status")
def status(wid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = SERVERS.get(wid)
    if not s: return {"running": False}
    alive = s["p"].poll() is None
    return {"running": alive, "command": s["cmd"], "port": s["port"], "started": s["started"]}

@router.get("/{path:path}")
def proxy(wid: int, path: str, request: Request, user=Depends(current_user), db: Session = Depends(get_db)):
    _own(db, user.id, wid)
    s = SERVERS.get(wid)
    if not s or s["p"].poll() is not None:
        raise HTTPException(404, "no preview server running for this workspace; start one first")
    url = f"http://127.0.0.1:{s['port']}/{path}"
    if request.url.query: url += "?" + request.url.query
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(url, headers={k: v for k, v in request.headers.items() if k.lower() in ("accept", "user-agent", "accept-language")})
        excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
        headers = {k: v for k, v in r.headers.items() if k.lower() not in excluded}
        return Response(content=r.content, status_code=r.status_code, headers=headers, media_type=r.headers.get("content-type"))
    except httpx.HTTPError:
        raise HTTPException(502, "preview server did not respond")
