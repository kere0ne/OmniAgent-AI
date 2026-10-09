import time
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .db import get_db
from .models import User
from .security import verify_token
from .config import CFG

def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    uid = verify_token(auth[7:])
    if not uid:
        raise HTTPException(401, "invalid or expired token")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "user not found")
    return user

class RateLimiter:
    def __init__(self): self.hits = {}
    def check(self, key: str):
        now = time.time()
        window = self.hits.get(key, [])
        window = [t for t in window if now - t < 60]
        if len(window) >= CFG.RATE_LIMIT_PER_MIN:
            raise HTTPException(429, "rate limit exceeded, slow down")
        window.append(now); self.hits[key] = window

limiter = RateLimiter()
