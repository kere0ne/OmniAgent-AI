import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .db import init_db
from .config import CFG
from .routers import auth, projects, terminal, chat, agents, models, git, preview
from .services.workspaces import PathError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("omniagent")

app = FastAPI(title=CFG.APP_NAME, version=CFG.VERSION,
              docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # same-origin in production (served by this app); tighten for split deploys
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, projects, terminal, chat, agents, models, git, preview):
    app.include_router(r.router)

@app.on_event("startup")
def startup():
    init_db()
    log.info("OmniAgent AI %s ready; data dir %s", CFG.VERSION, CFG.DATA_DIR)

@app.exception_handler(PathError)
def path_error_handler(request: Request, exc: PathError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

@app.get("/api/health")
def health():
    return {"ok": True, "app": CFG.APP_NAME, "version": CFG.VERSION}

_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        f = _dist / full_path
        if full_path and f.is_file():
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
