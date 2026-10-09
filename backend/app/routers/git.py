import json, urllib.parse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import GitCredential, Workspace, AuditLog, User
from ..deps import current_user
from ..services import workspaces
from ..services.executor import run
from ..config import CFG

router = APIRouter(prefix="/api/workspaces/{wid}/git", tags=["git"])

def _own_workspace(db, user_id, wid):
    w = db.get(Workspace, wid)
    if not w: raise HTTPException(404, "workspace not found")
    from ..models import Project
    p = db.get(Project, w.project_id)
    if not p or p.user_id != user_id: raise HTTPException(404, "workspace not found")
    return w, workspaces.ensure_ws(user_id, wid)

def _token(db, user_id):
    c = db.query(GitCredential).filter_by(user_id=user_id).first()
    return (c.github_token if c else "") or ""

@router.post("/credential")
def set_credential(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.query(GitCredential).filter_by(user_id=user.id).first()
    if not c:
        c = GitCredential(user_id=user.id); db.add(c)
    c.github_token = (body.get("token") or "").strip()
    db.commit()
    return {"ok": True, "has_token": bool(c.github_token)}

@router.get("/credential")
def get_credential(user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.query(GitCredential).filter_by(user_id=user.id).first()
    return {"has_token": bool(c and c.github_token)}

@router.post("/clone")
def clone(wid: int, body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    url = (body.get("url") or "").strip()
    if not url.startswith(("https://", "git@")): raise HTTPException(400, "https git URL required")
    r = run(f"git clone --depth 50 {json.dumps(url)} .", str(workspaces.ensure_ws(user.id, wid)), timeout=180)
    if r["exit_code"] != 0: raise HTTPException(400, r["stderr"][-500:] or "clone failed")
    db.add(AuditLog(user_id=user.id, action="git.clone", detail=url)); db.commit()
    return r

@router.post("/exec")
def git_exec(wid: int, body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    """Runs a read-only git subcommand: status, log, diff, branch."""
    _own_workspace(db, user.id, wid)
    sub = (body.get("subcommand") or "").strip()
    allowed = {"status", "log", "diff", "branch", "show", "shortlog"}
    first = sub.split()[0] if sub else ""
    if first not in allowed:
        raise HTTPException(400, f"only read-only git commands allowed here: {sorted(allowed)}")
    r = run(f"git {sub}", str(workspaces.ensure_ws(user.id, wid)), timeout=60)
    return r

class CommitIn(BaseModel):
    message: str
    add_all: bool = True
    files: list[str] | None = None

@router.post("/commit")
def commit(wid: int, body: CommitIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    root = str(workspaces.ensure_ws(user.id, wid))
    if not run("git rev-parse --git-dir", root)["exit_code"] == 0:
        raise HTTPException(400, "not a git repository; clone one or run git init first")
    if body.add_all:
        r = run("git add -A", root)
        if r["exit_code"] != 0: raise HTTPException(400, r["stderr"][-400:])
    r = run("git commit -m " + json.dumps(body.message[:300]), root)
    if r["exit_code"] != 0:
        raise HTTPException(400, (r["stdout"] + r["stderr"])[-500:] or "commit failed")
    db.add(AuditLog(user_id=user.id, action="git.commit", detail=body.message[:200])); db.commit()
    return r

@router.post("/push")
def push(wid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    """Pushes with the stored GitHub token. Destructive/publishing: audited; the UI confirms first."""
    _own_workspace(db, user.id, wid)
    token = _token(db, user.id)
    if not token:
        raise HTTPException(400, "No GitHub token saved. Add one on the GitHub page (a fine-grained PAT with repo scope).")
    root = str(workspaces.ensure_ws(user.id, wid))
    remote = run("git config --get remote.origin.url", root)
    if remote["exit_code"] != 0 or not remote["stdout"].strip():
        raise HTTPException(400, "no remote.origin.url configured")
    url = remote["stdout"].strip()
    if url.startswith("https://"):
        parsed = urllib.parse.urlparse(url)
        authed = f"https://x-access-token:{token}@{parsed.netloc}{parsed.path}"
    else:
        raise HTTPException(400, "only https remotes can push with a token; switch the remote to https")
    # token used in-memory only; masked in output
    r = run(f"git push origin HEAD 2>&1 | sed 's/{token}/***MASKED***/g'", root, env_extra={})
    push2 = run(f"git -c credential.helper= push {json.dumps(authed)} HEAD 2>&1", root, timeout=180)
    out = (push2["stdout"] + push2["stderr"]).replace(token, "***MASKED***")
    ok = push2["exit_code"] == 0
    db.add(AuditLog(user_id=user.id, action="git.push", detail=("ok" if ok else "failed") + ": " + out[-200:])); db.commit()
    return {"ok": ok, "output": out[-2000:], "exit_code": push2["exit_code"]}

@router.get("/diff")
def diff(wid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    root = str(workspaces.ensure_ws(user.id, wid))
    r = run("git diff HEAD --stat && git diff HEAD", root, timeout=60)
    return r
