import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from ..db import get_db, SessionLocal
from ..models import Workspace, AuditLog, User
from ..services import workspaces
from ..services.executor import ShellSession
from ..deps import current_user
from ..config import CFG

router = APIRouter(prefix="/api", tags=["terminal"])

SESSIONS: dict[str, ShellSession] = {}

def _own_workspace(db, user_id, wid):
    w = db.get(Workspace, wid)
    if not w: raise HTTPException(404, "workspace not found")
    from ..models import Project
    p = db.get(Project, w.project_id)
    if not p or p.user_id != user_id: raise HTTPException(404, "workspace not found")
    return w

class ExecIn(dict): pass

@router.post("/workspaces/{wid}/exec")
def exec_command(wid: int, body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    cmd = (body or {}).get("command", "")
    if not cmd.strip(): raise HTTPException(400, "command required")
    timeout = min(int((body or {}).get("timeout", CFG.EXEC_TIMEOUT_DEFAULT)), CFG.EXEC_TIMEOUT_MAX)
    root = workspaces.ensure_ws(user.id, wid)
    from ..services.executor import run
    r = run(cmd, str(root), timeout=timeout, cpu=CFG.EXEC_CPU_SECONDS, mem_mb=CFG.EXEC_MEM_MB)
    db.add(AuditLog(user_id=user.id, action="exec", detail=cmd[:200])); db.commit()
    return r

@router.post("/workspaces/{wid}/terminal/open")
def open_session(wid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    root = workspaces.ensure_ws(user.id, wid)
    sid = uuid.uuid4().hex
    SESSIONS[sid] = ShellSession(str(root), cpu=CFG.EXEC_CPU_SECONDS, mem_mb=CFG.EXEC_MEM_MB)
    return {"session_id": sid}

@router.websocket("/ws/terminal/{sid}")
async def ws_terminal(ws: WebSocket, sid: str, token: str = ""):
    await ws.accept()
    from ..security import verify_token
    if not verify_token(token):
        await ws.send_json({"type": "error", "message": "unauthorized"})
        await ws.close(); return
    sess = SESSIONS.get(sid)
    if not sess:
        await ws.send_json({"type": "error", "message": "unknown or expired session"})
        await ws.close(); return
    await ws.send_json({"type": "ready", "cwd": sess.cwd})
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("action") == "close": break
            cmd = msg.get("command", "")
            r = sess.run(cmd, timeout=int(msg.get("timeout", 120)))
            await ws.send_json({"type": "output", "output": r.get("output", "")})
            await ws.send_json({"type": "exit", "exit_code": r.get("exit_code"), "timed_out": r.get("timed_out", False)})
            if r.get("dead"):
                await ws.send_json({"type": "error", "message": "shell died; open a new session"})
                break
    except WebSocketDisconnect:
        pass
    finally:
        sess.kill(); SESSIONS.pop(sid, None)
