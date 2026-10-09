import shutil, time
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Project, Workspace, AuditLog
from ..deps import current_user, limiter
from ..config import CFG
from ..services import workspaces

router = APIRouter(prefix="/api", tags=["projects"])

def _own_project(db, user_id, project_id):
    p = db.get(Project, project_id)
    if not p or p.user_id != user_id:
        raise HTTPException(404, "project not found")
    return p

def _own_workspace(db, user_id, workspace_id):
    w = db.get(Workspace, workspace_id)
    if not w: raise HTTPException(404, "workspace not found")
    _own_project(db, user_id, w.project_id)
    return w

class ProjectIn(BaseModel):
    name: str
    description: str = ""

class WorkspaceIn(BaseModel):
    name: str
    image: str = "python:default"

@router.get("/projects")
def list_projects(user=Depends(current_user), db: Session = Depends(get_db)):
    ps = db.query(Project).filter_by(user_id=user.id).order_by(Project.id.desc()).all()
    out = []
    for p in ps:
        wss = db.query(Workspace).filter_by(project_id=p.id).all()
        out.append({"id": p.id, "name": p.name, "description": p.description,
                    "workspaces": [{"id": w.id, "name": w.name, "image": w.image} for w in wss]})
    return out

@router.post("/projects")
def create_project(body: ProjectIn, user=Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"user{user.id}")
    p = Project(user_id=user.id, name=body.name.strip()[:120], description=body.description[:2000])
    db.add(p); db.commit(); db.refresh(p)
    db.add(AuditLog(user_id=user.id, action="project.create", detail=p.name)); db.commit()
    return {"id": p.id, "name": p.name}

@router.delete("/projects/{pid}")
def delete_project(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_project(db, user.id, pid)
    for w in db.query(Workspace).filter_by(project_id=pid).all():
        shutil.rmtree(workspaces.ws_root(user.id, w.id), ignore_errors=True)
        db.delete(w)
    db.delete(db.get(Project, pid)); db.commit()
    return {"ok": True}

@router.post("/projects/{pid}/workspaces")
def create_workspace(pid: int, body: WorkspaceIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_project(db, user.id, pid)
    w = Workspace(project_id=pid, name=body.name.strip()[:120], image=body.image)
    db.add(w); db.commit(); db.refresh(w)
    workspaces.ensure_ws(user.id, w.id)
    return {"id": w.id, "name": w.name}

@router.get("/workspaces/{wid}/files")
def list_files(wid: int, path: str = ".", user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    root = workspaces.resolve_safe(user.id, wid, path)
    return {"path": path, "entries": workspaces.list_tree(root)[:2000]}

@router.get("/workspaces/{wid}/file")
def read_file(wid: int, path: str, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    p = workspaces.resolve_safe(user.id, wid, path)
    if not p.exists(): raise HTTPException(404, "file not found")
    if p.is_dir(): raise HTTPException(400, "path is a directory")
    if p.stat().st_size > 2_000_000: raise HTTPException(413, "file too large for editor (>2MB)")
    return {"path": path, "content": p.read_text(errors="replace")}

class WriteIn(BaseModel):
    path: str
    content: str

@router.put("/workspaces/{wid}/file")
def write_file(wid: int, body: WriteIn, user=Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"user{user.id}")
    _own_workspace(db, user.id, wid)
    p = workspaces.resolve_safe(user.id, wid, body.path)
    used = workspaces.ws_disk_usage(user.id, wid)
    if used + len(body.content.encode()) > CFG.WORKSPACE_QUOTA_MB * 1024 * 1024:
        raise HTTPException(507, "workspace disk quota exceeded")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body.content)
    return {"ok": True}

class RenameIn(BaseModel):
    from_path: str
    to_path: str

@router.post("/workspaces/{wid}/rename")
def rename(wid: int, body: RenameIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    src = workspaces.resolve_safe(user.id, wid, body.from_path)
    dst = workspaces.resolve_safe(user.id, wid, body.to_path)
    if not src.exists(): raise HTTPException(404, "source not found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"ok": True}

@router.delete("/workspaces/{wid}/file")
def delete_file(wid: int, path: str, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    p = workspaces.resolve_safe(user.id, wid, path)
    if p.is_dir(): shutil.rmtree(p)
    elif p.exists(): p.unlink()
    return {"ok": True}

@router.post("/workspaces/{wid}/upload")
def upload(wid: int, file: UploadFile = File(...), user=Depends(current_user), db: Session = Depends(get_db)):
    limiter.check(f"user{user.id}")
    _own_workspace(db, user.id, wid)
    max_bytes = CFG.UPLOAD_MAX_MB * 1024 * 1024
    used = workspaces.ws_disk_usage(user.id, wid)
    dest_dir = workspaces.ensure_ws(user.id, wid) / "uploads" / str(int(time.time()))
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (file.filename or "upload.bin").replace("/", "_")
    size = 0
    with open(dest, "wb") as out:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes: raise HTTPException(413, f"upload exceeds {CFG.UPLOAD_MAX_MB}MB limit")
            if used + size > CFG.WORKSPACE_QUOTA_MB * 1024 * 1024:
                raise HTTPException(507, "workspace disk quota exceeded")
            out.write(chunk)
    result = {"path": str(dest.relative_to(workspaces.ensure_ws(user.id, wid))), "size": size, "extracted": False}
    if dest.suffix.lower() == ".zip":
        try:
            extract_to = dest_dir / (dest.stem + "_extracted")
            workspaces.safe_extract_zip(dest, extract_to)
            result["extracted"] = True
            result["extract_path"] = str(extract_to.relative_to(workspaces.ensure_ws(user.id, wid)))
        except ValueError as e:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, str(e))
    db.add(AuditLog(user_id=user.id, action="upload", detail=result["path"])); db.commit()
    return result

@router.get("/workspaces/{wid}/download")
def download(wid: int, path: str, user=Depends(current_user), db: Session = Depends(get_db)):
    _own_workspace(db, user.id, wid)
    p = workspaces.resolve_safe(user.id, wid, path)
    if not p.exists(): raise HTTPException(404, "not found")
    if p.is_dir():
        import zipfile, tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in p.rglob("*"):
                if f.is_file() and "node_modules" not in f.parts and ".git" not in f.parts:
                    z.write(f, f.relative_to(p))
        tmp.close()
        return FileResponse(tmp.name, filename=p.name + ".zip", background=None)
    return FileResponse(p, filename=p.name)
