import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import AgentTask, Workspace, AuditLog
from ..deps import current_user
from ..services import agent as agent_svc
from ..services import tools as toolreg

router = APIRouter(prefix="/api/agents", tags=["agents"])

class RunIn(BaseModel):
    goal: str
    workspace_id: int | None = None
    role: str = "engineer"
    require_approval: bool = False

@router.post("/run")
def run(body: RunIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if body.role not in agent_svc.ROLES: raise HTTPException(400, f"unknown role; one of {list(agent_svc.ROLES)}")
    if body.workspace_id:
        w = db.get(Workspace, body.workspace_id)
        if not w: raise HTTPException(404, "workspace not found")
        from ..models import Project
        p = db.get(Project, w.project_id)
        if not p or p.user_id != user.id: raise HTTPException(404, "workspace not found")
    t = AgentTask(user_id=user.id, workspace_id=body.workspace_id, goal=body.goal.strip(),
                  role=body.role, require_approval=body.require_approval)
    db.add(t); db.commit(); db.refresh(t)
    db.add(AuditLog(user_id=user.id, action="agent.run", detail=f"role={body.role} goal={body.goal[:150]}")); db.commit()
    agent_svc.run_agent(t.id)
    return {"id": t.id, "status": t.status}

@router.get("")
def list_tasks(user=Depends(current_user), db: Session = Depends(get_db)):
    ts = db.query(AgentTask).filter_by(user_id=user.id).order_by(AgentTask.id.desc()).limit(50).all()
    return [{"id": t.id, "goal": t.goal[:120], "role": t.role, "status": t.status,
             "workspace_id": t.workspace_id, "result": (t.result or "")[:300]} for t in ts]

@router.get("/{tid}")
def get_task(tid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(AgentTask, tid)
    if not t or t.user_id != user.id: raise HTTPException(404, "task not found")
    return {"id": t.id, "goal": t.goal, "role": t.role, "status": t.status, "result": t.result,
            "events": t.events(), "pending_tool": json.loads(t.pending_tool) if t.pending_tool else None}

@router.post("/{tid}/cancel")
def cancel(tid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(AgentTask, tid)
    if not t or t.user_id != user.id: raise HTTPException(404, "task not found")
    if t.status in ("running", "awaiting_approval", "queued"):
        t.status = "cancelled"; t.append_event({"type": "cancelled"}); db.commit()
    return {"id": t.id, "status": t.status}

class ApprovalIn(BaseModel):
    approved: bool

@router.post("/{tid}/approve")
def approve(tid: int, body: ApprovalIn, user=Depends(current_user), db: Session = Depends(get_db)):
    t = db.get(AgentTask, tid)
    if not t or t.user_id != user.id: raise HTTPException(404, "task not found")
    if t.status != "awaiting_approval": raise HTTPException(400, f"task is {t.status}, not awaiting approval")
    pending = json.loads(t.pending_tool)
    pending["approved"] = body.approved
    t.pending_tool = json.dumps(pending)
    t.status = "running" if body.approved else "running"  # resolver thread reads pending_tool
    if not body.approved: t.status = "awaiting_approval"
    db.commit()
    return {"id": t.id, "status": t.status}

@router.get("/tools/catalog")
def catalog(user=Depends(current_user)):
    return [{"name": n, "description": d["description"], "permission": d["perm"], "schema": d["schema"]}
            for n, d in toolreg.REGISTRY.items()]
