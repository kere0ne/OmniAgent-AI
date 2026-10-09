import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import ModelProvider, User, AuditLog
from ..deps import current_user
from ..services.providers import build, ProviderError

router = APIRouter(prefix="/api/models", tags=["models"])

class ProviderIn(BaseModel):
    name: str
    kind: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""
    default_model: str = ""
    settings: dict = {}
    is_default: bool = False

def _own(db, user_id, pid):
    p = db.get(ModelProvider, pid)
    if not p or p.user_id != user_id: raise HTTPException(404, "provider not found")
    return p

@router.get("")
def list_providers(user=Depends(current_user), db: Session = Depends(get_db)):
    ps = db.query(ModelProvider).filter_by(user_id=user.id).all()
    return [{"id": p.id, "name": p.name, "kind": p.kind, "base_url": p.base_url,
             "default_model": p.default_model, "is_default": p.is_default,
             "settings": json.loads(p.settings or "{}"), "has_api_key": bool(p.api_key)} for p in ps]

@router.post("")
def create_provider(body: ProviderIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if body.kind not in ("openai_compatible", "ollama", "mock"):
        raise HTTPException(400, "kind must be openai_compatible, ollama, or mock")
    if body.kind == "openai_compatible" and not body.base_url.strip():
        raise HTTPException(400, "base_url is required for openai_compatible providers (e.g. http://localhost:11434/v1 for Ollama)")
    p = ModelProvider(user_id=user.id, name=body.name.strip()[:80], kind=body.kind,
                      base_url=body.base_url.strip(), api_key=body.api_key.strip(),
                      default_model=body.default_model.strip(),
                      settings=json.dumps(body.settings or {"temperature": 0.2, "max_tokens": 2048}))
    if body.is_default:
        for q in db.query(ModelProvider).filter_by(user_id=user.id): q.is_default = False
        p.is_default = True
    elif not db.query(ModelProvider).filter_by(user_id=user.id).first():
        p.is_default = True
    db.add(p); db.commit(); db.refresh(p)
    db.add(AuditLog(user_id=user.id, action="model.provider.create", detail=f"{p.kind}:{p.name}")); db.commit()
    return {"id": p.id, "name": p.name}

@router.delete("/{pid}")
def delete_provider(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _own(db, user.id, pid); db.delete(p); db.commit()
    return {"ok": True}

@router.post("/{pid}/set-default")
def set_default(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _own(db, user.id, pid)
    for q in db.query(ModelProvider).filter_by(user_id=user.id): q.is_default = False
    p.is_default = True; db.commit()
    return {"ok": True}

@router.post("/{pid}/test")
async def test_provider(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _own(db, user.id, pid)
    try:
        prov = build(p.kind, p.base_url, p.api_key)
        return await prov.test_connection()
    except ProviderError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"connection failed: {e}"}

@router.post("/test-connection")
async def test_connection(body: ProviderIn, user=Depends(current_user)):
    """Test settings before saving."""
    try:
        prov = build(body.kind, body.base_url, body.api_key)
        return await prov.test_connection()
    except ProviderError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": f"connection failed: {e}"}
