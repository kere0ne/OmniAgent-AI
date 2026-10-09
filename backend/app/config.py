import os, secrets
from pathlib import Path

_DATA_DEFAULT = Path.home() / ".omniagent" / "data"

class Config:
    APP_NAME = "OmniAgent AI"
    VERSION = "0.1.0"
    SECRET_KEY = os.environ.get("OMNI_SECRET_KEY", "dev-secret-change-me-in-production")
    DATABASE_URL = os.environ.get("OMNI_DATABASE_URL", "sqlite:///" + str(_DATA_DEFAULT / "app.db"))
    DATA_DIR = Path(os.environ.get("OMNI_DATA_DIR", str(_DATA_DEFAULT)))
    TOKEN_TTL_HOURS = int(os.environ.get("OMNI_TOKEN_TTL_HOURS", "72"))
    UPLOAD_MAX_MB = int(os.environ.get("OMNI_UPLOAD_MAX_MB", "200"))
    WORKSPACE_QUOTA_MB = int(os.environ.get("OMNI_WORKSPACE_QUOTA_MB", "500"))
    EXEC_TIMEOUT_DEFAULT = int(os.environ.get("OMNI_EXEC_TIMEOUT", "60"))
    EXEC_TIMEOUT_MAX = int(os.environ.get("OMNI_EXEC_TIMEOUT_MAX", "600"))
    EXEC_CPU_SECONDS = int(os.environ.get("OMNI_EXEC_CPU_SECONDS", "120"))
    EXEC_MEM_MB = int(os.environ.get("OMNI_EXEC_MEM_MB", "768"))
    EXEC_MAX_PROCS = int(os.environ.get("OMNI_EXEC_MAX_PROCS", "128"))
    RATE_LIMIT_PER_MIN = int(os.environ.get("OMNI_RATE_LIMIT_PER_MIN", "240"))
    GIT_MAX_MB = 64

CFG = Config()
CFG.DATA_DIR.mkdir(parents=True, exist_ok=True)
(CFG.DATA_DIR / "workspaces").mkdir(parents=True, exist_ok=True)
(CFG.DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)
