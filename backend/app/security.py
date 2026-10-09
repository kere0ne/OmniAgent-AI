import base64, hashlib, hmac, json, os, time
from .config import CFG

def hash_password(pw: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + dk.hex()

def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, dk_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(dk.hex(), dk_hex)
    except Exception:
        return False

def _sig(b: bytes) -> str:
    return hmac.new(CFG.SECRET_KEY.encode(), b, hashlib.sha256).hexdigest()

def make_token(user_id: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"u": user_id, "exp": time.time() + CFG.TOKEN_TTL_HOURS * 3600}).encode()).decode()
    return payload + "." + _sig(payload.encode())

def verify_token(token: str):
    try:
        payload, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(_sig(payload.encode()), sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode()))
        if data.get("exp", 0) < time.time():
            return None
        return int(data["u"])
    except Exception:
        return None
