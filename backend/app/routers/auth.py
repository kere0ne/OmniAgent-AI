from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, AuditLog
from ..security import hash_password, verify_password, make_token
from ..deps import current_user, limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

class Creds(BaseModel):
    username: str
    password: str

@router.post("/register")
def register(creds: Creds, db: Session = Depends(get_db)):
    if not creds.username.strip() or len(creds.password) < 8:
        raise HTTPException(400, "username required, password at least 8 characters")
    if db.query(User).filter_by(username=creds.username).first():
        raise HTTPException(409, "username already taken")
    u = User(username=creds.username.strip()[:64], pw_hash=hash_password(creds.password))
    db.add(u); db.commit(); db.refresh(u)
    db.add(AuditLog(user_id=u.id, action="register", detail=creds.username)); db.commit()
    return {"token": make_token(u.id), "username": u.username}

@router.post("/login")
def login(creds: Creds, db: Session = Depends(get_db)):
    limiter.check("login:" + creds.username)
    u = db.query(User).filter_by(username=creds.username).first()
    if not u or not verify_password(creds.password, u.pw_hash):
        raise HTTPException(401, "invalid username or password")
    db.add(AuditLog(user_id=u.id, action="login", detail="")); db.commit()
    return {"token": make_token(u.id), "username": u.username}

@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "tool_permissions": user.tool_permissions}
